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
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=2)

def test_ui_has_import_export_json() -> None:
    from veillock.ui import PAGE
    assert "Import JSON file" in PAGE
    assert "Export JSON" in PAGE
    assert 'type="file"' in PAGE
    assert "YOUR camera/screen only" in PAGE
    assert "Not a call interceptor" in PAGE
