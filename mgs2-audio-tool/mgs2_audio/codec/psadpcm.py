#!/usr/bin/env python3
"""
psadpcm.py — PlayStation 4-bit ADPCM (PS-ADPCM / VAG) codec.

This module knows nothing about Metal Gear Solid: it only turns PS-ADPCM frames
into 16-bit PCM samples and back. Every game format in `mgs2_audio.formats`
builds on it.

A frame is 16 bytes and carries 28 samples:

    byte 0      predictor filter (high nibble, 0-4) and shift (low nibble)
    byte 1      flags — see FLAG_* below
    bytes 2-15  28 samples, two 4-bit nibbles per byte

The flag byte follows the usual SPU convention. Loop points matter when
rewriting audio in place: they must be preserved frame by frame.

Pure Python, no dependencies.
"""

from typing import List, Tuple

FRAME_SIZE = 16              # bytes per PS-ADPCM frame
SAMPLES_PER_FRAME = 28       # PCM samples decoded from one frame

FLAG_END = 0x01              # last frame of a sample
FLAG_LOOP = 0x02             # loop rather than stop at the end
FLAG_LOOP_START = 0x04       # loop restarts here


def frame_count(n_bytes: int) -> int:
    """How many whole PS-ADPCM frames fit in `n_bytes`."""
    return n_bytes // FRAME_SIZE


def samples_for_bytes(n_bytes: int) -> int:
    """How many PCM samples `n_bytes` of PS-ADPCM decode to."""
    return frame_count(n_bytes) * SAMPLES_PER_FRAME


def bytes_for_samples(n_samples: int) -> int:
    """How many PS-ADPCM bytes are needed to hold `n_samples` PCM samples."""
    frames = (n_samples + SAMPLES_PER_FRAME - 1) // SAMPLES_PER_FRAME
    return frames * FRAME_SIZE


# Sony PS-ADPCM prediction coefficients (scaled by /64)
VAG_COEFS = [
    (0.0, 0.0),
    (60.0 / 64.0, 0.0),
    (115.0 / 64.0, -52.0 / 64.0),
    (98.0 / 64.0, -55.0 / 64.0),
    (122.0 / 64.0, -60.0 / 64.0),
]


def decode_psadpcm(adpcm: bytes) -> List[int]:
    """Decode a PS-ADPCM stream (16-byte frames) into 16-bit PCM samples."""
    samples: List[int] = []
    hist1 = 0.0
    hist2 = 0.0

    for off in range(0, len(adpcm) - 15, 16):
        header = adpcm[off]
        shift = header & 0x0F
        filt = (header >> 4) & 0x0F
        if filt >= len(VAG_COEFS):
            filt = 0
        c0, c1 = VAG_COEFS[filt]

        # flag = adpcm[off + 1]  (0x07 = end of stream; ignored here)

        for i in range(14):
            byte = adpcm[off + 2 + i]
            for nibble in (byte & 0x0F, (byte >> 4) & 0x0F):
                # 4-bit sign
                s = nibble - 16 if nibble >= 8 else nibble
                # rescale
                sample = (s << 12) >> shift if shift <= 12 else 0
                sample += c0 * hist1 + c1 * hist2
                sample = max(-32768.0, min(32767.0, sample))
                samples.append(int(round(sample)))
                hist2 = hist1
                hist1 = sample

    return samples


def _encode_block(samples28: List[int], prev1: float, prev2: float
                  ) -> Tuple[bytes, float, float]:
    """Encode 28 samples into one 16-byte PS-ADPCM block."""
    best = None
    for filt in range(5):
        c0, c1 = VAG_COEFS[filt]
        for shift in range(13):
            p1, p2 = prev1, prev2
            encoded = []
            max_err = 0.0
            for s in samples28:
                predicted = p1 * c0 + p2 * c1
                diff = s - predicted
                q = int(round(diff * (1 << shift) / 4096.0))
                q = max(-8, min(7, q))
                dec = (q * 4096.0) / (1 << shift) + predicted
                dec = max(-32768.0, min(32767.0, dec))
                err = abs(dec - s)
                if err > max_err:
                    max_err = err
                encoded.append(q & 0xF)
                p2, p1 = p1, dec
            if best is None or max_err < best[0]:
                best = (max_err, filt, shift, encoded, p1, p2)

    _, filt, shift, encoded, np1, np2 = best
    block = bytearray(16)
    block[0] = (filt << 4) | shift
    block[1] = 0
    for i in range(0, 28, 2):
        block[2 + i // 2] = (encoded[i] & 0xF) | ((encoded[i + 1] & 0xF) << 4)
    return bytes(block), np1, np2


def encode_psadpcm(samples: List[int]) -> bytes:
    """Encode 16-bit PCM samples into a PS-ADPCM stream."""
    out = bytearray()
    p1 = p2 = 0.0
    # Pad up to a multiple of 28
    padded = list(samples)
    if len(padded) % 28 != 0:
        padded += [0] * (28 - len(padded) % 28)
    for i in range(0, len(padded), 28):
        blk, p1, p2 = _encode_block(padded[i:i + 28], p1, p2)
        out += blk
    return bytes(out)
