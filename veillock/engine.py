"""Layer 2/3 — Frame Encryption Engine and Trusted Decode Surface.

VeilLockSession is the library entry point.

Pipeline: render → encrypt → decode locally → display.
Plaintext lives in the engine framebuffer only for the duration of
encrypt; it is zeroed before encrypt_frame returns.
"""

from __future__ import annotations

import json
import secrets
from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence

import numpy as np

from veillock.crypto import (
    DecryptError,
    aes_gcm_decrypt,
    aes_gcm_encrypt,
    derive_frame_key,
    derive_nonce,
    rotate_session_key,
    unwrap_session_key,
    wrap_session_key,
    zero_bytearray,
)
from veillock.metadata import build_headers, pack_aad
from veillock.modes import Mode, synthetic_ui_noise
from veillock.phoenix import DEFAULT_PHOENIX_THRESHOLD, PhoenixLoop
from veillock.pulse import AlwaysPass, HaltedError, PhoenixError, PulseCheck

DEFAULT_ROTATION_INTERVAL = 120
MIN_ROTATION_INTERVAL = 60
MAX_ROTATION_INTERVAL = 240


@dataclass
class EncryptedFrame:
    """One sealed visual frame plus public headers (already scrubbed)."""

    ciphertext: bytes
    nonce: bytes
    frame_index: int
    shape: tuple[int, int, int]
    epoch: int
    aad: bytes
    headers: dict[str, Any]
    decoy: np.ndarray | None = None


@dataclass
class EncryptedStream:
    """A sequence of sealed frames plus mode extras (wrapped key, decoys)."""

    frames: list[EncryptedFrame] = field(default_factory=list)
    mode: str = Mode.PRIVATE.value
    rotation_interval: int = DEFAULT_ROTATION_INTERVAL
    wrapped_key: bytes | None = None
    decoy: np.ndarray | None = None  # (N, H, W, C) when mode is obfuscation


class VeilLockSession:
    """Continuous stream encryption with forward-secure key rotation.

    Parameters
    ----------
    session_key:
        32-byte root key. Generated if omitted. Private mode never writes
        this key into the ciphertext package.
    rotation_interval:
        Rotate the session key every N frames. Default 120, range 60–240.
    mode:
        ``private``, ``broadcast`` (secure_broadcast), or ``obfuscation``.
    pulse:
        PulseCheck consulted before any plaintext is produced.
    phoenix_threshold:
        Failed PCI / decode-mismatch count that enters Phoenix Loop.
    receiver_secret:
        For broadcast mode, wraps the *root* session key for receivers.
    """

    def __init__(
        self,
        session_key: bytes | None = None,
        rotation_interval: int = DEFAULT_ROTATION_INTERVAL,
        mode: str | Mode = Mode.PRIVATE,
        pulse: PulseCheck | None = None,
        phoenix_threshold: int = DEFAULT_PHOENIX_THRESHOLD,
        receiver_secret: bytes | None = None,
        rng: np.random.Generator | None = None,
    ) -> None:
        interval = int(rotation_interval)
        if not (MIN_ROTATION_INTERVAL <= interval <= MAX_ROTATION_INTERVAL):
            raise ValueError(
                f"rotation_interval must be in "
                f"[{MIN_ROTATION_INTERVAL}, {MAX_ROTATION_INTERVAL}]"
            )
        if session_key is None:
            key = secrets.token_bytes(32)
        else:
            key = bytes(session_key)
            if len(key) != 32:
                raise ValueError("session_key must be 32 bytes")

        self.rotation_interval = interval
        self.mode = Mode.parse(mode)
        self.pulse: PulseCheck = pulse if pulse is not None else AlwaysPass()
        self.phoenix = PhoenixLoop(threshold=int(phoenix_threshold))
        self.receiver_secret = bytes(receiver_secret) if receiver_secret is not None else None
        self._rng = rng if rng is not None else np.random.default_rng()

        # Root key is held only long enough to wrap for broadcast, then the
        # ratchet buffer is the sole in-memory key. We keep a wrapped copy
        # (not the raw root) for the ciphertext package.
        self._wrapped_key: bytes | None = None
        if self.mode is Mode.BROADCAST:
            if self.receiver_secret is None:
                raise ValueError("broadcast mode requires receiver_secret")
            self._wrapped_key = wrap_session_key(key, self.receiver_secret)

        self._session_key = bytearray(key)
        # Drop the local ``key`` binding; ratchet state is _session_key only.
        del key

        self._frame_index = 0
        self._epoch_index = 0
        self._in_epoch = 0
        self._framebuffer = np.zeros((0, 0, 3), dtype=np.uint8)

    # --- inspected by tests -------------------------------------------------

    @property
    def framebuffer(self) -> np.ndarray:
        """Engine framebuffer. After encrypt_frame this is all zeros."""
        return self._framebuffer

    @property
    def current_key(self) -> bytes:
        """Copy of the *current* (possibly rotated) session key.

        Compromising this value must not decrypt older epochs: previous
        keys are dropped on rotation.
        """
        return bytes(self._session_key)

    @property
    def frame_index(self) -> int:
        return self._frame_index

    @property
    def epoch_index(self) -> int:
        return self._epoch_index

    @property
    def wrapped_key(self) -> bytes | None:
        return self._wrapped_key

    # --- gate ---------------------------------------------------------------

    def _gate(self, *, for_decrypt: bool = False) -> None:
        """Refuse work when PCI fails or Phoenix is holding the session."""
        if self.phoenix.active:
            if self.phoenix.try_restore(self.pulse):
                self._reboot_keys()
            else:
                raise PhoenixError(
                    "phoenix mode: refusing encrypt/decrypt until PCI PASS"
                )
        result = self.pulse.pci()
        if result != "PASS":
            entered = self.phoenix.record_failure()
            if entered:
                self._reboot_keys()
                raise PhoenixError(
                    "phoenix mode: repeated integrity failure; session rebooted"
                )
            raise HaltedError(f"PCI did not PASS ({result!r}); no plaintext produced")

    def _reboot_keys(self) -> None:
        """Phoenix reboot: drop current key material, mint a fresh session."""
        zero_bytearray(self._session_key)
        self._session_key = bytearray(secrets.token_bytes(32))
        self._frame_index = 0
        self._epoch_index = 0
        self._in_epoch = 0
        if self._framebuffer.size:
            self._framebuffer.fill(0)
        if self.mode is Mode.BROADCAST and self.receiver_secret is not None:
            self._wrapped_key = wrap_session_key(bytes(self._session_key), self.receiver_secret)

    def _advance(self) -> None:
        self._frame_index += 1
        self._in_epoch += 1
        if self._in_epoch >= self.rotation_interval:
            new_key = rotate_session_key(bytes(self._session_key), self._epoch_index)
            zero_bytearray(self._session_key)
            self._session_key = bytearray(new_key)
            self._epoch_index += 1
            self._in_epoch = 0

    def record_tamper(self) -> None:
        """External decode-mismatch / display tamper signal."""
        entered = self.phoenix.record_failure()
        if entered:
            self._reboot_keys()

    # --- Layer 2 encrypt ----------------------------------------------------

    def encrypt_frame(
        self,
        frame: np.ndarray,
        metadata: Mapping[str, Any] | None = None,
    ) -> EncryptedFrame:
        """Encrypt one RGB uint8 frame. Engine framebuffer is zeroed on return."""
        self._gate()

        src = np.ascontiguousarray(frame, dtype=np.uint8)
        if src.ndim != 3 or src.shape[-1] != 3:
            raise ValueError("frame must have shape (H, W, 3) uint8")

        self._framebuffer = np.empty(src.shape, dtype=np.uint8)
        np.copyto(self._framebuffer, src)

        headers = build_headers(
            frame_index=self._frame_index,
            shape=(int(src.shape[0]), int(src.shape[1]), int(src.shape[2])),
            epoch=self._epoch_index,
            metadata=metadata,
            mode=self.mode.value,
        )
        aad = pack_aad(headers)
        frame_key = derive_frame_key(bytes(self._session_key), self._frame_index)
        nonce = derive_nonce(self._frame_index)
        plaintext_mv = memoryview(self._framebuffer).cast("B")
        ciphertext = aes_gcm_encrypt(frame_key, nonce, plaintext_mv.tobytes(), aad)

        # Drop key material for this frame and zero the engine framebuffer.
        if isinstance(frame_key, bytearray):
            zero_bytearray(frame_key)
        self._framebuffer.fill(0)

        decoy = None
        if self.mode is Mode.OBFUSCATION:
            decoy = synthetic_ui_noise(src.shape, self._rng)

        sealed = EncryptedFrame(
            ciphertext=ciphertext,
            nonce=nonce,
            frame_index=headers["frame_index"],
            shape=(headers["height"], headers["width"], headers["channels"]),
            epoch=headers["epoch"],
            aad=aad,
            headers=headers,
            decoy=decoy,
        )
        self._advance()
        return sealed

    def encrypt_frames(
        self,
        frames: np.ndarray | Iterable[np.ndarray],
        metadata: Sequence[Mapping[str, Any] | None] | Mapping[str, Any] | None = None,
    ) -> EncryptedStream:
        """Encrypt a stack or iterable of RGB frames."""
        stack = _as_frame_list(frames)
        sealed: list[EncryptedFrame] = []
        for i, fr in enumerate(stack):
            meta: Mapping[str, Any] | None
            if metadata is None:
                meta = None
            elif isinstance(metadata, Mapping):
                meta = metadata
            else:
                meta = metadata[i] if i < len(metadata) else None
            sealed.append(self.encrypt_frame(fr, metadata=meta))

        decoy = None
        if self.mode is Mode.OBFUSCATION and sealed:
            decoy = np.stack(
                [
                    s.decoy if s.decoy is not None else np.zeros(s.shape, dtype=np.uint8)
                    for s in sealed
                ],
                axis=0,
            )
        return EncryptedStream(
            frames=sealed,
            mode=self.mode.value,
            rotation_interval=self.rotation_interval,
            wrapped_key=self._wrapped_key,
            decoy=decoy,
        )

    # --- Layer 3 decrypt ----------------------------------------------------

    def decrypt_frame(self, sealed: EncryptedFrame) -> np.ndarray:
        """Authorized decrypt of one frame. Advances the ratchet in lockstep."""
        self._gate(for_decrypt=True)
        frame_key = derive_frame_key(bytes(self._session_key), sealed.frame_index)
        try:
            plaintext = aes_gcm_decrypt(frame_key, sealed.nonce, sealed.ciphertext, sealed.aad)
        except DecryptError:
            entered = self.phoenix.record_failure()
            if entered:
                self._reboot_keys()
                raise PhoenixError(
                    "phoenix mode: decode mismatch; session rebooted"
                ) from None
            raise
        h, w, c = sealed.shape
        expected = h * w * c
        if len(plaintext) != expected:
            raise DecryptError("plaintext length does not match frame shape")
        out = np.frombuffer(plaintext, dtype=np.uint8).reshape(h, w, c).copy()
        self._advance()
        return out

    def decrypt_frames(self, stream: EncryptedStream) -> np.ndarray:
        frames = [self.decrypt_frame(s) for s in stream.frames]
        if not frames:
            return np.zeros((0, 0, 0, 3), dtype=np.uint8)
        return np.stack(frames, axis=0)

    def protect_frame(
        self,
        frame: np.ndarray,
        metadata: Mapping[str, Any] | None = None,
    ) -> tuple[EncryptedFrame, np.ndarray]:
        """Encrypt then immediately decode for the trusted local surface.

        Decrypt uses the pre-advance key (same epoch as the sealed frame)
        by reconstructing from the ciphertext with a one-frame rewind of
        the ratchet: we decrypt *before* ``_advance`` inside a dedicated
        path so the local display never needs retained epoch keys.
        """
        self._gate()
        src = np.ascontiguousarray(frame, dtype=np.uint8)
        if src.ndim != 3 or src.shape[-1] != 3:
            raise ValueError("frame must have shape (H, W, 3) uint8")

        self._framebuffer = np.empty(src.shape, dtype=np.uint8)
        np.copyto(self._framebuffer, src)
        headers = build_headers(
            frame_index=self._frame_index,
            shape=(int(src.shape[0]), int(src.shape[1]), int(src.shape[2])),
            epoch=self._epoch_index,
            metadata=metadata,
            mode=self.mode.value,
        )
        aad = pack_aad(headers)
        frame_key = derive_frame_key(bytes(self._session_key), self._frame_index)
        nonce = derive_nonce(self._frame_index)
        ciphertext = aes_gcm_encrypt(
            frame_key, nonce, memoryview(self._framebuffer).cast("B").tobytes(), aad
        )
        display = aes_gcm_decrypt(frame_key, nonce, ciphertext, aad)
        self._framebuffer.fill(0)
        h, w, c = headers["height"], headers["width"], headers["channels"]
        display_arr = np.frombuffer(display, dtype=np.uint8).reshape(h, w, c).copy()
        decoy = synthetic_ui_noise(src.shape, self._rng) if self.mode is Mode.OBFUSCATION else None
        sealed = EncryptedFrame(
            ciphertext=ciphertext,
            nonce=nonce,
            frame_index=headers["frame_index"],
            shape=(h, w, c),
            epoch=headers["epoch"],
            aad=aad,
            headers=headers,
            decoy=decoy,
        )
        self._advance()
        return sealed, display_arr


def _as_frame_list(frames: np.ndarray | Iterable[np.ndarray]) -> list[np.ndarray]:
    if isinstance(frames, np.ndarray):
        if frames.ndim == 4:
            return [frames[i] for i in range(frames.shape[0])]
        if frames.ndim == 3:
            return [frames]
        raise ValueError("ndarray frames must be (H,W,3) or (N,H,W,3)")
    return [np.ascontiguousarray(f, dtype=np.uint8) for f in frames]


def save_cipher_npz(path: str, stream: EncryptedStream) -> None:
    """Write an EncryptedStream without pickle (concatenated blobs + lengths)."""
    blobs = [f.ciphertext for f in stream.frames]
    aads = [f.aad for f in stream.frames]
    headers = [f.headers for f in stream.frames]
    blob = np.frombuffer(b"".join(blobs), dtype=np.uint8) if blobs else np.zeros((0,), dtype=np.uint8)
    aad_blob = np.frombuffer(b"".join(aads), dtype=np.uint8) if aads else np.zeros((0,), dtype=np.uint8)
    headers_json = json.dumps(headers, separators=(",", ":"), default=_json_default).encode("utf-8")
    decoy = stream.decoy if stream.decoy is not None else np.zeros((0,), dtype=np.uint8)
    wrapped = (
        np.frombuffer(stream.wrapped_key, dtype=np.uint8)
        if stream.wrapped_key is not None
        else np.zeros((0,), dtype=np.uint8)
    )
    n = len(stream.frames)
    if n:
        shape = np.array([n, *stream.frames[0].shape], dtype=np.int64)
        indices = np.array([f.frame_index for f in stream.frames], dtype=np.int64)
        epochs = np.array([f.epoch for f in stream.frames], dtype=np.int64)
        nonces = np.frombuffer(b"".join(f.nonce for f in stream.frames), dtype=np.uint8)
    else:
        shape = np.array([0, 0, 0, 3], dtype=np.int64)
        indices = np.zeros((0,), dtype=np.int64)
        epochs = np.zeros((0,), dtype=np.int64)
        nonces = np.zeros((0,), dtype=np.uint8)
    np.savez_compressed(
        path,
        blob=blob,
        lengths=np.array([len(b) for b in blobs], dtype=np.int64),
        aad_blob=aad_blob,
        aad_lengths=np.array([len(a) for a in aads], dtype=np.int64),
        headers_json=np.frombuffer(headers_json, dtype=np.uint8),
        indices=indices,
        epochs=epochs,
        nonces=nonces,
        shape=shape,
        mode=np.array(stream.mode),
        rotation_interval=np.int64(stream.rotation_interval),
        wrapped_key=wrapped,
        decoy=decoy,
    )


def load_cipher_npz(path: str) -> EncryptedStream:
    with np.load(path, allow_pickle=False) as z:
        lengths = z["lengths"]
        blob = bytes(z["blob"])
        aad_lengths = z["aad_lengths"]
        aad_blob = bytes(z["aad_blob"])
        headers = json.loads(bytes(z["headers_json"]).decode("utf-8") or "[]")
        indices = z["indices"]
        epochs = z["epochs"]
        nonces_b = bytes(z["nonces"])
        shape = [int(x) for x in z["shape"]]
        mode = str(z["mode"])
        rotation_interval = int(z["rotation_interval"])
        wrapped_raw = bytes(z["wrapped_key"])
        wrapped_key = wrapped_raw if len(wrapped_raw) else None
        decoy_arr = z["decoy"]
        decoy = decoy_arr if decoy_arr.ndim == 4 else None

    frames: list[EncryptedFrame] = []
    off = 0
    aoff = 0
    noff = 0
    n = int(shape[0])
    hw = (int(shape[1]), int(shape[2]), int(shape[3])) if n else (0, 0, 3)
    for i in range(n):
        clen = int(lengths[i])
        alen = int(aad_lengths[i])
        ct = blob[off : off + clen]
        aad = aad_blob[aoff : aoff + alen]
        nonce = nonces_b[noff : noff + 12]
        off += clen
        aoff += alen
        noff += 12
        hdr = headers[i] if i < len(headers) else {}
        sh = (
            int(hdr.get("height", hw[0])),
            int(hdr.get("width", hw[1])),
            int(hdr.get("channels", hw[2])),
        )
        decoy_i = decoy[i] if decoy is not None else None
        frames.append(
            EncryptedFrame(
                ciphertext=ct,
                nonce=nonce,
                frame_index=int(indices[i]),
                shape=sh,
                epoch=int(epochs[i]),
                aad=aad,
                headers=hdr,
                decoy=decoy_i,
            )
        )
    return EncryptedStream(
        frames=frames,
        mode=mode,
        rotation_interval=rotation_interval,
        wrapped_key=wrapped_key,
        decoy=decoy,
    )


def _json_default(obj: Any) -> Any:
    if isinstance(obj, (bytes, bytearray)):
        return bytes(obj).hex()
    if isinstance(obj, np.integer):
        return int(obj)
    raise TypeError(f"not JSON serializable: {type(obj)!r}")


def session_from_wrapped(
    wrapped_key: bytes,
    receiver_secret: bytes,
    **kwargs: Any,
) -> VeilLockSession:
    """Open a decrypt session from a broadcast wrapped root key."""
    root = unwrap_session_key(wrapped_key, receiver_secret)
    return VeilLockSession(
        session_key=root,
        mode=kwargs.pop("mode", Mode.BROADCAST),
        receiver_secret=receiver_secret,
        **kwargs,
    )
