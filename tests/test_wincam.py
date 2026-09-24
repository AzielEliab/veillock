"""Windows frame protocol. Registration is not claimed on this machine."""

from __future__ import annotations

from pathlib import Path

import numpy as np

from veillock.wincam import (
    CLSID,
    FRIENDLY_NAME,
    HEADER,
    HEIGHT,
    MAGIC,
    PICKER_NAME,
    WIDTH,
    WindowsCameraSession,
    decode_frame,
    helper_present,
    pack_frame,
    veil_pixels,
)

ROOT = Path(__file__).resolve().parents[1]


def test_round_trip_and_bad_magic_is_a_veil() -> None:
    rgb = np.zeros((HEIGHT, WIDTH, 3), dtype=np.uint8)
    rgb[..., 0] = 10
    rgb[..., 1] = 20
    rgb[..., 2] = 30
    session = WindowsCameraSession()
    blob = session.publish_rgb(rgb)
    assert blob[:4] == MAGIC
    assert len(blob) == HEADER + WIDTH * HEIGHT * 4
    pixels = session.pixels()
    assert pixels[0:4] == bytes((30, 20, 10, 255))
    assert decode_frame(b"nope") == veil_pixels()
    assert decode_frame(b"XXXX" + blob[4:]) == veil_pixels()
    assert helper_present() is False
    assert FRIENDLY_NAME == "VeilLock"
    assert "Windows Virtual Camera" in PICKER_NAME


def test_cpp_matches_the_python_contract_and_does_not_open_a_webcam() -> None:
    header = (ROOT / "windows" / "vcam" / "frame.h").read_text(encoding="utf-8")
    source = (ROOT / "windows" / "vcam" / "veilcam.cpp").read_text(encoding="utf-8")
    registrar = (ROOT / "windows" / "vcam" / "register.cpp").read_text(encoding="utf-8")
    assert 'VEILLOCK_FRAME_MAGIC "VLFC"' in header
    assert "640" in header and "480" in header
    assert CLSID in header
    assert "MFCreateVirtualCamera" in registrar
    assert "MFVirtualCameraType_SoftwareCameraSource" in registrar
    assert "22000" in registrar
    assert "does not hook" in registrar
    assert "CABLE Output" in registrar
    combined = source + registrar
    assert "AddDeviceSourceInfo" not in combined
    assert "MFEnumDeviceSources" not in combined
    assert "CopyPublishedOrVeil" in source
    assert "FillVeil" in source
