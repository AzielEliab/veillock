"""Suite mesh Live Nodes + QNM-BUILD-1.0 contract.

Default OFF. live|locked|isolated. No Node Gate. No auto-heal. Not anonymity.
"""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MESH = (ROOT / "workers/download-tracker/src/mesh.js").read_text(encoding="utf-8")
RUNTIME = (ROOT / "workers/download-tracker/src/runtime.js").read_text(encoding="utf-8")
INDEX = (ROOT / "workers/download-tracker/src/index.js").read_text(encoding="utf-8")
HOMEPAGE = (ROOT / "workers/download-tracker/src/homepage.js").read_text(encoding="utf-8")
WRANGLER = (ROOT / "workers/download-tracker/wrangler.toml").read_text(encoding="utf-8")
README = (ROOT / "README.md").read_text(encoding="utf-8")
SKILL = (ROOT / "SKILL.md").read_text(encoding="utf-8")
WORKER_README = (ROOT / "workers/download-tracker/README.md").read_text(encoding="utf-8")


def test_mesh_contract_default_off_qnm_law() -> None:
    assert 'QNM_SPEC = "QNM-BUILD-1.0"' in MESH
    assert "MESH_DEFAULT_OFF = true" in MESH
    assert "MESH_ANONYMITY_NETWORK = false" in MESH
    assert "MESH_NODE_GATE = false" in MESH
    assert "MESH_AUTO_HEAL = false" in MESH
    assert "MESH_IDENTITY = IDENTITY" in MESH or '"Aziel Eliab"' in MESH
    assert 'MESH_PRODUCT = "veillock"' in MESH
    assert 'MESH_PATH = "/v1/mesh"' in MESH
    assert "live|locked|isolated" in MESH
    assert "enabled_default: false" in MESH
    assert "anon_broadcast_publish_path: false" in MESH
    assert "Aziel Eliab" in MESH
    assert "code: extra.code || \"MESH-OK\"" in MESH or '"MESH-OK"' in MESH
    assert 'QNS_CD_SPEC = "QNS-CD-1.0"' in MESH
    assert "export const QNS_CD" in MESH
    assert "photon QNS1 packet transfer" in MESH
    assert "github.com/AzielEliab/qnm-node" in MESH
    assert "github.com/AzielEliab/aziel-runtime" in MESH
    assert "softwares_tab: false" in MESH
    assert "public_qnsd_proxy: false" in MESH
    assert "QNS-CD-1.0" in MESH
    assert "No public qnsd proxy" in MESH or "no public qnsd proxy" in MESH.lower()
    assert "/v1/qnsd" not in MESH


def test_mesh_pointer_and_openapi_helpers() -> None:
    assert "export function meshPointer" in MESH
    assert "export function meshOpenApiPaths" in MESH
    assert "export function parseMeshDoc" in MESH
    assert "export function emptyMesh" in MESH
    assert "export function alignLiveNodes" in MESH
    assert "export function attachQnsCd" in MESH
    assert "fraggate_slug: MESH_SLUG" in MESH
    assert "veillock_mesh_" in MESH


def test_mesh_proxies_via_aziel_runtime() -> None:
    assert "MESH_ROUTE_METHODS" in MESH
    assert "isMeshPath" in MESH
    assert "runMeshProxy" in MESH
    assert "handleMeshApi" in MESH
    assert "originFetch" in MESH
    assert '"/v1/mesh"' in MESH
    assert 'startsWith("/v1/mesh/")' in MESH
    assert "AZIEL_RUNTIME" in MESH
    assert "AZIEL_RUNTIME" in WRANGLER
    assert "aziel-runtime" in WRANGLER
    assert "/v1/mesh" in WRANGLER
    assert 'id = "47a25aa1221e4b5fa3bb83618210c760"' in WRANGLER


def test_index_routes_mesh_before_runtime_catchall() -> None:
    assert 'from "./mesh.js"' in INDEX
    assert "handleMeshApi" in INDEX
    mesh_idx = INDEX.index("handleMeshApi(request, url, env)")
    runtime_idx = INDEX.index("handleRuntime(request, url, env)")
    assert mesh_idx < runtime_idx
    not_found = INDEX.rindex('return json({ error: "not found" }, 404)')
    assert mesh_idx < not_found


def test_runtime_advertises_mesh_proxy_and_pointer() -> None:
    assert 'from "./mesh.js"' in RUNTIME
    assert "meshPointer" in RUNTIME
    assert "meshOpenApiPaths" in RUNTIME
    assert "...meshOpenApiPaths()" in RUNTIME
    assert "mesh: meshPointer()" in RUNTIME
    assert "/v1/mesh" in RUNTIME
    assert "QNM-BUILD-1.0" in RUNTIME
    assert "No Node Gate" in RUNTIME
    assert 'path === "/v1/mesh"' in RUNTIME or 'path.startsWith("/v1/mesh/")' in RUNTIME


def test_home_live_nodes_strip_no_node_gate() -> None:
    assert 'id="meshStrip"' in HOMEPAGE
    assert 'id="meshLiveCount"' in HOMEPAGE
    assert 'id="meshLine"' in HOMEPAGE
    assert "Live Nodes" in HOMEPAGE
    assert "QNM-BUILD-1.0" in HOMEPAGE
    assert "QNS-CD-1.0" in HOMEPAGE
    assert "no public qnsd proxy" in HOMEPAGE
    assert "No Node Gate" in HOMEPAGE
    assert "No auto-heal" in HOMEPAGE
    assert "Not an anonymity network" in HOMEPAGE
    assert "/v1/mesh" in HOMEPAGE
    assert 'product: "veillock"' in HOMEPAGE
    assert 'id="node-gate"' not in HOMEPAGE
    assert 'href="/node-gate"' not in HOMEPAGE
    assert "auto-heal this node" not in HOMEPAGE
    assert "veillock_mesh_node" in HOMEPAGE


def test_docs_advertise_mesh_proxy() -> None:
    assert "/v1/mesh" in README
    assert "/v1/mesh" in SKILL
    assert "QNS-CD-1.0" in README
    assert "QNS-CD-1.0" in SKILL
    assert "QNM-BUILD-1.0" in WORKER_README
    assert "QNS-CD-1.0" in WORKER_README
    assert "AZIEL_RUNTIME" in WORKER_README
    assert "Live Nodes" in WORKER_README
    assert "MESH-OK" in WORKER_README
    assert "enabled: false" in WORKER_README
    assert "Aziel Eliab" in MESH
    assert "QNS-CD-1.0" in RUNTIME
    assert "attachQnsCd" in MESH
    assert "qns_cd_spec" in MESH
