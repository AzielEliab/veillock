"""Deployment modes: private, secure_broadcast, obfuscation.

Camera and video default to a natural privacy veil. Display-level
streams can still use synthetic UI noise. Neither path is plaintext
and neither is GCM snow.

Author: Aziel Eliab.
"""

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


def natural_camera_veil(
    shape: tuple[int, int, int],
    rng: np.random.Generator,
    *,
    luminance_hint: float | None = None,
    tick: int = 0,
) -> np.ndarray:
    """Camera-like privacy veil for a live feed.

    Looks like a camera is on (soft wash, grain, slow drift). Does not
    copy spatial content from the real frame. Optional ``luminance_hint``
    is a single mean-brightness number so room lighting can match without
    leaking a face or scene.
    """
    h, w, c = int(shape[0]), int(shape[1]), int(shape[2])
    if h < 1 or w < 1 or c != 3:
        raise ValueError("shape must be (H, W, 3) with H,W >= 1")
    yy = np.linspace(-1.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(-1.0, 1.0, w, dtype=np.float32)[None, :]
    phase = ((int(tick) % 240) / 240.0) * (2.0 * np.pi)
    vignette = 1.0 - 0.45 * (xx * xx + yy * yy)
    wash = 0.55 + 0.20 * np.sin(xx * 2.1 + phase) + 0.15 * np.cos(yy * 1.7 - phase * 0.7)
    field = np.clip(vignette * wash, 0.05, 1.0)
    grain = rng.normal(0.0, 0.035, size=(h, w)).astype(np.float32)
    field = np.clip(field + grain, 0.0, 1.0)
    luma = 88.0 if luminance_hint is None else float(np.clip(luminance_hint, 36.0, 170.0))
    r = field * (luma * 0.72) + 20.0
    g = field * (luma * 0.58) + 16.0
    b = field * (luma * 0.90) + 38.0
    oval = np.exp(-((xx * 1.4) ** 2 + ((yy + 0.08) * 1.8) ** 2) * 2.2)
    r = r + oval * 18.0
    g = g + oval * 10.0
    b = b + oval * 8.0
    frame = np.stack([r, g, b], axis=-1)
    return np.clip(frame, 0, 255).astype(np.uint8)


def obfuscate_camera_frame(
    frame: np.ndarray,
    rng: np.random.Generator,
    *,
    tick: int = 0,
) -> np.ndarray:
    """Natural camera/video veil from a caller-owned frame.

    Uses only the mean luminance of ``frame``. Spatial pixels are not
    copied. The result is never the plaintext camera.
    """
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    hint = float(src.mean())
    out = natural_camera_veil(src.shape, rng, luminance_hint=hint, tick=tick)
    return np.ascontiguousarray(out, dtype=np.uint8)


def public_veil(
    frame: np.ndarray,
    rng: np.random.Generator,
    *,
    source: str = "camera",
    tick: int = 0,
) -> np.ndarray:
    """Choose the natural camera veil or display-level UI noise."""
    kind = str(source).strip().lower()
    if kind in ("camera", "video"):
        return obfuscate_camera_frame(frame, rng, tick=tick)
    return synthetic_ui_noise(tuple(int(x) for x in frame.shape), rng)
