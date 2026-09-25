"""Smoke the localhost UI. No network beyond 127.0.0.1."""

from __future__ import annotations

import threading
from http.server import ThreadingHTTPServer

from veillock.cli import _build_parser
from veillock.ui import DEFAULT_HOST, DEFAULT_PORT, Handler


def test_cli_ui_defaults() -> None:
    args = _build_parser().parse_args(["ui"])
    assert args.host == "127.0.0.1"
    assert args.host == DEFAULT_HOST
    assert args.port == 8761
    assert args.port == DEFAULT_PORT
    serve = _build_parser().parse_args(["serve"])
    assert serve.cmd in ("ui", "serve")
    assert serve.host == "127.0.0.1"


def _start():
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    return httpd, thread


def test_ui_get_root_contains_tether() -> None:
    import urllib.request

    httpd, thread = _start()
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as res:
            body = res.read()
            assert res.status == 200
            assert b"VeilLock" in body
            assert b"127.0.0.1" in body
            assert b"Tether" in body
            assert b"Wrap any call" in body
            assert b"not AES-256-GCM" in body
            assert b"AZ-OS" in body
            assert b"consent" in body.lower() or b"Consent" in body
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_ui_azos_accept_lifts_veil() -> None:
    import json
    import urllib.request

    httpd, thread = _start()
    try:
        port = httpd.server_address[1]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/azos/accept",
            data=json.dumps({"actor": "Aziel Eliab"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            body = json.loads(res.read().decode("utf-8"))
            assert res.status == 200
            assert body.get("azos_hook") is True
            assert body.get("veil") == "lifted"
            assert "AZ-OS" in (body.get("reason") or "")
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/azos/end",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as res:
            body = json.loads(res.read().decode("utf-8"))
            assert body.get("veil") == "on"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_ui_wrap_preview_and_record_demo() -> None:
    import json
    import urllib.request

    httpd, thread = _start()
    try:
        port = httpd.server_address[1]
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/wrap/preview",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=15) as res:
            body = json.loads(res.read().decode("utf-8"))
        assert body["aes_256_gcm"] is False
        assert body["with_key"]["authorized"] is True
        assert body["with_key"]["correlation"] > 0.9
        assert body["without_key"]["authorized"] is False
        assert body["provider"]["correlation"] < 0.25
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/record/demo",
            data=b"{}",
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=15) as res:
            rec = json.loads(res.read().decode("utf-8"))
        assert rec["aes_256_gcm"] is True
        assert rec["match"] is True
        assert "AES-256-GCM" in rec["note"]
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)


def test_ui_join_engulf_and_suite_stay_on_the_plan() -> None:
    import json
    import urllib.error
    import urllib.request

    httpd, thread = _start()
    try:
        port = httpd.server_address[1]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=5) as res:
            page = res.read()
        assert b"Plan this link" in page
        assert b"Plan engulf" in page
        assert b"Seal and play in memory" in page
        assert b"AZInterface" in page
        req = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/join",
            data=json.dumps(
                {
                    "url": "https://teams.microsoft.com/l/meetup-join/abc",
                    "platform": "chromium",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=5) as res:
            joined = json.loads(res.read().decode("utf-8"))
        assert joined["camera"] == "extension-getusermedia"
        assert joined["joined_call"] is False
        assert joined["aes_on_call_path"] is False
        assert joined["executed"] is False
        assert "not an AES mesh" in joined["report"]
        req2 = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/engulf/plan",
            data=json.dumps({"app": "zoom", "platform": "windows"}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req2, timeout=5) as res:
            plan = json.loads(res.read().decode("utf-8"))
        assert plan["executed"] is False
        assert plan["registered_camera"] is False
        assert plan["engulfs"] is False
        assert "does not hook" in plan["note"]
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/suite", timeout=5) as res:
            tile = json.loads(res.read().decode("utf-8"))
        assert tile["consumed_by_azinterface_in_this_repo"] is False
        assert tile["merged_into_azinterface"] is False
        assert tile["implemented_in_azinterface_repo"] is False
        assert tile["honesty"]["aes_on_call_path"] is False
        assert tile["honesty"]["increments_downloads"] is False
        assert tile["orchestration_host"]["built"] is False
        assert tile["orchestration_host"]["mcp"] is False
        assert "join_plan" in tile["safe_calls"]
        assert "wrap" in tile["entries"]
        assert "play" in tile["entries"]
        lied = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/join",
            data=json.dumps(
                {
                    "process": "Zoom.exe",
                    "platform": "windows",
                    "have_vcam": True,
                    "capture": "media-foundation",
                }
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(lied, timeout=5) as res:
            honest = json.loads(res.read().decode("utf-8"))
        assert honest["camera"] == "unregistered"
        assert honest["registered_camera"] is False
        assert honest["returns_key"] is False
        assert honest["lifts_veil"] is False
        assert "argv" not in honest
        forged = urllib.request.Request(
            f"http://127.0.0.1:{port}/api/engulf/plan",
            data=json.dumps(
                {"app": "zoom;id", "platform": "linux", "have_vcam": True, "video_device": "/etc/passwd"}
            ).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            urllib.request.urlopen(forged, timeout=5)
            raise AssertionError("shell-looking app was accepted")
        except urllib.error.HTTPError as exc:
            refused = json.loads(exc.read().decode("utf-8"))
            assert exc.code == 400
        assert refused["ok"] is False
        assert refused["executed"] is False
        assert "argv" not in refused
        assert "argv" not in plan
        assert plan["returns_argv"] is False
        assert plan["returns_key"] is False
        assert plan["launch"] == "cli-only"
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)
