/**
 * VeilLock hosted runtime (Cloudflare Worker).
 * Consent-gated camera protection via AZ-OS.
 * Natural camera/video veil unless the user turns it off or accepts a call.
 * Desktop tether stays local. iOS FaceTime cannot pick a third-party cam.
 * /v1/mesh/* PROXY to aziel-runtime via AZIEL_RUNTIME (handled in index.js before this catch-all).
 */
import { meshOpenApiPaths, meshPointer } from "./mesh.js";
function runtimeCors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, HEAD, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type, Accept, Authorization, X-Aziel-Runtime-Token, User-Agent",
  };
}

function runtimeJson(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: { "Content-Type": "application/json; charset=utf-8", ...runtimeCors() },
  });
}

async function sha256Hex(bytes) {
  const data = bytes instanceof Uint8Array ? bytes : new TextEncoder().encode(String(bytes));
  const dig = await crypto.subtle.digest("SHA-256", data);
  const arr = new Uint8Array(dig);
  let out = "";
  for (let i = 0; i < arr.length; i++) out += arr[i].toString(16).padStart(2, "0");
  return out;
}

async function readJsonBody(request) {
  const ct = (request.headers.get("content-type") || "").toLowerCase();
  if (request.method === "GET" || request.method === "HEAD") return {};
  const text = await request.text();
  if (!text || !text.trim()) return {};
  try {
    return JSON.parse(text);
  } catch {
    const err = new Error("JSON body required");
    err.status = 400;
    throw err;
  }
}

function utcNow() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

const AI_CLIENTS = [
  "ChatGPT (GPT Actions / OpenAI)",
  "Grok (xAI)",
  "Venice",
  "Claude (Anthropic)",
  "Cursor (MCP)",
  "Glama (MCP)",
  "Perplexity",
  "Microsoft Copilot / Bing",
  "Google Gemini / Vertex",
  "Mistral",
  "Meta AI",
  "Apple Intelligence surfaces",
  "Amazon Q tooling",
  "DuckAssist",
  "You.com",
  "Cohere",
  "other MCP/OpenAPI-capable assistants",
];

function aiHowTo(base) {
  const openapi = base + "/openapi.json";
  const health = base + "/v1/health";
  const mcp = "https://aziel-runtime.vibelock.workers.dev/mcp";
  return {
    clients: AI_CLIENTS,
    chatgpt_actions: [
      "Open GPT Editor → Actions → Import from URL",
      "Paste " + openapi,
      "Authentication: None",
      "Allow GET /v1/health and the listed POST /v1 routes",
      "Test GET /v1/health, then a sample POST from the spec",
    ],
    grok_xai_tools: [
      "Add an HTTP / OpenAPI tool pointing at " + openapi,
      "Or register GET /v1/health, GET /openapi.json, and the product POSTs",
      "No API key. CORS is *",
    ],
    venice_http_tools: [
      "Add an HTTP tool with method, URL, and JSON body from " + openapi,
      "Start with GET " + health,
      "Then call the product POST listed in the spec",
    ],
    claude_anthropic: [
      "Import " + openapi + " as a custom OpenAPI tool",
      "Or attach the MCP catalog at " + mcp,
    ],
    cursor_mcp: [
      "Add an MCP server pointing at POST " + mcp,
    ],
    glama_mcp: [
      "Register the MCP catalog at " + mcp,
    ],
    openapi_or_mcp: [
      "Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants: import " + openapi + " or attach " + mcp,
    ],
    mcp_catalog: mcp,
    identity: "Aziel Eliab only",
    notes: [
      "GET /download still serves the gzip tarball and increments the counter.",
      "/v1, /openapi.json, and /ai do not increment DOWNLOADS.",
    ],
  };
}

const PRODUCT = "veillock";
const SKILL_MARKDOWN = "---\nname: VeilLock\ndescription: Use when calling VeilLock hosted /v1 or installing the local package. Dual surface: Worker /v1 + catalog MCP. This Worker /v1/mesh/* PROXY to aziel-runtime via AZIEL_RUNTIME. Suite mesh default OFF. QNM-BUILD-1.0 live|locked|isolated. QNS-CD-1.0 hub cite / Worker mesh cross-map (photon QNS1 packet transfer; qnm-node qnsd + aziel-runtime). Not a Softwares-tab product. No public qnsd proxy. No Node Gate. No auto-heal. Not anonymity. Consent-gated camera protection via AZ-OS. Author Aziel Eliab.\n---\n\n# VeilLock\n\nConsent-gated camera protection via AZ-OS. Author: **Aziel Eliab**.\n\n**THIS IS:** a privacy veil on the user's own camera and video. The feed is naturally obfuscated unless (a) the user turns obfuscation off, or (b) the user accepts a call through AZ-OS.\n\n**THIS IS NOT:** a VPN, Tor, anonymous relay, or a claim of untraceable origin. Hosted `/v1` does not increment downloads or views. Hosted AZ-OS halt is a token, not killing the caller OS.\n\nAlways send `User-Agent: Mozilla/5.0`. Cloudflare Workers may 403 an empty agent.\n\n## Call these URLs\n\n- Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json\n- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json\n- MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`\n- Live skill (this markdown): `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`\n- Suite mesh: `GET https://veillock-download-tracker.vibelock.workers.dev/v1/mesh` (PROXY; default OFF; QNS-CD-1.0 cite)\n- AZ-OS: https://azos-download-tracker.vibelock.workers.dev/v1/status\n\nOps (do **not** increment downloads or views):\n\n| Method | Path | What |\n|--------|------|------|\n| GET | `/v1/health` | Liveness. AZ-OS hook present. |\n| GET | `/v1/skill` | This markdown. |\n| GET | `/v1/mesh` | PROXY suite mesh status. Default OFF. QNM live|locked|isolated. QNS-CD-1.0 cross-map (photon QNS1). Never enables. No public qnsd proxy. |\n| GET | `/v1/mesh/nodes` | PROXY Live Nodes roster (5-minute presence). Payload includes QNS-CD-1.0 cite. |\n| POST | `/v1/mesh/{enable,disable,join,heartbeat,leave,broadcast}` | PROXY. Bearer required to enable. No auto-heal. Anon-broadcast is not a publish path. |\n| GET/POST | `/v1/apps` | Local-app steps. Does not inject into FaceTime, Zoom, Meet, Teams, or Skype. |\n| POST | `/v1/pulse` | PulseCheck. Fail \u2192 halt/noise, never plaintext. |\n| POST | `/v1/obfuscate-preview` | Natural camera/video veil recipe. |\n| POST | `/v1/azos-hook` | Consent-gate status. |\n| POST | `/v1/call-accept` | User accepted a call through AZ-OS (receipt). |\n| POST | `/v1/consent` | Evaluate veil: default on; lift if user off or call accepted. |\n\nWorks with ChatGPT (GPT Actions / OpenAI), Grok (xAI), Venice, Claude (Anthropic), Cursor (MCP), Glama (MCP), Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants. ChatGPT: GPT Actions (import OpenAPI). Grok / xAI: import OpenAPI as a custom tool. Venice: HTTP tools from the spec. Claude: OpenAPI tool or MCP. Cursor / Glama: MCP catalog. Other OpenAPI/MCP assistants: same Worker OpenAPI or MCP URL. Catalog MCP `mesh_*` + FragGate `slug=mesh`. Suite mesh default OFF. QNM-BUILD-1.0 live|locked|isolated. QNS-CD-1.0 hub cite (photon QNS1). Not a Softwares-tab product. No public qnsd proxy. No Node Gate. No auto-heal. Not anonymity.\n\nIdentity is Aziel Eliab only.\n\n## Example\n\n```bash\ncurl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health\ncurl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill\ncurl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/mesh\ncurl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/consent \\\n  -H 'content-type: application/json' \\\n  -d '{\"obfuscation_on\":true,\"call_accepted\":false}'\ncurl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/call-accept \\\n  -H 'content-type: application/json' \\\n  -d '{\"actor\":\"user\"}'\n```\n\n## Local (after one-click install)\n\n```bash\ncurl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash\nveillock ui\nveillock doctor\nveillock azos\n```\n\nThen open http://127.0.0.1:8761 (loopback only). Worker homepage Live Nodes strip polls `GET /v1/mesh` (default OFF; QNS-CD-1.0 cite; no public qnsd proxy).\n\nCounted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.2.0.tar.gz\nGitHub: https://github.com/AzielEliab/veillock\n\nPaper: DOI https://doi.org/10.5281/zenodo.21431659 \u00b7 https://zenodo.org/records/21431659 \u00b7 Apache-2.0. Forks welcome.\n";

const VERSION = "0.2.0";
const BASE = "https://veillock-download-tracker.vibelock.workers.dev";
const MOTTO = "Consent-gated camera protection via AZ-OS.";
const IDENTITY = "consent-gated camera protection via AZ-OS";
const IOS_FACETIME = "iOS FaceTime cannot pick a third-party camera.";
const TETHER_NOTE = "Desktop tether stays local. Hosted /v1 is a consent receipt, not a virtual camera.";
const AZOS_HOST = "https://azos-download-tracker.vibelock.workers.dev";
const NO_INJECT = "VeilLock does not attach to a running FaceTime, Zoom, Meet, Teams, or Skype process. This worker does not register a camera. macOS and iOS are not engulfed. A local Windows 11 helper can register a user-mode camera; this worker does not.";
const LIMITATION =
  "THIS IS: a privacy veil on the user's own camera and video, plus local-app steps. THIS IS NOT: a VPN, Tor, anonymous relay, or an attach to a running FaceTime/Zoom/Meet/Teams/Skype process. YOUR camera/screen only.";
const DOI = "10.5281/zenodo.21431659";
const DOI_URL = "https://doi.org/10.5281/zenodo.21431659";
const ZENODO = "https://zenodo.org/records/21431659";
const GITHUB = "https://github.com/AzielEliab/veillock";

const APP_GUIDES = {
  zoom: [
    "Use YOUR camera/screen on this device only.",
    "VeilLock does not attach to a running Zoom process.",
    "Apply the local veil (virtual camera / screen overlay) from the local package if you want obfuscation.",
    "In Zoom desktop: Settings → Video → Camera → VeilLock.",
    "Hosted / in-process ops return a consent receipt and recipe, not pixels.",
  ],
  meet: [
    "Use YOUR camera/screen on this device only.",
    "VeilLock does not attach to a running Google Meet process. The Chromium extension wraps getUserMedia instead.",
    "Apply the local veil from the local package.",
    "In Meet (desktop browser): More → Settings → Video → Camera → VeilLock.",
  ],
  teams: [
    "Use YOUR camera/screen on this device only.",
    "VeilLock does not attach to a running Microsoft Teams process.",
    "Apply the local veil from the local package.",
    "In Teams desktop: Settings → Devices → Camera → VeilLock.",
  ],
  facetime: [
    "iOS FaceTime cannot pick a third-party camera.",
    "VeilLock does not inject into FaceTime. Apple-signed FaceTime cannot be injected into.",
    "Use YOUR device camera/screen only.",
    "Mac FaceTime can choose Video → VeilLock after the local tether is running.",
  ],
  skype: [
    "Use YOUR camera/screen on this device only.",
    "VeilLock does not attach to a running Skype process.",
    "Apply the local veil from the local package.",
    "In Skype desktop: Settings → Audio & Video → Camera → VeilLock.",
  ],
  camera: [
    "Use YOUR camera on this device only.",
    "Hosted VeilLock returns a consent receipt and veil recipe, not camera pixels.",
    "Install the local package to advertise a virtual camera named VeilLock.",
    NO_INJECT,
  ],
  screen: [
    "Use YOUR screen on this device only.",
    "Hosted /v1 is a consent receipt, not a screen capture.",
    "The local package can veil this display. Call apps still choose the camera.",
    NO_INJECT,
  ],
};

const EXTRA_APP_GUIDES = {
  discord: [
    "Use YOUR camera on this device only.",
    "Discord desktop: User Settings → Voice & Video → Camera → VeilLock.",
    "Input device: VeilLock Microphone on Linux after veillock wrap --mic. On Mac, BlackHole 2ch only if BlackHole is installed. On Windows, CABLE Output only if VB-Audio Virtual Cable is installed.",
    "Browser Discord uses the site camera permission, same as other WebRTC calls.",
    "The live picture is a veil or a keyed scramble. It is not AES-256-GCM.",
  ],
  whatsapp: [
    "WhatsApp desktop can use VeilLock only when its call screen offers a camera picker.",
    "WhatsApp on a phone cannot select a third-party camera.",
    "The live picture is a veil or a keyed scramble. It is not AES-256-GCM.",
  ],
  signal: [
    "Signal desktop: call device menu → Camera → VeilLock, when the app offers a picker.",
    "Signal on a phone cannot select a third-party camera.",
    "The live picture is a veil or a keyed scramble. It is not AES-256-GCM.",
  ],
  obs: [
    "OBS: Sources → Video Capture Device → VeilLock.",
    "Audio Input Capture: VeilLock Microphone on Linux, BlackHole 2ch on Mac if installed, or CABLE Output on Windows if VB-Cable is installed.",
    "An OBS recording of that source stores the veil or the scramble, not the local AES-256-GCM file.",
  ],
  webrtc: [
    "Browser WebRTC (Meet, Discord, and other sites): install the VeilLock Chromium extension. It wraps getUserMedia, so the page gets a veil by default instead of the real camera.",
    "With a shared key on both browsers, encoded frames are AES-256-GCM. A relay that forwards them unchanged sees ciphertext. A server that decodes does not recover the picture. Both ends need the extension.",
    "Without the extension, site permission → Camera → VeilLock. That path is the veil or the scramble, not AES-256-GCM.",
  ],
};

const PLATFORM_LIMITS =
  "iPhone FaceTime cannot select a third-party camera or microphone. Most phone clients (Zoom, Meet, Teams, WhatsApp, Signal) cannot either. Use a desktop app. VeilLock does not attach to a call app that is already running. Linux: veillock wrap --mic creates a PipeWire or PulseAudio source named VeilLock Microphone via pactl (not a kernel driver). Linux engulf (bwrap or LD_PRELOAD) only starts a new process that opens /dev/video* itself; PipeWire is not engulfed. macOS: no CoreAudio plugin is shipped; SIP and the hardened runtime block injection, including Apple-signed FaceTime. If BlackHole is installed the app selects BlackHole 2ch. Windows: no audio driver is shipped and capture APIs are not hooked. If VB-Audio Virtual Cable is installed the app selects CABLE Output and VeilLock writes to CABLE Input. Windows 11 build 22000+ can register a user-mode Media Foundation camera locally (friendly name VeilLock; Windows appends Windows Virtual Camera) while veilcam-register.exe is running. Other cameras remain. This worker does not register a camera. The coverage set is profiles, not a market-share ranking.";

const WRAP_SKILL_ADDENDUM = `

## Call wrap (local package)

\`veillock wrap\` feeds any desktop app that can choose a camera named VeilLock. \`veillock receive\` unveils a capture for a peer who has the out-of-band key. \`veillock record\` / \`veillock play\` are the local file.

| Path | What it actually is |
|------|---------------------|
| Live call video | Keyed 8×8 scramble (permutation, rotation, invert). Obfuscation. **Not AES-256-GCM.** The provider sees the veil or the tiles. A peer with the key gets an approximation after the call codec, not bit-exact plaintext. Channel swaps are not used; 4:2:0 would not bring them back. |
| Live call audio | Comfort-noise veil until the user lifts it, then the microphone, or a keyed PCM block permutation if scramble was chosen. **Not AES-256-GCM.** Opus and AAC do not carry sample ciphertext. A phase-rebuilding speech codec does not return the waveform. Short blocks can still contain speech fragments. |
| Virtual microphone | Linux: VeilLock creates **VeilLock Microphone** with pactl (not a kernel driver). macOS: no CoreAudio plugin; the app selects **BlackHole 2ch** only if BlackHole is installed. Windows: no driver; the app selects **CABLE Output** only if VB-Audio Virtual Cable is installed, and VeilLock writes to CABLE Input. |
| \`veillock record\` / \`play\` | **AES-256-GCM at rest** for video+audio, video-only, and audio-only, including what was sent and what a peer decrypted. The key is not in the file. Playback is in memory. Plaintext export is off unless explicitly requested and leaves this protection. A screen recorder pointed at a playing screen is outside the file. |
| Keys | Out of band: 32-byte pre-shared key, HMAC-wrapped broadcast key (the wrap is AES-GCM of the key, not of the pixels), or X25519 then HKDF-SHA256. The E2E media key uses the HKDF label veillock-e2e-media-v1. The scramble key is a different label and is not AES. |
| Engulf | Linux, app opens /dev/video* itself: bwrap or LD_PRELOAD via veillock engulf. PipeWire is not engulfed. Windows 11 build 22000+: local MFCreateVirtualCamera, friendly name VeilLock, picker suffix Windows Virtual Camera, no kernel driver, does not hook, other cameras remain, mic still CABLE Output. Without the helper, nothing is registered. macOS (SIP, hardened runtime, Apple-signed FaceTime) and iOS: not engulfed. Chromium: the extension wraps getUserMedia. |
| VeilLock link | **AES-256-GCM** on deflate-encoded frames over TCP between two VeilLock users. The call app still carries only the veil or the scramble. Both ends need VeilLock. A wrong key fails closed. |
| Browser encoded frames | **AES-256-GCM** on each encoded frame when both Chromium browsers run the extension and share the key. A forwarding relay sees ciphertext. A server that decodes or transcodes does not recover the picture. |

PulseCheck failure halts to veil or noise. Plaintext is not sent. The veil stays on until you lift it. Hosted \`GET /v1/wrap\` describes this. It does not scramble pixels, join a call, register a camera, or increment downloads. The loopback desk (\`veillock ui\` on 127.0.0.1:8761) plans join and engulf through the same adapter as the CLI and does not launch them. \`suite/azinterface-tile.json\` is the AZInterface handoff. VeilLock is not merged into AZInterface.

iPhone FaceTime cannot select a third-party camera or microphone. Most mobile clients cannot either.

Lamb Lens order: Service, then Clarity, then Peace. Identity is Aziel Eliab only. Forks are welcome and always allowed.

Works with ChatGPT (GPT Actions / OpenAI), Grok (xAI), Venice, Claude (Anthropic), Cursor (MCP), Glama (MCP), Perplexity, Microsoft Copilot / Bing, Google Gemini / Vertex, Mistral, Meta AI, Apple Intelligence surfaces, Amazon Q tooling, DuckAssist, You.com, Cohere, and other MCP/OpenAPI-capable assistants.
`;

export function wrapContract() {
  return {
    product: PRODUCT,
    ok: true,
    virtual_camera: false,
    hosted_does_not_scramble: true,
    plaintext: false,
    increments_downloads: false,
    aes_on_call_path: false,
    e2e: {
      aes_256_gcm: true,
      both_ends_need_veillock: true,
      call_app_stream: "veil or keyed scramble; obfuscation, not AES-256-GCM",
      link: "TCP between two VeilLock users; AES-256-GCM after a deflate encoder; not the call provider's connection",
      browser: "Chromium extension seals the browser's encoded frames with AES-256-GCM. A relay that forwards those frames unchanged sees ciphertext. A server that decodes or transcodes does not recover the picture.",
      scramble_fallback: "keyed visual scramble is obfuscation for a peer without VeilLock",
      pulsecheck: "failure sends nothing on the link; never plaintext",
      consent: "until the veil is lifted, the sealed picture is the veil, not the camera",
    },
    engulf: {
      linux_v4l2: "bwrap fresh /dev with only the VeilLock node, or LD_PRELOAD of open(/dev/video*). PipeWire is not engulfed.",
      windows: "Windows 11 build 22000+ user-mode MFCreateVirtualCamera while veilcam-register.exe is running locally. Friendly name VeilLock; Windows appends Windows Virtual Camera. No kernel driver. Does not hook. Other cameras remain. Mic is still CABLE Output. Without the helper, nothing is registered. This worker does not register a camera.",
      strategies: ["engulf-v4l2", "win11-vcam", "unregistered", "directshow-only", "extension-getusermedia", "pick-cam", "impossible"],
      coverage: "schema 1 profile registry; capture hint outranks the process name; unknown apps get a safe default; not a market-share ranking",
      meetings: "Teams, Meet, Zoom, Webex, Slack huddles, and Discord share one report. Gallery is one outgoing veil or scramble, not an AES mesh. Screen share is outside the camera. veillock join reads the link and does not join the call.",
      windows_10: "builds before 22000 are unregistered; MFCreateVirtualCamera is not available",
      directshow: "DirectShow-only apps do not see the Media Foundation camera; no DirectShow filter is shipped; VeilLock does not hook",
      flatpak_snap: "PipeWire, portal, Flatpak, and Snap are not engulfed",
      firefox_safari: "pick-cam; the extension is Chromium only; encoded-frame AES-256-GCM is not attached",
      macos: "not engulfed; SIP and the hardened runtime block injection; Apple-signed FaceTime cannot be injected into",
      ios: "apps cannot be wrapped",
      chromium: "extension wraps getUserMedia; default veil; encoded-frame AES-256-GCM only when both sides have the key",
    },
    call_video: {
      kind: "keyed compression-tolerant scramble",
      aes_256_gcm: false,
      provider_sees: "natural veil by default, or shuffled 8x8 tiles after the user lifts the veil for a protected call",
      peer_with_key: "approximate recovery after the call app's lossy codec; not bit-exact",
    },
    call_audio: {
      kind: "comfort-noise veil by default; real microphone only after the user lifts the veil; optional keyed PCM block permutation",
      aes_256_gcm: false,
      opus_aac: "Opus and AAC do not carry sample-level ciphertext. A speech codec that rebuilds phase does not return the original waveform. Short blocks can still contain speech fragments.",
    },
    virtual_microphone: {
      created_on_worker: false,
      call_audio_aes_256_gcm: false,
      linux: {
        created_by_veillock: true,
        selectable_name: "VeilLock Microphone",
        how: "pactl loads module-null-sink and module-remap-source. paplay feeds the sink. Stop unloads both modules. Requires pipewire-pulse or pulseaudio. Not a kernel driver.",
      },
      macos: {
        created_by_veillock: false,
        selectable_name: "BlackHole 2ch",
        how: "No CoreAudio HAL plugin is shipped. If BlackHole is installed, sox or ffmpeg feeds that device. The call app selects BlackHole 2ch, not a device named VeilLock.",
      },
      windows: {
        created_by_veillock: false,
        selectable_name: "CABLE Output",
        playback_name: "CABLE Input",
        how: "No kernel driver is shipped. If VB-Audio Virtual Cable is installed, ffmpeg writes to CABLE Input. The call app selects CABLE Output.",
      },
    },
    local_recording: {
      kind: "AES-256-GCM at rest for video+audio, video-only, and audio-only",
      aes_256_gcm: true,
      key_rotation: true,
      key_stored_in_file: false,
      plaintext_file: false,
      playback: "in memory inside veillock play, the loopback UI, and the extension player",
      plaintext_export: "off unless the user passes --export and the key; that export leaves VeilLock protection",
      screen_recorder: "another camera or a screen recorder pointed at a playing screen is outside the file",
      covers: ["sent", "received", "cli", "loopback-ui", "engulf", "browser-extension"],
      pulsecheck: "failure halts; plaintext is not written",
      commands: ["veillock record", "veillock play"],
    },
    keys: "out of band: pre-shared 32-byte key, HMAC-wrapped broadcast key, or X25519",
    consent: "default veil; the user lifts it; pulse failure returns veil or noise, never plaintext",
    platform_limits: PLATFORM_LIMITS,
    ios_facetime: IOS_FACETIME,
    lamb_lens: "Service, then Clarity, then Peace",
    author: "Aziel Eliab",
    identity: "Aziel Eliab only",
    surfaces: {
      layer: "Engine, then strategy adapters, then one plan object, then CLI, loopback UI, extension, this worker, and the AZInterface tile",
      loopback_ui: "veillock ui binds 127.0.0.1:8761. Plan this link and Plan engulf call the same adapter as the CLI. The desk seals and plays an AES-256-GCM recording in memory. It does not launch an app or join a call.",
      entries: ["wrap", "engulf", "join", "link", "play", "record"],
      cli: "veillock wrap, engulf, join, link, play, record, compat. Join and compat print the coverage report. Engulf launches only from the CLI when the plan says it can.",
      extension: "Chromium getUserMedia veil, and encoded-frame AES-256-GCM when both peers share the key. Not Firefox or Safari.",
      worker: "GET /v1/wrap describes the contract. It does not run the join planner, scramble pixels, register a camera, or increment downloads.",
      azinterface: {
        tile: "suite/azinterface-tile.json",
        merged_into_azinterface: false,
        implemented_in_azinterface_repo: false,
        repo: "https://github.com/AzielEliab/azinterface",
        launch: ["veillock", "ui"],
        note: "Handoff only. AZInterface is a separate Softwares desk. This worker is not a Softwares-tab product and does not boot that desk.",
      },
    },
  };
}

export function appsResult(src) {
  const raw = src && typeof src === "object" ? src : {};
  const app = String(raw.app || raw.name || "").toLowerCase().trim();
  const names = ["zoom", "meet", "teams", "facetime", "skype", "discord", "whatsapp", "signal", "obs", "webrtc"];
  const extra = app === "camera" || app === "screen" ? [app] : [];
  const pick = names.includes(app) ? [app] : names;
  const selected = [...pick, ...extra].filter((name, i, arr) => arr.indexOf(name) === i);
  const apps = selected.map((name) => ({
    app: name,
    inject: false,
    your_device_only: true,
    steps: APP_GUIDES[name] || EXTRA_APP_GUIDES[name] || APP_GUIDES.camera,
  }));
  return {
    product: PRODUCT,
    version: VERSION,
    inject: false,
    your_device_only: true,
    limitation: LIMITATION,
    apps,
    note: "Local-app steps only. " + NO_INJECT,
    ios_facetime: IOS_FACETIME,
    platform_limits: PLATFORM_LIMITS,
    call_video: "keyed visual scramble (obfuscation, not AES-256-GCM)",
    local_recording: "AES-256-GCM in the local package (veillock record / play)",
    author: "Aziel Eliab",
  };
}

export function citeDoc() {
  return {
    author: "Aziel Eliab",
    title: "VeilLock",
    one_line: "Live-stream encryption of visual output before it reaches any external display, by Aziel Eliab.",
    github: GITHUB,
    download: BASE + "/download",
    homepage: BASE + "/",
    doi: DOI,
    doi_url: DOI_URL,
    zenodo: ZENODO,
    license: "Apache-2.0",
    catalog: "https://aziel-runtime.vibelock.workers.dev/",
    version: VERSION,
    identity: "Aziel Eliab",
  };
}

function llmsTxt() {
  return [
    "# VeilLock",
    "",
    "Author: Aziel Eliab",
    "Identity: Aziel Eliab only",
    "License: Apache-2.0. Forks welcome.",
    "Version: " + VERSION,
    "",
    MOTTO,
    LIMITATION,
    NO_INJECT,
    IOS_FACETIME,
    "",
    "Homepage: " + BASE + "/",
    "Download (counted): " + BASE + "/download?asset=veillock-0.2.0.tar.gz",
    "Install: curl -fsSL " + BASE + "/install.sh | bash",
    "GitHub: " + GITHUB,
    "Cite: " + BASE + "/cite.json",
    "DOI: " + DOI_URL,
    "Skill: " + BASE + "/v1/skill",
    "Health: " + BASE + "/v1/health",
    "Mesh: " + BASE + "/v1/mesh (PROXY to aziel-runtime; default OFF; QNM-BUILD-1.0 + QNS-CD-1.0; no public qnsd proxy)",
    "AI assistants: " + AI_CLIENTS.join(", "),
    "OpenAPI: " + BASE + "/openapi.json",
    "MCP: https://aziel-runtime.vibelock.workers.dev/mcp",
    "",
  ].join("\n");
}

function sitemapXml() {
  const paths = ["/", "/cite.json", "/llms.txt", "/openapi.json", "/v1/skill", "/v1/health", "/v1/mesh", "/ai"];
  const urls = paths
    .map((p) => "  <url><loc>" + BASE + p + "</loc><changefreq>weekly</changefreq></url>")
    .join("\n");
  return '<?xml version="1.0" encoding="UTF-8"?>\n<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n' + urls + "\n</urlset>\n";
}

function mulberry32(a) {
  return function () {
    a |= 0;
    a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

async function seedToInt(seed) {
  const hex = await sha256Hex(String(seed == null ? "veillock" : seed));
  return parseInt(hex.slice(0, 8), 16) >>> 0;
}

function randInt(rng, lo, hi) {
  return lo + Math.floor(rng() * (hi - lo));
}

function pciFromValues(values) {
  if (values && typeof values === "object" && !Array.isArray(values)) {
    if (values.pci != null) {
      const token = String(values.pci).toUpperCase();
      if (token === "PASS") return { pci: "PASS", reason: "pci token PASS" };
      return { pci: token || "FAIL", reason: "pci token is not PASS" };
    }
    values = Object.values(values);
  }
  if (!Array.isArray(values) || values.length === 0) {
    return { pci: "FAIL", reason: "values required" };
  }
  const nums = [];
  for (const v of values) {
    if (v === "PASS" || v === true) continue;
    if (v === "FAIL" || v === false) return { pci: "FAIL", reason: "explicit FAIL token" };
    const n = Number(v);
    if (!Number.isFinite(n)) return { pci: "FAIL", reason: "non-finite value" };
    nums.push(n);
  }
  if (!nums.length) return { pci: "FAIL", reason: "no numeric pulse samples" };
  if (nums.every((n) => n === 0)) return { pci: "FAIL", reason: "dead pulse (all zeros)" };
  return { pci: "PASS", reason: "finite non-zero pulse samples", n: nums.length };
}

function consentDecision(body) {
  const src = body && typeof body === "object" ? body : {};
  const obfuscationOn = src.obfuscation_on == null ? true : Boolean(src.obfuscation_on);
  const callAccepted = Boolean(src.call_accepted || src.azos_call_accepted);
  const actor = String(src.actor || "");
  let obfuscate = true;
  let reason = "default veil: camera and video protected";
  if (!obfuscationOn) {
    obfuscate = false;
    reason = "user turned obfuscation off";
  } else if (callAccepted) {
    obfuscate = false;
    reason = "user accepted a call through AZ-OS";
  }
  return {
    azos_hook: true,
    overlay: "AZ-OS",
    identity: IDENTITY,
    user_controls: true,
    obfuscation_on: obfuscationOn,
    call_accepted: callAccepted,
    obfuscate,
    veil: obfuscate ? "on" : "lifted",
    reason,
    actor: actor || null,
    kernel: false,
    kills_caller_os: false,
    hosted_azos: AZOS_HOST,
  };
}

async function obfuscateRecipe(body) {
  let width = Number(body && body.width);
  let height = Number(body && body.height);
  if (!Number.isFinite(width) || width <= 0) width = 640;
  if (!Number.isFinite(height) || height <= 0) height = 480;
  width = Math.min(1920, Math.max(8, width | 0));
  height = Math.min(1080, Math.max(8, height | 0));
  const seed = body && body.seed != null ? body.seed : 0;
  const kind = String((body && body.source) || "camera").toLowerCase();
  const rng = mulberry32(await seedToInt(seed));
  const luma = 88;
  const wash = [Math.round(luma * 0.72 + 20), Math.round(luma * 0.58 + 16), Math.round(luma * 0.90 + 38)];
  const grain = Number(rng().toFixed(4));
  const bg = [randInt(rng, 24, 64), randInt(rng, 24, 64), randInt(rng, 24, 64)];
  const nRect = randInt(rng, 2, 6);
  const rectangles = [];
  for (let i = 0; i < nRect; i++) {
    const y1 = randInt(rng, 0, Math.max(height, 1));
    const x1 = randInt(rng, 0, Math.max(width, 1));
    const y2 = randInt(rng, y1 + 1, height + 1);
    const x2 = randInt(rng, x1 + 1, width + 1);
    const color = [randInt(rng, 80, 210), randInt(rng, 80, 210), randInt(rng, 80, 210)];
    const bar = Math.min(y1 + Math.max(1, Math.floor(height / 16)), y2);
    const bar_color = [randInt(rng, 40, 120), randInt(rng, 40, 120), randInt(rng, 40, 120)];
    rectangles.push({ y1, x1, y2, x2, color, title_bar: { y1, y2: bar, x1, x2, color: bar_color } });
  }
  const camera = kind === "screen" ? false : true;
  return {
    mode: "obfuscation",
    pipeline: camera ? "natural_camera_veil" : "synthetic_ui_noise",
    plaintext: false,
    virtual_camera: false,
    default_display: "obfuscation",
    azos_hook: true,
    seed: String(seed),
    width,
    height,
    channels: 3,
    wash: camera ? wash : bg,
    grain: camera ? grain : null,
    background: bg,
    rectangles: camera ? [] : rectangles,
    description: camera
      ? "Natural camera/video veil recipe (soft wash, grain, live-looking). Not plaintext and not GCM snow. Spatial camera pixels are not copied."
      : "Synthetic UI-noise recipe (fake windows / panels). Not plaintext and not GCM snow.",
  };
}

function openapiDoc() {
  return {
    openapi: "3.1.0",
    info: {
      title: "VeilLock Runtime API",
      version: VERSION,
      summary: MOTTO,
      description: "Consent-gated camera protection via AZ-OS. Natural camera/video veil unless the user turns it off or accepts a call. " + IOS_FACETIME + " Suite mesh /v1/mesh/* PROXY to aziel-runtime (AZIEL_RUNTIME). Default OFF. QNM-BUILD-1.0 live|locked|isolated. QNS-CD-1.0 photon QNS1 packet transfer is a hub cite / Worker mesh cross-map (not a Softwares-tab product; no public qnsd proxy). No Node Gate. No auto-heal. Not anonymity. Aziel Eliab only.",
    },
    servers: [{ url: BASE }],
    paths: {
      "/count": {
        get: {
          operationId: "veillockCount",
          summary: "Isolated download/view counts. Does not increment.",
          responses: {
            "200": {
              description: "{project, views, downloads, total}",
              content: {
                "application/json": {
                  schema: {
                    type: "object",
                    required: ["project", "views", "downloads", "total"],
                    properties: {
                      project: { type: "string", const: "veillock" },
                      views: { type: "integer" },
                      downloads: { type: "integer" },
                      total: { type: "integer" },
                    },
                  },
                },
              },
            },
          },
        },
      },
      "/v1/health": { get: { operationId: "veillockHealth", summary: "Liveness. AZ-OS hook present.", responses: { "200": { description: "OK" } } } },
      ...meshOpenApiPaths(),
      "/v1/pulse": {
        post: {
          operationId: "veillockPulse",
          summary: "PulseCheck. Fail → halt/noise, never a plaintext claim.",
          requestBody: { required: true, content: { "application/json": { schema: { type: "object", properties: { values: { oneOf: [{ type: "array" }, { type: "object" }] } } } } } },
          responses: { "200": { description: "PCI PASS or FAIL (halt/noise)" } },
        },
      },
      "/v1/obfuscate-preview": {
        post: {
          operationId: "veillockObfuscatePreview",
          summary: "Natural camera/video veil recipe",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { seed: {}, width: { type: "integer" }, height: { type: "integer" }, source: { type: "string" } } } } } },
          responses: { "200": { description: "Obfuscation recipe" } },
        },
      },
      "/v1/azos-hook": {
        post: {
          operationId: "veillockAzosHook",
          summary: "AZ-OS consent-gate status",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { obfuscation_on: { type: "boolean" }, call_accepted: { type: "boolean" }, actor: { type: "string" } } } } } },
          responses: { "200": { description: "Hook status" } },
        },
      },
      "/v1/call-accept": {
        post: {
          operationId: "veillockCallAccept",
          summary: "User accepted a call through AZ-OS (consent receipt)",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { actor: { type: "string" }, call_id: { type: "string" } } } } } },
          responses: { "200": { description: "Call-accept receipt; veil lifted" } },
        },
      },
      "/v1/consent": {
        post: {
          operationId: "veillockConsent",
          summary: "Evaluate veil: default on; lift if user off or AZ-OS accept",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { obfuscation_on: { type: "boolean" }, call_accepted: { type: "boolean" } } } } } },
          responses: { "200": { description: "Consent decision" } },
        },
      },
      "/v1/apps": {
        get: {
          operationId: "veillockAppsGet",
          summary: "Local-app steps. Does not inject into FaceTime, Zoom, Meet, Teams, or Skype.",
          parameters: [{ name: "app", in: "query", schema: { type: "string" } }],
          responses: { "200": { description: "Local-app steps" } },
        },
        post: {
          operationId: "veillockApps",
          summary: "Local-app steps. Does not inject into FaceTime, Zoom, Meet, Teams, or Skype.",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { app: { type: "string" } } } } } },
          responses: { "200": { description: "Local-app steps" } },
        },
      },
      "/v1/wrap": {
        get: {
          operationId: "veillockWrapGet",
          summary: "Call-wrap contract. Live video is a scramble, not AES-256-GCM. Local record/play is AES-256-GCM. Join and engulf planning run on the local desk. Does not join a call, register a camera, or increment downloads.",
          responses: { "200": { description: "Honesty contract for wrap, receive, record, and play" } },
        },
        post: {
          operationId: "veillockWrap",
          summary: "Call-wrap contract. Live video is a scramble, not AES-256-GCM. Local record/play is AES-256-GCM. Join and engulf planning run on the local desk. Does not join a call, register a camera, or increment downloads.",
          responses: { "200": { description: "Honesty contract for wrap, receive, record, and play" } },
        },
      },
    },
  };
}

export async function handleRuntime(request, url, env) {
  const path = url.pathname;
  if (path === "/v1/mesh" || path.startsWith("/v1/mesh/")) return null;
  if (path === "/v1/health" && request.method === "GET") {
    return runtimeJson({
      ok: true, product: PRODUCT, version: VERSION, motto: MOTTO, identity: IDENTITY,
      azos_hook: true, user_controls: true, obfuscation_default: true,
      virtual_camera: false, plaintext: false, inject: false,
      ios_facetime: IOS_FACETIME, tether: "local",
      limitation: LIMITATION, author: "Aziel Eliab",
      mesh: meshPointer(),
    });
  }

  if (path === "/v1/skill" && request.method === "GET") {
    return new Response(SKILL_MARKDOWN + WRAP_SKILL_ADDENDUM, {
      status: 200,
      headers: {
        "Content-Type": "text/markdown; charset=utf-8",
        "Cache-Control": "private, no-store",
        "X-KV-Increment": "false",
        "Access-Control-Allow-Origin": "*",
      },
    });
  }

  if (path === "/openapi.json" && request.method === "GET") return runtimeJson(openapiDoc());
  if (path === "/cite.json" && request.method === "GET") return runtimeJson(citeDoc());
  if (path === "/llms.txt" && request.method === "GET") {
    return new Response(llmsTxt(), {
      status: 200,
      headers: { "Content-Type": "text/plain; charset=utf-8", "Cache-Control": "public, max-age=300", ...runtimeCors() },
    });
  }
  if (path === "/sitemap.xml" && request.method === "GET") {
    return new Response(sitemapXml(), {
      status: 200,
      headers: { "Content-Type": "application/xml; charset=utf-8", "Cache-Control": "public, max-age=300", ...runtimeCors() },
    });
  }
  if (path === "/ai" && request.method === "GET") {
    return runtimeJson({
      product: PRODUCT, title: "Use with AI assistants", motto: MOTTO, clients: AI_CLIENTS, identity: "Aziel Eliab only",
      openapi: BASE + "/openapi.json", health: BASE + "/v1/health",
      mesh: meshPointer(),
      ios_facetime: IOS_FACETIME, ...aiHowTo(BASE),
    });
  }
  if (path === "/v1" && request.method === "GET") {
    return runtimeJson({
      product: PRODUCT,
      identity: IDENTITY,
      endpoints: [
        "GET /v1/health",
        "GET /v1/mesh",
        "GET /v1/mesh/nodes",
        "GET /v1/apps",
        "POST /v1/apps",
        "GET /v1/wrap",
        "POST /v1/wrap",
        "POST /v1/pulse",
        "POST /v1/obfuscate-preview",
        "POST /v1/azos-hook",
        "POST /v1/call-accept",
        "POST /v1/consent",
        "GET /openapi.json",
        "GET /ai",
        "GET /cite.json",
      ],
    });
  }
  if (path === "/v1/pulse" && request.method === "POST") {
    let body = {};
    try { body = await readJsonBody(request); } catch (e) { return runtimeJson({ ok: false, error: e.message, plaintext: false }, e.status || 400); }
    const check = pciFromValues(body.values);
    const pass = check.pci === "PASS";
    return runtimeJson({
      ok: true,
      product: PRODUCT,
      pci: check.pci,
      reason: check.reason,
      halted: !pass,
      plaintext: false,
      display: pass ? "obfuscation" : "noise",
      phoenix: pass ? false : true,
      virtual_camera: false,
      note: pass
        ? "PCI PASS. Default display is obfuscation, not plaintext. " + TETHER_NOTE
        : "Pulse fail → halt/noise, never plaintext. " + TETHER_NOTE,
      ios_facetime: IOS_FACETIME,
    });
  }
  if (path === "/v1/obfuscate-preview" && request.method === "POST") {
    let body = {};
    try { body = await readJsonBody(request); } catch (e) { return runtimeJson({ ok: false, error: e.message, plaintext: false, virtual_camera: false }, e.status || 400); }
    const recipe = await obfuscateRecipe(body);
    return runtimeJson({
      ok: true,
      product: PRODUCT,
      ...recipe,
      tether: "local",
      ios_facetime: IOS_FACETIME,
      note: TETHER_NOTE + " Default natural camera/video veil, not plaintext. User controls.",
    });
  }
  if ((path === "/v1/azos-hook" || path === "/v1/consent") && request.method === "POST") {
    let body = {};
    try { body = await readJsonBody(request); } catch (e) { return runtimeJson({ ok: false, error: e.message }, e.status || 400); }
    return runtimeJson({
      ok: true,
      product: PRODUCT,
      ...consentDecision(body),
      note: "You control the veil. Hosted receipt only. " + TETHER_NOTE,
    });
  }
  if (path === "/v1/wrap" && (request.method === "GET" || request.method === "POST")) {
    return runtimeJson(wrapContract());
  }
  if (path === "/v1/apps" && (request.method === "GET" || request.method === "POST")) {
    let body = {};
    try { body = await readJsonBody(request); } catch (e) { return runtimeJson({ ok: false, error: e.message }, e.status || 400); }
    const app = body.app || url.searchParams.get("app");
    return runtimeJson({
      ok: true,
      ...appsResult({ app }),
    });
  }
  if (path === "/v1/call-accept" && request.method === "POST") {
    let body = {};
    try { body = await readJsonBody(request); } catch (e) { return runtimeJson({ ok: false, error: e.message }, e.status || 400); }
    const actor = String((body && body.actor) || "user");
    const callId = body && body.call_id != null ? String(body.call_id) : null;
    const decision = consentDecision({ obfuscation_on: true, call_accepted: true, actor });
    return runtimeJson({
      ok: true,
      product: PRODUCT,
      accepted: true,
      call_id: callId,
      ...decision,
      note: "Consent receipt: you accepted a call through AZ-OS. Veil lifted for this session. " + TETHER_NOTE,
    });
  }
  if (path === "/v1/pulse" || path === "/v1/obfuscate-preview" || path === "/v1/azos-hook" || path === "/v1/call-accept" || path === "/v1/consent" || path === "/v1/apps" || path === "/v1/wrap") {
    return runtimeJson({ error: "method not allowed" }, 405);
  }
  if (path.startsWith("/v1/")) return runtimeJson({ error: "not found", product: PRODUCT, hint: "GET /v1/health GET /v1/skill GET /v1/mesh POST /v1/{consent,call-accept,pulse}" }, 404);
  return null;
}
