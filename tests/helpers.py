from __future__ import annotations

import math
from collections import Counter

import numpy as np

from veillock.engine import EncryptedFrame, VeilLockSession
from veillock.modes import Mode


def entropy_bits(data: bytes) -> float:
    if not data:
        return 0.0
    counts = Counter(data)
    n = len(data)
    ent = 0.0
    for c in counts.values():
        p = c / n
        ent -= p * math.log2(p)
    return ent


def clone_session(session: VeilLockSession, root_key: bytes, **kwargs) -> VeilLockSession:
    params = dict(
        session_key=root_key,
        rotation_interval=session.rotation_interval,
        mode=session.mode,
        receiver_secret=session.receiver_secret,
    )
    params.update(kwargs)
    return VeilLockSession(**params)


def roundtrip(frames: np.ndarray, root_key: bytes, **kwargs) -> np.ndarray:
    enc = VeilLockSession(session_key=root_key, **kwargs)
    stream = enc.encrypt_frames(frames)
    dec = VeilLockSession(session_key=root_key, **kwargs)
    return dec.decrypt_frames(stream)
