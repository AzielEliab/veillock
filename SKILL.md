---
name: VeilLock
description: Use when calling VeilLock hosted /v1 or installing the local package. Dual surface: Worker /v1 + catalog MCP. This Worker /v1/mesh/* PROXY to aziel-runtime via AZIEL_RUNTIME. Suite mesh default OFF. QNM-BUILD-1.0 live|locked|isolated. QNS-CD-1.0 hub cite / Worker mesh cross-map (photon QNS1 packet transfer; qnm-node qnsd + aziel-runtime). Not a Softwares-tab product. No public qnsd proxy. No Node Gate. No auto-heal. Not anonymity. Consent-gated camera protection via AZ-OS. Author Aziel Eliab.
---

# VeilLock

Consent-gated camera protection via AZ-OS. Author: **Aziel Eliab**.

**THIS IS:** a privacy veil on the user's own camera and video. The feed is naturally obfuscated unless (a) the user turns obfuscation off, or (b) the user accepts a call through AZ-OS.

**THIS IS NOT:** a VPN, Tor, anonymous relay, or a claim of untraceable origin. Hosted `/v1` does not increment downloads or views. Hosted AZ-OS halt is a token, not killing the caller OS.

Always send `User-Agent: Mozilla/5.0`. Cloudflare Workers may 403 an empty agent.

## Call these URLs

- Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json
- MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`
- Live skill (this markdown): `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`
- Suite mesh: `GET https://veillock-download-tracker.vibelock.workers.dev/v1/mesh` (PROXY; default OFF; QNS-CD-1.0 cite)
- AZ-OS: https://azos-download-tracker.vibelock.workers.dev/v1/status

Ops (do **not** increment downloads or views):

| Method | Path | What |
|--------|------|------|
| GET | `/v1/health` | Liveness. AZ-OS hook present. |
| GET | `/v1/skill` | This markdown. |
| GET | `/v1/mesh` | PROXY suite mesh status. Default OFF. QNM live|locked|isolated. QNS-CD-1.0 cross-map (photon QNS1). Never enables. No public qnsd proxy. |
| GET | `/v1/mesh/nodes` | PROXY Live Nodes roster (5-minute presence). Payload includes QNS-CD-1.0 cite. |
| POST | `/v1/mesh/{enable,disable,join,heartbeat,leave,broadcast}` | PROXY. Bearer required to enable. No auto-heal. Anon-broadcast is not a publish path. |
| GET/POST | `/v1/apps` | Local-app steps. Does not inject into FaceTime, Zoom, Meet, Teams, or Skype. |
| POST | `/v1/pulse` | PulseCheck. Fail → halt/noise, never plaintext. |
| POST | `/v1/obfuscate-preview` | Natural camera/video veil recipe. |
| POST | `/v1/azos-hook` | Consent-gate status. |
| POST | `/v1/call-accept` | User accepted a call through AZ-OS (receipt). |
| POST | `/v1/consent` | Evaluate veil: default on; lift if user off or call accepted. |

Works with ChatGPT (GPT Actions / OpenAI), Grok (xAI), Venice, Claude (Anthropic), Cursor (MCP), Glama (MCP), Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants. ChatGPT: GPT Actions (import OpenAPI). Grok / xAI: import OpenAPI as a custom tool. Venice: HTTP tools from the spec. Claude: OpenAPI tool or MCP. Cursor / Glama: MCP catalog. Other OpenAPI/MCP assistants: same Worker OpenAPI or MCP URL.

Identity is Aziel Eliab only.

## Example

```bash
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/mesh
curl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/consent \
  -H 'content-type: application/json' \
  -d '{"obfuscation_on":true,"call_accepted":false}'
curl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/call-accept \
  -H 'content-type: application/json' \
  -d '{"actor":"user"}'
curl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/apps \
  -H 'content-type: application/json' \
  -d '{"app":"facetime"}'
```

## Local (after one-click install)

```bash
curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash
veillock ui
veillock doctor
veillock azos
```

Then open http://127.0.0.1:8761 (loopback only). Worker homepage Live Nodes strip polls `GET /v1/mesh` (default OFF; QNS-CD-1.0 cite; no public qnsd proxy).

Counted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.2.0.tar.gz
GitHub: https://github.com/AzielEliab/veillock

Paper: DOI https://doi.org/10.5281/zenodo.21431659 · https://zenodo.org/records/21431659 · Apache-2.0. Forks welcome.

## Call wrap (local package)

`veillock wrap` feeds any desktop app that can choose a camera named VeilLock. `veillock receive` unveils a capture for a peer who has the out-of-band key. `veillock record` / `veillock play` are the local file. Hosted `GET /v1/wrap` describes this contract. It does not scramble pixels and it does not increment downloads.

| Path | What it actually is |
|------|---------------------|
| Live call video | Keyed 8×8 scramble (permutation, rotation, invert). Obfuscation. **Not AES-256-GCM.** The provider sees the veil or the tiles. A peer with the key gets an approximation after the call codec, not bit-exact plaintext. Channel swaps are not used; 4:2:0 would not bring them back. |
| Live call audio | Comfort-noise veil until the user lifts it, then the microphone, or a keyed PCM block permutation if scramble was chosen. **Not AES-256-GCM.** Opus and AAC do not carry sample ciphertext. A phase-rebuilding speech codec does not return the waveform. Short blocks can still contain speech fragments. |
| Virtual microphone | Linux: VeilLock creates **VeilLock Microphone** with pactl (not a kernel driver). macOS: no CoreAudio plugin; the app selects **BlackHole 2ch** only if BlackHole is installed. Windows: no driver; the app selects **CABLE Output** only if VB-Audio Virtual Cable is installed, and VeilLock writes to CABLE Input. |
| `veillock record` / `play` | **AES-256-GCM** per frame and per audio chunk, key rotation, PulseCheck. The call app's cloud recording is not this file. |
| Keys | Out of band: 32-byte pre-shared key, HMAC-wrapped broadcast key (the wrap is AES-GCM of the key, not of the pixels), or X25519 then HKDF-SHA256. |

PulseCheck failure halts to veil or noise. Plaintext is not sent. The veil stays on until the user lifts it.

iPhone FaceTime cannot select a third-party camera or microphone. Most mobile clients (Zoom, Meet, Teams, WhatsApp, Signal) cannot either. VeilLock does not inject into the call app.

Lamb Lens order: Service, then Clarity, then Peace. Identity is Aziel Eliab only. Forks are welcome and always allowed.

Works with ChatGPT (GPT Actions / OpenAI), Grok (xAI), Venice, Claude (Anthropic), Cursor (MCP), Glama (MCP), Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants.
