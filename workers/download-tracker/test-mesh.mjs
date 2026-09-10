import { handleMeshApi } from "./src/mesh.js";

function assert(cond, label) {
  if (!cond) throw new Error(label);
}

const env = { AZIEL_RUNTIME_ORIGIN: "https://aziel-runtime.vibelock.workers.dev" };

async function call(path, init = {}) {
  const req = new Request("https://example.test" + path, {
    ...init,
    headers: { "user-agent": "Mozilla/5.0", accept: "application/json", ...(init.headers || {}) },
  });
  return handleMeshApi(req, new URL(req.url), env);
}

const status = await call("/v1/mesh/status");
assert(status && status.status === 200, "GET /v1/mesh/status HTTP " + (status && status.status));
const body = await status.json();
assert(body.code === "MESH-OK", "expected MESH-OK, got " + JSON.stringify(body.code));
assert(body.enabled === false, "expected enabled:false, got " + JSON.stringify(body.enabled));

const enable = await call("/v1/mesh/enable", {
  method: "POST",
  headers: { "content-type": "application/json" },
  body: "{}",
});
const enableBody = await enable.json();
assert(
  enableBody.code === "MESH-NEED-BEARER" || enableBody.enabled === false,
  "empty enable should stay off / MESH-NEED-BEARER, got " + JSON.stringify(enableBody),
);

const unknown = await call("/v1/mesh/not-a-door");
assert(unknown.status === 404, "unknown path HTTP " + unknown.status);
const unknownBody = await unknown.json();
assert(unknownBody.code === "MESH-UNKNOWN", "expected MESH-UNKNOWN, got " + JSON.stringify(unknownBody.code));

console.log("GET /v1/mesh/status MESH-OK enabled:false");
console.log("mesh proxy smoke ok");
