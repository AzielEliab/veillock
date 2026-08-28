"""Per-frame AES-256-GCM, forward-secure session-key rotation, key wrap.

frame_key = SHA-256(session_key || frame_index_le64)  # 32 bytes, AES-256
nonce     = 12 bytes derived from frame_index (unique per index)
rotation  = session_key = SHA-256(session_key || b"rotate" || epoch_index_le64)
            after every rotation_interval frames; old key is dropped.
"""

from __future__ import annotations

import hashlib
import hmac
from typing import ByteString

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

WRAP_INFO = b"veillock-wrap"
WRAP_AAD = b"veillock-keywrap"
NONCE_TAIL = b"VLCK"


class CryptoError(Exception):
    """Cipher or key-wrap failure."""


class DecryptError(CryptoError):
    """GCM authentication failed (wrong key, truncated ciphertext, or tamper)."""


def derive_frame_key(session_key: bytes, frame_index: int) -> bytes:
    """SHA-256(session_key || frame_index as little-endian uint64).

    The digest is 32 bytes; those bytes are the AES-256 key.
    """
    idx = int(frame_index).to_bytes(8, "little", signed=False)
    return hashlib.sha256(session_key + idx).digest()


def derive_nonce(frame_index: int) -> bytes:
    """12-byte GCM nonce unique for this frame_index."""
    return int(frame_index).to_bytes(8, "little", signed=False) + NONCE_TAIL


def rotate_session_key(session_key: bytes, epoch_index: int) -> bytes:
    """Forward-secure ratchet: SHA-256(session_key || b'rotate' || epoch_index_le64)."""
    epoch = int(epoch_index).to_bytes(8, "little", signed=False)
    return hashlib.sha256(session_key + b"rotate" + epoch).digest()


def aes_gcm_encrypt(frame_key: bytes, nonce: bytes, plaintext: bytes, aad: bytes) -> bytes:
    if len(frame_key) != 32:
        raise CryptoError("AES-256 key must be 32 bytes")
    if len(nonce) != 12:
        raise CryptoError("GCM nonce must be 12 bytes")
    return AESGCM(frame_key).encrypt(nonce, plaintext, aad)


def aes_gcm_decrypt(frame_key: bytes, nonce: bytes, ciphertext: bytes, aad: bytes) -> bytes:
    if len(frame_key) != 32:
        raise CryptoError("AES-256 key must be 32 bytes")
    if len(nonce) != 12:
        raise CryptoError("GCM nonce must be 12 bytes")
    try:
        return AESGCM(frame_key).decrypt(nonce, ciphertext, aad)
    except InvalidTag as exc:
        raise DecryptError("AES-GCM authentication failed") from exc


def wrap_session_key(session_key: bytes, receiver_secret: bytes) -> bytes:
    """HMAC-derived AES-GCM wrap of the session key for authorized receivers.

    KEK = SHA-256(b"veillock-wrap" || receiver_secret)
    nonce is derived from the secret so wrap is deterministic for tests.
    """
    if not receiver_secret:
        raise CryptoError("receiver_secret must be non-empty")
    kek = hashlib.sha256(WRAP_INFO + receiver_secret).digest()
    nonce = hashlib.sha256(WRAP_INFO + b"-nonce" + receiver_secret).digest()[:12]
    return AESGCM(kek).encrypt(nonce, session_key, WRAP_AAD)


def unwrap_session_key(wrapped: bytes, receiver_secret: bytes) -> bytes:
    if not receiver_secret:
        raise CryptoError("receiver_secret must be non-empty")
    kek = hashlib.sha256(WRAP_INFO + receiver_secret).digest()
    nonce = hashlib.sha256(WRAP_INFO + b"-nonce" + receiver_secret).digest()[:12]
    try:
        return AESGCM(kek).decrypt(nonce, wrapped, WRAP_AAD)
    except InvalidTag as exc:
        raise DecryptError("key-unwrap authentication failed") from exc


def hmac_confirm(session_key: bytes, receiver_secret: bytes) -> bytes:
    """Optional HMAC tag over the wrapped-key context (tests / extra AAD)."""
    return hmac.new(receiver_secret, session_key, hashlib.sha256).digest()


def zero_bytearray(buf: bytearray) -> None:
    for i in range(len(buf)):
        buf[i] = 0


def sha256_bytes(data: ByteString) -> bytes:
    return hashlib.sha256(bytes(data)).digest()
