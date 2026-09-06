import worker, { countBody } from "./src/index.js";

function assertEqual(actual, expected, label) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a !== e) {
    throw new Error(`${label}: expected ${e}, got ${a}`);
  }
}

const body = countBody({ project: "veillock", views: 32, downloads: 35, total: 35 });
assertEqual(Object.keys(body), ["project", "views", "downloads", "total"], "key order");
assertEqual(body, { project: "veillock", views: 32, downloads: 35, total: 35 }, "full body");

const fallback = countBody({ views: 4, total: 9 });
assertEqual(fallback, { project: "veillock", views: 4, downloads: 9, total: 9 }, "downloads from total");

const empty = countBody({});
assertEqual(empty, { project: "veillock", views: 0, downloads: 0, total: 0 }, "empty stats");

class MockKV {
  constructor(store = {}) {
    this.store = { ...store };
  }
  async get(key) {
    return Object.prototype.hasOwnProperty.call(this.store, key) ? this.store[key] : null;
  }
  async put(key, value) {
    this.store[key] = String(value);
  }
  async list() {
    return { keys: Object.keys(this.store).map((name) => ({ name })), list_complete: true };
  }
}

const origFetch = globalThis.fetch;
globalThis.fetch = async () => new Response("{}", { status: 404, headers: { "content-type": "application/json" } });
try {
  const env = {
    DOWNLOADS: new MockKV({
      "veillock|AzielEliab|veillock|main|0": "7",
      "veillock|__views__": "3",
    }),
  };
  const res = await worker.fetch(new Request("https://example.test/count"), env);
  if (res.status !== 200) throw new Error("GET /count status " + res.status);
  const json = await res.json();
  assertEqual(json, { project: "veillock", views: 3, downloads: 7, total: 7 }, "worker GET /count");
} finally {
  globalThis.fetch = origFetch;
}

console.log("GET /count contract ok");
