"""PulseCheck: PCI failure halts frame generation; no plaintext produced."""

from __future__ import annotations

import numpy as np
import pytest

from veillock.engine import VeilLockSession
from veillock.frames import FrameSource
from veillock.pulse import HaltedError


class FlipPulse:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def pci(self) -> str:
        return "PASS" if self.ok else "FAIL"


def test_pci_fail_halts_frame_source(frames_16: np.ndarray) -> None:
    pulse = FlipPulse(ok=False)
    src = FrameSource(frames_16, pulse=pulse)
    with pytest.raises(HaltedError, match="halted"):
        next(iter(src))


def test_pci_fail_halts_encrypt_no_plaintext(frames_16: np.ndarray, session_key: bytes) -> None:
    pulse = FlipPulse(ok=True)
    sess = VeilLockSession(session_key=session_key, pulse=pulse, rotation_interval=60)
    sess.encrypt_frame(frames_16[0])
    pulse.ok = False
    with pytest.raises(HaltedError):
        sess.encrypt_frame(frames_16[1])
    # Engine framebuffer is zeros (never left holding the second frame).
    assert np.all(sess.framebuffer == 0)


def test_pci_pass_allows_generation(frames_16: np.ndarray) -> None:
    src = FrameSource(frames_16, pulse=FlipPulse(ok=True))
    got = list(src)
    assert len(got) == len(frames_16)
    np.testing.assert_array_equal(got[0], frames_16[0])
