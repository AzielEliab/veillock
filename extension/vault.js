/**
 * AES-256-GCM chunk recording. Same bytes as veillock.record.ChunkVault.
 * Playback decrypts in memory. This file does not write plaintext.
 *
 * Author: Aziel Eliab.
 */

const TEXT = new TextEncoder();

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

function u64le(value) {
  const out = new Uint8Array(8);
  const view = new DataView(out.buffer);
  const big = BigInt(value);
  view.setUint32(0, Number(big & 0xffffffffn), true);
  view.setUint32(4, Number((big >> 32n) & 0xffffffffn), true);
  return out;
}

async function sha256(bytes) {
  return new Uint8Array(await crypto.subtle.digest("SHA-256", bytes));
}

async function epochKey(root, epoch) {
  let key = root;
  for (let step = 0; step < epoch; step += 1) {
    key = await sha256(concat([key, TEXT.encode("rotate"), u64le(step)]));
  }
  return key;
}

function prefix(kind, epoch, index, width, height, count) {
  const out = new Uint8Array(21);
  const view = new DataView(out.buffer);
  out[0] = kind;
  view.setUint32(1, epoch, true);
  view.setBigUint64(5, BigInt(index), true);
  view.setUint16(13, width, true);
  view.setUint16(15, height, true);
  view.setUint32(17, count, true);
  return out;
}

async function sealBody(plain, root, index, epoch, kind, width, height, count) {
  const epoched = await epochKey(root, epoch);
  const frameKey = await sha256(concat([epoched, u64le(index)]));
  const head = prefix(kind, epoch, index, width, height, count);
  const nonce = concat([u64le(index), TEXT.encode("VLCK")]);
  const key = await crypto.subtle.importKey("raw", frameKey, "AES-GCM", false, ["encrypt"]);
  const cipher = new Uint8Array(
    await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce, additionalData: head }, key, plain)
  );
  return concat([head, cipher]);
}

export async function sealVideoChunk(frameBytes, root, index, epoch, width, height) {
  return sealBody(frameBytes, root, index, epoch, 1, width, height, frameBytes.length);
}

export async function sealAudioChunk(pcmBytes, root, index, epoch) {
  return sealBody(pcmBytes, root, index, epoch, 2, 0, 0, pcmBytes.length / 2);
}

export async function openChunk(body, videoRoot, audioRoot) {
  const view = new DataView(body.buffer, body.byteOffset, body.byteLength);
  const kind = body[0];
  const epoch = view.getUint32(1, true);
  const index = Number(view.getBigUint64(5, true));
  const root = kind === 1 ? videoRoot : audioRoot;
  const epoched = await epochKey(root, epoch);
  const frameKey = await sha256(concat([epoched, u64le(index)]));
  const head = body.slice(0, 21);
  const nonce = concat([u64le(index), TEXT.encode("VLCK")]);
  const key = await crypto.subtle.importKey("raw", frameKey, "AES-GCM", false, ["decrypt"]);
  try {
    const plain = new Uint8Array(
      await crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce, additionalData: head }, key, body.slice(21))
    );
    return plain;
  } catch (_err) {
    throw new Error("AES-GCM authentication failed");
  }
}

export function encodeFile(sampleRate, rotation, bodies) {
  const header = new Uint8Array(16);
  const view = new DataView(header.buffer);
  header.set(TEXT.encode("VLRC"), 0);
  header[4] = 1;
  view.setUint32(8, sampleRate, true);
  view.setUint16(12, rotation, true);
  const parts = [header];
  for (const body of bodies) {
    const len = new Uint8Array(4);
    new DataView(len.buffer).setUint32(0, body.length, false);
    parts.push(len, body);
  }
  return concat(parts);
}
