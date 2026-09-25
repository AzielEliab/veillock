"""Virtual microphone the call app can select.

Linux is the only platform where VeilLock creates the device. ``pactl``
loads a null sink and a remap source. Apps then see a source described
as ``VeilLock Microphone`` (source name ``VeilLock``). ``paplay`` feeds
that sink. Stop unloads both modules. This is not a kernel driver. It
needs ``pactl`` and ``paplay`` from pipewire-pulse or PulseAudio.

macOS: no CoreAudio HAL plugin is shipped. If BlackHole is already
installed, playback is aimed at ``BlackHole 2ch`` (or 16ch) with sox or
ffmpeg. The call app selects that BlackHole name, not VeilLock.

Windows: no kernel driver is shipped. If VB-Audio Virtual Cable is
already installed, playback is aimed at ``CABLE Input``. The call app
selects ``CABLE Output`` as its microphone.

Call audio that leaves this device is comfort noise, the real
microphone, or a PCM scramble. None of those are AES-256-GCM.

Author: Aziel Eliab.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

import numpy as np

from veillock.audio import AUDIO_BLOCK, comfort_noise, scramble_pcm
from veillock.honesty import CALL_AUDIO

SELECTABLE_LINUX = "VeilLock Microphone"
SOURCE_NAME = "VeilLock"
SINK_NAME = "veillock_sink"
RATE = 16000
BLACKHOLE_2CH = "BlackHole 2ch"
BLACKHOLE_16CH = "BlackHole 16ch"
CABLE_PLAYBACK = "CABLE Input"
CABLE_MIC = "CABLE Output"
BLACKHOLE_PATHS = (
    ("/Library/Audio/Plug-Ins/HAL/BlackHole2ch.driver", BLACKHOLE_2CH),
    ("/Library/Audio/Plug-Ins/HAL/BlackHole16ch.driver", BLACKHOLE_16CH),
)


@dataclass
class MicStatus:
    """What this machine can actually offer a call app."""

    ok: bool
    running: bool
    platform: str
    backend: str
    selectable_name: str | None
    created_by_veillock: bool
    call_audio_aes_256_gcm: bool
    note: str
    error: str | None = None
    tools: dict[str, bool] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "running": self.running,
            "platform": self.platform,
            "backend": self.backend,
            "selectable_name": self.selectable_name,
            "created_by_veillock": self.created_by_veillock,
            "call_audio_aes_256_gcm": self.call_audio_aes_256_gcm,
            "note": self.note,
            "error": self.error,
            "tools": dict(self.tools),
            "author": "Aziel Eliab",
        }


class _Stdin:
    def write(self, data: bytes) -> None: ...

    def flush(self) -> None: ...

    def close(self) -> None: ...


class CommandIO:
    """Process stand-in. Tests record stdin and script stdout."""

    def __init__(self, stdout: bytes = b"", returncode: int = 0) -> None:
        self.stdout = stdout
        self.returncode = returncode
        self.stdin_buf = bytearray()
        self.closed = False

    def write(self, data: bytes) -> None:
        self.stdin_buf.extend(data)

    def flush(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True


class CommandRunner:
    """subprocess wrapper. Tests replace ``which``, ``run``, and ``popen``."""

    def which(self, name: str) -> str | None:
        return shutil.which(name)

    def run(self, argv: Sequence[str]) -> CommandIO:
        proc = subprocess.run(list(argv), check=False, capture_output=True)
        out = CommandIO(stdout=proc.stdout or b"", returncode=int(proc.returncode))
        if proc.returncode != 0:
            err = (proc.stderr or b"").decode("utf-8", errors="replace").strip()
            out.stdout = (proc.stdout or b"") + b"\n" + err.encode("utf-8")
        return out

    def popen(self, argv: Sequence[str]) -> Any:
        return subprocess.Popen(
            list(argv),
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )


def host_platform(name: str | None = None) -> str:
    raw = name if name is not None else sys.platform
    key = str(raw).lower()
    if key.startswith("linux"):
        return "linux"
    if key == "darwin":
        return "darwin"
    if key.startswith("win"):
        return "windows"
    return key


def choose_public_pcm(
    chunk: np.ndarray,
    *,
    audio_feed: str,
    lifted: bool,
    pulse_ok: bool,
    key: bytes | None,
    epoch: int,
    rng: np.random.Generator,
) -> tuple[np.ndarray, str]:
    """Public samples for one mic chunk.

    Comfort noise unless the user has lifted the veil. Scramble is opt-in
    and still not AES. Pulse failure is noise, never the microphone.
    """
    feed = str(audio_feed or "off").strip().lower()
    samples = np.ascontiguousarray(chunk, dtype=np.int16).ravel()
    if feed in ("off", "none"):
        return np.zeros((0,), dtype=np.int16), "off"
    if not pulse_ok:
        return comfort_noise(int(samples.shape[0]), rng), "veil"
    if not lifted or feed == "veil":
        return comfort_noise(int(samples.shape[0]), rng), "veil"
    if feed == "scramble":
        if key is None or len(bytes(key)) != 32:
            raise ValueError("scramble audio requires a 32-byte key")
        return scramble_pcm(samples, bytes(key), epoch=epoch), "scramble"
    if feed in ("auto", "plaintext"):
        return samples.copy(), "plaintext"
    raise ValueError("audio_feed must be off, veil, auto, plaintext, or scramble")


def _tool_map(runner: CommandRunner, names: Sequence[str]) -> dict[str, bool]:
    return {name: runner.which(name) is not None for name in names}


def _note_linux(tools: Mapping[str, bool]) -> str:
    missing = [name for name in ("pactl", "paplay") if not tools.get(name)]
    base = (
        "Linux creates the microphone. pactl loads module-null-sink "
        f"({SINK_NAME}) and module-remap-source (source name {SOURCE_NAME}, "
        f"description {SELECTABLE_LINUX}). paplay writes the public PCM into "
        "the sink. Stop unloads both modules. This is not a kernel driver. "
        "Call audio is obfuscated, not AES-256-GCM. " + CALL_AUDIO
    )
    if missing:
        return base + " Missing on PATH: " + ", ".join(missing) + "."
    return base


def _note_mac(found: str | None, tools: Mapping[str, bool]) -> str:
    player = "sox" if tools.get("sox") else ("ffmpeg" if tools.get("ffmpeg") else None)
    if found is None:
        return (
            "macOS: VeilLock does not ship a CoreAudio HAL plugin, so it "
            "cannot create a device named VeilLock. Install BlackHole, then "
            "the call app selects BlackHole 2ch. sox or ffmpeg feeds that "
            "device. Call audio is obfuscated, not AES-256-GCM."
        )
    if player is None:
        return (
            f"BlackHole is installed ({found}). The call app selects {found}, "
            "not a device named VeilLock. sox or ffmpeg is required to feed "
            "it and neither is on PATH. No CoreAudio plugin is shipped. "
            "Call audio is obfuscated, not AES-256-GCM."
        )
    return (
        f"macOS routes into the installed device {found} using {player}. "
        f"The call app selects {found}, not VeilLock. No CoreAudio plugin "
        "is shipped. Call audio is obfuscated, not AES-256-GCM."
    )


def _note_windows(found: bool, tools: Mapping[str, bool]) -> str:
    if not found:
        return (
            "Windows: VeilLock does not ship a kernel audio driver. Install "
            "VB-Audio Virtual Cable. The call app selects CABLE Output. "
            "VeilLock writes to CABLE Input. ffmpeg is required to feed it. "
            "Call audio is obfuscated, not AES-256-GCM."
        )
    if not tools.get("ffmpeg"):
        return (
            "VB-Audio Virtual Cable looks installed. The call app selects "
            "CABLE Output, not a device named VeilLock. ffmpeg is not on "
            "PATH, so VeilLock cannot feed CABLE Input yet. No kernel driver "
            "is shipped. Call audio is obfuscated, not AES-256-GCM."
        )
    return (
        "Windows routes into the installed VB-Audio device CABLE Input "
        "using ffmpeg. The call app selects CABLE Output as the microphone, "
        "not VeilLock. No kernel driver is shipped. Call audio is obfuscated, "
        "not AES-256-GCM."
    )


class VirtualMicrophone:
    """One virtual-mic session. ``runner`` is injectable so tests need no device."""

    def __init__(
        self,
        *,
        runner: CommandRunner | None = None,
        platform: str | None = None,
        path_exists: Callable[[str], bool] | None = None,
        playback_devices: Sequence[str] | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        self.runner = runner if runner is not None else CommandRunner()
        self.platform = host_platform(platform)
        self._path_exists = path_exists if path_exists is not None else os.path.exists
        self._playback_devices = list(playback_devices) if playback_devices is not None else None
        self._rng = rng if rng is not None else np.random.default_rng()
        self._lock = threading.RLock()
        self._running = False
        self._modules: list[str] = []
        self._proc: Any = None
        self._stdin: Any = None
        self._selectable: str | None = None
        self._backend = "unavailable"
        self._created = False
        self._error: str | None = None

    def probe(self) -> MicStatus:
        with self._lock:
            return self._describe(running=self._running)

    def start(self) -> MicStatus:
        with self._lock:
            if self._running:
                return self._describe(running=True)
            self._error = None
            self._modules = []
            try:
                if self.platform == "linux":
                    self._start_linux()
                elif self.platform == "darwin":
                    self._start_darwin()
                elif self.platform == "windows":
                    self._start_windows()
                else:
                    raise RuntimeError(
                        f"No virtual microphone for platform {self.platform}. "
                        "Call audio is obfuscated, not AES-256-GCM."
                    )
            except Exception as exc:  # noqa: BLE001
                self._teardown_locked()
                self._error = str(exc)
                self._running = False
                status = self._describe(running=False)
                status.ok = False
                status.error = self._error
                return status
            self._running = True
            return self._describe(running=True)

    def write(self, pcm: np.ndarray) -> None:
        raw = np.ascontiguousarray(pcm, dtype=np.int16).ravel().tobytes()
        with self._lock:
            if not self._running or self._stdin is None:
                raise RuntimeError("virtual microphone is not running")
            self._stdin.write(raw)
            flush = getattr(self._stdin, "flush", None)
            if flush is not None:
                flush()

    def stop(self) -> MicStatus:
        with self._lock:
            self._teardown_locked()
            self._running = False
            return self._describe(running=False)

    def _describe(self, *, running: bool) -> MicStatus:
        if self.platform == "linux":
            tools = _tool_map(self.runner, ("pactl", "paplay", "parecord"))
            name = SELECTABLE_LINUX
            backend = "pulse-remap"
            created = bool(running)
            note = _note_linux(tools)
        elif self.platform == "darwin":
            tools = _tool_map(self.runner, ("sox", "ffmpeg"))
            found = self._blackhole_name()
            name = found
            backend = "blackhole" if found else "unavailable"
            created = False
            note = _note_mac(found, tools)
        elif self.platform == "windows":
            tools = _tool_map(self.runner, ("ffmpeg",))
            found = self._cable_playback()
            name = CABLE_MIC if found else None
            backend = "vb-cable" if found else "unavailable"
            created = False
            note = _note_windows(found is not None, tools)
        else:
            tools = {}
            name = None
            backend = "unavailable"
            created = False
            note = "This platform has no VeilLock microphone. Call audio is obfuscated, not AES-256-GCM."
        if running and self._selectable:
            name = self._selectable
        return MicStatus(
            ok=self._error is None,
            running=running,
            platform=self.platform,
            backend=self._backend if running else backend,
            selectable_name=name,
            created_by_veillock=created,
            call_audio_aes_256_gcm=False,
            note=note,
            error=self._error,
            tools=tools,
        )

    def _start_linux(self) -> None:
        if self.runner.which("pactl") is None or self.runner.which("paplay") is None:
            raise RuntimeError(
                "Linux microphone needs pactl and paplay (pipewire-pulse or "
                "pulseaudio). VeilLock does not ship a kernel audio driver."
            )
        sink = self._load(
            [
                "pactl",
                "load-module",
                "module-null-sink",
                f"sink_name={SINK_NAME}",
                "sink_properties=device.description=VeilLock",
            ]
        )
        try:
            self._load(
                [
                    "pactl",
                    "load-module",
                    "module-remap-source",
                    f"source_name={SOURCE_NAME}",
                    f"master={SINK_NAME}.monitor",
                    "source_properties=device.description=VeilLock Microphone",
                ]
            )
        except RuntimeError:
            if sink in self._modules:
                self._modules.remove(sink)
            self._unload(sink)
            raise
        proc = self.runner.popen(
            [
                "paplay",
                f"--device={SINK_NAME}",
                "--raw",
                "--format=s16le",
                f"--rate={RATE}",
                "--channels=1",
            ]
        )
        stdin = getattr(proc, "stdin", None)
        if stdin is None:
            raise RuntimeError("paplay did not provide stdin")
        self._proc = proc
        self._stdin = stdin
        self._backend = "pulse-remap"
        self._created = True
        self._selectable = SELECTABLE_LINUX

    def _start_darwin(self) -> None:
        found = self._blackhole_name()
        if found is None:
            raise RuntimeError(
                "BlackHole is not installed. VeilLock does not ship a "
                "CoreAudio HAL plugin and cannot create a VeilLock microphone."
            )
        if self.runner.which("sox") is not None:
            argv = [
                "sox",
                "-t",
                "raw",
                "-r",
                str(RATE),
                "-e",
                "signed-integer",
                "-b",
                "16",
                "-c",
                "1",
                "-",
                "-t",
                "coreaudio",
                found,
            ]
        elif self.runner.which("ffmpeg") is not None:
            argv = [
                "ffmpeg",
                "-f",
                "s16le",
                "-ar",
                str(RATE),
                "-ac",
                "1",
                "-i",
                "pipe:0",
                "-f",
                "audiotoolbox",
                found,
            ]
        else:
            raise RuntimeError(
                f"{found} is installed, but sox and ffmpeg are missing, so "
                "VeilLock cannot feed it. No CoreAudio plugin is shipped."
            )
        proc = self.runner.popen(argv)
        stdin = getattr(proc, "stdin", None)
        if stdin is None:
            raise RuntimeError("audio player did not provide stdin")
        self._proc = proc
        self._stdin = stdin
        self._backend = "blackhole"
        self._created = False
        self._selectable = found

    def _start_windows(self) -> None:
        playback = self._cable_playback()
        if playback is None:
            raise RuntimeError(
                "VB-Audio Virtual Cable is not installed. VeilLock does not "
                "ship a Windows audio driver."
            )
        if self.runner.which("ffmpeg") is None:
            raise RuntimeError(
                "CABLE Input is installed, but ffmpeg is not on PATH, so "
                "VeilLock cannot feed it. No kernel driver is shipped."
            )
        proc = self.runner.popen(
            [
                "ffmpeg",
                "-f",
                "s16le",
                "-ar",
                str(RATE),
                "-ac",
                "1",
                "-i",
                "pipe:0",
                "-f",
                "wasapi",
                playback,
            ]
        )
        stdin = getattr(proc, "stdin", None)
        if stdin is None:
            raise RuntimeError("ffmpeg did not provide stdin")
        self._proc = proc
        self._stdin = stdin
        self._backend = "vb-cable"
        self._created = False
        self._selectable = CABLE_MIC

    def _blackhole_name(self) -> str | None:
        for path, label in BLACKHOLE_PATHS:
            if self._path_exists(path):
                return label
        return None

    def _cable_playback(self) -> str | None:
        devices = self._playback_devices
        if devices is None:
            devices = _windows_playback_names(self.runner)
        for name in devices:
            if "CABLE Input" in name or name.strip() == CABLE_PLAYBACK:
                return name
        return None

    def _load(self, argv: Sequence[str]) -> str:
        result = self.runner.run(argv)
        text = bytes(getattr(result, "stdout", b"") or b"").decode("utf-8", errors="replace")
        if int(getattr(result, "returncode", 1)) != 0:
            raise RuntimeError(text.strip() or "pactl load-module failed")
        index = ""
        for line in text.splitlines():
            token = line.strip()
            if token.isdigit():
                index = token
        if not index:
            raise RuntimeError("pactl did not return a module index: " + text.strip())
        self._modules.append(index)
        return index

    def _unload(self, index: str) -> None:
        self.runner.run(["pactl", "unload-module", index])

    def _teardown_locked(self) -> None:
        stdin = self._stdin
        self._stdin = None
        if stdin is not None:
            close = getattr(stdin, "close", None)
            if close is not None:
                try:
                    close()
                except Exception:  # noqa: BLE001
                    pass
        proc = self._proc
        self._proc = None
        if proc is not None:
            terminate = getattr(proc, "terminate", None)
            if terminate is not None:
                try:
                    terminate()
                except Exception:  # noqa: BLE001
                    pass
            wait = getattr(proc, "wait", None)
            if wait is not None:
                try:
                    wait(timeout=2)
                except TypeError:
                    try:
                        wait()
                    except Exception:  # noqa: BLE001
                        pass
                except Exception:  # noqa: BLE001
                    pass
        for index in reversed(self._modules):
            try:
                self._unload(index)
            except Exception:  # noqa: BLE001
                pass
        self._modules = []
        self._created = False


def _windows_playback_names(runner: CommandRunner) -> list[str]:
    if runner.which("ffmpeg") is None:
        return []
    result = runner.run(["ffmpeg", "-hide_banner", "-list_devices", "true", "-f", "wasapi", "-i", "dummy"])
    text = bytes(getattr(result, "stdout", b"") or b"").decode("utf-8", errors="replace")
    return [line.strip() for line in text.splitlines() if line.strip()]


class MicRuntime:
    """Start/stop for the loopback UI. The AZ-OS hook decides the veil."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._mic: VirtualMicrophone | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._scramble = False
        self._key = bytes(range(32))
        self._error: str | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            mic = self._mic or VirtualMicrophone()
            payload = mic.probe().as_dict()
            payload["scramble_when_lifted"] = self._scramble
            payload["ui_error"] = self._error
            return payload

    def start(self, *, scramble_when_lifted: bool = False) -> dict[str, Any]:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                return {"ok": False, "error": "microphone already running", **self.status()}
            self._scramble = bool(scramble_when_lifted)
            self._stop = threading.Event()
            self._error = None
            mic = VirtualMicrophone()
            started = mic.start()
            if not started.running:
                self._mic = mic
                return started.as_dict()
            self._mic = mic
            stop = self._stop

            def _loop() -> None:
                from veillock.tether import RUNTIME

                rng = np.random.default_rng()
                capture = _open_default_capture()
                try:
                    while not stop.is_set():
                        raw = capture.read(AUDIO_BLOCK) if capture is not None else np.zeros((AUDIO_BLOCK,), dtype=np.int16)
                        hook = RUNTIME.azos
                        # This panel follows the AZ-OS veil only. PulseCheck
                        # halt-to-noise is enforced by `veillock wrap --mic`.
                        feed = "scramble" if self._scramble else "auto"
                        public, _label = choose_public_pcm(
                            raw,
                            audio_feed=feed,
                            lifted=not hook.veil_on(),
                            pulse_ok=True,
                            key=self._key,
                            epoch=0,
                            rng=rng,
                        )
                        try:
                            mic.write(public)
                        except Exception as exc:  # noqa: BLE001
                            with self._lock:
                                self._error = str(exc)
                            break
                finally:
                    if capture is not None:
                        close = getattr(capture, "close", None)
                        if close is not None:
                            close()

            thread = threading.Thread(target=_loop, name="veillock-mic", daemon=True)
            self._thread = thread
            thread.start()
            return {"ok": True, **self.status()}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop.set()
            thread = self._thread
            mic = self._mic
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        stopped = mic.stop() if mic is not None else VirtualMicrophone().probe()
        with self._lock:
            self._thread = None
            return {"ok": True, **stopped.as_dict()}


class _ParecordCapture:
    def __init__(self, proc: Any) -> None:
        self._proc = proc

    def read(self, n: int) -> np.ndarray:
        stdout = getattr(self._proc, "stdout", None)
        if stdout is None:
            return np.zeros((n,), dtype=np.int16)
        data = stdout.read(int(n) * 2)
        if not data:
            return np.zeros((n,), dtype=np.int16)
        samples = np.frombuffer(data, dtype=np.int16)
        if samples.shape[0] < n:
            pad = np.zeros((n - samples.shape[0],), dtype=np.int16)
            samples = np.concatenate([samples, pad])
        return samples[:n].copy()

    def close(self) -> None:
        terminate = getattr(self._proc, "terminate", None)
        if terminate is not None:
            terminate()


def _open_default_capture() -> _ParecordCapture | None:
    if shutil.which("parecord") is None:
        return None
    proc = subprocess.Popen(
        ["parecord", "--raw", "--format=s16le", f"--rate={RATE}", "--channels=1"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
    )
    return _ParecordCapture(proc)


MIC_RUNTIME = MicRuntime()
