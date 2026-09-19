# VeilLock

VeilLock keeps your camera veiled until you lift it.

**Author:** Aziel Eliab  
**License:** [Apache-2.0](LICENSE)  
**Version:** 0.2.0

## Start

1. Install.

   ```bash
   python -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. Open the app.

   ```bash
   veillock ui
   ```

3. Open http://127.0.0.1:8761 and press **Start camera veil**.

`veillock doctor` checks this computer. `veillock` with no arguments prints the same next steps. `veillock --help` lists commands.

One-click install (counted tarball, then the same app):

```bash
curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash
```

Same three steps are in [RUN.txt](RUN.txt). Spec: [docs/whitepaper.md](docs/whitepaper.md). Forks are welcome.

## Counted download

The Worker serves the gzip itself (HTTP 200). GitHub releases are a mirror.

- Page: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)
- Tarball: [veillock-0.2.0.tar.gz](https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.2.0.tar.gz)
- Install script: [https://veillock-download-tracker.vibelock.workers.dev/install.sh](https://veillock-download-tracker.vibelock.workers.dev/install.sh)
- OpenAPI: [https://veillock-download-tracker.vibelock.workers.dev/openapi.json](https://veillock-download-tracker.vibelock.workers.dev/openapi.json)
- Skill: [https://veillock-download-tracker.vibelock.workers.dev/v1/skill](https://veillock-download-tracker.vibelock.workers.dev/v1/skill)
- Suite mesh proxy: [https://veillock-download-tracker.vibelock.workers.dev/v1/mesh](https://veillock-download-tracker.vibelock.workers.dev/v1/mesh) — default OFF; QNM live / locked / isolated; QNS-CD-1.0 hub cite (photon QNS1 packet transfer; no public qnsd proxy)
- GitHub: [https://github.com/AzielEliab/veillock](https://github.com/AzielEliab/veillock)
- DOI: [10.5281/zenodo.21431659](https://doi.org/10.5281/zenodo.21431659)
- Zenodo: [https://zenodo.org/records/21431659](https://zenodo.org/records/21431659)

Isolated counter: Worker `veillock-download-tracker`, KV `VEILLOCK_DOWNLOADS`. Counted `/download` increments this counter. `/v1` leaves the counter unchanged.

## AZ-OS hook

VeilLock hooks **AZ-OS** as the consent surface for the camera and video
feed.

- **Default:** natural camera/video veil (live-looking obfuscation).
- **You turn obfuscation off:** the veil lifts.
- **You accept a call through AZ-OS:** the veil lifts for that session.
- **Call ends:** the veil returns unless you left obfuscation off.

You control both paths. Hosted AZ-OS halt is a token. In the local app, under Advanced: **Accept call through AZ-OS**,
**End call**, and **Keep the veil on**. CLI: `veillock azos`,
`veillock tether --azos-accept --actor "your name"`,
`veillock tether --obfuscation-off`.

## Tether

Pipe **your** camera (or screen) through VeilLock into Zoom, FaceTime (Mac),
Skype, Meet, or Teams as a virtual camera named **VeilLock**. The call app
chooses that camera. The public feed is veiled until you lift it.

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

Default public feed: a natural camera/video veil. PulseCheck must PASS
or the feed stays veiled (`HaltedError` / Phoenix).

Lift the veil (your choice):

```bash
veillock tether --obfuscation-off
veillock tether --azos-accept --actor "your name"
```

Counted download: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)



---

## Download

**Counted download page (this project only, ticks automatically):**

# → [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/) ←

The big button on that page is the download. The number next to it is
**veillock only** — its own Worker and KV. Clicking it increments the
counter. Nobody reports anything. Forks that use the same link are
counted too.

Direct tarball (also counted): [veillock-0.2.0.tar.gz](https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.2.0.tar.gz)

- Live count JSON `{project, views, downloads, total}`: [https://veillock-download-tracker.vibelock.workers.dev/count](https://veillock-download-tracker.vibelock.workers.dev/count)
- Stats: [https://veillock-download-tracker.vibelock.workers.dev/stats](https://veillock-download-tracker.vibelock.workers.dev/stats)
- GitHub releases: [https://github.com/AzielEliab/veillock/releases](https://github.com/AzielEliab/veillock/releases)

---

## iPhone & Android

A local-first Flutter client lives in [`mobile/`](mobile/). Open that
folder in Android Studio or Xcode through Flutter (`flutter create .`
first if `android/` / `ios/` still hold the skeleton READMEs). Live
camera preview, Private / Obfuscation / Broadcast. The overlay is a
**visual obfuscation surface**. Desktop remains the AES-256-GCM engine.

Counted desktop download: [https://veillock-download-tracker.vibelock.workers.dev/](https://veillock-download-tracker.vibelock.workers.dev/)

Forks are welcome and always allowed.

---


## Local UI

`veillock ui` prints `Open http://127.0.0.1:8761/` and serves the app on this computer only.

The first screen has one primary button, **Start camera veil**, and a secondary **Check this computer**. Source, seal mode, AZ-OS consent, sample frames, and call-app steps are under **Advanced**. The page follows the system light or dark setting. `Accept: application/json` on `GET /` returns the same JSON as `GET /health`.

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

Modes: `private` (key stays with the operator), `broadcast`
(HMAC-wrapped session key for authorized receivers), `obfuscation`
(attackers see synthetic UI noise; authorized decoders recover the
sealed frames).

Identifying metadata (window ids, application fingerprints, UI
telemetry) is stripped before encrypt.

The engine seals frames the caller already holds. Camera and video
leave as a natural veil unless you lift it.

The design target is &lt;1 ms/frame for small frames (numpy +
cryptography). This README publishes the design target only.

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
python -m pip install veillock-0.2.0.tar.gz
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

veillock                 # welcome and next steps
veillock --help
veillock version
veillock ui            # prints Open http://127.0.0.1:8761/
veillock doctor        # add --json for the same report as JSON
veillock azos --json
veillock azos          # consent-hook status
veillock tether --source camera --mode obfuscation --device 0
veillock tether --obfuscation-off
veillock tether --azos-accept --actor "your name"
veillock apps          # Zoom / Skype / FaceTime / Meet / Teams steps
```

`encrypt` prints `session_key=<hex>` (and `receiver_secret=<hex>` in
broadcast mode if you did not pass one). Private mode keeps the key
out of `cipher.npz`.

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
obfuscation seals the public feed, ciphertext entropy, framebuffer zeroing,
the tether (mocked VideoCapture / pyvirtualcam; no camera), the AZ-OS
hook, and the natural camera veil.

## Layout

```
veillock/           library (engine, crypto, frames, sources, tether, azos, pulse, phoenix, metadata, modes, cli, ui)
tests/              pytest, synthetic RGB
docs/whitepaper.md  July 2026 spec
examples/           encrypt a synthetic stack
workers/download-tracker/   Cloudflare Worker + wrangler.toml
mobile/             Flutter iPhone & Android client
CONTRIBUTING.md     forks are first-class
```

## Use with AI assistants

Works with ChatGPT (GPT Actions / OpenAI), Grok (xAI), Venice, Claude (Anthropic), Cursor (MCP), Glama (MCP), Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants.

Live HTTPS runtime on the download-tracker Worker (download counter stays unchanged):

- OpenAPI 3.1: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
- Health: https://veillock-download-tracker.vibelock.workers.dev/v1/health
- How to wire tools: https://veillock-download-tracker.vibelock.workers.dev/ai
- MCP catalog: https://aziel-runtime.vibelock.workers.dev/mcp. Suite mesh `/v1/mesh/*` PROXY via `AZIEL_RUNTIME` (default OFF; QNM-BUILD-1.0 live|locked|isolated; QNS-CD-1.0 photon QNS1 packet transfer cross-map to [qnm-node](https://github.com/AzielEliab/qnm-node) + [aziel-runtime](https://github.com/AzielEliab/aziel-runtime)). Catalog MCP `mesh_*` + FragGate `slug=mesh`.

POST /v1/pulse {values}, POST /v1/obfuscate-preview {seed,width,height,source}, POST /v1/consent, POST /v1/call-accept, POST /v1/azos-hook. Desktop `tether` stays local. Mac FaceTime can select VeilLock after the local tether is running. Default natural camera/video veil. Lift only if you turn obfuscation off or accept a call through AZ-OS. Pulse fail → halt/noise.

**ChatGPT Actions:** GPT Editor → Actions → Import from URL → `https://veillock-download-tracker.vibelock.workers.dev/openapi.json` (no auth).

**Grok / xAI tools:** add an HTTP/OpenAPI tool pointing at `https://veillock-download-tracker.vibelock.workers.dev/openapi.json`.

**Venice HTTP tools:** add an HTTP tool with method, URL, and JSON body from that spec. Start with GET `https://veillock-download-tracker.vibelock.workers.dev/v1/health`.

**Claude (Anthropic):** import the same OpenAPI URL as a custom tool, or attach the MCP catalog.

**Cursor / Glama (MCP):** `POST https://aziel-runtime.vibelock.workers.dev/mcp`.

**Other OpenAPI / MCP assistants** (Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and others): import `openapi.json` or attach the MCP catalog.

Identity is Aziel Eliab only.

```bash
curl -sS -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/pulse \
  -H 'content-type: application/json' \
  -d '{"values":[0.2,0.3,0.25]}'
```

GET `/download` still serves the gzip tarball and is counted.


## Call wrap

`veillock wrap` is the generic path for any desktop app that can choose
a camera: Skype, Zoom, Google Meet, Teams, Discord, WhatsApp desktop,
Signal desktop, OBS, Mac FaceTime, and browser WebRTC. The app is not
modified. It is pointed at the virtual camera named **VeilLock**.

Two different protections, and they are not the same thing:

| Path | What it is |
|------|------------|
| Live call video | A keyed visual scramble (8×8 block permutation, rotation, and invert) plus a sync strip. An authorized peer running `veillock receive` approximately reverses a capture of the incoming call. **Obfuscation, not AES-256-GCM.** The call provider sees the natural veil, or the scrambled tiles after you lift the veil for a protected call. Lossy codecs (H.264, VP8, VP9, AV1) would destroy raw AES-GCM pixels, so those pixels are not what is sent. Channel swaps are not used; 4:2:0 color subsampling would not bring them back. |
| Live call audio | Comfort noise until you lift the veil. Then the microphone, or a keyed permutation of short PCM blocks if you chose scramble. **Obfuscation, not AES-256-GCM.** Opus and AAC do not carry sample ciphertext. A speech codec that rebuilds phase does not return the waveform, with or without the key. A short block can still contain a speech fragment. PulseCheck failure is noise, never the microphone. |
| `veillock record` / `veillock play` | **AES-256-GCM at rest** for video and audio, video only, or audio only. The key is not in the file. Playback decrypts in memory. Plaintext export is off unless you pass `--export`. A call app or a screen recorder pointed at a playing screen is not this file. |

The veil stays on until you turn obfuscation off or accept a call
through AZ-OS. You control the lift. PulseCheck failure halts to veil
or noise. Plaintext is not sent and is not written.

Keys are exchanged out of band: a 32-byte pre-shared key, the existing
HMAC-wrapped broadcast key (that wrap is AES-GCM of the *key*, not of
the picture), or X25519 then HKDF-SHA256 (`veillock keygen`,
`veillock agree`).

```bash
veillock keygen
veillock wrap --mic --source camera --feed scramble --azos-accept --actor "your name"
veillock receive --in captured.npy --out picture.npy --key <hex>
veillock record --in frames.npy --audio-in mic.npy --out clip.veilrec --key <hex>
veillock play --in clip.veilrec --key <hex>
veillock play --in clip.veilrec --export --out frames.npy --key <hex>
```

`veillock wrap --mic` also feeds a microphone the call app can select.
On Linux, VeilLock creates that source. The name in the picker is
**VeilLock Microphone**. `pactl` loads a null sink and a remap source;
`paplay` writes the public audio; stop unloads both modules. That needs
pipewire-pulse or PulseAudio. It is not a kernel driver.

On macOS, no CoreAudio plugin is shipped. If BlackHole is already
installed, the call app selects **BlackHole 2ch** (not a device named
VeilLock) and sox or ffmpeg feeds it. On Windows, no audio driver is
shipped. If VB-Audio Virtual Cable is already installed, the call app
selects **CABLE Output** and VeilLock writes to **CABLE Input**.

Default public audio is comfort noise. After you lift the veil it is
the real microphone, unless you passed `--audio-feed scramble`. The
real microphone can be sealed into the AES-256-GCM `.veilrec` at the
same time. The call app never receives that file.

Every recording VeilLock writes is encrypted at rest and readable only
through VeilLock. That includes what you send and the decrypted stream
you receive, from the CLI, the loopback UI, `veillock engulf --record`,
and the browser extension. Chunks are sealed and flushed one at a time,
so a crash does not leave a plaintext file. `veillock play` and the UI
player decrypt in memory. `--export` is off unless you ask for it, and
it is labeled as leaving this protection. Someone can still point
another camera or a screen recorder at a playing screen.

Engulf and end-to-end encryption are separate from that picker.

| Platform | App | Engulf | Encryption |
|----------|-----|--------|------------|
| Linux | Native app that opens `/dev/video*` itself | `veillock engulf -- <app>`. `bwrap` hides the other video nodes, or `LD_PRELOAD` redirects `open()` of `/dev/video*`. PipeWire is not engulfed. | The app still gets the veil or the scramble. **Not AES-256-GCM.** |
| Linux | PipeWire, portal, Flatpak, Snap | Not engulfed. | Same obfuscation on the app's stream. |
| Windows 11 | Zoom, Skype, Teams, Discord, and other native apps | `veilcam-register.exe` on build 22000+ calls `MFCreateVirtualCamera`. The friendly name argument is VeilLock; Windows appends ` Windows Virtual Camera`. No kernel driver. VeilLock does not hook. Other cameras remain, so a saved device id may still need one pick. Without the helper, nothing is registered. The microphone is still **CABLE Output** if VB-Audio Virtual Cable is installed. | The app's stream is obfuscation, **not AES-256-GCM.** |
| macOS | FaceTime and other hardened or Apple-signed apps | Not engulfed. SIP and the hardened runtime block injection. Apple-signed FaceTime cannot be injected into. Select the virtual camera. | The app's stream is obfuscation. |
| Chromium | Meet, Teams web, Zoom web, Discord web, any WebRTC page | The extension wraps `getUserMedia`. Default is a generated veil, not the real camera. | **AES-256-GCM** on each encoded frame when both browsers have the extension and the same key. A relay that forwards those frames unchanged sees ciphertext. A server that decodes or transcodes does not recover the picture. |
| iOS | Any app, including iPhone FaceTime | Apps cannot be wrapped. | No VeilLock path on iOS. |
| Two VeilLock users | Beside any native call | `veillock link` is a separate TCP channel. The call app still sends the veil. | **AES-256-GCM** after a deflate encoder, with key rotation. Both ends need VeilLock. A wrong key fails closed. PulseCheck failure sends nothing. |

The keyed scramble is the fallback for a person who does not run VeilLock. That path is obfuscation, not AES-256-GCM. The X25519 label for the encrypted channel is `veillock-e2e-media-v1`. The scramble key is a different label.

`veillock compat` prints the coverage set: about 50 widely used call and video apps, with desktop, browser, and phone variants where those clients differ. It is not a market-share ranking. Profiles are schema 1. A capture hint (V4L2, PipeWire, Media Foundation, DirectShow, AVFoundation, getUserMedia) outranks a process name. An unknown app still gets a safe default report. `veillock join <url>` prints that same report for a Teams, Meet, Zoom, Webex, Slack, or Discord link and does not join the call. A gallery is one outgoing veil or scramble, not an AES mesh. Screen share is outside the camera wrap. A new app is a profile entry (`register_profile`) plus a test, not a new capture fork. The per-app table and the sources are in [docs/app-coverage.md](docs/app-coverage.md). iPhone FaceTime cannot select a third-party camera. Windows 10, DirectShow-only apps, Flatpak, Snap, Firefox, Safari, and macOS SIP stay on the limits written there.

`veillock apps` prints the device-picker steps. iPhone FaceTime cannot
select a third-party camera or microphone. Most phone clients cannot
either. VeilLock does not attach to a call app that is already running. Screen-sharing a
window that already shows unveiled video shows that window.

Lamb Lens order: Service, then Clarity, then Peace. Identity is Aziel
Eliab only. Forks are welcome and always allowed.

The local UI (`veillock ui`) has a Wrap panel: preview the scramble
against a JPEG-like recompression, and seal and play a synthetic
AES-256-GCM recording in memory. The same desk plans a join link and an
engulf. It does not join the call or launch the app. Numbers shown there
are computed for that preview. The layer map is
[docs/layers.md](docs/layers.md). The human UI is aziel-runtime.
`suite/runtime-ui.json` (schema `veillock-runtime-ui-1`) is the contract
that UI can cross-update against. Slug `veillock` stays local-only, with
no public door ops. This package does not append the ACT-RECEIPT-1.0 chain.
Until that UI opens the desk, VeilLock still opens with `veillock ui`.

## License

Apache-2.0. See [LICENSE](LICENSE).

Forks are welcome and always allowed.
