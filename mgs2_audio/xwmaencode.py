#!/usr/bin/env python3
"""
xwmaencode.py — Optional bridge to Microsoft's `xWMAEncode.exe`.

Producing **game-compatible** Konami XWMA requires WMA encoded exactly the way
the game expects.  ffmpeg's wmav2 encoder does not qualify: its bitstream needs
codec-private extradata that the Konami `AMWX` container has no slot for, so the
game can't decode it.  Microsoft's `xWMAEncode` (a small tool from the legacy
DirectX SDK, widely mirrored in modding circles) produces xWMA that decodes with
no extradata — which is what the game does.  So replacement (unlike decode) uses
xWMAEncode, not ffmpeg.

Located via a path the user sets in the config (`xwmaencode_path`) or on PATH.
"""

import os
import shutil
import subprocess
import tempfile
from typing import Optional


class XwmaEncodeMissing(RuntimeError):
    """xWMAEncode.exe was not found — replacing stock XWMA audio needs it."""

    def __init__(self):
        super().__init__(
            "xWMAEncode.exe is required to build game-compatible XWMA audio "
            "(ffmpeg's WMA isn't accepted by the game). It ships with the "
            "legacy DirectX SDK and is widely mirrored; point the tool at your "
            "xWMAEncode.exe.")


def find_xwmaencode(configured_path: Optional[str] = None) -> Optional[str]:
    """Return a usable xWMAEncode path, or None."""
    if configured_path and os.path.isfile(configured_path):
        return configured_path
    return shutil.which("xWMAEncode") or shutil.which("xwmaencode")


def available(configured_path: Optional[str] = None) -> bool:
    return find_xwmaencode(configured_path) is not None


def encode_to_xwma(wav_path: str, exe_path: Optional[str] = None) -> bytes:
    """Encode a WAV file to standard RIFF xWMA bytes using xWMAEncode.

    Raises XwmaEncodeMissing when the tool can't be found, or RuntimeError with
    the tool's message when encoding fails.
    """
    exe = find_xwmaencode(exe_path)
    if not exe:
        raise XwmaEncodeMissing()

    fd, out = tempfile.mkstemp(suffix=".xwma")
    os.close(fd)
    try:
        proc = subprocess.run([exe, wav_path, out],
                              capture_output=True, text=True)
        if proc.returncode != 0 or not os.path.exists(out) \
                or os.path.getsize(out) == 0:
            tail = ((proc.stderr or proc.stdout or "").strip().splitlines()
                    or [f"xWMAEncode exited with {proc.returncode}"])
            raise RuntimeError(f"xWMAEncode failed: {tail[-1]}")
        with open(out, "rb") as f:
            return f.read()
    finally:
        try:
            os.unlink(out)
        except OSError:
            pass
