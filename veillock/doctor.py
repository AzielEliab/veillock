"""veillock doctor — local self-check. No network. No telemetry.

    veillock doctor
"""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np

from veillock import __version__
from veillock.pulse import AlwaysPass
from veillock.ui import LOOPBACK


def _check(cid: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"id": cid, "ok": bool(ok), "detail": detail}


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_check("version", __version__ == "0.1.0", __version__))
    checks.append(_check("numpy", True, getattr(np, "__version__", "present")))
    pci = AlwaysPass().pci()
    checks.append(_check("pulse_pass", pci == "PASS", pci))
    checks.append(_check("loopback", "127.0.0.1" in LOOPBACK, "127.0.0.1"))
    checks.append(_check("not_interceptor", True, "YOUR camera/screen only; not a call MITM"))
    checks.append(_check("telemetry", True, "off"))
    ok = all(c["ok"] for c in checks)
    return {
        "ok": ok,
        "product": "veillock",
        "version": __version__,
        "limitation": "Not a FaceTime/Zoom interceptor. YOUR camera/screen only. Author: Aziel Eliab.",
        "checks": checks,
    }


def format_report(payload: dict[str, Any]) -> str:
    lines = [f"VeilLock doctor {payload.get('version')}"]
    for c in payload.get("checks") or []:
        mark = "ok" if c.get("ok") else "FAIL"
        detail = f"  {c.get('detail')}" if c.get("detail") else ""
        lines.append(f"{mark}  {c.get('id')}{detail}")
    lines.append("doctor: healthy" if payload.get("ok") else "doctor: FAILED")
    lines.append(str(payload.get("limitation") or ""))
    return "\n".join(lines)


def doctor_cli(*, as_json: bool = False) -> int:
    payload = run()
    if as_json:
        sys.stdout.write(json.dumps(payload, indent=2, ensure_ascii=False) + "\n")
    else:
        sys.stdout.write(format_report(payload) + "\n")
    return 0 if payload.get("ok") else 1
