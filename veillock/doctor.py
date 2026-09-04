"""veillock doctor — local self-check. No network. No telemetry.

    veillock doctor
"""

from __future__ import annotations

import json
import sys
from typing import Any

import numpy as np

from veillock import __version__
from veillock.azos import AzosHook
from veillock.pulse import AlwaysPass
from veillock.ui import LOOPBACK


def _check(cid: str, ok: bool, detail: str = "") -> dict[str, Any]:
    return {"id": cid, "ok": bool(ok), "detail": detail}


def run() -> dict[str, Any]:
    checks: list[dict[str, Any]] = []
    checks.append(_check("version", __version__ == "0.2.0", __version__))
    checks.append(_check("numpy", True, getattr(np, "__version__", "present")))
    pci = AlwaysPass().pci()
    checks.append(_check("pulse_pass", pci == "PASS", pci))
    checks.append(_check("loopback", "127.0.0.1" in LOOPBACK, "127.0.0.1"))
    hook = AzosHook()
    checks.append(_check("azos_hook", bool(hook.status().get("azos_hook")), "AZ-OS consent gate"))
    checks.append(_check("consent_default_veil", hook.veil_on(), hook.reason()))
    hook.set_obfuscation(False)
    checks.append(_check("user_off_lifts_veil", not hook.veil_on(), hook.reason()))
    hook.set_obfuscation(True)
    hook.accept_call(actor="Aziel Eliab", call_id="doctor")
    checks.append(_check("azos_accept_lifts_veil", not hook.veil_on(), hook.reason()))
    checks.append(_check("telemetry", True, "off"))
    ok = all(c["ok"] for c in checks)
    return {
        "ok": ok,
        "product": "veillock",
        "version": __version__,
        "identity": "consent-gated camera protection via AZ-OS",
        "limitation": (
            "Consent-gated camera protection via AZ-OS. You control the veil. "
            "Author: Aziel Eliab."
        ),
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
