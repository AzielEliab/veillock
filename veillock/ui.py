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
    --bg: #0d0b14; --card: #171427; --ink: #efeaf8; --muted: #9a91b3;
    --line: #2c2744; --accent: #a78bfa; --accent-dim: #3b2d66; --warn: #e0b46a;
  }
  * { box-sizing: border-box; }
  html, body { margin: 0; background: var(--bg); color: var(--ink);
    font-family: "Iowan Old Style", Palatino, Georgia, serif; }
  main { max-width: 46rem; margin: 0 auto; padding: 2.4rem 1.25rem 4rem; }
  .mark { font-size: 0.72rem; letter-spacing: 0.22em; text-transform: uppercase;
    color: var(--accent); margin: 0 0 0.45rem; }
  h1 { font-weight: 500; letter-spacing: 0.04em; font-size: 2.1rem; margin: 0 0 0.4rem; }
  .motto { font-style: italic; color: var(--muted); margin: 0; }
  .local { display: inline-block; margin-top: 0.85rem; font-size: 0.78rem;
    color: var(--muted); border: 1px solid var(--line); padding: 0.2rem 0.55rem;
    border-radius: 999px; font-family: ui-monospace, monospace; }
  .card { background: var(--card); border: 1px solid var(--line); border-radius: 12px;
    padding: 1.15rem 1.2rem 1.25rem; margin: 1.1rem 0; }
  h2 { font-size: 1.02rem; font-weight: 500; margin: 0 0 0.75rem; }
  p.help { color: var(--muted); font-size: 0.92rem; margin: 0 0 0.9rem; }
  label { display: block; font-size: 0.82rem; color: var(--muted); margin: 0.55rem 0 0.28rem; }
  select { width: 100%; background: #0d0b14; color: var(--ink); border: 1px solid var(--line);
    padding: 0.45rem 0.55rem; border-radius: 6px; }
  button.primary { font-family: inherit; cursor: pointer; border: 0; border-radius: 8px;
    padding: 0.55rem 1.15rem; background: var(--accent); color: #1a1230; font-weight: 600; }
  button:disabled { opacity: 0.5; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(11rem, 1fr)); gap: 0.85rem; }
  canvas { width: 100%; image-rendering: pixelated; background: #000; border: 1px solid var(--line);
    border-radius: 6px; }
  .cap { font-size: 0.78rem; color: var(--muted); margin: 0.3rem 0 0; }
  .key { font-family: ui-monospace, monospace; font-size: 0.75rem; word-break: break-all;
    background: #0d0b14; border: 1px dashed var(--line); padding: 0.6rem; border-radius: 6px; }
  .hex { font-family: ui-monospace, monospace; font-size: 0.72rem; color: var(--muted);
    word-break: break-all; }
  .err { color: #e07a7a; }
  footer { margin-top: 2rem; color: #6d6584; font-size: 0.8rem; }
  button.ghost { font-family: inherit; cursor: pointer; border: 1px solid var(--line);
    border-radius: 8px; padding: 0.55rem 1.15rem; background: transparent; color: var(--ink); margin-left: 0.4rem; }
  pre.apps { white-space: pre-wrap; font-family: ui-monospace, monospace; font-size: 0.78rem;
    color: var(--muted); background: #0d0b14; border: 1px solid var(--line); padding: 0.75rem; border-radius: 6px; }
  label.inline { display: flex; align-items: center; gap: 0.45rem; margin-top: 0.75rem; color: var(--ink); }
</style>
</head>
<body>
<main>
  <header>
    <p class="mark">Aziel Eliab · July 2026</p>
    <h1>VeilLock</h1>
    <p class="motto">Render → encrypt → decode locally → display.</p>
    <span class="local">localhost · 127.0.0.1 · key shown once</span>
  </header>
  <aside class="card" role="note" id="honest-banner">
    <h2>Honest scope</h2>
    <p class="help"><strong>YOUR camera/screen only. Not a call interceptor.</strong> VeilLock does not inject into FaceTime, Zoom, Meet, Teams, or Skype. The call app must choose the virtual camera named VeilLock. iPhone FaceTime cannot select a third-party virtual camera.</p>
  </aside>
  <section class="card">
    <h2>Seal synthetic frames</h2>
    <p class="help">Generates a tiny RGB stack here, encrypts it, and shows ciphertext as noise against the decrypted preview. The session key is printed once and not stored.</p>
    <label>Mode</label>
    <select id="mode">
      <option value="private">private</option>
      <option value="broadcast">broadcast</option>
      <option value="obfuscation">obfuscation</option>
    </select>
    <p style="margin-top:0.95rem"><button class="primary" id="go" type="button">Seal frames</button></p>
  </section>
  <section class="card" id="result" hidden>
    <h2>Session</h2>
    <p class="help" id="meta"></p>
    <p class="key" id="key"></p>
    <div class="grid" style="margin-top:1rem">
      <div><canvas id="plain" width="64" height="48"></canvas><p class="cap">plaintext (synthetic)</p></div>
      <div><canvas id="cipher" width="64" height="48"></canvas><p class="cap">ciphertext as pixels</p></div>
      <div><canvas id="dec" width="64" height="48"></canvas><p class="cap">decrypted preview</p></div>
      <div id="decoy-wrap" hidden><canvas id="decoy" width="64" height="48"></canvas><p class="cap">obfuscation decoy</p></div>
    </div>
    <p class="cap">Ciphertext hex (first 96 bytes)</p>
    <p class="hex" id="hex"></p>
  </section>
  <section class="card" id="tether">
    <h2>Tether</h2>
    <p class="help">Pipe <em>your</em> camera or screen through VeilLock into Zoom, FaceTime (Mac), Skype, Meet, or Teams. The call app must choose the virtual camera named <strong>VeilLock</strong>. Not a call interceptor. iPhone FaceTime cannot select a third-party virtual camera (Apple).</p>
    <label>Source</label>
    <select id="tether-source">
      <option value="camera" selected>camera (this device)</option>
      <option value="screen">screen (this display)</option>
    </select>
    <label>Mode</label>
    <select id="tether-mode">
      <option value="obfuscation" selected>obfuscation (call apps see synthetic UI noise)</option>
      <option value="private">private (black unless trusted decode)</option>
      <option value="broadcast">broadcast</option>
    </select>
    <label class="inline"><input type="checkbox" id="tether-trusted"> Trusted decode to the virtual camera (your choice; default off)</label>
    <p style="margin-top:0.95rem">
      <button class="primary" id="tether-start" type="button">Start</button>
      <button class="ghost" id="tether-stop" type="button">Stop</button>
      <button class="ghost" id="copy-apps" type="button">Copy app instructions</button>
    </p>
    <p class="help" id="tether-status">Stopped. Default mode is obfuscation.</p>
    <h2>App instructions</h2>
    <pre class="apps" id="apps-help">__APPS__</pre>
  </section>
  <section class="card" id="json-io">
    <h2>Import / Export JSON</h2>
    <p class="help">Import a JSON file of session settings (mode, tether source). Export JSON saves settings plus last seal metadata (not the session key — that is shown once and not stored). Local only.</p>
    <input id="import-json" type="file" accept="application/json,.json">
    <p style="margin-top:0.75rem">
      <button class="primary" id="import-json-btn" type="button">Import JSON file</button>
      <button class="ghost" id="export-json-btn" type="button">Export JSON</button>
    </p>
    <p class="help" id="json-status"></p>
  </section>
  <p class="err" id="err" hidden></p>
  <footer>VeilLock __VERSION__ · Apache-2.0 · forks welcome · <code>veillock ui</code></footer>
</main>
<script>
(function () {
  const $ = (id) => document.getElementById(id);
  function draw(canvas, b64, w, h) {
    const raw = Uint8Array.from(atob(b64), c => c.charCodeAt(0));
    canvas.width = w; canvas.height = h;
    const ctx = canvas.getContext("2d");
    const img = ctx.createImageData(w, h);
    let n = w * h;
    for (let i = 0, j = 0; i < n; i++) {
      img.data[j++] = raw[i*3] || 0;
      img.data[j++] = raw[i*3+1] || 0;
      img.data[j++] = raw[i*3+2] || 0;
      img.data[j++] = 255;
    }
    ctx.putImageData(img, 0, 0);
  }
  $("go").onclick = async () => {
    $("err").hidden = true;
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
      $("meta").textContent = data.frames + " frames · " + w + "×" + h + " · mode " + data.mode
        + " · ciphertext looks like noise; decrypt matches the synthetic source.";
      let key = "session_key (shown once)\\n" + data.session_key;
      if (data.receiver_secret) key += "\\nreceiver_secret (shown once)\\n" + data.receiver_secret;
      $("key").textContent = key;
      draw($("plain"), data.plain_b64, w, h);
      draw($("cipher"), data.cipher_b64, w, h);
      draw($("dec"), data.decrypt_b64, w, h);
      if (data.decoy_b64) {
        $("decoy-wrap").hidden = false;
        draw($("decoy"), data.decoy_b64, w, h);
      } else { $("decoy-wrap").hidden = true; }
      $("hex").textContent = data.cipher_hex;
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    } finally { $("go").disabled = false; }
  };
  $("tether-start").onclick = async () => {
    $("err").hidden = true;
    $("tether-start").disabled = true;
    try {
      const res = await fetch("/api/tether/start", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify({
          source: $("tether-source").value,
          mode: $("tether-mode").value,
          trusted: $("tether-trusted").checked,
        }),
      });
      const data = await res.json();
      if (!res.ok || data.ok === false) throw new Error(data.error || ("HTTP " + res.status));
      $("tether-status").textContent = "Running. Pick camera VeilLock in the call app.";
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
      $("tether-status").textContent = "Start failed.";
    } finally { $("tether-start").disabled = false; }
  };
  $("tether-stop").onclick = async () => {
    try {
      await fetch("/api/tether/stop", {method: "POST"});
      $("tether-status").textContent = "Stopped.";
    } catch (e) {
      $("err").hidden = false;
      $("err").textContent = String(e.message || e);
    }
  };

  let lastExport = {product:"veillock", author:"Aziel Eliab"};
  function collectVeil(){
    return {
      product: "veillock",
      author: "Aziel Eliab",
      mode: $("mode").value,
      "tether-source": $("tether-source").value,
      "tether-mode": $("tether-mode").value,
      "tether-trusted": $("tether-trusted").checked,
      last: lastExport.last || null,
    };
  }
  $("import-json-btn").onclick = () => $("import-json").click();
  $("import-json").onchange = () => {
    const f = $("import-json").files && $("import-json").files[0];
    if (!f) return;
    const r = new FileReader();
    r.onload = () => {
      try {
        const obj = JSON.parse(String(r.result || "{}"));
        if (obj.mode) $("mode").value = obj.mode;
        if (obj["tether-source"]) $("tether-source").value = obj["tether-source"];
        if (obj["tether-mode"]) $("tether-mode").value = obj["tether-mode"];
        if (typeof obj["tether-trusted"] === "boolean") $("tether-trusted").checked = obj["tether-trusted"];
        $("json-status").textContent = "Imported " + f.name;
      } catch (e) { $("json-status").textContent = "Invalid JSON"; }
    };
    r.readAsText(f);
  };
  $("export-json-btn").onclick = () => {
    const blob = new Blob([JSON.stringify(collectVeil(), null, 2)], {type:"application/json"});
    const a = document.createElement("a");
    a.href = URL.createObjectURL(blob);
    a.download = "veillock-session.json";
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 800);
    $("json-status").textContent = "Exported JSON (session key is not written).";
  };

  $("copy-apps").onclick = async () => {
    const text = $("apps-help").textContent;
    try {
      await navigator.clipboard.writeText(text);
      $("tether-status").textContent = "App instructions copied.";
    } catch (e) {
      $("tether-status").textContent = "Copy failed — select the instructions and copy manually.";
    }
  };
})();
</script>
</body>
</html>
""".replace("__VERSION__", __version__)

PAGE = PAGE.replace("__APPS__", APPS_GUIDE)


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


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt: str, *args: object) -> None:
        sys.stderr.write("%s - %s\n" % (self.address_string(), fmt % args))

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
            self._send(200, PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/health":
            self._json(200, {"ok": True, "bind_host": DEFAULT_HOST, "name": "VeilLock"})
            return
        if path == "/api/apps":
            self._send(200, APPS_GUIDE.encode("utf-8"), "text/plain; charset=utf-8")
            return
        if path == "/api/tether":
            self._json(200, RUNTIME.status())
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
        if path == "/api/tether/start":
            try:
                body = json.loads(raw.decode("utf-8") or "{}") if raw else {}
                cfg = TetherConfig(
                    source=str(body.get("source") or "camera"),
                    mode=str(body.get("mode") or "obfuscation"),
                    trusted=bool(body.get("trusted")),
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


def make_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    if host not in LOOPBACK:
        raise ValueError("VeilLock UI binds loopback only (127.0.0.1)")
    return ThreadingHTTPServer((host, port), Handler)


def serve(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    httpd = make_server(host, port)
    sys.stdout.write(f"VeilLock UI  http://{host}:{port}/\n")
    sys.stdout.write("Local only. Session key is shown once and not written to disk.\n")
    sys.stdout.flush()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        sys.stdout.write("\nstopped\n")
    finally:
        httpd.server_close()
