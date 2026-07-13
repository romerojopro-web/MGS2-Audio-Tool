"""
Audio Tool — read, export and replace the audio of
Metal Gear Solid 2 (Master Collection & Substance).

Layers, from the bottom up:

    codec/       PS-ADPCM, MS-ADPCM and WAV. No game knowledge.
    core/        Abstract base classes (GamePlugin) and plugin registry.
    formats/     Shared format parsers (.sdt, .sdx, .bgm, .sequence).
    games/       Game-specific plugins (mgs2_mc, mgs2_substance, …).
    library/     Legacy tagging database (kept for backward compat).
    ui/          PyQt6 interface.  cli.py  Scriptable, no Qt.

The reverse-engineering notes live in docs/FORMATS.md — that document, not this
code, is what someone adapting the tool to another game will need.
"""

__version__ = "3.0.0"
