"""VeilLock: consent-gated camera protection via AZ-OS.

Author: Aziel Eliab.

Pipeline: render → encrypt → decode locally → display.
Camera and video are naturally veiled unless you turn obfuscation off
or accept a call through AZ-OS.

Forks are welcome and always allowed.
"""

from __future__ import annotations

from veillock.azos import AzosHook
from veillock.engine import EncryptedFrame, EncryptedStream, VeilLockSession
from veillock.frames import FrameSource
from veillock.phoenix import PhoenixLoop
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck

__version__ = "0.2.0"
__author__ = "Aziel Eliab"
__all__ = [
    "AlwaysPass",
    "AzosHook",
    "EncryptedFrame",
    "EncryptedStream",
    "FrameSource",
    "HaltedError",
    "PhoenixError",
    "PhoenixLoop",
    "PulseCheck",
    "VeilLockSession",
    "__version__",
]
