---
name: VeilLock
description: Use when calling VeilLock hosted /v1 or installing the local package. Consent-gated camera protection via AZ-OS. Author Aziel Eliab.
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
- AZ-OS: https://azos-download-tracker.vibelock.workers.dev/v1/status

Ops (do **not** increment downloads or views):

| Method | Path | What |
|--------|------|------|
| GET | `/v1/health` | Liveness. AZ-OS hook present. |
| GET | `/v1/skill` | This markdown. |
| GET/POST | `/v1/apps` | Local-app steps. Does not inject into FaceTime, Zoom, Meet, Teams, or Skype. |
| POST | `/v1/pulse` | PulseCheck. Fail → halt/noise, never plaintext. |
| POST | `/v1/obfuscate-preview` | Natural camera/video veil recipe. |
| POST | `/v1/azos-hook` | Consent-gate status. |
| POST | `/v1/call-accept` | User accepted a call through AZ-OS (receipt). |
| POST | `/v1/consent` | Evaluate veil: default on; lift if user off or call accepted. |

Grok: import OpenAPI as a custom tool. ChatGPT: GPT Actions. Venice: HTTP tools.

## Example

```bash
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health
curl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill
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

Then open http://127.0.0.1:8761 (loopback only).

Counted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.2.0.tar.gz
GitHub: https://github.com/AzielEliab/veillock

Paper: DOI https://doi.org/10.5281/zenodo.21431659 · https://zenodo.org/records/21431659 · Apache-2.0. Forks welcome.
