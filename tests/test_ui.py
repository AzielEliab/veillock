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
