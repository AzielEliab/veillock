"""AZ-OS hook — consent-gated camera protection.

VeilLock's identity is a privacy veil on the user's own camera and video.
The veil stays on unless (a) the user turns obfuscation off, or (b) the
user accepts a call through AZ-OS. The user controls both paths.

This is a local overlay receipt, not a kernel and not remote exec.
Hosted AZ-OS halt is a token, not killing the caller OS.

Author: Aziel Eliab.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


AZOS_OVERLAY = "AZ-OS"
AZOS_INTERFACE = "AZ Interface"
AZOS_HOST = "https://azos-download-tracker.vibelock.workers.dev"
IDENTITY = "consent-gated camera protection via AZ-OS"
DEFAULT_OBFUSCATION = True


def should_obfuscate(*, obfuscation_on: bool, call_accepted: bool) -> bool:
    """Default veil. Lift only on explicit user control."""
    if not obfuscation_on:
        return False
    if call_accepted:
        return False
    return True


def consent_reason(*, obfuscation_on: bool, call_accepted: bool) -> str:
    if not obfuscation_on:
        return "user turned obfuscation off"
    if call_accepted:
        return "user accepted a call through AZ-OS"
    return "default veil: camera and video protected"


@dataclass
class AzosHook:
    """Local AZ-OS consent gate for the camera and video feed.

    Session-memory only. No disk store. No telemetry.
    """

    obfuscation_on: bool = DEFAULT_OBFUSCATION
    call_accepted: bool = False
    actor: str = ""
    call_id: str | None = None
    overlay: str = AZOS_OVERLAY
    _receipts: list[dict[str, Any]] = field(default_factory=list)

    def veil_on(self) -> bool:
        return should_obfuscate(
            obfuscation_on=bool(self.obfuscation_on),
            call_accepted=bool(self.call_accepted),
        )

    def reason(self) -> str:
        return consent_reason(
            obfuscation_on=bool(self.obfuscation_on),
            call_accepted=bool(self.call_accepted),
        )

    def set_obfuscation(self, on: bool) -> dict[str, Any]:
        """User toggle. Off is an explicit lift. On restores the default veil."""
        self.obfuscation_on = bool(on)
        if self.obfuscation_on is False:
            self._receipts.append({"kind": "obfuscation_off", "actor": self.actor or "user"})
        return self.status()

    def accept_call(self, actor: str = "", call_id: str | None = None) -> dict[str, Any]:
        """User accepted a call through AZ-OS. Lifts the veil for this session."""
        name = str(actor or self.actor or "user").strip() or "user"
        self.actor = name
        self.call_id = str(call_id) if call_id else self.call_id
        self.call_accepted = True
        self._receipts.append(
            {
                "kind": "call_accept",
                "actor": name,
                "call_id": self.call_id,
                "overlay": self.overlay,
            }
        )
        return self.status()

    def end_call(self) -> dict[str, Any]:
        """Call ended. Re-veil unless the user left obfuscation off."""
        self.call_accepted = False
        self.call_id = None
        self._receipts.append({"kind": "call_end", "actor": self.actor or "user"})
        return self.status()

    def status(self) -> dict[str, Any]:
        veil = self.veil_on()
        return {
            "ok": True,
            "product": "veillock",
            "identity": IDENTITY,
            "azos_hook": True,
            "overlay": self.overlay,
            "interface": AZOS_INTERFACE,
            "user_controls": True,
            "obfuscation_on": bool(self.obfuscation_on),
            "call_accepted": bool(self.call_accepted),
            "obfuscate": veil,
            "veil": "on" if veil else "lifted",
            "reason": self.reason(),
            "actor": self.actor or None,
            "call_id": self.call_id,
            "kernel": False,
            "kills_caller_os": False,
            "remote_exec": False,
            "hosted_azos": AZOS_HOST,
        }


# Process-local hook for the localhost UI and CLI.
HOOK = AzosHook()
