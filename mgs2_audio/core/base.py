#!/usr/bin/env python3
"""
base.py — Abstract base classes for the multi-game audio tool.

A ``GamePlugin`` declares its UI pages and CLI subcommands, grouped into one
or more "modes" (e.g. Master Collection vs Substance), each with its own
stylesheet key. The tool shell (app.py, cli.py) never imports game-specific
code directly — it works exclusively through these interfaces.

Pure Python, no dependencies.
"""

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, List, Optional, Tuple, Type


# ─────────────────────────────────────────────────────────────────────────────
# Audio format descriptor
# ─────────────────────────────────────────────────────────────────────────────

class AudioFormat(ABC):
    """Describes one audio container format (e.g. SDT, SDX, BGM)."""

    name: str = ""                  # "SDT", "SDX", "BGM", etc.

    @staticmethod
    @abstractmethod
    def detect(raw: bytes) -> bool:
        """Return True if *raw* looks like this format."""

    @staticmethod
    @abstractmethod
    def parse(path: str) -> Any:
        """Parse the file at *path* and return a format-specific object."""

    @staticmethod
    def describe(parsed: Any) -> str:
        """Return a human-readable summary of a parsed object."""
        return str(parsed)


# ─────────────────────────────────────────────────────────────────────────────
# Audio container — uniform interface over any multi-entry format
# ─────────────────────────────────────────────────────────────────────────────

class AudioContainer(ABC):
    """Uniform read-only interface over a parsed audio file.

    Wraps a parsed object and exposes a small, common API regardless of
    the underlying format.  Created via ``from_path(path)`` — do not
    instantiate directly.
    """

    path: str
    entry_count: int
    sample_rate: int
    channels: int

    @classmethod
    @abstractmethod
    def from_path(cls, path: str) -> "AudioContainer":
        """Auto-detect and open the file at *path*."""

    @abstractmethod
    def describe(self) -> str:
        """Human-readable summary string."""

    @abstractmethod
    def decode_pcm(self, entry_index: int) -> List[int]:
        """Decode entry *entry_index* into interleaved 16-bit PCM."""

    def entry_metadata(self, entry_index: int) -> Dict:
        """Return per-entry metadata as a dict."""
        return {"index": entry_index}


# ─────────────────────────────────────────────────────────────────────────────
# UI page specification
# ─────────────────────────────────────────────────────────────────────────────

class PageSpec:
    """Declares one tab in the UI.

    Attributes:
        key:      short identifier (e.g. "sdt", "bgm")
        cls:      the QWidget subclass (lazy import OK — pass the class itself)
        tab_key:  i18n key for the tab label (e.g. "tab_sdt")
    """

    __slots__ = ("key", "cls", "tab_key")

    def __init__(self, key: str, cls: Type, tab_key: str):
        self.key = key
        self.cls = cls
        self.tab_key = tab_key

    def __repr__(self) -> str:
        return f"PageSpec({self.key!r}, {self.cls.__name__}, {self.tab_key!r})"


# ─────────────────────────────────────────────────────────────────────────────
# Game plugin interface
# ─────────────────────────────────────────────────────────────────────────────

class GamePlugin(ABC):
    """Everything a game contributes to the tool.

    Subclass this, set the class attributes, and optionally override
    ``build_cli()`` to register CLI subcommands.

    Convention: each game lives in ``mgs2_audio.games.<id>/`` and its
    ``__init__.py`` exports a ``Plugin`` class that is an instance of
    this ABC (or a concrete subclass).
    """

    # ── Identity ────────────────────────────────────────────────────────
    id: str = ""                    # "mgs2", "zoe", "mgs3"
    name: str = ""                  # "Metal Gear Solid 2"

    # ── UI ──────────────────────────────────────────────────────────────
    # List of PageSpec for the tab bar.
    pages: List[PageSpec] = []

    # Per-mode stylesheets.  A game can offer multiple "modes" (e.g.
    # Master Collection vs Substance) — each mode has its own CSS and
    # a set of pages.  The first mode is the default.
    # Structure: {"mode_id": {"pages": [...], "subtitle_key": ..., "style": ...}}
    modes: Dict[str, Dict] = {}

    # ── CLI ─────────────────────────────────────────────────────────────
    # Callable(argparse_subparsers) -> None  — register subcommands.
    cli_register: Optional[Callable] = None

    # ── i18n ────────────────────────────────────────────────────────────
    # Per-game translation keys (merged into the global i18n dict).
    i18n: Dict[str, Dict[str, str]] = {}  # {"fr": {...}, "en": {...}}

    # ── Registration ────────────────────────────────────────────────────
    def register(self) -> None:
        """Called once at import time to add this plugin to the global registry."""
        from .registry import REGISTRY
        REGISTRY.register(self)
