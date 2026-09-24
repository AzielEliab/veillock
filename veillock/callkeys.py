"""Out-of-band keys for a VeilLock call.

The 32-byte value is a shared secret. It drives the call scramble
(obfuscation) and, if you record, the local AES-256-GCM file. The call
provider does not receive it.

Three ways to agree, all outside the video codec:

- a pre-shared 32-byte key you already hold
- the existing HMAC-wrapped broadcast key (AES-GCM wraps the key, not the pixels)
- X25519, then HKDF-SHA256

Author: Aziel Eliab.
"""

from __future__ import annotations

import secrets

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric.x25519 import X25519PrivateKey, X25519PublicKey
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from veillock.crypto import unwrap_session_key, wrap_session_key

HKDF_SALT = b"veillock-x25519-v1"
HKDF_INFO = b"call-scramble-root"


def random_psk() -> bytes:
    """32-byte pre-shared key."""
    return secrets.token_bytes(32)


def generate_x25519() -> tuple[bytes, bytes]:
    """Return (private_key, public_key), each 32 raw bytes."""
    priv = X25519PrivateKey.generate()
    priv_b = priv.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pub_b = priv.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return priv_b, pub_b


def agree_x25519(private_key: bytes, peer_public: bytes) -> bytes:
    """Derive the 32-byte call key. Both peers get the same bytes."""
    if len(private_key) != 32 or len(peer_public) != 32:
        raise ValueError("X25519 keys must be 32 bytes")
    priv = X25519PrivateKey.from_private_bytes(bytes(private_key))
    pub = X25519PublicKey.from_public_bytes(bytes(peer_public))
    shared = priv.exchange(pub)
    return HKDF(
        algorithm=hashes.SHA256(),
        length=32,
        salt=HKDF_SALT,
        info=HKDF_INFO,
    ).derive(shared)


def wrap_call_key(call_key: bytes, receiver_secret: bytes) -> bytes:
    """AES-GCM wrap of the call key. The wrap is encryption; the pixels are not."""
    if len(call_key) != 32:
        raise ValueError("call key must be 32 bytes")
    return wrap_session_key(bytes(call_key), bytes(receiver_secret))


def unwrap_call_key(wrapped: bytes, receiver_secret: bytes) -> bytes:
    key = unwrap_session_key(bytes(wrapped), bytes(receiver_secret))
    if len(key) != 32:
        raise ValueError("unwrapped call key must be 32 bytes")
    return key
