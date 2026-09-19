/**
 * Offline human/bot classify + /stats remainder invariant.
 * Author: Aziel Eliab. Apache-2.0.
 */
import assert from "node:assert/strict";
import {
  BOT_SCORE_THRESHOLD,
  METHOD_UA_ONLY,
  METHOD_WITH_BOT_MANAGEMENT,
  classifyRequest,
  readBotManagement,
} from "../src/classify.js";
import {
  CLASSIFICATION_LEGACY,
  LEGACY_STRATEGY,
  isolatedKeys,
  invariantHolds,
  shapeCountBody,
  shapeHumanBotFields,
} from "../src/stats-shape.js";
import worker from "../src/index.js";

assert.equal(BOT_SCORE_THRESHOLD, 30);
assert.equal(LEGACY_STRATEGY, "b");
assert.match(CLASSIFICATION_LEGACY, /display remainder/);

function fakeRequest({ ua = "Mozilla/5.0", cf } = {}) {
  return {
    headers: {
      get(name) {
        if (String(name).toLowerCase() === "user-agent") return ua;
        return null;
      },
    },
    cf,
  };
}

assert.equal(classifyRequest(fakeRequest({ ua: "CF-Healthchecks" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "CF-Healthchecks" })).reason, "healthcheck_ua");
assert.equal(classifyRequest(fakeRequest({ ua: "Mozilla/5.0 (compatible; Googlebot/2.1)" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "Mozilla/5.0 (compatible; bingbot/2.0)" })).reason, "ua_denylist");
assert.equal(classifyRequest(fakeRequest({ ua: "GPTBot" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "ClaudeBot" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "Bytespider" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "PetalBot" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "Mozilla/5.0 (compatible; YandexBot/3.0)" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "SemrushBot" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "AhrefsBot" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "Mozilla/5.0 (compatible; DotBot/1.2)" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "curl/8.5.0" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "Wget/1.21" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "python-requests/2.31.0" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "" })).bucket, "bot");
assert.equal(classifyRequest(fakeRequest({ ua: "" })).reason, "empty_ua");
assert.equal(classifyRequest(null).bucket, "bot");

const noBm = classifyRequest(fakeRequest({ ua: "Mozilla/5.0" }));
assert.equal(noBm.bucket, "human");
assert.equal(noBm.method, METHOD_UA_ONLY);
assert.equal(noBm.score, null);
assert.equal(readBotManagement(fakeRequest({})).available, false);

const verified = classifyRequest(fakeRequest({
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 99, verifiedBot: true } },
}));
assert.equal(verified.bucket, "bot");
assert.equal(verified.reason, "verified_bot");
assert.equal(verified.method, METHOD_WITH_BOT_MANAGEMENT);

const lowScore = classifyRequest(fakeRequest({
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 30, verifiedBot: false } },
}));
assert.equal(lowScore.bucket, "bot");
assert.equal(lowScore.reason, "bot_score");

const scoreZero = classifyRequest(fakeRequest({
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 0, verifiedBot: false } },
}));
assert.equal(scoreZero.bucket, "human");
assert.equal(scoreZero.score, null);
assert.equal(scoreZero.method, METHOD_WITH_BOT_MANAGEMENT);

const likelyHuman = classifyRequest(fakeRequest({
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 95, verifiedBot: false } },
}));
assert.equal(likelyHuman.bucket, "human");

const legacy = shapeHumanBotFields({
  views: 11,
  downloads: 10,
  views_human: 0,
  downloads_human: 0,
  botManagementAvailable: false,
});
assert.equal(legacy.views_human, 0);
assert.equal(legacy.views_bot, 11);
assert.equal(legacy.downloads_human, 0);
assert.equal(legacy.downloads_bot, 10);
assert.deepEqual(legacy.human, { views: 0, downloads: 0 });
assert.deepEqual(legacy.bot, { views: 11, downloads: 10 });
assert.equal(legacy.classification.method, METHOD_UA_ONLY);
assert.equal(legacy.classification.bot_score_threshold, 30);
assert.match(legacy.classification.note, /Display strategy \(b\)/);
assert.equal(
  invariantHolds({ views: 11, downloads: 10, ...legacy }),
  true,
);

const afterHuman = shapeHumanBotFields({
  views: 12,
  downloads: 11,
  views_human: 1,
  downloads_human: 1,
  botManagementAvailable: true,
});
assert.equal(afterHuman.views_human, 1);
assert.equal(afterHuman.views_bot, 11);
assert.equal(afterHuman.downloads_human, 1);
assert.equal(afterHuman.downloads_bot, 10);
assert.equal(afterHuman.classification.method, METHOD_WITH_BOT_MANAGEMENT);
assert.equal(
  invariantHolds({ views: 12, downloads: 11, ...afterHuman }),
  true,
);

const capped = shapeHumanBotFields({
  views: 5,
  downloads: 5,
  views_human: 99,
  downloads_human: 99,
});
assert.equal(capped.views_human, 5);
assert.equal(capped.views_bot, 0);
assert.equal(capped.downloads_human, 5);
assert.equal(capped.downloads_bot, 0);

const keys = isolatedKeys("whitestone");
assert.equal(keys.views, "whitestone|__views__");
assert.equal(keys.views_human, "whitestone|__views_human__");
assert.equal(keys.views_bot, "whitestone|__views_bot__");
assert.equal(keys.total, "whitestone|__total__");
assert.equal(keys.downloads_human, "whitestone|__downloads_human__");
assert.equal(keys.downloads_bot, "whitestone|__downloads_bot__");

const countBody = shapeCountBody({
  project: "whitestone",
  views: 11,
  downloads: 10,
  total: 10,
  views_human: 0,
  downloads_human: 0,
  botManagementAvailable: false,
});
assert.equal(countBody.project, "whitestone");
assert.equal(countBody.total, 10);
assert.equal(countBody.views, 11);
assert.equal(countBody.downloads, 10);
assert.equal(countBody.views_bot, 11);
assert.equal(invariantHolds(countBody), true);

function memoryKv(init = {}) {
  const store = { ...init };
  return {
    async get(k) {
      return Object.prototype.hasOwnProperty.call(store, k) ? store[k] : null;
    },
    async put(k, v) {
      store[k] = String(v);
    },
    async list() {
      return {
        keys: Object.keys(store).map((name) => ({ name })),
        list_complete: true,
      };
    },
    store,
  };
}

function withCf(request, cf) {
  Object.defineProperty(request, "cf", { value: cf, configurable: true });
  return request;
}

const HOST = "https://whitestone-download-tracker.vibelock.workers.dev";
const seeded = {
  "whitestone|__views__": "11",
  "whitestone|__total__": "10",
  "whitestone|AzielEliab|Whitestone|main|0": "10",
  "whitestone|__github__": JSON.stringify({
    stars: 0,
    forks: 0,
    watchers: 0,
    release_download_count: 0,
    fetched_at: Date.now(),
  }),
};

async function hit(env, path, { method = "GET", ua = "Mozilla/5.0", cf, body } = {}) {
  const url = new URL(path, HOST);
  const init = {
    method,
    headers: { "User-Agent": ua, Accept: "application/json" },
  };
  if (body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(body);
  }
  const request = withCf(new Request(url, init), cf);
  const res = await worker.fetch(request, env);
  const text = await res.text();
  let data = text;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    /* keep text */
  }
  return { status: res.status, data, store: env.DOWNLOADS.store };
}

const env = { DOWNLOADS: memoryKv({ ...seeded }) };
const stats = await hit(env, "/stats");
assert.equal(stats.status, 200);
assert.equal(stats.data.project, "whitestone");
assert.equal(stats.data.views, 11);
assert.equal(stats.data.downloads, 10);
assert.equal(stats.data.total, 10);
assert.equal(stats.data.views_human, 0);
assert.equal(stats.data.views_bot, 11);
assert.equal(stats.data.downloads_human, 0);
assert.equal(stats.data.downloads_bot, 10);
assert.deepEqual(stats.data.human, { views: 0, downloads: 0 });
assert.deepEqual(stats.data.bot, { views: 11, downloads: 10 });
assert.equal(stats.data.classification.bot_score_threshold, 30);
assert.equal(stats.data.classification.method, METHOD_UA_ONLY);
assert.equal(invariantHolds(stats.data), true);
assert.equal(env.DOWNLOADS.store["whitestone|__views__"], "11");
assert.equal(env.DOWNLOADS.store["whitestone|__total__"], "10");
assert.equal(env.DOWNLOADS.store["whitestone|__views_human__"], undefined);

const count = await hit(env, "/count");
assert.equal(count.status, 200);
assert.equal(count.data.views, 11);
assert.equal(count.data.downloads, 10);
assert.equal(count.data.total, 10);
assert.equal(count.data.views_bot, 11);
assert.equal(invariantHolds(count.data), true);

const humanEnv = { DOWNLOADS: memoryKv({ ...seeded }) };
const humanEvent = await hit(humanEnv, "/event", {
  method: "POST",
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 95, verifiedBot: false } },
  body: { owner: "AzielEliab", repo: "Whitestone", branch: "main" },
});
assert.equal(humanEvent.status, 200);
assert.equal(humanEvent.data.ok, true);
assert.equal(humanEnv.DOWNLOADS.store["whitestone|__total__"], "11");
assert.equal(humanEnv.DOWNLOADS.store["whitestone|__downloads_human__"], "1");
assert.equal(humanEnv.DOWNLOADS.store["whitestone|__downloads_bot__"], undefined);

const afterHumanStats = await hit(humanEnv, "/stats", {
  ua: "Mozilla/5.0",
  cf: { botManagement: { score: 95, verifiedBot: false } },
});
assert.equal(afterHumanStats.data.downloads, 11);
assert.equal(afterHumanStats.data.downloads_human, 1);
assert.equal(afterHumanStats.data.downloads_bot, 10);
assert.equal(afterHumanStats.data.classification.method, METHOD_WITH_BOT_MANAGEMENT);
assert.equal(invariantHolds(afterHumanStats.data), true);

const botEnv = { DOWNLOADS: memoryKv({ ...seeded }) };
const botEvent = await hit(botEnv, "/event", {
  method: "POST",
  ua: "Googlebot/2.1",
  body: { owner: "AzielEliab", repo: "Whitestone", branch: "main" },
});
assert.equal(botEvent.status, 200);
assert.equal(botEnv.DOWNLOADS.store["whitestone|__total__"], "11");
assert.equal(botEnv.DOWNLOADS.store["whitestone|__downloads_bot__"], "1");
assert.equal(botEnv.DOWNLOADS.store["whitestone|__downloads_human__"], undefined);

const botStats = await hit(botEnv, "/stats");
assert.equal(botStats.data.downloads, 11);
assert.equal(botStats.data.downloads_human, 0);
assert.equal(botStats.data.downloads_bot, 11);
assert.equal(invariantHolds(botStats.data), true);

const viewEnv = { DOWNLOADS: memoryKv({ ...seeded }) };
const viewHit = await hit(viewEnv, "/", { ua: "Mozilla/5.0" });
assert.equal(viewHit.status, 200);
assert.equal(typeof viewHit.data, "string");
assert.match(viewHit.data, /<p class="count">/);
assert.doesNotMatch(viewHit.data, /views_human/);
assert.equal(viewEnv.DOWNLOADS.store["whitestone|__views__"], "12");
assert.equal(viewEnv.DOWNLOADS.store["whitestone|__views_human__"], "1");

console.log("verify-human-bot: classify + remainder invariant + /stats /count additive fields");
