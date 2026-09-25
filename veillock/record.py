"""Local AES-256-GCM recordings. The file is encryption at rest.

Video+audio, video-only, and audio-only all use the same chunk log.
Each chunk is sealed and flushed before the next one starts, so a crash
leaves sealed chunks and no plaintext. The key is not stored in the file.
Playback decrypts in memory. PulseCheck failure writes nothing further
and returns no plaintext.

Author: Aziel Eliab.
"""

from __future__ import annotations

import hashlib
import io
import os
import struct
from dataclasses import dataclass

import numpy as np

from veillock.crypto import (
    DecryptError,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    derive_frame_key,
    derive_nonce,
    rotate_session_key,
    zero_bytearray,
)
from veillock.engine import (
    DEFAULT_ROTATION_INTERVAL,
    EncryptedStream,
    VeilLockSession,
    load_cipher_npz,
    save_cipher_npz,
)
from veillock.honesty import LOCAL_RECORDING, PULSE
from veillock.pulse import AlwaysPass, HaltedError, PulseCheck

KIND = "veillock-aes-gcm-record"
AUDIO_INFO = b"veillock-audio-v1"
AUDIO_CHUNK = 3200
VAULT_MAGIC = b"VLRC"
VAULT_VERSION = 1
HEADER_LEN = 16
KIND_VIDEO = 1
KIND_AUDIO = 2
PREFIX_LEN = 21


@dataclass
class Playback:
    """Authorized playback of a local recording."""

    frames: np.ndarray
    pcm: np.ndarray | None
    sample_rate: int
    note: str


def _require_pass(pulse: PulseCheck | None) -> None:
    gate = pulse if pulse is not None else AlwaysPass()
    result = gate.pci()
    if result != "PASS":
        raise HaltedError(f"PCI did not PASS ({result!r}); recording refused. {PULSE}")


def _audio_root(session_key: bytes) -> bytearray:
    return bytearray(hashlib.sha256(bytes(session_key) + AUDIO_INFO).digest())


def seal_pcm(
    session_key: bytes,
    pcm: np.ndarray,
    *,
    rotation_interval: int = DEFAULT_ROTATION_INTERVAL,
    chunk: int = AUDIO_CHUNK,
) -> dict[str, np.ndarray]:
    """AES-256-GCM each PCM chunk under a key derived from the session key."""
    samples = np.ascontiguousarray(pcm, dtype=np.int16).ravel()
    audio_key = _audio_root(session_key)
    blobs: list[bytes] = []
    aads: list[bytes] = []
    nonces: list[bytes] = []
    indices: list[int] = []
    epochs: list[int] = []
    counts: list[int] = []
    idx = 0
    epoch = 0
    in_epoch = 0
    step = max(int(chunk), 1)
    try:
        if samples.size == 0:
            return _empty_audio()
        for off in range(0, int(samples.shape[0]), step):
            piece = samples[off : off + step]
            frame_key = derive_frame_key(bytes(audio_key), idx)
            nonce = derive_nonce(idx)
            aad = b"veillock-audio|" + str(idx).encode() + b"|" + str(epoch).encode()
            ct = aes_gcm_encrypt(frame_key, nonce, piece.tobytes(), aad)
            blobs.append(ct)
            aads.append(aad)
            nonces.append(nonce)
            indices.append(idx)
            epochs.append(epoch)
            counts.append(int(piece.shape[0]))
            idx += 1
            in_epoch += 1
            if in_epoch >= int(rotation_interval):
                nxt = rotate_session_key(bytes(audio_key), epoch)
                zero_bytearray(audio_key)
                audio_key = bytearray(nxt)
                epoch += 1
                in_epoch = 0
    finally:
        zero_bytearray(audio_key)
    return {
        "audio_blob": np.frombuffer(b"".join(blobs), dtype=np.uint8),
        "audio_lengths": np.array([len(b) for b in blobs], dtype=np.int64),
        "audio_aad_blob": np.frombuffer(b"".join(aads), dtype=np.uint8),
        "audio_aad_lengths": np.array([len(a) for a in aads], dtype=np.int64),
        "audio_nonces": np.frombuffer(b"".join(nonces), dtype=np.uint8),
        "audio_indices": np.array(indices, dtype=np.int64),
        "audio_epochs": np.array(epochs, dtype=np.int64),
        "audio_counts": np.array(counts, dtype=np.int64),
    }


def _empty_audio() -> dict[str, np.ndarray]:
    return {
        "audio_blob": np.zeros((0,), dtype=np.uint8),
        "audio_lengths": np.zeros((0,), dtype=np.int64),
        "audio_aad_blob": np.zeros((0,), dtype=np.uint8),
        "audio_aad_lengths": np.zeros((0,), dtype=np.int64),
        "audio_nonces": np.zeros((0,), dtype=np.uint8),
        "audio_indices": np.zeros((0,), dtype=np.int64),
        "audio_epochs": np.zeros((0,), dtype=np.int64),
        "audio_counts": np.zeros((0,), dtype=np.int64),
    }


def open_pcm(
    session_key: bytes,
    audio: dict[str, np.ndarray],
    *,
    rotation_interval: int = DEFAULT_ROTATION_INTERVAL,
) -> np.ndarray:
    """Decrypt PCM chunks. Wrong key raises DecryptError. Not a scramble inverse."""
    lengths = audio["audio_lengths"]
    if int(lengths.shape[0]) == 0:
        return np.zeros((0,), dtype=np.int16)
    blob = bytes(audio["audio_blob"])
    aad_blob = bytes(audio["audio_aad_blob"])
    aad_lengths = audio["audio_aad_lengths"]
    nonces = bytes(audio["audio_nonces"])
    indices = audio["audio_indices"]
    counts = audio["audio_counts"]
    audio_key = _audio_root(session_key)
    pieces: list[np.ndarray] = []
    off = 0
    aoff = 0
    noff = 0
    epoch = 0
    in_epoch = 0
    try:
        for i in range(int(lengths.shape[0])):
            clen = int(lengths[i])
            alen = int(aad_lengths[i])
            ct = blob[off : off + clen]
            aad = aad_blob[aoff : aoff + alen]
            nonce = nonces[noff : noff + 12]
            index = int(indices[i])
            frame_key = derive_frame_key(bytes(audio_key), index)
            plain = aes_gcm_decrypt(frame_key, nonce, ct, aad)
            count = int(counts[i])
            if len(plain) != count * 2:
                raise DecryptError("audio plaintext length does not match")
            pieces.append(np.frombuffer(plain, dtype=np.int16).copy())
            off += clen
            aoff += alen
            noff += 12
            in_epoch += 1
            if in_epoch >= int(rotation_interval):
                nxt = rotate_session_key(bytes(audio_key), epoch)
                zero_bytearray(audio_key)
                audio_key = bytearray(nxt)
                epoch += 1
                in_epoch = 0
    finally:
        zero_bytearray(audio_key)
    if not pieces:
        return np.zeros((0,), dtype=np.int16)
    return np.concatenate(pieces)


def save_recording(
    path: str,
    stream: EncryptedStream,
    *,
    session_key: bytes,
    pcm: np.ndarray | None = None,
    sample_rate: int = 16000,
    rotation_interval: int | None = None,
) -> None:
    """Write a .veilrec (npz) that holds AES-GCM video and optional PCM.

    The session key is not stored in the file.
    """
    bio = io.BytesIO()
    save_cipher_npz(bio, stream)
    bio.seek(0)
    with np.load(bio, allow_pickle=False) as z:
        data = {k: np.array(z[k]) for k in z.files}
    interval = int(rotation_interval if rotation_interval is not None else stream.rotation_interval)
    audio = seal_pcm(session_key, pcm if pcm is not None else np.zeros((0,), dtype=np.int16), rotation_interval=interval)
    data.update(audio)
    data["kind"] = np.array(KIND)
    data["honesty"] = np.array(LOCAL_RECORDING)
    data["crypto"] = np.array("AES-256-GCM")
    data["call_path"] = np.array("not-in-this-file")
    data["sample_rate"] = np.int64(sample_rate)
    with open(path, "wb") as fh:
        np.savez_compressed(fh, **data)


def _prefix(kind: int, epoch: int, index: int, width: int, height: int, count: int) -> bytes:
    return struct.pack("<BIQHHI", int(kind), int(epoch), int(index), int(width), int(height), int(count))


def _pack_header(sample_rate: int, rotation_interval: int) -> bytes:
    return VAULT_MAGIC + bytes((VAULT_VERSION, 0)) + struct.pack("<H", 0) + struct.pack("<I", int(sample_rate)) + struct.pack("<HH", int(rotation_interval), 0)


class ChunkVault:
    """Append-only AES-256-GCM log. Each chunk is flushed before the next plaintext is sealed."""

    def __init__(
        self,
        path: str,
        session_key: bytes,
        *,
        rotation_interval: int = DEFAULT_ROTATION_INTERVAL,
        pulse: PulseCheck | None = None,
        sample_rate: int = 16000,
    ) -> None:
        if len(session_key) != 32:
            raise ValueError("session_key must be 32 bytes")
        interval = int(rotation_interval)
        if not 60 <= interval <= 240:
            raise ValueError("rotation_interval must be in [60, 240]")
        self.path = path
        self.rotation_interval = interval
        self.sample_rate = int(sample_rate)
        self.pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self._video_key = bytearray(session_key)
        self._audio_key = _audio_root(session_key)
        self._v_index = 0
        self._v_epoch = 0
        self._v_in = 0
        self._a_index = 0
        self._a_epoch = 0
        self._a_in = 0
        self._wrote = 0
        self._fh = open(path, "wb")
        self._fh.write(_pack_header(self.sample_rate, interval))
        self._fh.flush()
        os.fsync(self._fh.fileno())

    @property
    def wrote(self) -> int:
        return self._wrote

    def write_video(self, frame: np.ndarray) -> None:
        self._gate()
        image = np.ascontiguousarray(frame, dtype=np.uint8)
        if image.ndim != 3 or image.shape[2] != 3:
            raise ValueError("frame must be HxWx3")
        plain = bytearray(image.tobytes())
        height, width = int(image.shape[0]), int(image.shape[1])
        prefix = _prefix(KIND_VIDEO, self._v_epoch, self._v_index, width, height, len(plain))
        try:
            sealed = self._seal(self._video_key, self._v_index, prefix, plain)
        finally:
            zero_bytearray(plain)
        self._append(sealed)
        self._v_index, self._v_epoch, self._v_in, self._video_key = _advance(
            self._video_key, self._v_index, self._v_epoch, self._v_in, self.rotation_interval
        )

    def write_audio(self, pcm: np.ndarray) -> None:
        samples = np.ascontiguousarray(pcm, dtype=np.int16).ravel()
        if samples.size == 0:
            return
        step = AUDIO_CHUNK
        for off in range(0, int(samples.shape[0]), step):
            self._gate()
            piece = np.ascontiguousarray(samples[off : off + step], dtype=np.int16)
            plain = bytearray(piece.tobytes())
            prefix = _prefix(KIND_AUDIO, self._a_epoch, self._a_index, 0, 0, int(piece.shape[0]))
            try:
                sealed = self._seal(self._audio_key, self._a_index, prefix, plain)
            finally:
                zero_bytearray(plain)
            self._append(sealed)
            self._a_index, self._a_epoch, self._a_in, self._audio_key = _advance(
                self._audio_key, self._a_index, self._a_epoch, self._a_in, self.rotation_interval
            )

    def close(self) -> None:
        zero_bytearray(self._video_key)
        zero_bytearray(self._audio_key)
        if self._fh is not None and not self._fh.closed:
            self._fh.flush()
            os.fsync(self._fh.fileno())
            self._fh.close()

    def _gate(self) -> None:
        result = self.pulse.pci()
        if result != "PASS":
            raise HaltedError(f"PCI did not PASS ({result!r}); recording refused. {PULSE}")

    def _seal(self, key: bytearray, index: int, prefix: bytes, plain: bytes) -> bytes:
        frame_key = derive_frame_key(bytes(key), int(index))
        nonce = derive_nonce(int(index))
        return prefix + aes_gcm_encrypt(frame_key, nonce, bytes(plain), prefix)

    def _append(self, body: bytes) -> None:
        self._fh.write(struct.pack(">I", len(body)) + body)
        self._fh.flush()
        os.fsync(self._fh.fileno())
        self._wrote += 1


def _advance(
    key: bytearray, index: int, epoch: int, in_epoch: int, interval: int
) -> tuple[int, int, int, bytearray]:
    index += 1
    in_epoch += 1
    if in_epoch >= int(interval):
        nxt = rotate_session_key(bytes(key), epoch)
        zero_bytearray(key)
        key = bytearray(nxt)
        epoch += 1
        in_epoch = 0
    return index, epoch, in_epoch, key


def _read_vault(path: str) -> tuple[int, int, list[bytes]]:
    with open(path, "rb") as fh:
        data = fh.read()
    if len(data) < HEADER_LEN or not data.startswith(VAULT_MAGIC):
        raise ValueError("not a VeilLock chunk recording")
    if data[4] != VAULT_VERSION:
        raise ValueError("unsupported VeilLock recording version")
    sample_rate, rotation = struct.unpack_from("<IH", data, 8)
    chunks: list[bytes] = []
    pos = HEADER_LEN
    while pos + 4 <= len(data):
        size = struct.unpack_from(">I", data, pos)[0]
        pos += 4
        if size < PREFIX_LEN + 16 or pos + size > len(data):
            break
        chunks.append(data[pos : pos + size])
        pos += size
    return int(sample_rate), int(rotation), chunks


def _open_chunk(body: bytes, video_key: bytearray, audio_key: bytearray) -> tuple[int, np.ndarray]:
    if len(body) < PREFIX_LEN + 16:
        raise DecryptError("sealed chunk is truncated")
    prefix = body[:PREFIX_LEN]
    kind, epoch, index, width, height, count = struct.unpack_from("<BIQHHI", prefix, 0)
    key = video_key if kind == KIND_VIDEO else audio_key
    if kind not in (KIND_VIDEO, KIND_AUDIO):
        raise DecryptError("unknown recording chunk")
    frame_key = derive_frame_key(bytes(key), int(index))
    plain = aes_gcm_decrypt(frame_key, derive_nonce(int(index)), body[PREFIX_LEN:], prefix)
    if kind == KIND_VIDEO:
        expect = int(width) * int(height) * 3
        if len(plain) != expect or int(count) != expect:
            raise DecryptError("video plaintext length does not match")
        frame = np.frombuffer(plain, dtype=np.uint8).copy().reshape((int(height), int(width), 3))
        return KIND_VIDEO, frame
    if len(plain) != int(count) * 2:
        raise DecryptError("audio plaintext length does not match")
    return KIND_AUDIO, np.frombuffer(plain, dtype=np.int16).copy()


def play_vault(
    path: str,
    session_key: bytes,
    *,
    pulse: PulseCheck | None = None,
) -> Playback:
    """Decrypt in memory. A wrong key raises before any plaintext is returned."""
    _require_pass(pulse)
    if len(session_key) != 32:
        raise ValueError("session_key must be 32 bytes")
    sample_rate, rotation, chunks = _read_vault(path)
    video_key = bytearray(session_key)
    audio_key = _audio_root(session_key)
    frames: list[np.ndarray] = []
    pieces: list[np.ndarray] = []
    v_epoch = 0
    v_in = 0
    a_epoch = 0
    a_in = 0
    try:
        for body in chunks:
            kind = body[0]
            try:
                got, array = _open_chunk(body, video_key, audio_key)
            except DecryptError:
                frames.clear()
                pieces.clear()
                raise
            if got == KIND_VIDEO:
                frames.append(array)
                v_in += 1
                if v_in >= rotation:
                    nxt = rotate_session_key(bytes(video_key), v_epoch)
                    zero_bytearray(video_key)
                    video_key = bytearray(nxt)
                    v_epoch += 1
                    v_in = 0
            else:
                pieces.append(array)
                a_in += 1
                if a_in >= rotation:
                    nxt = rotate_session_key(bytes(audio_key), a_epoch)
                    zero_bytearray(audio_key)
                    audio_key = bytearray(nxt)
                    a_epoch += 1
                    a_in = 0
    finally:
        zero_bytearray(video_key)
        zero_bytearray(audio_key)
    if frames:
        stack = np.stack(frames, axis=0)
    else:
        stack = np.zeros((0, 0, 0, 3), dtype=np.uint8)
    pcm = np.concatenate(pieces) if pieces else np.zeros((0,), dtype=np.int16)
    return Playback(frames=stack, pcm=pcm, sample_rate=sample_rate, note=LOCAL_RECORDING)


def seal_recording(
    path: str,
    frames: np.ndarray,
    session_key: bytes,
    *,
    pcm: np.ndarray | None = None,
    sample_rate: int = 16000,
    rotation_interval: int = DEFAULT_ROTATION_INTERVAL,
    pulse: PulseCheck | None = None,
    mode: str = "private",
    receiver_secret: bytes | None = None,
) -> EncryptedStream:
    """Seal frames and optional PCM chunk by chunk. Refuses on PulseCheck failure before creating the file."""
    _require_pass(pulse)
    if len(session_key) != 32:
        raise ValueError("session_key must be 32 bytes")
    video = None if frames is None else np.ascontiguousarray(frames, dtype=np.uint8)
    if video is not None and video.ndim == 3:
        video = video[None, ...]
    vault = ChunkVault(
        path,
        bytes(session_key),
        rotation_interval=int(rotation_interval),
        pulse=pulse,
        sample_rate=int(sample_rate),
    )
    try:
        if video is not None and video.size:
            for frame in video:
                vault.write_video(frame)
        if pcm is not None and int(np.asanyarray(pcm).size):
            vault.write_audio(np.asanyarray(pcm))
    finally:
        vault.close()
    return EncryptedStream(frames=[], mode=str(mode), rotation_interval=int(rotation_interval))


def load_recording(path: str) -> tuple[EncryptedStream, dict[str, np.ndarray], int, str]:
    with np.load(path, allow_pickle=False) as z:
        kind = str(z["kind"]) if "kind" in z.files else ""
        if kind != KIND:
            raise ValueError(f"not a VeilLock AES-GCM recording ({kind!r})")
        honesty = str(z["honesty"]) if "honesty" in z.files else LOCAL_RECORDING
        sample_rate = int(z["sample_rate"]) if "sample_rate" in z.files else 0
        audio = {
            "audio_blob": np.array(z["audio_blob"]),
            "audio_lengths": np.array(z["audio_lengths"]),
            "audio_aad_blob": np.array(z["audio_aad_blob"]),
            "audio_aad_lengths": np.array(z["audio_aad_lengths"]),
            "audio_nonces": np.array(z["audio_nonces"]),
            "audio_indices": np.array(z["audio_indices"]),
            "audio_epochs": np.array(z["audio_epochs"]),
            "audio_counts": np.array(z["audio_counts"]),
        }
    stream = load_cipher_npz(path)
    return stream, audio, sample_rate, honesty


def play_recording(
    path: str,
    session_key: bytes,
    *,
    pulse: PulseCheck | None = None,
    receiver_secret: bytes | None = None,
) -> Playback:
    """Decrypt a local recording in memory. Wrong key fails closed and returns nothing."""
    with open(path, "rb") as fh:
        magic = fh.read(4)
    if magic == VAULT_MAGIC:
        return play_vault(path, bytes(session_key), pulse=pulse)
    _require_pass(pulse)
    stream, audio, sample_rate, honesty = load_recording(path)
    session = VeilLockSession(
        session_key=bytes(session_key),
        rotation_interval=stream.rotation_interval,
        mode=stream.mode,
        receiver_secret=receiver_secret,
        pulse=pulse if pulse is not None else AlwaysPass(),
    )
    frames = session.decrypt_frames(stream)
    pcm = open_pcm(bytes(session_key), audio, rotation_interval=stream.rotation_interval)
    return Playback(frames=frames, pcm=pcm, sample_rate=sample_rate, note=honesty)
