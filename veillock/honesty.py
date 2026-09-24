"""Plain-language limits for VeilLock call wrap.

These sentences are the contract. Docs, the local UI, the CLI, and the
Worker skill quote them. Do not soften them into an AES claim.

Author: Aziel Eliab.
"""

from __future__ import annotations

CALL_VIDEO = (
    "The live call path is a keyed visual scramble: 8×8 blocks are "
    "permuted, rotated, and sometimes inverted. A channel swap is not used: "
    "call codecs subsample color (4:2:0) and a channel swap would not survive that. A sync strip is what the peer reads back. An authorized peer can approximately "
    "reverse it after a lossy codec. It is obfuscation. It is not "
    "AES-256-GCM. Skype, Zoom, Meet, Teams, Discord, WhatsApp, Signal, "
    "OBS, and the browser re-encode the pixels; the provider sees the "
    "natural veil or the scrambled tiles, not a GCM ciphertext."
)

CALL_AUDIO = (
    "Call-path audio is obfuscation, not AES-256-GCM. The public "
    "microphone is comfort noise until you turn obfuscation off or accept "
    "a call through AZ-OS. After that lift it is your microphone, or a "
    "keyed permutation of short PCM blocks if you chose scramble. "
    "PulseCheck failure is noise, never the microphone. Opus and AAC do "
    "not carry sample-level ciphertext. A speech codec that rebuilds phase "
    "does not give the original waveform back, with or without the key. "
    "A short block can still contain a speech fragment the provider can hear."
)

LOCAL_RECORDING = (
    "VeilLock's own recording is AES-256-GCM per video frame and per "
    "audio chunk, with key rotation and PulseCheck. That file is "
    "encryption. A call app or screen recorder only stores what left "
    "the virtual camera and microphone: the veil or the scramble."
)

PULSE = (
    "PulseCheck failure halts to veil or noise. Plaintext is not sent "
    "and is not written into a recording."
)

CONSENT = (
    "The veil stays on until you turn obfuscation off or accept a call "
    "through AZ-OS. You control the lift. A protected call then sends "
    "the scramble, not the camera, unless you explicitly choose plaintext."
)

PLATFORM = (
    "iPhone FaceTime cannot select a third-party camera or microphone. "
    "Most phone clients (Zoom, Meet, Teams, WhatsApp, Signal) cannot "
    "either. Use a desktop app that lets you pick the camera and "
    "microphone. VeilLock does not inject into the call app. "
    "Linux: veillock wrap --mic creates a PipeWire or PulseAudio source. "
    "The app selects VeilLock Microphone. That needs pactl and paplay. "
    "It is not a kernel driver. "
    "macOS: no CoreAudio plugin is shipped. If BlackHole is installed, "
    "the app selects BlackHole 2ch and VeilLock feeds that device. "
    "Windows: no audio driver is shipped. If VB-Audio Virtual Cable is "
    "installed, the app selects CABLE Output and VeilLock writes to "
    "CABLE Input."
)

SCREEN_SHARE = (
    "If you screen-share a window that already shows unveiled video, "
    "that share is the picture on the screen. Wrap covers the camera "
    "and microphone the call app captures."
)

LAMBS = "Lamb Lens order: Service, then Clarity, then Peace."

AUTHOR = "Aziel Eliab"
