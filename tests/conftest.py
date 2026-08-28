"""Synthetic RGB fixtures. No hardware."""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(20260701)


@pytest.fixture
def frames_16(rng: np.random.Generator) -> np.ndarray:
    """8 structured 16x16 RGB frames (not random snow)."""
    n, h, w = 8, 16, 16
    out = np.zeros((n, h, w, 3), dtype=np.uint8)
    for i in range(n):
        out[i, :, :] = (20 + i * 10, 40, 80)
        out[i, 2:10, 2:10] = (200, 30 + i * 5, 30)
        out[i, 0, :] = 255
    return out


@pytest.fixture
def frames_64(rng: np.random.Generator) -> np.ndarray:
    n, h, w = 4, 64, 64
    out = np.zeros((n, h, w, 3), dtype=np.uint8)
    for i in range(n):
        out[i] = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
        out[i, 10:30, 10:40] = (i * 40, 180, 90)
    return out


@pytest.fixture
def session_key() -> bytes:
    return bytes(range(32))
