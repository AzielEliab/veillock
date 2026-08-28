"""TemporalLock integrity gating (PulseCheck).

A PulseCheck returns "PASS" or a failure token. If PCI does not PASS,
frame generation HALTS and no plaintext frame is produced.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


class HaltedError(Exception):
    """Frame generation halted; no plaintext frame was produced."""


class PhoenixError(HaltedError):
    """Phoenix loop is active: session rebooted, plaintext refused until PCI PASS."""


@runtime_checkable
class PulseCheck(Protocol):
    """Integrity gate consulted before any plaintext frame is produced."""

    def pci(self) -> str:
        """Return ``"PASS"`` on success, or any other string on failure."""
        ...


class AlwaysPass:
    """Default PulseCheck: always returns PASS."""

    def pci(self) -> str:
        return "PASS"


class CallablePulse:
    """Wrap a zero-arg callable as a PulseCheck."""

    def __init__(self, fn):
        self._fn = fn

    def pci(self) -> str:
        return self._fn()
