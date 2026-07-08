#!/usr/bin/env python3
"""
library.py — Local "voice library" database for the MGS2 SDT Tool.

Lets the user point at a folder full of .sdt voice files and keep a small,
manually-curated database about each one:
  - done      : whether the user has already dubbed this line (manual)
  - tag       : a free-text label the user types (e.g. "Soldier", "Codec")
  - speaker   : who is talking (useful for multi-voice codec calls)
  - notes     : a free transcript / reminder of what is said

Plus a cached, auto-detected part (never manual):
  - channels, duration, size, blocks, sample_rate

The database is a single JSON file stored in a folder the user chooses (kept
separate from the voice files themselves). Everything here is pure Python and
has no GUI dependency, so it can be unit-tested on its own.
"""

import os
import json
from typing import Dict, List, Optional

import sdt_core as core

LIBRARY_FILENAME = "mgs2_sdt_library.json"
LIBRARY_VERSION = 1

# Manual fields curated by the user + auto-detected cached fields.
ENTRY_DEFAULTS = {
    # manual
    "done": False,
    "tag": "",
    "speaker": "",
    "notes": "",
    # auto-detected cache (filled on scan, may be None until then)
    "channels": None,
    "duration": None,
    "size": None,
    "blocks": None,
    "sample_rate": None,
}

MANUAL_FIELDS = ("done", "tag", "speaker", "notes")
CACHE_FIELDS = ("channels", "duration", "size", "blocks", "sample_rate")


# ─────────────────────────────────────────────────────────────────────────────
# Database file location
# ─────────────────────────────────────────────────────────────────────────────

def library_path(db_folder: str) -> str:
    """Full path of the JSON database inside the chosen database folder."""
    return os.path.join(db_folder, LIBRARY_FILENAME)


def load_library(db_folder: str) -> dict:
    """Load the database from db_folder, or return a fresh empty one."""
    path = library_path(db_folder)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "entries" not in data:
            raise ValueError("malformed library")
        data.setdefault("version", LIBRARY_VERSION)
        data.setdefault("entries", {})
        return data
    except Exception:
        return {"version": LIBRARY_VERSION, "entries": {}}


def save_library(db_folder: str, data: dict) -> bool:
    """Write the database to db_folder. Returns True on success."""
    path = library_path(db_folder)
    try:
        os.makedirs(db_folder, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        return True
    except Exception:
        return False


# ─────────────────────────────────────────────────────────────────────────────
# Entry access
# ─────────────────────────────────────────────────────────────────────────────

def get_entry(data: dict, filename: str) -> dict:
    """Return a full entry for filename (defaults filled in), without mutating."""
    entry = dict(ENTRY_DEFAULTS)
    stored = data.get("entries", {}).get(filename)
    if isinstance(stored, dict):
        entry.update({k: stored.get(k, entry[k]) for k in ENTRY_DEFAULTS})
    return entry


def set_entry(data: dict, filename: str, **fields) -> dict:
    """Update the stored entry for filename with the given fields.

    Only known fields are accepted; unknown keys are ignored. The (possibly
    new) stored entry dict is returned.
    """
    entries = data.setdefault("entries", {})
    stored = entries.get(filename)
    if not isinstance(stored, dict):
        stored = dict(ENTRY_DEFAULTS)
        entries[filename] = stored
    for k, v in fields.items():
        if k in ENTRY_DEFAULTS:
            stored[k] = v
    return stored


def collect_tags(data: dict) -> List[str]:
    """Return the sorted list of distinct non-empty tags already used.

    Handy to offer the user quick reuse of their own labels.
    """
    tags = set()
    for stored in data.get("entries", {}).values():
        if isinstance(stored, dict):
            t = (stored.get("tag") or "").strip()
            if t:
                tags.add(t)
    return sorted(tags, key=str.lower)


def counts(data: dict, filenames: List[str]) -> Dict[str, int]:
    """Return {'total','done','todo'} for the given filename list."""
    done = 0
    for name in filenames:
        if get_entry(data, name)["done"]:
            done += 1
    return {"total": len(filenames), "done": done, "todo": len(filenames) - done}


# ─────────────────────────────────────────────────────────────────────────────
# Folder listing + metadata scan
# ─────────────────────────────────────────────────────────────────────────────

def list_sdt_files(voice_folder: str) -> List[str]:
    """Return the sorted list of .sdt filenames in voice_folder (non-recursive)."""
    try:
        names = [n for n in os.listdir(voice_folder)
                 if n.lower().endswith(".sdt")
                 and os.path.isfile(os.path.join(voice_folder, n))]
    except Exception:
        return []
    return sorted(names, key=str.lower)


def quick_header(path: str) -> dict:
    """Cheaply read just the header for sample_rate + channels.

    Reads only the first bytes of the file (no block scan, no decode), so this
    is safe to call on thousands of files. Uses the same robust detection as the
    engine, so header-shifted variants (e.g. "PACB" music files) report the
    correct channel count. Returns {'sample_rate','channels'} with sensible
    defaults if the header is too short/unknown.
    """
    try:
        with open(path, "rb") as f:
            head = f.read(0x400)
        sample_rate, channels = core._detect_format(head)
        return {"sample_rate": sample_rate, "channels": channels}
    except Exception:
        return {"sample_rate": core.DEFAULT_SAMPLE_RATE, "channels": 1}


def scan_metadata(path: str) -> dict:
    """Full metadata for one file (channels, duration, size, blocks, rate).

    This parses the whole file (block scan) but does NOT decode audio, so it is
    reasonably fast per file. Meant to be cached in the database afterwards.
    """
    sdt = core.parse_sdt(path)
    return {
        "channels": sdt.channels,
        "duration": sdt.duration_seconds,
        "size": len(sdt.raw),
        "blocks": len(sdt.blocks),
        "sample_rate": sdt.sample_rate,
    }


def cache_metadata(data: dict, filename: str, path: str) -> dict:
    """Scan file metadata and store it in the entry cache. Returns the metadata."""
    md = scan_metadata(path)
    set_entry(data, filename, **md)
    return md
