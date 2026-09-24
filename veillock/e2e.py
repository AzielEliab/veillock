"""AES-256-GCM for encoded media between two VeilLock users.

The call app's own stream is not this. That stream is the veil or the
keyed scramble, which is obfuscation. This module seals bytes that an
encoder already produced: a browser's encoded frame, or the deflate
elementary stream from ``encode_picture``. Raw pixels are not the
plaintext.

Wire header (18 bytes), then AES-256-GCM ciphertext including the tag:

    VLK1 | version=1 | kind | epoch uint32 le | index uint64 le

AAD is that header. The frame key is SHA-256(epoch_key || index_le64).
The nonce is index_le64 || b"VLCK". Epoch keys ratchet with the same
rotate_session_key as the rest of VeilLock. Both ends need the root key.
A wrong key fails closed. PulseCheck failure produces no plaintext.

Author: Aziel Eliab.
"""

from __future__ import annotations

import socket
import struct
import threading
import zlib
from dataclasses import dataclass

import numpy as np

from veillock.crypto import (
    DecryptError,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    derive_frame_key,
    derive_nonce,
    rotate_session_key,
)
from veillock.pulse import AlwaysPass, HaltedError, PulseCheck

MAGIC = b"VLK1"
VERSION = 1
HEADER_LEN = 18
KIND_VIDEO = 1
KIND_AUDIO = 2
ELEMENTARY_MAGIC = b"VLZ1"


def key_at_epoch(root: bytes, epoch: int) -> bytes:
    """Ratchet the root key ``epoch`` times. Epoch 0 is the root."""
    if len(root) != 32:
        raise ValueError("root key must be 32 bytes")
    key = bytes(root)
    for step in range(int(epoch)):
        key = rotate_session_key(key, step)
    return key


def pack_header(kind: int, epoch: int, index: int) -> bytes:
    if int(kind) not in (KIND_VIDEO, KIND_AUDIO):
        raise ValueError("kind must be video or audio")
    if not 0 <= int(epoch) <= 0xFFFFFFFF:
        raise ValueError("epoch out of range")
    if not 0 <= int(index) <= 0xFFFFFFFFFFFFFFFF:
        raise ValueError("index out of range")
    return MAGIC + bytes((VERSION, int(kind))) + struct.pack("<IQ", int(epoch), int(index))


def seal_encoded(payload: bytes, root: bytes, *, index: int, epoch: int, kind: int) -> bytes:
    """Seal one already-encoded blob. The payload is not a raw picture."""
    header = pack_header(kind, epoch, index)
    frame_key = derive_frame_key(key_at_epoch(root, epoch), int(index))
    nonce = derive_nonce(int(index))
    return header + aes_gcm_encrypt(frame_key, nonce, bytes(payload), header)


def open_encoded(blob: bytes, root: bytes, *, pulse: PulseCheck | None = None) -> tuple[bytes, int]:
    """Return (encoded payload, kind). Wrong key, tamper, or a bad header fails closed."""
    gate = pulse if pulse is not None else AlwaysPass()
    if gate.pci() != "PASS":
        raise HaltedError("PCI did not PASS; encoded plaintext is not produced")
    raw = bytes(blob)
    if len(raw) < HEADER_LEN + 16 or not raw.startswith(MAGIC):
        raise DecryptError("not a VeilLock encoded frame")
    if raw[4] != VERSION:
        raise DecryptError("unsupported encoded-frame version")
    kind = raw[5]
    if kind not in (KIND_VIDEO, KIND_AUDIO):
        raise DecryptError("unknown encoded-frame kind")
    epoch, index = struct.unpack_from("<IQ", raw, 6)
    header = raw[:HEADER_LEN]
    frame_key = derive_frame_key(key_at_epoch(root, epoch), index)
    try:
        payload = aes_gcm_decrypt(frame_key, derive_nonce(index), raw[HEADER_LEN:], header)
    except DecryptError:
        raise
    except Exception as exc:  # noqa: BLE001
        raise DecryptError("AES-GCM authentication failed") from exc
    return payload, kind


class EncodedChannel:
    """Sender state: index, epoch, and PulseCheck. The receiver only needs the root key."""

    def __init__(
        self,
        root: bytes,
        *,
        rotation_interval: int = 120,
        pulse: PulseCheck | None = None,
    ) -> None:
        if len(root) != 32:
            raise ValueError("root key must be 32 bytes")
        interval = int(rotation_interval)
        if not 60 <= interval <= 240:
            raise ValueError("rotation_interval must be in [60, 240]")
        self.root = bytes(root)
        self.rotation_interval = interval
        self.pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self.index = 0
        self.epoch = 0
        self._in_epoch = 0

    def seal(self, payload: bytes, kind: int = KIND_VIDEO) -> bytes:
        if self.pulse.pci() != "PASS":
            raise HaltedError("PCI did not PASS; encoded plaintext is not sealed")
        blob = seal_encoded(payload, self.root, index=self.index, epoch=self.epoch, kind=kind)
        self.index += 1
        self._in_epoch += 1
        if self._in_epoch >= self.rotation_interval:
            self.epoch += 1
            self._in_epoch = 0
        return blob


def choose_payload(camera: bytes, veil: bytes, *, lifted: bool, pulse_ok: bool) -> bytes | None:
    """What may be sealed. Pulse failure seals nothing. A closed veil seals the veil, not the camera."""
    if not pulse_ok:
        return None
    if not lifted:
        return bytes(veil)
    return bytes(camera)


def encode_picture(frame: np.ndarray) -> bytes:
    """Deflate elementary stream. This is not H.264, VP8, or VP9.

    The VeilLock TCP channel has no lossy codec in the middle, so AES-GCM
    of this stream is the encryption. The browser path instead seals the
    encoded frames the browser already produced.
    """
    image = np.ascontiguousarray(frame, dtype=np.uint8)
    if image.ndim != 3 or image.shape[2] != 3:
        raise ValueError("frame must be HxWx3")
    height, width = int(image.shape[0]), int(image.shape[1])
    if height > 65535 or width > 65535:
        raise ValueError("frame dimension out of range")
    body = zlib.compress(image.tobytes(), 9)
    return ELEMENTARY_MAGIC + struct.pack("<HH", width, height) + body


def decode_picture(blob: bytes) -> np.ndarray:
    raw = bytes(blob)
    if len(raw) < 8 or not raw.startswith(ELEMENTARY_MAGIC):
        raise ValueError("not a VeilLock elementary picture")
    width, height = struct.unpack_from("<HH", raw, 4)
    pixels = zlib.decompress(raw[8:])
    frame = np.frombuffer(pixels, dtype=np.uint8)
    expected = int(width) * int(height) * 3
    if frame.size != expected:
        raise ValueError("elementary picture has the wrong size")
    return frame.reshape((height, width, 3)).copy()


def encode_pcm(samples: np.ndarray) -> bytes:
    pcm = np.ascontiguousarray(samples, dtype=np.int16).ravel()
    return b"VLA1" + struct.pack("<I", int(pcm.shape[0])) + zlib.compress(pcm.tobytes(), 9)


def decode_pcm(blob: bytes) -> np.ndarray:
    raw = bytes(blob)
    if len(raw) < 8 or not raw.startswith(b"VLA1"):
        raise ValueError("not a VeilLock elementary audio blob")
    count = struct.unpack_from("<I", raw, 4)[0]
    pcm = np.frombuffer(zlib.decompress(raw[8:]), dtype=np.int16)
    if int(pcm.shape[0]) != int(count):
        raise ValueError("elementary audio has the wrong size")
    return pcm.copy()


@dataclass
class RelayCapture:
    """Bytes a relay or observer forwarded. This is the ciphertext, not the camera."""

    forwarded: list[bytes]

    def saw_plaintext(self, secret: bytes) -> bool:
        raw = bytes(secret)
        return any(raw in blob for blob in self.forwarded)


def exchange_over_relay(
    payloads: list[bytes],
    root: bytes,
    *,
    kind: int = KIND_VIDEO,
    veil: bytes | None = None,
    lifted: bool = False,
    pulse_ok: bool = True,
    rotation_interval: int = 120,
    peer_key: bytes | None = None,
) -> tuple[list[bytes], RelayCapture]:
    """Seal, let a relay copy the blobs, then open them with the peer key.

    The relay's copies are what an observer sees. ``peer_key`` defaults to
    the sender root. A different key fails closed on open.
    """
    channel = EncodedChannel(root, rotation_interval=rotation_interval)
    wire: list[bytes] = []
    for payload in payloads:
        chosen = choose_payload(payload, veil if veil is not None else b"", lifted=lifted, pulse_ok=pulse_ok)
        if chosen is None:
            continue
        wire.append(channel.seal(chosen, kind))
    relay = RelayCapture(forwarded=[bytes(blob) for blob in wire])
    opener = peer_key if peer_key is not None else root
    opened: list[bytes] = []
    for blob in relay.forwarded:
        payload, got_kind = open_encoded(blob, opener)
        if got_kind != kind:
            raise DecryptError("encoded frame kind changed in transit")
        opened.append(payload)
    return opened, relay


def send_blobs(sock: socket.socket, blobs: list[bytes]) -> None:
    for blob in blobs:
        sock.sendall(struct.pack(">I", len(blob)) + blob)
    try:
        sock.shutdown(socket.SHUT_WR)
    except OSError:
        pass


def recv_blobs(sock: socket.socket) -> list[bytes]:
    buf = bytearray()
    while True:
        chunk = sock.recv(65536)
        if not chunk:
            break
        buf.extend(chunk)
    out: list[bytes] = []
    offset = 0
    while offset + 4 <= len(buf):
        size = struct.unpack_from(">I", buf, offset)[0]
        offset += 4
        if size > 8_000_000 or offset + size > len(buf):
            raise ValueError("truncated encoded frame on the link")
        out.append(bytes(buf[offset : offset + size]))
        offset += size
    return out


def tcp_relay(blobs: list[bytes]) -> list[bytes]:
    """Localhost sender → copying relay → receiver. The relay keeps the ciphertext."""
    received: list[bytes] = []
    ready = threading.Event()
    holder: dict[str, socket.socket] = {}

    def _recv() -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind(("127.0.0.1", 0))
        srv.listen(1)
        holder["port"] = srv
        ready.set()
        conn, _addr = srv.accept()
        try:
            received.extend(recv_blobs(conn))
        finally:
            conn.close()
            srv.close()

    thread = threading.Thread(target=_recv, daemon=True)
    thread.start()
    ready.wait(2)
    port = holder["port"].getsockname()[1]
    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(("127.0.0.1", port))
    try:
        send_blobs(client, blobs)
    finally:
        client.close()
    thread.join(2)
    return received
