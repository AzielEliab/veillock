"""Virtual microphone: Linux creates the source; macOS and Windows only route."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

import numpy as np
import pytest

from veillock.audio import AUDIO_BLOCK, unveil_pcm
from veillock.mic import (
    BLACKHOLE_2CH,
    CABLE_MIC,
    CABLE_PLAYBACK,
    SELECTABLE_LINUX,
    SOURCE_NAME,
    CommandIO,
    VirtualMicrophone,
    choose_public_pcm,
)
from veillock.tether import APPS_GUIDE
from veillock.ui import Handler
from veillock.wrap import ArrayCamera, ArrayMic, WrapConfig, run_wrap


class FakeRunner:
    def __init__(self, tools: set[str], *, fail_remap: bool = False) -> None:
        self.tools = set(tools)
        self.fail_remap = fail_remap
        self.calls: list[list[str]] = []
        self._next = 40
        self.player: CommandIO | None = None

    def which(self, name: str) -> str | None:
        return f"/bin/{name}" if name in self.tools else None

    def run(self, argv: list[str]) -> CommandIO:
        self.calls.append(list(argv))
        io = CommandIO()
        if argv[:2] == ["pactl", "load-module"]:
            if self.fail_remap and "module-remap-source" in argv:
                io.returncode = 1
                io.stdout = b"module missing"
                return io
            io.returncode = 0
            io.stdout = f"{self._next}\n".encode()
            self._next += 1
            return io
        io.returncode = 0
        io.stdout = b""
        return io

    def popen(self, argv: list[str]) -> CommandIO:
        self.calls.append(list(argv))
        proc = CommandIO()
        proc.stdin = proc
        self.player = proc
        return proc


def _speech() -> np.ndarray:
    t = np.linspace(0, 1, 320, endpoint=False)
    return (np.sin(2 * np.pi * 4 * t) * 8000).astype(np.int16)


def test_linux_creates_veillock_microphone_and_tears_it_down() -> None:
    runner = FakeRunner({"pactl", "paplay"})
    mic = VirtualMicrophone(runner=runner, platform="linux", rng=np.random.default_rng(1))
    idle = mic.probe()
    assert idle.running is False
    assert idle.created_by_veillock is False
    assert idle.selectable_name == SELECTABLE_LINUX
    assert idle.call_audio_aes_256_gcm is False
    assert "not a kernel driver" in idle.note

    started = mic.start()
    assert started.ok and started.running
    assert started.created_by_veillock is True
    assert started.selectable_name == SELECTABLE_LINUX
    assert started.backend == "pulse-remap"
    load_calls = [c for c in runner.calls if c[:2] == ["pactl", "load-module"]]
    assert any("module-null-sink" in c for c in load_calls)
    assert any("module-remap-source" in c and f"source_name={SOURCE_NAME}" in c for c in load_calls)
    assert any(c[0] == "paplay" and "--device=veillock_sink" in c for c in runner.calls)

    tone = _speech()
    mic.write(tone)
    assert runner.player is not None
    assert bytes(runner.player.stdin_buf) == tone.tobytes()

    stopped = mic.stop()
    assert stopped.running is False
    assert stopped.created_by_veillock is False
    unloaded = [c for c in runner.calls if c[:2] == ["pactl", "unload-module"]]
    assert [c[2] for c in unloaded] == ["41", "40"]


def test_linux_refuses_without_pactl_and_rolls_back_a_failed_source() -> None:
    bare = VirtualMicrophone(runner=FakeRunner(set()), platform="linux")
    missing = bare.start()
    assert missing.ok is False
    assert missing.running is False
    assert missing.created_by_veillock is False
    assert "pactl" in (missing.error or "")
    assert "kernel" in (missing.error or "")

    runner = FakeRunner({"pactl", "paplay"}, fail_remap=True)
    failed = VirtualMicrophone(runner=runner, platform="linux").start()
    assert failed.ok is False
    assert any(c[:3] == ["pactl", "unload-module", "40"] for c in runner.calls)
    assert not any(c[0] == "paplay" for c in runner.calls)


def test_macos_routes_into_blackhole_and_does_not_invent_a_device() -> None:
    def exists(path: str) -> bool:
        return path.endswith("BlackHole2ch.driver")

    runner = FakeRunner({"sox"})
    mic = VirtualMicrophone(runner=runner, platform="darwin", path_exists=exists)
    started = mic.start()
    assert started.ok and started.running
    assert started.created_by_veillock is False
    assert started.selectable_name == BLACKHOLE_2CH
    assert started.backend == "blackhole"
    assert any("BlackHole 2ch" in c and c[0] == "sox" for c in runner.calls)
    assert "not VeilLock" in started.note or "not a device named VeilLock" in started.note
    assert "CoreAudio" in started.note

    absent = VirtualMicrophone(
        runner=FakeRunner({"sox"}),
        platform="darwin",
        path_exists=lambda _path: False,
    ).start()
    assert absent.ok is False
    assert absent.selectable_name is None
    assert "CoreAudio" in (absent.error or "")


def test_windows_routes_into_vb_cable_and_does_not_ship_a_driver() -> None:
    runner = FakeRunner({"ffmpeg"})
    mic = VirtualMicrophone(
        runner=runner,
        platform="windows",
        playback_devices=["Speakers", "CABLE Input (VB-Audio Virtual Cable)"],
    )
    started = mic.start()
    assert started.ok and started.running
    assert started.created_by_veillock is False
    assert started.selectable_name == CABLE_MIC
    play = [c for c in runner.calls if c and c[0] == "ffmpeg"]
    assert play and CABLE_PLAYBACK in " ".join(play[-1])
    assert "wasapi" in play[-1]
    assert "kernel driver" in started.note

    missing = VirtualMicrophone(
        runner=FakeRunner({"ffmpeg"}),
        platform="windows",
        playback_devices=["Speakers"],
    ).start()
    assert missing.ok is False
    assert "kernel" in (missing.error or "").lower() or "driver" in (missing.error or "").lower()


def test_public_audio_follows_consent_and_pulse() -> None:
    speech = _speech()
    key = bytes(range(32))
    rng = np.random.default_rng(3)
    veiled, label = choose_public_pcm(
        speech, audio_feed="auto", lifted=False, pulse_ok=True, key=key, epoch=0, rng=rng
    )
    assert label == "veil"
    assert not np.array_equal(veiled, speech)

    lifted, label = choose_public_pcm(
        speech, audio_feed="auto", lifted=True, pulse_ok=True, key=key, epoch=0, rng=rng
    )
    assert label == "plaintext"
    np.testing.assert_array_equal(lifted, speech)

    longer = np.arange(AUDIO_BLOCK * 4, dtype=np.int16)
    scrambled = longer
    used = 0
    for used in range(8):
        scrambled, label = choose_public_pcm(
            longer, audio_feed="scramble", lifted=True, pulse_ok=True, key=key, epoch=used, rng=rng
        )
        assert label == "scramble"
        if not np.array_equal(scrambled, longer):
            break
    else:
        raise AssertionError("scramble left four blocks unchanged")
    np.testing.assert_array_equal(unveil_pcm(scrambled, key, epoch=used), longer)

    halted, label = choose_public_pcm(
        speech, audio_feed="auto", lifted=True, pulse_ok=False, key=key, epoch=0, rng=rng
    )
    assert label == "veil"
    assert not np.array_equal(halted, speech)


def test_wrap_mic_records_real_audio_while_the_call_hears_noise(tmp_path) -> None:
    key = bytes(range(32))
    plain = np.zeros((128, 128, 3), dtype=np.uint8)
    plain[16:112, 16:112] = (20, 180, 40)
    speech = _speech()
    cam = ArrayCamera()
    sink = ArrayMic()
    veiled = run_wrap(
        WrapConfig(
            feed="scramble",
            audio_feed="auto",
            mic=True,
            width=128,
            height=128,
            max_frames=1,
            session_key=key,
            record_path=str(tmp_path / "mic.veilrec"),
            rng=np.random.default_rng(4),
        ),
        frame_source=iter([plain]),
        virtual_cam=cam,
        pcm_source=iter([speech]),
        pcm_sink=sink,
        log=__import__("io").StringIO(),
    )
    assert veiled.audio_labels == ["veil"]
    assert not np.array_equal(sink.sent[0], speech)
    from veillock.record import play_recording

    played = play_recording(str(tmp_path / "mic.veilrec"), key)
    assert played.pcm is not None
    np.testing.assert_array_equal(played.pcm, speech)

    opened = ArrayMic()
    lifted = run_wrap(
        WrapConfig(
            feed="plaintext",
            audio_feed="auto",
            width=128,
            height=128,
            max_frames=1,
            session_key=key,
            obfuscation_off=True,
            rng=np.random.default_rng(4),
        ),
        frame_source=iter([plain.copy()]),
        virtual_cam=ArrayCamera(),
        pcm_source=iter([speech.copy()]),
        pcm_sink=opened,
        log=__import__("io").StringIO(),
    )
    assert lifted.audio_labels == ["plaintext"]
    np.testing.assert_array_equal(opened.sent[0], speech)


def test_apps_name_each_platform_microphone() -> None:
    assert "VeilLock Microphone" in APPS_GUIDE
    assert "BlackHole 2ch" in APPS_GUIDE
    assert "CABLE Output" in APPS_GUIDE
    assert "not a kernel driver" in APPS_GUIDE
    assert "No CoreAudio" in APPS_GUIDE or "No CoreAudio HAL" in APPS_GUIDE
    assert "not AES-256-GCM" in APPS_GUIDE
    assert "iPhone FaceTime cannot" in APPS_GUIDE


def test_ui_reports_mic_status_without_a_device() -> None:
    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    host, port = server.server_address[:2]
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/mic", timeout=5) as res:
            body = json.loads(res.read().decode())
        assert body["call_audio_aes_256_gcm"] is False
        assert body["running"] is False
        page = urllib.request.urlopen(f"http://{host}:{port}/", timeout=5).read().decode()
        assert "VeilLock Microphone" in page
        assert "BlackHole 2ch" in page
        assert "CABLE Output" in page
        assert "not AES-256-GCM" in page
        req = urllib.request.Request(
            f"http://{host}:{port}/api/mic/start",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with pytest.raises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(req, timeout=5)
        detail = json.loads(caught.value.read().decode())
        assert detail["ok"] is False
        assert detail["call_audio_aes_256_gcm"] is False
    finally:
        server.shutdown()
        server.server_close()
