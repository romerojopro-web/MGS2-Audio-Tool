"""Tests for the PS-ADPCM codec: it must not know anything about MGS2."""

import math
import random

from mgs2_audio.codec import psadpcm


def speech_like(n):
    """A signal with a wandering pitch and envelope: closer to a voice than a sine."""
    return [int(6000 * math.sin(2 * math.pi * (150 + 60 * math.sin(i * 0.0007)) * i / 44100)
                * (0.5 + 0.5 * math.sin(i * 0.0002)))
            for i in range(n)]


def test_frame_arithmetic():
    assert psadpcm.FRAME_SIZE == 16
    assert psadpcm.SAMPLES_PER_FRAME == 28
    assert psadpcm.samples_for_bytes(160) == 280
    assert psadpcm.bytes_for_samples(280) == 160
    # a partial frame still needs a whole frame of storage
    assert psadpcm.bytes_for_samples(1) == 16
    assert psadpcm.frame_count(31) == 1


def test_decode_length_matches_frames():
    random.seed(1)
    data = bytearray(random.randrange(256) for _ in range(16 * 10))
    for i in range(0, len(data), 16):
        data[i] = (random.randrange(5) << 4) | random.randrange(13)
    pcm = psadpcm.decode_psadpcm(bytes(data))
    assert len(pcm) == 10 * psadpcm.SAMPLES_PER_FRAME


def test_encode_produces_whole_frames():
    pcm = speech_like(28 * 7 + 5)          # not a multiple of 28
    data = psadpcm.encode_psadpcm(pcm)
    assert len(data) % psadpcm.FRAME_SIZE == 0
    assert len(data) == 8 * psadpcm.FRAME_SIZE   # padded up to the next frame


def test_encoded_frames_are_valid():
    """Every frame must carry a legal filter (0-4); other tools rely on it."""
    data = psadpcm.encode_psadpcm(speech_like(28 * 40))
    for off in range(0, len(data), 16):
        assert (data[off] >> 4) & 0xF <= 4


def test_round_trip_is_close_enough():
    pcm = speech_like(28 * 200)
    out = psadpcm.decode_psadpcm(psadpcm.encode_psadpcm(pcm))
    assert len(out) >= len(pcm)
    peak = max(abs(v) for v in pcm)
    worst = max(abs(a - b) for a, b in zip(pcm, out))
    assert worst < peak * 0.05           # lossy, but not by much


def test_silence_round_trips_to_silence():
    out = psadpcm.decode_psadpcm(psadpcm.encode_psadpcm([0] * 280))
    assert max(abs(v) for v in out) == 0


def test_decode_ignores_trailing_partial_frame():
    data = psadpcm.encode_psadpcm(speech_like(280)) + b"\x00\x01\x02"
    pcm = psadpcm.decode_psadpcm(data)
    assert len(pcm) == 280
