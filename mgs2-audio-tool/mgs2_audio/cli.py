#!/usr/bin/env python3
"""
cli.py — Drive the engine from a terminal, with no Qt and no GUI.

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
from .formats import sdt, sdx


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
    print(f"\n→ WAV written: {args.out_wav}  ({n:,} frames, {ch})")
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
    print(f"→ SDT written: {args.out_sdt}  ({len(new_raw):,} bytes, same size as original)")
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
        print(f"→ WAV written: {args.out}  ({n:,} frames, {sdx.SDX_SAMPLE_RATE} Hz mono)")
        return 0

    # no index: export every sample into a folder
    os.makedirs(args.out, exist_ok=True)
    base = os.path.splitext(os.path.basename(args.sdx))[0]
    for s in bank.samples:
        path = os.path.join(args.out, f"{base}_{s.index:03d}.wav")
        sdx.sample_to_wav(bank, s, path)
    print(f"→ {len(bank.samples)} WAV files written to {args.out}")
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
    print(f"→ SDX written: {args.out}  ({len(new_raw):,} bytes, same size as original)")
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
    print(f"scanning {len(paths)} banks…")

    def progress(n, total, path):
        if n % 20 == 0 or n == total:
            print(f"  {n}/{total}", end="\r", flush=True)

    groups = sdx.scan_banks(paths, progress)
    print(" " * 30, end="\r")

    shown = [g for g in groups if g.count >= args.min_count]
    total_refs = sum(g.count for g in groups)
    print(f"\n{len(paths)} banks · {total_refs:,} sounds · {len(groups):,} distinct")
    print(f"showing {len(shown)} sounds present in at least {args.min_count} bank(s)\n")

    print(f"{'key':>16}  {'banks':>5}  {'dur':>7}  {'size':>9}  example")
    for g in shown[:args.limit]:
        example = os.path.basename(os.path.dirname(g.refs[0].bank_path))
        print(f"{g.key:>16}  {g.count:>5}  {g.duration_seconds:6.2f}s  "
              f"{g.size:>9,}  {example}#{g.refs[0].index}")
    if len(shown) > args.limit:
        print(f"… and {len(shown) - args.limit} more (use --limit)")
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
    print(f"→ WAV written: {args.out}  ({group.duration_seconds:.2f}s, "
          f"present in {group.count} bank(s))")
    return 0


def _sdx_replace_all(args) -> int:
    folder = _resolve_folder(args.folder)
    if folder is None:
        return 1
    paths = sdx.find_banks(folder)
    print(f"scanning {len(paths)} banks…")
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

    changed = sdx.replace_group(group, pcm, backup=not args.no_backup)
    print(f"→ {changed} bank(s) updated"
          f"{'' if args.no_backup else ', originals kept as .bak'}")
    return 0

# ─────────────────────────────────────────────────────────────────────────────
# Argument parsing
# ─────────────────────────────────────────────────────────────────────────────

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

    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(sys.argv[1:] if argv is None else argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 1
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
