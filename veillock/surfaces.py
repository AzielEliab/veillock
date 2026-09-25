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
import re
from pathlib import Path
from typing import Any

from veillock.coverage import PROFILE_SCHEMA, _normalize_platform, detect, format_detection
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

# Read-only names a later host may call. This module is not that host.
SAFE_CALLS = (
    "describe",
    "join_plan",
    "engulf_plan",
    "suite_tile",
)

_PLATFORMS = frozenset(
    {"linux", "windows", "darwin", "ios", "android", "chromium", "firefox", "safari"}
)
_CONTROL = re.compile(r"[\x00-\x1f\x7f]")
_SHELL = re.compile(r"[;&|$`<>(){}]")
_VIDEO = re.compile(r"/dev/video[0-9]{1,3}\Z")
_SANDBOX_ENV = ("FLATPAK_ID", "SNAP", "SNAP_NAME")


def _one_line(value: object, limit: int, field: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if _CONTROL.search(text) or len(text) > limit:
        raise ValueError(f"{field} must be one short line")
    return text


def _platform(value: object) -> str | None:
    text = _one_line(value, 32, "platform")
    if text is None:
        return None
    plat = _normalize_platform(text)
    if plat not in _PLATFORMS:
        raise ValueError("unknown platform")
    return plat


def _token(value: object, field: str, limit: int = 120) -> str | None:
    text = _one_line(value, limit, field)
    if text is None:
        return None
    if _SHELL.search(text) or text.startswith("-") or ".." in text.split("/"):
        raise ValueError(f"{field} must be a single program or profile name")
    return text


def _video_device(value: object) -> str:
    text = _one_line(value, 16, "video_device") or "/dev/video10"
    if _VIDEO.fullmatch(text) is None:
        raise ValueError("video_device must be a /dev/videoN node")
    return text


def _windows_build(value: object) -> int | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("windows_build must be an integer")
    if value < 0 or value > 300_000:
        raise ValueError("windows_build is out of range")
    return value


def sandbox_environ(source: dict[str, str] | None = None) -> dict[str, str]:
    """Only the sandbox markers. The rest of the environment is not a plan input."""
    import os

    env = source if source is not None else dict(os.environ)
    return {key: env[key] for key in _SANDBOX_ENV if env.get(key)}


def _closed(**extra: Any) -> dict[str, Any]:
    body = {
        "executed": False,
        "joined_call": False,
        "registered_camera": False,
        "returns_argv": False,
        "returns_key": False,
        "lifts_veil": False,
        "writes_recording": False,
        "plaintext_file": False,
        "aes_on_call_path": False,
        "increments_downloads": False,
    }
    body.update(extra)
    return body


def describe(
    process: str | None = None,
    platform: str | None = None,
    bundle_id: str | None = None,
    url: str | None = None,
    **kwargs: Any,
) -> str:
    """Same text ``veillock join`` and ``veillock compat --detect`` print."""
    clean = dict(kwargs)
    if clean.get("capture") is not None:
        clean["capture"] = _token(clean["capture"], "capture", 32)
    if "windows_build" in clean:
        clean["windows_build"] = _windows_build(clean["windows_build"])
    if clean.get("environ") is not None:
        clean["environ"] = sandbox_environ(clean["environ"])
    return format_detection(
        detect(
            _token(process, "process"),
            platform=_platform(platform),
            bundle_id=_token(bundle_id, "bundle", 200),
            url=_one_line(url, 2000, "url"),
            **clean,
        )
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
        _token(process, "process"),
        platform=_platform(platform),
        bundle_id=_token(bundle_id, "bundle", 200),
        url=_one_line(url, 2000, "url"),
        have_vcam=have_vcam,
        opens_v4l2=bool(opens_v4l2),
        sandboxed=bool(sandboxed),
        capture=_token(capture, "capture", 32),
        windows_build=_windows_build(windows_build),
        environ=sandbox_environ(environ) if environ is not None else None,
    )
    return _closed(
        ok=True,
        layer="strategy",
        schema=PROFILE_SCHEMA,
        recording_aes_256_gcm=True,
        assumed_have_vcam=have_vcam,
        capability_source="assumed" if have_vcam is not None else "observed",
        matched=found.matched,
        camera=found.camera,
        mic=found.mic,
        e2e=found.e2e,
        command=found.command,
        meeting=found.meeting,
        note=found.note,
        limit=found.limit,
        report=format_detection(found),
        author="Aziel Eliab",
        lamb_lens="Service, then Clarity, then Peace",
    )


def engulf_plan(
    app: list[str] | str,
    *,
    platform: str | None = None,
    have_vcam: bool | None = None,
    windows_build: int | None = None,
    have_bwrap: bool | None = None,
    video_device: str = "/dev/video10",
) -> dict[str, Any]:
    """Ask whether engulf can start. Does not start the app or return a command line."""
    if isinstance(app, str):
        parts = [_token(app, "app")]
    else:
        parts = [_token(part, "app") for part in app]
    argv = [part for part in parts if part]
    plan = plan_engulf(
        argv or ["app"],
        platform=_platform(platform),
        have_vcam=have_vcam,
        windows_build=_windows_build(windows_build),
        have_bwrap=have_bwrap,
        video_device=_video_device(video_device),
    )
    body = plan.as_dict()
    body.pop("argv", None)
    body.pop("env", None)
    body.update(
        _closed(
            ok=True,
            layer="strategy",
            engulfs=bool(plan.engulfs),
            launch="cli-only",
            assumed_have_vcam=have_vcam,
            capability_source="assumed" if have_vcam is not None or have_bwrap is not None else "observed",
            author="Aziel Eliab",
        )
    )
    return body


def suite_tile() -> dict[str, Any]:
    """The handoff AZInterface can read. This repo does not boot that desk."""
    tile = json.loads(TILE_PATH.read_text(encoding="utf-8"))
    tile["present_in_this_repo"] = True
    tile["consumed_by_azinterface_in_this_repo"] = False
    tile["entries"] = list(ENTRIES)
    tile["safe_calls"] = list(SAFE_CALLS)
    tile["orchestration_host"] = {
        "built": False,
        "mcp": False,
        "node_mesh": False,
        "forensic": False,
        "note": (
            "A later host may call describe, join_plan, engulf_plan, and suite_tile. "
            "Those calls do not launch, join, register a camera, return a key, or lift the veil. "
            "Engulf launch stays on the veillock engulf CLI, which plans again before it starts anything."
        ),
    }
    return tile
