"""
formats — Shared audio format parsers for MGS2.

Provides detection, parsing and description for SDT, SDX, BGM and Sequence
formats.  The ``detect`` module offers auto-detection; individual modules
handle their own format.
"""

from .detect import Format, detect_path, open_file

__all__ = ["Format", "detect_path", "open_file"]
