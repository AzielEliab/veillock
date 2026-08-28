# VeilLock

**A live-stream encryption protocol for visual output**

**Author:** Aziel Eliab
**Date:** July 2026
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
package. It is an encryption engine. It is not a screen scraper, not
malware, and not an exploit toolkit.

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
| CLI | `veillock encrypt` / `decrypt` / `version` |

Tests use synthetic 16×16 and 64×64 RGB frames. No hardware is required.

---

## What this is not

VeilLock is the encryption engine described above. It does not implement
malware, screen scrapers, credential theft, or exploits against other
systems. Forks that add capture against unwitting users are outside this
spec and outside the license grant’s intended use as a protective
display path.
