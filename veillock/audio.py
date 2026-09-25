"""Call-path audio veil and optional PCM block scramble.

Default public audio is comfort noise, not the microphone. The optional
scramble permutes short blocks and may flip their sign. That survives
only a codec that keeps each block's waveform. It does not survive a
codec that rebuilds phase. It is not AES-256-GCM.

AES-256-GCM for audio lives in ``veillock.record`` (the local recording).

Author: Aziel Eliab.
"""

from __future__ import annotations

import hashlib
import hmac

import numpy as np

from veillock.honesty import CALL_AUDIO

AUDIO_BLOCK = 320


def _u32_stream(key: bytes, label: bytes, n: int) -> list[int]:
    out: list[int] = []
    counter = 0
    buf = b""
    need = max(int(n), 0)
    while len(out) < need:
        buf += hmac.new(key, label + counter.to_bytes(4, "little"), hashlib.sha256).digest()
        counter += 1
        while len(buf) >= 4 and len(out) < need:
            out.append(int.from_bytes(buf[:4], "little"))
            buf = buf[4:]
    return out


def _check_key(key: bytes) -> bytes:
    raw = bytes(key)
    if len(raw) != 32:
        raise ValueError("audio key must be 32 bytes")
    return raw


def _order(nblk: int, key: bytes, epoch: int) -> list[int]:
    stream = _u32_stream(key, b"aperm" + int(epoch).to_bytes(8, "little"), max(nblk, 1))
    order = list(range(nblk))
    for i in range(nblk - 1, 0, -1):
        j = stream[nblk - 1 - i] % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def comfort_noise(n: int, rng: np.random.Generator, amplitude: int = 180) -> np.ndarray:
    """Quiet noise used as the audio veil. Not a copy of the microphone."""
    count = int(n)
    if count < 0:
        raise ValueError("n must be >= 0")
    if count == 0:
        return np.zeros((0,), dtype=np.int16)
    amp = int(np.clip(amplitude, 1, 2000))
    return rng.integers(-amp, amp, size=count, dtype=np.int16)


def scramble_pcm(samples: np.ndarray, key: bytes, epoch: int = 0, block: int = AUDIO_BLOCK) -> np.ndarray:
    """Permute PCM blocks. Obfuscation only. See CALL_AUDIO."""
    key_b = _check_key(key)
    x = np.ascontiguousarray(samples, dtype=np.int16).ravel()
    n = int(x.shape[0])
    blk = int(block)
    if blk < 2:
        raise ValueError("audio block must be >= 2")
    pad = (-n) % blk
    if pad:
        x = np.concatenate([x, np.zeros(pad, dtype=np.int16)])
    nblk = len(x) // blk
    if nblk == 0:
        return np.zeros((n,), dtype=np.int16)
    order = _order(nblk, key_b, int(epoch))
    signs = _u32_stream(key_b, b"asign" + int(epoch).to_bytes(8, "little"), nblk)
    pieces = [x[i * blk : (i + 1) * blk].astype(np.int32) for i in range(nblk)]
    out = np.empty(nblk * blk, dtype=np.int32)
    for dest in range(nblk):
        src_i = order[dest]
        chunk = pieces[src_i]
        if signs[src_i] & 1:
            chunk = -chunk
        out[dest * blk : (dest + 1) * blk] = chunk
    clipped = np.clip(out, -32768, 32767).astype(np.int16)
    return clipped[:n]


def unveil_pcm(samples: np.ndarray, key: bytes, epoch: int = 0, block: int = AUDIO_BLOCK) -> np.ndarray:
    """Inverse of ``scramble_pcm`` for the same epoch. Not an AES decrypt."""
    key_b = _check_key(key)
    x = np.ascontiguousarray(samples, dtype=np.int16).ravel()
    n = int(x.shape[0])
    blk = int(block)
    pad = (-n) % blk
    if pad:
        x = np.concatenate([x, np.zeros(pad, dtype=np.int16)])
    nblk = len(x) // blk
    if nblk == 0:
        return np.zeros((n,), dtype=np.int16)
    order = _order(nblk, key_b, int(epoch))
    signs = _u32_stream(key_b, b"asign" + int(epoch).to_bytes(8, "little"), nblk)
    pieces: list[np.ndarray | None] = [None] * nblk
    for dest in range(nblk):
        src_i = order[dest]
        chunk = x[dest * blk : (dest + 1) * blk].astype(np.int32)
        if signs[src_i] & 1:
            chunk = -chunk
        pieces[src_i] = np.clip(chunk, -32768, 32767).astype(np.int16)
    out = np.concatenate(pieces)
    return out[:n]


def audio_note() -> str:
    return CALL_AUDIO
