# VeilLock

Live-stream encryption of visual output, UI rendering, and screen-level
data streams **before** they reach any external display.

**Author:** Aziel Eliab
**Date:** July 2026
**License:** [Apache-2.0](LICENSE)

> Render → encrypt → decode locally → display.
> Without the correct runtime key state, the display is undecodable noise.

See the spec: [docs/whitepaper.md](docs/whitepaper.md).
How to contribute: [CONTRIBUTING.md](CONTRIBUTING.md).

**Forks are welcome and always allowed.**

---

## Download

**Counted download page (this project only, ticks automatically):**

# → [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/) ←

The big button on that page is the download. The number next to it is
**veillock only** — its own Worker and KV, not mixed with VibeLock or
anything else. Clicking it increments the counter. Nobody reports
anything. Forks that use the same link are counted too.

Direct tarball (also counted): [veillock-0.1.0.tar.gz](https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.1.0.tar.gz)

- Live count JSON: [https://veillock-download-tracker.vibelock.workers.dev/count](https://veillock-download-tracker.vibelock.workers.dev/count)
- Stats: [https://veillock-download-tracker.vibelock.workers.dev/stats](https://veillock-download-tracker.vibelock.workers.dev/stats)
- GitHub releases: [https://github.com/AzielEliab/veillock/releases](https://github.com/AzielEliab/veillock/releases)

---

## What it does

VeilLock is a three-layer pipeline:

1. **Render capture** — a `FrameSource` yields RGB uint8 numpy frames
   (software stand-in for intercepting frames before GPU display).
2. **Frame encryption engine** — AES-256-GCM per frame, key
   `SHA-256(session_key || frame_index_le64)`, 12-byte nonce derived
   from the frame index. Session key rotates every N frames
   (default 120, range 60–240) with
   `SHA-256(session_key || b"rotate" || epoch_index)`; old keys are
   dropped.
3. **Trusted decode surface** — authorized decrypt immediately before
   display.

Integrity: `PulseCheck.pci()` must return `"PASS"` or generation
**halts** (`HaltedError`). Repeated failures enter **Phoenix Loop**:
the session reboots, keys are reset, and encrypt/decrypt refuse
plaintext until PCI PASSes.

Modes: `private` (key not exported in the package), `broadcast`
(HMAC-wrapped session key for authorized receivers), `obfuscation`
(attackers see synthetic UI noise, not ciphertext snow and not
plaintext).

Identifying metadata (window ids, application fingerprints, UI
telemetry) is stripped before encrypt.

This engine is not a screen scraper and not malware. It seals frames
the caller already holds.

The design target is &lt;1 ms/frame for small frames (numpy +
cryptography). This README does not invent benchmark numbers.

## Install

Python 3.10+. numpy and cryptography.

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

From a release artifact:

```bash
python -m pip install veillock-0.1.0.tar.gz
```

## CLI

```bash
# Encrypt an RGB stack (N,H,W,3) uint8
veillock encrypt --in frames.npy --out cipher.npz --mode private
veillock encrypt --in frames.npy --out cipher.npz --mode broadcast
veillock encrypt --in frames.npy --out cipher.npz --mode obfuscation

# Decrypt (private / obfuscation need the hex session key printed at encrypt)
veillock decrypt --in cipher.npz --out frames.npy --key <hex>
# Broadcast can unwrap with the receiver secret instead
veillock decrypt --in cipher.npz --out frames.npy --receiver-secret <hex>

veillock version
```

`encrypt` prints `session_key=<hex>` (and `receiver_secret=<hex>` in
broadcast mode if you did not pass one). Private mode does **not**
embed the key in `cipher.npz`.

Library entry point:

```python
from veillock.engine import VeilLockSession
import numpy as np

frames = np.zeros((4, 16, 16, 3), dtype=np.uint8)
key = bytes(range(32))
enc = VeilLockSession(session_key=key, rotation_interval=120, mode="private")
stream = enc.encrypt_frames(frames)
dec = VeilLockSession(session_key=key, rotation_interval=120, mode="private")
out = dec.decrypt_frames(stream)
assert np.array_equal(out, frames)
```

## Synthetic example

No hardware required:

```bash
python examples/encrypt_synthetic.py
```

That script builds a 16×16 RGB stack, encrypts it, decrypts it, and
writes artifacts under `examples/_out/`.

## Tests

```bash
pip install -e ".[dev]"
python -m pytest -q
```

Fixtures are synthetic. They cover roundtrip, wrong key, rotation
forward-secrecy, PCI halt, Phoenix Loop, metadata scrubbing,
obfuscation ≠ plaintext, ciphertext entropy, and framebuffer zeroing.

## Layout

```
veillock/           library (engine, crypto, frames, pulse, phoenix, metadata, modes, cli)
tests/              pytest, synthetic RGB
docs/whitepaper.md  July 2026 spec
examples/           encrypt a synthetic stack
workers/download-tracker/   Cloudflare Worker + wrangler.toml
CONTRIBUTING.md     forks are first-class
```

## License

Apache-2.0. See [LICENSE](LICENSE).

Forks are welcome and always allowed.
