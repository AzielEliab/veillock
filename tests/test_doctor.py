"""Doctor reports the AZ-OS consent gate."""

from __future__ import annotations

from veillock.cli import main
from veillock.doctor import run


def test_doctor_healthy() -> None:
    payload = run()
    assert payload["ok"] is True
    ids = {c["id"]: c for c in payload["checks"]}
    assert ids["azos_hook"]["ok"] is True
    assert ids["consent_default_veil"]["ok"] is True
    assert ids["user_off_lifts_veil"]["ok"] is True
    assert ids["azos_accept_lifts_veil"]["ok"] is True
    assert "AZ-OS" in payload["limitation"]
    assert payload["version"] == "0.2.0"


def test_doctor_cli(capsys) -> None:
    assert main(["doctor"]) == 0
    out = capsys.readouterr().out
    assert "azos_hook" in out
    assert "healthy" in out
