"""
MGS2 Audio Tool — read, export and replace the audio of
Metal Gear Solid 2: Sons of Liberty (Master Collection, PC).

Layers, from the bottom up:

    codec/     PS-ADPCM and WAV. No game knowledge.
    formats/   .sdt (dialogue, music) and .sdx (stage sound banks).
    library/   The tagging databases.
    ui/        PyQt6 interface.  cli.py  Scriptable, no Qt.

The reverse-engineering notes live in docs/FORMATS.md — that document, not this
code, is what someone adapting the tool to another game will need.
"""

__version__ = "2.0.0"
