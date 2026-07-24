#!/usr/bin/env python3
"""
db.py — Local tagging databases for MGS2 Audio Tool.

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

import json
import logging
import os
import tempfile
from typing import Dict, List

log = logging.getLogger(__name__)

from ..formats import sdt as _sdt

LIBRARY_FILENAME = "mgs2_sdt_library.json"
SDX_LIBRARY_FILENAME = "mgs2_sdx_library.json"
# Substance's .sdx layout differs from Master Collection's, and the two games'
# sound effects are unrelated — give Substance its own file rather than
# sharing (and co-mingling tags in) the Master Collection one.
SUBSTANCE_SDX_LIBRARY_FILENAME = "mgs2_substance_sdx_library.json"
# One tab per game, so no MC/Substance naming collision needed here (unlike SDX,
# which exists in both).
VOX_LIBRARY_FILENAME = "mgs2_vox_library.json"
BGM_LIBRARY_FILENAME = "mgs2_bgm_library.json"
DEMOS_LIBRARY_FILENAME = "mgs2_demos_library.json"
SEQ_LIBRARY_FILENAME = "mgs2_seq_library.json"
MCBGM_LIBRARY_FILENAME = "mgs2_mc_bgm_library.json"
GSA_LIBRARY_FILENAME = "mgs2_gsa_library.json"
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

# SDX sounds are identified by a content hash, not a filename: the same effect
# lives in dozens of stage banks. Tagging one tags every copy of it.
SDX_ENTRY_DEFAULTS = {
    # manual
    "done": False,
    "tag": "",
    "notes": "",
    # auto-detected cache
    "duration": None,
    "size": None,
    "banks": None,
}

# Shared by VOX / BGM / Dém / Séquenceur: no per-entry cache needed (their
# metadata is already cheap to read from the archive already held in memory,
# unlike SDT's per-file-on-disk scan), and no "speaker" field outside SDT.
TAG_ENTRY_DEFAULTS = {
    "done": False,
    "tag": "",
    "notes": "",
}

MANUAL_FIELDS = ("done", "tag", "speaker", "notes")
CACHE_FIELDS = ("channels", "duration", "size", "blocks", "sample_rate")


# ─────────────────────────────────────────────────────────────────────────────
# Database file location
# ─────────────────────────────────────────────────────────────────────────────

def library_path(db_folder: str, filename: str = LIBRARY_FILENAME) -> str:
    """Full path of a JSON database inside the chosen database folder."""
    return os.path.join(db_folder, filename)


def load_library(db_folder: str, filename: str = LIBRARY_FILENAME) -> dict:
    """Load a database from db_folder, or return a fresh empty one."""
    path = library_path(db_folder, filename)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        if not isinstance(data, dict) or "entries" not in data:
            raise ValueError("malformed library")
        data.setdefault("version", LIBRARY_VERSION)
        data.setdefault("entries", {})
        return data
    except FileNotFoundError:
        # Normal state for any tab the user hasn't tagged yet — not a warning.
        return {"version": LIBRARY_VERSION, "entries": {}}
    except (json.JSONDecodeError, ValueError) as e:
        log.warning("corrupt library %s, starting fresh: %s", path, e)
        return {"version": LIBRARY_VERSION, "entries": {}}
    except Exception as e:
        log.warning("could not load library %s: %s", path, e)
        return {"version": LIBRARY_VERSION, "entries": {}}


def save_library(db_folder: str, data: dict,
                 filename: str = LIBRARY_FILENAME) -> bool:
    """Write a database to db_folder. Returns True on success."""
    path = library_path(db_folder, filename)
    try:
        os.makedirs(db_folder, exist_ok=True)
        fd, tmp = tempfile.mkstemp(dir=db_folder, suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(tmp, path)
        except Exception:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise
        return True
    except Exception as e:
        log.warning("could not save library to %s: %s", path, e)
        return False


# The SDX database lives beside the SDT one but stays a separate file: its
# entries are keyed by sound hash rather than filename, so it can be shared on
# its own (the tags of the game's sound effects are the same for everyone).

def load_sdx_library(db_folder: str, filename: str = SDX_LIBRARY_FILENAME) -> dict:
    return load_library(db_folder, filename)


def save_sdx_library(db_folder: str, data: dict,
                     filename: str = SDX_LIBRARY_FILENAME) -> bool:
    return save_library(db_folder, data, filename)


# ─────────────────────────────────────────────────────────────────────────────
# Entry access
# ─────────────────────────────────────────────────────────────────────────────

def get_entry(data: dict, filename: str, defaults: dict = None) -> dict:
    """Return a full entry (defaults filled in), without mutating the database."""
    defaults = defaults or ENTRY_DEFAULTS
    entry = dict(defaults)
    stored = data.get("entries", {}).get(filename)
    if isinstance(stored, dict):
        entry.update({k: stored.get(k, entry[k]) for k in defaults})
    return entry


def set_entry(data: dict, filename: str, defaults: dict = None, **fields) -> dict:
    """Update the stored entry for filename with the given fields.

    Only known fields are accepted; unknown keys are ignored. The (possibly
    new) stored entry dict is returned.
    """
    defaults = defaults or ENTRY_DEFAULTS
    entries = data.setdefault("entries", {})
    stored = entries.get(filename)
    if not isinstance(stored, dict):
        stored = dict(defaults)
        entries[filename] = stored
    for k, v in fields.items():
        if k in defaults:
            stored[k] = v
    return stored


def get_sdx_entry(data: dict, key: str) -> dict:
    return get_entry(data, key, SDX_ENTRY_DEFAULTS)


def set_sdx_entry(data: dict, key: str, **fields) -> dict:
    return set_entry(data, key, SDX_ENTRY_DEFAULTS, **fields)


def collect_tags(data: dict) -> List[str]:
    """Distinct tags already used, most frequently used first.

    Ordering by frequency puts the labels the user actually relies on at the top
    of the completer, instead of burying them alphabetically.
    """
    counts = {}
    for stored in data.get("entries", {}).values():
        if isinstance(stored, dict):
            t = (stored.get("tag") or "").strip()
            if t:
                counts[t] = counts.get(t, 0) + 1
    return sorted(counts, key=lambda t: (-counts[t], t.lower()))


def tag_counts(data: dict) -> Dict[str, int]:
    """How many entries carry each tag (used for progress per tag)."""
    counts = {}
    for stored in data.get("entries", {}).values():
        if isinstance(stored, dict):
            t = (stored.get("tag") or "").strip()
            if t:
                counts[t] = counts.get(t, 0) + 1
    return counts


def counts(data: dict, filenames: List[str], defaults: dict = None) -> Dict[str, int]:
    """Return {'total','done','todo'} for the given key list."""
    done = 0
    for name in filenames:
        if get_entry(data, name, defaults)["done"]:
            done += 1
    return {"total": len(filenames), "done": done, "todo": len(filenames) - done}


# ─────────────────────────────────────────────────────────────────────────────
# Folder listing + metadata scan
# ─────────────────────────────────────────────────────────────────────────────

def list_sdt_files(voice_folder: str) -> List[str]:
    """Return the sorted list of .sdt filenames in voice_folder (non-recursive).

    Also lists ``.sdt.vortex_backup`` files: on an install modded through
    Vortex (e.g. the Better Audio Mod), those are the untouched **stock**
    originals — the Konami XWMA audio the tool can now decode.
    """
    try:
        names = [n for n in os.listdir(voice_folder)
                 if (n.lower().endswith(".sdt")
                     or n.lower().endswith(".sdt.vortex_backup"))
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
        sample_rate, channels = _sdt._detect_format(head)
        # channels may be None when the header does not expose it; the list then
        # shows mono until a full parse (on open/scan) resolves the real value.
        return {"sample_rate": sample_rate, "channels": channels or 1}
    except Exception:
        return {"sample_rate": _sdt.DEFAULT_SAMPLE_RATE, "channels": 1}


def scan_metadata(path: str) -> dict:
    """Full metadata for one file (channels, duration, size, blocks, rate).

    This parses the whole file (block scan) but does NOT decode audio, so it is
    reasonably fast per file. Meant to be cached in the database afterwards.
    """
    try:
        sdt = _sdt.parse_sdt(path)
    except Exception as e:
        log.warning("could not scan metadata for %s: %s", path, e)
        return {}
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
    if md:
        set_entry(data, filename, **md)
    return md
