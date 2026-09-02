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


## One-click install

```bash
curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash
```

The script curls the **counted** tarball from this project's Worker
(`/download`, User-Agent `Mozilla/5.0`), extracts, makes a venv, and
`pip install -e .`. Then run `veillock ui`.

Or tap **Download** / **One-click install** on the Worker homepage
(a 6th-grader can tap it):
https://veillock-download-tracker.vibelock.workers.dev/

## Counted download (Cloudflare Worker)

**This is the counted download.** GitHub releases exist as a mirror.
The Worker serves the gzip itself (HTTP 200, no 302 to GitHub).

# → [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/) ←

Direct tarball (also counted):
[veillock-0.1.0.tar.gz](https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.1.0.tar.gz)

- Live count JSON: [https://veillock-download-tracker.vibelock.workers.dev/stats](https://veillock-download-tracker.vibelock.workers.dev/stats)
- OpenAPI: [https://veillock-download-tracker.vibelock.workers.dev/openapi.json](https://veillock-download-tracker.vibelock.workers.dev/openapi.json)
- Skill: [https://veillock-download-tracker.vibelock.workers.dev/v1/skill](https://veillock-download-tracker.vibelock.workers.dev/v1/skill)
- One-click install: [https://veillock-download-tracker.vibelock.workers.dev/install.sh](https://veillock-download-tracker.vibelock.workers.dev/install.sh)
- GitHub: [https://github.com/AzielEliab/veillock](https://github.com/AzielEliab/veillock)

- DOI: [10.5281/zenodo.21431659](https://doi.org/10.5281/zenodo.21431659)
- Zenodo: [https://zenodo.org/records/21431659](https://zenodo.org/records/21431659)

Isolated counter: Worker `veillock-download-tracker`, KV `VEILLOCK_DOWNLOADS`. Not mixed with any other product. `/v1` does not increment downloads.


## Quick start

```bash
pip install -e ".[dev]"
veillock version
veillock ui
```

Open http://127.0.0.1:8761 (loopback only). No CDN, no telemetry.

Counted download: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)

## Tether

Pipe **your** camera (or screen) through VeilLock into Zoom, FaceTime (Mac),
Skype, Meet, or Teams as a virtual camera named **VeilLock**. The call app
chooses that camera. VeilLock does not MITM the call.

```bash
pip install -e ".[tether]"
veillock tether --source camera --mode obfuscation --device 0
```

Then pick **VeilLock** as the camera:

- **Zoom (desktop):** Settings → Video → Camera → VeilLock
- **Skype (desktop):** Settings → Audio & Video → Camera → VeilLock
- **FaceTime (Mac):** Video menu → VeilLock. Desktop FaceTime can select a
  third-party virtual camera. **iPhone FaceTime cannot** select a third-party
  virtual camera (Apple).
- **Google Meet / Teams (desktop):** camera dropdown or Settings → Devices →
  Camera → VeilLock
- **Android / iOS:** most mobile clients cannot select a third-party virtual
  camera. Use the desktop app.

`veillock apps` prints the same steps. Linux needs v4l2loopback labeled
`VeilLock` (see that command). Default size is 640×480 @ 15 fps.

Default `--mode obfuscation`: people on the call see synthetic UI noise, not
your plaintext camera. Private mode sends black/decoy unless you pass
`--trusted` (trusted local decode — still your choice). PulseCheck must PASS
or the feed becomes obfuscation noise (`HaltedError` / Phoenix) — never
plaintext.

**Safety:** YOUR camera/screen only. Not a call interceptor, not malware, not
a screen scraper of other apps' private buffers. Do not MITM Zoom/FaceTime.
The call app **chooses** the virtual camera named VeilLock.

Counted download: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)



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

## iPhone & Android

A local-first Flutter client lives in [`mobile/`](mobile/). Open that
folder in Android Studio or Xcode through Flutter (`flutter create .`
first if `android/` / `ios/` still hold the skeleton READMEs). Live
camera preview, Private / Obfuscation / Broadcast. The overlay is a
**visual obfuscation surface**, not AES-GCM — desktop remains the
AES-256-GCM engine.

Counted desktop download: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)

Forks are welcome and always allowed.

---


## Local UI

`veillock ui` serves a loopback dashboard at http://127.0.0.1:8761

Binds to `127.0.0.1` only. Self-contained HTML (no CDN). Synthetic frames are sealed in-process; the session key is shown once. The **Tether** panel starts/stops the virtual camera and copies app instructions.

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

Python 3.10+. numpy and cryptography (core). Optional extra:
`pip install -e ".[tether]"` (opencv-python-headless + pyvirtualcam).

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
veillock ui            # localhost UI on 127.0.0.1:8761 (Tether panel)
veillock tether --source camera --mode obfuscation --device 0
veillock apps          # Zoom / Skype / FaceTime / Meet / Teams steps
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
obfuscation ≠ plaintext, ciphertext entropy, framebuffer zeroing,
and the tether (mocked VideoCapture / pyvirtualcam; no camera).

## Layout

```
veillock/           library (engine, crypto, frames, sources, tether, pulse, phoenix, metadata, modes, cli, ui)
tests/              pytest, synthetic RGB
docs/whitepaper.md  July 2026 spec
examples/           encrypt a synthetic stack
workers/download-tracker/   Cloudflare Worker + wrangler.toml
mobile/             Flutter iPhone & Android client
CONTRIBUTING.md     forks are first-class
```

## Use with Grok, ChatGPT, Venice

Live HTTPS runtime on the download-tracker Worker (does **not** increment the download counter):

- OpenAPI 3.1: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
- Health: https://veillock-download-tracker.vibelock.workers.dev/v1/health
- How to wire tools: https://veillock-download-tracker.vibelock.workers.dev/ai
- MCP catalog: https://aziel-runtime.vibelock.workers.dev/mcp

POST /v1/pulse {values} and POST /v1/obfuscate-preview {seed,width,height} (noise recipe, not a virtual camera). Desktop `tether` stays local. iOS FaceTime cannot pick a third-party cam. Default obfuscation, not plaintext. Pulse fail → halt/noise, never a plaintext claim.

**ChatGPT Actions:** GPT Editor → Actions → Import from URL → `https://veillock-download-tracker.vibelock.workers.dev/openapi.json` (no auth).

**Grok / xAI tools:** add an HTTP/OpenAPI tool pointing at `https://veillock-download-tracker.vibelock.workers.dev/openapi.json`.

**Venice HTTP tools:** add an HTTP tool with method, URL, and JSON body from that spec. Start with GET `https://veillock-download-tracker.vibelock.workers.dev/v1/health`.

```bash
curl -sS -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/pulse \
  -H 'content-type: application/json' \
  -d '{"values":[0.2,0.3,0.25]}'
```

GET `/download` still serves the gzip tarball and is counted.


## Cite this

Aziel Eliab. VeilLock. https://github.com/AzielEliab/veillock. https://veillock-download-tracker.vibelock.workers.dev. https://doi.org/10.5281/zenodo.21431659.

- Catalog: https://aziel-runtime.vibelock.workers.dev/
- Worker homepage: https://veillock-download-tracker.vibelock.workers.dev/
- Counted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download
- GitHub: https://github.com/AzielEliab/veillock
- Citation JSON: https://veillock-download-tracker.vibelock.workers.dev/cite.json
- DOI: https://doi.org/10.5281/zenodo.21431659

## License

Apache-2.0. See [LICENSE](LICENSE).

Forks are welcome and always allowed.
