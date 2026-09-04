"""Obfuscation: synthetic UI noise and natural camera veil, never plaintext."""

from __future__ import annotations

import numpy as np

from veillock.engine import VeilLockSession
from veillock.modes import natural_camera_veil, obfuscate_camera_frame
from tests.helpers import entropy_bits


def test_obfuscation_decoy_is_not_plaintext(frames_16: np.ndarray, session_key: bytes) -> None:
    sess = VeilLockSession(
        session_key=session_key,
        mode="obfuscation",
        rotation_interval=60,
        rng=np.random.default_rng(1),
    )
    stream = sess.encrypt_frames(frames_16)
    assert stream.decoy is not None
    assert stream.decoy.shape == frames_16.shape
    assert stream.decoy.dtype == np.uint8
    assert not np.array_equal(stream.decoy, frames_16)
    for i, fr in enumerate(stream.frames):
        assert fr.decoy is not None
        assert not np.array_equal(fr.decoy, frames_16[i])
        # Decoy is structured (not high-entropy GCM snow).
        assert entropy_bits(fr.decoy.tobytes()) < 6.5
        # Real ciphertext remains sealed and is not plaintext.
        assert fr.ciphertext[: frames_16[i].nbytes] != frames_16[i].tobytes()

    # Authorized decrypt still recovers the original.
    dec = VeilLockSession(
        session_key=session_key, mode="obfuscation", rotation_interval=60
    )
    out = dec.decrypt_frames(stream)
    np.testing.assert_array_equal(out, frames_16)


def test_natural_camera_veil_is_not_plaintext(frames_16: np.ndarray) -> None:
    rng = np.random.default_rng(4)
    plain = frames_16[0]
    veil = obfuscate_camera_frame(plain, rng, tick=3)
    assert veil.shape == plain.shape
    assert veil.dtype == np.uint8
    assert not np.array_equal(veil, plain)
    assert entropy_bits(veil.tobytes()) < 6.5
    again = natural_camera_veil(plain.shape, np.random.default_rng(4), luminance_hint=float(plain.mean()), tick=3)
    # Same seed + tick is structured and still not the camera.
    assert again.shape == plain.shape
    assert not np.array_equal(again, plain)
