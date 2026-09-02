---
name: VeilLock
description: Use when calling VeilLock hosted /v1 or installing the local package. Author Aziel Eliab.
---

# VeilLock

Encrypt visual output before it reaches any external observer. Author: **Aziel Eliab**.

**THIS IS:** a live-stream encryption protocol for visual output.

**THIS IS NOT:** a VPN, Tor, anonymous relay, or a claim of untraceable origin. Hosted `/v1` does not increment downloads or views.

Always send `User-Agent: Mozilla/5.0`. Cloudflare Workers may 403 an empty agent.

## Call these URLs

- Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json
- MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`
- Live skill (this markdown): `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`

Ops (do **not** increment downloads or views):

- `GET /v1/health` — liveness
- `GET /v1/skill` — this file
- Product POSTs listed in OpenAPI

Grok: import OpenAPI as a custom tool. ChatGPT: GPT Actions. Venice: HTTP tools.

## Example

```bash
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill
```

## Local (after one-click install)

```bash
curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash
veillock ui
veillock doctor
```

Then open http://127.0.0.1:8761 (loopback only).

Counted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.1.0.tar.gz
GitHub: https://github.com/AzielEliab/veillock

Paper: DOI https://doi.org/10.5281/zenodo.21431659 · https://zenodo.org/records/21431659 · Apache-2.0. Forks welcome.
