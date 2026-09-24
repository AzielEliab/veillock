"""Local AES-256-GCM recordings. This file is encryption.

The call app's recording is a different thing: it only has the veil or
the scramble. PulseCheck failure raises before any plaintext is written.

Author: Aziel Eliab.
"""

from __future__ import annotations

import hashlib
import io
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
    """Seal frames (and optional PCM) to ``path``. Refuses on PulseCheck failure."""
    _require_pass(pulse)
    if len(session_key) != 32:
        raise ValueError("session_key must be 32 bytes")
    session = VeilLockSession(
        session_key=bytes(session_key),
        rotation_interval=int(rotation_interval),
        mode=mode,
        receiver_secret=receiver_secret,
        pulse=pulse if pulse is not None else AlwaysPass(),
    )
    stream = session.encrypt_frames(frames)
    save_recording(
        path,
        stream,
        session_key=bytes(session_key),
        pcm=pcm,
        sample_rate=sample_rate,
        rotation_interval=int(rotation_interval),
    )
    return stream


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
    """Decrypt a local recording. Wrong key fails closed."""
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
