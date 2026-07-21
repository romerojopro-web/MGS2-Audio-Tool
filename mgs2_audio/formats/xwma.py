#!/usr/bin/env python3
"""
xwma.py — Stock (un-modded) Master Collection `.sdt` audio: Konami XWMA.

The stock Steam `.sdt` files are NOT PS-ADPCM (that's the Better Audio Mod).
They are a **multiplexed container** of interleaved 16-byte-header records, one
stream of which is **Konami XWMA** (`AMWX` magic) wrapping WMA v2 audio
(`wFormatTag` 0x0161).  The WMA data is scattered in chunks across the file,
interleaved with other streams (subtitles, video…), so it must be
de-interleaved before it can be decoded.

This module turns such a `.sdt` into a standard RIFF `XWMA` file that ffmpeg
can decode (see `mgs2_audio.ffmpeg`).  Pure Python, no dependencies.

Format knowledge and the AMWX→RIFF conversion are adapted, with thanks, from
**RockeyLol/RIFF-XWMA-Konami-XWMA-Converter** (MIT License, © 2026 RockeyLol) —
specifically its `sdt_demux.py` (container de-interleaving) and `KontoRiff.py`
(AMWX→RIFF xWMA). See the README acknowledgements.
"""

import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Multiplex container record IDs (u32 at record start).
MUX_REGISTER = 0x10          # declares a stream; its sid is u32 at +0x0C
MUX_END = 0xF0               # end of container
RECORD_HEADER = 16

# Stream id of the XWMA audio in MC's `.sdt` (XBOX360 HD-remaster audio format)
# — a fallback; the real id is detected from the data (which stream is AMWX).
XWMA_STREAM_SID = 0x00040001

AMWX_MAGIC = b"AMWX"


@dataclass
class XwmaClip:
    """A parsed Konami AMWX clip: WMA format params + seek table + WMA bytes."""
    codec: int               # wFormatTag (0x0161 = WMA v2)
    channels: int
    sample_rate: int
    avg_bytes: int
    block_align: int
    seek_table: List[int] = field(default_factory=list)   # dpds (decoded bytes)
    data: bytes = b""        # the WMA packet bytes (de-padded)

    @property
    def duration_seconds(self) -> float:
        if self.seek_table and self.sample_rate and self.channels:
            return self.seek_table[-1] / (self.sample_rate * self.channels * 2)
        return 0.0


# ─────────────────────────────────────────────────────────────────────────────
# Detection
# ─────────────────────────────────────────────────────────────────────────────

def is_xwma_sdt(raw: bytes) -> bool:
    """True when a `.sdt` carries a Konami XWMA (AMWX) stream.

    The AMWX magic sits at the start of the audio stream's first chunk, which
    appears early in the container — a cheap head scan is enough.
    """
    return AMWX_MAGIC in raw[:0x2000]


# ─────────────────────────────────────────────────────────────────────────────
# De-interleaving the multiplexed container
# ─────────────────────────────────────────────────────────────────────────────

def demux_streams(raw: bytes) -> Dict[int, bytes]:
    """Split a multiplexed `.sdt` into its streams, keyed by stream id.

    Walks the 16-byte records: `0x10` registers a stream (its id at +0x0C),
    `0xF0` ends the container, any other id is a data chunk for that stream
    (its size is the u32 at +0x04, header included).  Faithful to RockeyLol's
    `sdt_demux.py`, but tolerant: it stops cleanly on a malformed record
    instead of raising.
    """
    streams: Dict[int, bytearray] = {}
    pos = 0
    n = len(raw)
    while pos + RECORD_HEADER <= n:
        rec_id = struct.unpack_from("<I", raw, pos)[0]
        if rec_id == MUX_END:
            break
        if rec_id == MUX_REGISTER:
            sid = struct.unpack_from("<I", raw, pos + 0x0C)[0]
            streams.setdefault(sid, bytearray())
            pos += RECORD_HEADER
        elif rec_id in streams:
            size = struct.unpack_from("<I", raw, pos + 0x04)[0]
            if size < RECORD_HEADER:
                break
            body = raw[pos + RECORD_HEADER:pos + size]
            streams[rec_id].extend(body)
            pos += size
        else:
            # Unknown / unregistered record — stop rather than misread.
            break
    return {sid: bytes(buf) for sid, buf in streams.items()}


def find_amwx_stream(raw: bytes) -> Optional[bytes]:
    """Return the de-interleaved stream that begins with the AMWX magic."""
    for data in demux_streams(raw).values():
        if data[:4] == AMWX_MAGIC:
            return data
    return None


def find_amwx_sid(raw: bytes) -> Optional[int]:
    """Return the stream id whose de-interleaved data is the AMWX audio."""
    for sid, data in demux_streams(raw).items():
        if data[:4] == AMWX_MAGIC:
            return sid
    return None


# ─────────────────────────────────────────────────────────────────────────────
# AMWX → standard RIFF xWMA  (adapted from RockeyLol's KontoRiff.py)
# ─────────────────────────────────────────────────────────────────────────────

def parse_amwx(amwx: bytes) -> XwmaClip:
    """Parse a de-interleaved Konami AMWX stream (magic at offset 0)."""
    if amwx[:4] != AMWX_MAGIC:
        raise ValueError("not a Konami AMWX stream")

    codec = struct.unpack_from("<I", amwx, 0x04)[0]
    channels = struct.unpack_from("<I", amwx, 0x08)[0]
    sample_rate = struct.unpack_from("<I", amwx, 0x0C)[0]
    data_size = struct.unpack_from("<I", amwx, 0x10)[0]
    avg_bytes = struct.unpack_from("<I", amwx, 0x14)[0]
    block_align = struct.unpack_from("<I", amwx, 0x18)[0]

    seek_table: List[int] = []
    # A seek table is present when the duplicated WAVEFORMATEX's rate field
    # (at 0x24) matches the sample rate.
    if struct.unpack_from("<I", amwx, 0x24)[0] == sample_rate:
        count = struct.unpack_from("<H", amwx, 0x32)[0]
        for i in range(count):
            off = 0x36 + i * 4
            if off + 4 > len(amwx):
                break
            seek_table.append(struct.unpack_from("<I", amwx, off)[0])
        data_offset = 0x20 + 0x10 + 0x06 + 0x04 * count
        data_offset = (data_offset + 0x0F) & ~0x0F      # align up to 16
    else:
        data_offset = 0x20

    # The WMA packets are stored padded to 16-byte boundaries; strip the
    # padding to recover the clean stream, then trim to the declared size.
    block_size = block_align if block_align <= 0x10000 else 0x2000
    audio = bytearray()
    src = amwx[data_offset:]
    off = 0
    while off < len(src):
        audio.extend(src[off:off + block_size])
        off += block_size
        while off % 0x10 != 0 and off < len(src):
            off += 1
    if len(audio) > data_size:
        del audio[data_size:]

    return XwmaClip(codec, channels, sample_rate, avg_bytes, block_align,
                    seek_table, bytes(audio))


def to_riff_xwma(clip: XwmaClip) -> bytes:
    """Assemble a standard RIFF `XWMA` file (fmt + dpds + data) for ffmpeg."""
    seek = clip.seek_table
    if not seek:
        # No table in the source — approximate one entry per second.
        seek = [0]
        bps = clip.sample_rate * clip.channels * 2
        for off in range(bps, len(clip.data), bps):
            seek.append(off)
        if seek[-1] != len(clip.data):
            seek.append(len(clip.data))

    fmt = struct.pack("<HHIIHH", clip.codec, clip.channels, clip.sample_rate,
                      clip.avg_bytes, clip.block_align, 16)   # 16 bytes, no cbSize
    dpds = b"".join(struct.pack("<I", e) for e in seek)

    def chunk(cid: bytes, payload: bytes) -> bytes:
        return cid + struct.pack("<I", len(payload)) + payload

    body = (b"XWMA" + chunk(b"fmt ", fmt) + chunk(b"dpds", dpds)
            + chunk(b"data", clip.data))
    return b"RIFF" + struct.pack("<I", len(body)) + body


def sdt_to_riff_xwma(raw: bytes) -> bytes:
    """Full path: a stock `.sdt` → standard RIFF xWMA bytes (ffmpeg-ready)."""
    amwx = find_amwx_stream(raw)
    if amwx is None:
        raise ValueError("no AMWX audio stream found in this .sdt")
    return to_riff_xwma(parse_amwx(amwx))


# ─────────────────────────────────────────────────────────────────────────────
# Replacement: standard RIFF xWMA → Konami AMWX → re-mux into the .sdt
# (adapted from RockeyLol's RifftoKon.py + SDT_buld.py, MIT)
# ─────────────────────────────────────────────────────────────────────────────

# Konami-engine constants written verbatim into the rebuilt header — these
# fixed values are what makes the game accept the file (per RockeyLol).
_KONAMI_AVG_BYTES = 24000
_KONAMI_BLOCK_ALIGN_32 = 0x00102000


def riff_to_amwx(riff: bytes, big_endian: bool = True) -> bytes:
    """Convert a standard RIFF `XWMA` file into a Konami `AMWX` stream.

    The input must be a **game-compatible** xWMA (i.e. WMA encoded the way the
    game expects — in practice, produced by Microsoft's xWMAEncode; ffmpeg's
    wmav2 needs codec-private extradata the AMWX cannot carry, so ffmpeg output
    is NOT game-loadable here).  The WMA packets are re-padded to 16-byte
    boundaries and wrapped in the Konami header + duplicated WAVEFORMATEX + seek
    table.
    """
    if riff[:4] != b"RIFF" or riff[8:12] != b"XWMA":
        raise ValueError("not a RIFF xWMA file")

    codec = channels = sample_rate = avg_bps = block_align = 0
    dpds: List[int] = []
    audio = b""
    off = 12
    while off + 8 <= len(riff):
        cid = riff[off:off + 4]
        size = struct.unpack_from("<I", riff, off + 4)[0]
        body = riff[off + 8:off + 8 + size]
        if cid == b"fmt ":
            codec, channels, sample_rate, avg_bps, block_align, _bits = \
                struct.unpack_from("<HHIIHH", body, 0)
        elif cid == b"dpds":
            dpds = list(struct.unpack_from("<%dI" % (size // 4), body, 0))
        elif cid == b"data":
            audio = body
        off += 8 + size + (size & 1)          # chunks are word-aligned

    data_size = len(audio)
    if not dpds:
        dpds = [0]
        bps = sample_rate * channels * 2
        dpds += list(range(bps, data_size, bps))
        if not dpds or dpds[-1] != data_size:
            dpds.append(data_size)

    codec = 0x0162 if channels >= 6 else 0x0161     # WMA Pro (5.1) / WMA v2
    header = bytearray(b"AMWX" if big_endian else b"XWMA")
    header += struct.pack("<IIIIII", codec, channels, sample_rate, data_size,
                          _KONAMI_AVG_BYTES, block_align)
    header += b"\x00" * 4
    header += struct.pack("<HHIII", codec, channels, sample_rate,
                          _KONAMI_AVG_BYTES, _KONAMI_BLOCK_ALIGN_32)
    header += b"\x00" * 2
    header += struct.pack("<H", len(dpds))
    header += b"\x00" * 2
    for e in dpds:
        header += struct.pack("<I", e)
    while len(header) % 0x10 != 0:
        header.append(0)

    block_size = block_align if block_align >= 0x100 else 0x2000
    padded = bytearray()
    o = 0
    while o < data_size:
        padded += audio[o:o + block_size]
        o += block_size
        while len(padded) % 0x10 != 0:
            padded.append(0)
    return bytes(header) + bytes(padded)


def xwma_capacity(sdt_raw: bytes) -> int:
    """Total bytes available for the XWMA stream across the container's chunks.

    A replacement AMWX must not exceed this (the container is rewritten at its
    exact original size, zero-padding any slack).
    """
    sid = find_amwx_sid(sdt_raw) or XWMA_STREAM_SID
    total, pos, n = 0, 0, len(sdt_raw)
    while pos + RECORD_HEADER <= n:
        rec_id = struct.unpack_from("<I", sdt_raw, pos)[0]
        if rec_id == MUX_END:
            break
        if rec_id == MUX_REGISTER:
            pos += RECORD_HEADER
        else:
            size = struct.unpack_from("<I", sdt_raw, pos + 0x04)[0]
            if size < RECORD_HEADER:
                break
            if rec_id == sid:
                total += size - RECORD_HEADER
            pos += size
    return total


def replace_amwx_in_sdt(sdt_raw: bytes, new_amwx: bytes) -> bytes:
    """Rewrite a stock `.sdt` with a new AMWX stream, preserving the container.

    Every non-audio byte (other streams, chunk headers, sizes) is copied
    verbatim; only the XWMA stream's payload is replaced, chunk by chunk, in
    order — zero-padded when the new audio is shorter.  The output is byte-for-
    byte the same size as the input.  Raises ValueError when the new audio is
    larger than the container can hold (it must be ≤ :func:`xwma_capacity`).
    """
    sid = find_amwx_sid(sdt_raw) or XWMA_STREAM_SID
    chunks = []       # (pos, total_size, data_size)
    pos, n = 0, len(sdt_raw)
    while pos + RECORD_HEADER <= n:
        rec_id = struct.unpack_from("<I", sdt_raw, pos)[0]
        if rec_id == MUX_END:
            break
        if rec_id == MUX_REGISTER:
            pos += RECORD_HEADER
        else:
            total = struct.unpack_from("<I", sdt_raw, pos + 0x04)[0]
            if total < RECORD_HEADER:
                break
            if rec_id == sid:
                chunks.append((pos, total, total - RECORD_HEADER))
            pos += total

    capacity = sum(c[2] for c in chunks)
    if not chunks:
        raise ValueError("no XWMA stream to replace in this .sdt")
    if len(new_amwx) > capacity:
        raise ValueError(
            f"replacement audio ({len(new_amwx)} bytes) exceeds the file's "
            f"XWMA capacity ({capacity} bytes) — use a shorter clip or a lower "
            f"bitrate")

    out = bytearray()
    cur = 0
    src = 0
    for cpos, ctotal, cdata in chunks:
        out += sdt_raw[cur:cpos]                              # up to this chunk
        out += sdt_raw[cpos:cpos + RECORD_HEADER]             # original header
        take = max(0, min(cdata, len(new_amwx) - src))
        out += new_amwx[src:src + take] + b"\x00" * (cdata - take)
        src += take
        cur = cpos + ctotal
    out += sdt_raw[cur:]                                      # trailing bytes
    return bytes(out)


def build_replacement_sdt(sdt_raw: bytes, riff_xwma: bytes) -> bytes:
    """Full replace path: game-compatible RIFF xWMA → AMWX → re-muxed `.sdt`."""
    return replace_amwx_in_sdt(sdt_raw, riff_to_amwx(riff_xwma))
