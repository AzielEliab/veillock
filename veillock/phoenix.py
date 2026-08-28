"""Phoenix Loop: reboot the display session after repeated tampering.

If N failed integrity checks or decode mismatches are observed, enter
phoenix mode: reset session keys and refuse encrypt/decrypt until PCI
returns PASS. No plaintext frame is produced while phoenix is active.
"""

from __future__ import annotations

from veillock.pulse import PulseCheck

DEFAULT_PHOENIX_THRESHOLD = 3


class PhoenixLoop:
    """Count integrity failures and gate the display session."""

    def __init__(self, threshold: int = DEFAULT_PHOENIX_THRESHOLD) -> None:
        if threshold < 1:
            raise ValueError("phoenix threshold must be >= 1")
        self.threshold = int(threshold)
        self.failures = 0
        self.active = False

    def record_failure(self) -> bool:
        """Record a failed integrity check or decode mismatch.

        Returns True if this call caused entry into phoenix mode.
        """
        self.failures += 1
        if self.failures >= self.threshold:
            self.active = True
            return True
        return False

    def try_restore(self, pulse: PulseCheck) -> bool:
        """If active and ``pulse.pci()`` is PASS, exit phoenix.

        Returns True if the loop restored. Does nothing if not active.
        """
        if not self.active:
            return False
        if pulse.pci() == "PASS":
            self.active = False
            self.failures = 0
            return True
        return False

    def reset_counters(self) -> None:
        self.failures = 0
        self.active = False
