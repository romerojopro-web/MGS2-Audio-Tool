#!/usr/bin/env python3
"""
ffmpeg.py — Optional bridge to an external ffmpeg binary.

Decoding WMA (the codec inside Konami XWMA) is impractical in pure Python, so
the stock-`.sdt` (XWMA) feature shells out to ffmpeg — the first and only
external-binary dependency in the project, and an optional one: everything
else works without it, exactly like UnityPy for the BGM tab.

ffmpeg is located via `shutil.which`, or a path the user points at (persisted
in the app config as `ffmpeg_path`).
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


class FfmpegMissing(RuntimeError):
    """ffmpeg was not found — the XWMA feature needs it."""

    def __init__(self):
        super().__init__(
            "ffmpeg is required to decode the stock (XWMA) .sdt audio. "
            "Install it (e.g. `winget install ffmpeg`) and make sure it is on "
            "your PATH, or point the tool at the ffmpeg.exe you downloaded.")


def find_ffmpeg(configured_path: Optional[str] = None) -> Optional[str]:
    """Return a usable ffmpeg path, or None.

    Order: an explicitly configured path (if it exists), then whatever is on
    the system PATH.
    """
    if configured_path and os.path.isfile(configured_path):
        return configured_path
    return shutil.which("ffmpeg")


def decode_to_wav(riff_xwma: bytes, out_wav: str,
                  ffmpeg_path: Optional[str] = None) -> None:
    """Decode standard RIFF xWMA bytes to a WAV file using ffmpeg.

    Raises FfmpegMissing when ffmpeg can't be found, or RuntimeError with
    ffmpeg's own message when the conversion fails.
    """
    exe = find_ffmpeg(ffmpeg_path)
    if not exe:
        raise FfmpegMissing()

    fd, tmp = tempfile.mkstemp(suffix=".xwma")
    os.close(fd)
    try:
        with open(tmp, "wb") as f:
            f.write(riff_xwma)
        proc = subprocess.run(
            [exe, "-y", "-loglevel", "error", "-i", tmp, out_wav],
            capture_output=True, text=True,
        )
        if proc.returncode != 0 or not os.path.exists(out_wav):
            tail = (proc.stderr or "").strip().splitlines()
            msg = tail[-1] if tail else f"ffmpeg exited with {proc.returncode}"
            raise RuntimeError(f"ffmpeg failed: {msg}")
    finally:
        try:
            os.unlink(tmp)
        except OSError:
            pass


def available(configured_path: Optional[str] = None) -> bool:
    """Whether ffmpeg can be found right now."""
    return find_ffmpeg(configured_path) is not None
