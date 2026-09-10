/**
 * Suite node mesh — QNM-BUILD-1.0 Live Nodes contract.
 * Default OFF. Public rollup is live|locked|isolated counts only.
 * No Node Gate. No auto-heal. Not an anonymity network.
 * /v1/mesh/* PROXY to aziel-runtime (AZIEL_RUNTIME binding).
 * Author: Aziel Eliab only.
 */

const RUNTIME = "https://aziel-runtime.vibelock.workers.dev";
const FRAGGATE_MCP = "https://aziel-runtime.vibelock.workers.dev/mcp";
const FRAGGATE_CALL = "https://aziel-runtime.vibelock.workers.dev/v1/fraggate/call";
const SERVICE_BINDING_ORIGIN = "https://aziel-runtime";
const IDENTITY = "Aziel Eliab";

export const QNM_SPEC = "QNM-BUILD-1.0";
export const MESH_KERNEL = "NM-0.1";
export const MESH_DEFAULT_OFF = true;
export const MESH_ANONYMITY_NETWORK = false;
export const MESH_NODE_GATE = false;
export const MESH_AUTO_HEAL = false;
export const MESH_IDENTITY = IDENTITY;
export const MESH_SLUG = "mesh";
export const MESH_PRODUCT = "veillock";
export const MESH_PATH = "/v1/mesh";
export const MESH_STATUS_PATH = "/v1/mesh/status";
export const MESH_NODES_PATH = "/v1/mesh/nodes";
export const MESH_ENABLE_PATH = "/v1/mesh/enable";
export const MESH_DISABLE_PATH = "/v1/mesh/disable";
export const MESH_JOIN_PATH = "/v1/mesh/join";
export const MESH_HEARTBEAT_PATH = "/v1/mesh/heartbeat";
export const MESH_LEAVE_PATH = "/v1/mesh/leave";
export const MESH_BROADCAST_PATH = "/v1/mesh/broadcast";
export const ANON_BROADCAST = "https://github.com/AzielEliab/anon-broadcast";

export const MESH_NOTE =
  "QNM-BUILD-1.0. Suite mesh default off. Live|locked|isolated counts only. No Node Gate. No auto-heal. Not an anonymity network. Author: Aziel Eliab only.";

export const MESH_OPS = Object.freeze([
  "status",
  "enable",
  "disable",
  "join",
  "heartbeat",
  "leave",
  "nodes",
  "broadcast",
]);

export const MESH_PROXY_ROUTES = Object.freeze([
  { path: MESH_PATH, methods: ["get", "head"], op: "status", summary: "PROXY to aziel-runtime GET /v1/mesh. Suite mesh status. Default OFF. Not a local op." },
  { path: MESH_STATUS_PATH, methods: ["get"], op: "status", summary: "PROXY alias of GET /v1/mesh. Not a local op." },
  { path: MESH_NODES_PATH, methods: ["get"], op: "nodes", summary: "PROXY to aziel-runtime GET /v1/mesh/nodes. Live Nodes (5-minute presence). Not a local op." },
  { path: MESH_ENABLE_PATH, methods: ["post"], op: "enable", summary: "PROXY to aziel-runtime POST /v1/mesh/enable. Operator bearer required. Rate-limited. Not a local op." },
  { path: MESH_DISABLE_PATH, methods: ["post"], op: "disable", summary: "PROXY to aziel-runtime POST /v1/mesh/disable. Always allowed. Not a local op." },
  { path: MESH_JOIN_PATH, methods: ["post"], op: "join", summary: "PROXY to aziel-runtime POST /v1/mesh/join. Body {product, node_id?, label?, presence?}. Refused while OFF. Not a local op." },
  { path: MESH_HEARTBEAT_PATH, methods: ["post"], op: "heartbeat", summary: "PROXY to aziel-runtime POST /v1/mesh/heartbeat. Body {node_id}. Not a local op." },
  { path: MESH_LEAVE_PATH, methods: ["post"], op: "leave", summary: "PROXY to aziel-runtime POST /v1/mesh/leave. Body {node_id}. Not a local op." },
  { path: MESH_BROADCAST_PATH, methods: ["post"], op: "broadcast", summary: "PROXY to aziel-runtime POST /v1/mesh/broadcast. SHA-256 receipt only. Not AnonBroadcast upload. Not a local op." },
]);

/** Allowlisted suite mesh PROXY paths. Not a Node Gate. Not local ops. */
export const MESH_ROUTE_METHODS = Object.freeze({
  "/v1/mesh": ["GET", "HEAD"],
  "/v1/mesh/status": ["GET", "HEAD"],
  "/v1/mesh/nodes": ["GET", "HEAD"],
  "/v1/mesh/enable": ["POST"],
  "/v1/mesh/disable": ["POST"],
  "/v1/mesh/join": ["POST"],
  "/v1/mesh/heartbeat": ["POST"],
  "/v1/mesh/leave": ["POST"],
  "/v1/mesh/broadcast": ["POST"],
});

export function meshCorsHeaders() {
  return {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Methods": "GET, HEAD, POST, OPTIONS",
    "Access-Control-Allow-Headers":
      "Content-Type, Accept, Authorization, X-Aziel-Runtime-Token, User-Agent",
    "Access-Control-Expose-Headers": "X-Aziel-Runtime-Version, X-Aziel-Mesh-Door",
  };
}

function firstNum(...vals) {
  for (const raw of vals) {
    if (raw == null || raw === "") continue;
    const n = typeof raw === "number" ? raw : Number(String(raw).replace(/,/g, ""));
    if (Number.isFinite(n) && n >= 0) return Math.floor(n);
  }
  return null;
}

function asList(value) {
  if (!value) return [];
  if (Array.isArray(value)) return value;
  if (typeof value === "object") return Object.values(value);
  return [];
}

function truthyEnabled(value) {
  if (value === true || value === 1) return true;
  const s = String(value || "").trim().toLowerCase();
  return s === "on" || s === "enabled" || s === "true" || s === "live";
}

export function emptyRollup() {
  return { live: 0, locked: 0, isolated: 0 };
}

export function meshRollup(mesh) {
  const m = mesh && typeof mesh === "object" ? mesh : {};
  const r = m.rollup && typeof m.rollup === "object" && !Array.isArray(m.rollup) ? m.rollup : {};
  return {
    live: firstNum(r.live, m.live_nodes, m.live) ?? 0,
    locked: firstNum(r.locked, m.locked_nodes, m.locked) ?? 0,
    isolated: firstNum(r.isolated, m.isolated_nodes, m.isolated) ?? 0,
  };
}

function parseRollup(inner, listedLive) {
  const r = inner.rollup && typeof inner.rollup === "object" && !Array.isArray(inner.rollup)
    ? inner.rollup
    : {};
  const live = firstNum(
    r.live,
    r.live_nodes,
    r.live_count,
    inner.live,
    inner.live_nodes,
    inner.mesh_live_nodes,
    inner.live_count,
    inner.count,
    inner.n,
    inner.node_count,
    listedLive,
  );
  const locked = firstNum(r.locked, r.locked_nodes, r.locked_count, inner.locked, inner.locked_nodes, inner.locked_count);
  const isolated = firstNum(r.isolated, r.isolated_nodes, r.isolated_count, inner.isolated, inner.isolated_nodes, inner.isolated_count);
  return {
    live: live != null ? live : 0,
    locked: locked != null ? locked : 0,
    isolated: isolated != null ? isolated : 0,
  };
}

export function emptyMesh(extra = {}) {
  const rollup = extra.rollup && typeof extra.rollup === "object"
    ? { ...emptyRollup(), ...extra.rollup }
    : emptyRollup();
  return {
    ok: true,
    code: extra.code || "MESH-OK",
    spec: QNM_SPEC,
    kernel: MESH_KERNEL,
    enabled: false,
    default_off: true,
    live_nodes: 0,
    status: extra.status || "off",
    source: extra.source || "fallback",
    node_gate: false,
    auto_heal: false,
    anonymity_network: false,
    author: MESH_IDENTITY,
    identity: MESH_IDENTITY,
    note: MESH_NOTE,
    door: MESH_PATH,
    ...extra,
    spec: QNM_SPEC,
    rollup,
    node_gate: false,
    auto_heal: false,
    anonymity_network: false,
    author: MESH_IDENTITY,
    identity: MESH_IDENTITY,
  };
}

export function compactMeshNode(raw) {
  if (raw == null) return null;
  if (typeof raw === "string") {
    const id = raw.trim();
    return id ? { id } : null;
  }
  if (typeof raw !== "object") return null;
  const id = String(raw.id || raw.node_id || raw.session_id || raw.peer || raw.name || "").trim();
  const product = String(raw.product || raw.slug || raw.suite || "").trim();
  const seen = raw.last_utc || raw.last_seen || raw.seen_utc || raw.heartbeat_utc || "";
  if (!id && !product && !seen) return null;
  const out = {};
  if (id) out.id = id;
  if (product) out.product = product;
  if (seen) out.last_utc = String(seen);
  return out;
}

export function parseMeshDoc(body) {
  if (body == null) return emptyMesh({ status: "unavailable", source: "empty" });
  if (typeof body !== "object" || Array.isArray(body)) {
    return emptyMesh({ status: "unavailable", source: "empty" });
  }
  const inner = body.result && typeof body.result === "object" && !Array.isArray(body.result)
    ? { ...body, ...body.result }
    : (body.mesh && typeof body.mesh === "object" && !Array.isArray(body.mesh)
      ? { ...body, ...body.mesh }
      : body);
  const listed = asList(inner.nodes || inner.list || inner.peers || inner.live_nodes_list)
    .map(compactMeshNode)
    .filter(Boolean);
  const rollup = parseRollup(inner, listed.length ? listed.length : null);
  const enabled = truthyEnabled(inner.enabled)
    || truthyEnabled(inner.mesh_enabled)
    || String(inner.status || "").toLowerCase() === "on";
  const unavailable = inner.ok === false
    && !enabled
    && (inner.error || inner.status === "unavailable" || inner.status === "not_found");
  const status = enabled ? "on" : (unavailable ? "unavailable" : "off");
  const live = enabled ? rollup.live : 0;
  const locked = enabled ? rollup.locked : 0;
  const isolated = enabled ? rollup.isolated : 0;
  const products = asList(inner.products_present || inner.products)
    .map((p) => (typeof p === "string" ? p : (p && (p.product || p.slug || p.name)) || ""))
    .map((s) => String(s).trim())
    .filter(Boolean);
  return emptyMesh({
    ok: inner.ok !== false,
    enabled,
    default_off: inner.default_off !== false,
    live_nodes: live,
    rollup: { live, locked, isolated },
    products_present: products,
    nodes: listed,
    status,
    source: inner.source || "parsed",
    door: inner.door || MESH_PATH,
    note: enabled
      ? "QNM-BUILD-1.0. Suite mesh is on. Live|locked|isolated counts only. No Node Gate. No auto-heal. Not an anonymity network."
      : MESH_NOTE,
  });
}

export function publicMesh(mesh) {
  const m = mesh && typeof mesh === "object" ? mesh : emptyMesh();
  const enabled = !!m.enabled;
  const rollup = enabled ? meshRollup(m) : emptyRollup();
  return {
    spec: QNM_SPEC,
    kernel: MESH_KERNEL,
    enabled,
    default_off: m.default_off !== false,
    live_nodes: enabled ? rollup.live : 0,
    rollup,
    status: enabled ? "on" : (m.status === "unavailable" ? "unavailable" : "off"),
    source: m.source || "fallback",
    node_gate: false,
    auto_heal: false,
    anonymity_network: false,
    author: MESH_IDENTITY,
    identity: MESH_IDENTITY,
    door: MESH_PATH,
    status_path: MESH_STATUS_PATH,
    nodes_path: MESH_NODES_PATH,
    join: MESH_JOIN_PATH,
    heartbeat: MESH_HEARTBEAT_PATH,
    enable: MESH_ENABLE_PATH,
    disable: MESH_DISABLE_PATH,
    leave: MESH_LEAVE_PATH,
    broadcast: MESH_BROADCAST_PATH,
    mcp: FRAGGATE_MCP,
    fraggate: FRAGGATE_CALL,
    slug: MESH_SLUG,
    product: MESH_PRODUCT,
    ops: MESH_OPS.slice(),
    origin: RUNTIME + MESH_PATH,
    note: m.note || MESH_NOTE,
  };
}

export function meshStatusLine(mesh) {
  const m = mesh && typeof mesh === "object" ? mesh : emptyMesh();
  if (m.enabled) {
    const r = meshRollup(m);
    return "Suite mesh: on · live " + r.live + " · locked " + r.locked + " · isolated " + r.isolated + ". Not an anonymity network.";
  }
  if (m.status === "unavailable") {
    return "Suite mesh: off (unavailable). QNM-BUILD-1.0. Not an anonymity network.";
  }
  return "Suite mesh: off (default). QNM-BUILD-1.0. Not an anonymity network.";
}

/** Public Live Nodes count. Never auto-heal a visiting floor. */
export function alignLiveNodes({ mesh } = {}) {
  if (mesh && mesh.enabled) return meshRollup(mesh).live;
  return 0;
}

export function meshPointer() {
  return {
    pointer: true,
    path: MESH_PATH,
    enabled_default: false,
    spec: QNM_SPEC,
    kernel: MESH_KERNEL,
    rollup: "live|locked|isolated",
    node_gate: false,
    auto_heal: false,
    anonymity_network: false,
    author: MESH_IDENTITY,
    identity: MESH_IDENTITY,
    catalog_mcp: FRAGGATE_MCP,
    fraggate_slug: MESH_SLUG,
    origin: RUNTIME + MESH_PATH,
    note: "PROXY to aziel-runtime /v1/mesh/* via AZIEL_RUNTIME. Not a local op. Not AnonBroadcast. Not AZMail's product-local ring. VeilLock remains consent-gated camera protection via AZ-OS. Full node process is local qnm-node/. " + MESH_NOTE,
    anon_broadcast: ANON_BROADCAST,
    anon_broadcast_publish_path: false,
  };
}

export function meshOpenApiPaths() {
  const paths = {};
  for (const route of MESH_PROXY_ROUTES) {
    const entry = paths[route.path] || {};
    for (const method of route.methods) {
      entry[method] = {
        operationId: "veillock_mesh_" + route.op + (method === "head" ? "_head" : "") + "_proxy",
        summary: route.summary,
        tags: ["mesh"],
        responses: { "200": { description: "aziel-runtime mesh envelope" } },
      };
      if (method === "post") {
        entry[method].requestBody = { content: { "application/json": { schema: { type: "object" } } } };
      }
    }
    paths[route.path] = entry;
  }
  return paths;
}

export function normalizeMeshPath(pathname) {
  const raw = String(pathname == null ? "" : pathname);
  const noQuery = raw.split("?")[0];
  const path = noQuery.replace(/\/+$/, "") || "/";
  return path.startsWith("/") ? path : `/${path}`;
}

export function isMeshPath(pathname) {
  const path = normalizeMeshPath(pathname);
  return path === "/v1/mesh" || path.startsWith("/v1/mesh/");
}

export function runtimeOrigin(env) {
  const fromEnv = env && (env.AZIEL_RUNTIME_ORIGIN || env.RUNTIME_ORIGIN);
  if (typeof fromEnv === "string" && /^https:\/\//i.test(fromEnv)) {
    return fromEnv.replace(/\/+$/, "");
  }
  return RUNTIME;
}

function runtimeService(env) {
  const bind = env && env.AZIEL_RUNTIME;
  if (bind && typeof bind === "object" && typeof bind.fetch === "function") return bind;
  return null;
}

function joinOriginUrl(base, pathAndQuery) {
  const origin = String(base || RUNTIME).replace(/\/+$/, "");
  const raw = String(pathAndQuery == null ? "" : pathAndQuery);
  const qIndex = raw.indexOf("?");
  const pathOnly = qIndex >= 0 ? raw.slice(0, qIndex) : raw;
  const query = qIndex >= 0 ? raw.slice(qIndex) : "";
  let path = pathOnly.startsWith("/") ? pathOnly : `/${pathOnly}`;
  path = path.replace(/\/{2,}/g, "/");
  if (!path || path === "/") path = "/";
  return origin + path + query;
}

function meshJson(body, status = 200) {
  return new Response(JSON.stringify(body, null, 2), {
    status,
    headers: {
      "Content-Type": "application/json; charset=utf-8",
      "Cache-Control": "private, no-store",
      ...meshCorsHeaders(),
    },
  });
}

function meshErrFields({ message, door_url, http_status, content_type, via, extra }) {
  return {
    ok: false,
    code: "MESH-ERR",
    door: "mesh",
    kernel: "mesh",
    spec: QNM_SPEC,
    author: MESH_IDENTITY,
    identity: MESH_IDENTITY,
    node_gate: false,
    auto_heal: false,
    anonymity_network: false,
    enabled: false,
    default_off: true,
    message,
    door_url: door_url || "",
    http_status: http_status == null ? null : http_status,
    content_type: content_type || "",
    via: via || "",
    ...(extra || {}),
  };
}

async function originFetch(env, pathAndQuery, init, request) {
  const headers = new Headers((init && init.headers) || {});
  if (!headers.has("User-Agent") && !headers.has("user-agent")) headers.set("User-Agent", "Mozilla/5.0");
  if (!headers.has("Accept") && !headers.has("accept")) headers.set("Accept", "application/json");
  headers.set("X-Aziel-Runtime-Via", "veillock-download-tracker");
  const next = { ...(init || {}), headers };
  if (!next.signal && typeof AbortSignal !== "undefined" && typeof AbortSignal.timeout === "function") {
    next.signal = AbortSignal.timeout(20000);
  }

  const raw = String(pathAndQuery == null ? "" : pathAndQuery);
  const path = raw.startsWith("/") ? raw : `/${raw}`;
  const door_url = joinOriginUrl(runtimeOrigin(env), path);
  const bind = runtimeService(env);
  if (bind) {
    const res = await bind.fetch(new Request(SERVICE_BINDING_ORIGIN + path, next));
    return { res, via: "service-binding", door_url };
  }

  try {
    if (request && request.url) {
      const here = new URL(request.url).origin;
      const there = new URL(door_url).origin;
      if (here && here === there) {
        throw new Error("Mesh URL points at this Worker — refusing self-fetch loop.");
      }
    }
  } catch (err) {
    if (String(err && err.message || "").includes("self-fetch")) throw err;
  }
  const res = await fetch(door_url, next);
  return { res, via: "http", door_url };
}

/**
 * PROXY one allowlisted /v1/mesh/* path to aziel-runtime.
 * Not a local op. GET never enables. Default radios OFF.
 */
export async function runMeshProxy(env, request, pathAndQuery) {
  const pathOnly = normalizeMeshPath(pathAndQuery);
  const allowed = MESH_ROUTE_METHODS[pathOnly];
  if (!allowed) {
    return {
      status: 404,
      data: meshErrFields({
        message: "Unknown mesh path. Use GET /v1/mesh /status /nodes or POST /enable /disable /join /heartbeat /leave /broadcast.",
        extra: { code: "MESH-UNKNOWN", path: pathOnly },
      }),
    };
  }
  const method = String((request && request.method) || "GET").toUpperCase();
  if (!allowed.includes(method)) {
    return {
      status: 405,
      data: meshErrFields({
        message: "Method not allowed on " + pathOnly + ".",
        extra: { code: "MESH-METHOD", path: pathOnly, method },
      }),
    };
  }

  let search = "";
  try {
    if (pathAndQuery && String(pathAndQuery).includes("?")) {
      search = "?" + String(pathAndQuery).split("?").slice(1).join("?");
    } else if (request && request.url) {
      search = new URL(request.url).search || "";
    }
  } catch {
    search = "";
  }
  const path = pathOnly + search;

  let body;
  if (method === "POST") {
    try {
      body = await request.json();
    } catch {
      body = {};
    }
  }

  const headers = {
    Accept: "application/json",
    "User-Agent": "Mozilla/5.0",
  };
  if (body !== undefined) headers["Content-Type"] = "application/json";
  if (request && request.headers) {
    const token = request.headers.get("Authorization") || request.headers.get("X-Aziel-Runtime-Token");
    if (token) {
      headers.Authorization = token.startsWith("Bearer ") || token.startsWith("bearer ") ? token : `Bearer ${token}`;
      headers["X-Aziel-Runtime-Token"] = token.replace(/^Bearer\s+/i, "");
    }
  }

  const door_url = joinOriginUrl(runtimeOrigin(env), path);
  let fetched;
  try {
    fetched = await originFetch(
      env,
      path,
      {
        method,
        headers,
        body: body !== undefined ? JSON.stringify(body) : undefined,
      },
      request,
    );
  } catch (err) {
    return {
      status: 502,
      data: meshErrFields({
        message: "Mesh door fetch failed.",
        door_url,
        http_status: null,
        content_type: "",
        via: runtimeService(env) ? "service-binding" : "http",
        extra: { detail: String(err && err.message ? err.message : err) },
      }),
    };
  }

  const res = fetched.res;
  const via = fetched.via;
  const len = Number(res.headers.get("Content-Length") || "0");
  if (Number.isFinite(len) && len > 2 * 1024 * 1024) {
    return {
      status: 502,
      data: meshErrFields({
        message: "Mesh response too large for this Worker proxy.",
        door_url: fetched.door_url || door_url,
        http_status: res.status,
        content_type: res.headers.get("Content-Type") || "",
        via,
      }),
    };
  }

  if (method === "HEAD") {
    return { status: res.status, data: { ok: res.ok, code: res.ok ? "MESH-OK" : "MESH-ERR", door: "mesh", via, enabled: false } };
  }

  const text = await res.text();
  let data;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = null;
  }
  if (!data || typeof data !== "object") {
    const preview = String(text || "").replace(/\s+/g, " ").slice(0, 160);
    return {
      status: res.status || 502,
      data: meshErrFields({
        message: "Mesh door returned non-JSON.",
        door_url: fetched.door_url || door_url,
        http_status: res.status,
        content_type: res.headers.get("Content-Type") || "",
        via,
        extra: { preview },
      }),
    };
  }
  return { status: res.status, data };
}

/**
 * Worker fetch entry for /v1/mesh and /v1/mesh/*.
 * Returns null when the path is not a mesh door path.
 */
export async function handleMeshApi(request, url, env) {
  if (!isMeshPath(url.pathname)) return null;
  const result = await runMeshProxy(env, request, url.pathname + (url.search || ""));
  return meshJson(result.data, result.status);
}
