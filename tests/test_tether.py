"""Tether: mock camera + virtual cam. No hardware."""

from __future__ import annotations

import io

import numpy as np
import pytest

from veillock.cli import _build_parser, main
from veillock.engine import VeilLockSession
from veillock.frames import FrameSource
from veillock.pulse import HaltedError
from veillock.sources import CameraSource, InstallError, ScreenSource, _require_cv2
from veillock.azos import AzosHook
from veillock.tether import (
    DEFAULT_MODE,
    DEVICE_NAME,
    TetherConfig,
    emit_public_frame,
    run_tether,
)


class FailPulse:
    def pci(self) -> str:
        return "FAIL"


class RecordingCam:
    def __init__(self) -> None:
        self.sent: list[np.ndarray] = []

    def send(self, frame: np.ndarray) -> None:
        self.sent.append(np.ascontiguousarray(frame, dtype=np.uint8).copy())

    def sleep_until_next_frame(self) -> None:
        return None


class FakeCap:
    def __init__(self, device: object) -> None:
        self.device = device
        self.opened = True
        self.props: dict[int, float] = {}
        self.reads = 0
        self.released = False
        self.frame = np.zeros((480, 640, 3), dtype=np.uint8)
        self.frame[:, :] = (10, 40, 70)  # BGR

    def isOpened(self) -> bool:
        return self.opened

    def set(self, prop: int, val: float) -> bool:
        self.props[int(prop)] = float(val)
        return True

    def get(self, prop: int) -> float:
        return float(self.props.get(int(prop), 0.0))

    def read(self):
        self.reads += 1
        return True, self.frame.copy()

    def release(self) -> None:
        self.released = True
        self.opened = False


class FakeCV2:
    CAP_PROP_FRAME_WIDTH = 3
    CAP_PROP_FRAME_HEIGHT = 4

    def __init__(self) -> None:
        self.last: FakeCap | None = None

    def VideoCapture(self, device):
        self.last = FakeCap(device)
        return self.last


def test_default_mode_is_obfuscation() -> None:
    assert DEFAULT_MODE == "obfuscation"
    args = _build_parser().parse_args(["tether"])
    assert args.mode == "obfuscation"
    assert args.source == "camera"
    assert args.device == 0
    assert args.trusted is False
    assert args.obfuscation_off is False
    assert args.azos_accept is False
    assert args.width == 640
    assert args.height == 480
    assert args.fps == 15
    assert DEVICE_NAME == "VeilLock"


def test_camera_source_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCV2()
    monkeypatch.setattr("veillock.sources._require_cv2", lambda: fake)
    src = CameraSource(device=0, width=640, height=480)
    assert src.shape == (480, 640, 3)
    frame = next(src)
    assert frame.shape == (480, 640, 3)
    assert frame.dtype == np.uint8
    # OpenCV BGR (10,40,70) → RGB (70,40,10)
    assert tuple(frame[0, 0].tolist()) == (70, 40, 10)
    src.close()
    assert fake.last is not None and fake.last.released


def test_camera_source_pci_halt_does_not_read(monkeypatch: pytest.MonkeyPatch) -> None:
    fake = FakeCV2()
    monkeypatch.setattr("veillock.sources._require_cv2", lambda: fake)
    src = CameraSource(device=0, pulse=FailPulse())
    with pytest.raises(HaltedError, match="halted"):
        next(src)
    assert fake.last is not None
    assert fake.last.reads == 0
    src.close()


def test_camera_source_requires_tether_extra(monkeypatch: pytest.MonkeyPatch) -> None:
    import builtins

    real = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "cv2":
            raise ImportError("simulated missing opencv")
        return real(name, globals, locals, fromlist, level)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    with pytest.raises(InstallError, match=r"pip install 'veillock\[tether\]'"):
        _require_cv2()


def test_screen_source_shape() -> None:
    def grab() -> np.ndarray:
        return np.zeros((120, 160, 3), dtype=np.uint8)

    src = ScreenSource(width=64, height=48, grab=grab)
    assert src.shape == (48, 64, 3)
    frame = next(src)
    assert frame.shape == (48, 64, 3)
    assert frame.dtype == np.uint8
    src.close()


def test_pulse_halt_does_not_send_plaintext() -> None:
    plain = np.full((48, 64, 3), 221, dtype=np.uint8)
    src = FrameSource(plain[None, ...], pulse=FailPulse())
    cam = RecordingCam()
    cfg = TetherConfig(
        width=64,
        height=48,
        max_frames=1,
        pulse=FailPulse(),
        mode="obfuscation",
        trusted=True,
        rotation_interval=60,
        rng=np.random.default_rng(7),
    )
    n = run_tether(cfg, frame_source=src, virtual_cam=cam, log=io.StringIO())
    assert n == 1
    assert len(cam.sent) == 1
    assert cam.sent[0].shape == (48, 64, 3)
    assert not np.array_equal(cam.sent[0], plain)
    assert not np.all(cam.sent[0] == 221)


def test_emit_halt_does_not_leak_plaintext(session_key: bytes) -> None:
    plain = np.full((16, 16, 3), 199, dtype=np.uint8)
    sess = VeilLockSession(
        session_key=session_key,
        rotation_interval=60,
        mode="private",
        pulse=FailPulse(),
        rng=np.random.default_rng(3),
    )
    out = emit_public_frame(sess, plain, trusted=True, rng=np.random.default_rng(3))
    assert out.shape == plain.shape
    assert not np.array_equal(out, plain)
    assert not np.all(out == 199)
    assert np.all(sess.framebuffer == 0)


def test_obfuscation_feed_is_not_plaintext(frames_16: np.ndarray, session_key: bytes) -> None:
    plain = frames_16[0]
    src = FrameSource(plain[None, ...])
    cam = RecordingCam()
    cfg = TetherConfig(
        width=16,
        height=16,
        max_frames=1,
        mode="obfuscation",
        session_key=session_key,
        rotation_interval=60,
        rng=np.random.default_rng(11),
    )
    run_tether(cfg, frame_source=src, virtual_cam=cam, log=io.StringIO())
    assert len(cam.sent) == 1
    assert not np.array_equal(cam.sent[0], plain)


def test_private_default_is_natural_veil_not_plaintext(
    frames_16: np.ndarray, session_key: bytes
) -> None:
    plain = frames_16[0]
    src = FrameSource(plain[None, ...])
    cam = RecordingCam()
    cfg = TetherConfig(
        width=16,
        height=16,
        max_frames=1,
        mode="private",
        trusted=False,
        source="camera",
        session_key=session_key,
        rotation_interval=60,
        rng=np.random.default_rng(5),
    )
    run_tether(cfg, frame_source=src, virtual_cam=cam, log=io.StringIO())
    assert cam.sent[0].shape == plain.shape
    assert not np.array_equal(cam.sent[0], plain)


def test_user_off_sends_trusted_decode(frames_16: np.ndarray, session_key: bytes) -> None:
    plain = frames_16[0]
    src = FrameSource(plain[None, ...])
    cam = RecordingCam()
    cfg = TetherConfig(
        width=16,
        height=16,
        max_frames=1,
        mode="obfuscation",
        obfuscation_off=True,
        source="camera",
        session_key=session_key,
        rotation_interval=60,
        rng=np.random.default_rng(9),
    )
    run_tether(cfg, frame_source=src, virtual_cam=cam, log=io.StringIO())
    np.testing.assert_array_equal(cam.sent[0], plain)


def test_azos_accept_sends_trusted_decode(frames_16: np.ndarray, session_key: bytes) -> None:
    plain = frames_16[0]
    src = FrameSource(plain[None, ...])
    cam = RecordingCam()
    cfg = TetherConfig(
        width=16,
        height=16,
        max_frames=1,
        mode="obfuscation",
        azos_accept=True,
        actor="Aziel Eliab",
        source="camera",
        session_key=session_key,
        rotation_interval=60,
        rng=np.random.default_rng(10),
    )
    run_tether(cfg, frame_source=src, virtual_cam=cam, log=io.StringIO())
    np.testing.assert_array_equal(cam.sent[0], plain)


def test_emit_respects_shared_hook(frames_16: np.ndarray, session_key: bytes) -> None:
    plain = frames_16[0]
    sess = VeilLockSession(
        session_key=session_key,
        rotation_interval=60,
        mode="obfuscation",
        rng=np.random.default_rng(2),
    )
    hook = AzosHook()
    veiled = emit_public_frame(sess, plain, hook=hook, source="camera", rng=np.random.default_rng(2))
    assert not np.array_equal(veiled, plain)
    hook.accept_call(actor="user")
    lifted = emit_public_frame(sess, frames_16[1], hook=hook, source="camera", rng=np.random.default_rng(2))
    np.testing.assert_array_equal(lifted, frames_16[1])


def test_cli_apps_exit_0(capsys) -> None:
    assert main(["apps"]) == 0
    out = capsys.readouterr().out
    assert "Zoom" in out
    assert "Skype" in out
    assert "FaceTime" in out
    assert "VeilLock" in out
    assert "iPhone FaceTime cannot" in out
    assert "Meet" in out
    assert "Teams" in out
