#!/usr/bin/env python3
"""
cli.py — Drive the engine from a terminal, with no Qt and no GUI.

Game plugins register their CLI subcommands via the core REGISTRY.

    python -m mgs2_audio.cli sdt info    vc000101.sdt
    python -m mgs2_audio.cli sdt export  vc000101.sdt out.wav
    python -m mgs2_audio.cli sdt replace vc000101.sdt dub.wav out.sdt

    python -m mgs2_audio.cli sdx list        pk000000.sdx
    python -m mgs2_audio.cli sdx scan        "C:/.../MGS2"
    python -m mgs2_audio.cli sdx export-key  "C:/.../MGS2" <key> out.wav
    python -m mgs2_audio.cli sdx replace-all "C:/.../MGS2" <key> sound.wav

`scan` accepts the game folder and finds `us/stage` on its own.
"""

import argparse
import os
import sys
from typing import Optional

from .codec.wav import save_wav
from .formats import sdt, sdx, bgm
from .formats.detect import detect_path, open_file, Format

# ── Game plugin discovery ────────────────────────────────────────────────────
from . import games  # noqa: F401  (side-effect: registers plugins)
from .core import REGISTRY


# ─────────────────────────────────────────────────────────────────────────────
# SDT — dialogue, music
# ─────────────────────────────────────────────────────────────────────────────

def _sdt_info(args) -> int:
    sdt_file = sdt.parse_sdt(args.sdt)
    print(sdt.describe(sdt_file))
    return 0


def _sdt_export(args) -> int:
    sdt_file = sdt.parse_sdt(args.sdt)
    print(sdt.describe(sdt_file))
    n = sdt.sdt_to_wav(sdt_file, args.out_wav)
    ch = "stereo" if sdt_file.channels == 2 else "mono"
    print(f"\n-> WAV written: {args.out_wav}  ({n:,} frames, {ch})")
    return 0


def _sdt_replace(args) -> int:
    sdt_file = sdt.parse_sdt(args.sdt)
    print(sdt.describe(sdt_file))
    samples, src_rate = sdt.load_wav_mono(args.dub_wav, sdt_file.sample_rate)
    new_raw = sdt.replace_audio(sdt_file, samples)
    sdt.save_sdt(new_raw, args.out_sdt)
    ch = "stereo (dub duplicated on both channels)" if sdt_file.channels == 2 else "mono"
    print(f"\nDub source : {args.dub_wav}  ({src_rate} Hz)")
    print(f"Re-encoded : PS-ADPCM, {ch}")
    print(f"-> SDT written: {args.out_sdt}  ({len(new_raw):,} bytes, same size as original)")
    return 0

# ─────────────────────────────────────────────────────────────────────────────
# SDX — stage sound banks
# ─────────────────────────────────────────────────────────────────────────────

def _sdx_info(args) -> int:
    print(sdx.describe(sdx.parse_sdx(args.sdx)))
    return 0


def _sdx_list(args) -> int:
    bank = sdx.parse_sdx(args.sdx)
    print(sdx.describe(bank))
    print()
    print(sdx.list_samples(bank))
    return 0


def _sdx_export(args) -> int:
    bank = sdx.parse_sdx(args.sdx)
    if args.index is not None:
        if not 0 <= args.index < len(bank.samples):
            print(f"error: sample index out of range (0..{len(bank.samples)-1})")
            return 1
        n = sdx.sample_to_wav(bank, bank.samples[args.index], args.out)
        print(f"-> WAV written: {args.out}  ({n:,} frames, {sdx.SDX_SAMPLE_RATE} Hz mono)")
        return 0

    # no index: export every sample into a folder
    os.makedirs(args.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.sdx))[0]
    for s in bank.samples:
        path = os.path.join(args.out, f"{base}_{s.index:03d}.wav")
        sdx.sample_to_wav(bank, s, path)
    print(f"-> {len(bank.samples)} WAV files written to {args.out}")
    return 0


def _sdx_replace(args) -> int:
    bank = sdx.parse_sdx(args.sdx)
    if not 0 <= args.index < len(bank.samples):
        print(f"error: sample index out of range (0..{len(bank.samples)-1})")
        return 1
    sample = bank.samples[args.index]
    pcm = sdx.load_wav_mono(args.wav)

    original = sample.duration_seconds
    incoming = len(pcm) / sdx.SDX_SAMPLE_RATE
    fit = "same length" if abs(incoming - original) < 0.01 else (
        "will be trimmed" if incoming > original else "will be padded with silence")

    new_raw = sdx.replace_sample(bank, sample, pcm)
    sdx.save_sdx(new_raw, args.out)
    print(sdx.describe(bank))
    print(f"\nSample #{args.index}: {original:.2f}s, {sample.size:,} bytes")
    print(f"New audio  : {incoming:.2f}s ({fit})")
    print(f"-> SDX written: {args.out}  ({len(new_raw):,} bytes, same size as original)")
    return 0


def _resolve_folder(folder: str) -> Optional[str]:
    """Accept a game root, a language folder, or the stage folder itself."""
    stage = sdx.find_stage_folder(folder)
    if stage is None:
        print(f"no .sdx found under {folder}")
    elif os.path.normpath(stage) != os.path.normpath(folder):
        print(f"stage folder: {stage}")
    return stage


def _sdx_scan(args) -> int:
    folder = _resolve_folder(args.folder)
    if folder is None:
        return 1
    paths = sdx.find_banks(folder)
    print(f"scanning {len(paths)} banks...")

    def progress(n, total, path):
        if n % 20 == 0 or n == total:
            print(f"  {n}/{total}", end="\r", flush=True)

    groups = sdx.scan_banks(paths, progress)
    print(" " * 30, end="\r")

    shown = [g for g in groups if g.count >= args.min_count]
    total_refs = sum(g.count for g in groups)
    print(f"\n{len(paths)} banks - {total_refs:,} sounds - {len(groups):,} distinct")
    print(f"showing {len(shown)} sounds present in at least {args.min_count} bank(s)\n")

    print(f"{'key':>16}  {'banks':>5}  {'dur':>7}  {'size':>9}  example")
    for g in shown[:args.limit]:
        example = os.path.basename(os.path.dirname(g.refs[0].bank_path))
        print(f"{g.key:>16}  {g.count:>5}  {g.duration_seconds:6.2f}s  "
              f"{g.size:>9,}  {example}#{g.refs[0].index}")
    if len(shown) > args.limit:
        print(f"... and {len(shown) - args.limit} more (use --limit)")
    return 0


def _sdx_export_group(args) -> int:
    folder = _resolve_folder(args.folder)
    if folder is None:
        return 1
    groups = sdx.scan_banks(sdx.find_banks(folder))
    group = next((g for g in groups if g.key == args.key), None)
    if group is None:
        print(f"error: no sound with key {args.key}")
        return 1
    pcm = sdx.read_group_sample(group)
    save_wav(pcm, args.out, sdx.SDX_SAMPLE_RATE, channels=1)
    print(f"-> WAV written: {args.out}  ({group.duration_seconds:.2f}s, "
          f"present in {group.count} bank(s))")
    return 0


def _sdx_replace_all(args) -> int:
    folder = _resolve_folder(args.folder)
    if folder is None:
        return 1
    paths = sdx.find_banks(folder)
    print(f"scanning {len(paths)} banks...")
    groups = sdx.scan_banks(paths)

    group = next((g for g in groups if g.key == args.key), None)
    if group is None:
        print(f"error: no sound with key {args.key} (run 'scan' first)")
        return 1

    pcm = sdx.load_wav_mono(args.wav)
    incoming = len(pcm) / sdx.SDX_SAMPLE_RATE
    fit = "trimmed" if incoming > group.duration_seconds else "padded with silence"
    print(f"\nSound {group.key}: {group.duration_seconds:.2f}s, "
          f"{group.size:,} bytes, in {group.count} bank(s)")
    print(f"New audio  : {incoming:.2f}s ({fit})")

    if not args.yes:
        answer = input(f"Rewrite {len(group.banks)} bank(s) in place? [y/N] ")
        if answer.strip().lower() not in ("y", "yes"):
            print("aborted")
            return 1

    try:
        changed = sdx.replace_group(group, pcm, backup=not args.no_backup)
    except sdx.ReplaceGroupError as e:
        print(f"-> {len(e.changed)} bank(s) updated, {len(e.failed)} FAILED"
              f"{'' if args.no_backup else ', originals kept as .bak'}")
        for path, exc in e.failed:
            print(f"   failed: {path} - {exc}")
        return 1
    print(f"-> {changed} bank(s) updated"
          f"{'' if args.no_backup else ', originals kept as .bak'}")
    return 0

# ─────────────────────────────────────────────────────────────────────────────
# BGM — background music archive (bgm.dat)
# ─────────────────────────────────────────────────────────────────────────────

def _bgm_info(args) -> int:
    archive = bgm.parse_bgm(args.bgm)
    print(bgm.describe(archive))
    return 0


def _bgm_export(args) -> int:
    archive = bgm.parse_bgm(args.bgm)
    if args.index is not None:
        if not 0 <= args.index < archive.entry_count:
            print(f"error: entry index out of range (0..{archive.entry_count - 1})")
            return 1
        n = bgm.bgm_to_wav(archive, args.index, args.out)
        e = archive.entries[args.index]
        ch = f"{e.channels}ch"
        print(f"\n-> WAV written: {args.out}  ({n:,} frames, {e.sample_rate} Hz {ch})")
        return 0

    # no index: export every entry into a folder
    os.makedirs(args.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.bgm))[0]
    for e in archive.entries:
        path = os.path.join(args.out, f"{base}_{e.index:03d}.wav")
        bgm.bgm_to_wav(archive, e.index, path)
    print(f"-> {archive.entry_count} WAV files written to {args.out}")
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# open — auto-detect format and export
# ─────────────────────────────────────────────────────────────────────────────

def _open_info(args) -> int:
    fmt = detect_path(args.file)
    if fmt is None:
        print(f"error: unrecognised format ({args.file})")
        return 1
    print(f"detected: {fmt.name}")
    from .formats.container import RavenContainer
    rc = RavenContainer.from_path(args.file)
    print(rc.describe())
    return 0


def _open_export(args) -> int:
    fmt = detect_path(args.file)
    if fmt is None:
        print(f"error: unrecognised format ({args.file})")
        return 1

    if fmt is Format.BGM:
        archive = bgm.parse_bgm(args.file)
        if args.index is not None:
            if not 0 <= args.index < archive.entry_count:
                print(f"error: entry index out of range (0..{archive.entry_count - 1})")
                return 1
            n = bgm.bgm_to_wav(archive, args.index, args.out)
            e = archive.entries[args.index]
            print(f"-> WAV written: {args.out}  ({n:,} frames, "
                  f"{e.sample_rate} Hz {e.channels}ch)")
        else:
            os.makedirs(args.out, exist_ok=True)
            base = os.path.splitext(os.path.basename(args.file))[0]
            for e in archive.entries:
                path = os.path.join(args.out, f"{base}_{e.index:03d}.wav")
                bgm.bgm_to_wav(archive, e.index, path)
            print(f"-> {archive.entry_count} WAV files written to {args.out}")
    elif fmt is Format.SDT:
        sdt_file = sdt.parse_sdt(args.file)
        if args.index is not None:
            print("error: SDT export does not support --index (use 'sdt export')")
            return 1
        n = sdt.sdt_to_wav(sdt_file, args.out)
        ch = "stereo" if sdt_file.channels == 2 else "mono"
        print(f"-> WAV written: {args.out}  ({n:,} frames, {ch})")
    else:
        print(f"error: export not implemented for {fmt.name} yet")
        return 1
    return 0


# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────

# ─────────────────────────────────────────────────────────────────────────────
# SDX — the music sequencer
# ─────────────────────────────────────────────────────────────────────────────

def _sdx_cues(args) -> int:
    from .formats import sequence
    try:
        bank = sequence.parse_sequence(args.sdx)
    except ValueError as e:
        print(f"error: {e}")
        return 1
    print(sequence.describe(bank))
    print()
    print(sequence.list_cues(bank, min_notes=args.min_notes))
    return 0


def _sdx_render(args) -> int:
    from .formats import sequence
    from . import render as renderer
    try:
        bank = sequence.parse_sequence(args.sdx)
    except ValueError as e:
        print(f"error: {e}")
        return 1

    if args.all:
        os.makedirs(args.out, exist_ok=True)
        base = os.path.splitext(os.path.basename(args.sdx))[0]
        written = 0
        for cue in bank.cues:
            notes = bank.note_count(cue)
            if notes < args.min_notes:
                continue
            left, right = renderer.render_cue(
                bank, cue, stereo=not args.mono, tune=not args.no_tune,
                seconds=args.seconds)
            if not left:
                continue
            name = os.path.join(args.out, f"{base}_cue{cue.index:03d}_{notes}notes.wav")
            renderer.save_cue(left, right, name, stereo=not args.mono)
            written += 1
        print(f"-> {written} cues rendered into {args.out}")
        return 0

    if args.cue is None:
        # no index given: the busiest cue is the most likely piece of music
        cue = max(bank.cues, key=bank.note_count)
    else:
        cue = next((c for c in bank.cues if c.index == args.cue), None)
        if cue is None:
            print(f"error: no cue {args.cue} (0..{len(bank.cues)-1})")
            return 1

    left, right = renderer.render_cue(
        bank, cue, stereo=not args.mono, tune=not args.no_tune, seconds=args.seconds)
    renderer.save_cue(left, right, args.out, stereo=not args.mono)
    print(f"cue {cue.index}: {cue.track_count} track(s), {bank.note_count(cue)} notes")
    print(f"-> WAV written: {args.out}  ({len(left)/renderer.OUTPUT_RATE:.1f}s)")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="mgs2-audio",
        description="Inspect, export and replace the audio of Metal Gear Solid 2 "
                    "(Master Collection, PC).")
    fmt = p.add_subparsers(dest="format")

    # ── sdt ──────────────────────────────────────────────────────────────────
    p_sdt = fmt.add_parser("sdt", help="dialogue, music and some effects (.sdt)")
    sdt_sub = p_sdt.add_subparsers(dest="command")

    s = sdt_sub.add_parser("info", help="show metadata")
    s.add_argument("sdt")
    s.set_defaults(func=_sdt_info)

    s = sdt_sub.add_parser("export", help="decode to WAV")
    s.add_argument("sdt"); s.add_argument("out_wav")
    s.set_defaults(func=_sdt_export)

    s = sdt_sub.add_parser("replace", help="inject your audio into an .sdt")
    s.add_argument("sdt"); s.add_argument("dub_wav"); s.add_argument("out_sdt")
    s.set_defaults(func=_sdt_replace)

    # ── sdx ──────────────────────────────────────────────────────────────────
    p_sdx = fmt.add_parser("sdx", help="stage sound-effect banks (.sdx)")
    sdx_sub = p_sdx.add_subparsers(dest="command")

    s = sdx_sub.add_parser("info", help="show bank metadata")
    s.add_argument("sdx")
    s.set_defaults(func=_sdx_info)

    s = sdx_sub.add_parser("list", help="list every sample in a bank")
    s.add_argument("sdx")
    s.set_defaults(func=_sdx_list)

    s = sdx_sub.add_parser("export", help="export one sample, or all of them")
    s.add_argument("sdx"); s.add_argument("out")
    s.add_argument("-i", "--index", type=int, default=None,
                   help="sample index (omit to export every sample)")
    s.set_defaults(func=_sdx_export)

    s = sdx_sub.add_parser("replace", help="replace one sample in one bank")
    s.add_argument("sdx"); s.add_argument("index", type=int)
    s.add_argument("wav"); s.add_argument("out")
    s.set_defaults(func=_sdx_replace)

    s = sdx_sub.add_parser("scan", help="group identical sounds across every bank")
    s.add_argument("folder", help="the MGS2 game folder (or its stage folder)")
    s.add_argument("--min-count", type=int, default=2)
    s.add_argument("--limit", type=int, default=40)
    s.set_defaults(func=_sdx_scan)

    s = sdx_sub.add_parser("export-key", help="export a scanned sound by key")
    s.add_argument("folder"); s.add_argument("key"); s.add_argument("out")
    s.set_defaults(func=_sdx_export_group)

    s = sdx_sub.add_parser(
        "replace-all", help="replace a sound in EVERY bank holding it (in place)")
    s.add_argument("folder"); s.add_argument("key"); s.add_argument("wav")
    s.add_argument("-y", "--yes", action="store_true", help="skip confirmation")
    s.add_argument("--no-backup", action="store_true",
                   help="do not keep the originals as .bak")
    s.set_defaults(func=_sdx_replace_all)

    # ── seq (music sequencer from .sdx banks) ────────────────────────────────
    p_seq = fmt.add_parser("seq", help="music sequencer - cues and synthesis (.sdx)")
    seq_sub = p_seq.add_subparsers(dest="command")

    s = seq_sub.add_parser("cues", help="list the music cues of a bank")
    s.add_argument("sdx")
    s.add_argument("--min-notes", type=int, default=1,
                   help="hide cues with fewer notes than this")
    s.set_defaults(func=_sdx_cues)

    s = seq_sub.add_parser("render", help="play a cue and write it to WAV")
    s.add_argument("sdx")
    s.add_argument("out", help="output .wav, or a folder with --all")
    s.add_argument("-c", "--cue", type=int, default=None,
                   help="cue index (default: the one with the most notes)")
    s.add_argument("--all", action="store_true", help="render every cue into a folder")
    s.add_argument("--min-notes", type=int, default=4, help="with --all, skip quiet cues")
    s.add_argument("--mono", action="store_true", help="mono output, ignoring pan")
    s.add_argument("--no-tune", action="store_true",
                   help="ignore each instrument's base rate")
    s.add_argument("--seconds", type=int, default=40, help="maximum length")
    s.set_defaults(func=_sdx_render)

    # ── bgm ─────────────────────────────────────────────────────────────────
    p_bgm = fmt.add_parser("bgm", help="background music archive (bgm.dat)")
    bgm_sub = p_bgm.add_subparsers(dest="command")

    s = bgm_sub.add_parser("info", help="show archive metadata")
    s.add_argument("bgm")
    s.set_defaults(func=_bgm_info)

    s = bgm_sub.add_parser("export", help="decode one entry, or all of them")
    s.add_argument("bgm"); s.add_argument("out")
    s.add_argument("-i", "--index", type=int, default=None,
                   help="entry index (omit to export every entry)")
    s.set_defaults(func=_bgm_export)

    # ── open (auto-detect) ──────────────────────────────────────────────────
    p_open = fmt.add_parser("open", help="auto-detect format and act on it")
    open_sub = p_open.add_subparsers(dest="command")

    s = open_sub.add_parser("info", help="show metadata of any audio file")
    s.add_argument("file")
    s.set_defaults(func=_open_info)

    s = open_sub.add_parser("export", help="export audio to WAV (auto-detect)")
    s.add_argument("file"); s.add_argument("out")
    s.add_argument("-i", "--index", type=int, default=None,
                   help="entry index (for BGM archives)")
    s.set_defaults(func=_open_export)

    # ── game-specific subcommands ───────────────────────────────────────────
    for plugin in REGISTRY:
        if plugin.cli_register:
            plugin.cli_register(fmt)

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    try:
        return args.func(args)
    except Exception as e:
        print(f"error: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
