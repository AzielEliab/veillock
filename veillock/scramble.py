"""Keyed visual scramble that can survive a lossy video codec.

This is obfuscation. It is not AES-256-GCM. AES-GCM ciphertext painted
into pixels does not survive H.264, VP8, VP9, or AV1. The call provider
sees shuffled 8×8 tiles (or the natural veil when consent is still on).
An authorized peer reverses the same permutation after capture.

The top 8 rows are a sync strip (magic, epoch, keyed check), not picture.

Author: Aziel Eliab.
"""

from __future__ import annotations

import hashlib
import hmac
from dataclasses import dataclass

import numpy as np

from veillock.honesty import CALL_VIDEO
from veillock.modes import natural_camera_veil

BLOCK = 8
MAGIC = (0, 1, 0, 1)
_DARK = 96.0
_BRIGHT = 160.0


@dataclass
class UnveilResult:
    """What a peer gets from one captured call frame."""

    image: np.ndarray
    authorized: bool
    kind: str
    epoch: int | None
    note: str


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


def header_layout(width: int, block: int = BLOCK) -> tuple[int, int, int, int, int]:
    """Return (cells, magic_cells, epoch_bits, top_mac_cells, mac_bits).

    The keyed check uses the rest of the top row plus the whole bottom
    row, so a wrong key is rejected instead of shown as shuffled tiles.
    Width must be at least 128.
    """
    cells = int(width) // int(block)
    magic = len(MAGIC)
    if cells < 16:
        raise ValueError(
            f"frame width {width} is too narrow for a scramble sync strip "
            f"({cells} cells of {block}px; need at least 16, width >= 128)"
        )
    epoch_bits = 16 if cells >= 24 else 8
    top_mac = cells - magic - epoch_bits
    if top_mac < 4:
        epoch_bits = 4
        top_mac = cells - magic - epoch_bits
    mac_bits = top_mac + cells
    return cells, magic, epoch_bits, top_mac, mac_bits


def _mask_epoch(epoch: int, epoch_bits: int) -> int:
    return int(epoch) & ((1 << int(epoch_bits)) - 1)


def public_epoch(width: int, epoch: int, block: int = BLOCK) -> int:
    """Epoch bits that fit in the sync strip. Audio must use this same integer."""
    _cells, _magic, ebits, _top_mac, _mac_bits = header_layout(int(width), block)
    return _mask_epoch(epoch, ebits)


def _permutation(n: int, key: bytes, epoch: int) -> list[int]:
    stream = _u32_stream(key, b"perm" + int(epoch).to_bytes(8, "little"), max(n, 1))
    order = list(range(n))
    for i in range(n - 1, 0, -1):
        j = stream[n - 1 - i] % (i + 1)
        order[i], order[j] = order[j], order[i]
    return order


def _apply_transform(block: np.ndarray, word: int, *, inverse: bool) -> np.ndarray:
    rot = int(word) & 3
    neg = (int(word) >> 2) & 1
    # A channel swap does not survive 4:2:0, which call codecs use.
    # The sign flip is the color transform that still reverses.
    b = np.ascontiguousarray(block, dtype=np.uint8)
    if not inverse:
        if neg:
            b = np.bitwise_xor(b, np.uint8(255))
        b = np.rot90(b, k=-rot)
    else:
        b = np.rot90(b, k=rot)
        if neg:
            b = np.bitwise_xor(b, np.uint8(255))
    return np.ascontiguousarray(b, dtype=np.uint8)


def _paint(frame: np.ndarray, col: int, value: int, block: int = BLOCK) -> None:
    frame[0:block, col * block : (col + 1) * block] = np.uint8(value)


def _cell_bit_at(frame: np.ndarray, row: int, col: int, block: int = BLOCK) -> int | None:
    y = int(row) * block
    x = int(col) * block
    cell = frame[y : y + block, x : x + block]
    mean = float(cell.mean())
    if mean < _DARK:
        return 0
    if mean > _BRIGHT:
        return 1
    return None


def _cell_bit(frame: np.ndarray, col: int, block: int = BLOCK) -> int | None:
    return _cell_bit_at(frame, 0, col, block)


def _mac_bit(mac: bytes, index: int) -> int:
    return (mac[index // 8] >> (index % 8)) & 1


def _write_checks(frame: np.ndarray, mac: bytes, *, magic: int, ebits: int, top_mac: int, block: int) -> None:
    cells = frame.shape[1] // block
    for i in range(top_mac):
        _paint(frame, magic + ebits + i, 255 if _mac_bit(mac, i) else 0, block)
    bottom = frame.shape[0] // block - 1
    for i in range(cells):
        bit = _mac_bit(mac, top_mac + i)
        y = bottom * block
        x = i * block
        frame[y : y + block, x : x + block] = np.uint8(255 if bit else 0)


def _checks_match(frame: np.ndarray, mac: bytes, *, magic: int, ebits: int, top_mac: int, mac_bits: int, block: int) -> bool:
    cells = frame.shape[1] // block
    for i in range(top_mac):
        if _cell_bit(frame, magic + ebits + i, block) != _mac_bit(mac, i):
            return False
    bottom = frame.shape[0] // block - 1
    for i in range(cells):
        if _cell_bit_at(frame, bottom, i, block) != _mac_bit(mac, top_mac + i):
            return False
    return mac_bits == top_mac + cells


def _mac(key: bytes, epoch: int, height: int, width: int) -> bytes:
    msg = (
        b"mac"
        + int(epoch).to_bytes(8, "little")
        + int(height).to_bytes(2, "little")
        + int(width).to_bytes(2, "little")
    )
    return hmac.new(key, msg, hashlib.sha256).digest()


def _check_key(key: bytes) -> bytes:
    raw = bytes(key)
    if len(raw) != 32:
        raise ValueError("scramble key must be 32 bytes")
    return raw


def has_scramble_magic(frame: np.ndarray, block: int = BLOCK) -> bool:
    """True when the sync strip looks like a VeilLock scramble, key or not."""
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[0] < block or src.shape[1] < block * len(MAGIC):
        return False
    try:
        header_layout(int(src.shape[1]), block)
    except ValueError:
        return False
    for i, expected in enumerate(MAGIC):
        if _cell_bit(src, i, block) != expected:
            return False
    return True


def scramble_frame(frame: np.ndarray, key: bytes, epoch: int = 0, block: int = BLOCK) -> np.ndarray:
    """Return the public call image. Picture tiles are obfuscated, not AES-sealed."""
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    key_b = _check_key(key)
    h, w, _ = (int(src.shape[0]), int(src.shape[1]), 3)
    if h % block or w % block or h < block * 3:
        raise ValueError(
            f"scramble frame must be a multiple of {block} and at least {block * 3}px tall "
            f"(got {h}x{w})"
        )
    _cells, magic, ebits, top_mac, _mac_bits = header_layout(w, block)
    epoch_i = _mask_epoch(epoch, ebits)
    body_h = h // block - 2
    body_w = w // block
    n = body_h * body_w
    order = _permutation(n, key_b, epoch_i)
    words = _u32_stream(key_b, b"xfm" + epoch_i.to_bytes(8, "little"), n)
    blocks = []
    for by in range(body_h):
        for bx in range(body_w):
            y, x = (by + 1) * block, bx * block
            blocks.append(src[y : y + block, x : x + block].copy())
    out = np.full_like(src, 128)
    for i, bit in enumerate(MAGIC):
        _paint(out, i, 255 if bit else 0, block)
    for i in range(ebits):
        bit = (epoch_i >> (ebits - 1 - i)) & 1
        _paint(out, magic + i, 255 if bit else 0, block)
    mac = _mac(key_b, epoch_i, h, w)
    _write_checks(out, mac, magic=magic, ebits=ebits, top_mac=top_mac, block=block)
    for dest in range(n):
        src_i = order[dest]
        tile = _apply_transform(blocks[src_i], words[src_i], inverse=False)
        by, bx = divmod(dest, body_w)
        y, x = (by + 1) * block, bx * block
        out[y : y + block, x : x + block] = tile
    return out


def _refuse(shape: tuple[int, int, int], kind: str, note: str, epoch: int | None = None) -> UnveilResult:
    rng = np.random.default_rng(int.from_bytes(hashlib.sha256(note.encode()).digest()[:8], "little"))
    veil = natural_camera_veil(shape, rng, tick=0)
    return UnveilResult(image=veil, authorized=False, kind=kind, epoch=epoch, note=note)


def unveil_frame(frame: np.ndarray, key: bytes, block: int = BLOCK) -> UnveilResult:
    """Reverse a captured scramble. Wrong key or a plain veil returns a veil, not tiles."""
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    key_b = _check_key(key)
    h, w, c = (int(src.shape[0]), int(src.shape[1]), 3)
    shape = (h, w, c)
    if h % block or w % block or h < block * 3:
        return _refuse(shape, "not-scramble", "Captured frame is not a VeilLock scramble grid. " + CALL_VIDEO)
    try:
        _cells, magic, ebits, top_mac, mac_bits = header_layout(w, block)
    except ValueError:
        return _refuse(shape, "not-scramble", "Captured frame has no scramble sync strip. " + CALL_VIDEO)
    if not has_scramble_magic(src, block):
        return UnveilResult(
            image=src.copy(),
            authorized=False,
            kind="not-scramble",
            epoch=None,
            note="No scramble sync strip. Nothing to unveil. " + CALL_VIDEO,
        )
    epoch = 0
    for i in range(ebits):
        bit = _cell_bit(src, magic + i, block)
        if bit is None:
            return _refuse(shape, "damaged", "Epoch strip did not survive the codec. " + CALL_VIDEO)
        epoch = (epoch << 1) | bit
    mac = _mac(key_b, epoch, h, w)
    if not _checks_match(src, mac, magic=magic, ebits=ebits, top_mac=top_mac, mac_bits=mac_bits, block=block):
        return _refuse(
            shape,
            "unauthorized",
            "Key check failed. The call stays veiled. The scramble is not AES-256-GCM. " + CALL_VIDEO,
            epoch=epoch,
        )
    body_h = h // block - 2
    body_w = w // block
    n = body_h * body_w
    order = _permutation(n, key_b, epoch)
    words = _u32_stream(key_b, b"xfm" + int(epoch).to_bytes(8, "little"), n)
    tiles: list[np.ndarray | None] = [None] * n
    for dest in range(n):
        by, bx = divmod(dest, body_w)
        y, x = (by + 1) * block, bx * block
        src_i = order[dest]
        tiles[src_i] = _apply_transform(src[y : y + block, x : x + block], words[src_i], inverse=True)
    out = np.zeros_like(src)
    k = 0
    for by in range(body_h):
        for bx in range(body_w):
            y, x = (by + 1) * block, bx * block
            tile = tiles[k]
            if tile is None:
                return _refuse(shape, "damaged", "Scramble grid was incomplete. " + CALL_VIDEO, epoch=epoch)
            out[y : y + block, x : x + block] = tile
            k += 1
    return UnveilResult(
        image=out,
        authorized=True,
        kind="scramble",
        epoch=epoch,
        note="Authorized approximate recovery of the picture below the sync strip. " + CALL_VIDEO,
    )
