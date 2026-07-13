#!/usr/bin/env python3
"""
bgm.py — The `bgm.dat` archive of Metal Gear Solid 2 (PC).

`bgm.dat` is a flat concatenation of MS-ADPCM audio entries, each preceded by
a small big-endian header.  There is no file-level directory; entries are
separated only by the size field embedded in the header.

Mini-header layout (all values big-endian):

    +0x00  u32   approximate data size (not exact — off by up to 0x1800)
    +0x04  u8    0x00  (padding / volume high byte?)
    +0x05  u8    0x7F  (volume)
    +0x06  u16   sample rate (e.g. 0xAC44 = 44100)
    +0x08  u8    channels (2 or 4)
    +0x09  u16   0x0011  (unknown)
    +0x0B  u8    0x00  (unknown)
    +0x0C  u32   loop start (total samples)
    +0x10  u32   loop end   (total samples)
    +0x14  …     padding zeros up to offset 0x800

Audio data starts at offset 0x800 within each entry.  Codec is MS-ADPCM,
block size 0x800 (confirmed by bnnm / vgmstream).

Detection strategy: scan the file for the 2-byte volume pattern  00 7F  at
offset +0x04 inside each entry header, then validate sample-rate, channels, and
size fields.  Works regardless of sample rate.

Pure Python, no dependencies.
"""

import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional

from ..codec.msadpcm import (
    DEFAULT_BLOCK_SIZE, bytes_to_samples, decode_msadpcm,
)

# ─────────────────────────────────────────────────────────────────────────────
# Format constants
# ─────────────────────────────────────────────────────────────────────────────

HEADER_SIZE = 0x800                  # fixed header size per entry
ANCHOR_PATTERN = b"\x00\x7F"  # volume bytes at header offset +0x04
VALID_SAMPLE_RATES = (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000)
VALID_CHANNELS = (2, 4)              # MGS2 bgm.dat uses 2ch or 4ch MS-ADPCM


# ─────────────────────────────────────────────────────────────────────────────
# Representation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class BGMEntry:
    """One audio entry inside a bgm.dat archive."""
    index: int
    file_offset: int          # absolute byte offset of the header in bgm.dat
    data_offset: int          # absolute byte offset of audio data (= file_offset + 0x800)
    data_size: int            # approximate audio data size (from header field)
    sample_rate: int
    channels: int
    loop_start: int           # in total samples
    loop_end: int             # in total samples
    next_entry_offset: int    # absolute offset of the next entry (or EOF)

    @property
    def header_size(self) -> int:
        return HEADER_SIZE

    @property
    def actual_data_size(self) -> int:
        """Exact audio data size = distance to next entry minus header."""
        return self.next_entry_offset - self.data_offset

    @property
    def total_samples(self) -> int:
        """Total decoded samples per channel."""
        return bytes_to_samples(self.actual_data_size, DEFAULT_BLOCK_SIZE,
                                self.channels)

    @property
    def duration_seconds(self) -> float:
        return self.total_samples / self.sample_rate if self.sample_rate else 0.0


@dataclass
class BGMFile:
    """A parsed bgm.dat archive."""
    path: str
    raw: bytes
    entries: List[BGMEntry] = field(default_factory=list)

    @property
    def entry_count(self) -> int:
        return len(self.entries)

    def __getitem__(self, idx: int) -> BGMEntry:
        return self.entries[idx]


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _parse_mini_header(raw: bytes, offset: int) -> Optional[dict]:
    """Parse the big-endian mini-header at `offset` inside `raw`.

    Returns None if the data does not look like a valid BGM header.
    """
    if offset + HEADER_SIZE > len(raw):
        return None

    # Check the anchor pattern at +0x04 (volume bytes, sample-rate agnostic)
    if raw[offset + 4:offset + 6] != ANCHOR_PATTERN:
        return None

    size_field = struct.unpack_from(">I", raw, offset)[0]
    sample_rate = struct.unpack_from(">H", raw, offset + 6)[0]
    channels = raw[offset + 8]
    loop_start = struct.unpack_from(">I", raw, offset + 0x0C)[0]
    loop_end = struct.unpack_from(">I", raw, offset + 0x10)[0]

    if sample_rate not in VALID_SAMPLE_RATES:
        return None
    if channels not in VALID_CHANNELS:
        return None

    return {
        "size_field": size_field,
        "sample_rate": sample_rate,
        "channels": channels,
        "loop_start": loop_start,
        "loop_end": loop_end,
    }


def _scan_anchor_positions(raw: bytes) -> List[int]:
    """Scan the file for every occurrence of the anchor pattern.

    Returns the absolute file offsets where the 2-byte volume pattern
    ``00 7F`` is found (at header offset +0x04).  Only positions that
    parse cleanly (valid sample-rate, channels, size) are kept.
    """
    positions: List[int] = []
    start = 0
    while True:
        idx = raw.find(ANCHOR_PATTERN, start)
        if idx == -1:
            break
        header_offset = idx - 4  # anchor is at +0x04 in the header
        if header_offset >= 0:
            positions.append(header_offset)
        start = idx + len(ANCHOR_PATTERN)
    return positions


def parse_bgm(path: str) -> BGMFile:
    """Read a bgm.dat file and locate its audio entries."""
    with open(path, "rb") as f:
        raw = f.read()

    bgm = BGMFile(path=path, raw=raw)

    anchor_positions = _scan_anchor_positions(raw)

    # Filter: keep only positions that parse cleanly
    valid_offsets: List[int] = []
    for off in anchor_positions:
        hdr = _parse_mini_header(raw, off)
        if hdr is not None:
            valid_offsets.append(off)

    # Sort and deduplicate
    valid_offsets = sorted(set(valid_offsets))

    # Build entries: each entry spans from its header to the next entry.
    # Validate no overlap: each entry's data region must not reach the next header.
    for i, off in enumerate(valid_offsets):
        hdr = _parse_mini_header(raw, off)
        if hdr is None:
            continue

        if i + 1 < len(valid_offsets):
            next_off = valid_offsets[i + 1]
        else:
            next_off = len(raw)

        data_offset = off + HEADER_SIZE
        # Skip if the data region would overlap the next entry's header
        if data_offset >= next_off:
            continue

        bgm.entries.append(BGMEntry(
            index=i,
            file_offset=off,
            data_offset=data_offset,
            data_size=hdr["size_field"],
            sample_rate=hdr["sample_rate"],
            channels=hdr["channels"],
            loop_start=hdr["loop_start"],
            loop_end=hdr["loop_end"],
            next_entry_offset=next_off,
        ))

    return bgm


# ─────────────────────────────────────────────────────────────────────────────
# Decoding
# ─────────────────────────────────────────────────────────────────────────────

def get_entry_audio_data(bgm: BGMFile, entry: BGMEntry) -> bytes:
    """Return the raw MS-ADPCM audio bytes for one entry."""
    return bgm.raw[entry.data_offset:entry.data_offset + entry.actual_data_size]


def bgm_entry_to_pcm(bgm: BGMFile, entry: BGMEntry) -> List[int]:
    """Decode one BGM entry into interleaved 16-bit PCM samples."""
    adpcm = get_entry_audio_data(bgm, entry)
    return decode_msadpcm(adpcm, channels=entry.channels,
                          block_size=DEFAULT_BLOCK_SIZE)


def bgm_to_wav(bgm: BGMFile, entry_index: int, out_path: str) -> int:
    """Decode one entry and write it to a WAV file.

    Returns the number of sample frames written.
    """
    from ..codec.wav import save_wav
    entry = bgm.entries[entry_index]
    pcm = bgm_entry_to_pcm(bgm, entry)
    save_wav(pcm, out_path, entry.sample_rate, channels=entry.channels)
    return len(pcm) // entry.channels


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def describe_entry(entry: BGMEntry) -> str:
    ch = "stereo" if entry.channels == 2 else f"{entry.channels}ch"
    return (
        f"  [{entry.index}]  {entry.sample_rate} Hz {ch}  "
        f"{entry.duration_seconds:.2f} s  "
        f"loop {entry.loop_start}->{entry.loop_end}  "
        f"@ 0x{entry.file_offset:08X}"
    )


def describe(bgm: BGMFile) -> str:
    lines = [
        f"File        : {os.path.basename(bgm.path)}",
        f"Size        : {len(bgm.raw):,} bytes",
        f"Entries     : {bgm.entry_count}",
    ]
    for e in bgm.entries:
        lines.append(describe_entry(e))
    return "\n".join(lines)


def metadata(bgm: BGMFile) -> dict:
    return {
        "file": os.path.basename(bgm.path),
        "size": len(bgm.raw),
        "entries": bgm.entry_count,
        "details": [
            {
                "index": e.index,
                "sample_rate": e.sample_rate,
                "channels": e.channels,
                "duration": e.duration_seconds,
                "loop_start": e.loop_start,
                "loop_end": e.loop_end,
            }
            for e in bgm.entries
        ],
    }
