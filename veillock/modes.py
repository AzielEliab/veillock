"""Deployment modes: private, secure_broadcast, obfuscation."""

from __future__ import annotations

from enum import Enum

import numpy as np


class Mode(str, Enum):
    PRIVATE = "private"
    BROADCAST = "broadcast"
    OBFUSCATION = "obfuscation"

    @classmethod
    def parse(cls, value: str | Mode) -> Mode:
        if isinstance(value, cls):
            return value
        key = str(value).strip().lower().replace("-", "_")
        if key in ("secure_broadcast", "securebroadcast"):
            key = "broadcast"
        try:
            return cls(key)
        except ValueError as exc:
            raise ValueError(
                "mode must be private, broadcast (secure_broadcast), or obfuscation"
            ) from exc


def synthetic_ui_noise(
    shape: tuple[int, int, int],
    rng: np.random.Generator,
) -> np.ndarray:
    """Structured decoy frame (fake windows / panels), not plaintext and not GCM snow."""
    h, w, c = int(shape[0]), int(shape[1]), int(shape[2])
    bg = rng.integers(24, 64, size=(c,), dtype=np.uint8)
    frame = np.empty((h, w, c), dtype=np.uint8)
    frame[:, :] = bg
    n_rect = int(rng.integers(2, 6))
    for _ in range(n_rect):
        y1 = int(rng.integers(0, max(h, 1)))
        x1 = int(rng.integers(0, max(w, 1)))
        y2 = int(rng.integers(y1 + 1, h + 1))
        x2 = int(rng.integers(x1 + 1, w + 1))
        color = rng.integers(80, 210, size=(c,), dtype=np.uint8)
        frame[y1:y2, x1:x2] = color
        # title-bar strip on the fake window
        bar = min(y1 + max(1, h // 16), y2)
        bar_color = rng.integers(40, 120, size=(c,), dtype=np.uint8)
        frame[y1:bar, x1:x2] = bar_color
    return frame
