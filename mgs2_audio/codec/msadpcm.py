#!/usr/bin/env python3
"""
msadpcm.py — Microsoft ADPCM (MS-ADPCM) codec.

Decodes MS-ADPCM blocks into 16-bit PCM samples.  The implementation follows
the reference in vgmstream (msadpcm_decoder.c) which in turn mirrors
Microsoft's msadp32.acm decoder (SHR variant).

A block layout (all multi-byte values are little-endian):

    **Mono (1 channel), block header = 7 bytes**

        +0x00  u8    predictor index  (0-6 → coef table row)
        +0x01  s16   iDelta (adaptation step)
        +0x03  s16   iSamp1 (previous sample)
        +0x05  s16   iSamp2 (two samples back)
        +0x07  …     nibble payload (high nibble first)

    **Stereo (2 channels), block header = 14 bytes**

        +0x00  u8    predictor ch0 (& 0x07)
        +0x01  u8    predictor ch1 (& 0x07)
        +0x02  s16   iDelta ch0
        +0x04  s16   iDelta ch1
        +0x06  s16   iSamp1 ch0
        +0x08  s16   iSamp1 ch1
        +0x0A  s16   iSamp2 ch0
        +0x0C  s16   iSamp2 ch1
        +0x0E  …     nibble payload (interleaved L/R, high nibble = L)

    Samples-per-frame formula (from the MS-ADPCM spec):

        spf = (block_size - 7 * channels) * 2 // channels + 2

    The first two samples per channel come from the block header (iSamp2 then
    iSamp1); all subsequent samples are decoded from the nibble payload.

Pure Python, no dependencies.
"""

from typing import List

__all__ = [
    "DEFAULT_BLOCK_SIZE",
    "COEFS", "STEPS",
    "samples_per_block", "bytes_to_samples",
    "decode_msadpcm",
    "encode_msadpcm_block",
]

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

# Default block size used by MGS2 bgm.dat (and most MS-ADPCM files).
DEFAULT_BLOCK_SIZE = 0x800

# Fixed-point scaling (8.8 signed).
FIXED_POINT_BASE = 256

# ─────────────────────────────────────────────────────────────────────────────
# Coefficient table (7 rows × 2 coefficients, integer fixed-point 8.8)
# ─────────────────────────────────────────────────────────────────────────────

COEFS: List[List[int]] = [
    [256,    0],
    [512, -256],
    [  0,    0],
    [192,   64],
    [240,    0],
    [460, -208],
    [392, -232],
]

# ─────────────────────────────────────────────────────────────────────────────
# Adaptation step table (16 entries)
# ─────────────────────────────────────────────────────────────────────────────

STEPS: List[int] = [
    230, 230, 230, 230,
    307, 409, 512, 614,
    768, 614, 512, 409,
    307, 230, 230, 230,
]


# ─────────────────────────────────────────────────────────────────────────────
# Per-channel decoder state (mirrors VGMSTREAMCHANNEL fields)
# ─────────────────────────────────────────────────────────────────────────────

class _Channel:
    """Lightweight decode state for one channel."""
    __slots__ = ("coef0", "coef1", "scale", "hist1", "hist2")

    def __init__(self) -> None:
        self.coef0: int = 0
        self.coef1: int = 0
        self.scale: int = 16
        self.hist1: int = 0
        self.hist2: int = 0

    def expand_nibble(self, nibble: int) -> int:
        """Decode one 4-bit signed nibble and advance state.

        Uses the SHR variant (>> 8) matching Windows msadp32.acm.
        """
        code = nibble - 16 if nibble >= 8 else nibble

        predicted = self.hist1 * self.coef0 + self.hist2 * self.coef1
        predicted >>= 8  # SHR, not DIV
        predicted += code * self.scale
        predicted = max(-32768, min(32767, predicted))

        self.hist2 = self.hist1
        self.hist1 = predicted

        self.scale = (STEPS[code & 0x0F] * self.scale) >> 8
        if self.scale < 16:
            self.scale = 16

        return predicted


# ─────────────────────────────────────────────────────────────────────────────
# Public helpers
# ─────────────────────────────────────────────────────────────────────────────

def samples_per_block(block_size: int, channels: int) -> int:
    """Number of PCM samples one block produces per channel.

    `channels=4` ("quad" — two block-interleaved stereo pairs, see
    `_decode_quad_stream`) has no single block of its own: one logical unit
    is a *pair* of stereo blocks (front + rear, `2 * block_size` bytes), each
    producing the ordinary stereo sample count.
    """
    if channels == 4:
        return (block_size - 7 * 2) * 2 // 2 + 2
    return (block_size - 7 * channels) * 2 // channels + 2


def bytes_to_samples(total_bytes: int, block_size: int, channels: int) -> int:
    """Total PCM samples (per channel) for a given byte count."""
    if block_size <= 0 or channels <= 0:
        return 0
    if channels == 4:
        pair_bytes = block_size * 2
        full = total_bytes // pair_bytes
        return full * samples_per_block(block_size, 4)
    full = total_bytes // block_size
    remainder = total_bytes % block_size
    per_block = samples_per_block(block_size, channels)
    total = full * per_block
    if remainder >= 7 * channels:
        total += 2 + (remainder - 7 * channels) * 2 // channels
    return total


# ─────────────────────────────────────────────────────────────────────────────
# Block decoders
# ─────────────────────────────────────────────────────────────────────────────

def _decode_mono_block(block: bytes) -> List[int]:
    """Decode a single mono MS-ADPCM block into PCM samples."""
    if len(block) < 7:
        return []

    ch = _Channel()
    coef_idx = min(block[0] & 0x07, 6)
    ch.coef0 = COEFS[coef_idx][0]
    ch.coef1 = COEFS[coef_idx][1]
    ch.scale = int.from_bytes(block[1:3], "little", signed=True)
    ch.hist1 = int.from_bytes(block[3:5], "little", signed=True)
    ch.hist2 = int.from_bytes(block[5:7], "little", signed=True)

    # Header samples (needed before nibble decoding)
    out = [ch.hist2, ch.hist1]

    # Decode nibbles (high nibble first per byte)
    for i in range(7, len(block)):
        byte = block[i]
        out.append(ch.expand_nibble((byte >> 4) & 0x0F))
        out.append(ch.expand_nibble(byte & 0x0F))

    return out


def _decode_stereo_block(block: bytes) -> List[int]:
    """Decode a single stereo MS-ADPCM block into interleaved PCM samples.

    Returns [L0, R0, L1, R1, …] — standard WAV interleaving.
    """
    if len(block) < 14:
        return []

    ch0 = _Channel()
    ch1 = _Channel()

    coef_idx0 = min(block[0] & 0x07, 6)
    coef_idx1 = min(block[1] & 0x07, 6)
    ch0.coef0, ch0.coef1 = COEFS[coef_idx0]
    ch1.coef0, ch1.coef1 = COEFS[coef_idx1]

    ch0.scale = int.from_bytes(block[2:4], "little", signed=True)
    ch1.scale = int.from_bytes(block[4:6], "little", signed=True)
    ch0.hist1 = int.from_bytes(block[6:8], "little", signed=True)
    ch1.hist1 = int.from_bytes(block[8:10], "little", signed=True)
    ch0.hist2 = int.from_bytes(block[10:12], "little", signed=True)
    ch1.hist2 = int.from_bytes(block[12:14], "little", signed=True)

    # Header samples (L, R interleaved)
    out = [ch0.hist2, ch1.hist2, ch0.hist1, ch1.hist1]

    # Decode nibbles (interleaved: high nibble = ch0/L, low nibble = ch1/R)
    for i in range(14, len(block)):
        byte = block[i]
        out.append(ch0.expand_nibble((byte >> 4) & 0x0F))  # L
        out.append(ch1.expand_nibble(byte & 0x0F))          # R

    return out


def _decode_quad_stream(data: bytes, block_size: int) -> List[int]:
    """Decode a "4-channel" MS-ADPCM stream as two block-interleaved stereo pairs.

    Standard MS-ADPCM has no native >2-channel mode — Microsoft's own spec
    tops out at stereo (confirmed against vgmstream's decoder). MGS2's
    "4-channel" `bgm.dat` entries are two independent stereo streams,
    alternating every `block_size` bytes: even blocks are the front L/R pair,
    odd blocks are the rear L/R pair. Verified against real game data
    (docs/AUDIT.md): treating it as a single quad nibble-interleaved stream
    (the previous approach here) clips ~15% of samples at full scale; this
    block-alternation decodes cleanly, matching known-good stereo entries.

    Returns interleaved 4-channel frames: [FL, FR, RL, RR, FL, FR, RL, RR, …].
    """
    front: List[int] = []
    rear: List[int] = []
    for i, off in enumerate(range(0, len(data), block_size)):
        block = data[off:off + block_size]
        if len(block) < 14:
            break
        pcm = _decode_stereo_block(block)
        (front if i % 2 == 0 else rear).extend(pcm)

    n = min(len(front), len(rear)) // 2
    out: List[int] = []
    for i in range(n):
        out.append(front[2 * i])
        out.append(front[2 * i + 1])
        out.append(rear[2 * i])
        out.append(rear[2 * i + 1])
    return out


# ─────────────────────────────────────────────────────────────────────────────
# Stream decoder
# ─────────────────────────────────────────────────────────────────────────────

def decode_msadpcm(data: bytes, channels: int = 2,
                   block_size: int = DEFAULT_BLOCK_SIZE) -> List[int]:
    """Decode an MS-ADPCM stream into interleaved 16-bit PCM samples.

    Parameters
    ----------
    data : bytes
        Raw MS-ADPCM data (one or more blocks, already positioned at the
        first block — no file-level header).
    channels : int
        1 (mono), 2 (stereo), or 4 (two block-interleaved stereo pairs —
        see `_decode_quad_stream`).
    block_size : int
        Block size in bytes (default 0x800 as used in MGS2 bgm.dat).

    Returns
    -------
    list[int]
        Interleaved 16-bit PCM samples.  For mono the list is flat; for
        stereo it is [L, R, L, R, …]; for "quad" it is [FL, FR, RL, RR, …].
    """
    if channels == 4:
        return _decode_quad_stream(data, block_size)

    if channels == 1:
        decode_block = _decode_mono_block
    elif channels == 2:
        decode_block = _decode_stereo_block
    else:
        raise ValueError(f"unsupported channel count: {channels}")

    out: List[int] = []
    for off in range(0, len(data), block_size):
        block = data[off:off + block_size]
        if len(block) < (7 * channels):
            break
        out.extend(decode_block(block))

    return out


# ─────────────────────────────────────────────────────────────────────────────
# Encoder (kept minimal — only needed if we ever rewrite BGM entries)
# ─────────────────────────────────────────────────────────────────────────────

def encode_msadpcm_block(samples: List[int], channels: int = 1) -> bytes:
    """Encode one block of 16-bit PCM samples into MS-ADPCM.

    This is a minimal brute-force encoder.  It is NOT optimised for quality
    or speed; it exists so that round-trip tests can verify the decoder.
    """
    spf = samples_per_block(DEFAULT_BLOCK_SIZE, channels)
    # Pad input to at least spf samples
    padded = list(samples) + [0] * max(0, spf - len(samples))

    if channels == 1:
        return _encode_mono_block(padded[:spf])
    elif channels == 2:
        return _encode_stereo_block(padded[:spf])
    else:
        raise ValueError(f"unsupported channel count: {channels}")


def _encode_mono_block(pcm: List[int]) -> bytes:
    """Minimal mono encoder (brute-force predictor)."""
    best = None
    for coef_idx in range(7):
        c0, c1 = COEFS[coef_idx]
        h1 = h2 = 0
        delta = 16
        encoded = []
        max_err = 0
        for s in pcm[2:]:  # skip 2 header samples
            predicted = (h1 * c0 + h2 * c1) >> 8
            diff = s - predicted
            if delta > 0:
                q = max(-8, min(7, int(round(diff * 256.0 / delta))))
            else:
                q = 0
            dec = predicted + q * delta
            dec = max(-32768, min(32767, dec))
            err = abs(dec - s)
            if err > max_err:
                max_err = err
            encoded.append(q & 0x0F)
            h2, h1 = h1, dec
            delta = max(16, (STEPS[q & 0x0F] * delta) >> 8)
        if best is None or max_err < best[0]:
            best = (max_err, coef_idx, encoded, delta, h1, h2)

    _, coef_idx, encoded, delta, h1, h2 = best
    block = bytearray(DEFAULT_BLOCK_SIZE)
    block[0] = coef_idx & 0x07
    block[1:3] = delta.to_bytes(2, "little", signed=True)
    block[3:5] = h1.to_bytes(2, "little", signed=True)
    block[5:7] = h2.to_bytes(2, "little", signed=True)
    # Pack nibbles
    for i in range(0, len(encoded) - 1, 2):
        idx = 7 + i // 2
        if idx < DEFAULT_BLOCK_SIZE:
            block[idx] = (encoded[i] << 4) | (encoded[i + 1] & 0x0F)
    return bytes(block)


def _encode_stereo_block(pcm: List[int]) -> bytes:
    """Minimal stereo encoder (brute-force, per-channel).

    NOTE: This encoder encodes L and R independently then merges headers.
    The output may not match the exact block layout expected by all MS-ADPCM
    decoders.  Use only for round-trip tests, not for generating game-ready
    audio.
    """
    # Split interleaved PCM into per-channel lists
    left = pcm[0::2]
    right = pcm[1::2]
    left_blk = _encode_mono_block(left)
    right_blk = _encode_mono_block(right)
    # Merge into interleaved block
    block = bytearray(DEFAULT_BLOCK_SIZE)
    block[0] = left_blk[0] & 0x07
    block[1] = right_blk[0] & 0x07
    block[2:4] = left_blk[1:3]
    block[4:6] = right_blk[1:3]
    block[6:8] = left_blk[3:5]
    block[8:10] = right_blk[3:5]
    block[10:12] = left_blk[5:7]
    block[12:14] = right_blk[5:7]
    # Interleave nibble payloads
    l_nibbles = [((left_blk[i] >> 4) & 0x0F, left_blk[i] & 0x0F)
                 for i in range(7, DEFAULT_BLOCK_SIZE)]
    r_nibbles = [((right_blk[i] >> 4) & 0x0F, right_blk[i] & 0x0F)
                 for i in range(7, DEFAULT_BLOCK_SIZE)]
    out_pos = 14
    for ln, rn in zip(l_nibbles, r_nibbles):
        if out_pos + 1 >= DEFAULT_BLOCK_SIZE:
            break
        block[out_pos] = (ln[0] << 4) | (rn[0] & 0x0F)
        block[out_pos + 1] = (ln[1] << 4) | (rn[1] & 0x0F)
        out_pos += 2
    return bytes(block)
