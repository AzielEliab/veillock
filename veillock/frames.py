"""Layer 1 — Render Capture.

In software this is a FrameSource that yields RGB uint8 numpy frames.
PCI is checked *before* a frame is yielded so a failing gate never
produces plaintext.
"""

from __future__ import annotations

from typing import Iterator

import numpy as np

from veillock.pulse import AlwaysPass, HaltedError, PulseCheck


class FrameSource:
    """Yield RGB uint8 frames from an in-memory (N, H, W, 3) stack.

    This is the software stand-in for intercepting visual frames before
    they reach a GPU display. It is not a screen scraper: it only emits
    frames the caller already constructed.
    """

    def __init__(
        self,
        frames: np.ndarray,
        pulse: PulseCheck | None = None,
    ) -> None:
        arr = np.ascontiguousarray(frames, dtype=np.uint8)
        if arr.ndim != 4 or arr.shape[-1] != 3:
            raise ValueError("FrameSource expects an RGB stack of shape (N, H, W, 3)")
        self._frames = arr
        self._pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self._i = 0

    def __len__(self) -> int:
        return int(self._frames.shape[0])

    def __iter__(self) -> Iterator[np.ndarray]:
        self._i = 0
        return self

    def __next__(self) -> np.ndarray:
        if self._pulse.pci() != "PASS":
            raise HaltedError("PCI did not PASS; frame generation halted")
        if self._i >= self._frames.shape[0]:
            raise StopIteration
        frame = self._frames[self._i]
        self._i += 1
        return frame

    @property
    def shape(self) -> tuple[int, int, int, int]:
        return tuple(int(x) for x in self._frames.shape)  # type: ignore[return-value]
