/**
 * VeilLock hosted runtime (Cloudflare Worker).
 * PulseCheck + obfuscation noise recipe. Not a virtual camera.
 * Desktop tether stays local. iOS FaceTime cannot pick a third-party cam.
 */
function runtimeCors() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
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

function aiHowTo(base) {
  const openapi = base + "/openapi.json";
  const health = base + "/v1/health";
  return {
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
    mcp_catalog: "https://aziel-runtime.vibelock.workers.dev/mcp",
    notes: [
      "GET /download still serves the gzip tarball and increments the counter.",
      "/v1, /openapi.json, and /ai do not increment DOWNLOADS.",
    ],
  };
}

const PRODUCT = "veillock";
const EXAMPLE_PAYLOAD = {
  "app": "zoom",
  "source": "camera",
  "mode": "obfuscation",
  "note": "YOUR camera/screen only. Not a call interceptor."
};

const SKILL_MARKDOWN = "---\nname: VeilLock\ndescription: Use when calling VeilLock hosted /v1 or installing the local package. Author Aziel Eliab.\n---\n\n# VeilLock\n\nLive-stream encryption of visual output before it reaches any external display. Not FaceTime/Zoom intercept. Not call intercept. Author: Aziel Eliab.\n\n**THIS IS:** live-stream encryption of visual output, UI rendering, and screen-level data streams before they reach any external display.\n\n**THIS IS NOT:** FaceTime/Zoom intercept, call intercept, a VPN, or a claim that network packets are captured.\n\nAuthor: **Aziel Eliab**. Forks are welcome and always allowed. Apache-2.0.\n\nAlways send `User-Agent: Mozilla/5.0`. Cloudflare Workers may 403 an empty agent.\n\n## Call these URLs\n\n- Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json\n- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json\n- MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`\n- Live skill (this markdown): `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`\n\nOps (do **not** increment downloads or views):\n\n| Method | Path | What |\n|--------|------|------|\n| GET | `/v1/health` | Liveness. Does not increment downloads. |\n| GET | `/v1/skill` | This markdown. Does not increment downloads. |\n| POST | `/v1/pulse` | Runtime key-state pulse. Not call intercept. |\n| POST | `/v1/obfuscate-preview` | Preview obfuscation. Not FaceTime/Zoom intercept. |\n\nGrok: import OpenAPI as a custom tool. ChatGPT: GPT Actions. Venice: HTTP tools.\n\n## Example\n\n```bash\ncurl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/health\ncurl -s -A 'Mozilla/5.0' https://veillock-download-tracker.vibelock.workers.dev/v1/skill\ncurl -s -A 'Mozilla/5.0' -X POST https://veillock-download-tracker.vibelock.workers.dev/v1/pulse \\\n  -H 'content-type: application/json' \\\n  -d '{}'\n```\n\n## Local (after one-click install)\n\n```bash\ncurl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash\nveillock ui\n```\n\nThen open http://127.0.0.1:8761 (loopback only).\n\nDOI: https://doi.org/10.5281/zenodo.21431659  \nRecord: https://zenodo.org/records/21431659  \n\nCounted download (gzip HTTP 200, no 302): https://veillock-download-tracker.vibelock.workers.dev/download?asset=veillock-0.1.0.tar.gz\nGitHub: https://github.com/AzielEliab/veillock\n\n## Catalog + local UI\n\nAuthor: **Aziel Eliab**. Honest scope: YOUR camera/screen only. Not a call interceptor. Not FaceTime/Zoom intercept.\n\n- Catalog product: https://aziel-runtime.vibelock.workers.dev/p/veillock/\n- Catalog OpenAPI: https://aziel-runtime.vibelock.workers.dev/openapi.json\n- Catalog MCP: `POST https://aziel-runtime.vibelock.workers.dev/mcp`\n- This Worker skill: `GET https://veillock-download-tracker.vibelock.workers.dev/v1/skill`\n- This Worker OpenAPI: https://veillock-download-tracker.vibelock.workers.dev/openapi.json\n- Sample payload: `GET https://veillock-download-tracker.vibelock.workers.dev/v1/example`\n\nLocal UI: **Import JSON file** (`type=file`) and **Export JSON**. Then `veillock doctor`.\n\nGrok: import catalog or Worker OpenAPI as a custom tool. ChatGPT: GPT Actions. Venice: HTTP tools.\n";

const VERSION = "0.1.0";
const BASE = "https://veillock-download-tracker.vibelock.workers.dev";
const MOTTO = "Render to encrypt to decode locally to display.";
const IOS_FACETIME = "iOS FaceTime cannot pick a third-party camera.";
const TETHER_NOTE = "Desktop `tether` stays local. This hosted API is not a virtual camera.";

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

async function obfuscateRecipe(body) {
  let width = Number(body && body.width);
  let height = Number(body && body.height);
  if (!Number.isFinite(width) || width <= 0) width = 640;
  if (!Number.isFinite(height) || height <= 0) height = 480;
  width = Math.min(1920, Math.max(8, width | 0));
  height = Math.min(1080, Math.max(8, height | 0));
  const seed = body && body.seed != null ? body.seed : 0;
  const rng = mulberry32(await seedToInt(seed));
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
  return {
    mode: "obfuscation",
    plaintext: false,
    virtual_camera: false,
    default_display: "obfuscation",
    seed: String(seed),
    width,
    height,
    channels: 3,
    background: bg,
    rectangles,
    description: "Synthetic UI-noise recipe (fake windows / panels). Not plaintext camera frames and not GCM snow. Not a virtual camera.",
  };
}

function openapiDoc() {
  return {
    openapi: "3.1.0",
    info: {
      title: "VeilLock Runtime API",
      version: VERSION,
      summary: MOTTO,
      description: "PulseCheck and obfuscation preview. Not a virtual camera. " + IOS_FACETIME,
    },
    servers: [{ url: BASE }],
    paths: {
            "/v1/example": { get: { operationId: "veillockExample", summary: "Sample JSON payload. Does not increment downloads.", responses: { "200": { description: "OK" } } } },
      "/v1/health": { get: { operationId: "veillockHealth", summary: "Liveness", responses: { "200": { description: "OK" } } } },
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
          summary: "Return a noise recipe, not a virtual camera",
          requestBody: { required: false, content: { "application/json": { schema: { type: "object", properties: { seed: {}, width: { type: "integer" }, height: { type: "integer" } } } } } },
          responses: { "200": { description: "Obfuscation recipe" } },
        },
      },
    },
  };
}

export async function handleRuntime(request, url, env) {
  const path = url.pathname;
  if (path === "/v1/health" && request.method === "GET") {
    return runtimeJson({
      ok: true, author: "Aziel Eliab", product: PRODUCT, version: VERSION, motto: MOTTO,
      virtual_camera: false, plaintext: false, ios_facetime: IOS_FACETIME, tether: "local",
    });
  }
  if ((path === "/v1/example" || path === "/v1/example/") && (request.method === "GET" || request.method === "HEAD")) {
    return runtimeJson({
      ok: true,
      product: PRODUCT,
      author: "Aziel Eliab",
      example: EXAMPLE_PAYLOAD,
      note: "Sample payload only. Does not increment downloads.",
    });
  }


  if (path === "/v1/skill" && request.method === "GET") {
    return new Response(SKILL_MARKDOWN, {
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
  if (path === "/ai" && request.method === "GET") {
    return runtimeJson({
      product: PRODUCT, title: "Use with Grok, ChatGPT, Venice", motto: MOTTO,
      openapi: BASE + "/openapi.json", health: BASE + "/v1/health",
      ios_facetime: IOS_FACETIME, ...aiHowTo(BASE),
    });
  }
  if (path === "/v1" && request.method === "GET") {
    return runtimeJson({ product: PRODUCT, endpoints: ["GET /v1/health", "POST /v1/pulse", "POST /v1/obfuscate-preview", "GET /openapi.json", "GET /ai"] });
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
      note: TETHER_NOTE + " Default obfuscation, not plaintext.",
    });
  }
  if (path === "/v1/pulse" || path === "/v1/obfuscate-preview") return runtimeJson({ error: "method not allowed" }, 405);
  if (path.startsWith("/v1/")) return runtimeJson({ error: "not found", product: PRODUCT }, 404);
  return null;
}
