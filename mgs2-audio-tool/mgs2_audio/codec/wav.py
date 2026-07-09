#!/usr/bin/env python3
"""
wav.py — Reading and writing WAV files, with no game-specific knowledge.

Just enough of the format to load a user's recording and to hand decoded audio
back to them. Resampling is nearest-neighbour: crude, but the tool always tells
the user to record at the target rate anyway.

Pure Python (the standard library's `wave` module), no dependencies.
"""

import struct
import wave
from typing import List, Tuple

DEFAULT_SAMPLE_RATE = 44100


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
