#!/usr/bin/env python3
"""Encrypt a synthetic 16x16 RGB stack with VeilLock. No hardware."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from veillock.engine import VeilLockSession, load_cipher_npz, save_cipher_npz

OUT = Path(__file__).resolve().parent / "_out"


def make_frames(n: int = 8, h: int = 16, w: int = 16) -> np.ndarray:
    frames = np.zeros((n, h, w, 3), dtype=np.uint8)
    for i in range(n):
        frames[i, :, :] = (20 + i * 8, 50, 90)
        frames[i, 3:12, 3:12] = (180, 20 + i * 10, 40)
        frames[i, 0, :] = 255
    return frames


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    frames = make_frames()
    np.save(OUT / "frames.npy", frames)
    key = bytes(range(32))
    enc = VeilLockSession(session_key=key, rotation_interval=60, mode="private")
    stream = enc.encrypt_frames(frames, metadata={"note": "synthetic", "window_id": "must-strip"})
    save_cipher_npz(str(OUT / "cipher.npz"), stream)
    assert "window_id" not in stream.frames[0].headers
    dec = VeilLockSession(session_key=key, rotation_interval=60, mode="private")
    out = dec.decrypt_frames(stream)
    np.save(OUT / "recovered.npy", out)
    assert np.array_equal(out, frames)
    loaded = load_cipher_npz(str(OUT / "cipher.npz"))
    print(f"frames={frames.shape} sealed={len(loaded.frames)} out={OUT}")
    print("roundtrip ok")


if __name__ == "__main__":
    main()
