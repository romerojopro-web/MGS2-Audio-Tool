#!/usr/bin/env python3
"""
Analyze opcode usage in .sdx sequencer banks.

Run against your own .sdx files to see which opcodes actually appear,
their parameter values, and frequent patterns.

Usage:
    python scripts/analyze_opcodes.py path/to/pk000000.sdx [pk000001.sdx ...]
"""

import sys
import os
from collections import Counter, defaultdict

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from mgs2_audio.formats.sequence import parse_sequence, OPCODE_NAMES, OP_END


def fmt_params(e):
    """Format event parameters as a compact string."""
    if e.is_note:
        return f"vel={e.velocity:3d} gate={e.gate_pct:3d}% delay={e.delay:3d}"
    parts = []
    if e.b0:
        parts.append(f"b0={e.b0}")
    if e.b1:
        parts.append(f"b1={e.b1}")
    if e.b2:
        parts.append(f"b2={e.b2}")
    return " ".join(parts) if parts else "--"


def analyze(path):
    print(f"\n{'=' * 72}")
    print(f"FILE: {path}")
    print(f"{'=' * 72}")

    bank = parse_sequence(path)
    print(f"Instruments: {len(bank.instruments)}")
    print(f"Cues:        {len(bank.cues)}")

    # ── Per-opcode statistics ──
    opcode_counts = Counter()
    param_ranges = defaultdict(lambda: {"b0": set(), "b1": set(), "b2": set()})
    note_params = {"velocity": set(), "gate": set(), "delay": set()}
    pattern_counter = Counter()
    track_count_total = 0

    for cue in bank.cues:
        # show first few cues in detail
        show_detail = cue.index < 3

        for ti, addr in enumerate(cue.tracks):
            events = bank.track(addr)
            track_count_total += 1
            if not events:
                continue

            # Track header for detailed cues
            if show_detail:
                print(f"\n  -- Cue {cue.index} (kind={cue.kind:#04x}), Track {ti} ({len(events)} events) --")

            last_op = None
            seq = []

            for ei, e in enumerate(events):
                name = OPCODE_NAMES.get(e.opcode, f"???" if e.opcode >= 0x80 else "note")

                if e.is_note:
                    note_params["velocity"].add(e.velocity)
                    note_params["gate"].add(e.gate_pct)
                    note_params["delay"].add(e.delay)
                    tag = f"note {e.pitch}"
                else:
                    tag = f"{name}"

                opcode_counts[e.opcode] += 1

                if not e.is_note:
                    param_ranges[e.opcode]["b0"].add(e.b0)
                    param_ranges[e.opcode]["b1"].add(e.b1)
                    param_ranges[e.opcode]["b2"].add(e.b2)

                # track 2-grams (pairs)
                if last_op is not None:
                    pattern_counter[(last_op, e.opcode)] += 1
                last_op = e.opcode if not e.is_note else 0xFF  # treat notes as a group

                if show_detail:
                    sep = ""
                    p = fmt_params(e)
                    print(f"    {e.opcode:#04x}  {name:<30s}  {p}")

            if show_detail:
                # print Event byte representation
                pass

    # ── Summary ──
    print(f"\n{'=' * 72}")
    print(f"SUMMARY - {len(bank.cues)} cues, {track_count_total} tracks")
    print(f"{'=' * 72}")

    # Opcode frequency
    print(f"\nOpcode frequencies:")
    for opcode, count in opcode_counts.most_common():
        pct = count / sum(opcode_counts.values()) * 100
        name = OPCODE_NAMES.get(opcode, "note" if opcode < 0x80 else "???")
        vals = param_ranges.get(opcode)
        if vals:
            b0 = sorted(vals["b0"]) if vals["b0"] else []
            b1 = sorted(vals["b1"]) if vals["b1"] else []
            b2 = sorted(vals["b2"]) if vals["b2"] else []
            extra = ""
            if b0:
                extra += f" b0=[{min(b0)}..{max(b0)}]"
            if b1:
                extra += f" b1=[{min(b1)}..{max(b1)}]"
            if b2:
                extra += f" b2=[{min(b2)}..{max(b2)}]"
        else:
            extra = ""
        print(f"  {opcode:#04x}  {name:<30s}  {count:>5}x ({pct:.1f}%){extra}")

    if note_params["velocity"]:
        v = sorted(note_params["velocity"])
        g = sorted(note_params["gate"])
        d = sorted(note_params["delay"])
        print(f"  note  {'note':<30s}  velocities={v[0]}..{v[-1]}, gates={g[0]}..{g[-1]}, delays={d[0]}..{d[-1]}")

    # Top patterns
    if pattern_counter:
        print(f"\nMost common opcode pairs (transition ->):")
        for (a, b), count in pattern_counter.most_common(20):
            aname = OPCODE_NAMES.get(a, "note" if a < 0x80 else "???")
            bname = OPCODE_NAMES.get(b, "note" if b < 0x80 else "???")
            print(f"  {aname:<30s}  -> {bname:<30s}  ({count}x)")

    # Reverb usage
    reverb_cues = 0
    for cue in bank.cues:
        for addr in cue.tracks:
            for e in bank.track(addr):
                if e.opcode in (0xF6, 0xF7):
                    reverb_cues += 1
                    break

    print(f"\nReverb found in {reverb_cues}/{len(bank.cues)} cues")
    print()

    # ── Name reconciliation hints ──
    # Check if 0xD5 is used with pan-like values (0 or 255) or volume-like (0-127)
    d5_vals = param_ranges.get(0xD5, {}).get("b2", set())
    d0_vals = param_ranges.get(0xD0, {}).get("b2", set())

    hints = []
    if d5_vals:
        if max(d5_vals) <= 127:
            hints.append(f"  0xD5 b2 in [{min(d5_vals)}..{max(d5_vals)}] -> looks like VOLUME (0-127), not PAN")
        if max(d5_vals) > 200:
            hints.append(f"  0xD5 b2 in [{min(d5_vals)}..{max(d5_vals)}] -> looks like PAN (0-255)")
    if d0_vals:
        hints.append(f"  0xD0 b2 in [{min(d0_vals)}..{max(d0_vals)}] -> tempo (raven) or volume?")

    if hints:
        print(f"Reconciliation hints:")
        for h in hints:
            print(f"  {h}")

    return opcode_counts


def main():
    paths = sys.argv[1:]
    if not paths:
        print(__doc__)
        sys.exit(1)

    for p in paths:
        if not os.path.exists(p):
            print(f"NOT FOUND: {p}")
            continue
        try:
            analyze(p)
        except ValueError as e:
            print(f"SKIP ({e}): {p}")


if __name__ == "__main__":
    main()
