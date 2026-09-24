"""Windows 11 frame feeder for the VeilLock Media Foundation camera.

The C++ source in ``windows/vcam`` reads ``Local\\VeilLockFrame``. This
module packs that mapping. A missing or corrupt header is a solid veil,
never a physical camera. Publishing does not register the camera. Registration
is ``veilcam-register.exe`` on Windows 11 build 22000 or newer, and this
Linux tree does not run that program.

The friendly name passed to ``MFCreateVirtualCamera`` is VeilLock. Windows
appends `` Windows Virtual Camera``. VeilLock does not hook capture APIs.
Other cameras stay visible. The microphone is still CABLE Output when
VB-Audio Virtual Cable is installed.

Author: Aziel Eliab.
"""

from __future__ import annotations

import struct
import sys
from pathlib import Path

import numpy as np

MAGIC = b"VLFC"
VERSION = 1
WIDTH = 640
HEIGHT = 480
HEADER = 32
PIXELS = WIDTH * HEIGHT * 4
MAPPING_BYTES = HEADER + PIXELS
MAPPING_NAME = r"Local\VeilLockFrame"
FRIENDLY_NAME = "VeilLock"
PICKER_NAME = "VeilLock Windows Virtual Camera"
CLSID = "{C2A1E7B4-5D33-4F10-9A6E-7B18D4F02A91}"
VEIL_BGRA = bytes((0x32, 0x2A, 0x2A, 0xFF))
_HEADER = struct.Struct("<4sIIIIIII")

REPO_ROOT = Path(__file__).resolve().parents[1]
HELPER_EXE = REPO_ROOT / "windows" / "vcam" / "veilcam-register.exe"


def helper_present() -> bool:
    """True only when the Windows registrar binary is on disk. Never implied."""
    return HELPER_EXE.is_file()


def veil_pixels() -> bytes:
    return VEIL_BGRA * (WIDTH * HEIGHT)


def fit_rgb(frame: np.ndarray, width: int = WIDTH, height: int = HEIGHT) -> np.ndarray:
    """Nearest-neighbor resize to the fixed camera size. No extra dependencies."""
    rgb = np.ascontiguousarray(frame, dtype=np.uint8)
    if rgb.ndim != 3 or rgb.shape[2] != 3:
        raise ValueError("frame must be HxWx3 RGB")
    src_h, src_w = rgb.shape[:2]
    if src_h == height and src_w == width:
        return rgb
    ys = (np.arange(height) * src_h // height).astype(np.intp)
    xs = (np.arange(width) * src_w // width).astype(np.intp)
    return np.ascontiguousarray(rgb[ys][:, xs])


def rgb_to_bgra(frame: np.ndarray) -> bytes:
    rgb = fit_rgb(frame)
    bgra = np.empty((HEIGHT, WIDTH, 4), dtype=np.uint8)
    bgra[..., 0] = rgb[..., 2]
    bgra[..., 1] = rgb[..., 1]
    bgra[..., 2] = rgb[..., 0]
    bgra[..., 3] = 255
    return bgra.tobytes()


def pack_frame(bgra: bytes, sequence: int, flags: int = 1) -> bytes:
    if len(bgra) != PIXELS:
        raise ValueError(f"BGRA frame must be {PIXELS} bytes")
    header = _HEADER.pack(
        MAGIC,
        VERSION,
        WIDTH,
        HEIGHT,
        WIDTH * 4,
        sequence & 0xFFFFFFFF,
        PIXELS,
        flags & 0xFFFFFFFF,
    )
    if len(header) != HEADER:
        raise RuntimeError("frame header drifted from 32 bytes")
    return header + bgra


def decode_frame(blob: bytes) -> bytes:
    """Return BGRA pixels. A bad header returns the solid veil, not a partial buffer."""
    veil = veil_pixels()
    if len(blob) < HEADER:
        return veil
    magic, version, width, height, stride, _sequence, size, _flags = _HEADER.unpack_from(blob, 0)
    if (
        magic != MAGIC
        or version != VERSION
        or width != WIDTH
        or height != HEIGHT
        or stride != WIDTH * 4
        or size != PIXELS
    ):
        return veil
    pixels = blob[HEADER : HEADER + PIXELS]
    if len(pixels) != PIXELS:
        return veil
    return pixels


class MemoryBackend:
    """In-process stand-in for the named mapping. Tests use this."""

    def __init__(self) -> None:
        self.blob = b""

    def publish(self, blob: bytes) -> None:
        self.blob = bytes(blob)

    def read(self) -> bytes:
        return self.blob

    def close(self) -> None:
        self.blob = b""


class WindowsMappingBackend:
    """``Local\\VeilLockFrame`` via CreateFileMappingW. Windows only."""

    def __init__(self) -> None:
        if not sys.platform.startswith("win"):
            raise OSError("the named VeilLock mapping exists only on Windows; nothing was registered")
        import ctypes
        from ctypes import wintypes

        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        handle = kernel.CreateFileMappingW(
            wintypes.HANDLE(-1),
            None,
            0x04,
            0,
            MAPPING_BYTES,
            MAPPING_NAME,
        )
        if not handle:
            raise OSError(ctypes.get_last_error(), "CreateFileMappingW failed; no camera was registered by this call")
        view = kernel.MapViewOfFile(handle, 0xF001F, 0, 0, MAPPING_BYTES)
        if not view:
            err = ctypes.get_last_error()
            kernel.CloseHandle(handle)
            raise OSError(err, "MapViewOfFile failed; no camera was registered by this call")
        self._ctypes = ctypes
        self._kernel = kernel
        self._handle = handle
        self._view = view

    def publish(self, blob: bytes) -> None:
        if len(blob) > MAPPING_BYTES:
            raise ValueError("frame does not fit the VeilLock mapping")
        padded = blob + bytes(MAPPING_BYTES - len(blob))
        self._ctypes.memmove(self._view, padded, MAPPING_BYTES)

    def read(self) -> bytes:
        return self._ctypes.string_at(self._view, MAPPING_BYTES)

    def close(self) -> None:
        if self._view:
            self._kernel.UnmapViewOfFile(self._view)
            self._view = None
        if self._handle:
            self._kernel.CloseHandle(self._handle)
            self._handle = None


class WindowsCameraSession:
    """Publish public RGB frames. Does not register the camera and does not open a webcam."""

    def __init__(self, backend: MemoryBackend | WindowsMappingBackend | None = None) -> None:
        self.backend = backend if backend is not None else MemoryBackend()
        self.sequence = 0

    def publish_rgb(self, frame: np.ndarray) -> bytes:
        self.sequence += 1
        blob = pack_frame(rgb_to_bgra(frame), self.sequence)
        self.backend.publish(blob)
        return blob

    def pixels(self) -> bytes:
        return decode_frame(self.backend.read())

    def close(self) -> None:
        self.backend.close()


def default_windows_sink() -> WindowsCameraSession | None:
    """A live mapping on Windows. ``None`` everywhere else, including this development VM."""
    if not sys.platform.startswith("win"):
        return None
    try:
        return WindowsCameraSession(WindowsMappingBackend())
    except OSError:
        return None
