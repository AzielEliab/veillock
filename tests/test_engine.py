"""Encrypt/decrypt roundtrip, wrong key, entropy, framebuffer zeroing."""

from __future__ import annotations

import numpy as np
import pytest

from veillock.crypto import DecryptError
from veillock.engine import VeilLockSession
from tests.helpers import entropy_bits, roundtrip


def test_roundtrip_16x16(frames_16: np.ndarray, session_key: bytes) -> None:
    out = roundtrip(frames_16, session_key, rotation_interval=60)
    assert out.shape == frames_16.shape
    assert out.dtype == np.uint8
    np.testing.assert_array_equal(out, frames_16)


def test_roundtrip_64x64(frames_64: np.ndarray, session_key: bytes) -> None:
    out = roundtrip(frames_64, session_key, rotation_interval=60)
    np.testing.assert_array_equal(out, frames_64)


def test_wrong_key_fails(frames_16: np.ndarray, session_key: bytes) -> None:
    enc = VeilLockSession(session_key=session_key, rotation_interval=60)
    stream = enc.encrypt_frames(frames_16)
    bad = bytes((b ^ 0xFF) for b in session_key)
    dec = VeilLockSession(session_key=bad, rotation_interval=60)
    with pytest.raises(DecryptError):
        dec.decrypt_frames(stream)


def test_ciphertext_high_entropy_not_a_valid_image(
    frames_16: np.ndarray, session_key: bytes
) -> None:
    enc = VeilLockSession(session_key=session_key, rotation_interval=60)
    sealed = enc.encrypt_frame(frames_16[0])
    assert entropy_bits(sealed.ciphertext) > 7.0
    # Ciphertext is not the plaintext bytes and is not a near-copy of the image.
    plain = frames_16[0].tobytes()
    assert sealed.ciphertext[: len(plain)] != plain
    h, w, c = sealed.shape
    body = sealed.ciphertext[: h * w * c]
    recovered = np.frombuffer(body, dtype=np.uint8).reshape(h, w, c)
    assert not np.array_equal(recovered, frames_16[0])


def test_framebuffer_zeroed_after_encrypt(frames_16: np.ndarray, session_key: bytes) -> None:
    enc = VeilLockSession(session_key=session_key, rotation_interval=60)
    enc.encrypt_frame(frames_16[0])
    fb = enc.framebuffer
    assert fb.dtype == np.uint8
    assert fb.size > 0
    assert np.all(fb == 0)


def test_protect_frame_local_decode(frames_16: np.ndarray, session_key: bytes) -> None:
    sess = VeilLockSession(session_key=session_key, rotation_interval=60)
    sealed, display = sess.protect_frame(frames_16[0])
    np.testing.assert_array_equal(display, frames_16[0])
    assert np.all(sess.framebuffer == 0)
    assert sealed.ciphertext


def test_private_mode_does_not_export_key(frames_16: np.ndarray, session_key: bytes) -> None:
    enc = VeilLockSession(session_key=session_key, mode="private", rotation_interval=60)
    stream = enc.encrypt_frames(frames_16[:2])
    assert stream.wrapped_key is None
    blob = b"".join(f.ciphertext for f in stream.frames)
    assert session_key not in blob
    assert session_key not in stream.frames[0].aad


def test_broadcast_wraps_key(frames_16: np.ndarray, session_key: bytes) -> None:
    secret = b"receiver-secret-for-tests-32b!!!"
    enc = VeilLockSession(
        session_key=session_key,
        mode="broadcast",
        receiver_secret=secret,
        rotation_interval=60,
    )
    stream = enc.encrypt_frames(frames_16[:2])
    assert stream.wrapped_key is not None
    assert session_key not in stream.wrapped_key
    from veillock.engine import session_from_wrapped

    dec = session_from_wrapped(stream.wrapped_key, secret, rotation_interval=60)
    out = dec.decrypt_frames(stream)
    np.testing.assert_array_equal(out, frames_16[:2])


def test_rotation_interval_bounds() -> None:
    with pytest.raises(ValueError):
        VeilLockSession(rotation_interval=59)
    with pytest.raises(ValueError):
        VeilLockSession(rotation_interval=241)
    VeilLockSession(rotation_interval=60)
    VeilLockSession(rotation_interval=240)
