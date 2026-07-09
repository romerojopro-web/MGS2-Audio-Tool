"""Shared fixtures: synthetic .sdt and .sdx files built from scratch.

No copyrighted game data is needed to test the tool. These builders produce
files with the same structure the game uses, so the parsers and writers get
exercised end to end.

PS-ADPCM frames are written directly rather than run through the encoder: the
encoder brute-forces every filter and shift, which is far too slow for a test
suite. `speech_like` stays available for the codec's own round-trip tests.
"""

import math
import random
import struct

import pytest

from mgs2_audio.codec import psadpcm
from mgs2_audio.formats import sdt as sdt_fmt
from mgs2_audio.formats import sdx as sdx_fmt

FRAMES_PER_CHUNK = sdt_fmt.CHANNEL_INTERLEAVE // psadpcm.FRAME_SIZE


def speech_like(n, base=150):
    """PCM with a wandering pitch and envelope."""
    return [int(6000 * math.sin(2 * math.pi * (base + 60 * math.sin(i * 0.0007)) * i / 44100)
                * (0.5 + 0.5 * math.sin(i * 0.0002)))
            for i in range(n)]


def tone(n, freq, rate=22050, amp=8000):
    return [int(amp * math.sin(2 * math.pi * freq * i / rate)) for i in range(n)]


# ─────────────────────────────────────────────────────────────────────────────
# Raw PS-ADPCM frame builders (fast: no encoder search)
# ─────────────────────────────────────────────────────────────────────────────

def adpcm_sweep(frames, period_from, period_to, shift=2, noise=0.0, seed=7):
    """Frames whose pitch drifts over time — non-stationary, like real speech.

    `shift` is small on purpose so the decoded audio is loud: the channel
    detector skips near-silent passages, and a quiet fixture would tell it
    nothing.
    """
    rng = random.Random(seed)
    out = bytearray()
    for f in range(frames):
        out.append(shift)                      # filter 0, given shift
        out.append(0)                          # no loop / end flag
        period = period_from + (period_to - period_from) * f / max(1, frames - 1)
        for i in range(14):
            t = f * 14 + i
            a = int(7 * math.sin(2 * math.pi * t / period)) & 0xF
            b = int(7 * math.sin(2 * math.pi * (t + 0.5) / period)) & 0xF
            if noise and rng.random() < noise:
                a = rng.randrange(16)
            out.append(a | (b << 4))
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────────
# .sdt builders
# ─────────────────────────────────────────────────────────────────────────────

def build_sdt(path, channels=1, blocks=1, audio=None):
    """A minimal but structurally faithful .sdt: header, then MG blocks."""
    payload = sdt_fmt.FULL_BLOCK_DATA
    adpcm = audio if audio is not None else b"\x00" * (payload * blocks)
    if len(adpcm) < payload * blocks:
        adpcm = adpcm + b"\x00" * (payload * blocks - len(adpcm))

    raw = bytearray(0x100)
    raw[0x96] = 0xAC          # 44100, big-endian
    raw[0x97] = 0x44
    raw[0x98] = channels

    for i in range(blocks):
        raw += struct.pack("<II", 1, sdt_fmt.BLOCK_HEADER_SIZE + payload)
        raw += b"\x00" * 8
        raw += adpcm[i * payload:(i + 1) * payload]

    path.write_bytes(bytes(raw))
    return str(path)


def build_stereo_sdt(path, left=None, right=None, chunks=48):
    """A stereo .sdt with the game's 0x800 interleave.

    The two channels are *similar but distinct*, as a real recording's are: the
    detector's continuity test targets that case. Two wildly different channels
    would push the spectral distance past the detector's guard and be read as
    mono — a real limitation, noted in docs/FORMATS.md.
    """
    frames = chunks * FRAMES_PER_CHUNK
    left = left if left is not None else adpcm_sweep(frames, 30, 12)
    right = right if right is not None else adpcm_sweep(frames, 31, 12.5, seed=11)
    stream = sdt_fmt.interleave_channels([left, right])
    blocks = max(1, -(-len(stream) // sdt_fmt.FULL_BLOCK_DATA))
    return build_sdt(path, channels=2, blocks=blocks, audio=stream)


def blank_header_fields(path):
    """Erase the sample-rate and channel bytes, as the 'PACB' variants do."""
    raw = bytearray(open(path, "rb").read())
    raw[0x96] = raw[0x97] = raw[0x98] = 0
    open(path, "wb").write(bytes(raw))
    return path


# ─────────────────────────────────────────────────────────────────────────────
# .sdx builders
# ─────────────────────────────────────────────────────────────────────────────

def build_sdx(path, sounds):
    """A .sdx bank: header, samples each ending on a flagged frame, padding."""
    raw = bytearray(sdx_fmt.DATA_START)
    for pcm in sounds:
        data = bytearray(psadpcm.encode_psadpcm(pcm))
        data[-psadpcm.FRAME_SIZE + 1] = psadpcm.FLAG_END
        raw += data
    raw += b"\xff" * 0x100        # padding marks the end of the audio region
    raw += b"\x00" * 0x100        # stand-in for the bank table / sequence
    path.write_bytes(bytes(raw))
    return str(path)


def build_stage_tree(root, banks):
    """A `<game>/us/stage/<stage>/pk000000.sdx` tree. `banks` maps stage -> sounds."""
    stage = root / "us" / "stage"
    for name, sounds in banks.items():
        folder = stage / name
        folder.mkdir(parents=True)
        build_sdx(folder / "pk000000.sdx", sounds)
    return str(root)


# ─────────────────────────────────────────────────────────────────────────────
# Fixtures
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def mono_sdt(tmp_path):
    audio = adpcm_sweep(48 * FRAMES_PER_CHUNK, 30, 12)
    blocks = max(1, -(-len(audio) // sdt_fmt.FULL_BLOCK_DATA))
    return build_sdt(tmp_path / "vc000101.sdt", channels=1, blocks=blocks, audio=audio)


@pytest.fixture
def stereo_sdt(tmp_path):
    return build_stereo_sdt(tmp_path / "vc117031.sdt")


@pytest.fixture
def dual_mono_sdt(tmp_path):
    """Stereo whose channels are duplicates — the usual case for centred voice."""
    frames = 48 * FRAMES_PER_CHUNK
    channel = adpcm_sweep(frames, 30, 12)
    return build_stereo_sdt(tmp_path / "dual.sdt", left=channel, right=channel)


@pytest.fixture
def bank(tmp_path):
    return build_sdx(tmp_path / "pk000000.sdx",
                     [tone(6000, 300), tone(9000, 440), tone(4000, 220)])
