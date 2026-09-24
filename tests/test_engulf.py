"""Engulf only where the platform actually allows it."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from veillock.cli import main
from veillock.engulf import ENGULF_ROWS, engulf_guide_text, plan_engulf
from veillock.tether import APPS_GUIDE

ROOT = Path(__file__).resolve().parents[1]


def test_table_says_what_each_platform_can_do() -> None:
    by_platform = {(row.platform, row.engulfs) for row in ENGULF_ROWS}
    assert ("Linux", True) in by_platform
    assert ("Windows", False) in by_platform
    assert ("macOS", False) in by_platform
    assert ("iOS", False) in by_platform
    assert ("Browser (Chromium)", True) in by_platform
    text = engulf_guide_text()
    assert text in APPS_GUIDE
    for phrase in (
        "not AES-256-GCM",
        "AES-256-GCM",
        "iPhone FaceTime cannot",
        "SIP",
        "Apple-signed FaceTime",
        "Apps cannot be wrapped",
        "PipeWire",
        "does not hook",
    ):
        assert phrase in text


def test_plans_refuse_platforms_that_cannot_be_wrapped() -> None:
    app = ["zoom"]
    mac = plan_engulf(app, platform="darwin", have_bwrap=True, preload="/tmp/x.so")
    windows = plan_engulf(app, platform="windows", have_bwrap=True, preload="/tmp/x.so")
    ios = plan_engulf(app, platform="ios")
    browser = plan_engulf(["google-chrome"], platform="linux", have_bwrap=True, preload="/tmp/x.so")
    assert mac.engulfs is False and "FaceTime" in mac.note
    assert windows.engulfs is False and "does not hook" in windows.note
    assert "no camera was registered" in windows.note
    ready = plan_engulf(app, platform="windows", have_vcam=True, vcam_helper="/opt/veil/veilcam-register.exe")
    assert ready.engulfs is True
    assert ready.argv[0].endswith("veilcam-register.exe")
    assert ready.argv[1:] == ["--", "zoom"]
    for phrase in ("does not hook", "CABLE Output", "Windows Virtual Camera", "not AES-256-GCM"):
        assert phrase in ready.note
    windows_10 = plan_engulf(app, platform="windows", have_vcam=True, windows_build=19041)
    assert windows_10.engulfs is False and windows_10.argv == []
    assert "22000" in windows_10.note and "does not hook" in windows_10.note
    assert "veillock wrap --mic" in mac.note
    assert ios.engulfs is False and "cannot be wrapped" in ios.note
    assert browser.engulfs is False and "extension" in browser.note
    missing = plan_engulf(["ffmpeg"], platform="linux", have_bwrap=False, preload="")
    assert missing.engulfs is False
    assert missing.argv == []


def test_linux_bwrap_plan_hides_other_video_nodes() -> None:
    plan = plan_engulf(["ffmpeg", "-i", "/dev/video0"], platform="linux", have_bwrap=True, video_device="/tmp/veilcam")
    assert plan.engulfs is True
    assert plan.argv[0] == "bwrap"
    assert plan.argv[plan.argv.index("--bind") + 1] == "/tmp/veilcam"
    assert "/dev/video0" in plan.argv
    assert "--dev" in plan.argv
    assert plan.env["PULSE_SOURCE"] == "VeilLock"
    assert plan.env["VEILLOCK_VIDEO"] == "/tmp/veilcam"


def test_preload_redirects_only_video_opens(tmp_path: Path) -> None:
    source = ROOT / "engulf" / "libveilcapture.c"
    library = tmp_path / "libveilcapture.so"
    built = subprocess.run(
        ["gcc", "-shared", "-fPIC", "-o", str(library), str(source), "-ldl"],
        check=False,
        capture_output=True,
        text=True,
    )
    assert built.returncode == 0, built.stderr
    device = tmp_path / "veil-device"
    device.write_bytes(b"VEIL-DEVICE")
    other = tmp_path / "plain.txt"
    other.write_bytes(b"PLAIN-FILE")
    env = dict(os.environ)
    env["LD_PRELOAD"] = str(library)
    env["VEILLOCK_VIDEO"] = str(device)

    def opened(path: str) -> bytes:
        proc = subprocess.run(
            [sys.executable, "-c", "import os,sys; fd=os.open(sys.argv[1], os.O_RDONLY); sys.stdout.buffer.write(os.read(fd, 64))", path],
            check=False,
            capture_output=True,
            env=env,
        )
        assert proc.returncode == 0, proc.stderr
        return proc.stdout

    assert opened("/dev/video0") == b"VEIL-DEVICE"
    assert opened("/dev/video2") == b"VEIL-DEVICE"
    assert opened(str(other)) == b"PLAIN-FILE"
    plan = plan_engulf(["ffmpeg"], platform="linux", have_bwrap=False, preload=str(library), video_device=str(device))
    assert plan.engulfs is True
    assert plan.env["LD_PRELOAD"].startswith(str(library))
    assert "not AES-256-GCM" in plan.note


def test_cli_engulf_does_not_start_a_browser(capsys) -> None:
    assert main(["engulf", "--", "google-chrome"]) == 2
    out = capsys.readouterr().out
    assert "extension" in out
    assert "iPhone FaceTime cannot" in out
