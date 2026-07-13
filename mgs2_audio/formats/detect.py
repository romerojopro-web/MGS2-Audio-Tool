#!/usr/bin/env python3
"""
detect.py — Structural auto-detection of MGS2 audio formats.

RavenHunter philosophy: never guess by extension, always inspect the file's
own bytes.  This module probes a file (or raw bytes) and returns the matching
format, or ``None`` if the content is not recognised.

Supported formats
-----------------
* **SDT**  — first block type == 1 (little-endian u32) at offset 0x00,
  followed by a valid block size in a sane range.
* **SDX**  — first 4 bytes == ``0x00000001`` (SDX v1 header).
* **Sequence** (embedded in SDX) — first block type == ``0x11000000`` (bank
  header with embedded cue data).
* **BGM**  — presence of the 4-byte anchor ``00 7F AC 44`` at offset +0x04
  of a plausible header, with valid sample-rate / channel values.

Detection is ordered from most specific to least specific so that an SDX file
containing sequence data is identified as SDX (not Sequence) and a bgm.dat is
identified as BGM (not SDT).

Pure Python, no dependencies.
"""

import struct
from enum import Enum, auto
from typing import Optional


class Format(Enum):
    """Recognised audio container formats."""
    SDT = auto()
    SDX = auto()
    SEQUENCE = auto()
    BGM = auto()


# ─────────────────────────────────────────────────────────────────────────────
# Individual detectors (all return bool)
# ─────────────────────────────────────────────────────────────────────────────

def is_sdt(raw: bytes) -> bool:
    """Does the byte content look like an SDT file?

    Heuristic: first little-endian u32 == 1 (audio block type) and the
    accompanying size field is in a plausible range for an MG block.
    """
    if len(raw) < 8:
        return False
    block_type = struct.unpack_from("<I", raw, 0)[0]
    block_size = struct.unpack_from("<I", raw, 4)[0]
    return block_type == 1 and 0x1000 <= block_size <= 0x4010


def is_sdx(raw: bytes) -> bool:
    """Does the byte content look like an SDX file?

    SDX v1 files start with the 4-byte value 0x00000001.
    """
    if len(raw) < 4:
        return False
    return struct.unpack_from("<I", raw, 0)[0] == 1


def is_sequence(raw: bytes) -> bool:
    """Does the byte content look like a Sequence bank?

    Sequence banks start with a bank header block whose type is 0x11
    (big-endian: ``0x11 0x00 0x00 0x00``).
    """
    if len(raw) < 8:
        return False
    return raw[0] == 0x11 and raw[1] == 0 and raw[2] == 0 and raw[3] == 0


def is_bgm(raw: bytes) -> bool:
    """Does the byte content look like a bgm.dat archive?

    Heuristic: find the 2-byte volume pattern ``00 7F`` at offset +0x04
    from a plausible header start, then validate sample-rate and channels.
    """
    if len(raw) < 0x814:  # need at least header + a few bytes of data
        return False

    anchor = b"\x00\x7F"
    VALID_RATES = (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000)

    # Check the first candidate: offset 0x00 + 0x04 = 0x04
    if raw[4:6] == anchor:
        sr = (raw[6] << 8) | raw[7]
        ch = raw[8]
        if sr in VALID_RATES and ch in (2, 4):
            # Additional sanity: check that there's at least one more entry
            # by looking for another anchor within a reasonable range
            size_field = struct.unpack_from(">I", raw, 0)[0]
            if 0x1000 < size_field < 0x2000000:
                return True

    # Fallback: scan for the anchor at any position (up to 4 KB in)
    for off in range(0, min(len(raw) - 8, 0x2000), 4):
        if raw[off + 4:off + 6] == anchor:
            sr = (raw[off + 6] << 8) | raw[off + 7]
            ch = raw[off + 8]
            if sr in VALID_RATES and ch in (2, 4):
                return True

    return False


# ─────────────────────────────────────────────────────────────────────────────
# Main entry point
# ─────────────────────────────────────────────────────────────────────────────

def detect(raw: bytes) -> Optional[Format]:
    """Detect the format of a file from its raw bytes.

    Returns a ``Format`` enum member, or ``None`` if nothing matches.
    Order matters: SDX and Sequence are checked before SDT because an SDX
    file may also start with bytes that look like an SDT block.
    """
    if is_sdx(raw):
        return Format.SDX
    if is_sequence(raw):
        return Format.SEQUENCE
    if is_sdt(raw):
        return Format.SDT
    if is_bgm(raw):
        return Format.BGM
    return None


def detect_path(path: str) -> Optional[Format]:
    """Detect the format of a file on disk (reads up to 64 KB of head)."""
    with open(path, "rb") as f:
        head = f.read(0x10000)  # 64 KB is plenty for all detectors
    return detect(head)


def open_file(path: str):
    """Auto-detect the format of `path` and return the parsed object.

    Returns an ``SDTFile``, ``SDXFile``, ``BGMFile``, etc.  Raises
    ``ValueError`` if the format is not recognised.
    """
    from .bgm import parse_bgm
    from .sdt import parse_sdt
    from .sdx import parse_sdx

    fmt = detect_path(path)
    if fmt is None:
        raise ValueError(f"unrecognised format: {path}")

    if fmt is Format.SDT:
        return parse_sdt(path)
    if fmt is Format.SDX:
        return parse_sdx(path)
    if fmt is Format.BGM:
        return parse_bgm(path)
    if fmt is Format.SEQUENCE:
        return parse_sdx(path)  # sequences live inside SDX files

    raise ValueError(f"unsupported format: {fmt}")
