"""Consent-gated camera tether: YOUR camera/video → VeilLock → call apps.

Default: the public feed is a natural camera/video veil. The veil lifts
only when (a) the user turns obfuscation off, or (b) the user accepts a
call through AZ-OS. PulseCheck must PASS or the virtual camera still
receives veil noise — never plaintext.

Author: Aziel Eliab.
"""

from __future__ import annotations

import sys
import threading
from dataclasses import dataclass, field
from typing import Any, Iterator, TextIO

import numpy as np

from veillock.azos import AzosHook
from veillock.engine import EncryptedFrame, VeilLockSession
from veillock.modes import Mode, public_veil, synthetic_ui_noise
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck
from veillock.sources import (
    DEFAULT_HEIGHT,
    DEFAULT_WIDTH,
    InstallError,
    open_source,
    resize_rgb,
)

DEVICE_NAME = "VeilLock"
DEFAULT_FPS = 15.0
DEFAULT_MODE = "obfuscation"
DEFAULT_SOURCE = "camera"

APPS_GUIDE = """\
VeilLock — consent-gated camera protection via AZ-OS
====================================================

Your camera or screen. The public feed is a natural privacy veil unless
you turn obfuscation off, or you accept a call through AZ-OS. You control
both paths.

What is encrypted, and what is only obfuscated
----------------------------------------------
Live call video is a keyed visual scramble (shuffled 8×8 tiles) once you
lift the veil for a protected call (`veillock wrap --feed scramble`).
An authorized peer can approximately reverse it. It is not AES-256-GCM.
The call provider sees the veil or the tiles.
Live call audio is a comfort-noise veil by default, or an optional PCM
block permutation. Opus and AAC do not carry sample ciphertext. That
path is not AES-256-GCM. Short blocks can still contain speech fragments.
VeilLock's own file (`veillock record` / `veillock play`) is AES-256-GCM
per frame and per audio chunk, with key rotation and PulseCheck.
PulseCheck failure halts to veil or noise. Plaintext is not sent.

Install the optional extra, then start the tether:

  pip install 'veillock[tether]'
  veillock tether --source camera --mode obfuscation --device 0

Default: people on the call see a natural camera/video veil, not your
plaintext camera. PulseCheck must PASS or the feed stays veiled (never
plaintext).

Lift the veil (your choice):

  veillock tether --obfuscation-off
  veillock tether --azos-accept --actor "your name"

Linux (v4l2loopback), once per boot if the VeilLock device is missing:

  sudo modprobe v4l2loopback devices=1 video_nr=10 card_label=VeilLock exclusive_caps=1

Microphone — the name the call app actually shows
  Linux: VeilLock Microphone.
    `veillock wrap --mic` or `veillock mic start` loads module-null-sink
    and module-remap-source through pactl, and paplay feeds the sink.
    Stop unloads both modules. This needs pipewire-pulse or PulseAudio.
    VeilLock creates that source. It is not a kernel driver.
  macOS: BlackHole 2ch, and only if BlackHole is already installed.
    No CoreAudio HAL plugin is shipped. The selectable name is not VeilLock.
    sox or ffmpeg feeds BlackHole.
  Windows: CABLE Output, and only if VB-Audio Virtual Cable is installed.
    No kernel driver is shipped. VeilLock writes to CABLE Input. The
    selectable microphone is CABLE Output, not VeilLock.
  Default public audio is comfort noise. It becomes the real microphone
  only after you lift the veil, or a PCM scramble if you passed
  `--audio-feed scramble`. That call audio is not AES-256-GCM. The real
  microphone can still be sealed into the `.veilrec` file at the same time.

Zoom (desktop)
  Settings → Video → Camera → VeilLock
  Settings → Audio → Microphone → the name in the Microphone section

Skype (desktop)
  Settings → Audio & Video → Camera → VeilLock
  Settings → Audio & Video → Microphone → the name in the Microphone section

FaceTime (Mac)
  Video menu → VeilLock
  Microphone menu → BlackHole 2ch, if BlackHole is installed
  Desktop FaceTime can select a third-party virtual camera.
  iPhone FaceTime cannot select a third-party virtual camera or microphone.

Google Meet (desktop browser)
  Meeting → More → Settings → Video → Camera → VeilLock
  Settings → Audio → Microphone → the name in the Microphone section
  Allow the browser to use those devices.

Microsoft Teams (desktop)
  Settings → Devices → Camera → VeilLock
  Settings → Devices → Microphone → the name in the Microphone section

Discord (desktop app or browser)
  User Settings → Voice & Video → Camera → VeilLock
  Input Device → the name in the Microphone section
  Browser Discord uses the same site permission prompt as other WebRTC calls.

WhatsApp (desktop)
  Call screen → camera menu → VeilLock, when the desktop app offers a
  camera picker. Microphone → the name in the Microphone section.
  WhatsApp on a phone cannot select a third-party camera or microphone.

Signal (desktop)
  Call device menu → Camera → VeilLock, when the desktop app offers it.
  Microphone → the name in the Microphone section.
  Signal on a phone cannot select a third-party camera or microphone.

OBS
  Sources → Video Capture Device → VeilLock
  Audio Input Capture → the name in the Microphone section
  An OBS recording of that source stores the veil or the scramble.
  It is not the AES-256-GCM file from `veillock record`.

Browser WebRTC (Meet, Discord, and other sites)
  Site permission → Camera → VeilLock
  Site permission → Microphone → the name in the Microphone section

iPhone FaceTime cannot select a third-party camera or microphone.

Android / iOS
  iPhone FaceTime, Zoom iOS, and most mobile clients cannot select a
  third-party virtual camera. Use the desktop app (Mac FaceTime / Zoom /
  Skype / Meet / Teams).
"""

from veillock.coverage import coverage_guide_text
from veillock.engulf import engulf_guide_text
from veillock.honesty import EXPORT_LEAVES, LOCAL_RECORDING

APPS_GUIDE = (
    APPS_GUIDE
    + engulf_guide_text()
    + coverage_guide_text()
    + "\nRecordings stay inside VeilLock\n------------------------------\n"
    + LOCAL_RECORDING
    + "\n"
    + EXPORT_LEAVES
    + "\n"
)


def _require_pyvirtualcam():
    try:
        import pyvirtualcam  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InstallError(
            "Virtual camera requires pyvirtualcam. Install with: pip install 'veillock[tether]'"
        ) from exc
    return pyvirtualcam


def _linux_v4l2_named(name: str = DEVICE_NAME) -> str | None:
    """Find a v4l2loopback node whose card label contains ``name``."""
    import glob

    needle = name.lower()
    for path in glob.glob("/sys/class/video4linux/video*/name"):
        try:
            with open(path, encoding="utf-8") as fh:
                label = fh.read().strip()
        except OSError:
            continue
        if needle in label.lower():
            node = path.rsplit("/", 2)[-2]
            return f"/dev/{node}"
    return None


def open_virtual_camera(
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    fps: float = DEFAULT_FPS,
    name: str = DEVICE_NAME,
):
    """Open a virtual camera advertised as VeilLock when the backend allows it."""
    pvc = _require_pyvirtualcam()
    kwargs: dict[str, Any] = {
        "width": int(width),
        "height": int(height),
        "fps": float(fps),
    }
    fmt = getattr(getattr(pvc, "PixelFormat", None), "RGB", None)
    if fmt is not None:
        kwargs["fmt"] = fmt

    linux_dev = _linux_v4l2_named(name)
    attempts: list[dict[str, Any]] = []
    if linux_dev:
        attempts.append({"device": linux_dev})
    attempts.append({"device": name})
    attempts.append({})

    last_err: Exception | None = None
    for extra in attempts:
        try:
            return pvc.Camera(**kwargs, **extra)
        except TypeError:
            continue
        except Exception as exc:  # noqa: BLE001
            last_err = exc
            continue
    hint = (
        " Could not open a virtual camera named VeilLock. "
        "On Linux load v4l2loopback with card_label=VeilLock "
        "(see `veillock apps`)."
    )
    if last_err is not None:
        raise RuntimeError(str(last_err) + hint) from last_err
    raise RuntimeError("pyvirtualcam.Camera rejected the VeilLock constructor." + hint)


@dataclass
class TetherConfig:
    source: str = DEFAULT_SOURCE
    mode: str = DEFAULT_MODE
    device: int | str = 0
    width: int = DEFAULT_WIDTH
    height: int = DEFAULT_HEIGHT
    fps: float = DEFAULT_FPS
    trusted: bool = False
    obfuscation_off: bool = False
    azos_accept: bool = False
    actor: str = ""
    session_key: bytes | None = None
    receiver_secret: bytes | None = None
    pulse: PulseCheck | None = None
    rotation_interval: int = 120
    max_frames: int | None = None
    rng: np.random.Generator | None = None
    feed: str = "auto"
    scramble_key: bytes | None = None
    azos: AzosHook = field(default_factory=AzosHook)

    def apply_consent(self) -> AzosHook:
        hook = self.azos
        if self.obfuscation_off or self.trusted:
            hook.set_obfuscation(False)
        if self.azos_accept:
            hook.accept_call(actor=self.actor or "user")
        return hook


@dataclass
class PublicFrame:
    """Pixels the call app will encode, plus the AES frame if sealing succeeded."""

    pixels: np.ndarray
    label: str
    sealed: EncryptedFrame | None


def _veiled_public(
    session: VeilLockSession,
    sealed: EncryptedFrame,
    src: np.ndarray,
    noise_rng: np.random.Generator,
    source: str,
    tick: int,
) -> np.ndarray:
    if str(source).strip().lower() in ("camera", "video"):
        return public_veil(src, noise_rng, source=source, tick=tick)
    if session.mode is Mode.OBFUSCATION and sealed.decoy is not None:
        return np.ascontiguousarray(sealed.decoy, dtype=np.uint8)
    h, w, c = int(src.shape[0]), int(src.shape[1]), int(src.shape[2])
    return synthetic_ui_noise((h, w, c), noise_rng)


def compose_call_frame(
    session: VeilLockSession,
    frame: np.ndarray,
    *,
    trusted: bool = False,
    rng: np.random.Generator | None = None,
    hook: AzosHook | None = None,
    source: str = DEFAULT_SOURCE,
    tick: int = 0,
    feed: str = "auto",
    scramble_key: bytes | None = None,
    epoch: int = 0,
) -> PublicFrame:
    """Choose the public pixels. Pulse halt returns a veil and no sealed frame.

    ``feed``:
    - ``auto`` — veil until you lift it, then the trusted decode (existing tether)
    - ``veil`` — natural veil even after a lift
    - ``scramble`` — after a lift, keyed visual scramble (not AES-256-GCM)
    - ``plaintext`` — after a lift, the camera
    """
    from veillock.scramble import scramble_frame

    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    noise_rng = rng if rng is not None else np.random.default_rng()
    gate = hook if hook is not None else AzosHook()
    if trusted:
        gate.set_obfuscation(False)
    feed_name = str(feed or "auto").strip().lower()
    if feed_name not in ("auto", "veil", "scramble", "plaintext"):
        raise ValueError("feed must be auto, veil, scramble, or plaintext")
    try:
        sealed, display = session.protect_frame(src)
    except (HaltedError, PhoenixError):
        return PublicFrame(
            pixels=public_veil(src, noise_rng, source=source, tick=tick),
            label="pulse-halt",
            sealed=None,
        )
    if feed_name == "veil" or gate.veil_on():
        return PublicFrame(
            pixels=_veiled_public(session, sealed, src, noise_rng, source, tick),
            label="veil",
            sealed=sealed,
        )
    if feed_name == "scramble":
        if scramble_key is None or len(bytes(scramble_key)) != 32:
            raise ValueError("scramble feed requires a 32-byte key")
        return PublicFrame(
            pixels=scramble_frame(np.ascontiguousarray(display, dtype=np.uint8), bytes(scramble_key), epoch),
            label="scramble",
            sealed=sealed,
        )
    return PublicFrame(
        pixels=np.ascontiguousarray(display, dtype=np.uint8),
        label="plaintext",
        sealed=sealed,
    )


def emit_public_frame(
    session: VeilLockSession,
    frame: np.ndarray,
    *,
    trusted: bool = False,
    rng: np.random.Generator | None = None,
    hook: AzosHook | None = None,
    source: str = DEFAULT_SOURCE,
    tick: int = 0,
    feed: str = "auto",
    scramble_key: bytes | None = None,
    epoch: int = 0,
) -> np.ndarray:
    """Encrypt a caller-owned frame and choose pixels for the virtual camera.

    Default public feed is a natural camera/video veil. The veil lifts
    when the user turns obfuscation off, accepts a call through AZ-OS,
    or passes ``trusted``. Pulse halt / Phoenix → veil, never plaintext.
    ``feed="scramble"`` lifts to a keyed visual scramble, not AES-256-GCM.
    """
    return compose_call_frame(
        session,
        frame,
        trusted=trusted,
        rng=rng,
        hook=hook,
        source=source,
        tick=tick,
        feed=feed,
        scramble_key=scramble_key,
        epoch=epoch,
    ).pixels


def halt_noise(width: int, height: int, rng: np.random.Generator | None = None) -> np.ndarray:
    """Veil used when PCI fails and no plaintext may leave."""
    noise_rng = rng if rng is not None else np.random.default_rng()
    blank = np.zeros((int(height), int(width), 3), dtype=np.uint8)
    return public_veil(blank, noise_rng, source="camera", tick=0)


def run_tether(
    config: TetherConfig | None = None,
    *,
    frame_source: Iterator[np.ndarray] | None = None,
    virtual_cam: Any = None,
    stop_event: threading.Event | None = None,
    log: TextIO | None = None,
) -> int:
    """Grab → encrypt → write the public feed to the VeilLock virtual camera.

    ``frame_source`` and ``virtual_cam`` are injectable so tests never need
    a physical camera. Returns the number of frames sent.
    """
    cfg = config if config is not None else TetherConfig()
    mode = Mode.parse(cfg.mode)
    pulse: PulseCheck = cfg.pulse if cfg.pulse is not None else AlwaysPass()
    rng = cfg.rng if cfg.rng is not None else np.random.default_rng()
    out = log if log is not None else sys.stdout
    width, height = int(cfg.width), int(cfg.height)
    hook = cfg.apply_consent()

    receiver_secret = cfg.receiver_secret
    if mode is Mode.BROADCAST and receiver_secret is None:
        import secrets as _secrets

        receiver_secret = _secrets.token_bytes(32)

    session = VeilLockSession(
        session_key=cfg.session_key,
        rotation_interval=cfg.rotation_interval,
        mode=mode,
        pulse=pulse,
        receiver_secret=receiver_secret,
        rng=rng,
    )

    owns_source = frame_source is None
    source: Any = frame_source
    if source is None:
        source = open_source(
            cfg.source,
            device=cfg.device,
            width=width,
            height=height,
            pulse=pulse,
        )

    owns_cam = virtual_cam is None
    cam = virtual_cam
    sent = 0
    try:
        if cam is None:
            cam = open_virtual_camera(width=width, height=height, fps=cfg.fps, name=DEVICE_NAME)
            enter = getattr(cam, "__enter__", None)
            if enter is not None:
                cam = enter()
        out.write(
            f"VeilLock tether  device={DEVICE_NAME}  "
            f"{width}x{height}@{cfg.fps:g}fps  "
            f"source={cfg.source}  mode={mode.value}  "
            f"veil={'on' if hook.veil_on() else 'lifted'}  "
            f"reason={hook.reason()}\n"
        )
        out.write(
            "Consent-gated camera protection via AZ-OS. "
            "Pick camera VeilLock in Zoom / Skype / desktop FaceTime / Meet / Teams. "
            "iPhone FaceTime cannot select a third-party virtual camera (Apple).\n"
        )
        if mode is Mode.BROADCAST and receiver_secret is not None:
            out.write(f"receiver_secret={receiver_secret.hex()}\n")
        out.write(f"session_key={session.current_key.hex()}\n")
        out.flush()

        while True:
            if stop_event is not None and stop_event.is_set():
                break
            if cfg.max_frames is not None and sent >= cfg.max_frames:
                break
            try:
                frame = next(source)
            except StopIteration:
                break
            except HaltedError:
                public = halt_noise(width, height, rng)
            else:
                frame = resize_rgb(frame, width, height)
                scramble_key = cfg.scramble_key if cfg.scramble_key is not None else cfg.session_key
                public = emit_public_frame(
                    session,
                    frame,
                    trusted=bool(cfg.trusted),
                    rng=rng,
                    hook=hook,
                    source=cfg.source,
                    tick=sent,
                    feed=cfg.feed,
                    scramble_key=scramble_key,
                    epoch=sent // int(cfg.rotation_interval),
                )
                if str(cfg.feed) != "scramble":
                    public = resize_rgb(public, width, height)
            send = getattr(cam, "send", None)
            if send is None:
                raise RuntimeError("virtual camera has no send()")
            send(np.ascontiguousarray(public, dtype=np.uint8))
            sleeper = getattr(cam, "sleep_until_next_frame", None)
            if sleeper is not None:
                sleeper()
            sent += 1
    finally:
        if owns_cam and cam is not None:
            closer = getattr(cam, "__exit__", None)
            if closer is not None:
                closer(None, None, None)
            else:
                close = getattr(cam, "close", None)
                if close is not None:
                    close()
        if owns_source:
            close = getattr(source, "close", None)
            if close is not None:
                close()
    return sent


class TetherRuntime:
    """Background tether for the localhost UI (Start/Stop + AZ-OS consent)."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._error: str | None = None
        self._running = False
        self._cfg: TetherConfig | None = None
        self.azos = AzosHook()

    def status(self) -> dict[str, Any]:
        with self._lock:
            hook = self.azos.status()
            return {
                "running": self._running,
                "error": self._error,
                "source": None if self._cfg is None else self._cfg.source,
                "mode": None if self._cfg is None else self._cfg.mode,
                "trusted": None if self._cfg is None else (not self.azos.obfuscation_on),
                "device_name": DEVICE_NAME,
                **hook,
            }

    def start(self, config: TetherConfig) -> dict[str, Any]:
        try:
            Mode.parse(config.mode)
            if str(config.source).strip().lower() not in ("camera", "screen"):
                raise ValueError("source must be camera or screen")
            _require_pyvirtualcam()
            if str(config.source).strip().lower() == "camera":
                from veillock.sources import _require_cv2

                _require_cv2()
        except (InstallError, ValueError) as exc:
            return {"ok": False, "error": str(exc), "running": False, "device_name": DEVICE_NAME}
        with self._lock:
            if self._running:
                return {"ok": False, "error": "tether already running", **self.status()}
            config.azos = self.azos
            config.apply_consent()
            self._stop = threading.Event()
            self._error = None
            self._cfg = config
            self._running = True
            stop = self._stop

            def _worker() -> None:
                try:
                    run_tether(config, stop_event=stop)
                except Exception as exc:  # noqa: BLE001
                    with self._lock:
                        self._error = str(exc)
                finally:
                    with self._lock:
                        self._running = False

            thread = threading.Thread(target=_worker, name="veillock-tether", daemon=True)
            self._thread = thread
            thread.start()
            return {"ok": True, **self.status()}

    def stop(self) -> dict[str, Any]:
        with self._lock:
            self._stop.set()
            thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)
        with self._lock:
            self._running = False
            return {"ok": True, **self.status()}

    def accept_call(self, actor: str = "", call_id: str | None = None) -> dict[str, Any]:
        with self._lock:
            self.azos.accept_call(actor=actor, call_id=call_id)
            return {"ok": True, **self.status()}

    def end_call(self) -> dict[str, Any]:
        with self._lock:
            self.azos.end_call()
            return {"ok": True, **self.status()}

    def set_obfuscation(self, on: bool) -> dict[str, Any]:
        with self._lock:
            self.azos.set_obfuscation(on)
            return {"ok": True, **self.status()}


RUNTIME = TetherRuntime()


def run_from_args(args: Any) -> int:
    """CLI entry used by ``veillock tether``."""
    cfg = TetherConfig(
        source=str(getattr(args, "source", DEFAULT_SOURCE)),
        mode=str(getattr(args, "mode", DEFAULT_MODE)),
        device=getattr(args, "device", 0),
        width=int(getattr(args, "width", DEFAULT_WIDTH)),
        height=int(getattr(args, "height", DEFAULT_HEIGHT)),
        fps=float(getattr(args, "fps", DEFAULT_FPS)),
        trusted=bool(getattr(args, "trusted", False)),
        obfuscation_off=bool(getattr(args, "obfuscation_off", False)),
        azos_accept=bool(getattr(args, "azos_accept", False)),
        actor=str(getattr(args, "actor", "") or ""),
    )
    try:
        run_tether(cfg)
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped\n")
        return 0
    except InstallError as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    except (HaltedError, PhoenixError, ValueError, RuntimeError) as exc:
        sys.stderr.write(f"error: {exc}\n")
        return 2
    return 0
