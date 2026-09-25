"""Synthetic lossy codecs for tests. No camera, no libx264, no libopus.

``jpeg_like`` is an 8×8 DCT quantizer with the JPEG luminance table.
It stands in for an intra frame of a call encoder (H.264/VP8/VP9/AV1
family). It is not a measurement of Zoom, Meet, or any product.

``spectral_quantize_pcm`` keeps a rough waveform when the codec frame
lines up with a scramble block. ``phase_discard_pcm`` rebuilds each
block from magnitudes only, which is closer to what a speech codec does
to phase. Neither function is Opus or AAC.

Author: Aziel Eliab.
"""

from __future__ import annotations

import numpy as np

_JPEG_Q = np.array(
    [
        16, 11, 10, 16, 24, 40, 51, 61,
        12, 12, 14, 19, 26, 58, 60, 55,
        14, 13, 16, 24, 40, 57, 69, 56,
        14, 17, 22, 29, 51, 87, 80, 62,
        18, 22, 37, 56, 68, 109, 103, 77,
        24, 35, 55, 64, 81, 104, 113, 92,
        49, 64, 78, 87, 103, 121, 120, 101,
        72, 92, 95, 98, 112, 100, 103, 99,
    ],
    dtype=np.float64,
).reshape(8, 8)


def _dct_matrix(n: int = 8) -> np.ndarray:
    c = np.zeros((n, n), dtype=np.float64)
    for k in range(n):
        alpha = np.sqrt(1.0 / n) if k == 0 else np.sqrt(2.0 / n)
        for i in range(n):
            c[k, i] = alpha * np.cos((2 * i + 1) * k * np.pi / (2 * n))
    return c


_C = _dct_matrix(8)


def jpeg_quality_table(quality: int) -> np.ndarray:
    """JPEG quantizer scale. Quality is 1–100. This is the standard map, not a benchmark."""
    q = int(np.clip(int(quality), 1, 100))
    scale = 5000.0 / q if q < 50 else 200.0 - 2.0 * q
    table = np.floor((_JPEG_Q * scale + 50.0) / 100.0)
    return np.clip(table, 1.0, 255.0)


def jpeg_like(frame: np.ndarray, quality: int = 40, *, chroma_420: bool = False) -> np.ndarray:
    """Recompress one RGB uint8 frame with an 8×8 DCT quantizer.

    Optional ``chroma_420`` downsamples the G and B planes 2×2 before the
    DCT, then nearest-neighbor upsamples them. That is a harsh stand-in
    for 4:2:0 video, not a claim about a specific encoder.
    """
    src = np.ascontiguousarray(frame, dtype=np.uint8)
    if src.ndim != 3 or src.shape[-1] != 3:
        raise ValueError("frame must have shape (H, W, 3) uint8")
    h, w, _ = src.shape
    if h < 8 or w < 8:
        return src.copy()
    work = src.astype(np.float64)
    if chroma_420:
        # Box-filter 4:2:0 stand-in: average each 2×2 of G and B, then
        # replicate. Point sampling was harsher than a call encoder.
        for ch in (1, 2):
            plane = work[:, :, ch]
            hh2, ww2 = h - (h % 2), w - (w % 2)
            small = plane[:hh2, :ww2].reshape(hh2 // 2, 2, ww2 // 2, 2).mean(axis=(1, 3))
            up = np.repeat(np.repeat(small, 2, axis=0), 2, axis=1)
            work[:hh2, :ww2, ch] = up
    hh, ww = h - (h % 8), w - (w % 8)
    plane = work[:hh, :ww] - 128.0
    bh, bw = hh // 8, ww // 8
    blocks = plane.reshape(bh, 8, bw, 8, 3).swapaxes(1, 2)
    coeff = np.einsum("ki,abijc,lj->abklc", _C, blocks, _C, optimize=True)
    qt = jpeg_quality_table(quality)
    quant = np.round(coeff / qt[None, None, :, :, None]) * qt[None, None, :, :, None]
    rec = np.einsum("ki,abklc,lj->abijc", _C, quant, _C, optimize=True)
    tiled = np.ascontiguousarray(np.swapaxes(rec, 1, 2).reshape(hh, ww, 3))
    out = work.copy()
    out[:hh, :ww] = tiled + 128.0
    return np.clip(np.round(out), 0, 255).astype(np.uint8)


def spectral_quantize_pcm(
    samples: np.ndarray,
    block: int = 320,
    *,
    keep: float = 0.5,
    step: float = 32.0,
) -> np.ndarray:
    """Per-block FFT crop and quantize. Aligned blocks stay ordered.

    This simulator does not overlap frames. A real Opus/AAC encoder does.
    Use it only to show that a block permutation can be undone when the
    codec happens to leave each block's waveform roughly intact.
    """
    x = np.ascontiguousarray(samples, dtype=np.int16).ravel()
    nblk = len(x) // int(block)
    if nblk < 1:
        return x.copy()
    usable = nblk * int(block)
    spec = np.fft.rfft(x[:usable].reshape(nblk, int(block)).astype(np.float64), axis=1)
    k = max(1, int(spec.shape[1] * float(keep)))
    spec[:, k:] = 0
    spec = np.round(spec.real / step) * step + 1j * (np.round(spec.imag / step) * step)
    rec = np.fft.irfft(spec, n=int(block), axis=1)
    out = np.clip(np.round(rec.ravel()), -32768, 32767).astype(np.int16)
    if usable != len(x):
        out = np.concatenate([out, x[usable:]])
    return out


def phase_discard_pcm(samples: np.ndarray, block: int = 320) -> np.ndarray:
    """Rebuild each block from quantized magnitudes and zero phase.

    Correlation with the original waveform collapses. That is the honest
    stand-in for a speech codec that does not preserve samples. It is
    not a measurement of Opus or AAC.
    """
    x = np.ascontiguousarray(samples, dtype=np.int16).ravel()
    nblk = len(x) // int(block)
    if nblk < 1:
        return x.copy()
    usable = nblk * int(block)
    spec = np.fft.rfft(x[:usable].reshape(nblk, int(block)).astype(np.float64), axis=1)
    mag = np.abs(spec)
    mag[:, mag.shape[1] // 2 :] = 0
    mag = np.round(mag / 32.0) * 32.0
    rec = np.fft.irfft(mag + 0j, n=int(block), axis=1)
    out = np.clip(np.round(rec.ravel()), -32768, 32767).astype(np.int16)
    if usable != len(x):
        out = np.concatenate([out, x[usable:]])
    return out
