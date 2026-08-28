"""Strip window identifiers, application fingerprints, and UI telemetry.

Scrubbed keys never enter AES-GCM associated data or public headers.
"""

from __future__ import annotations

import json
import struct
from typing import Any, Mapping

# Exact names plus common aliases. Tests assert these are absent from AAD/headers.
SCRUB_KEYS = frozenset(
    {
        "window_id",
        "window_ids",
        "window_identifier",
        "window_identifiers",
        "app_fingerprint",
        "application_fingerprint",
        "application_fingerprints",
        "ui_telemetry",
        "telemetry",
        "app_id",
        "hwnd",
        "process_id",
        "pid",
    }
)

_HEADER_MAGIC = b"VLCK"
_HEADER_VERSION = 1


def scrub_metadata(meta: Mapping[str, Any] | None) -> dict[str, Any]:
    """Return a new dict with identifying / telemetry keys removed."""
    if not meta:
        return {}
    out: dict[str, Any] = {}
    for key, value in meta.items():
        if str(key).lower() in SCRUB_KEYS:
            continue
        out[str(key)] = value
    return out


def build_headers(
    frame_index: int,
    shape: tuple[int, int, int],
    epoch: int,
    metadata: Mapping[str, Any] | None,
    mode: str,
) -> dict[str, Any]:
    """Public headers: geometry + mode + scrubbed metadata. No fingerprints."""
    h, w, c = (int(shape[0]), int(shape[1]), int(shape[2]))
    headers: dict[str, Any] = {
        "frame_index": int(frame_index),
        "height": h,
        "width": w,
        "channels": c,
        "epoch": int(epoch),
        "mode": str(mode),
    }
    headers.update(scrub_metadata(metadata))
    return headers


def pack_aad(headers: Mapping[str, Any]) -> bytes:
    """Canonical associated data: fixed binary prefix plus JSON of headers.

    The JSON object is sorted by key so AAD is stable. Scrubbed keys are
    already absent from ``headers``.
    """
    h = int(headers["height"])
    w = int(headers["width"])
    c = int(headers["channels"])
    epoch = int(headers["epoch"])
    index = int(headers["frame_index"])
    prefix = struct.pack("<4sBIIIQQ", _HEADER_MAGIC, _HEADER_VERSION, h, w, c, epoch, index)
    body = json.dumps(headers, sort_keys=True, separators=(",", ":"), default=str).encode("utf-8")
    return prefix + body
