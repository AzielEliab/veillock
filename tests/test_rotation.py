"""Forward-secure key rotation: current key must not decrypt older epochs."""

from __future__ import annotations

import numpy as np
import pytest

from veillock.crypto import DecryptError, derive_frame_key, rotate_session_key
from veillock.engine import VeilLockSession


def test_rotation_happens_on_interval(frames_16: np.ndarray, session_key: bytes) -> None:
    interval = 60
    enc = VeilLockSession(session_key=session_key, rotation_interval=interval)
    assert enc.epoch_index == 0
    # Need `interval` frames to cross an epoch. Repeat the 16x16 stack.
    stack = np.concatenate([frames_16] * 10, axis=0)  # 80 frames
    enc.encrypt_frames(stack)
    assert enc.epoch_index == 1
    assert enc.frame_index == 80
    assert enc.current_key != session_key


def test_forward_secrecy_current_key_cannot_decrypt_older_epoch(
    frames_16: np.ndarray, session_key: bytes
) -> None:
    interval = 60
    stack = np.concatenate([frames_16] * 10, axis=0)  # 80 frames → epoch 0 then 1
    enc = VeilLockSession(session_key=session_key, rotation_interval=interval)
    stream = enc.encrypt_frames(stack)
    current = enc.current_key
    assert current != session_key

    # Attacker who captures the *current* session key after rotation.
    attacker = VeilLockSession(session_key=current, rotation_interval=interval)
    with pytest.raises(DecryptError):
        attacker.decrypt_frame(stream.frames[0])  # epoch 0

    # Honest decryptor with the root key recovers everything, including epoch 0.
    honest = VeilLockSession(session_key=session_key, rotation_interval=interval)
    recovered = honest.decrypt_frames(stream)
    np.testing.assert_array_equal(recovered, stack)

    # Current-epoch frames *can* be opened with the rotated key if the
    # attacker's frame_index is aligned to the new epoch (they start at 0,
    # so even current-epoch frames fail unless they skip). Either way, they
    # cannot walk the ratchet backwards: SHA-256 is one-way.
    expected_rotated = rotate_session_key(session_key, 0)
    assert current == expected_rotated
    old_frame_key = derive_frame_key(session_key, 0)
    new_frame_key = derive_frame_key(current, 0)
    assert old_frame_key != new_frame_key


def test_old_key_dropped_from_session(session_key: bytes, frames_16: np.ndarray) -> None:
    interval = 60
    stack = np.concatenate([frames_16] * 8, axis=0)  # 64 frames
    enc = VeilLockSession(session_key=session_key, rotation_interval=interval)
    enc.encrypt_frames(stack)
    # Only the current key remains; the root is not an attribute.
    assert not hasattr(enc, "_root_key")
    assert enc.current_key != session_key
    # Internal buffer is a single 32-byte key.
    assert len(enc._session_key) == 32
