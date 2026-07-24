#!/usr/bin/env python3
"""
sdx.py — The `.sdx` sound banks of Metal Gear Solid 2 (Master Collection, PC).

Every stage folder carries its own `pk*.sdx`: the sound effects of that stage —
footsteps, doors, weapons, ambience.

Layout
------
    0x0000 .. 0x0800   small header
    0x0800 .. <audio>  a 16-byte-record table (SE banks: SPU voice addresses;
                       music banks: the sequencer's instrument directory)
    <audio> .. <pad>   audio: PS-ADPCM samples laid end to end, 22050 Hz mono
    <pad>  .. <table>  frame-aligned padding: 0xFF (SE) or 0xFE (music banks)
    <table>            bank table: 16-byte records pointing at the samples
                       (addresses counted in 8-byte units)
    <tail>             sequence / sound-program data

Audio nominally begins at 0x1000, but that is only exact when the 0x800 table
holds 128 records; measured over 600 stage banks it ranges 0x9E0..0x1070. The
partition below re-syncs on the end-flag, so the nominal start stays safe.

A sample runs up to and including the first frame whose flag has the end bit set.

Two constraints shape every edit:

* the bank table stores byte addresses, so a replacement must keep the sample's
  size EXACTLY the same, or every following pointer breaks;
* the per-frame flag bytes carry the loop and end markers, so they must survive
  re-encoding.

`replace_sample` and `replace_group` honour both. See `docs/FORMATS.md`.

Common effects are duplicated across dozens of banks, so editing one stage often
has no audible result in game — `scan_banks` groups identical sounds so a single
edit can reach all of them.

Pure Python, no dependencies.
"""

import glob as _glob
import hashlib
import logging
import os
import tempfile
from dataclasses import dataclass, field
from typing import List, Optional

from ..codec import psadpcm as codec
from ..codec.wav import load_wav_mono as _load_wav, save_wav

log = logging.getLogger(__name__)
# ─────────────────────────────────────────────────────────────────────────────
# Format constants
# ─────────────────────────────────────────────────────────────────────────────

DATA_START = 0x1000        # audio always begins here
FRAME_SIZE = 16            # one PS-ADPCM frame
SAMPLES_PER_FRAME = 28     # 16 bytes -> 28 PCM samples
SDX_SAMPLE_RATE = 22050    # confirmed by ear on decoded effects
MIN_SAMPLE_BYTES = 256     # below this a "sample" is just a terminator frame

FLAG_END = 0x01
FLAG_LOOP = 0x02
FLAG_LOOP_START = 0x04

# The frame-aligned padding that closes the audio region. SE banks use 0xFF,
# music/sequencer banks use 0xFE — both occur across the game's stage banks.
PADDING_FF = b"\xff" * FRAME_SIZE
PADDING_FE = b"\xfe" * FRAME_SIZE


# ─────────────────────────────────────────────────────────────────────────────
# Representation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class SDXSample:
    """One PS-ADPCM sample inside the bank."""
    index: int
    offset: int            # byte offset in the file
    size: int              # byte length (always a multiple of 16)

    @property
    def frames(self) -> int:
        return self.size // FRAME_SIZE

    @property
    def duration_seconds(self) -> float:
        return self.frames * SAMPLES_PER_FRAME / SDX_SAMPLE_RATE


@dataclass
class SDXFile:
    """A parsed .sdx sound bank."""
    path: str
    raw: bytes
    data_start: int = DATA_START
    data_end: int = 0
    samples: List[SDXSample] = field(default_factory=list)

    @property
    def sample_rate(self) -> int:
        return SDX_SAMPLE_RATE

    @property
    def has_audio(self) -> bool:
        return bool(self.samples)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _find_audio_end(raw: bytes) -> int:
    """First padding frame after the audio, i.e. where the samples stop.

    Banks pad with **0xFF or 0xFE** — measured across 600 stage banks, the ~80
    music/sequencer banks all use 0xFE. Recognising only 0xFF made this scan run
    off the end of the audio on those banks and carve "samples" out of the cue
    table and the sequence that follow it.

    The scan is frame-aligned: a run of either byte can occur mid-frame as
    ordinary audio data, and only a whole padding frame marks the end.
    """
    limit = len(raw) - FRAME_SIZE + 1
    for off in range(DATA_START, limit, FRAME_SIZE):
        frame = raw[off:off + FRAME_SIZE]
        if frame == PADDING_FF or frame == PADDING_FE:
            return off
    return DATA_START + ((len(raw) - DATA_START) // FRAME_SIZE) * FRAME_SIZE


def parse_sdx(path: str) -> SDXFile:
    """Read a .sdx bank and locate every PS-ADPCM sample inside it."""
    with open(path, "rb") as f:
        raw = f.read()

    sdx = SDXFile(path=path, raw=raw)
    if len(raw) <= DATA_START + FRAME_SIZE:
        return sdx

    sdx.data_end = _find_audio_end(raw)

    # A sample ends on the first frame whose flag has the end bit set. Runs of
    # 16-byte "samples" are just terminator frames and are skipped.
    index = 0
    start = sdx.data_start
    for off in range(sdx.data_start, sdx.data_end - FRAME_SIZE + 1, FRAME_SIZE):
        if raw[off + 1] & FLAG_END:
            size = off + FRAME_SIZE - start
            if size >= MIN_SAMPLE_BYTES:
                sdx.samples.append(SDXSample(index=index, offset=start, size=size))
                index += 1
            start = off + FRAME_SIZE

    return sdx


def sample_bytes(sdx: SDXFile, sample: SDXSample) -> bytes:
    return sdx.raw[sample.offset:sample.offset + sample.size]


def sample_flags(sdx: SDXFile, sample: SDXSample) -> List[int]:
    """The per-frame flag byte of a sample (loop points and end marker)."""
    data = sample_bytes(sdx, sample)
    return [data[i * FRAME_SIZE + 1] for i in range(sample.frames)]


# ─────────────────────────────────────────────────────────────────────────────
# Decoding / export
# ─────────────────────────────────────────────────────────────────────────────

def decode_sample(sdx: SDXFile, sample: SDXSample) -> List[int]:
    """Decode one sample to 16-bit PCM (mono)."""
    return codec.decode_psadpcm(sample_bytes(sdx, sample))


def sample_to_wav(sdx: SDXFile, sample: SDXSample, out_path: str) -> int:
    """Export one sample as a mono WAV at the bank's sample rate."""
    pcm = decode_sample(sdx, sample)
    save_wav(pcm, out_path, SDX_SAMPLE_RATE, channels=1)
    return len(pcm)


# ─────────────────────────────────────────────────────────────────────────────
# Replacement
# ─────────────────────────────────────────────────────────────────────────────

def replace_sample(sdx: SDXFile, sample: SDXSample, new_pcm: List[int]) -> bytes:
    """Replace one sample's audio, keeping its exact byte size and flags.

    The new audio is re-encoded into exactly the same number of PS-ADPCM frames
    (padded with silence if too short, truncated if too long), then each frame's
    original flag byte is copied back. That keeps the loop markers, the end
    marker, and every pointer in the bank table valid.

    Returns the bytes of the new .sdx file.
    """
    frames = sample.frames
    max_samples = frames * SAMPLES_PER_FRAME

    pcm = list(new_pcm)
    if len(pcm) < max_samples:
        pcm += [0] * (max_samples - len(pcm))
    else:
        pcm = pcm[:max_samples]

    encoded = bytearray(codec.encode_psadpcm(pcm))
    # encode_psadpcm pads to a multiple of 28 samples; force the exact size
    if len(encoded) < sample.size:
        encoded += b"\x00" * (sample.size - len(encoded))
    else:
        del encoded[sample.size:]

    # Restore the original flag byte of every frame (loop / end markers)
    original_flags = sample_flags(sdx, sample)
    for i, flag in enumerate(original_flags):
        encoded[i * FRAME_SIZE + 1] = flag

    raw = bytearray(sdx.raw)
    raw[sample.offset:sample.offset + sample.size] = bytes(encoded)
    return bytes(raw)


def save_sdx(raw: bytes, path: str):
    with open(path, "wb") as f:
        f.write(raw)


def load_wav_mono(path: str) -> List[int]:
    """Load a WAV as mono 16-bit samples at the bank's rate (resampling if needed)."""
    pcm, _ = _load_wav(path, SDX_SAMPLE_RATE)
    return pcm


# ─────────────────────────────────────────────────────────────────────────────
# Cross-bank scanning: the same sound lives in many stage banks
# ─────────────────────────────────────────────────────────────────────────────
#
# Every stage folder carries its own pk*.sdx, and common sounds (rain, footsteps,
# gunshots…) are duplicated across dozens of them. Editing one bank is therefore
# not enough: the game may well play the copy stored in another stage's bank.
#
# Sounds are identified by hashing their audio payload with the per-frame flag
# bytes zeroed out, so the same sound still matches even when two banks give it
# different loop markers. Each occurrence keeps its own flags when rewritten.


def sample_key(raw: bytes, sample: SDXSample) -> str:
    """Stable identity of a sound: its audio payload, ignoring per-frame flags."""
    data = bytearray(raw[sample.offset:sample.offset + sample.size])
    for i in range(sample.frames):
        data[i * FRAME_SIZE + 1] = 0
    return hashlib.sha1(bytes(data)).hexdigest()[:16]


@dataclass
class SampleRef:
    """One occurrence of a sound inside a specific bank."""
    bank_path: str
    index: int
    offset: int
    size: int

    @property
    def duration_seconds(self) -> float:
        return (self.size // FRAME_SIZE) * SAMPLES_PER_FRAME / SDX_SAMPLE_RATE


@dataclass
class SoundGroup:
    """A distinct sound, and every bank it appears in."""
    key: str
    refs: List[SampleRef] = field(default_factory=list)

    @property
    def count(self) -> int:
        return len(self.refs)

    @property
    def size(self) -> int:
        return self.refs[0].size if self.refs else 0

    @property
    def duration_seconds(self) -> float:
        return self.refs[0].duration_seconds if self.refs else 0.0

    @property
    def banks(self) -> List[str]:
        return sorted({r.bank_path for r in self.refs})


def find_banks(root: str) -> List[str]:
    """Every .sdx below `root` (recursively), sorted."""
    pattern = os.path.join(root, "**", "*.sdx")
    return sorted(_glob.glob(pattern, recursive=True))


def find_stage_folder(game_root: str) -> Optional[str]:
    """Locate the folder holding the stage banks, given the game's root.

    Only the `stage` folder carries `.sdx` files, and it sits under a language
    directory (`us/stage`, and so on). Asking the user for the game folder and
    resolving the rest here is friendlier than making them navigate there.

    Accepts a game root, a language folder, or the stage folder itself. Returns
    None when no `.sdx` can be found anywhere below.
    """
    if not game_root or not os.path.isdir(game_root):
        return None

    def holds_banks_directly(path: str) -> bool:
        """True when this folder is the stage folder: its banks sit one level in."""
        return bool(_glob.glob(os.path.join(path, "*", "*.sdx"))
                    or _glob.glob(os.path.join(path, "*.sdx")))

    # The user may already have pointed straight at the stage folder (or at one
    # stage inside it) — in that case the banks are right there.
    if holds_banks_directly(game_root):
        return game_root

    # Usual layout: <game>/<lang>/stage. Prefer 'us', then any other language.
    candidates = [os.path.join(game_root, "stage")]
    for lang in ("us", "eu", "jp", "uk"):
        candidates.append(os.path.join(game_root, lang, "stage"))
    try:
        for entry in sorted(os.listdir(game_root)):
            candidates.append(os.path.join(game_root, entry, "stage"))
    except OSError:
        pass

    for path in candidates:
        if os.path.isdir(path) and find_banks(path):
            return path

    # Fallback: any 'stage' directory anywhere below the root.
    for path in sorted(_glob.glob(os.path.join(game_root, "**", "stage"),
                                  recursive=True)):
        if os.path.isdir(path) and find_banks(path):
            return path

    # No folder named 'stage'? Accept any subtree that holds banks.
    return game_root if find_banks(game_root) else None


def scan_banks(paths: List[str], progress=None) -> List[SoundGroup]:
    """Parse each bank, hash its sounds, and group identical ones together.

    Only metadata is kept in memory (never the raw banks), so scanning a whole
    `stage/` tree of a couple hundred files stays cheap.

    `progress` is an optional callback receiving (done, total, path). If it
    returns a truthy value, the scan stops early and returns what it has
    grouped so far.
    """
    groups = {}
    total = len(paths)
    for n, path in enumerate(paths, 1):
        if progress and progress(n, total, path):
            break
        try:
            bank = parse_sdx(path)
        except Exception as exc:
            log.warning("skipping corrupt bank %s: %s", path, exc)
            continue
        raw = bank.raw
        for s in bank.samples:
            key = sample_key(raw, s)
            group = groups.get(key)
            if group is None:
                group = groups[key] = SoundGroup(key=key)
            group.refs.append(SampleRef(bank_path=path, index=s.index,
                                        offset=s.offset, size=s.size))
        del bank        # release the raw bytes straight away

    ordered = sorted(groups.values(),
                     key=lambda g: (-g.count, -g.duration_seconds))
    return ordered


def read_group_sample(group: SoundGroup) -> List[int]:
    """Decode the first occurrence of a group to PCM (for previewing)."""
    ref = group.refs[0]
    with open(ref.bank_path, "rb") as f:
        f.seek(ref.offset)
        data = f.read(ref.size)
    return codec.decode_psadpcm(data)


def _encode_for_size(pcm: List[int], size: int) -> bytearray:
    """Encode PCM into exactly `size` bytes of PS-ADPCM (pad/trim as needed)."""
    frames = size // FRAME_SIZE
    wanted = frames * SAMPLES_PER_FRAME
    data = list(pcm)
    if len(data) < wanted:
        data += [0] * (wanted - len(data))
    else:
        data = data[:wanted]
    encoded = bytearray(codec.encode_psadpcm(data))
    if len(encoded) < size:
        encoded += b"\x00" * (size - len(encoded))
    else:
        del encoded[size:]
    return encoded


class ReplaceGroupError(Exception):
    """Raised when a batch `replace_group` run leaves one or more banks untouched.

    `changed` is the list of bank paths that WERE successfully rewritten;
    `failed` is a list of (path, error) for the ones that weren't. Banks that
    succeeded before the first failure are not rolled back — the caller can
    inspect both lists to know exactly what state the game folder is in.
    """

    def __init__(self, changed: List[str], failed: List[tuple]):
        self.changed = changed
        self.failed = failed
        detail = ", ".join(f"{os.path.basename(p)}: {e}" for p, e in failed)
        super().__init__(f"{len(changed)} bank(s) updated, {len(failed)} failed - {detail}")


def _atomic_write(path: str, data: bytes):
    """Write `data` to `path` without ever leaving a half-written file on disk."""
    dir_ = os.path.dirname(path) or "."
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as f:
            f.write(data)
        os.replace(tmp, path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def replace_group(group: SoundGroup, new_pcm: List[int],
                  backup: bool = True, progress=None) -> int:
    """Replace this sound in EVERY bank where it occurs, in place.

    All occurrences share the same byte size, so the audio is encoded once and
    reused. Each occurrence keeps its own per-frame flag bytes, so loop markers
    and end markers stay exactly as the game expects, and every pointer in every
    bank table remains valid.

    With `backup`, an untouched `<bank>.bak` is written next to each bank the
    first time it is modified — if a `.bak` already exists it is left alone
    (it holds whatever was there before this tool first touched the file, which
    is only truly pristine if that first touch also used `backup=True`).

    Writes are atomic (temp file + rename): a crash or full disk mid-write
    cannot leave a bank half-written. If any bank in the batch fails, every
    bank that succeeded is still written — the failures are reported together
    at the end via `ReplaceGroupError` rather than aborting the whole batch
    partway through with no record of what was and wasn't touched.

    Returns the number of banks changed on full success; raises
    `ReplaceGroupError` if any bank could not be updated.
    """
    if not group.refs:
        return 0

    encoded = _encode_for_size(new_pcm, group.size)

    by_bank = {}
    for ref in group.refs:
        by_bank.setdefault(ref.bank_path, []).append(ref)

    changed = []
    failed = []
    total = len(by_bank)
    for n, (path, refs) in enumerate(sorted(by_bank.items()), 1):
        if progress:
            progress(n, total, path)
        try:
            with open(path, "rb") as f:
                raw = bytearray(f.read())
            original = bytes(raw)

            for ref in refs:
                block = bytearray(encoded)
                # keep this occurrence's own flag bytes
                for i in range(ref.size // FRAME_SIZE):
                    block[i * FRAME_SIZE + 1] = raw[ref.offset + i * FRAME_SIZE + 1]
                raw[ref.offset:ref.offset + ref.size] = block

            if backup:
                bak = path + ".bak"
                if not os.path.exists(bak):
                    _atomic_write(bak, original)

            _atomic_write(path, bytes(raw))
            changed.append(path)
        except Exception as exc:
            log.warning("failed to update bank %s: %s", path, exc)
            failed.append((path, exc))

    if failed:
        raise ReplaceGroupError(changed, failed)
    return len(changed)


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable summary
# ─────────────────────────────────────────────────────────────────────────────

def describe(sdx: SDXFile) -> str:
    total = sum(s.size for s in sdx.samples)
    return (
        f"File        : {os.path.basename(sdx.path)}\n"
        f"Size        : {len(sdx.raw):,} bytes\n"
        f"Sample rate : {sdx.sample_rate} Hz (mono)\n"
        f"Audio region: {sdx.data_start:#x} .. {sdx.data_end:#x}\n"
        f"Samples     : {len(sdx.samples)} ({total:,} bytes of audio)"
    )


def list_samples(sdx: SDXFile) -> str:
    rows = [f"{'idx':>4}  {'offset':>10}  {'size':>9}  {'frames':>7}  duration"]
    for s in sdx.samples:
        rows.append(f"{s.index:>4}  {s.offset:#10x}  {s.size:>9,}  "
                    f"{s.frames:>7}  {s.duration_seconds:6.2f}s")
    return "\n".join(rows)
