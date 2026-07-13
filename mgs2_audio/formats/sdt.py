#!/usr/bin/env python3
"""
sdt.py — The `.sdt` audio files of Metal Gear Solid 2 (Master Collection, PC).

`.sdt` files hold dialogue, music and some sound effects. They are what the
Better Audio Mod ships; the stock Steam files use a different codec (see
`looks_like_psadpcm`).

Layout
------
    header (TOC + metadata)
    a series of "MG blocks": 16-byte header + up to 0x4000 bytes of audio

Concatenated, the block payloads form one PS-ADPCM stream at 44100 Hz.

Stereo files interleave their two channels in chunks of 0x800 bytes
(L, R, L, R...). Flattening them into one mono stream glues channel R about
81 ms behind L — the echo that plagued early versions of this tool.

Some files ("PACB" variants, carrying embedded text) do not expose their channel
count in the header, so it is recovered from the audio itself. See
`docs/FORMATS.md` for the full reverse-engineering notes.

Pure Python, no dependencies.
"""

import math
import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..codec.psadpcm import (
    FRAME_SIZE, SAMPLES_PER_FRAME, VAG_COEFS,
    decode_psadpcm, encode_psadpcm,
)
from ..codec.wav import DEFAULT_SAMPLE_RATE, load_wav_mono, save_wav


# ─────────────────────────────────────────────────────────────────────────────
# Format constants
# ─────────────────────────────────────────────────────────────────────────────

BLOCK_HEADER_SIZE = 16          # header of each MG block
FULL_BLOCK_DATA = 0x4000        # data size of a full block

# Stereo interleave step, in bytes. One 0x4000 data block = 8 chunks of 0x800
# (L R L R L R L R).
CHANNEL_INTERLEAVE = 0x800


# ─────────────────────────────────────────────────────────────────────────────
# Representation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AudioBlock:
    """An audio block within the file."""
    file_offset: int      # position of the block header in the file
    total_size: int       # total size (header + data)
    data_offset: int      # position of the data (file_offset + 16)
    data_size: int        # size of the audio data


@dataclass
class SDTFile:
    """A parsed SDT file."""
    path: str
    raw: bytes
    sample_rate: int = DEFAULT_SAMPLE_RATE
    channels: int = 1
    blocks: List[AudioBlock] = field(default_factory=list)
    is_psadpcm: bool = True   # False if the audio is not PS-ADPCM (unsupported)

    @property
    def has_audio(self) -> bool:
        """True if the file actually contains PS-ADPCM audio blocks."""
        return len(self.blocks) > 0

    @property
    def supported(self) -> bool:
        """True if this file can be decoded/replaced by the tool."""
        return self.has_audio and self.is_psadpcm

    @property
    def total_audio_bytes(self) -> int:
        return sum(b.data_size for b in self.blocks)

    @property
    def units_per_channel(self) -> int:
        """Number of ADPCM units (16 bytes) available PER CHANNEL.

        On a stereo file the audio data is shared between the channels, so the
        usable capacity per channel is the total unit count divided by the
        number of channels.
        """
        total_units = self.total_audio_bytes // 16
        return total_units // self.channels

    @property
    def duration_seconds(self) -> float:
        # PS-ADPCM: 16 bytes -> 28 samples (per channel)
        n_samples = self.units_per_channel * 28
        return n_samples / self.sample_rate

# ─────────────────────────────────────────────────────────────────────────────
# Format detection: sample rate, channel count, codec sanity
# ─────────────────────────────────────────────────────────────────────────────

VALID_SAMPLE_RATES = (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000)


def _detect_format(raw: bytes):
    """Return (sample_rate, channels) for an SDT file.

    Most files store the sample rate big-endian at 0x96 and the channel count
    at 0x98. Some variants (e.g. music/VR files carrying a "PACB" sub-header)
    shift the whole header by a number of bytes, moving those fields. To stay
    robust, we first try the usual fixed offsets, then fall back to scanning the
    header for the anchor <0x7F><rate big-endian><channels> which is present in
    those layouts.

    Returns (sample_rate, channels) where channels may be None when the header
    does not expose it (some PACB variants carrying embedded text). In that case
    the caller falls back to detecting the channel count from the audio content.
    """
    # Primary: fixed offsets 0x96 (rate, big-endian) / 0x98 (channels)
    if len(raw) >= 0x99:
        sr = (raw[0x96] << 8) | raw[0x97]
        ch = raw[0x98]
        if sr in VALID_SAMPLE_RATES and ch in (1, 2):
            return sr, ch

    # Fallback: scan the header for the <0x7F><rate><channels> anchor
    window = raw[:0x400]
    for i in range(len(window) - 3):
        if window[i] != 0x7F:
            continue
        sr = (window[i + 1] << 8) | window[i + 2]
        ch = window[i + 3]
        if sr in VALID_SAMPLE_RATES and ch in (1, 2):
            return sr, ch

    # Last resort: keep a valid rate if we can read one; channels unknown
    sample_rate = DEFAULT_SAMPLE_RATE
    if len(raw) >= 0x98:
        sr = (raw[0x96] << 8) | raw[0x97]
        if sr in VALID_SAMPLE_RATES:
            sample_rate = sr
    return sample_rate, None


def looks_like_psadpcm(stream: bytes, sample_units: int = 3000) -> bool:
    """Heuristic: does this byte stream look like PS-ADPCM?

    In standard VAG every 16-byte frame starts with a header byte whose high
    nibble (the predictor filter) is 0-4.  Other codecs (e.g. XWMA/WMA found
    in some vanilla files) fail this: their "filter" nibble spreads uniformly
    across 0-15.

    The Substance 2003 ``vox.dat`` uses a wider range of predictor values
    (0-15) while still being valid PS-ADPCM — the decoder clamps unknown
    predictors to 0.  The threshold is therefore set generously (50 %) so
    that such files are accepted while pure-random or XWMA streams (where
    every nibble value is equally likely) are still rejected.

    The flag byte (second byte) is not checked because some PS-ADPCM variants
    repurpose it for non-standard metadata.
    """
    if len(stream) < 32:
        return False
    bad = 0
    tot = 0
    for off in range(0, min(len(stream), sample_units * 16), 16):
        header = stream[off]
        if (header >> 4) & 0xF > 4:
            bad += 1
        tot += 1
    return tot > 0 and (bad / tot) < 0.5


def _adjacent_chunk_correlation(pcm: List[int]) -> float:
    """Mean correlation between chunk 2i and chunk 2i+1 of a decoded segment.

    On a stereo file whose two channels carry (nearly) the same centered voice —
    very common for dialogue — consecutive 0x800 chunks are near-duplicates, so
    this is close to +1. On a mono file, consecutive chunks are different moments
    of the same take, so it stays near 0.
    """
    cs = (CHANNEL_INTERLEAVE // 16) * 28
    n_chunks = len(pcm) // cs
    scores = []
    for i in range(0, min(n_chunks - 1, 40), 2):
        a = pcm[i * cs:(i + 1) * cs]
        b = pcm[(i + 1) * cs:(i + 2) * cs]
        m = min(len(a), len(b))
        if m < 64:
            continue
        ma, mb = sum(a) / m, sum(b) / m
        da = [v - ma for v in a[:m]]
        db = [v - mb for v in b[:m]]
        na = math.sqrt(sum(v * v for v in da))
        nb = math.sqrt(sum(v * v for v in db))
        if na < 1.0 or nb < 1.0:      # skip silent chunks
            continue
        scores.append(sum(da[j] * db[j] for j in range(m)) / (na * nb))
    return sum(scores) / len(scores) if scores else 0.0


_BAND_BINS = (2, 3, 4, 6, 8, 11, 14, 18, 23, 29, 37, 47, 60, 76, 96, 120)


def _band_spectrum(pcm: List[int], start: int, window: int = 512) -> Optional[List[float]]:
    """Normalized energy in a few log-spaced bands (Goertzel, pure Python).

    Cheap stand-in for an FFT: enough resolution to tell whether two short
    windows of audio "sound like" a continuation of one another.
    """
    if start < 0 or start + window > len(pcm):
        return None
    step = 2                                   # subsample time: plenty for bands
    samples = pcm[start:start + window:step]
    n = len(samples)
    if n < 32:
        return None
    mags = []
    for k in _BAND_BINS:
        w = 2.0 * math.pi * k / window * step
        cw, sw = math.cos(w), math.sin(w)
        coeff = 2.0 * cw
        s0 = s1 = s2 = 0.0
        for v in samples:
            s0 = v + coeff * s1 - s2
            s2, s1 = s1, s0
        real = s1 - s2 * cw
        imag = s2 * sw
        mags.append(math.hypot(real, imag) + 1e-6)
    total = sum(mags)
    return [m / total for m in mags]


def _spectral_distance(a: List[float], b: List[float]) -> float:
    return sum(abs(a[i] - b[i]) for i in range(len(a)))


def _analysis_windows(stream: bytes, n_chunks: int = 48, count: int = 6) -> List[bytes]:
    """A handful of windows spread across the file.

    A single window is not enough: files often open on silence or ambience, and
    long ones mix passages where the two channels are duplicates with passages
    where they truly differ. Sampling several places and accepting the first
    stereo-looking one makes the decision stable.
    """
    IL = CHANNEL_INTERLEAVE
    total = len(stream) // IL
    if total <= n_chunks:
        return [stream]
    step = max(1, (total - n_chunks) // count)
    starts = range(0, total - n_chunks, step)
    return [stream[s * IL:(s + n_chunks) * IL] for s in starts][:count]


def _window_signals(pcm: List[int], window: int = 512):
    """Return (duplication, d_next, d_after_next) for one decoded window.

    d_next        : mean spectral distance from the end of chunk k to chunk k+1
    d_after_next  : same, but to chunk k+2

    Returns None when the window is too quiet to say anything.
    """
    cs = (CHANNEL_INTERLEAVE // 16) * 28
    n_chunks = len(pcm) // cs
    d_next = d_after = 0.0
    used = 0
    for k in range(min(n_chunks - 2, 30)):
        tail = (k + 1) * cs - window
        a = _band_spectrum(pcm, tail, window)
        b = _band_spectrum(pcm, (k + 1) * cs, window)
        c = _band_spectrum(pcm, (k + 2) * cs, window)
        if a is None or b is None or c is None:
            continue
        seg = pcm[tail:tail + window]
        mean = sum(seg) / len(seg)
        rms = math.sqrt(sum((v - mean) ** 2 for v in seg) / len(seg))
        if rms < 80:                      # skip near-silent transitions
            continue
        d_next += _spectral_distance(a, b)
        d_after += _spectral_distance(a, c)
        used += 1
    if used < 8 or d_next <= 0:
        return None
    return _adjacent_chunk_correlation(pcm), d_next / used, d_after / used


def detect_channels_from_content(stream: bytes) -> int:
    """Guess channel count (1 or 2) from the audio itself.

    Used only when the header does not expose the channel count (some "PACB"
    variants). Each analysis window is checked for two complementary signals,
    either of which means stereo:

      * duplication — the channels carry nearly the same centered voice, so
        chunk 2i and chunk 2i+1 are near-identical (correlation close to +1);
      * continuity — the channels genuinely differ, so the audio of chunk k
        continues into chunk k+2 (same channel) rather than chunk k+1.

    A real mono file triggers neither: adjacent chunks are uncorrelated, and its
    audio continues into the very next chunk. One stereo-looking window is
    enough to call the file stereo.
    """
    if len(stream) < CHANNEL_INTERLEAVE * 8:
        return 1
    for window_bytes in _analysis_windows(stream):
        signals = _window_signals(decode_psadpcm(window_bytes))
        if signals is None:
            continue
        duplication, d_next, d_after = signals
        if duplication > 0.55:
            return 2
        ratio = d_after / d_next
        if ratio < 0.88 and 0.25 < d_next < 0.85:
            return 2
    return 1

def parse_sdt(path: str) -> SDTFile:
    """Read an SDT file and locate its audio blocks."""
    with open(path, "rb") as f:
        raw = f.read()

    sdt = SDTFile(path=path, raw=raw)

    # Sample rate + channel count (robust to header-shifted variants). The
    # channel count may come back None when the header does not expose it.
    sdt.sample_rate, header_channels = _detect_format(raw)

    # Locate the audio blocks (type 1). The last one may be smaller.
    pos = 0
    while pos <= len(raw) - 8:
        typ = struct.unpack_from("<I", raw, pos)[0]
        sz = struct.unpack_from("<I", raw, pos + 4)[0]
        # typ 1 = audio block; upper bound = FULL_BLOCK_DATA (0x4000) + header (16)
        if typ == 1 and 0x1000 <= sz <= 0x4010 and pos + sz <= len(raw):
            sdt.blocks.append(AudioBlock(
                file_offset=pos,
                total_size=sz,
                data_offset=pos + BLOCK_HEADER_SIZE,
                data_size=sz - BLOCK_HEADER_SIZE,
            ))
            pos += sz
        else:
            pos += 4

    # Verify the audio is really PS-ADPCM (some files use other codecs, e.g.
    # XWMA/WMA, which this tool cannot decode).
    stream = get_audio_stream(sdt)
    sdt.is_psadpcm = looks_like_psadpcm(stream) if sdt.blocks else True

    # Resolve the channel count: header value if known, otherwise detect it from
    # the audio content (only meaningful for real PS-ADPCM streams).
    if header_channels is not None:
        sdt.channels = header_channels
    elif sdt.is_psadpcm and len(stream) > FULL_BLOCK_DATA * 2:
        sdt.channels = detect_channels_from_content(stream)
    else:
        sdt.channels = 1

    return sdt


def get_audio_stream(sdt: SDTFile) -> bytes:
    """Concatenate every block's data = the complete PS-ADPCM stream
    (on a stereo file the channels are still interleaved in it)."""
    return b"".join(
        sdt.raw[b.data_offset:b.data_offset + b.data_size]
        for b in sdt.blocks
    )

def deinterleave_channels(adpcm: bytes, channels: int,
                          interleave: int = CHANNEL_INTERLEAVE) -> List[bytes]:
    """Split an interleaved PS-ADPCM stream into `channels` independent streams.

    Interleaving is done in chunks of `interleave` bytes. A trailing partial
    group (fewer than `channels` chunks left over, e.g. a stereo stream ending
    mid L-R pair) is kept rather than dropped: whichever channel(s) have a
    final chunk get it, and the other channel(s) are padded with one silent
    chunk so every stream comes out the same length. Any remainder smaller
    than a single chunk is still dropped (there's nothing to recover there).
    """
    if channels <= 1:
        return [adpcm]

    n_chunks = len(adpcm) // interleave
    full_groups = n_chunks - (n_chunks % channels)  # complete round-robin groups

    streams = [bytearray() for _ in range(channels)]
    for i in range(full_groups):
        chunk = adpcm[i * interleave:(i + 1) * interleave]
        streams[i % channels] += chunk

    leftover = n_chunks - full_groups
    if leftover:
        silence = b"\x00" * interleave
        for ch in range(channels):
            if ch < leftover:
                i = full_groups + ch
                streams[ch] += adpcm[i * interleave:(i + 1) * interleave]
            else:
                streams[ch] += silence

    return [bytes(s) for s in streams]


def interleave_channels(channel_streams: List[bytes],
                        interleave: int = CHANNEL_INTERLEAVE) -> bytes:
    """Re-interleave per-channel PS-ADPCM streams (inverse of deinterleave_channels)."""
    channels = len(channel_streams)
    if channels <= 1:
        return channel_streams[0]

    n_chunks = min(len(s) // interleave for s in channel_streams)
    out = bytearray()
    for i in range(n_chunks):
        for ch in range(channels):
            out += channel_streams[ch][i * interleave:(i + 1) * interleave]
    return bytes(out)

def sdt_to_pcm(sdt: SDTFile) -> List[int]:
    """Decode the whole SDT file into 16-bit PCM samples.

    - Mono file (channels == 1): a flat list of samples, as before.
    - Stereo file (channels == 2): the two channels are first deinterleaved,
      then decoded separately, and the resulting PCM samples are re-interleaved
      in standard WAV order (L, R, L, R…). This is what fixes the echo bug:
      decoding the raw ADPCM stream without deinterleaving glues channel R about
      0x800 bytes (~81 ms) behind L, which is heard as an overlap/echo.
    """
    stream = get_audio_stream(sdt)
    if sdt.channels <= 1:
        return decode_psadpcm(stream)

    per_channel_adpcm = deinterleave_channels(stream, sdt.channels)
    per_channel_pcm = [decode_psadpcm(s) for s in per_channel_adpcm]

    n = min(len(s) for s in per_channel_pcm)
    interleaved: List[int] = []
    for i in range(n):
        for ch_samples in per_channel_pcm:
            interleaved.append(ch_samples[i])
    return interleaved

def sdt_to_wav(sdt: SDTFile, out_path: str):
    """Convert an SDT file to WAV (mono or stereo depending on the source file)."""
    samples = sdt_to_pcm(sdt)
    save_wav(samples, out_path, sdt.sample_rate, channels=sdt.channels)
    return len(samples) // sdt.channels

def replace_audio(sdt: SDTFile, new_samples: List[int]) -> bytes:
    """
    Replace the SDT's audio with new 16-bit PCM samples (mono — the user's
    dub recording).

    The audio is re-encoded to PS-ADPCM then redistributed across the existing
    blocks (same sizes). If the new audio is shorter it is padded with silence;
    if it is longer it is truncated to the blocks' total capacity, so the file
    structure stays EXACTLY the same (required for the game to read it back).

    On a stereo file (channels == 2), the mono dub is encoded once and then
    duplicated onto both channels, which are re-interleaved in chunks of
    CHANNEL_INTERLEAVE bytes (see interleave_channels) to reproduce the original
    layout the game expects. The exact file size is preserved.

    Returns the bytes of the new SDT file.
    """
    channels = sdt.channels
    original_stream = get_audio_stream(sdt)
    total_capacity = len(original_stream)   # PS-ADPCM bytes available (all channels)

    if channels <= 1:
        # ── Mono case: original behavior ─────────────────────────────────────
        channel_capacity = total_capacity
        max_samples = (channel_capacity // 16) * 28

        samples = list(new_samples)
        if len(samples) < max_samples:
            samples += [0] * (max_samples - len(samples))
        else:
            samples = samples[:max_samples]

        new_adpcm = encode_psadpcm(samples)
        if len(new_adpcm) < channel_capacity:
            new_adpcm += b"\x00" * (channel_capacity - len(new_adpcm))
        else:
            new_adpcm = new_adpcm[:channel_capacity]
    else:
        # ── Stereo case: per-channel capacity derived from a real deinterleave ─
        channel_streams = deinterleave_channels(original_stream, channels)
        channel_capacity = min(len(s) for s in channel_streams)  # bytes per channel
        # align to an ADPCM unit (16 bytes) — 0x800 already is, kept for safety
        channel_capacity -= channel_capacity % 16
        max_samples = (channel_capacity // 16) * 28

        samples = list(new_samples)
        if len(samples) < max_samples:
            samples += [0] * (max_samples - len(samples))
        else:
            samples = samples[:max_samples]

        encoded = encode_psadpcm(samples)
        if len(encoded) < channel_capacity:
            encoded += b"\x00" * (channel_capacity - len(encoded))
        else:
            encoded = encoded[:channel_capacity]

        # Same dub on each channel, re-interleaved at the correct step (0x800)
        new_adpcm = interleave_channels([encoded] * channels)

    # Possible trailing remainder (an incomplete chunk not covered by the
    # interleaving): copy the original bytes so the size stays strictly identical.
    if len(new_adpcm) < total_capacity:
        new_adpcm += original_stream[len(new_adpcm):total_capacity]
    elif len(new_adpcm) > total_capacity:
        new_adpcm = new_adpcm[:total_capacity]

    # Reinject block by block (structure and sizes unchanged)
    raw = bytearray(sdt.raw)
    cursor = 0
    for b in sdt.blocks:
        chunk = new_adpcm[cursor:cursor + b.data_size]
        raw[b.data_offset:b.data_offset + b.data_size] = chunk
        cursor += b.data_size

    return bytes(raw)


def save_sdt(raw: bytes, path: str):
    with open(path, "wb") as f:
        f.write(raw)

def describe(sdt: SDTFile) -> str:
    ch_label = "mono" if sdt.channels <= 1 else "stereo"
    return (
        f"File        : {os.path.basename(sdt.path)}\n"
        f"Size        : {len(sdt.raw):,} bytes\n"
        f"Sample rate : {sdt.sample_rate} Hz ({ch_label})\n"
        f"Audio blocks: {len(sdt.blocks)}\n"
        f"Duration    : {sdt.duration_seconds:.2f} s"
    )


def metadata(sdt: SDTFile) -> dict:
    """Return the metadata as separate fields (for display)."""
    return {
        "file": os.path.basename(sdt.path),
        "size": len(sdt.raw),
        "sample_rate": sdt.sample_rate,
        "channels": sdt.channels,
        "blocks": len(sdt.blocks),
        "duration": sdt.duration_seconds,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Command-line interface
# ─────────────────────────────────────────────────────────────────────────────
#
# The engine can be driven entirely from the command line, without opening the
# GUI. Three sub-commands are available:
#
#   info     <file.sdt>                     show metadata (size, rate, channels…)
#   export   <file.sdt> <out.wav>           decode the SDT to a WAV file
#   replace  <file.sdt> <dub.wav> <out.sdt> inject a dub WAV into the SDT
#
# A legacy positional form is also accepted for backward compatibility:
#
#   sdt_core.py <file.sdt> [out.wav]        = info (+ export if out.wav given)

def _cli_info(args) -> int:
    sdt = parse_sdt(args.sdt)
    print(describe(sdt))
    return 0


def _cli_export(args) -> int:
    sdt = parse_sdt(args.sdt)
    print(describe(sdt))
    n = sdt_to_wav(sdt, args.out_wav)
    ch = "stereo" if sdt.channels == 2 else "mono"
    print(f"\n→ WAV written: {args.out_wav}  ({n:,} frames, {ch})")
    return 0


def _cli_replace(args) -> int:
    sdt = parse_sdt(args.sdt)
    print(describe(sdt))
    samples, src_rate = load_wav_mono(args.dub_wav, sdt.sample_rate)
    new_raw = replace_audio(sdt, samples)
    save_sdt(new_raw, args.out_sdt)
    ch = "stereo (dub duplicated on both channels)" if sdt.channels == 2 else "mono"
    print(f"\nDub source : {args.dub_wav}  ({src_rate} Hz)")
    print(f"Re-encoded : PS-ADPCM, {ch}")
    print(f"→ SDT written: {args.out_sdt}  ({len(new_raw):,} bytes, same size as original)")
    return 0


def build_cli():
    import argparse
    p = argparse.ArgumentParser(
        prog="sdt_core.py",
        description="MGS2 SDT engine — inspect, export and re-dub .sdt audio files "
                    "from the command line.")
    sub = p.add_subparsers(dest="command")

    p_info = sub.add_parser("info", help="show metadata of an SDT file")
    p_info.add_argument("sdt", help="path to the .sdt file")
    p_info.set_defaults(func=_cli_info)

    p_exp = sub.add_parser("export", help="decode an SDT file to WAV")
    p_exp.add_argument("sdt", help="path to the .sdt file")
    p_exp.add_argument("out_wav", help="output .wav path")
    p_exp.set_defaults(func=_cli_export)

    p_rep = sub.add_parser("replace", help="inject a dub WAV into an SDT file")
    p_rep.add_argument("sdt", help="path to the original .sdt file")
    p_rep.add_argument("dub_wav", help="your dub recording (.wav)")
    p_rep.add_argument("out_sdt", help="output .sdt path (keep the original name for the game)")
    p_rep.set_defaults(func=_cli_replace)

    return p


def main(argv=None) -> int:
    import sys
    argv = list(sys.argv[1:] if argv is None else argv)

    known = {"info", "export", "replace"}
    # Legacy positional form: "<file.sdt> [out.wav]" (no sub-command given)
    if argv and argv[0] not in known and not argv[0].startswith("-"):
        sdt = parse_sdt(argv[0])
        print(describe(sdt))
        if len(argv) > 1:
            n = sdt_to_wav(sdt, argv[1])
            ch = "stereo" if sdt.channels == 2 else "mono"
            print(f"\n→ WAV written: {argv[1]}  ({n:,} frames, {ch})")
        return 0

    parser = build_cli()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)
