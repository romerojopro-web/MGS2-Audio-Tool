#!/usr/bin/env python3
"""
container.py — Unified ``RavenContainer`` interface for all MGS2 audio formats.

Every format that the tool understands is wrapped in a RavenContainer, which
exposes a small, uniform API:

* ``entry_count``     — number of audio entries
* ``sample_rate``     — sample rate (Hz)
* ``channels``        — channel count per entry
* ``describe()``      — human-readable summary string
* ``decode_pcm(i)``   — decode entry *i* into interleaved 16-bit PCM
* ``entry_metadata(i)`` — dict of per-entry metadata

The container is intentionally thin: it does NOT re-implement any parsing or
decoding logic; it delegates to the existing format-specific modules.

Pure Python, no dependencies.
"""

import os
from dataclasses import dataclass
from enum import Enum, auto
from typing import Any, Callable, Dict, List, Optional

from .detect import Format, detect_path


# ─────────────────────────────────────────────────────────────────────────────
# Container
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class RavenContainer:
    """Unified wrapper around any recognised MGS2 audio format.

    Created via ``RavenContainer.from_path(path)`` — do not instantiate
    directly.
    """
    path: str
    format: Format
    _parsed: Any                   # SDTFile, SDXFile, BGMFile, etc.
    _entry_count: int = 0
    _sample_rate: int = 0
    _channels: int = 0
    _describe_fn: Optional[Callable] = None
    _decode_fn: Optional[Callable] = None
    _meta_fn: Optional[Callable] = None

    # ── Factory ──────────────────────────────────────────────────────────

    @classmethod
    def from_path(cls, path: str) -> "RavenContainer":
        """Auto-detect and parse the file at *path*."""
        from .bgm import BGMFile, parse_bgm
        from .sdt import SDTFile, parse_sdt
        from .sdx import SDXFile, parse_sdx

        fmt = detect_path(path)
        if fmt is None:
            raise ValueError(f"unrecognised format: {path}")

        if fmt is Format.SDT:
            parsed = parse_sdt(path)
            return cls(
                path=path,
                format=fmt,
                _parsed=parsed,
                _entry_count=len(parsed.blocks),
                _sample_rate=parsed.sample_rate,
                _channels=parsed.channels,
                _describe_fn=lambda: _describe_sdt(parsed),
                _decode_fn=lambda i: _decode_sdt(parsed, i),
                _meta_fn=lambda i: _meta_sdt(parsed, i),
            )

        if fmt is Format.SDX or fmt is Format.SEQUENCE:
            # Sequence banks are SDX banks whose cue/event data happens to be
            # what detect() keyed on — the sample data parses the same way.
            parsed = parse_sdx(path)
            return cls(
                path=path,
                format=fmt,
                _parsed=parsed,
                _entry_count=len(parsed.samples),
                _sample_rate=parsed.sample_rate,
                _channels=1,
                _describe_fn=lambda: _describe_sdx(parsed),
                _decode_fn=lambda i: _decode_sdx(parsed, i),
                _meta_fn=lambda i: _meta_sdx(parsed, i),
            )

        if fmt is Format.BGM:
            parsed = parse_bgm(path)
            return cls(
                path=path,
                format=fmt,
                _parsed=parsed,
                _entry_count=parsed.entry_count,
                _sample_rate=0,  # varies per entry
                _channels=0,     # varies per entry
                _describe_fn=lambda: _describe_bgm(parsed),
                _decode_fn=lambda i: _decode_bgm(parsed, i),
                _meta_fn=lambda i: _meta_bgm(parsed, i),
            )

        raise ValueError(f"unsupported format: {fmt}")

    # ── Public API ───────────────────────────────────────────────────────

    @property
    def entry_count(self) -> int:
        return self._entry_count

    @property
    def sample_rate(self) -> int:
        return self._sample_rate

    @property
    def channels(self) -> int:
        return self._channels

    def describe(self) -> str:
        if self._describe_fn:
            return self._describe_fn()
        return f"{os.path.basename(self.path)}  ({self.format.name})"

    def decode_pcm(self, entry_index: int) -> List[int]:
        """Decode entry *entry_index* into interleaved 16-bit PCM."""
        if self._decode_fn is None:
            raise RuntimeError("decode not available for this format")
        return self._decode_fn(entry_index)

    def entry_metadata(self, entry_index: int) -> Dict:
        """Return per-entry metadata as a dict."""
        if self._meta_fn is None:
            return {"index": entry_index}
        return self._meta_fn(entry_index)


# ─────────────────────────────────────────────────────────────────────────────
# Format-specific helpers (private)
# ─────────────────────────────────────────────────────────────────────────────

def _describe_sdt(parsed) -> str:
    from .sdt import describe
    return describe(parsed)


def _decode_sdt(parsed, entry_index: int) -> List[int]:
    from ..codec.psadpcm import decode_psadpcm
    from .sdt import get_audio_stream, deinterleave_channels
    stream = get_audio_stream(parsed)
    if parsed.channels <= 1:
        return decode_psadpcm(stream)
    per_ch = deinterleave_channels(stream, parsed.channels)
    per_ch_pcm = [decode_psadpcm(s) for s in per_ch]
    n = min(len(s) for s in per_ch_pcm) if per_ch_pcm else 0
    out = []
    for i in range(n):
        for ch_samples in per_ch_pcm:
            out.append(ch_samples[i])
    return out


def _meta_sdt(parsed, entry_index: int) -> Dict:
    if 0 <= entry_index < len(parsed.blocks):
        b = parsed.blocks[entry_index]
        return {
            "index": entry_index,
            "file_offset": b.file_offset,
            "data_size": b.data_size,
            "sample_rate": parsed.sample_rate,
            "channels": parsed.channels,
        }
    return {"index": entry_index}


def _describe_sdx(parsed) -> str:
    from .sdx import describe
    return describe(parsed)


def _decode_sdx(parsed, entry_index: int) -> List[int]:
    from .sdx import decode_sample
    if 0 <= entry_index < len(parsed.samples):
        return decode_sample(parsed, parsed.samples[entry_index])
    return []


def _meta_sdx(parsed, entry_index: int) -> Dict:
    if 0 <= entry_index < len(parsed.samples):
        s = parsed.samples[entry_index]
        return {
            "index": s.index,
            "offset": s.offset,
            "size": s.size,
        }
    return {"index": entry_index}


def _describe_bgm(parsed) -> str:
    from .bgm import describe
    return describe(parsed)


def _decode_bgm(parsed, entry_index: int) -> List[int]:
    from .bgm import bgm_entry_to_pcm
    if 0 <= entry_index < len(parsed.entries):
        return bgm_entry_to_pcm(parsed, parsed.entries[entry_index])
    return []


def _meta_bgm(parsed, entry_index: int) -> Dict:
    if 0 <= entry_index < len(parsed.entries):
        e = parsed.entries[entry_index]
        return {
            "index": e.index,
            "sample_rate": e.sample_rate,
            "channels": e.channels,
            "duration": e.duration_seconds,
            "loop_start": e.loop_start,
            "loop_end": e.loop_end,
            "file_offset": e.file_offset,
        }
    return {"index": entry_index}
