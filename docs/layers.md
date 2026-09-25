# Layers

Author: Aziel Eliab.

VeilLock is one Softwares package. AZInterface is another. This page is the tether between the engine, the strategy adapters, and the surfaces that show them.

```
Engine
  consent veil, PulseCheck, scramble, AES-256-GCM recordings, e2e frames
        |
Strategy / adapters
  coverage.detect (schema 1) · engulf.plan_engulf · mic · wincam · e2e
        |
surfaces.py          one plan object; does not launch or register
        |
+--------+----------+-----------+----------------+------------------+
| CLI    | loopback | extension | Worker /v1/wrap | AZInterface tile |
|        | UI :8761 | Chromium  | description only| suite/*.json     |
+--------+----------+-----------+----------------+------------------+
```

## What each surface is allowed to do

| Surface | Calls | Does not |
|---------|--------|----------|
| `veillock wrap` / UI preview | Engine scramble. UI record demo seals and plays AES-256-GCM in memory. | Treat the call picture as AES. |
| `veillock engulf` | `plan_engulf`, then launch only from the CLI when the plan says it can. | Launch from the loopback desk. The desk shows the plan. |
| `veillock join` / UI “Plan this link” | `surfaces.join_plan` → `detect`. | Join the meeting or register a camera. |
| `veillock link` / UI “Seal an encoded frame” | E2E AES-256-GCM on the VeilLock channel. | Claim the call app’s gallery is an AES mesh. |
| `veillock play` / `record` | AES-256-GCM at rest. UI play is the in-memory demo. | Write a plaintext file unless `--export`. |
| Extension | `getUserMedia` veil, encoded-frame AES when both Chromium peers share the key. | Run inside Firefox, Safari, or a desktop Electron process. |
| `GET /v1/wrap` | Describe the contract. | Scramble pixels, join a call, register a camera, or increment downloads. |
| `suite/azinterface-tile.json` | Tell AZInterface how to launch `veillock ui`. | Merge VeilLock into AZInterface. That desk lives in [AzielEliab/azinterface](https://github.com/AzielEliab/azinterface). This repository does not boot it. |

A gallery (Teams, Meet, Zoom, Webex, Slack huddles, Discord) is one outgoing veil or scramble. Screen share is outside the camera wrap. PulseCheck failure is veil or noise, never plaintext.

Lamb Lens order: Service, then Clarity, then Peace. Identity is Aziel Eliab only.
