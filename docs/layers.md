# Layers

Author: Aziel Eliab.

VeilLock is the local package. The human UI is aziel-runtime (software card slug `veillock`, catalog status local-only, public door ops empty). This page is the tether between the engine, the strategy adapters, and the surfaces that show them.

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
| CLI    | loopback | extension | Worker /v1/wrap | aziel-runtime human UI |
|        | UI :8761 | Chromium  | description only| suite/runtime-ui.json |
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
| `suite/runtime-ui.json` | Versioned contract (`veillock-runtime-ui-1`) for the aziel-runtime human UI: wrap, engulf, join, link, play, record, status. | Boot that UI, add public door ops, or append the ACT-RECEIPT-1.0 chain. |

A gallery (Teams, Meet, Zoom, Webex, Slack huddles, Discord) is one outgoing veil or scramble. Screen share is outside the camera wrap. PulseCheck failure is veil or noise, never plaintext.

The loopback desk does not accept a caller `have_vcam`, capture hint, or sandbox flag. Those would let a page invent a camera. `engulf_plan` drops `argv` and `env`. A video node has to look like `/dev/videoN`. Process names and app tokens are one line, with no shell metacharacters, so a report cannot be forged into a command. The desk reads `FLATPAK_ID`, `SNAP`, and `SNAP_NAME` from this process only.

## What a later host can call

No MCP, node-mesh, forensic, or orchestration engine is in this repository. `orchestration_host.built` is false. A later host inside aziel-runtime can call only:

| Call | Effect |
|------|--------|
| `describe` / `join_plan` | Text or JSON report. Schema `veillock-runtime-ui-1`. `joined_call`, `registered_camera`, `returns_key`, `lifts_veil`, and `writes_recording` stay false. |
| `engulf_plan` | Whether engulf could start. `executed` is false. The body has no `argv` and no environment. Launch remains `veillock engulf`, which plans again before `exec`. |
| `status_report` | The existing AZ-OS consent fields (`veil`, `obfuscate`, `call_accepted`, `actor`, `azos_hook`) plus this contract. It does not lift the veil. |
| `runtime_ui` | `suite/runtime-ui.json`. It does not boot the human UI. |

## Receipts

ACT-RECEIPT-1.0 lives on aziel-runtime and the public chain at `https://www.azielcorpuslibrary.net/receipts`. The four fields are `hash`, `request`, `output`, and `event`. Attempt fields (`request_id`, `attempt_n`, `parent_receipt_id`, `correlation_id`) are filled there and hashed inside `event`. VeilLock does not mint those ids and does not append the chain. `writes_public_chain` is false. An empty public tip is not success.

What this package already returns, and must keep returning, is the consent receipt: `veil`, `obfuscate`, `obfuscation_on`, `call_accepted`, `reason`, `actor`, `call_id`, `azos_hook`. Hosted `POST /v1/call-accept` and the local AZ-OS hook share that shape. A later cross-update may place a VeilLock plan in the ACT `output` field. It must not rename the consent fields.

The QNS pair-custody cite in `workers/download-tracker/src/mesh.js` is a mesh cross-map. It is not this human-UI contract.

It must not shell the `command` string, pass `have_vcam` unless the helper file was actually seen, read recording keys out of a `.veilrec`, or point `/v1/wrap` at the download counter. Consent and PulseCheck stay in the engine. A failed check is veil or noise. AES-256-GCM recordings stay sealed. Wrong keys open nothing.

Lamb Lens order: Service, then Clarity, then Peace. Identity is Aziel Eliab only.
