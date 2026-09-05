# VeilLock download tracker (Cloudflare Worker)

Counts GitHub-release downloads for VeilLock across the canonical
repository, other branches, and forks. Forks are identified by GitHub
`owner/repo`.

**This worker must be deployed** before
`https://veillock-download-tracker.vibelock.workers.dev` resolves.
Until then, send people to
[GitHub Releases](https://github.com/AzielEliab/veillock/releases).

No secrets belong in this directory. The KV namespace id in
`wrangler.toml` is the placeholder `REPLACE_ME` until you create a
namespace.

## Bindings

| Binding     | Type | Purpose |
|-------------|------|---------|
| `DOWNLOADS` | KV   | Counters keyed `project|owner|repo|branch|fork` |

## Deploy

```bash
cd workers/download-tracker

# 1. Log in once (opens a browser; token stays in wrangler, not in git)
npx wrangler login

# 2. Create the KV namespace. Paste the id into wrangler.toml
#    replacing REPLACE_ME. Binding name MUST stay DOWNLOADS.
npx wrangler kv namespace create DOWNLOADS

# 3. Deploy
npx wrangler deploy
```

The `workers.dev` subdomain wrangler prints
(`veillock-download-tracker.<account>.workers.dev`) is enough until
custom DNS is ready. This tree documents the intended public URL
`https://veillock-download-tracker.vibelock.workers.dev`.

## Routes

| Method | Path | Behavior |
|--------|------|----------|
| GET | `/` | Product UI: consent desk, PulseCheck, veil compose, call-app steps, counted download |
| GET | `/download?repo=&tag=&asset=` | Increment KV, 302 to the GitHub asset (default: releases page) |
| GET | `/stats` | JSON totals plus per-repo and per-branch breakdown |
| POST | `/event` | A fork reports a download |

Query params on `/download`: `owner`, `repo` (`AzielEliab/veillock` is
accepted), `branch`, `fork` (`1` or `owner/repo`), `tag`, `asset`.

Default redirect with no asset:

```
https://github.com/AzielEliab/veillock/releases
```

Tracked asset URL (after deploy):

```
https://veillock-download-tracker.vibelock.workers.dev/download?repo=AzielEliab/veillock&tag=latest&asset=veillock-0.2.0.tar.gz
```

A fork reports its own download:

```bash
curl -X POST https://veillock-download-tracker.vibelock.workers.dev/event \
  -H "content-type: application/json" \
  -d '{
    "owner": "YourFork",
    "repo": "veillock",
    "branch": "main",
    "fork": "1",
    "asset": "veillock-0.2.0.tar.gz"
  }'
```

`fork=1` or `fork=YourFork/veillock`. If `owner/repo` is not
`AzielEliab/veillock`, the worker records `fork=1` automatically.

## Stats

`GET /stats` returns `total`, `by_repo`, `by_branch`, `by_fork`, and a
`breakdown` array so forks can read aggregates.

## CORS

All responses include `Access-Control-Allow-Origin: *`.

The homepage is the live VeilLock desk: consent (veil on / lifted), PulseCheck,
veil compose, and honest call-app steps. Counted `/download` and one-click
install stay on the same page. Title is `VeilLock — Aziel Eliab`. `/v1` does
not increment downloads.

## Use with Grok, ChatGPT, Venice

This Worker also hosts the product runtime API (CORS `*`). `/v1` routes do **not** increment `DOWNLOADS`.

| Method | Path | Notes |
|--------|------|-------|
| GET | `/v1/health` | Liveness. AZ-OS hook present. |
| GET | `/openapi.json` | OpenAPI 3.1 |
| GET | `/ai` | ChatGPT Actions, Grok/xAI tools, Venice HTTP tools; MCP catalog |
| GET/POST | `/v1/apps` | Local-app steps. Does not inject into FaceTime / Zoom / Meet / Teams / Skype |
| GET | `/cite.json` | How to cite. Aziel Eliab only. Existing Zenodo DOI only. |
| POST | `/v1/consent` | Veil decision (default on; user off or AZ-OS accept lifts) |
| POST | `/v1/call-accept` | User-accepted call receipt |
| POST | `/v1/azos-hook` | Consent-gate status |
| POST | `/v1/obfuscate-preview` | Natural camera/video veil recipe |

See the product README section **Use with Grok, ChatGPT, Venice**.
OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json
