/**
 * Page-world wrap of getUserMedia and RTCPeerConnection.
 * Default is a generated veil, not the real camera. Encryption runs only
 * when a key has been posted by the extension bridge.
 *
 * Author: Aziel Eliab.
 */
import { KIND_VIDEO, attachEncodedStreams, openEncoded, pickDevice, sealEncoded } from "./e2e.js";

const state = { lifted: false, key: null, index: 0 };

function veilStream() {
  const canvas = document.createElement("canvas");
  canvas.width = 640;
  canvas.height = 480;
  const ctx = canvas.getContext("2d");
  const draw = () => {
    if (!ctx) return;
    ctx.fillStyle = "#1c2430";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#8aa0b8";
    ctx.font = "28px sans-serif";
    ctx.fillText("VeilLock", 32, 240);
  };
  draw();
  const stream = canvas.captureStream(15);
  const audioCtx = new AudioContext();
  const noise = audioCtx.createBuffer(1, audioCtx.sampleRate, audioCtx.sampleRate);
  const data = noise.getChannelData(0);
  for (let i = 0; i < data.length; i += 1) data[i] = (Math.random() * 2 - 1) * 0.01;
  const src = audioCtx.createBufferSource();
  src.buffer = noise;
  src.loop = true;
  const dest = audioCtx.createMediaStreamDestination();
  src.connect(dest);
  src.start();
  stream.addTrack(dest.stream.getAudioTracks()[0]);
  return stream;
}

async function engulfConstraints(constraints) {
  const wantsVideo = constraints && constraints.video;
  const wantsAudio = constraints && constraints.audio;
  let devices = [];
  try {
    devices = await navigator.mediaDevices.enumerateDevices();
  } catch (_err) {
    devices = [];
  }
  const video = wantsVideo ? pickDevice(devices, "videoinput", state.lifted) : { mode: "skip" };
  const audio = wantsAudio ? pickDevice(devices, "audioinput", state.lifted) : { mode: "skip" };
  if ((wantsVideo && video.mode === "veil") || (wantsAudio && audio.mode === "veil")) {
    return { veil: true, constraints: null };
  }
  const next = Object.assign({}, constraints);
  if (video.mode === "device") next.video = Object.assign({}, typeof next.video === "object" ? next.video : {}, { deviceId: { exact: video.deviceId } });
  if (audio.mode === "device") next.audio = Object.assign({}, typeof next.audio === "object" ? next.audio : {}, { deviceId: { exact: audio.deviceId } });
  return { veil: false, constraints: next };
}

function hexToBytes(hex) {
  const clean = String(hex || "").trim();
  if (clean.length !== 64) return null;
  const out = new Uint8Array(32);
  for (let i = 0; i < 32; i += 1) out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  return out;
}

async function sealFrame(data) {
  if (!state.key) return data;
  const sealed = await sealEncoded(data, state.key, state.index, 0, KIND_VIDEO);
  state.index += 1;
  return sealed;
}

async function openFrame(data) {
  if (!state.key) return data;
  try {
    const opened = await openEncoded(data, state.key);
    return opened.payload;
  } catch (_err) {
    return new Uint8Array(0);
  }
}

function wrapPeerConnection(Original) {
  function Wrapped(config) {
    const pc = new Original(config);
    const addTrack = pc.addTrack.bind(pc);
    pc.addTrack = function (track, ...rest) {
      const sender = addTrack(track, ...rest);
      if (state.key) attachEncodedStreams(sender, sealFrame);
      return sender;
    };
    pc.addEventListener("track", (event) => {
      if (!state.key || !event.receiver || typeof event.receiver.createEncodedStreams !== "function") return;
      const streams = event.receiver.createEncodedStreams();
      const transform = new TransformStream({
        async transform(frame, controller) {
          const opened = await openFrame(new Uint8Array(frame.data));
          if (opened.length === 0) return;
          frame.data = opened.buffer.slice(opened.byteOffset, opened.byteOffset + opened.byteLength);
          controller.enqueue(frame);
        },
      });
      streams.readable.pipeThrough(transform).pipeTo(streams.writable);
    });
    return pc;
  }
  Wrapped.prototype = Original.prototype;
  return Wrapped;
}

const originalGetUserMedia = navigator.mediaDevices.getUserMedia.bind(navigator.mediaDevices);
navigator.mediaDevices.getUserMedia = async function (constraints) {
  const decision = await engulfConstraints(constraints || {});
  if (decision.veil) return veilStream();
  return originalGetUserMedia(decision.constraints);
};

if (typeof RTCPeerConnection === "function") {
  window.RTCPeerConnection = wrapPeerConnection(RTCPeerConnection);
}

window.addEventListener("message", (event) => {
  const data = event.data;
  if (!data || data.source !== "veillock-bridge") return;
  state.lifted = Boolean(data.lifted);
  state.key = hexToBytes(data.keyHex);
});
