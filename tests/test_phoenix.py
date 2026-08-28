"""Phoenix Loop: after N failures, refuse plaintext until PCI PASS; keys reset."""

from __future__ import annotations

import numpy as np
import pytest

from veillock.crypto import DecryptError
from veillock.engine import VeilLockSession
from veillock.pulse import HaltedError, PhoenixError


class FlipPulse:
    def __init__(self, ok: bool = True) -> None:
        self.ok = ok

    def pci(self) -> str:
        return "PASS" if self.ok else "FAIL"


def test_phoenix_refuses_plaintext_until_pci_pass(
    frames_16: np.ndarray, session_key: bytes
) -> None:
    pulse = FlipPulse(ok=True)
    sess = VeilLockSession(
        session_key=session_key,
        pulse=pulse,
        rotation_interval=60,
        phoenix_threshold=3,
    )
    sess.encrypt_frame(frames_16[0])
    key_before = sess.current_key

    pulse.ok = False
    with pytest.raises(HaltedError):
        sess.encrypt_frame(frames_16[1])
    with pytest.raises(HaltedError):
        sess.encrypt_frame(frames_16[1])
    with pytest.raises(PhoenixError):
        sess.encrypt_frame(frames_16[1])

    assert sess.phoenix.active
    # Keys were rebooted; old material is gone.
    assert sess.current_key != key_before
    assert sess.current_key != session_key

    # Still refuses while PCI fails.
    with pytest.raises(PhoenixError):
        sess.encrypt_frame(frames_16[2])

    pulse.ok = True
    # Integrity restored: encrypt is allowed again (fresh session).
    sealed = sess.encrypt_frame(frames_16[2])
    assert sealed.ciphertext
    assert not sess.phoenix.active
    assert np.all(sess.framebuffer == 0)


def test_phoenix_refuses_decrypt_until_pass(frames_16: np.ndarray, session_key: bytes) -> None:
    pulse = FlipPulse(ok=True)
    enc = VeilLockSession(session_key=session_key, rotation_interval=60)
    stream = enc.encrypt_frames(frames_16[:2])

    dec = VeilLockSession(
        session_key=session_key,
        pulse=pulse,
        rotation_interval=60,
        phoenix_threshold=3,
    )
    pulse.ok = False
    with pytest.raises(HaltedError):
        dec.decrypt_frame(stream.frames[0])
    with pytest.raises(HaltedError):
        dec.decrypt_frame(stream.frames[0])
    with pytest.raises(PhoenixError):
        dec.decrypt_frame(stream.frames[0])
    with pytest.raises(PhoenixError):
        dec.decrypt_frame(stream.frames[0])


def test_decode_mismatch_counts_toward_phoenix(
    frames_16: np.ndarray, session_key: bytes
) -> None:
    enc = VeilLockSession(session_key=session_key, rotation_interval=60)
    stream = enc.encrypt_frames(frames_16[:4])
    bad = bytes((b ^ 0xAA) for b in session_key)
    dec = VeilLockSession(session_key=bad, rotation_interval=60, phoenix_threshold=3)
    with pytest.raises(DecryptError):
        dec.decrypt_frame(stream.frames[0])
    with pytest.raises(DecryptError):
        dec.decrypt_frame(stream.frames[1])
    with pytest.raises(PhoenixError):
        dec.decrypt_frame(stream.frames[2])
    assert dec.phoenix.active
