"""One profile registry for the coverage set. Not a market-share table."""

from __future__ import annotations

from pathlib import Path

from veillock.cli import main
import pytest

from veillock.coverage import (
    CAMERA_STRATEGIES,
    E2E_STRATEGIES,
    MIC_STRATEGIES,
    PROFILE_SCHEMA,
    RESOLVED_ONLY,
    AppProfile,
    Variant,
    builtin_profiles,
    coverage_guide_text,
    detect,
    register_profile,
    remove_profile,
)
from veillock.tether import APPS_GUIDE

ROOT = Path(__file__).resolve().parents[1]


def test_builtin_set_is_fifty_profiles_and_only_known_strategies() -> None:
    rows = builtin_profiles()
    assert len(rows) == 50
    assert len({row.app_id for row in rows}) == 50
    for row in rows:
        assert row.schema == PROFILE_SCHEMA
        assert row.variants
        for variant in row.variants:
            assert variant.e2e in E2E_STRATEGIES
            for _key, value in variant.camera:
                assert value in CAMERA_STRATEGIES
                assert value not in RESOLVED_ONLY
            for _key, value in variant.mic:
                assert value in MIC_STRATEGIES
    text = coverage_guide_text()
    assert text in APPS_GUIDE
    assert "not a market-share ranking" in text
    assert "28%" not in text
    assert "iPhone FaceTime cannot" in text
    assert "CABLE Output" in text
    assert "does not hook" in text
    assert "schema is 1" in text
    assert "not an AES mesh" in text
    assert "DirectShow" in text
    paper = (ROOT / "docs" / "app-coverage.md").read_text(encoding="utf-8")
    assert "TalkingPointz" in paper
    assert "not a market-share ranking" in paper
    assert "MFCreateVirtualCamera" in paper
    assert "BlueJeans" in paper


def test_detect_windows_zoom_facetime_and_meet() -> None:
    zoom = detect("Zoom.exe", platform="windows", have_vcam=True)
    assert zoom is not None
    assert zoom.app_id == "zoom" and zoom.kind == "native"
    assert zoom.camera == "win11-vcam"
    assert zoom.mic == "vb-cable"
    assert zoom.e2e == "veillock-link"
    quiet = detect("Zoom.exe", platform="windows", have_vcam=False)
    assert quiet is not None and quiet.camera == "unregistered"
    phone = detect("FaceTime", platform="ios", bundle_id="com.apple.facetime")
    assert phone is not None
    assert phone.camera == "impossible" and phone.e2e == "none"
    mac = detect("FaceTime", platform="darwin")
    assert mac is not None and mac.camera == "pick-cam" and mac.kind == "native"
    meet = detect("chrome", platform="windows", url="https://meet.google.com/abc-defg", have_vcam=True)
    assert meet is not None
    assert meet.app_id == "meet" and meet.kind == "browser"
    assert meet.camera == "extension-getusermedia"
    assert meet.e2e == "insertable-streams"
    firefox = detect("firefox", platform="linux", url="https://meet.google.com/abc")
    assert firefox is not None and firefox.app_id == "meet"
    assert firefox.camera == "pick-cam" and firefox.e2e == "none"
    direct = detect("zoom", platform="linux", opens_v4l2=True, have_vcam=False)
    assert direct is not None and direct.camera == "engulf-v4l2"
    sandboxed = detect("zoom", platform="linux", opens_v4l2=True, sandboxed=True)
    assert sandboxed is not None and sandboxed.camera == "pick-cam"
    unknown = detect("not-a-real-call-app", platform="linux")
    assert unknown.matched is False and unknown.app_id == "unknown"
    assert unknown.camera == "pick-cam" and unknown.schema == PROFILE_SCHEMA
    fresh = detect("brand-new-dialer", platform="linux", capture="v4l2")
    assert fresh.matched is False and fresh.camera == "engulf-v4l2"


def test_register_profile_is_the_extension_point() -> None:
    profile = AppProfile(
        app_id="example-call",
        title="Example Call",
        group="workplace",
        note="Test profile.",
        variants=(
            Variant(
                variant_id="example-call-desktop",
                kind="native",
                processes=("example-call",),
                bundles=(),
                hosts=(),
                camera=(("windows", "win11-vcam"), ("linux", "pick-cam")),
                mic=(("windows", "vb-cable"), ("linux", "linux-veillock-mic")),
                e2e="veillock-link",
            ),
        ),
    )
    register_profile(profile)
    try:
        found = detect("Example-Call.exe", platform="windows", have_vcam=True)
        assert found is not None and found.app_id == "example-call"
        assert found.camera == "win11-vcam"
    finally:
        remove_profile("example-call")
    fallback = detect("example-call", platform="windows", have_vcam=False)
    assert fallback.app_id == "unknown" and fallback.camera == "unregistered"


def test_meetings_share_one_report_and_unknown_capture_wins() -> None:
    teams = detect(url="https://teams.microsoft.com/l/meetup-join/19%3ameeting", platform="chromium")
    assert teams is not None and teams.app_id == "teams" and teams.kind == "browser"
    assert teams.camera == "extension-getusermedia" and teams.e2e == "insertable-streams"
    assert "not an AES mesh" in teams.meeting
    assert "Screen share" in teams.meeting
    firefox = detect("firefox", platform="linux", url="https://teams.live.com/meet/abc")
    assert firefox is not None and firefox.app_id == "teams"
    assert firefox.camera == "pick-cam" and firefox.e2e == "none"
    desktop = detect("ms-teams", platform="windows", have_vcam=True, windows_build=22631)
    assert desktop is not None and desktop.camera == "win11-vcam" and desktop.kind == "native"
    windows_10 = detect("ms-teams", platform="windows", have_vcam=True, windows_build=19041)
    assert windows_10 is not None and windows_10.camera == "unregistered"
    assert "22000" in windows_10.limit
    directshow = detect("teams", platform="windows", have_vcam=True, windows_build=22631, capture="directshow")
    assert directshow is not None and directshow.camera == "directshow-only"
    assert directshow.e2e == "veillock-link"
    boxed = detect("teams", platform="linux", opens_v4l2=True, environ={"FLATPAK_ID": "com.microsoft.Teams"})
    assert boxed is not None and boxed.camera == "pick-cam"
    meet = detect(url="https://meet.google.com/abc-defg-hij", platform="chromium")
    zoom = detect(url="https://zoom.us/j/123", platform="chromium")
    assert meet is not None and zoom is not None
    assert meet.meeting == teams.meeting == zoom.meeting


def test_schema_mismatch_is_refused() -> None:
    profile = AppProfile(
        app_id="future-call",
        title="Future",
        group="workplace",
        note="nope",
        schema=PROFILE_SCHEMA + 1,
        variants=(
            Variant(
                variant_id="future-call-desktop",
                kind="native",
                processes=("future-call",),
                bundles=(),
                hosts=(),
                camera=(("linux", "pick-cam"),),
                mic=(("linux", "linux-veillock-mic"),),
                e2e="veillock-link",
            ),
        ),
    )
    with pytest.raises(ValueError, match="schema"):
        register_profile(profile)
    assert detect("future-call", platform="linux").app_id == "unknown"


def test_cli_compat_detects_without_registering_a_camera(capsys) -> None:
    assert main(["compat", "--detect", "--process", "Zoom.exe", "--platform", "windows", "--vcam"]) == 0
    out = capsys.readouterr().out
    assert "camera=win11-vcam" in out
    assert "CABLE Output" in out
    assert "not AES-256-GCM" in out
    assert main(["join", "https://teams.microsoft.com/l/meetup-join/abc", "--platform", "chromium"]) == 0
    joined = capsys.readouterr().out
    assert "camera=extension-getusermedia" in joined
    assert "matched=yes" in joined
    assert "not an AES mesh" in joined
    assert main(["join", "https://calls.example.test/room", "--platform", "linux"]) == 0
    unknown = capsys.readouterr().out
    assert "matched=no" in unknown
    assert "camera=pick-cam" in unknown
