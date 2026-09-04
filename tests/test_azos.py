"""AZ-OS hook: default veil; user off or call-accept lifts it."""

from __future__ import annotations

from veillock.azos import AzosHook, consent_reason, should_obfuscate
from veillock.cli import main


def test_default_veil_on() -> None:
    hook = AzosHook()
    assert hook.veil_on() is True
    assert hook.reason() == "default veil: camera and video protected"
    assert hook.status()["azos_hook"] is True
    assert hook.status()["user_controls"] is True
    assert should_obfuscate(obfuscation_on=True, call_accepted=False) is True


def test_user_turns_obfuscation_off() -> None:
    hook = AzosHook()
    hook.set_obfuscation(False)
    assert hook.veil_on() is False
    assert hook.reason() == "user turned obfuscation off"
    assert should_obfuscate(obfuscation_on=False, call_accepted=False) is False


def test_azos_call_accept_lifts_veil() -> None:
    hook = AzosHook()
    out = hook.accept_call(actor="Aziel Eliab", call_id="c-1")
    assert out["call_accepted"] is True
    assert out["obfuscate"] is False
    assert out["veil"] == "lifted"
    assert out["reason"] == "user accepted a call through AZ-OS"
    assert out["actor"] == "Aziel Eliab"
    assert should_obfuscate(obfuscation_on=True, call_accepted=True) is False


def test_end_call_reveils_unless_user_off() -> None:
    hook = AzosHook()
    hook.accept_call(actor="user")
    hook.end_call()
    assert hook.veil_on() is True
    hook.set_obfuscation(False)
    hook.accept_call(actor="user")
    hook.end_call()
    assert hook.veil_on() is False


def test_consent_reason_words() -> None:
    assert "protected" in consent_reason(obfuscation_on=True, call_accepted=False)
    assert "turned obfuscation off" in consent_reason(obfuscation_on=False, call_accepted=False)
    assert "AZ-OS" in consent_reason(obfuscation_on=True, call_accepted=True)


def test_cli_azos_status(capsys) -> None:
    assert main(["azos"]) == 0
    out = capsys.readouterr().out
    assert "AZ-OS hook" in out
    assert "veil=on" in out
    assert main(["azos", "--json"]) == 0
    js = capsys.readouterr().out
    assert "azos_hook" in js
    assert main(["azos", "--accept", "--actor", "Aziel Eliab"]) == 0
    accepted = capsys.readouterr().out
    assert "lifted" in accepted
    assert main(["azos", "--end"]) == 0
    ended = capsys.readouterr().out
    assert "veil=on" in ended
    from veillock.azos import HOOK

    HOOK.set_obfuscation(True)
    HOOK.end_call()
