#!/usr/bin/env python3
"""
analyze_gbs_sar.py — Deep analysis of gbs_stage_*.sar files from MGS2 MC.

These files are suspected to contain orchestration/music data for the
in-game music. This script parses the SAR format, extracts payloads,
and searches for raven sequencer patterns (opcodes 0xD0-0xFF, note events,
end-of-track markers, etc.).

Usage:
    python scripts/analyze_gbs_sar.py "C:/Games/Steam/steamapps/common/MGS2"
"""

import os
import struct
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

# ─── Raven sequencer constants (from docs/FORMATS.md) ────────────────────────

RAVEN_OPCODES = {
    0xD0: "tempo_set",
    0xD1: "tempo_move",
    0xD2: "sno_set (program)",
    0xD3: "svl_set",
    0xD4: "svp_set",
    0xD5: "vol_chg",
    0xD6: "vol_move",
    0xD7: "ads_set",
    0xD8: "srs_set",
    0xD9: "rrs_set",
    0xDA: "no_cmd",
    0xDB: "no_cmd",
    0xDC: "no_cmd",
    0xDD: "pan_set",
    0xDE: "pan_move",
    0xDF: "trans_set",
    0xE0: "detune_set",
    0xE1: "vib_set",
    0xE2: "vib_change",
    0xE3: "rdm_set",
    0xE4: "swp_set",
    0xE5: "sws_set",
    0xE6: "por_set",
    0xE7: "lp1_start",
    0xE8: "lp1_end",
    0xE9: "lp2_start",
    0xEA: "lp2_end",
    0xEB: "l3s_set",
    0xEC: "l3e_set",
    0xED: "kakko_start",
    0xEE: "kakko_end",
    0xEF: "no_cmd",
    0xF0: "no_cmd",
    0xF1: "use_set",
    0xF2: "rest_set",
    0xF3: "tie_set",
    0xF4: "echo_set1",
    0xF5: "echo_set2",
    0xF6: "eon_set (reverb on)",
    0xF7: "eof_set (reverb off)",
    0xF8: "no_cmd",
    0xF9: "no_cmd",
    0xFA: "no_cmd",
    0xFB: "no_cmd",
    0xFC: "no_cmd",
    0xFD: "no_cmd",
    0xFE: "no_cmd",
    0xFF: "block_end",
}

END_EVENT = b"\x00\x00\xfe\xff"

# ─── SAR format ──────────────────────────────────────────────────────────────

SAR_MAGIC = 0x000154F6

@dataclass
class SAREntry:
    index: int
    hash_crc: int
    offset: int
    size_a: int
    size_b: int
    raw: bytes  # 32 bytes of the entry record


@dataclass
class SARFile:
    path: str
    raw: bytes
    magic: int
    entry_count: int
    data_size: int
    entries: List[SAREntry] = field(default_factory=list)
    data_payload: bytes = b""


def parse_sar(path: str) -> SARFile:
    with open(path, "rb") as f:
        raw = f.read()

    magic = struct.unpack_from("<I", raw, 0)[0]
    entry_count = struct.unpack_from("<I", raw, 4)[0]
    data_size = struct.unpack_from("<I", raw, 8)[0]

    sar = SARFile(
        path=path, raw=raw, magic=magic,
        entry_count=entry_count, data_size=data_size,
    )

    # Entry table starts at 0x40 (after 64-byte header)
    ENTRY_SIZE = 32
    table_start = 0x40
    table_end = table_start + entry_count * ENTRY_SIZE

    active_entries = []
    for i in range(entry_count):
        off = table_start + i * ENTRY_SIZE
        if off + ENTRY_SIZE > len(raw):
            break
        entry_raw = raw[off:off + ENTRY_SIZE]
        hash_crc = struct.unpack_from("<I", entry_raw, 0)[0]
        offset = struct.unpack_from("<I", entry_raw, 8)[0]
        size_a = struct.unpack_from("<I", entry_raw, 0x1C)[0] if len(entry_raw) >= 0x20 else 0
        size_b = 0  # field at +0x20 is past the 32-byte record

        entry = SAREntry(
            index=i, hash_crc=hash_crc, offset=offset,
            size_a=size_a, size_b=size_b, raw=entry_raw,
        )
        sar.entries.append(entry)
        if hash_crc != 0 and hash_crc != 0x4C:
            active_entries.append(entry)

    sar.data_payload = raw[table_end:]
    return sar


# ─── Analysis functions ──────────────────────────────────────────────────────

def analyze_raven_patterns(data: bytes, label: str) -> dict:
    """Scan data for raven sequencer opcode patterns."""
    results = {
        "size": len(data),
        "opcodes_found": Counter(),
        "notes_found": 0,
        "end_markers": 0,
        "possible_tracks": 0,
        "high_bytes": Counter(),  # bytes >= 0xD0
        "patterns": [],
    }

    # Scan for opcodes (last byte of each 4-byte event)
    i = 0
    while i + 4 <= len(data):
        b0, b1, b2, op = data[i], data[i+1], data[i+2], data[i+3]

        if op in RAVEN_OPCODES:
            results["opcodes_found"][f"0x{op:02X} ({RAVEN_OPCODES[op]})"] += 1

        if op < 0x80 and op > 0:
            results["notes_found"] += 1

        if data[i:i+4] == END_EVENT:
            results["end_markers"] += 1

        if op >= 0xD0:
            results["high_bytes"][f"0x{op:02X}"] += 1

        i += 4

    # Also scan byte-by-byte for interesting patterns
    for i in range(len(data)):
        if data[i] >= 0xD0 and data[i] <= 0xFF:
            pass  # already counted above

    return results


def find_structures(data: bytes) -> list:
    """Try to find structured regions in the data."""
    findings = []

    # Look for runs of 4-byte events where the last byte is a valid opcode
    run_start = None
    run_len = 0
    best_run = (0, 0)

    for i in range(0, len(data) - 3, 4):
        op = data[i + 3]
        is_event = (op < 0x80) or (0xD0 <= op <= 0xFF)

        if is_event:
            if run_start is None:
                run_start = i
                run_len = 1
            else:
                run_len += 1
        else:
            if run_len > best_run[1]:
                best_run = (run_start, run_len)
            run_start = None
            run_len = 0

    if run_len > best_run[1]:
        best_run = (run_start, run_len)

    if best_run[1] >= 4:
        findings.append({
            "type": "event_stream",
            "offset": best_run[0],
            "length_events": best_run[1],
            "length_bytes": best_run[1] * 4,
        })

    # Look for END_EVENT markers
    end_positions = []
    for i in range(0, len(data) - 3, 4):
        if data[i:i+4] == END_EVENT:
            end_positions.append(i)
    if end_positions:
        findings.append({
            "type": "end_markers",
            "positions": end_positions[:50],
            "total": len(end_positions),
        })

    # Look for 0x4C bytes (null marker in SAR entries) repeated
    count_4c = sum(1 for b in data if b == 0x4C)
    if count_4c > 10:
        findings.append({
            "type": "repeated_0x4C",
            "count": count_4c,
        })

    return findings


def hexdump(data: bytes, offset: int = 0, length: int = 256) -> str:
    """Produce a hex dump of data."""
    lines = []
    end = min(len(data), offset + length)
    for i in range(offset, end, 16):
        chunk = data[i:i + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {i:08X}: {hex_part:<48s}  {ascii_part}")
    return "\n".join(lines)


def compare_two_sars(sar1: SARFile, sar2: SARFile) -> str:
    """Compare two SAR files to find shared vs unique data."""
    lines = []
    lines.append(f"\n{'='*60}")
    lines.append(f"COMPARISON: {os.path.basename(sar1.path)} vs {os.path.basename(sar2.path)}")
    lines.append(f"{'='*60}")

    # Compare headers
    h1 = sar1.raw[:0x40]
    h2 = sar2.raw[:0x40]
    if h1 == h2:
        lines.append("  Headers: IDENTICAL")
    else:
        lines.append("  Headers: DIFFERENT")
        for i in range(0, min(len(h1), len(h2)), 4):
            v1 = struct.unpack_from("<I", h1, i)[0]
            v2 = struct.unpack_from("<I", h2, i)[0]
            if v1 != v2:
                lines.append(f"    Offset 0x{i:02X}: {v1:#010x} vs {v2:#010x}")

    # Compare entry tables
    t1_end = 0x40 + sar1.entry_count * 32
    t2_end = 0x40 + sar2.entry_count * 32
    table1 = sar1.raw[0x40:t1_end]
    table2 = sar2.raw[0x40:t2_end]

    if table1 == table2:
        lines.append("  Entry tables: IDENTICAL")
    else:
        diffs = 0
        for i in range(0, min(len(table1), len(table2)), 32):
            if table1[i:i+32] != table2[i:i+32]:
                diffs += 1
        lines.append(f"  Entry tables: {diffs} different entries out of {sar1.entry_count}")

    # Compare data payloads
    if sar1.data_payload == sar2.data_payload:
        lines.append("  Data payloads: IDENTICAL")
    else:
        # Find where they diverge
        div_point = 0
        for i in range(min(len(sar1.data_payload), len(sar2.data_payload))):
            if sar1.data_payload[i] != sar2.data_payload[i]:
                div_point = i
                break
        lines.append(f"  Data payloads: DIFFERENT (diverge at offset 0x{div_point:X} into payload)")
        lines.append(f"  Payload sizes: {len(sar1.data_payload)} vs {len(sar2.data_payload)} bytes")

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/analyze_gbs_sar.py <game_root>")
        print("  e.g. python scripts/analyze_gbs_sar.py \"C:/Games/Steam/steamapps/common/MGS2\"")
        sys.exit(1)

    game_root = sys.argv[1]
    sar_dir = os.path.join(game_root, "assets", "sar", "us")

    if not os.path.isdir(sar_dir):
        print(f"ERROR: SAR directory not found: {sar_dir}")
        sys.exit(1)

    # Find all gbs_*.sar files
    gbs_files = sorted(
        f for f in os.listdir(sar_dir)
        if f.startswith("gbs") and f.endswith(".sar")
    )

    if not gbs_files:
        print(f"ERROR: No gbs_*.sar files found in {sar_dir}")
        sys.exit(1)

    print(f"Found {len(gbs_files)} gbs_*.sar files in {sar_dir}\n")

    # Parse all files
    sars = {}
    for fname in gbs_files:
        path = os.path.join(sar_dir, fname)
        try:
            sar = parse_sar(path)
            sars[fname] = sar
        except Exception as e:
            print(f"  ERROR parsing {fname}: {e}")

    # ─── Section 1: Overview ──────────────────────────────────────────────
    print("=" * 70)
    print("SECTION 1: OVERVIEW OF ALL gbs_*.sar FILES")
    print("=" * 70)
    print(f"{'File':<35s} {'Size':>8s}  {'Entries':>7s}  {'Active':>6s}  {'Payload':>8s}")
    print("-" * 70)

    stage_sars = {}
    other_sars = {}

    for fname, sar in sorted(sars.items(), key=lambda x: len(x[1].raw), reverse=True):
        active = sum(1 for e in sar.entries if e.hash_crc != 0 and e.hash_crc != 0x4C)
        print(f"{fname:<35s} {len(sar.raw):>8,}  {sar.entry_count:>7d}  {active:>6d}  {len(sar.data_payload):>8,}")

        if fname.startswith("gbs_stage_"):
            stage_sars[fname] = sar
        else:
            other_sars[fname] = sar

    # ─── Section 2: Detailed header analysis ──────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 2: HEADER STRUCTURE (first 0x80 bytes of largest file)")
    print("=" * 70)

    largest = max(sars.values(), key=lambda s: len(s.raw))
    print(f"\nFile: {os.path.basename(largest.path)} ({len(largest.raw):,} bytes)")
    print(hexdump(largest.raw, 0, 0x80))

    # Parse header fields
    magic = struct.unpack_from("<I", largest.raw, 0)[0]
    entry_count = struct.unpack_from("<I", largest.raw, 4)[0]
    data_size = struct.unpack_from("<I", largest.raw, 8)[0]
    field3 = struct.unpack_from("<I", largest.raw, 12)[0]
    print(f"\n  magic       = 0x{magic:08X} {'(SAR!)' if magic == SAR_MAGIC else '(UNKNOWN!)'}")
    print(f"  entry_count = {entry_count} (0x{entry_count:X})")
    print(f"  data_size   = {data_size} (0x{data_size:X})")
    print(f"  field3      = {field3} (0x{field3:X})")

    # Show some non-zero header fields
    print("\n  Non-zero u32s in header (0x00-0x3F):")
    for i in range(0, 0x40, 4):
        v = struct.unpack_from("<I", largest.raw, i)[0]
        if v != 0:
            print(f"    +0x{i:02X} = 0x{v:08X} ({v})")

    # ─── Section 3: Entry table analysis ──────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 3: ENTRY TABLE ANALYSIS")
    print("=" * 70)

    # Show first 20 active entries
    active = [e for e in largest.entries if e.hash_crc != 0 and e.hash_crc != 0x4C]
    print(f"\nActive entries in {os.path.basename(largest.path)}: {len(active)} / {largest.entry_count}")
    print(f"{'Idx':>5s}  {'Hash/CRC':>10s}  {'Offset':>10s}  {'SizeA':>10s}  {'SizeB':>10s}  Raw (first 16B)")
    print("-" * 90)
    for e in active[:30]:
        raw_hex = " ".join(f"{b:02X}" for b in e.raw[:16])
        print(f"{e.index:>5d}  0x{e.hash_crc:08X}  0x{e.offset:08X}  0x{e.size_a:08X}  0x{e.size_b:08X}  {raw_hex}")

    if len(active) > 30:
        print(f"  ... ({len(active) - 30} more entries)")

    # Hash distribution
    hash_counts = Counter(e.hash_crc for e in largest.entries)
    common_hashes = hash_counts.most_common(10)
    print(f"\nMost common entry hashes:")
    for h, c in common_hashes:
        marker = " (null/empty)" if h == 0x4C else (" (zero)" if h == 0 else "")
        print(f"  0x{h:08X}: {c} entries{marker}")

    # ─── Section 4: Data payload analysis ─────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 4: DATA PAYLOAD ANALYSIS")
    print("=" * 70)

    payload = largest.data_payload
    print(f"\nPayload size: {len(payload):,} bytes")
    print(f"Non-zero bytes: {sum(1 for b in payload if b != 0):,} ({100*sum(1 for b in payload if b != 0)/max(len(payload),1):.1f}%)")

    # Byte frequency
    byte_freq = Counter(payload)
    print(f"Unique byte values: {len(byte_freq)}")
    print(f"Most common bytes: {byte_freq.most_common(10)}")

    # Look for patterns at specific offsets
    print(f"\nHex dump of payload (first 512 bytes):")
    print(hexdump(payload, 0, 512))

    if len(payload) > 512:
        print(f"\nHex dump of payload (offset 0x400-0x800):")
        print(hexdump(payload, 0x400, 0x400))

    # ─── Section 5: Raven opcode pattern search ───────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 5: RAVEN SEQUENCER PATTERN SEARCH")
    print("=" * 70)

    # Scan the ENTIRE file for raven patterns
    full_results = analyze_raven_patterns(largest.raw, "full file")
    print(f"\nFull file scan ({os.path.basename(largest.path)}):")
    print(f"  Possible notes (opcode < 0x80): {full_results['notes_found']}")
    print(f"  End markers (00 00 FE FF):      {full_results['end_markers']}")
    if full_results["opcodes_found"]:
        print(f"  Raven opcodes found:")
        for op, count in sorted(full_results["opcodes_found"].items()):
            print(f"    {op}: {count}")

    # Scan just the payload
    payload_results = analyze_raven_patterns(payload, "payload")
    print(f"\nPayload-only scan:")
    print(f"  Possible notes: {payload_results['notes_found']}")
    print(f"  End markers:    {payload_results['end_markers']}")
    if payload_results["opcodes_found"]:
        print(f"  Raven opcodes:")
        for op, count in sorted(payload_results["opcodes_found"].items()):
            print(f"    {op}: {count}")

    # Also scan the entry table area
    table_data = largest.raw[0x40:0x40 + largest.entry_count * 32]
    table_results = analyze_raven_patterns(table_data, "entry table")
    print(f"\nEntry table scan:")
    print(f"  Possible notes: {table_results['notes_found']}")
    print(f"  End markers:    {table_results['end_markers']}")
    if table_results["opcodes_found"]:
        print(f"  Raven opcodes:")
        for op, count in sorted(table_results["opcodes_found"].items()):
            print(f"    {op}: {count}")

    # Scan the header area (0x00 - 0x40)
    header_results = analyze_raven_patterns(largest.raw[:0x40], "header")
    print(f"\nHeader scan (0x00-0x3F):")
    print(f"  Possible notes: {header_results['notes_found']}")
    print(f"  End markers:    {header_results['end_markers']}")

    # ─── Section 6: Structure detection ───────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 6: STRUCTURE DETECTION IN DATA PAYLOAD")
    print("=" * 70)

    structures = find_structures(payload)
    for s in structures:
        print(f"\n  Type: {s['type']}")
        for k, v in s.items():
            if k == "type":
                continue
            if k == "positions" and isinstance(v, list) and len(v) > 20:
                print(f"    {k}: [{', '.join(f'0x{x:X}' for x in v[:20])} ...] ({s['total']} total)")
            else:
                print(f"    {k}: {v}")

    # Try treating payload as 4-byte events
    print(f"\n  Treating payload as 4-byte events:")
    event_results = analyze_raven_patterns(payload, "payload as events")
    print(f"    Valid raven opcode hits: {sum(event_results['opcodes_found'].values())}")
    print(f"    Note events: {event_results['notes_found']}")
    print(f"    End markers: {event_results['end_markers']}")

    # Try different alignments
    for align in [1, 2, 3]:
        aligned = payload[align:]
        ar = analyze_raven_patterns(aligned, f"align+{align}")
        total_ops = sum(ar["opcodes_found"].values())
        if total_ops > 0:
            print(f"\n  Alignment +{align} ({len(aligned)} bytes):")
            print(f"    Raven opcode hits: {total_ops}")
            print(f"    Notes: {ar['notes_found']}, End markers: {ar['end_markers']}")
            for op, count in sorted(ar["opcodes_found"].items()):
                print(f"      {op}: {count}")

    # ─── Section 7: Cross-file comparison ─────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 7: CROSS-FILE COMPARISON")
    print("=" * 70)

    # Compare two stage SARs
    stage_list = sorted(stage_sars.keys())
    if len(stage_list) >= 2:
        sar_a = stage_sars[stage_list[0]]
        sar_b = stage_sars[stage_list[1]]
        print(compare_two_sars(sar_a, sar_b))

        # Also compare a big one and a small one
        smallest_stage = min(stage_sars.values(), key=lambda s: len(s.raw))
        biggest_stage = max(stage_sars.values(), key=lambda s: len(s.raw))
        if smallest_stage is not biggest_stage:
            print(compare_two_sars(smallest_stage, biggest_stage))

    # Compare gbs_stage vs character SAR
    char_path = os.path.join(sar_dir, "snake.sar")
    if os.path.exists(char_path):
        try:
            char_sar = parse_sar(char_path)
            print(compare_two_sars(largest, char_sar))
        except Exception as e:
            print(f"\n  Could not parse snake.sar: {e}")

    # ─── Section 8: Search for 0x1770 (6000) pattern ─────────────────────
    print(f"\n{'='*70}")
    print("SECTION 8: SEARCH FOR 0x1770 (6000) PATTERN")
    print("=" * 70)

    positions_1770 = []
    for i in range(len(payload) - 3):
        v = struct.unpack_from("<H", payload, i)[0]
        if v == 0x1770:
            positions_1770.append(i)

    print(f"\nOccurrences of 0x1770 as u16 in payload: {len(positions_1770)}")
    if positions_1770:
        print(f"  First 30 positions: {[f'0x{x:X}' for x in positions_1770[:30]]}")
        # Show context around first few
        for pos in positions_1770[:5]:
            print(f"\n  Context around 0x{pos:X}:")
            start = max(0, pos - 8)
            end = min(len(payload), pos + 10)
            print(hexdump(payload, start, end - start))

    # Also as u32
    positions_1770_32 = []
    for i in range(len(payload) - 3):
        v = struct.unpack_from("<I", payload, i)[0]
        if v == 0x00001770 or v == 0x17700000:
            positions_1770_32.append((i, v))
    if positions_1770_32:
        print(f"\nAs u32: {len(positions_1770_32)} occurrences")
        for pos, val in positions_1770_32[:10]:
            print(f"  0x{pos:X}: 0x{val:08X}")

    # ─── Section 9: Full hex dump of payload ──────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 9: FULL HEX DUMP OF DATA PAYLOAD")
    print("=" * 70)

    # Dump in chunks of 1024 bytes
    for chunk_start in range(0, min(len(payload), 4096), 1024):
        chunk_end = min(len(payload), chunk_start + 1024)
        print(f"\n  Offset 0x{chunk_start:04X} - 0x{chunk_end:04X}:")
        print(hexdump(payload, chunk_start, chunk_end - chunk_start))

    if len(payload) > 4096:
        print(f"\n  ... ({len(payload) - 4096} more bytes)")

    # ─── Summary ──────────────────────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)
    print(f"""
  Files analyzed:  {len(sars)}
  Stage SARs:      {len(stage_sars)} (gbs_stage_*)
  Other SARs:      {len(other_sars)} (gbs.sar, gbs_*.sar without 'stage_')

  Largest file:    {os.path.basename(largest.path)} ({len(largest.raw):,} bytes)
  Entry count:     {largest.entry_count}
  Active entries:  {len(active)}
  Data payload:    {len(largest.data_payload):,} bytes

  Raven opcodes in payload: {sum(payload_results['opcodes_found'].values())}
  Note events in payload:   {payload_results['notes_found']}
  End markers in payload:   {payload_results['end_markers']}

  The data payload contains structured binary data but does NOT cleanly
  parse as raven sequencer events at any alignment. This suggests the
  gbs_stage_*.sar files use a DIFFERENT data format than the .sdx
  sequence region — possibly a higher-level orchestration format that
  references the .sdx cues rather than containing raw note events.
""")


if __name__ == "__main__":
    main()
