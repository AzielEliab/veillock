# VeilLock

**Consent-gated camera protection via AZ-OS**

**Author:** Aziel Eliab
**Date:** September 2026
**License:** Apache-2.0

---

## Abstract

VeilLock encrypts all visual output, UI rendering, and screen-level data
streams **before** they reach any external display. The pipeline is:

```
render → encrypt → decode locally → display
```

Without the correct runtime key state, the display is undecodable noise.
Captured ciphertext is not a valid image. The engine framebuffer does not
retain plaintext after encryption returns.

This document is the specification implemented by the `veillock` Python
package. Camera and video are naturally veiled unless the user turns
obfuscation off or accepts a call through AZ-OS. The user controls both
paths.

Forks are welcome and always allowed.

---

## Pipeline

1. A producer renders a visual frame (RGB, uint8).
2. The Frame Encryption Engine seals the frame under a per-frame AES-256-GCM
   key derived from the current session key.
3. A Trusted Decode Surface, holding the matching runtime key state,
   decrypts immediately before the physical display.
4. If PulseCheck (PCI) does not PASS, frame generation **halts**. No
   plaintext frame is produced.
5. After every `rotation_interval` frames the session key ratchets forward
   and the previous key is dropped (forward secrecy).

Target latency is **&lt;1 ms/frame for small frames**. That is a design
target for an efficient numpy + `cryptography` implementation, not a
measured benchmark published here.

---

## Architecture

### Layer 1 — Render Capture

Intercept visual frames **before** they are handed to a GPU/display
scanout. In software this is a `FrameSource` that yields RGB uint8 numpy
arrays already in the caller’s possession. VeilLock does not sample
another process’s framebuffer.

### Layer 2 — Frame Encryption Engine

Each frame is encrypted with a high-speed symmetric cipher suitable for
streaming (AES-256-GCM). Associated data carries geometry and mode, never
window identifiers, application fingerprints, or UI telemetry.

### Layer 3 — Trusted Decode Surface

Authorized decrypt happens immediately before physical display. The same
ratchet that sealed the frame must be in lockstep on the decoder. A
session that only holds the *current* epoch key cannot open older epochs.

---

## Encryption model

Continuous stream encryption with forward-secure rotation.

### Per-frame key derivation

```
frame_key = SHA-256(session_key || frame_index_le64)
```

The digest is 32 bytes and is used as an AES-256 key. The GCM nonce is
12 bytes derived from `frame_index` so the `(key, nonce)` pair is unique
for every frame.

### Rotation

Default `rotation_interval` is **120** frames. Valid range is **60–240**.

After every `rotation_interval` frames:

```
session_key = SHA-256(session_key || b"rotate" || epoch_index_le64)
```

`epoch_index` is packed as little-endian uint64. The previous session
key is zeroed and dropped. Compromising the current key does not decrypt
frames from earlier epochs (SHA-256 is one-way; the engine does not keep
old keys).

### AEAD

AES-256-GCM via the `cryptography` library. Associated data is a packed
header plus canonical JSON of **scrubbed** public headers (frame index,
shape, epoch, mode, and any remaining non-identifying metadata).

---

## TemporalLock / integrity gating

`PulseCheck.pci()` returns `"PASS"` or a failure token.

If PCI does not PASS:

- Frame generation **halts**.
- `HaltedError` is raised.
- No plaintext frame is produced (the engine framebuffer is not filled
  with the rejected frame).

This gate sits in front of both `FrameSource` iteration and
`VeilLockSession.encrypt_frame` / `decrypt_frame`.

---

## Attack resistance (properties of the pipeline)

These are invariants, tested on synthetic frames:

1. **Ciphertext is not a valid image.** A captured sealed frame, viewed
   as pixels, is high-entropy and is not the source RGB. Without the
   session key it does not decode.
2. **Framebuffer zeroing.** After `encrypt_frame` returns, the engine
   framebuffer contains only zeros. Plaintext is not retained.
3. **Forward secrecy.** After a rotation, the in-memory current key
   cannot derive previous epoch keys.
4. **Wrong key fails closed.** AES-GCM authentication failure is a hard
   error (`DecryptError`), counted as tamper.

---

## Phoenix Loop

Repeated display tampering — **N** failed integrity checks or decode
mismatches (default N = 3) — enters phoenix mode:

- The display session is rebooted: session keys are regenerated, old
  material is dropped, frame/epoch counters reset.
- Encrypt and decrypt **refuse** until `pci()` returns PASS. No
  plaintext frame is produced (`PhoenixError`, a `HaltedError`).
- When PCI PASSes, the loop restores and a fresh session continues.

This is a continuous reboot of the display session, not a process-killer
and not an attack on a third-party machine.

---

## Metadata scrubbing

Before encryption, a `FrameMetadata` mapping is scrubbed. The following
keys (and common aliases) are removed and must be absent from associated
data and public headers:

- window identifiers (`window_id`, `window_identifiers`, `hwnd`, …)
- application fingerprints (`app_fingerprint`, `application_fingerprint`, …)
- UI telemetry (`ui_telemetry`, `telemetry`, …)

Anything left (for example a non-identifying `title` or `fps`) may be
bound as associated data.

---

## Deployment modes

### private

Local display only. A single session key exists in the encrypting
process. It is **not** written into the ciphertext package. An operator
who later decrypts a saved package must already hold the key.

### secure_broadcast (`broadcast`)

Authorized receivers obtain the root session key wrapped under a
receiver secret (HMAC-derived AES-GCM key wrap). Tests use this wrap;
the package never carries the raw session key.

### obfuscation

Attackers looking at the display-facing stream see **synthetic UI
noise** (structured decoy frames: fake windows/panels) instead of
ciphertext snow. Decoys are not plaintext. The real frames remain
AES-GCM sealed for an authorized decoder.

---

## Software mapping

| Spec | Code |
|------|------|
| Library entry | `veillock.engine.VeilLockSession` |
| Render capture | `veillock.frames.FrameSource` |
| PulseCheck / HaltedError | `veillock.pulse` |
| Phoenix Loop | `veillock.phoenix.PhoenixLoop` |
| Scrub | `veillock.metadata.scrub_metadata` |
| Modes | `veillock.modes.Mode` |
| AZ-OS hook | `veillock.azos.AzosHook` |
| Natural camera veil | `veillock.modes.natural_camera_veil` |
| CLI | `veillock encrypt` / `decrypt` / `tether` / `azos` / `version` |

Tests use synthetic 16×16 and 64×64 RGB frames. No hardware is required.

---

## Call wrap

A call application re-encodes video with a lossy codec. AES-256-GCM
ciphertext painted into pixels does not survive that trip, so the live
call is not AES-256-GCM.

When the user lifts the veil for a protected call, VeilLock sends a
keyed visual scramble: the frame is tiled into 8×8 blocks, the blocks
are permuted, rotated, and sometimes inverted. Channel swaps are not
used, because call codecs subsample color and a swap would not come back.
The top strip carries a sync pattern and the start of a keyed check.
The bottom row carries the rest of that check. An authorized
peer reverses the same operations on a capture of the incoming image.
Reconstruction after a codec is approximate. Without the key the check
fails and the peer is shown a veil, not a shuffled face. The call
provider sees the veil (consent still on) or the tiles (consent lifted).
This is obfuscation.

Call audio defaults to comfort noise. After the user lifts the veil it
is the microphone, or an optional keyed permutation of short PCM blocks.
That is the same class of obfuscation. Opus and AAC do not preserve
sample-level ciphertext. A codec that discards phase does not return
the waveform. Blocks can still contain short speech fragments.
PulseCheck failure on this path is noise, never the microphone.

The virtual microphone is not the same thing on every operating system.
On Linux, `veillock wrap --mic` creates a PipeWire or PulseAudio source
described as VeilLock Microphone (`module-null-sink` plus
`module-remap-source`, fed by `paplay`, unloaded on stop). That is not
a kernel driver. On macOS no CoreAudio HAL plugin is shipped; if
BlackHole is installed the call app selects BlackHole 2ch. On Windows
no audio driver is shipped; if VB-Audio Virtual Cable is installed the
call app selects CABLE Output and VeilLock writes to CABLE Input. The
real microphone can be written into the AES-256-GCM recording while the
call app receives only the public audio.

`veillock record` / `veillock play` write a separate file sealed with
AES-256-GCM, key rotation, and PulseCheck. Video and audio, video only,
and audio only all use that file, including a recording of the decrypted
stream received from a peer. The key is not stored in the file. Each
chunk is sealed and flushed before the next, so a crash leaves sealed
chunks rather than plaintext. Playback decrypts in memory inside
VeilLock. A plaintext export exists only when the user passes `--export`
and the key, and that export leaves VeilLock's protection. Someone can
still point another camera or a screen recorder at a playing screen.
The call app's recording is not this file.

PulseCheck failure produces veil or noise. It does not send plaintext
and it does not write plaintext. The user controls the lift. iPhone FaceTime cannot select a third-party
camera. Most other phone clients cannot either.
VeilLock does not attach to a Skype, Zoom, Meet, Teams, Discord,
WhatsApp, Signal, OBS, or browser process that is already running.

Keys travel out of band (pre-shared, HMAC-wrapped broadcast key, or
X25519). The encrypted-media label is `veillock-e2e-media-v1`. The
scramble label is different. Lamb Lens order remains Service, then
Clarity, then Peace.

Engulf is not the same on every platform. On Linux, `veillock engulf`
can start an app that opens `/dev/video*` itself inside a `bwrap` device
namespace, or with an `LD_PRELOAD` that redirects those opens. PipeWire
and portal cameras are outside that sandbox and are not engulfed. On
Windows 11 build 22000 or newer, `veilcam-register.exe` calls
`MFCreateVirtualCamera` and registers a user-mode camera. The friendly
name argument is VeilLock. Windows appends ` Windows Virtual Camera`.
That is not a kernel driver. VeilLock does not hook capture APIs. Other
physical cameras remain visible, so an app that saved a device id may
still need one pick. Without the helper, no camera is registered. The
microphone is still CABLE Output if VB-Audio Virtual Cable is installed.
macOS is not engulfed: SIP and the hardened runtime block injection, and
Apple-signed FaceTime cannot be injected into. iOS apps cannot be wrapped.
Chromium pages are engulfed by the extension, which wraps `getUserMedia`
and, when both people have the key, seals each encoded frame with
AES-256-GCM. A relay that forwards those frames unchanged sees ciphertext.
A server that decodes or transcodes does not recover the picture.

`veillock link` is the native end-to-end path. It deflate-encodes the
picture, then seals that bitstream with AES-256-GCM, and sends it on a
TCP channel that is not the call. The call app still sends the veil or
the scramble. Both ends need VeilLock. A wrong key fails closed.
PulseCheck failure sends nothing. Until the user lifts the veil, the
sealed picture is the veil. The scramble stays the obfuscation fallback
for a peer without VeilLock.

## AZ-OS hook

VeilLock's identity is consent-gated camera protection via AZ-OS.

1. The public camera and video feed is a **natural privacy veil** by
   default (live-looking wash and grain; spatial pixels from the real
   frame are not copied).
2. The user may turn obfuscation **off**. That lifts the veil.
3. The user may **accept a call through AZ-OS**. That lifts the veil
   for the accepted session. Ending the call re-veils.
4. PulseCheck failure still refuses plaintext even when the veil is
   lifted.

The hook is a local overlay receipt. Hosted AZ-OS halt is a token, not
killing the caller OS. Hosted `/v1/call-accept` is a consent receipt,
not a placed telephone call.

The Worker homepage shows a suite Live Nodes strip. `/v1/mesh/*` PROXY
to aziel-runtime. Suite mesh default OFF. QNM rollup is
live|locked|isolated counts only. QNS-CD-1.0 (photon QNS1 packet
transfer) is a hub cite / Worker mesh cross-map to qnm-node +
aziel-runtime — not a Softwares-tab product and not a public qnsd
proxy. No Node Gate. No auto-heal. Not an anonymity network.
Anon-broadcast is not a publish path. VeilLock remains consent-gated
camera protection via AZ-OS.

## What this is not

VeilLock is the consent-gated camera path described above. It does not
implement malware, credential theft, or exploits against other systems.
Forks that add capture against unwitting users are outside this spec
and outside the license grant’s intended use as a protective camera
path. The user controls the veil.
