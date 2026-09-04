"""Opt-in capture of THIS machine's camera or screen.

CameraSource / ScreenSource yield RGB uint8 frames with the same iterator
contract as FrameSource. PulseCheck is consulted *before* a frame is
yielded so a failing gate never produces plaintext.

Consent-gated camera protection via AZ-OS: the caller already owns the
camera or the display they are piping through VeilLock. The public feed
stays veiled unless the user lifts it.
"""

from __future__ import annotations

from typing import Callable, Iterator

import numpy as np

from veillock.pulse import AlwaysPass, HaltedError, PulseCheck

DEFAULT_WIDTH = 640
DEFAULT_HEIGHT = 480


class InstallError(RuntimeError):
    """Optional extra missing: pip install 'veillock[tether]'."""


def _require_cv2():
    """Lazy OpenCV import so the core package stays free of the extra."""
    try:
        import cv2  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InstallError(
            "CameraSource requires OpenCV. Install with: pip install 'veillock[tether]'"
        ) from exc
    return cv2


def resize_rgb(frame: np.ndarray, width: int, height: int) -> np.ndarray:
    """Nearest-neighbor resize to (height, width, 3) uint8 RGB."""
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    h, w = int(src.shape[0]), int(src.shape[1])
    if (h, w) == (int(height), int(width)):
        return src
    if height < 1 or width < 1:
        raise ValueError("width and height must be >= 1")
    ys = np.linspace(0, max(h - 1, 0), int(height)).astype(np.int64)
    xs = np.linspace(0, max(w - 1, 0), int(width)).astype(np.int64)
    return np.ascontiguousarray(src[ys][:, xs], dtype=np.uint8)


def _bgr_to_rgb(bgr: np.ndarray) -> np.ndarray:
    arr = np.ascontiguousarray(bgr, dtype=np.uint8)
    if arr.ndim == 2:
        arr = np.stack([arr, arr, arr], axis=-1)
    if arr.shape[-1] == 4:
        arr = arr[:, :, :3]
    if arr.shape[-1] != 3:
        raise ValueError("expected a 3-channel BGR frame from the camera")
    return np.ascontiguousarray(arr[:, :, ::-1], dtype=np.uint8)


class CameraSource:
    """Yield RGB uint8 frames from THIS machine's camera (opt-in).

    Uses OpenCV ``cv2.VideoCapture(device)``. The call app later
    *chooses* the VeilLock virtual camera if the user starts
    ``veillock tether``. The public feed is veiled until the user
    turns obfuscation off or accepts a call through AZ-OS.
    """

    def __init__(
        self,
        device: int | str = 0,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        pulse: PulseCheck | None = None,
    ) -> None:
        cv2 = _require_cv2()
        cap = cv2.VideoCapture(device)
        if cap is None or not cap.isOpened():
            raise RuntimeError(
                f"Could not open local camera {device!r}. "
                "VeilLock only uses YOUR camera on this machine."
            )
        width = int(width)
        height = int(height)
        cap.set(int(getattr(cv2, "CAP_PROP_FRAME_WIDTH", 3)), width)
        cap.set(int(getattr(cv2, "CAP_PROP_FRAME_HEIGHT", 4)), height)
        self._cv2 = cv2
        self._cap = cap
        self._device = device
        self.width = width
        self.height = height
        self._pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self._closed = False

    def __len__(self) -> int:
        # Live source: unknown length. 0 keeps ``list()`` from guessing.
        return 0

    def __iter__(self) -> Iterator[np.ndarray]:
        return self

    def __next__(self) -> np.ndarray:
        if self._closed or self._cap is None:
            raise StopIteration
        if self._pulse.pci() != "PASS":
            raise HaltedError("PCI did not PASS; frame generation halted")
        ok, bgr = self._cap.read()
        if not ok or bgr is None:
            raise StopIteration
        rgb = _bgr_to_rgb(bgr)
        return resize_rgb(rgb, self.width, self.height)

    @property
    def shape(self) -> tuple[int, int, int]:
        return (int(self.height), int(self.width), 3)

    def close(self) -> None:
        self._closed = True
        cap = self._cap
        self._cap = None
        if cap is not None:
            try:
                cap.release()
            except Exception:  # noqa: BLE001
                pass

    def __enter__(self) -> CameraSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def _grab_own_screen() -> np.ndarray:
    """Capture THIS machine's display as the user already sees it.

    Tries ``mss``, then Pillow ``ImageGrab``. Does not scrape another
    process's private buffers or DRM overlays.
    """
    try:
        import mss  # type: ignore[import-not-found]
    except ImportError:
        mss = None
    if mss is not None:
        with mss.mss() as sct:
            mon = sct.monitors[1] if len(sct.monitors) > 1 else sct.monitors[0]
            raw = sct.grab(mon)
            arr = np.asarray(raw, dtype=np.uint8)
            if arr.ndim == 3 and arr.shape[-1] >= 3:
                # mss is BGRA
                return np.ascontiguousarray(arr[:, :, 2::-1], dtype=np.uint8)
            raise RuntimeError("mss returned an unexpected screenshot shape")
    try:
        from PIL import ImageGrab  # type: ignore[import-not-found]
    except ImportError as exc:
        raise InstallError(
            "ScreenSource needs mss or Pillow in addition to the camera extra. "
            "Camera tether: pip install 'veillock[tether]'. "
            "Screen tether: pip install mss   (or pillow)."
        ) from exc
    img = ImageGrab.grab()
    return np.asarray(img.convert("RGB"), dtype=np.uint8)


class ScreenSource:
    """Yield RGB uint8 frames from THIS machine's screen (opt-in).

    Print-Screen of the local display the user already owns. Not a scraper
    of other apps' private buffers.
    """

    def __init__(
        self,
        width: int = DEFAULT_WIDTH,
        height: int = DEFAULT_HEIGHT,
        pulse: PulseCheck | None = None,
        grab: Callable[[], np.ndarray] | None = None,
    ) -> None:
        self.width = int(width)
        self.height = int(height)
        self._pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self._grab = grab if grab is not None else _grab_own_screen
        self._closed = False

    def __len__(self) -> int:
        return 0

    def __iter__(self) -> Iterator[np.ndarray]:
        return self

    def __next__(self) -> np.ndarray:
        if self._closed:
            raise StopIteration
        if self._pulse.pci() != "PASS":
            raise HaltedError("PCI did not PASS; frame generation halted")
        rgb = np.ascontiguousarray(self._grab(), dtype=np.uint8)
        if rgb.ndim != 3 or rgb.shape[-1] < 3:
            raise RuntimeError("screen grab must return RGB uint8 (H, W, 3)")
        if rgb.shape[-1] > 3:
            rgb = rgb[:, :, :3]
        return resize_rgb(rgb, self.width, self.height)

    @property
    def shape(self) -> tuple[int, int, int]:
        return (int(self.height), int(self.width), 3)

    def close(self) -> None:
        self._closed = True

    def __enter__(self) -> ScreenSource:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


def open_source(
    kind: str,
    *,
    device: int | str = 0,
    width: int = DEFAULT_WIDTH,
    height: int = DEFAULT_HEIGHT,
    pulse: PulseCheck | None = None,
    grab: Callable[[], np.ndarray] | None = None,
) -> CameraSource | ScreenSource:
    key = str(kind).strip().lower()
    if key == "camera":
        return CameraSource(device=device, width=width, height=height, pulse=pulse)
    if key == "screen":
        return ScreenSource(width=width, height=height, pulse=pulse, grab=grab)
    raise ValueError("source must be camera or screen")
