"""VeilLock: live-stream encryption of visual output before display.

July 2026 whitepaper implementation by Aziel Eliab.

Pipeline: render → encrypt → decode locally → display.
Without the correct runtime key state, the display is undecodable noise.

Forks are welcome and always allowed.
"""

from __future__ import annotations

from veillock.engine import EncryptedFrame, EncryptedStream, VeilLockSession
from veillock.frames import FrameSource
from veillock.phoenix import PhoenixLoop
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck

__version__ = "0.1.0"
__author__ = "Aziel Eliab"
__all__ = [
    "AlwaysPass",
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
