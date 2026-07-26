#!/usr/bin/env python3
"""
voiceswap.py — swap Japanese voices into a US install (Phase 1).

The JP `.sdt` files are the game's native takes: JP audio already in perfect sync
with their own lip-sync and length, no growing/terminator tricks needed. For the
voice folders below, the `.sdt` carry **no embedded subtitle text** (that lives in
separate files, or the `.xxs` movie subs), so copying a JP file over its US
namesake gives Japanese voices while the English subtitles are left untouched.

Only the text-less voice folders are swapped. Codec calls (`LCGB` containers)
embed their multilingual subtitle text and are deliberately skipped here — they
need the audio-only merge of Phase 2, not a wholesale copy.

Requires both the US and JP *Better Audio* mods installed (so both sides are the
PS-ADPCM `.sdt` this handles). No backups are written: the originals are trivially
restored by re-verifying the game files or re-applying the mod.
"""
import os
from dataclasses import dataclass
from typing import Callable, List, Optional, Tuple

# Voice folders whose .sdt hold audio + lip-sync only (no embedded subtitle text).
SAFE_VOICE_FOLDERS = ("vox", "demo", "demo2")

# Codec containers embed subtitle text — never wholesale-swap these here.
_LCGB_MAGIC = b"LCGB"


@dataclass
class SwapPair:
    rel: str          # path relative to the language folder, e.g. "vc000201.sdt"
    jp: str           # absolute JP source path
    us: str           # absolute US destination path


def _real(path: str) -> str:
    """Resolve a symlink (the Better Audio mod installs .sdt as symlinks)."""
    return os.path.realpath(path)


def _embeds_text(path: str) -> bool:
    """True if the file is a codec (LCGB) container that carries subtitle text."""
    try:
        with open(_real(path), "rb") as f:
            return f.read(4) == _LCGB_MAGIC
    except OSError:
        return False


def find_pairs(game_root: str,
               folders: Tuple[str, ...] = SAFE_VOICE_FOLDERS) -> List[SwapPair]:
    """Every JP voice file that has a US namesake, across the safe folders.

    Matched by path relative to the language folder, so `jp/vox/vc000201.sdt`
    pairs with `us/vox/vc000201.sdt` and nested demo files line up too. Codec
    (LCGB, text-bearing) files are skipped.
    """
    pairs: List[SwapPair] = []
    for folder in folders:
        jp_root = os.path.join(game_root, "jp", folder)
        us_root = os.path.join(game_root, "us", folder)
        if not (os.path.isdir(jp_root) and os.path.isdir(us_root)):
            continue
        for dirpath, _dirs, files in os.walk(jp_root):
            for name in files:
                if not name.lower().endswith(".sdt"):
                    continue
                jp = os.path.join(dirpath, name)
                rel = os.path.relpath(jp, jp_root)
                us = os.path.join(us_root, rel)
                if not os.path.isfile(us):
                    continue
                if _embeds_text(jp) or _embeds_text(us):
                    continue          # codec call — leave for Phase 2
                pairs.append(SwapPair(os.path.join(folder, rel), jp, us))
    return pairs


def swap_pair(pair: SwapPair) -> int:
    """Write the JP file's bytes to the US path. Returns bytes written.

    If the US path is a symlink (Better Audio mod), it is replaced by a real file
    so the mod's own file is left intact and the swap is easy to undo.
    """
    with open(_real(pair.jp), "rb") as f:
        data = f.read()
    if os.path.islink(pair.us):
        os.remove(pair.us)
    with open(pair.us, "wb") as f:
        f.write(data)
    return len(data)


def swap_all(game_root: str,
             folders: Tuple[str, ...] = SAFE_VOICE_FOLDERS,
             progress: Optional[Callable[[int, int, str], None]] = None) -> dict:
    """Swap every safe JP voice file into the US install. No backups.

    `progress(done, total, label)` is called as it goes, if given.
    Returns {"swapped": n, "bytes": total, "skipped": n}.
    """
    pairs = find_pairs(game_root, folders)
    total = len(pairs)
    written = 0
    for i, pair in enumerate(pairs):
        if progress:
            progress(i, total, pair.rel)
        written += swap_pair(pair)
    if progress:
        progress(total, total, "")
    return {"swapped": total, "bytes": written}
