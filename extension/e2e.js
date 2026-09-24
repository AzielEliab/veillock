/**
 * Encoded-frame AES-256-GCM. Same bytes as veillock.e2e.
 *
 * Header: VLK1 | version 1 | kind | epoch uint32 le | index uint64 le
 * AAD is the header. Frame key is SHA-256(epochKey || index_le64).
 * Nonce is index_le64 || "VLCK". Both browsers need this extension and the key.
 *
 * Author: Aziel Eliab.
 */

export const KIND_VIDEO = 1;
export const KIND_AUDIO = 2;

function concat(parts) {
  const size = parts.reduce((sum, part) => sum + part.length, 0);
  const out = new Uint8Array(size);
  let offset = 0;
  for (const part of parts) {
    out.set(part, offset);
    offset += part.length;
  }
  return out;
}

function u32le(value) {
  const out = new Uint8Array(4);
  new DataView(out.buffer).setUint32(0, value, true);
  return out;
}

function u64le(value) {
  const out = new Uint8Array(8);
  const view = new DataView(out.buffer);
  const big = BigInt(value);
  view.setUint32(0, Number(big & 0xffffffffn), true);
  view.setUint32(4, Number((big >> 32n) & 0xffffffffn), true);
  return out;
}

async function sha256(bytes) {
  const digest = await crypto.subtle.digest("SHA-256", bytes);
  return new Uint8Array(digest);
}

async function epochKey(root, epoch) {
  let key = root;
  for (let step = 0; step < epoch; step += 1) {
    const label = new TextEncoder().encode("rotate");
    const mixed = concat([key, label, u64le(step)]);
    key = await sha256(mixed);
  }
  return key;
}

function headerBytes(kind, epoch, index) {
  const magic = new TextEncoder().encode("VLK1");
  return concat([magic, new Uint8Array([1, kind]), u32le(epoch), u64le(index)]);
}

async function aesKey(raw) {
  return crypto.subtle.importKey("raw", raw, "AES-GCM", false, ["encrypt", "decrypt"]);
}

export async function sealEncoded(payload, root, index, epoch, kind) {
  const header = headerBytes(kind, epoch, index);
  const epoched = await epochKey(root, epoch);
  const frame = await sha256(concat([epoched, u64le(index)]));
  const nonce = concat([u64le(index), new TextEncoder().encode("VLCK")]);
  const key = await aesKey(frame);
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: header }, key, payload)
  );
  return concat([header, cipher]);
}

export async function openEncoded(blob, root) {
  if (blob.length < 18 + 16) {
    throw new Error("not a VeilLock encoded frame");
  }
  const magic = new TextDecoder().decode(blob.slice(0, 4));
  if (magic !== "VLK1" || blob[4] !== 1) {
    throw new Error("not a VeilLock encoded frame");
  }
  const kind = blob[5];
  const view = new DataView(blob.buffer, blob.byteOffset, blob.byteLength);
  const epoch = view.getUint32(6, true);
  const index = Number(view.getBigUint64(10, true));
  const header = blob.slice(0, 18);
  const epoched = await epochKey(root, epoch);
  const frame = await sha256(concat([epoched, u64le(index)]));
  const nonce = concat([u64le(index), new TextEncoder().encode("VLCK")]);
  const key = await aesKey(frame);
  try {
    const plain = new Uint8Array(
      await crypto.subtle.decrypt(
        { name: "AES-GCM", iv: nonce, additionalData: header },
        key,
        blob.slice(18)
      )
    );
    return { payload: plain, kind };
  } catch (_err) {
    throw new Error("AES-GCM authentication failed");
  }
}

const MIC_LABEL = /veillock|blackhole|cable output/i;

export function pickDevice(devices, kind, lifted) {
  if (!lifted) {
    return { mode: "veil", deviceId: null };
  }
  const match = (devices || []).find((device) => {
    if (device.kind !== kind) return false;
    const label = String(device.label || "");
    if (kind === "videoinput") return /veillock/i.test(label);
    return MIC_LABEL.test(label);
  });
  if (!match) {
    return { mode: "veil", deviceId: null };
  }
  return { mode: "device", deviceId: match.deviceId };
}

export function attachEncodedStreams(sender, sealFrame) {
  if (!sender || typeof sender.createEncodedStreams !== "function") {
    return { attached: false, reason: "createEncodedStreams is not available" };
  }
  const streams = sender.createEncodedStreams();
  const transform = new TransformStream({
    async transform(frame, controller) {
      const data = new Uint8Array(frame.data);
      const sealed = await sealFrame(data);
      frame.data = sealed.buffer.slice(sealed.byteOffset, sealed.byteOffset + sealed.byteLength);
      controller.enqueue(frame);
    },
  });
  const done = streams.readable.pipeThrough(transform).pipeTo(streams.writable);
  return { attached: true, reason: "AES-256-GCM on encoded frames", done };
}
