"""Localhost UI for VeilLock. Binds 127.0.0.1. No CDN, no outbound calls."""

from __future__ import annotations

import base64
import json
import secrets
import sys
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse

import numpy as np

from veillock import __version__
from veillock.engine import VeilLockSession
from veillock.honesty import CALL_AUDIO, CALL_VIDEO, E2E, ENGULF, LOCAL_RECORDING, PLATFORM, PULSE
from veillock.modes import Mode
from veillock.tether import APPS_GUIDE, RUNTIME, TetherConfig

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8761
LOOPBACK = frozenset({"127.0.0.1", "localhost", "::1"})
MAX_BODY = 2 * 1024 * 1024

PAGE = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>VeilLock</title>
<style>
  :root {
    color-scheme: light;
    --bg: #f4f0e6;
    --bar: #fbf8f1;
    --card: #fffdf8;
    --ink: #1c1915;
    --muted: #4e483e;
    --line: #e3d9c4;
    --gold: #c9a227;
    --gold-ink: #1a1408;
    --danger: #8c2f2f;
    --shadow: 0 1px 2px rgba(28, 25, 21, 0.05);
  }
  @media (prefers-color-scheme: dark) {
    :root {
      color-scheme: dark;
      --bg: #12110e;
      --bar: #181712;
      --card: #1e1c17;
      --ink: #f6f1e6;
      --muted: #c9c0af;
      --line: #3c362b;
      --gold: #c9a227;
      --gold-ink: #1a1408;
      --danger: #f0b4b4;
      --shadow: none;
    }
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; max-width: 100%; overflow-x: hidden; }
  body {
    background: var(--bg);
    color: var(--ink);
    font-family: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    font-size: 1rem;
    line-height: 1.5;
  }
  :focus-visible {
    outline: 3px solid var(--gold);
    outline-offset: 2px;
  }
  .bar {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    padding: 0.85rem 1.25rem;
    background: var(--bar);
    border-bottom: 1px solid var(--line);
  }
  .name { font-weight: 650; letter-spacing: -0.01em; }
  .where { color: var(--muted); font-size: 0.875rem; }
  main {
    width: min(38rem, 100%);
    margin: 0 auto;
    padding: 2rem 1.25rem 3.5rem;
  }
  h1 {
    font-size: 1.75rem;
    font-weight: 650;
    letter-spacing: -0.02em;
    line-height: 1.2;
    margin: 0 0 0.5rem;
  }
  .lead { margin: 0 0 1.25rem; font-size: 1.05rem; }
  .status {
    margin: 0 0 1.25rem;
    padding: 0.85rem 1rem;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: var(--shadow);
  }
  .actions { display: flex; flex-wrap: wrap; gap: 0.65rem; }
  button, summary, select, input[type="text"] { font: inherit; }
  button {
    min-height: 2.75rem;
    padding: 0.55rem 1.05rem;
    border-radius: 10px;
    cursor: pointer;
  }
  button.primary {
    background: var(--gold);
    color: var(--gold-ink);
    border: 1px solid transparent;
    font-weight: 650;
  }
  button.ghost {
    background: transparent;
    color: var(--ink);
    border: 1px solid var(--line);
  }
  button:disabled { opacity: 0.55; cursor: not-allowed; }
  .note { color: var(--muted); margin: 0.85rem 0 0; }
  pre.out {
    white-space: pre-wrap;
    word-break: break-word;
    margin: 1rem 0 0;
    padding: 0.85rem 1rem;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.82rem;
  }
  .err { color: var(--danger); margin: 1rem 0 0; }
  details {
    margin-top: 1.75rem;
    background: var(--card);
    border: 1px solid var(--line);
    border-radius: 12px;
    box-shadow: var(--shadow);
  }
  summary {
    cursor: pointer;
    padding: 0.9rem 1rem;
    font-weight: 650;
  }
  .panel { padding: 0 1rem 1.15rem; }
  .panel h2 { font-size: 1rem; font-weight: 650; margin: 1.1rem 0 0.35rem; }
  .help { color: var(--muted); margin: 0 0 0.75rem; }
  label { display: block; margin: 0.75rem 0 0.3rem; font-size: 0.92rem; }
  label.inline { display: flex; align-items: center; gap: 0.55rem; margin-top: 0.9rem; }
  select, input[type="text"] {
    width: 100%;
    max-width: 100%;
    background: var(--bg);
    color: var(--ink);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.5rem 0.6rem;
  }
  .row { display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 0.9rem; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(9.5rem, 1fr)); gap: 0.75rem; margin-top: 0.85rem; }
  canvas {
    width: 100%;
    height: auto;
    background: #111;
    border: 1px solid var(--line);
    border-radius: 8px;
  }
  .cap { color: var(--muted); font-size: 0.82rem; margin: 0.3rem 0 0; }
  .key, .hex {
    font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    font-size: 0.78rem;
    word-break: break-all;
    background: var(--bg);
    border: 1px solid var(--line);
    border-radius: 8px;
    padding: 0.65rem 0.75rem;
  }
  footer { margin-top: 2rem; color: var(--muted); font-size: 0.85rem; }
  @media (max-width: 480px) {
    .bar { padding: 0.75rem 1rem; }
    main { padding: 1.35rem 1rem 2.5rem; }
    .actions, .row { flex-direction: column; }
    .actions button, .row button { width: 100%; }
    h1 { font-size: 1.5rem; }
  }
</style>
</head>
<body>
<header class="bar">
  <span class="name">VeilLock</span>
  <span class="where">On this computer · 127.0.0.1</span>
</header>
<main>
  <h1>Your camera</h1>
  <p class="lead">VeilLock keeps your camera veiled until you lift it.</p>
  <p class="status" id="status" role="status">Stopped. Veil on — your camera stays protected.</p>
  <div class="actions">
    <button class="primary" id="start" type="button">Start camera veil</button>
    <button class="ghost" id="doctor" type="button">Check this computer</button>
  </div>
  <p class="note">Author: Aziel Eliab</p>
  <pre class="out" id="doctor-out" hidden></pre>
  <p class="err" id="err" hidden role="alert"></p>

  <details id="advanced">
    <summary>Advanced</summary>
    <div class="panel">
      <h2>Tether</h2>
      <p class="help">Send your camera, or this screen, through VeilLock. In the call app, choose the camera named VeilLock.</p>
      <label for="tether-source">Source</label>
      <select id="tether-source">
        <option value="camera" selected>Camera</option>
        <option value="screen">This screen</option>
      </select>
      <label for="tether-mode">Seal mode</label>
      <select id="tether-mode">
        <option value="obfuscation" selected>Obfuscation</option>
        <option value="private">Private</option>
        <option value="broadcast">Broadcast</option>
      </select>

      <h2>AZ-OS consent</h2>
      <p class="help">You give consent by turning obfuscation off, or by accepting a call through AZ-OS. The veil returns when the call ends, unless you left obfuscation off.</p>
      <label class="inline" for="obfuscation-on">
        <input type="checkbox" id="obfuscation-on" checked>
        Keep the veil on
      </label>
      <label for="azos-actor">Your name on the receipt</label>
      <input id="azos-actor" type="text" value="user" autocomplete="name">
      <div class="row">
        <button class="ghost" id="azos-accept" type="button">Accept call through AZ-OS</button>
        <button class="ghost" id="azos-end" type="button">End call</button>
      </div>
      <p class="help" id="azos-status"></p>

      <h2>Sample frames</h2>
      <p class="help">Seal a tiny picture made on this computer, then compare it with the sealed pixels and the opened preview. The session key is shown once.</p>
      <label for="mode">Mode</label>
      <select id="mode">
        <option value="private">Private</option>
        <option value="broadcast">Broadcast</option>
        <option value="obfuscation">Obfuscation</option>
      </select>
      <div class="row">
        <button class="ghost" id="go" type="button">Seal sample</button>
      </div>
      <div id="result" hidden>
        <p class="help" id="meta"></p>
        <p class="key" id="key"></p>
        <div class="grid">
          <div><canvas id="plain" width="64" height="48"></canvas><p class="cap">Sample</p></div>
          <div><canvas id="cipher" width="64" height="48"></canvas><p class="cap">Sealed pixels</p></div>
          <div><canvas id="dec" width="64" height="48"></canvas><p class="cap">Opened preview</p></div>
          <div id="decoy-wrap" hidden><canvas id="decoy" width="64" height="48"></canvas><p class="cap">Obfuscation veil</p></div>
        </div>
        <p class="cap">Ciphertext hex (first 96 bytes)</p>
        <p class="hex" id="hex"></p>
      </div>

      <h2>Call apps</h2>
      <pre class="out" id="apps-help">__APPS__</pre>
      <div class="row">
        <button class="ghost" id="copy-apps" type="button">Copy app instructions</button>
      </div>

      <h2>About</h2>
      <p class="help">VeilLock veils the camera on this computer until you lift it. You give consent through the AZ-OS hook above. Pulse must pass or the public feed stays veiled. Author: Aziel Eliab.</p>
      <p class="help">Commands on this computer: <code>veillock doctor</code>, <code>veillock apps</code>, <code>veillock --help</code>.</p>

      <h2>Wrap any call</h2>
      <p class="help" id="wrap-honesty">__HONESTY__</p>
      <p class="help">Preview uses a synthetic frame, a JPEG-like recompression, and the real key check. Numbers below are computed for this preview. The call path is a scramble. Record / play on this page seals video and audio with AES-256-GCM and decrypts in memory. No plaintext file is written. Someone can still point a screen recorder at this window.</p>
      <div class="row">
        <button class="primary" id="wrap-preview" type="button">Preview scramble</button>
        <button class="ghost" id="wrap-record" type="button">Seal and play in memory</button>
        <button class="ghost" id="mic-start" type="button">Start microphone</button>
        <button class="ghost" id="mic-stop" type="button">Stop microphone</button>
      </div>
      <label class="inline" for="mic-scramble"><input id="mic-scramble" type="checkbox" /> When the veil is lifted, send a PCM scramble instead of the microphone</label>
      <p class="help" id="mic-status">Microphone idle. Linux creates VeilLock Microphone. macOS feeds BlackHole 2ch only if BlackHole is installed. Windows feeds CABLE Input only if VB-Audio Virtual Cable is installed; the app selects CABLE Output. Call audio is not AES-256-GCM.</p>
      <p class="help" id="wrap-status">Idle. Default public feed is the veil until you lift it.</p>
      <div class="grid" id="wrap-grid" hidden>
        <div><canvas id="wrap-src" width="64" height="64"></canvas><p class="cap">synthetic camera</p></div>
        <div><canvas id="wrap-call" width="64" height="64"></canvas><p class="cap">what the call provider sees</p></div>
        <div><canvas id="wrap-peer" width="64" height="64"></canvas><p class="cap">peer with the key, after codec</p></div>
        <div><canvas id="wrap-nokey" width="64" height="64"></canvas><p class="cap">without the key</p></div>
      </div>
      <p class="cap" id="wrap-metrics"></p>
      <p class="key" id="wrap-key" hidden></p>

      <h2>Encrypted link</h2>
      <p class="help">This seals one synthetic encoded frame with AES-256-GCM and shows what a relay would see. The call app is not this channel. The scramble remains obfuscation for someone without VeilLock.</p>
      <div class="row">
        <button class="primary" id="e2e-demo" type="button">Seal an encoded frame</button>
      </div>
      <p class="help" id="e2e-status">Idle. Both ends need the key. A wrong key fails closed.</p>

      <h2>Join a link</h2>
      <p class="help">Plans the same report as <code>veillock join</code>. This desk does not join the call, register a camera, or launch an app. A gallery is one outgoing veil or scramble, not an AES mesh.</p>
      <label for="join-url">Meeting URL</label>
      <input id="join-url" type="text" value="https://teams.microsoft.com/l/meetup-join/example">
      <label for="join-platform">Platform</label>
      <select id="join-platform">
        <option value="chromium" selected>chromium</option>
        <option value="firefox">firefox</option>
        <option value="safari">safari</option>
        <option value="linux">linux</option>
        <option value="windows">windows</option>
        <option value="darwin">darwin</option>
        <option value="ios">ios</option>
      </select>
      <div class="row">
        <button class="primary" id="join-plan" type="button">Plan this link</button>
      </div>
      <pre class="out" id="join-report">Idle. Nothing is joined.</pre>

      <h2>Engulf plan</h2>
      <p class="help">Asks the engulf adapter only. The desk does not launch the app and does not register a camera. Windows without the local helper does not hook.</p>
      <label for="engulf-app">App</label>
      <input id="engulf-app" type="text" value="zoom">
      <label for="engulf-platform">Platform</label>
      <select id="engulf-platform">
        <option value="linux">linux</option>
        <option value="windows" selected>windows</option>
        <option value="darwin">darwin</option>
        <option value="ios">ios</option>
      </select>
      <div class="row">
        <button class="primary" id="engulf-plan-btn" type="button">Plan engulf</button>
      </div>
      <pre class="out" id="engulf-report">Idle. Nothing is launched.</pre>

      <h2>aziel-runtime</h2>
      <p class="help">The human UI is aziel-runtime. This desk is the local VeilLock surface that UI can open. The public door lists no ops for this slug. Consent stays the AZ-OS fields. The public ACT-RECEIPT chain is not written here.</p>
      <pre class="out" id="suite-status">Loading the contract.</pre>
    </div>
  </details>
  <footer>VeilLock __VERSION__ · Aziel Eliab</footer>
</main>
<script>
(function () {
  const $ = (id) => document.getElementById(id);
  function showError(text) {
    $("err").hidden = false;
    $("err").textContent = text;
  }
  function clearError() { $("err").hidden = true; $("err").textContent = ""; }
  function plain(data) {
    const running = data.running ? "Running. " : "Stopped. ";
    let veil = "Veil on — your camera stays protected.";
    const reason = data.reason || "";
    if (data.veil === "lifted") {
      veil = reason.indexOf("obfuscation off") !== -1
        ? "Veil lifted — you turned obfuscation off."
        : "Veil lifted — you accepted a call through AZ-OS.";
    }
    return running + veil;
  }
  function applyStatus(data) {
    $("status").textContent = plain(data);
    $("start").textContent = data.running ? "Stop camera veil" : "Start camera veil";
    $("start").dataset.running = data.running ? "1" : "0";
    if (typeof data.obfuscation_on === "boolean") {
      $("obfuscation-on").checked = data.obfuscation_on;
    }
    if (data.veil) {
      $("azos-status").textContent = plain(data);
    }
  }
  async function refresh() {
    try {
      const res = await fetch("/api/azos");
      applyStatus(await res.json());
    } catch (e) { /* local only */ }
  }
  function draw(canvas, b64, w, h) {
    const raw = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(w, h);
    const n = w * h;
    for (let i = 0, j = 0; i < n; i++) {
      img.data[j++] = raw[i * 3] || 0;
      img.data[j++] = raw[i * 3 + 1] || 0;
      img.data[j++] = raw[i * 3 + 2] || 0;
      img.data[j++] = 255;
    }
    ctx.putImageData(img, 0, 0);
  }
  $("start").onclick = async () => {
    clearError();
    $("start").disabled = true;
    try {
      if ($("start").dataset.running === "1") {
        const res = await fetch("/api/tether/stop", {method: "POST"});
        const data = await res.json();
        applyStatus(data);
        return;
      }
      const res = await fetch("/api/tether/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          source: $("tether-source").value,
          mode: $("tether-mode").value,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) {
        const reason = data.error || ("HTTP " + res.status);
        const next = /pip install/.test(reason)
          ? "Then press Start camera veil again."
          : "Try: veillock doctor";
        showError(reason + " " + next);
        $("status").textContent = "Stopped. The camera veil did not start.";
        return;
      }
      applyStatus(data);
    } catch (e) {
      showError(String(e.message || e) + " Try: veillock ui");
    } finally {
      $("start").disabled = false;
    }
  };
  $("doctor").onclick = async () => {
    clearError();
    $("doctor").disabled = true;
    try {
      const res = await fetch("/api/doctor");
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      const lines = (data.checks || []).map((c) => (c.ok ? "pass  " : "FAIL  ") + c.id);
      lines.push(data.ok ? "doctor: healthy" : "doctor: FAILED");
      if (!data.ok) lines.push("Next: veillock doctor --json");
      $("doctor-out").hidden = false;
      $("doctor-out").textContent = lines.join("\n");
    } catch (e) {
      showError(String(e.message || e) + " Try: veillock doctor");
    } finally {
      $("doctor").disabled = false;
    }
  };
  $("go").onclick = async () => {
    clearError();
    $("go").disabled = true;
    try {
      const res = await fetch("/api/demo", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({mode: $("mode").value}),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      $("result").hidden = false;
      const w = data.width, h = data.height;
      $("meta").textContent = data.frames + " frames · " + w + "×" + h + " · " + data.mode
        + ". The sealed pixels look like noise. The opened preview matches the sample.";
      let key = "session_key (shown once)\n" + data.session_key;
      if (data.receiver_secret) key += "\nreceiver_secret (shown once)\n" + data.receiver_secret;
      $("key").textContent = key;
      draw($("plain"), data.plain_b64, w, h);
      draw($("cipher"), data.cipher_b64, w, h);
      draw($("dec"), data.decrypt_b64, w, h);
      if (data.decoy_b64) {
        $("decoy-wrap").hidden = false;
        draw($("decoy"), data.decoy_b64, w, h);
      } else {
        $("decoy-wrap").hidden = true;
      }
      $("hex").textContent = data.cipher_hex;
    } catch (e) {
      showError(String(e.message || e) + " Try: Seal sample again.");
    } finally {
      $("go").disabled = false;
    }
  };
  $("obfuscation-on").onchange = async () => {
    clearError();
    try {
      const res = await fetch("/api/azos/obfuscation", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({on: $("obfuscation-on").checked}),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      applyStatus(data);
    } catch (e) {
      showError(String(e.message || e) + " Try: veillock azos");
    }
  };
  $("azos-accept").onclick = async () => {
    clearError();
    try {
      const res = await fetch("/api/azos/accept", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({actor: $("azos-actor").value || "user"}),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      applyStatus(data);
    } catch (e) {
      showError(String(e.message || e) + " Try: veillock azos --accept --actor \"your name\"");
    }
  };
  $("azos-end").onclick = async () => {
    clearError();
    try {
      const res = await fetch("/api/azos/end", {method: "POST"});
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      applyStatus(data);
    } catch (e) {
      showError(String(e.message || e) + " Try: veillock azos --end");
    }
  };
  async function refreshMic() {
    try {
      const res = await fetch("/api/mic");
      const data = await res.json();
      const name = data.selectable_name || "unavailable";
      $("mic-status").textContent = "Mic " + (data.running ? "running" : "stopped")
        + " · " + (data.platform || "")
        + " · " + name
        + " · created by VeilLock: " + (data.created_by_veillock ? "yes" : "no")
        + " · call audio AES-256-GCM: no. "
        + (data.note || data.error || "");
    } catch (e) { /* status line keeps the static honesty text */ }
  }
  $("mic-start").onclick = async () => {
    $("err").hidden = true;
    try {
      const res = await fetch("/api/mic/start", {method: "POST", headers: {"Content-Type": "application/json"}, body: JSON.stringify({scramble: $("mic-scramble").checked})});
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || data.note || ("HTTP " + res.status));
      await refreshMic();
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
      await refreshMic();
    }
  };
  $("mic-stop").onclick = async () => {
    try {
      await fetch("/api/mic/stop", {method: "POST"});
      await refreshMic();
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    }
  };
  refreshMic();
  $("e2e-demo").onclick = async () => {
    $("err").hidden = true;
    try {
      const res = await fetch("/api/e2e/demo", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      $("e2e-status").textContent = data.note;
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    }
  };
  $("wrap-preview").onclick = async () => {
    $("err").hidden = true;
    $("wrap-preview").disabled = true;
    try {
      const res = await fetch("/api/wrap/preview", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      $("wrap-grid").hidden = false;
      const w = data.width, h = data.height;
      draw($("wrap-src"), data.source_b64, w, h);
      draw($("wrap-call"), data.call_b64, w, h);
      draw($("wrap-peer"), data.peer_b64, w, h);
      draw($("wrap-nokey"), data.denied_b64, w, h);
      $("wrap-key").hidden = false;
      $("wrap-key").textContent = "call key (shown once)\\n" + data.session_key
        + "\\nCall path: scramble, not AES-256-GCM. Local recording of the same key would be AES-256-GCM.";
      $("wrap-metrics").textContent = "After JPEG-like q=" + data.quality
        + ": with key correlation " + data.with_key.correlation + ", MAE " + data.with_key.mae
        + ". Without key: " + data.without_key.kind + ", correlation " + data.without_key.correlation
        + ". Provider vs camera correlation " + data.provider.correlation + ".";
      $("wrap-status").textContent = data.note;
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    } finally { $("wrap-preview").disabled = false; }
  };
  $("wrap-record").onclick = async () => {
    $("err").hidden = true;
    $("wrap-record").disabled = true;
    try {
      const res = await fetch("/api/record/demo", {method: "POST", headers: {"Content-Type": "application/json"}, body: "{}"});
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || ("HTTP " + res.status));
      $("wrap-key").hidden = false;
      $("wrap-key").textContent = "recording key (shown once)\\n" + data.session_key
        + "\\n" + data.note;
      $("wrap-status").textContent = "AES-256-GCM recording stayed encrypted on disk. Playback matched in memory=" + data.match + ". A screen recorder pointed at this window can still see the picture."
        + " frames=" + data.frames + ". This file is encryption. It is not the call scramble.";
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    } finally { $("wrap-record").disabled = false; }
  };
  $("join-plan").onclick = async () => {
    $("err").hidden = true;
    try {
      const res = await fetch("/api/join", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({url: $("join-url").value, platform: $("join-platform").value}),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      $("join-report").textContent = data.report
        + "\\njoined_call=" + data.joined_call
        + "\\naes_on_call_path=" + data.aes_on_call_path
        + "\\ncamera=" + data.camera;
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    }
  };
  $("engulf-plan-btn").onclick = async () => {
    $("err").hidden = true;
    try {
      const res = await fetch("/api/engulf/plan", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({app: $("engulf-app").value, platform: $("engulf-platform").value}),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      $("engulf-report").textContent = (data.note || "")
        + "\\nengulfs=" + data.engulfs
        + "\\nexecuted=" + data.executed
        + "\\nregistered_camera=" + data.registered_camera
        + "\\naes_on_call_path=" + data.aes_on_call_path;
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    }
  };
  async function refreshSuite() {
    try {
      const res = await fetch("/api/suite");
      const data = await res.json();
      const receipts = data.receipts || {};
      $("suite-status").textContent = (data.schema || "")
        + " · human_ui=" + data.human_ui
        + " · local_only=" + data.local_only
        + " · writes_public_chain=" + receipts.writes_public_chain
        + "\\n" + (data.handoff || "");
    } catch (e) { /* the static line stays if the tile cannot be read */ }
  }
  refreshSuite();
  $("copy-apps").onclick = async () => {
    const text = $("apps-help").textContent;
    try {
      await navigator.clipboard.writeText(text);
      $("status").textContent = "App instructions copied.";
    } catch (e) {
      $("status").textContent = "Select the instructions and copy them.";
    }
  };
  refresh();
})();
</script>
</body>
</html>
""".replace("__VERSION__", __version__)

PAGE = PAGE.replace("__APPS__", APPS_GUIDE)
PAGE = PAGE.replace(
    "__HONESTY__",
    " ".join([CALL_VIDEO, CALL_AUDIO, LOCAL_RECORDING, PULSE, PLATFORM, E2E, ENGULF]),
)


def _rgb_b64(frame: np.ndarray) -> str:
    arr = np.ascontiguousarray(frame, dtype=np.uint8)
    return base64.b64encode(arr.tobytes()).decode("ascii")


def _synthetic_frames(n: int = 3, h: int = 48, w: int = 64) -> np.ndarray:
    frames = np.zeros((n, h, w, 3), dtype=np.uint8)
    for i in range(n):
        frames[i, :, :] = (18, 16, 36)
        x = 6 + i * 8
        frames[i, 10:38, x : x + 22] = (40 + i * 50, 170, 110)
        frames[i, 0:5, :] = (190, 150, 70)
        frames[i, h - 4 : h, :] = (50, 70, 120)
        frames[i, :, 0:3] = (90, 50, 140)
    return frames


def _cipher_as_rgb(ciphertext: bytes, h: int, w: int) -> np.ndarray:
    need = h * w * 3
    buf = (ciphertext * ((need // max(len(ciphertext), 1)) + 1))[:need]
    return np.frombuffer(buf, dtype=np.uint8).reshape(h, w, 3).copy()


def _health() -> dict[str, Any]:
    return {
        "ok": True,
        "bind_host": DEFAULT_HOST,
        "name": "VeilLock",
        "identity": "consent-gated camera protection via AZ-OS",
        "azos_hook": True,
    }


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

    def _wants_json(self) -> bool:
        accept = (self.headers.get("Accept") or "").lower()
        if not accept or accept.strip() in ("*/*", ""):
            return False
        parts = [p.split(";", 1)[0].strip() for p in accept.split(",")]
        if "text/html" in parts or "application/xhtml+xml" in parts:
            return False
        return "application/json" in parts

    def _send(self, code: int, body: bytes, content_type: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, obj: Any) -> None:
        self._send(code, json.dumps(obj).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        if path in ("/", "/index.html"):
            if self._wants_json():
                self._json(200, _health())
                return
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json(200, _health())
            return
        if path == "/api/doctor":
            from veillock.doctor import run as doctor_run

            self._json(200, doctor_run())
            return
        if path == "/api/apps":
            self._send(200, APPS_GUIDE.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if path == "/api/tether":
            self._json(200, RUNTIME.status())
            return
        if path == "/api/azos":
            self._json(200, RUNTIME.status())
            return
        if path == "/api/mic":
            from veillock.mic import MIC_RUNTIME

            self._json(200, MIC_RUNTIME.status())
            return
        if path == "/api/suite":
            from veillock.surfaces import runtime_ui

            self._json(200, runtime_ui())
            return
        if path == "/api/status":
            from veillock.surfaces import status_report

            self._json(200, status_report())
            return
        self._json(404, {"error": "not found"})

    def do_POST(self) -> None:  # noqa: N802
        path = urlparse(self.path).path
        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_BODY:
            self._json(400, {"error": "payload too large"})
            return
        raw = self.rfile.read(length) if length else b""
        if path == "/api/tether/stop":
            self._json(200, RUNTIME.stop())
            return
        if path == "/api/azos/end":
            self._json(200, RUNTIME.end_call())
            return
        if path == "/api/azos/accept":
            try:
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                self._json(
                    200,
                    RUNTIME.accept_call(
                        actor=str(body.get("actor") or "user"),
                        call_id=body.get("call_id"),
                    ),
                )
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(exc)})
            return
        if path == "/api/azos/obfuscation":
            try:
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                on = body.get("on")
                if on is None:
                    on = body.get("obfuscation_on", True)
                self._json(200, RUNTIME.set_obfuscation(bool(on)))
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(exc)})
            return
        if path == "/api/mic/start":
            from veillock.mic import MIC_RUNTIME

            try:
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                payload = MIC_RUNTIME.start(scramble_when_lifted=bool(body.get("scramble")))
                self._json(200 if payload.get("ok") else 400, payload)
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(exc), "call_audio_aes_256_gcm": False})
            return
        if path == "/api/mic/stop":
            from veillock.mic import MIC_RUNTIME

            self._json(200, MIC_RUNTIME.stop())
            return
        if path == "/api/e2e/demo":
            self._e2e_demo()
            return
        if path == "/api/wrap/preview":
            self._wrap_preview()
            return
        if path == "/api/record/demo":
            self._record_demo()
            return
        if path == "/api/join":
            self._join_plan(raw)
            return
        if path == "/api/engulf/plan":
            self._engulf_plan(raw)
            return
        if path == "/api/tether/start":
            try:
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                cfg = TetherConfig(
                    source=str(body.get("source") or "camera"),
                    mode=str(body.get("mode") or "obfuscation"),
                    trusted=bool(body.get("trusted")),
                    obfuscation_off=bool(body.get("obfuscation_off")),
                    azos_accept=bool(body.get("azos_accept")),
                    actor=str(body.get("actor") or ""),
                    device=int(body.get("device") or 0),
                )
                self._json(200, RUNTIME.start(cfg))
            except Exception as exc:  # noqa: BLE001
                self._json(400, {"ok": False, "error": str(exc)})
            return
        if path != "/api/demo":
            self._json(404, {"error": "not found"})
            return
        try:
            body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            mode = Mode.parse(str(body.get("mode") or "private"))
            frames = _synthetic_frames()
            key = secrets.token_bytes(32)
            receiver = secrets.token_bytes(32) if mode is Mode.BROADCAST else None
            enc = VeilLockSession(
                session_key=key,
                rotation_interval=60,
                mode=mode,
                receiver_secret=receiver,
            )
            stream = enc.encrypt_frames(frames)
            dec = VeilLockSession(
                session_key=key,
                rotation_interval=60,
                mode=mode,
                receiver_secret=receiver,
            )
            out = dec.decrypt_frames(stream)
            sealed = stream.frames[0]
            h, w, _ = sealed.shape
            cipher_rgb = _cipher_as_rgb(sealed.ciphertext, h, w)
            decoy_b64 = None
            if stream.decoy is not None and len(stream.decoy):
                decoy_b64 = _rgb_b64(stream.decoy[0])
            self._json(
                200,
                {
                    "mode": mode.value,
                    "frames": int(frames.shape[0]),
                    "height": h,
                    "width": w,
                    "session_key": key.hex(),
                    "receiver_secret": receiver.hex() if receiver is not None else None,
                    "plain_b64": _rgb_b64(frames[0]),
                    "cipher_b64": _rgb_b64(cipher_rgb),
                    "decrypt_b64": _rgb_b64(out[0]),
                    "decoy_b64": decoy_b64,
                    "cipher_hex": sealed.ciphertext[:96].hex(),
                    "match": bool(np.array_equal(out, frames)),
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})

    def _join_plan(self, raw: bytes) -> None:
        from veillock.surfaces import join_plan

        try:
            body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            if not isinstance(body, dict):
                body = {}
            from veillock.surfaces import sandbox_environ

            windows_build = body.get("windows_build")
            self._json(
                200,
                join_plan(
                    body.get("url") if body.get("url") else None,
                    process=body.get("process") or None,
                    platform=body.get("platform") or None,
                    bundle_id=body.get("bundle") or body.get("bundle_id") or None,
                    windows_build=windows_build if windows_build not in ("",) else None,
                    environ=sandbox_environ(),
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._json(
                400,
                {
                    "ok": False,
                    "error": str(exc),
                    "joined_call": False,
                    "executed": False,
                    "aes_on_call_path": False,
                },
            )

    def _engulf_plan(self, raw: bytes) -> None:
        from veillock.surfaces import engulf_plan

        try:
            body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
            if not isinstance(body, dict):
                body = {}
            windows_build = body.get("windows_build")
            self._json(
                200,
                engulf_plan(
                    str(body.get("app") or "zoom"),
                    platform=body.get("platform") or None,
                    windows_build=windows_build if windows_build not in ("",) else None,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            self._json(
                400,
                {
                    "ok": False,
                    "error": str(exc),
                    "executed": False,
                    "registered_camera": False,
                    "aes_on_call_path": False,
                },
            )

    def _e2e_demo(self) -> None:
        from veillock.crypto import DecryptError
        from veillock.e2e import exchange_over_relay

        try:
            camera = b"camera-encoded-frame"
            veil = b"veil-encoded-frame"
            key = bytes(range(32))
            opened, relay = exchange_over_relay([camera], key, veil=veil, lifted=False, pulse_ok=True)
            leaked = relay.saw_plaintext(camera) or relay.saw_plaintext(veil)
            wrong = False
            try:
                exchange_over_relay([camera], key, veil=veil, lifted=True, peer_key=bytes([9] * 32))
            except DecryptError:
                wrong = True
            self._json(
                200,
                {
                    "ok": True,
                    "aes_256_gcm": True,
                    "relay_saw_plaintext": leaked,
                    "peer_got": opened[0].decode("ascii"),
                    "wrong_key_closed": wrong,
                    "note": (
                        "Relay saw ciphertext only. With the veil still on, the peer decrypted the veil, "
                        "not the camera. A wrong key failed closed. This is AES-256-GCM on the VeilLock "
                        "link, not on the call app. The scramble is still obfuscation."
                    ),
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"ok": False, "error": str(exc)})

    def _wrap_preview(self) -> None:
        from veillock.codecsim import jpeg_like
        from veillock.scramble import scramble_frame, unveil_frame

        try:
            h, w = 128, 128
            rng = np.random.default_rng(7)
            src = rng.integers(0, 256, size=(h, w, 3), dtype=np.uint8)
            yy, xx = np.mgrid[0:h, 0:w]
            face = ((xx - w * 0.5) ** 2) / (w * w * 0.08) + ((yy - h * 0.45) ** 2) / (h * h * 0.10) < 1.0
            src[face] = (210, 160, 140)
            src[h // 3 : h // 3 + 8, w // 3 : w // 3 + 8] = (30, 30, 40)
            src[h // 3 : h // 3 + 8, w // 2 : w // 2 + 8] = (30, 30, 40)
            key = secrets.token_bytes(32)
            wrong = bytes((b ^ 0xFF) for b in key)
            quality = 40
            call = scramble_frame(src, key, epoch=1)
            lossy = jpeg_like(call, quality=quality)
            peer = unveil_frame(lossy, key)
            denied = unveil_frame(lossy, wrong)
            body = (slice(8, -8), slice(None), slice(None))
            self._json(
                200,
                {
                    "ok": True,
                    "width": w,
                    "height": h,
                    "quality": quality,
                    "aes_256_gcm": False,
                    "kind": "scramble",
                    "session_key": key.hex(),
                    "source_b64": _rgb_b64(src),
                    "call_b64": _rgb_b64(call),
                    "peer_b64": _rgb_b64(peer.image),
                    "denied_b64": _rgb_b64(denied.image),
                    "with_key": {
                        "authorized": peer.authorized,
                        "kind": peer.kind,
                        "correlation": round(_corr(peer.image[body], src[body]), 4),
                        "mae": round(_mae(peer.image[body], src[body]), 4),
                    },
                    "without_key": {
                        "authorized": denied.authorized,
                        "kind": denied.kind,
                        "correlation": round(_corr(denied.image[body], src[body]), 4),
                        "mae": round(_mae(denied.image[body], src[body]), 4),
                    },
                    "provider": {
                        "correlation": round(_corr(call[body], src[body]), 4),
                        "mae": round(_mae(call[body], src[body]), 4),
                    },
                    "note": peer.note,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})

    def _record_demo(self) -> None:
        import os
        import tempfile

        from veillock.record import play_recording, seal_recording

        path = None
        try:
            frames = _synthetic_frames(n=2, h=32, w=32)
            key = secrets.token_bytes(32)
            pcm = np.array([1000, -1000, 500, -500] * 80, dtype=np.int16)
            fd, path = tempfile.mkstemp(suffix=".veilrec")
            os.close(fd)
            seal_recording(path, frames, key, pcm=pcm, rotation_interval=60)
            played = play_recording(path, key)
            match = bool(np.array_equal(played.frames, frames) and np.array_equal(played.pcm, pcm))
            self._json(
                200,
                {
                    "ok": True,
                    "aes_256_gcm": True,
                    "match": match,
                    "frames": int(frames.shape[0]),
                    "session_key": key.hex(),
                    "note": played.note,
                },
            )
        except Exception as exc:  # noqa: BLE001
            self._json(400, {"error": str(exc)})
        finally:
            if path:
                try:
                    os.remove(path)
                except OSError:
                    pass


def _corr(a: np.ndarray, b: np.ndarray) -> float:
    x = a.astype(np.float64).ravel()
    y = b.astype(np.float64).ravel()
    x = x - x.mean()
    y = y - y.mean()
    denom = float(np.linalg.norm(x) * np.linalg.norm(y))
    if denom == 0.0:
        return 0.0
    return float(x @ y) / denom


def _mae(a: np.ndarray, b: np.ndarray) -> float:
    return float(np.mean(np.abs(a.astype(np.int16) - b.astype(np.int16))))


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise ValueError("VeilLock UI binds loopback only (127.0.0.1)")
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    httpd = make_server(host, port)
    sys.stdout.write(f"Open http://{host}:{port}/\n")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped\n")
    finally:
        httpd.server_close()
