#!/usr/bin/env python3
"""
seo2.py — `BP_SE.DAT`, the game's global sound container (`SEO2`).

`Misc/<lang>/BP_SE.DAT` is read **once at startup and never again**: its sounds
stay resident for the whole session. That is why they turn up in no `.sdx` and
why nothing is read from disk when, say, the alert alarm fires.

What it holds is not background music but the game's **iconic global sounds** —
item selection and pickup, using an item, interface blips, the alert-phase
alarm. Until now nothing could reach them.

Layout
------
    0x00  "SEO2"
    0x04  u32 = 1
    0x08  u32 count
    0x0C  count records of 0x60 bytes:
            +0   u32  id        (high byte 0x02; the low 16 bits identify the sound)
            +4   u32  channels  (1 or 2)
            +8   u32  data offset
            +12  u32  data length PER CHANNEL
            +16  0x50 bytes, not yet understood

The record layout is not a guess: `offset + length * channels` equals the next
entry's offset right across the table.

The payload is **PS-ADPCM at 44100 Hz** carrying **no end flags** — the table
gives the length instead. A stereo sound stores one whole channel after the
other, not interleaved.

Replacing keeps each sound's exact byte size, exactly as `.sdx` replacement
does, so every offset in the table stays valid.

Pure Python, no dependencies.
"""

import glob as _glob
import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional

from ..codec import psadpcm as codec
from ..codec.wav import load_wav_mono as _load_wav, save_wav

MAGIC = b"SEO2"
HEADER_SIZE = 0x0C
RECORD_SIZE = 0x60
SAMPLE_RATE = 44100        # confirmed by ear: the sounds play at their true pitch


@dataclass
class SEO2Sound:
    """One sound in the container."""
    index: int
    sound_id: int
    channels: int
    offset: int            # byte offset of the first channel
    length: int            # bytes PER CHANNEL

    @property
    def total_bytes(self) -> int:
        return self.length * self.channels

    @property
    def frames(self) -> int:
        return self.length // codec.FRAME_SIZE

    @property
    def duration_seconds(self) -> float:
        return self.frames * codec.SAMPLES_PER_FRAME / SAMPLE_RATE


@dataclass
class SEO2File:
    """A parsed `BP_SE.DAT`."""
    path: str
    raw: bytes
    sounds: List[SEO2Sound] = field(default_factory=list)

    @property
    def sample_rate(self) -> int:
        return SAMPLE_RATE

    @property
    def has_audio(self) -> bool:
        return bool(self.sounds)


FILENAME = "BP_SE.DAT"


def find_bp_se(game_root: str) -> Optional[str]:
    """Locate `BP_SE.DAT` given the game's root folder.

    The engine builds the path as `Misc/<lang>/BP_SE.DAT`, so the usual layout is
    `<game>/Misc/us/BP_SE.DAT`. The user is asked for the game folder and the
    rest is resolved here; pointing straight at the file or at `Misc/` works too.
    """
    if not game_root:
        return None
    if os.path.isfile(game_root):
        return game_root if os.path.basename(game_root).upper() == FILENAME else None
    if not os.path.isdir(game_root):
        return None

    candidates = [os.path.join(game_root, FILENAME)]
    for lang in ("us", "eu", "jp", "uk"):
        candidates.append(os.path.join(game_root, "Misc", lang, FILENAME))
        candidates.append(os.path.join(game_root, lang, FILENAME))
    for path in candidates:
        if os.path.isfile(path):
            return path

    # Fall back to a search, preferring the shallowest match.
    found = _glob.glob(os.path.join(game_root, "**", FILENAME), recursive=True)
    if not found:
        # Windows paths are case-insensitive, but a case-sensitive host is not.
        found = [p for p in _glob.glob(os.path.join(game_root, "**", "*.DAT"),
                                       recursive=True)
                 if os.path.basename(p).upper() == FILENAME]
    return min(found, key=lambda p: p.count(os.sep)) if found else None


def is_seo2(raw: bytes) -> bool:
    return raw[:4] == MAGIC


def parse_seo2(path: str) -> SEO2File:
    """Read a `BP_SE.DAT`. Raises ValueError when it isn't one."""
    with open(path, "rb") as f:
        raw = f.read()
    if not is_seo2(raw):
        raise ValueError(f"{path}: not a SEO2 container")

    count = struct.unpack_from("<I", raw, 8)[0]
    out = SEO2File(path=path, raw=raw)
    for i in range(count):
        rec = HEADER_SIZE + i * RECORD_SIZE
        if rec + 16 > len(raw):
            break
        sid, channels, offset, length = struct.unpack_from("<IIII", raw, rec)
        # Skip anything that doesn't describe real audio rather than trusting the
        # count blindly — a malformed tail should not sink the whole file.
        if channels not in (1, 2) or length == 0:
            continue
        if offset + length * channels > len(raw):
            continue
        out.sounds.append(SEO2Sound(index=i, sound_id=sid & 0xFFFF,
                                    channels=channels, offset=offset,
                                    length=length))
    return out


def channel_bytes(seo: SEO2File, sound: SEO2Sound, channel: int = 0) -> bytes:
    start = sound.offset + channel * sound.length
    return seo.raw[start:start + sound.length]


def decode_sound(seo: SEO2File, sound: SEO2Sound) -> List[int]:
    """Decode to 16-bit PCM, interleaved when the sound is stereo."""
    if sound.channels == 1:
        return codec.decode_psadpcm(channel_bytes(seo, sound, 0))
    left = codec.decode_psadpcm(channel_bytes(seo, sound, 0))
    right = codec.decode_psadpcm(channel_bytes(seo, sound, 1))
    n = min(len(left), len(right))
    out = []
    for i in range(n):
        out.append(left[i])
        out.append(right[i])
    return out


def sound_to_wav(seo: SEO2File, sound: SEO2Sound, out_path: str) -> int:
    pcm = decode_sound(seo, sound)
    save_wav(pcm, out_path, SAMPLE_RATE, channels=sound.channels)
    return len(pcm)


def load_wav_mono(path: str) -> List[int]:
    """Load a WAV as mono 16-bit samples at the container's rate."""
    pcm, _ = _load_wav(path, SAMPLE_RATE)
    return pcm


def _encode_exact(pcm: List[int], size: int) -> bytearray:
    """Encode PCM into exactly `size` bytes of PS-ADPCM (padding or trimming)."""
    frames = size // codec.FRAME_SIZE
    wanted = frames * codec.SAMPLES_PER_FRAME
    data = list(pcm)
    if len(data) < wanted:
        data += [0] * (wanted - len(data))
    else:
        data = data[:wanted]
    encoded = bytearray(codec.encode_psadpcm(data))
    if len(encoded) < size:
        encoded += b"\x00" * (size - len(encoded))
    else:
        del encoded[size:]
    return encoded


def replace_sound(seo: SEO2File, sound: SEO2Sound, new_pcm: List[int]) -> bytes:
    """Replace one sound's audio, keeping its exact byte size and frame flags.

    A mono recording put into a stereo sound is copied to both channels, which
    is what the `.sdt` and `.sdx` paths do too. Returns the new file bytes.
    """
    raw = bytearray(seo.raw)
    for ch in range(sound.channels):
        original = channel_bytes(seo, sound, ch)
        encoded = _encode_exact(new_pcm, sound.length)
        # These payloads carry no end flags, but any flag the original does set
        # belongs to the sound, not to our re-encoding.
        for i in range(sound.frames):
            encoded[i * codec.FRAME_SIZE + 1] = original[i * codec.FRAME_SIZE + 1]
        start = sound.offset + ch * sound.length
        raw[start:start + sound.length] = bytes(encoded)
    return bytes(raw)


def save_seo2(raw: bytes, path: str):
    with open(path, "wb") as f:
        f.write(raw)


def describe(seo: SEO2File) -> str:
    total = sum(s.total_bytes for s in seo.sounds)
    secs = sum(s.duration_seconds for s in seo.sounds)
    return (
        f"File        : {os.path.basename(seo.path)}\n"
        f"Size        : {len(seo.raw):,} bytes\n"
        f"Sample rate : {SAMPLE_RATE} Hz\n"
        f"Sounds      : {len(seo.sounds)} ({total:,} bytes, {secs:.1f}s of audio)"
    )


def list_sounds(seo: SEO2File) -> str:
    rows = [f"{'idx':>4}  {'id':>5}  {'ch':>2}  {'offset':>10}  {'bytes':>9}  duration"]
    for s in seo.sounds:
        rows.append(f"{s.index:>4}  {s.sound_id:#05x}  {s.channels:>2}  "
                    f"{s.offset:>10}  {s.total_bytes:>9,}  {s.duration_seconds:6.2f}s")
    return "\n".join(rows)
