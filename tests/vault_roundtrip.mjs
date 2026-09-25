import { openChunk, sealAudioChunk, sealVideoChunk } from "../extension/vault.js";

const [mode, payloadHex, keyHex, index, epoch, kind, width, height] = process.argv.slice(2);

function fromHex(hex) {
  const out = new Uint8Array(hex.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = parseInt(hex.slice(i * 2, i * 2 + 2), 16);
  return out;
}

function toHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

const payload = fromHex(payloadHex);
const key = fromHex(keyHex);

if (mode === "seal") {
  const body = Number(kind) === 1
    ? await sealVideoChunk(payload, key, Number(index), Number(epoch), Number(width), Number(height))
    : await sealAudioChunk(payload, key, Number(index), Number(epoch));
  process.stdout.write(toHex(body));
} else if (mode === "open") {
  try {
    const plain = await openChunk(payload, key, key);
    process.stdout.write(toHex(plain));
  } catch (err) {
    process.stderr.write(String(err && err.message ? err.message : err));
    process.exit(1);
  }
} else {
  process.exit(2);
}
