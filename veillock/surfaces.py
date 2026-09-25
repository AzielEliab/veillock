"""One adapter between strategy and the desks that show it.

CLI, the loopback UI, and the suite tile call these functions. They call
``coverage.detect`` and ``engulf.plan_engulf``. They do not launch a call
app, join a meeting, or register a camera.

Engine code (scramble, AES recordings, PulseCheck) stays under those
modules. This file does not reimplement it.

Author: Aziel Eliab.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from veillock.coverage import PROFILE_SCHEMA, detect, format_detection
from veillock.engulf import plan_engulf

REPO_ROOT = Path(__file__).resolve().parents[1]
TILE_PATH = REPO_ROOT / "suite" / "azinterface-tile.json"

ENTRIES = (
    "wrap",
    "engulf",
    "join",
    "link",
    "play",
    "record",
)


def describe(
    process: str | None = None,
    platform: str | None = None,
    bundle_id: str | None = None,
    url: str | None = None,
    **kwargs: Any,
) -> str:
    """Same text ``veillock join`` and ``veillock compat --detect`` print."""
    return format_detection(
        detect(process, platform=platform, bundle_id=bundle_id, url=url, **kwargs)
    )


def join_plan(
    url: str | None = None,
    *,
    process: str | None = None,
    platform: str | None = None,
    bundle_id: str | None = None,
    have_vcam: bool | None = None,
    opens_v4l2: bool = False,
    sandboxed: bool = False,
    capture: str | None = None,
    windows_build: int | None = None,
    environ: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Plan a meeting link. Does not join the call."""
    found = detect(
        process,
        platform=platform,
        bundle_id=bundle_id,
        url=url,
        have_vcam=have_vcam,
        opens_v4l2=opens_v4l2,
        sandboxed=sandboxed,
        capture=capture,
        windows_build=windows_build,
        environ=environ,
    )
    return {
        "ok": True,
        "layer": "strategy",
        "schema": PROFILE_SCHEMA,
        "joined_call": False,
        "registered_camera": False,
        "executed": False,
        "aes_on_call_path": False,
        "recording_aes_256_gcm": True,
        "matched": found.matched,
        "camera": found.camera,
        "mic": found.mic,
        "e2e": found.e2e,
        "command": found.command,
        "meeting": found.meeting,
        "note": found.note,
        "limit": found.limit,
        "report": format_detection(found),
        "author": "Aziel Eliab",
        "lamb_lens": "Service, then Clarity, then Peace",
    }


def engulf_plan(
    app: list[str] | str,
    *,
    platform: str | None = None,
    have_vcam: bool | None = None,
    windows_build: int | None = None,
    have_bwrap: bool | None = None,
    video_device: str = "/dev/video10",
) -> dict[str, Any]:
    """Ask whether engulf can start. Does not start the app."""
    argv = [app] if isinstance(app, str) else [part for part in app if part and part != "--"]
    plan = plan_engulf(
        argv or ["app"],
        platform=platform,
        have_vcam=have_vcam,
        windows_build=windows_build,
        have_bwrap=have_bwrap,
        video_device=video_device,
    )
    body = plan.as_dict()
    body.update(
        {
            "ok": True,
            "layer": "strategy",
            "executed": False,
            "registered_camera": False,
            "aes_on_call_path": False,
            "author": "Aziel Eliab",
        }
    )
    return body


def suite_tile() -> dict[str, Any]:
    """The handoff AZInterface can read. This repo does not boot that desk."""
    tile = json.loads(TILE_PATH.read_text(encoding="utf-8"))
    tile["present_in_this_repo"] = True
    tile["consumed_by_azinterface_in_this_repo"] = False
    tile["entries"] = list(ENTRIES)
    return tile
