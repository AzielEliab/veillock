"""One profile registry for the coverage set. Not a market-share table."""

from __future__ import annotations

from pathlib import Path

from veillock.cli import main
from veillock.coverage import (
    CAMERA_STRATEGIES,
    E2E_STRATEGIES,
    MIC_STRATEGIES,
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
        assert row.variants
        for variant in row.variants:
            assert variant.e2e in E2E_STRATEGIES
            for _key, value in variant.camera:
                assert value in CAMERA_STRATEGIES
                assert value != "unregistered"
            for _key, value in variant.mic:
                assert value in MIC_STRATEGIES
    text = coverage_guide_text()
    assert text in APPS_GUIDE
    assert "not a market-share ranking" in text
    assert "28%" not in text
    assert "iPhone FaceTime cannot" in text
    assert "CABLE Output" in text
    assert "does not hook" in text
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
    assert detect("not-a-real-call-app") is None


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
    assert detect("example-call", platform="windows") is None


def test_cli_compat_detects_without_registering_a_camera(capsys) -> None:
    assert main(["compat", "--detect", "--process", "Zoom.exe", "--platform", "windows", "--vcam"]) == 0
    out = capsys.readouterr().out
    assert "camera=win11-vcam" in out
    assert "CABLE Output" in out
    assert "not AES-256-GCM" in out
