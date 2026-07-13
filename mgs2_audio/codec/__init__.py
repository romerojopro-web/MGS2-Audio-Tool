"""
codec — Audio codec implementations (PS-ADPCM, MS-ADPCM, WAV).

Pure Python, no game-specific knowledge.
"""

from .psadpcm import decode_psadpcm, encode_psadpcm
from .msadpcm import decode_msadpcm
from .wav import load_wav_mono, save_wav

__all__ = [
    "decode_psadpcm", "encode_psadpcm",
    "decode_msadpcm",
    "load_wav_mono", "save_wav",
]
