#!/usr/bin/env python3
"""
sdt_core.py — Conversion engine for the SDT audio files of Metal Gear Solid 2
              (Master Collection, PC version).

Format discovered through reverse-engineering:
  - Audio codec : PlayStation 4-bit ADPCM (PS-ADPCM / VAG)
  - Sample rate : 44100 Hz
  - Channels    : 1 (mono) or 2 (stereo) — see the channel byte at 0x98
  - Structure   : header (TOC + metadata) followed by a series of "MG blocks"
                  (Metal Gear blocks). Each block = 16-byte header + 0x4000
                  bytes of audio data (the last block may be shorter). All
                  blocks concatenated form the complete audio stream.

Stereo layout: on 2-channel files, the two channels are interleaved in chunks
of 0x800 bytes (L, R, L, R...). See CHANNEL_INTERLEAVE and the note above
deinterleave_channels() for why decoding the raw stream as mono produces an echo.

This module has no external dependencies: PS-ADPCM decoding and encoding are
implemented in pure Python.
"""

import os
import struct
import wave
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Format constants
# ─────────────────────────────────────────────────────────────────────────────

BLOCK_HEADER_SIZE = 16          # header of each MG block
FULL_BLOCK_DATA = 0x4000        # data size of a full block
DEFAULT_SAMPLE_RATE = 44100

# Stereo interleave step, in bytes. On 2-channel files the audio is stored as
# large 0x800-byte chunks that alternate channel L / channel R (a classic
# PS-ADPCM interleave value). One 0x4000 data block = 8 chunks of 0x800
# (L R L R L R L R).
CHANNEL_INTERLEAVE = 0x800

# Sony PS-ADPCM prediction coefficients (scaled by /64)
VAG_COEFS = [
    (0.0, 0.0),
    (60.0 / 64.0, 0.0),
    (115.0 / 64.0, -52.0 / 64.0),
    (98.0 / 64.0, -55.0 / 64.0),
    (122.0 / 64.0, -60.0 / 64.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# SDT file representation
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
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_sdt(path: str) -> SDTFile:
    """Read an SDT file and locate its audio blocks."""
    with open(path, "rb") as f:
        raw = f.read()

    sdt = SDTFile(path=path, raw=raw)

    # Sample rate: stored big-endian at 0x96 in the header
    if len(raw) >= 0x98:
        sr = (raw[0x96] << 8) | raw[0x97]
        if sr in (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000):
            sdt.sample_rate = sr

    # Channel count: byte at 0x98. 1 = mono (the common case), 2 = stereo —
    # in which case the channels are interleaved in chunks of CHANNEL_INTERLEAVE
    # bytes (see deinterleave_channels).
    if len(raw) >= 0x99:
        ch = raw[0x98]
        if ch in (1, 2):
            sdt.channels = ch

    # Locate the audio blocks (type 1). The last one may be smaller.
    pos = 0
    while pos < len(raw) - 8:
        typ = struct.unpack_from("<I", raw, pos)[0]
        sz = struct.unpack_from("<I", raw, pos + 4)[0]
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

    return sdt


def get_audio_stream(sdt: SDTFile) -> bytes:
    """Concatenate every block's data = the complete PS-ADPCM stream
    (on a stereo file the channels are still interleaved in it)."""
    return b"".join(
        sdt.raw[b.data_offset:b.data_offset + b.data_size]
        for b in sdt.blocks
    )


# ─────────────────────────────────────────────────────────────────────────────
# Channel (de)interleaving (stereo files)
# ─────────────────────────────────────────────────────────────────────────────
#
# On stereo files (channels = 2 in the header), the audio is interleaved in
# large chunks of CHANNEL_INTERLEAVE bytes (0x800): chunk L, chunk R, chunk L,
# chunk R... Decoding the raw stream as a single mono flow flattens the two
# channels together: channel R ends up "glued" 0x800 bytes after L (about 81 ms
# at 44100 Hz), which produces the characteristic echo / overlap. Deinterleaving
# at the correct step (0x800) and decoding each channel separately removes the
# echo and restores the correct speed.

def deinterleave_channels(adpcm: bytes, channels: int,
                          interleave: int = CHANNEL_INTERLEAVE) -> List[bytes]:
    """Split an interleaved PS-ADPCM stream into `channels` independent streams.

    Interleaving is done in chunks of `interleave` bytes. Any trailing
    remainder (an incomplete chunk) is dropped here and must be handled by the
    caller if its exact preservation matters.
    """
    if channels <= 1:
        return [adpcm]

    n_chunks = len(adpcm) // interleave
    n_chunks -= n_chunks % channels  # keep only complete groups

    streams = [bytearray() for _ in range(channels)]
    for i in range(n_chunks):
        chunk = adpcm[i * interleave:(i + 1) * interleave]
        streams[i % channels] += chunk
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


# ─────────────────────────────────────────────────────────────────────────────
# PS-ADPCM decoding  →  16-bit PCM
# ─────────────────────────────────────────────────────────────────────────────

def decode_psadpcm(adpcm: bytes) -> List[int]:
    """Decode a PS-ADPCM stream (16-byte units) into 16-bit PCM samples."""
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


def save_wav(samples: List[int], path: str, sample_rate: int = DEFAULT_SAMPLE_RATE,
             channels: int = 1):
    """Write a list of 16-bit samples to a WAV file.

    `samples` must already be interleaved if channels > 1 (L, R, L, R…),
    as returned by sdt_to_pcm().
    """
    with wave.open(path, "w") as wf:
        wf.setnchannels(channels)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        clamped = [max(-32768, min(32767, s)) for s in samples]
        wf.writeframes(struct.pack(f"<{len(clamped)}h", *clamped))


def sdt_to_wav(sdt: SDTFile, out_path: str):
    """Convert an SDT file to WAV (mono or stereo depending on the source file)."""
    samples = sdt_to_pcm(sdt)
    save_wav(samples, out_path, sdt.sample_rate, channels=sdt.channels)
    return len(samples) // sdt.channels


# ─────────────────────────────────────────────────────────────────────────────
# 16-bit PCM encoding  →  PS-ADPCM
# ─────────────────────────────────────────────────────────────────────────────

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


def load_wav_mono(path: str, target_rate: int = DEFAULT_SAMPLE_RATE) -> Tuple[List[int], int]:
    """
    Load a WAV file as 16-bit mono samples.
    Converts stereo→mono and resamples if needed (simple, no filtering).
    Returns (samples, original_sample_rate).
    """
    with wave.open(path, "r") as wf:
        n_ch = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)

    # Convert to 16-bit samples
    if width == 2:
        data = list(struct.unpack(f"<{len(raw)//2}h", raw))
    elif width == 1:
        data = [(b - 128) * 256 for b in raw]
    else:
        # 24/32-bit: keep only the two high-order bytes
        step = width
        data = []
        for i in range(0, len(raw), step):
            data.append(struct.unpack_from("<h", raw, i + step - 2)[0])

    # Stereo → mono
    if n_ch > 1:
        mono = []
        for i in range(0, len(data) - n_ch + 1, n_ch):
            mono.append(sum(data[i:i + n_ch]) // n_ch)
        data = mono

    # Naive resampling (nearest neighbor) if needed
    if rate != target_rate and rate > 0:
        ratio = target_rate / rate
        new_len = int(len(data) * ratio)
        resampled = [data[min(len(data) - 1, int(i / ratio))] for i in range(new_len)]
        data = resampled

    return data, rate


# ─────────────────────────────────────────────────────────────────────────────
# Audio replacement: inject a new WAV into an existing SDT
# ─────────────────────────────────────────────────────────────────────────────

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


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable summary
# ─────────────────────────────────────────────────────────────────────────────

def describe(sdt: SDTFile) -> str:
    ch_label = "mono" if sdt.channels <= 1 else "stereo"
    return (
        f"File        : {sdt.path.split('/')[-1]}\n"
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


if __name__ == "__main__":
    import sys
    sys.exit(main())
