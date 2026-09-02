---
name: VeilLock
description: Use when calling VeilLock hosted /v1 or installing the local package. Author Aziel Eliab.
---

# VeilLock

Live-stream encryption of visual output before it reaches any external display. Not FaceTime/Zoom intercept. Not call intercept. Author: Aziel Eliab.

**THIS IS:** live-stream encryption of visual output, UI rendering, and screen-level data streams before they reach any external display.

**THIS IS NOT:** FaceTime/Zoom intercept, call intercept, a VPN, or a claim that network packets are captured.

Author: **Aziel Eliab**. Forks are welcome and always allowed. Apache-2.0.

Always send `User-Agent: Mozilla/5.0`. Cloudflare Workers may 403 an empty agent.

## Call these URLs

- Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json
- MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`
- Live skill (this markdown): `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`

Ops (do **not** increment downloads or views):

| Method | Path | What |
|--------|------|------|
| GET | `/v1/health` | Liveness. Does not increment downloads. |
| GET | `/v1/skill` | This markdown. Does not increment downloads. |
| POST | `/v1/pulse` | Runtime key-state pulse. Not call intercept. |
| POST | `/v1/obfuscate-preview` | Preview obfuscation. Not FaceTime/Zoom intercept. |

Grok: import OpenAPI as a custom tool. ChatGPT: GPT Actions. Venice: HTTP tools.

## Example

```bash
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill
curl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/pulse \
  -H 'content-type: application/json' \
  -d '{}'
```

## Local (after one-click install)

```bash
curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash
veillock ui
```

Then open http://127.0.0.1:8761 (loopback only).

DOI: https://doi.org/10.5281/zenodo.21431659  
Record: https://zenodo.org/records/21431659  

Counted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.1.0.tar.gz
GitHub: https://github.com/AzielEliab/veillock
