import { handleMeshApi, QNS_CD_SPEC, QNS_CD, MESH_NOTE, MESH_DEFAULT_OFF } from "./src/mesh.js";

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
assert(QNS_CD_SPEC === "QNS-CD-1.0", "QNS_CD_SPEC");
assert(QNS_CD && QNS_CD.spec === "QNS-CD-1.0", "QNS_CD.spec");
assert(QNS_CD.softwares_tab === false, "QNS-CD softwares_tab flag");
assert(QNS_CD.public_qnsd_proxy === false, "QNS-CD public_qnsd_proxy flag");
assert(QNS_CD.node_gate === false, "QNS-CD node_gate flag");
assert(MESH_DEFAULT_OFF === true, "mesh stays default OFF");
assert(String(MESH_NOTE).includes("QNS-CD-1.0"), "MESH_NOTE must cite QNS-CD-1.0");
assert(body.qns_cd_spec === "QNS-CD-1.0", "status payload qns_cd_spec");
assert(body.qns_cd && body.qns_cd.spec === "QNS-CD-1.0", "status payload qns_cd");
assert(body.qns_cd.public_qnsd_proxy === false, "status payload public_qnsd_proxy flag");

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

const nodes = await call("/v1/mesh/nodes");
assert(nodes && nodes.status === 200, "GET /v1/mesh/nodes HTTP " + (nodes && nodes.status));
const nodesBody = await nodes.json();
assert(nodesBody.qns_cd_spec === "QNS-CD-1.0", "nodes payload qns_cd_spec");
assert(nodesBody.qns_cd && nodesBody.qns_cd.spec === "QNS-CD-1.0", "nodes payload qns_cd");
assert(nodesBody.qns_cd.implemented_here === false, "qnsd is not implemented on this Worker");

const unknown = await call("/v1/mesh/not-a-door");
assert(unknown.status === 404, "unknown path HTTP " + unknown.status);
const unknownBody = await unknown.json();
assert(unknownBody.code === "MESH-UNKNOWN", "expected MESH-UNKNOWN, got " + JSON.stringify(unknownBody.code));

console.log("GET /v1/mesh/status MESH-OK enabled:false");
console.log("QNS-CD-1.0 stamped on status + nodes; hub cite / Worker mesh cross-map");
console.log("mesh proxy smoke ok");
