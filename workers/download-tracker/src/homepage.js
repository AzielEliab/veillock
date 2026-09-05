/**
 * VeilLock Worker homepage — complete human software surface.
 * Author: Aziel Eliab. Black / gold. Everblooming sigil.
 */

const HOST = "https://veillock-download-tracker.vibelock.workers.dev";
const GITHUB = "https://github.com/AzielEliab/veillock";
const GITHUB_LATEST = "https://github.com/AzielEliab/veillock/releases/latest";
const DEFAULT_ASSET = "veillock-0.2.0.tar.gz";
const INSTALL_LINE = "curl -fsSL https://veillock-download-tracker.vibelock.workers.dev/install.sh | bash";
const DOI = "10.5281/zenodo.21431659";
const DOI_URL = "https://doi.org/10.5281/zenodo.21431659";
const ZENODO = "https://zenodo.org/records/21431659";
const DESC =
  "VeilLock is consent-gated camera protection via AZ-OS by Aziel Eliab. Your camera and video stay veiled unless you turn obfuscation off or accept a call through AZ-OS. VeilLock does not inject into FaceTime, Zoom, Meet, Teams, or Skype.";

function esc(value) {
  return String(value == null ? "" : value)
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function ldJson() {
  return JSON.stringify({
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "VeilLock",
    alternateName: "VeilLock — Aziel Eliab",
    applicationCategory: "SecurityApplication",
    operatingSystem: "Linux, macOS, Windows",
    softwareVersion: "0.2.0",
    author: { "@type": "Person", name: "Aziel Eliab" },
    creator: { "@type": "Person", name: "Aziel Eliab" },
    codeRepository: GITHUB,
    downloadUrl: HOST + "/download?asset=" + DEFAULT_ASSET,
    license: "https://www.apache.org/licenses/LICENSE-2.0",
    url: HOST + "/",
    description: DESC,
    identifier: DOI_URL,
    offers: { "@type": "Offer", price: "0", priceCurrency: "USD" },
  });
}

export function renderHomepage({ downloads, views, breakdownHtml, github }) {
  const n = Number(downloads || 0).toLocaleString("en-US");
  const v = Number(views || 0).toLocaleString("en-US");
  const gh = github && typeof github === "object" ? github : {};
  const stars = Number(gh.stars || 0);
  const forks = Number(gh.forks || 0);
  const watchers = Number(gh.watchers || 0);
  return `<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VeilLock — Aziel Eliab</title>
<meta name="description" content="${esc(DESC)}">
<meta name="author" content="Aziel Eliab">
<meta name="robots" content="index,follow">
<link rel="canonical" href="${HOST}/">
<link rel="icon" href="/sigil.png" type="image/png">
<link rel="sitemap" type="application/xml" href="${HOST}/sitemap.xml">
<meta property="og:type" content="website">
<meta property="og:title" content="VeilLock — Aziel Eliab">
<meta property="og:description" content="${esc(DESC)}">
<meta property="og:url" content="${HOST}/">
<meta property="og:site_name" content="Aziel Eliab">
<meta property="og:image" content="${HOST}/sigil.png">
<meta name="twitter:card" content="summary">
<meta name="twitter:title" content="VeilLock — Aziel Eliab">
<meta name="twitter:description" content="${esc(DESC)}">
<meta name="twitter:image" content="${HOST}/sigil.png">
<script type="application/ld+json">${ldJson()}</script>
<style>
  :root {
    color-scheme: dark;
    --bg: #080806;
    --card: #12110c;
    --ink: #f4ecd4;
    --muted: #9a9074;
    --line: #3a3420;
    --gold: #d4af37;
    --gold-deep: #c9a227;
    --veil: #f0d78c;
    --ok: #7dcf9a;
    --halt: #e07a7a;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--ink);
    font: 16px/1.5 "Iowan Old Style", Palatino, Georgia, "Times New Roman", serif; }
  body { min-height: 100vh; }
  main { max-width: 58rem; margin: 0 auto; padding: 2.2rem 1.2rem 4.5rem; }
  .brandrow { display: flex; align-items: center; gap: 14px; margin: 0 0 0.85rem; }
  .brandmark {
    width: 52px; height: 52px; border-radius: 12px; object-fit: cover; flex: 0 0 auto;
    animation: bloom 7s ease-in-out infinite;
  }
  @keyframes bloom {
    0%, 100% { box-shadow: 0 0 0 1px #d4af3733, 0 0 10px #d4af3728; }
    50% { box-shadow: 0 0 0 1px #d4af3777, 0 0 26px #d4af3755; }
  }
  .eyebrow { margin: 0; font-size: 0.72rem; letter-spacing: 0.22em; text-transform: uppercase; color: var(--gold); }
  h1 { font-size: 2.05rem; font-weight: 500; letter-spacing: 0.03em; margin: 0.15rem 0 0.25rem; }
  .motto { color: var(--muted); font-style: italic; margin: 0; }
  .banner {
    border: 1px solid #5c4a1a; background: #1a1508; color: var(--veil);
    padding: 0.9rem 1.05rem; border-radius: 10px; margin: 1.15rem 0 1.25rem; font-size: 0.94rem;
  }
  .statusbar {
    display: flex; flex-wrap: wrap; gap: 0.55rem; margin: 0 0 1.15rem;
  }
  .chip {
    border: 1px solid var(--line); border-radius: 999px; padding: 0.22rem 0.7rem;
    font-size: 0.78rem; color: var(--muted); background: #0d0c09;
  }
  .chip.live { color: var(--ok); border-color: #2d5a3d; }
  .chip.warn { color: var(--veil); border-color: #5c4a1a; }
  .desk {
    display: grid; grid-template-columns: 1fr 1fr; gap: 0.9rem; margin: 0 0 0.9rem;
  }
  @media (max-width: 760px) { .desk { grid-template-columns: 1fr; } }
  .card {
    border: 1px solid var(--line); border-radius: 14px; padding: 1.15rem 1.2rem 1.25rem;
    background: var(--card);
  }
  .card.wide { grid-column: 1 / -1; }
  h2 { font-size: 1.08rem; font-weight: 600; margin: 0 0 0.45rem; color: var(--gold); }
  p.help { color: var(--muted); font-size: 0.92rem; margin: 0 0 0.85rem; }
  .veil-lamp {
    display: flex; align-items: center; justify-content: space-between; gap: 0.8rem;
    border: 1px solid var(--line); border-radius: 10px; padding: 0.85rem 1rem;
    background: #0c0b08; margin: 0 0 0.9rem;
  }
  .veil-lamp strong { display: block; font-size: 1.35rem; letter-spacing: 0.04em; }
  .veil-lamp span { color: var(--muted); font-size: 0.88rem; }
  .veil-lamp.on strong { color: var(--gold); }
  .veil-lamp.lifted strong { color: var(--ok); }
  label { display: block; font-size: 0.8rem; color: var(--muted); margin: 0.55rem 0 0.28rem; }
  label.inline { display: flex; align-items: center; gap: 0.5rem; color: var(--ink); margin: 0.65rem 0; }
  input[type="text"], select {
    width: 100%; background: #0c0b08; color: var(--ink); border: 1px solid var(--line);
    padding: 0.48rem 0.6rem; border-radius: 8px; font: inherit;
  }
  .row { display: flex; flex-wrap: wrap; gap: 0.5rem; margin-top: 0.75rem; }
  button, a.btn {
    font-family: inherit; cursor: pointer; border: 0; border-radius: 9px;
    padding: 0.62rem 1.05rem; font-weight: 700; text-decoration: none; display: inline-block;
    text-align: center;
  }
  button.gold, a.btn.gold { background: var(--gold-deep); color: #14110a; }
  button.ghost { background: transparent; color: var(--ink); border: 1px solid var(--line); }
  button:disabled { opacity: 0.5; cursor: wait; }
  .result {
    margin-top: 0.85rem; border: 1px dashed var(--line); border-radius: 10px;
    padding: 0.8rem 0.9rem; background: #0c0b08; min-height: 4.2rem;
  }
  .result h3 { margin: 0 0 0.25rem; font-size: 1.02rem; font-weight: 600; }
  .result p { margin: 0.25rem 0 0; color: var(--muted); font-size: 0.92rem; }
  .result.pass h3 { color: var(--ok); }
  .result.fail h3 { color: var(--halt); }
  .apps { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0 0 0.7rem; }
  .apps button[aria-pressed="true"] { background: var(--gold-deep); color: #14110a; border-color: var(--gold-deep); }
  .steps { margin: 0; padding-left: 1.15rem; color: var(--ink); }
  .steps li { margin: 0.28rem 0; }
  canvas.preview {
    width: 100%; max-width: 36rem; height: auto; aspect-ratio: 16 / 9;
    background: #000; border: 1px solid var(--line); border-radius: 8px;
    image-rendering: pixelated; display: block;
  }
  .nums { display: grid; grid-template-columns: 1fr 1fr; gap: 0.8rem; margin: 0 0 1rem; }
  .count { font-size: 2.15rem; font-variant-numeric: tabular-nums; font-weight: 700; margin: 0; }
  .count span { display: block; font-size: 0.92rem; font-weight: 500; color: var(--muted); }
  .btns { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; margin: 0 0 0.85rem; }
  @media (max-width: 520px) { .btns { grid-template-columns: 1fr; } }
  a.btn.primary, button.btn.install {
    display: block; width: 100%; box-sizing: border-box; font-size: 1.15rem; padding: 1rem 1.1rem;
  }
  a.btn.primary { background: var(--ink); color: #0e1014; }
  button.btn.install { background: var(--gold-deep); color: #14110a; }
  button.btn.install.copied { background: var(--ok); color: #0e1014; }
  pre { background: #0c0b08; padding: 0.75rem 0.9rem; overflow: auto; border-radius: 8px; font-size: 0.82rem; border: 1px solid var(--line); }
  .meta { margin-top: 1rem; color: var(--muted); font-size: 0.92rem; }
  .meta a, .cite a { color: #e6d48a; }
  .iso { margin-top: 0.75rem; font-size: 0.84rem; color: #7a7258; }
  .cite { margin-top: 1.3rem; padding-top: 1rem; border-top: 1px solid var(--line); }
  .cite h2 { font-size: 1.05rem; }
  footer { margin-top: 1.6rem; color: #6d6584; font-size: 0.8rem; }
  ul.break { color: var(--muted); font-size: 0.9rem; }
</style>
</head>
<body>
<main>
  <header>
    <div class="brandrow">
      <img class="brandmark" src="/sigil.png" width="52" height="52" alt="Everblooming sigil — Aziel Eliab" decoding="async">
      <div>
        <p class="eyebrow">Aziel Eliab · Apache-2.0</p>
        <h1>VeilLock</h1>
        <p class="motto">Consent-gated camera protection via AZ-OS.</p>
      </div>
    </div>
  </header>

  <p class="banner" role="note"><strong>Honest limit.</strong> VeilLock does not inject into FaceTime, Zoom, Meet, Teams, or Skype. iOS FaceTime cannot pick a third-party camera. This page is a consent desk and veil recipe — not a virtual camera and not a call interceptor. YOUR camera/screen only. You control the lift.</p>
  <div class="statusbar" id="status-bar">
    <span class="chip" id="chip-health">Checking VeilLock…</span>
    <span class="chip warn">Hosted receipt · local tether</span>
    <span class="chip">v0.2.0</span>
  </div>

  <section class="desk" aria-label="VeilLock workspace">
    <article class="card" id="consent-desk">
      <h2>Consent desk</h2>
      <p class="help">The veil stays on unless you turn obfuscation off or accept a call through AZ-OS. Hosted AZ-OS halt is a token, not killing this computer.</p>
      <div class="veil-lamp on" id="veil-lamp">
        <div>
          <strong id="veil-title">Veil on</strong>
          <span id="veil-reason">Camera and video protected.</span>
        </div>
        <span class="chip warn" id="veil-badge">AZ-OS hook</span>
      </div>
      <label class="inline"><input type="checkbox" id="obfuscation-on" checked> Obfuscation on (default)</label>
      <label for="azos-actor">Actor (you)</label>
      <input id="azos-actor" type="text" value="user" autocomplete="name">
      <div class="row">
        <button type="button" class="gold" id="azos-accept">Accept call through AZ-OS</button>
        <button type="button" class="ghost" id="azos-end">End call (re-veil)</button>
      </div>
      <div class="result" id="consent-result">
        <h3>Waiting for you</h3>
        <p>Toggle the veil, accept a call, or end it. The desk writes a consent receipt — not pixels.</p>
      </div>
    </article>

    <article class="card" id="pulse-desk">
      <h2>PulseCheck</h2>
      <p class="help">If the pulse fails, the feed stays halted as noise. Never a plaintext claim.</p>
      <div class="row">
        <button type="button" class="gold" id="pulse-live">Live pulse</button>
        <button type="button" class="ghost" id="pulse-dead">Dead pulse</button>
      </div>
      <div class="result" id="pulse-result">
        <h3>No pulse yet</h3>
        <p>Tap Live pulse for a passing sample, or Dead pulse to see halt/noise.</p>
      </div>
    </article>

    <article class="card wide" id="veil-compose">
      <h2>Compose a veil</h2>
      <p class="help">Real hosted recipe: natural camera wash, or synthetic screen panels. Spatial camera pixels are not copied.</p>
      <label for="veil-source">Source</label>
      <select id="veil-source">
        <option value="camera" selected>Your camera / video</option>
        <option value="screen">Your screen</option>
      </select>
      <label for="veil-seed">Seed (optional)</label>
      <input id="veil-seed" type="text" value="studio" autocomplete="off">
      <div class="row">
        <button type="button" class="gold" id="veil-run">Compose veil</button>
      </div>
      <p style="margin:0.85rem 0 0.45rem"><canvas class="preview" id="veil-canvas" width="640" height="360" aria-label="Veil preview"></canvas></p>
      <div class="result" id="veil-result">
        <h3>No recipe yet</h3>
        <p>Compose a veil to see a live-looking wash or synthetic UI noise.</p>
      </div>
    </article>

    <article class="card wide" id="apps-desk">
      <h2>Call apps — your device only</h2>
      <p class="help">These are local steps. VeilLock does not inject into the app. After install, the desktop tether can advertise a camera named VeilLock.</p>
      <div class="apps" id="app-picks">
        <button type="button" class="ghost" data-app="zoom" aria-pressed="false">Zoom</button>
        <button type="button" class="ghost" data-app="meet" aria-pressed="false">Meet</button>
        <button type="button" class="ghost" data-app="teams" aria-pressed="false">Teams</button>
        <button type="button" class="ghost" data-app="facetime" aria-pressed="true">FaceTime</button>
        <button type="button" class="ghost" data-app="skype" aria-pressed="false">Skype</button>
      </div>
      <div class="result" id="apps-result">
        <h3>Choose an app</h3>
        <p>FaceTime is selected so the FaceTime limit is visible first.</p>
      </div>
    </article>
  </section>

  <section class="card" id="install">
    <div class="nums">
      <p class="count">${v}<span>Views</span></p>
      <p class="count">${n}<span>Downloads</span></p>
    </div>
    <p class="help"><strong>Two big buttons.</strong> Download saves the gzip (the Downloads number goes up). One-click install copies a Terminal command. After it finishes, type <code>veillock ui</code>.</p>
    <div class="btns">
      <a class="btn primary" href="/download?asset=${DEFAULT_ASSET}">Download</a>
      <button type="button" class="btn install" id="install-btn">One-click install</button>
    </div>
    <pre id="install-cmd">${INSTALL_LINE}</pre>
    <p class="help">Then run: <code>veillock ui</code> and open http://127.0.0.1:8761 (this computer only).</p>
    <p class="meta">The download count ticks on the Download click. The Worker serves the gzip (HTTP 200). No 302 to GitHub. Forks using this same link are counted automatically. ${DEFAULT_ASSET} — ${n} counted.</p>
    <p class="iso">Isolated counter: Worker <code>veillock-download-tracker</code>, project <code>veillock</code>, KV <code>VEILLOCK_DOWNLOADS</code>. Not mixed with any other product. /v1 does not increment downloads.</p>
    <p class="meta">GitHub: stars ${stars} · forks ${forks} · watchers ${watchers}</p>
    <p class="meta">Paper: <a href="${DOI_URL}">doi:${DOI}</a> · <a href="${ZENODO}">Zenodo</a> · Apache-2.0 · Eliab, Aziel</p>
    <p class="meta"><a href="/stats">JSON stats</a> · <a href="/openapi.json">OpenAPI</a> · <a href="/v1/skill">Skill</a> · <a href="/ai">AI runtime</a> · <a href="${GITHUB}">GitHub</a> · <a href="${GITHUB_LATEST}">releases</a> · <a href="/cite.json">cite.json</a></p>
    <h2>Per repo / branch / fork</h2>
    <ul class="break">${breakdownHtml}</ul>
  </section>

  <section class="cite" id="cite">
    <h2>How to cite</h2>
    <p>Aziel Eliab. VeilLock. ${GITHUB}. ${HOST}. ${DOI_URL}.</p>
    <p><a href="https://aziel-runtime.vibelock.workers.dev/">Catalog</a> · <a href="${GITHUB}">GitHub</a> · <a href="${HOST}/download">Download</a> · <a href="${HOST}/cite.json">cite.json</a></p>
    <p class="iso">Identity is Aziel Eliab only. Forks are welcome and always allowed. Apache-2.0.</p>
  </section>
  <footer>VeilLock 0.2.0 · you control the veil · not a FaceTime inject · Aziel Eliab</footer>
</main>
<script>
(function () {
  var installCmd = ${JSON.stringify(INSTALL_LINE)};
  var btn = document.getElementById("install-btn");
  var pre = document.getElementById("install-cmd");
  if (btn) {
    btn.addEventListener("click", function () {
      function done(ok) {
        btn.textContent = ok ? "Copied! Paste in Terminal, then run veillock ui" : "Select the command, copy it, then run veillock ui";
        btn.classList.add("copied");
      }
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(installCmd).then(function () { done(true); }).catch(function () { done(false); });
      } else {
        done(false);
        if (pre && window.getSelection) {
          var r = document.createRange();
          r.selectNodeContents(pre);
          var sel = window.getSelection();
          sel.removeAllRanges();
          sel.addRange(r);
        }
      }
    });
  }

  function el(id) { return document.getElementById(id); }
  function setHtml(node, html) { if (node) node.innerHTML = html; }
  function headers() { return { "content-type": "application/json", "accept": "application/json" }; }
  function post(path, body) {
    return fetch(path, { method: "POST", headers: headers(), body: JSON.stringify(body || {}) })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); });
  }
  function get(path) {
    return fetch(path, { headers: { accept: "application/json" } })
      .then(function (res) { return res.json().then(function (data) { return { ok: res.ok, data: data }; }); });
  }
  function showResult(id, kind, title, summary) {
    var box = el(id);
    if (!box) return;
    box.className = "result" + (kind ? " " + kind : "");
    setHtml(box, "<h3>" + title + "</h3><p>" + summary + "</p>");
  }
  function paintLamp(decision) {
    var lamp = el("veil-lamp");
    var on = decision && decision.veil === "on";
    lamp.className = "veil-lamp " + (on ? "on" : "lifted");
    el("veil-title").textContent = on ? "Veil on" : "Veil lifted";
    el("veil-reason").textContent = decision.reason || (on ? "Camera and video protected." : "You lifted the veil.");
    el("veil-badge").textContent = decision.call_accepted ? "Call accepted" : "AZ-OS hook";
  }
  function consentCopy(data) {
    if (!data || !data.ok) return "The desk could not write a receipt.";
    if (data.veil === "on") return "Camera and video stay protected. Hosted receipt only — not a virtual camera.";
    if (data.reason && data.reason.indexOf("obfuscation") !== -1) return "You turned obfuscation off. The veil is lifted because you said so.";
    return "You accepted a call through AZ-OS. The veil is lifted for this session.";
  }

  get("/v1/health").then(function (out) {
    var chip = el("chip-health");
    if (!chip) return;
    if (out.ok && out.data && out.data.ok) {
      chip.textContent = "VeilLock live · AZ-OS hook present";
      chip.className = "chip live";
    } else {
      chip.textContent = "VeilLock health unavailable";
      chip.className = "chip warn";
    }
  }).catch(function () {
    var chip = el("chip-health");
    if (chip) { chip.textContent = "VeilLock health unavailable"; chip.className = "chip warn"; }
  });

  function runConsent(body, title) {
    post("/v1/consent", body).then(function (out) {
      var data = out.data || {};
      paintLamp(data);
      showResult("consent-result", data.veil === "on" ? "pass" : "", title, consentCopy(data));
    }).catch(function () {
      showResult("consent-result", "fail", "Receipt failed", "The consent desk could not reach VeilLock.");
    });
  }

  el("obfuscation-on").addEventListener("change", function () {
    runConsent({
      obfuscation_on: el("obfuscation-on").checked,
      call_accepted: false,
      actor: el("azos-actor").value || "user"
    }, el("obfuscation-on").checked ? "Default veil restored" : "You turned obfuscation off");
  });
  el("azos-accept").addEventListener("click", function () {
    var actor = el("azos-actor").value || "user";
    post("/v1/call-accept", { actor: actor }).then(function (out) {
      var data = out.data || {};
      el("obfuscation-on").checked = true;
      paintLamp(data);
      showResult("consent-result", "", "Call accepted", consentCopy(data));
    }).catch(function () {
      showResult("consent-result", "fail", "Accept failed", "The consent desk could not reach VeilLock.");
    });
  });
  el("azos-end").addEventListener("click", function () {
    el("obfuscation-on").checked = true;
    runConsent({ obfuscation_on: true, call_accepted: false, actor: el("azos-actor").value || "user" }, "Call ended · re-veiled");
  });

  function runPulse(values, label) {
    post("/v1/pulse", { values: values }).then(function (out) {
      var data = out.data || {};
      if (data.pci === "PASS") {
        showResult("pulse-result", "pass", "Pulse PASS — " + label, "The public feed stays a veil (obfuscation), not plaintext. Pulse is alive.");
      } else {
        showResult("pulse-result", "fail", "Pulse FAIL — halt / noise", "Generation halted. Noise only — never plaintext. " + (data.reason || "dead pulse") + ".");
      }
    }).catch(function () {
      showResult("pulse-result", "fail", "Pulse unreachable", "The desk could not reach PulseCheck.");
    });
  }
  el("pulse-live").addEventListener("click", function () { runPulse([0.2, 0.3, 0.25], "live sample"); });
  el("pulse-dead").addEventListener("click", function () { runPulse([0, 0, 0], "all zeros"); });

  function clamp(n) { return n < 0 ? 0 : n > 255 ? 255 : n; }
  function paintRecipe(recipe) {
    var canvas = el("veil-canvas");
    if (!canvas || !recipe) return;
    var ctx = canvas.getContext("2d");
    var w = canvas.width, h = canvas.height;
    var srcW = Number(recipe.width) || w;
    var srcH = Number(recipe.height) || h;
    if (recipe.pipeline === "synthetic_ui_noise") {
      var bg = recipe.background || [24, 24, 24];
      ctx.fillStyle = "rgb(" + bg[0] + "," + bg[1] + "," + bg[2] + ")";
      ctx.fillRect(0, 0, w, h);
      var rects = recipe.rectangles || [];
      for (var i = 0; i < rects.length; i++) {
        var r = rects[i];
        var x = (r.x1 / srcW) * w, y = (r.y1 / srcH) * h;
        var rw = ((r.x2 - r.x1) / srcW) * w, rh = ((r.y2 - r.y1) / srcH) * h;
        var c = r.color || [120, 120, 120];
        ctx.fillStyle = "rgb(" + c[0] + "," + c[1] + "," + c[2] + ")";
        ctx.fillRect(x, y, rw, rh);
        if (r.title_bar) {
          var tb = r.title_bar;
          var bc = tb.color || [60, 60, 60];
          ctx.fillStyle = "rgb(" + bc[0] + "," + bc[1] + "," + bc[2] + ")";
          ctx.fillRect((tb.x1 / srcW) * w, (tb.y1 / srcH) * h, ((tb.x2 - tb.x1) / srcW) * w, ((tb.y2 - tb.y1) / srcH) * h);
        }
      }
      return;
    }
    var wash = recipe.wash || [80, 70, 110];
    ctx.fillStyle = "rgb(" + wash[0] + "," + wash[1] + "," + wash[2] + ")";
    ctx.fillRect(0, 0, w, h);
    var img = ctx.getImageData(0, 0, w, h);
    var grain = Number(recipe.grain || 0.4);
    for (var p = 0; p < img.data.length; p += 4) {
      var n = (Math.random() - 0.5) * grain * 90;
      img.data[p] = clamp(img.data[p] + n);
      img.data[p + 1] = clamp(img.data[p + 1] + n * 0.85);
      img.data[p + 2] = clamp(img.data[p + 2] + n * 1.1);
    }
    ctx.putImageData(img, 0, 0);
  }
  el("veil-run").addEventListener("click", function () {
    var source = el("veil-source").value;
    var seed = el("veil-seed").value || "studio";
    post("/v1/obfuscate-preview", { source: source, seed: seed, width: 640, height: 360 }).then(function (out) {
      var data = out.data || {};
      paintRecipe(data);
      var title = data.pipeline === "synthetic_ui_noise" ? "Synthetic screen veil" : "Natural camera veil";
      showResult("veil-result", "pass", title, data.description || "Recipe ready. Not plaintext.");
    }).catch(function () {
      showResult("veil-result", "fail", "Recipe failed", "The desk could not compose a veil.");
    });
  });

  function renderApps(data, app) {
    var pack = data && data.apps ? data.apps : [];
    var chosen = pack[0] || null;
    if (app) {
      for (var i = 0; i < pack.length; i++) {
        if (pack[i].app === app) { chosen = pack[i]; break; }
      }
    }
    if (!chosen) {
      showResult("apps-result", "fail", "No steps", data && data.note ? data.note : "No local-app steps.");
      return;
    }
    var title = chosen.app === "facetime" ? "FaceTime — no inject" : chosen.app + " — your device only";
    var items = (chosen.steps || []).map(function (s) { return "<li>" + s + "</li>"; }).join("");
    var note = data.note || data.limitation || "";
    el("apps-result").className = "result";
    setHtml(el("apps-result"), "<h3>" + title + "</h3><ol class=\\"steps\\">" + items + "</ol><p>" + note + "</p>");
  }
  function loadApps(app) {
    var buttons = document.querySelectorAll("#app-picks button");
    for (var i = 0; i < buttons.length; i++) {
      buttons[i].setAttribute("aria-pressed", buttons[i].getAttribute("data-app") === app ? "true" : "false");
    }
    post("/v1/apps", { app: app }).then(function (out) {
      renderApps(out.data || {}, app);
    }).catch(function () {
      showResult("apps-result", "fail", "Steps unavailable", "The desk could not load local-app steps.");
    });
  }
  document.getElementById("app-picks").addEventListener("click", function (ev) {
    var t = ev.target;
    if (!t || !t.getAttribute) return;
    var app = t.getAttribute("data-app");
    if (app) loadApps(app);
  });
  loadApps("facetime");
})();
</script>
</body>
</html>`;
}
