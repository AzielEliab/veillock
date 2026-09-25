import { readFileSync } from "node:fs";
import { attachEncodedStreams, openEncoded, pickDevice, sealEncoded } from "../extension/e2e.js";

const [mode, ...rest] = process.argv.slice(2);

function fromHex(hex) {
  const clean = hex.trim();
  const out = new Uint8Array(clean.length / 2);
  for (let i = 0; i < out.length; i += 1) out[i] = parseInt(clean.slice(i * 2, i * 2 + 2), 16);
  return out;
}

function toHex(bytes) {
  return [...bytes].map((b) => b.toString(16).padStart(2, "0")).join("");
}

if (mode === "seal") {
  const [payloadHex, keyHex, index, epoch, kind] = rest;
  const sealed = await sealEncoded(fromHex(payloadHex), fromHex(keyHex), Number(index), Number(epoch), Number(kind));
  process.stdout.write(toHex(sealed));
} else if (mode === "open") {
  const [blobHex, keyHex] = rest;
  try {
    const opened = await openEncoded(fromHex(blobHex), fromHex(keyHex));
    process.stdout.write(toHex(opened.payload));
  } catch (err) {
    process.stderr.write(String(err && err.message ? err.message : err));
    process.exit(1);
  }
} else if (mode === "pick") {
  const devices = JSON.parse(readFileSync(rest[0], "utf8"));
  const lifted = rest[1] === "1";
  const video = pickDevice(devices, "videoinput", lifted);
  const audio = pickDevice(devices, "audioinput", lifted);
  process.stdout.write(JSON.stringify({ video, audio }));
} else if (mode === "streams") {
  const frames = [];
  const sender = {
    createEncodedStreams() {
      const readable = new ReadableStream({
        start(controller) {
          controller.enqueue({ data: new Uint8Array([1, 2, 3, 4]).buffer });
          controller.close();
        },
      });
      const writable = new WritableStream({
        write(frame) {
          frames.push(new Uint8Array(frame.data));
        },
      });
      return { readable, writable };
    },
  };
  const attached = attachEncodedStreams(sender, async (data) => {
    const out = new Uint8Array(data.length + 1);
    out.set(data, 0);
    out[data.length] = 9;
    return out;
  });
  await attached.done;
  process.stdout.write(JSON.stringify({ attached: attached.attached, reason: attached.reason, length: frames[0] ? frames[0].length : 0, last: frames[0] ? frames[0][frames[0].length - 1] : null }));
} else if (mode === "no-streams") {
  const attached = attachEncodedStreams({}, async (data) => data);
  process.stdout.write(JSON.stringify(attached));
} else {
  process.stderr.write("unknown mode");
  process.exit(2);
}
