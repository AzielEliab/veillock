"""Identifying metadata is stripped from headers and associated data."""

from __future__ import annotations

from veillock.engine import VeilLockSession
from veillock.metadata import SCRUB_KEYS, scrub_metadata


def test_scrub_drops_window_app_telemetry_keys() -> None:
    meta = {
        "window_id": "0xHWND",
        "window_identifiers": ["main"],
        "app_fingerprint": "com.example.app",
        "application_fingerprint": "deadbeef",
        "ui_telemetry": {"clicks": 3},
        "title": "ok-to-keep",
        "fps": 30,
    }
    out = scrub_metadata(meta)
    assert "title" in out and out["fps"] == 30
    for k in (
        "window_id",
        "window_identifiers",
        "app_fingerprint",
        "application_fingerprint",
        "ui_telemetry",
    ):
        assert k not in out


def test_headers_and_aad_omit_scrubbed_keys(frames_16, session_key: bytes) -> None:
    meta = {
        "window_id": "win-9",
        "app_fingerprint": "fp",
        "ui_telemetry": {"k": 1},
        "note": "safe",
    }
    sess = VeilLockSession(session_key=session_key, rotation_interval=60)
    sealed = sess.encrypt_frame(frames_16[0], metadata=meta)
    assert sealed.headers.get("note") == "safe"
    for k in SCRUB_KEYS:
        assert k not in sealed.headers
        assert k.encode("utf-8") not in sealed.aad
    # Raw identifying values must not leak into AAD either.
    assert b"win-9" not in sealed.aad
    assert b"fp" not in sealed.aad
    assert b"safe" in sealed.aad
