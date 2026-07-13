#!/usr/bin/env python3
"""
decode_gbs_payload.py — Decode the payload record format inside gbs_stage_*.sar.

Focuses on:
1. Full entry table dump (all 380 entries, including zero-hash ones)
2. CRC32 hashing of common MGS2 resource names to match entry hashes
3. Payload record parsing based on entry offset/size pairs
4. Structural analysis of the payload data

Usage:
    python scripts/decode_gbs_payload.py "C:/Games/Steam/steamapps/common/MGS2"
"""

import os
import struct
import sys
import zlib
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple


SAR_MAGIC = 0x000154F6
ENTRY_SIZE = 32
TABLE_START = 0x40


def parse_sar(path: str):
    with open(path, "rb") as f:
        raw = f.read()

    magic = struct.unpack_from("<I", raw, 0)[0]
    entry_count = struct.unpack_from("<I", raw, 4)[0]
    data_size = struct.unpack_from("<I", raw, 8)[0]

    entries = []
    for i in range(entry_count):
        off = TABLE_START + i * ENTRY_SIZE
        if off + ENTRY_SIZE > len(raw):
            break
        entry_raw = raw[off:off + ENTRY_SIZE]
        hash_crc = struct.unpack_from("<I", entry_raw, 0)[0]
        offset = struct.unpack_from("<I", entry_raw, 8)[0]
        field_18 = struct.unpack_from("<I", entry_raw, 0x18)[0]
        size = struct.unpack_from("<I", entry_raw, 0x1C)[0]
        entries.append({
            "index": i,
            "hash": hash_crc,
            "offset": offset,
            "field_18": field_18,
            "size": size,
            "raw": entry_raw,
        })

    table_end = TABLE_START + entry_count * ENTRY_SIZE
    payload = raw[table_end:]
    return raw, magic, entry_count, data_size, entries, payload


def hexdump(data: bytes, offset: int = 0, length: int = 64) -> str:
    lines = []
    end = min(len(data), offset + length)
    for i in range(offset, end, 16):
        chunk = data[i:i + 16]
        hex_part = " ".join(f"{b:02X}" for b in chunk)
        ascii_part = "".join(chr(b) if 32 <= b < 127 else "." for b in chunk)
        lines.append(f"  {i:08X}: {hex_part:<48s}  {ascii_part}")
    return "\n".join(lines)


# ─── CRC32 name matching ─────────────────────────────────────────────────────

def try_crc32_names():
    """Compute CRC32 of common MGS2 resource name patterns."""
    names = {}

    # Stage names (from directory listing)
    stage_names = [
        "a00a", "a02a", "a12a", "a12b", "a13a", "a13c", "a16a", "a20a", "a20e",
        "a25d", "a41a", "a45a", "d065p02", "sp03a", "sp06a",
        "w01b", "w01d", "w01f", "w02a", "w03a", "w12a", "w16b", "w17a",
        "w24c", "w24d", "w25b",
    ]

    # Try various name formats
    for s in stage_names:
        for prefix in ["", "pk000000", "pk000001", "pk000002", "pk000003",
                        "bgm_", "se_", "voice_", "gbs_", "stage_"]:
            for suffix in ["", ".sdx", ".sar", ".dat", ".var"]:
                name = prefix + s + suffix
                c = zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF
                names[c] = name

    # Try full paths the game might use
    for s in stage_names:
        for path in [
            f"us/stage/{s}/pk000000.sdx",
            f"us/stage/{s}/pk000001.sdx",
            f"stage/{s}/pk000000.sdx",
            f"./sound/stage/{s}",
            f"host0:./sound/mdx1/{s}",
            f"host0:./sound/stage/{s}",
            f"host0:./sound/{s}",
            f"gbs_stage_{s}",
            f"gbs_{s}",
            f"bgm_{s}",
            f"se_{s}",
        ]:
            c = zlib.crc32(path.encode("ascii")) & 0xFFFFFFFF
            names[c] = path

    # Try common SE/instrument names
    for name in [
        "footstep", "gunshot", "reload", "punch", "kick",
        "door_open", "door_close", "alarm", "beep",
        "rain", "wind", "thunder", "explosion",
        "voice_p1", "voice_p2", "voice_enemy",
        "bgm_init", "se_init", "gbs_init",
        "common", "shared", "global",
        "infiltration", "encounter", "action",
        "theme", "melody", "bass", "drums", "piano",
        "strings", "brass", "woodwind", "percussion",
    ]:
        c = zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF
        names[c] = name

    return names


# ─── Payload record analysis ─────────────────────────────────────────────────

def analyze_payload_records(payload: bytes, entries: list) -> str:
    """Try to parse the payload using entry offset/size pairs."""
    lines = []

    active = [e for e in entries if e["hash"] != 0]
    active_sorted = sorted(active, key=lambda e: e["offset"])

    lines.append(f"\nActive entries sorted by payload offset ({len(active_sorted)}):")
    lines.append(f"{'Idx':>5s}  {'Hash':>10s}  {'Offset':>8s}  {'Size':>6s}  {'F18':>8s}  Data")
    lines.append("-" * 90)

    for e in active_sorted:
        data = payload[e["offset"]:e["offset"] + e["size"]]
        data_hex = " ".join(f"{b:02X}" for b in data[:20])
        if len(data) > 20:
            data_hex += " ..."
        lines.append(
            f"{e['index']:>5d}  0x{e['hash']:08X}  0x{e['offset']:06X}  "
            f"{e['size']:>6d}  0x{e['field_18']:06X}  {data_hex}"
        )

    # Check for overlapping regions
    regions = [(e["offset"], e["offset"] + e["size"], e["index"]) for e in active_sorted]
    overlaps = []
    for i in range(len(regions) - 1):
        if regions[i][1] > regions[i + 1][0]:
            overlaps.append((regions[i], regions[i + 1]))
    if overlaps:
        lines.append(f"\n  WARNING: {len(overlaps)} overlapping payload regions!")
        for r1, r2 in overlaps[:5]:
            lines.append(f"    Entry {r1[2]} ends at 0x{r1[1]:X}, entry {r2[2]} starts at 0x{r2[0]:X}")
    else:
        lines.append(f"\n  No overlapping payload regions.")

    # Check for gaps
    gaps = []
    for i in range(len(active_sorted) - 1):
        end = active_sorted[i]["offset"] + active_sorted[i]["size"]
        next_start = active_sorted[i + 1]["offset"]
        if end < next_start:
            gap_size = next_start - end
            gaps.append((end, gap_size, active_sorted[i]["index"], active_sorted[i + 1]["index"]))
    if gaps:
        lines.append(f"\n  Gaps between entries:")
        for gap_off, gap_sz, prev_idx, next_idx in gaps[:20]:
            gap_data = payload[gap_off:gap_off + min(gap_sz, 32)]
            gap_hex = " ".join(f"{b:02X}" for b in gap_data[:32])
            lines.append(
                f"    0x{gap_off:06X}..0x{gap_off + gap_sz:06X} ({gap_sz:>4d} bytes, "
                f"after entry {prev_idx}, before entry {next_idx}): {gap_hex}"
            )
            # Show the gap data as potential records
            if gap_sz >= 4:
                for j in range(0, min(gap_sz, 64), 4):
                    v = struct.unpack_from("<I", payload, gap_off + j)[0]
                    lines.append(f"      +{j:02X}: 0x{v:08X} ({v})")

    return "\n".join(lines)


def scan_record_patterns(payload: bytes) -> str:
    """Scan the payload for structured record patterns."""
    lines = []

    # Look for the 0x1770 (6000) value pattern
    lines.append("\n--- Pattern: records ending with 0x1770 ---")
    count = 0
    positions = []
    for i in range(0, len(payload) - 7, 4):
        v = struct.unpack_from("<I", payload, i + 4)[0]
        if v == 0x1770:
            # Show the 4 bytes before
            prefix = payload[i:i + 4]
            positions.append(i)
            count += 1
    lines.append(f"  u32 0x1770 found at {count} positions (every 4 bytes)")
    if positions:
        lines.append(f"  First 20 positions: {[f'0x{p:X}' for p in positions[:20]]}")

    # Look for FF FF 00 00 delimiters
    lines.append("\n--- Pattern: FF FF 00 00 delimiters ---")
    delim_positions = []
    for i in range(0, len(payload) - 3):
        if payload[i:i + 4] == b"\xFF\xFF\x00\x00":
            delim_positions.append(i)
    lines.append(f"  Found {len(delim_positions)} delimiters")

    if delim_positions:
        # Analyze content between delimiters
        lines.append("\n  Content between first 20 delimiters:")
        for j in range(min(20, len(delim_positions) - 1)):
            start = delim_positions[j]
            end = delim_positions[j + 1]
            size = end - start
            block = payload[start:end]

            # Parse the block
            first_word = struct.unpack_from("<I", block, 0)[0]
            second_word = struct.unpack_from("<I", block, 4)[0] if len(block) >= 8 else 0

            lines.append(
                f"    [{j:3d}] 0x{start:06X}-0x{end:06X} ({size:>4d}B): "
                f"first=0x{first_word:08X} second=0x{second_word:08X}  "
                f"{' '.join(f'{b:02X}' for b in block[:32])}"
            )

    # Look for common byte sequences
    lines.append("\n--- Most common 4-byte sequences (aligned) ---")
    seq_counter = Counter()
    for i in range(0, len(payload) - 3, 4):
        seq = payload[i:i + 4]
        seq_counter[seq] += 1
    for seq, count in seq_counter.most_common(20):
        v = struct.unpack_from("<I", seq)[0]
        lines.append(f"  {seq.hex()}: {count:>4d}  (u32 = 0x{v:08X} = {v})")

    # Look for common 8-byte sequences
    lines.append("\n--- Most common 8-byte sequences (aligned) ---")
    seq8_counter = Counter()
    for i in range(0, len(payload) - 7, 8):
        seq = payload[i:i + 8]
        seq8_counter[seq] += 1
    for seq, count in seq8_counter.most_common(15):
        lines.append(f"  {seq.hex()}: {count:>4d}")

    return "\n".join(lines)


def analyze_entry_format(raw: bytes, entry_count: int) -> str:
    """Deep-dive into the entry table format."""
    lines = []

    # Dump ALL entries (not just active ones)
    lines.append(f"\nAll {entry_count} entries (showing non-zero ones):")
    lines.append(f"{'Idx':>5s}  {'Hash':>10s}  {'Off+08':>8s}  {'F10':>8s}  {'F14':>8s}  {'F18':>8s}  {'Size':>8s}")
    lines.append("-" * 85)

    non_zero_count = 0
    for i in range(entry_count):
        off = TABLE_START + i * ENTRY_SIZE
        entry_raw = raw[off:off + ENTRY_SIZE]
        hash_crc = struct.unpack_from("<I", entry_raw, 0)[0]
        f_08 = struct.unpack_from("<I", entry_raw, 8)[0]
        f_10 = struct.unpack_from("<I", entry_raw, 0x10)[0]
        f_14 = struct.unpack_from("<I", entry_raw, 0x14)[0]
        f_18 = struct.unpack_from("<I", entry_raw, 0x18)[0]
        size = struct.unpack_from("<I", entry_raw, 0x1C)[0]

        if hash_crc != 0 or f_08 != 0 or f_18 != 0 or size != 0:
            non_zero_count += 1
            lines.append(
                f"{i:>5d}  0x{hash_crc:08X}  0x{f_08:06X}  0x{f_10:06X}  "
                f"0x{f_14:06X}  0x{f_18:06X}  0x{size:06X}"
            )

    lines.append(f"\nNon-zero entries: {non_zero_count} / {entry_count}")

    # Analyze the field_18 pattern
    lines.append("\nField at offset 0x18 analysis:")
    f18_values = []
    for i in range(entry_count):
        off = TABLE_START + i * ENTRY_SIZE
        f_18 = struct.unpack_from("<I", raw, off + 0x18)[0]
        if f_18 != 0:
            f18_values.append((i, f_18))

    # Check if field_18 forms a chain
    lines.append(f"  Non-zero values: {len(f18_values)}")
    if f18_values:
        lines.append(f"  First 30: {[(i, f'0x{v:X}') for i, v in f18_values[:30]]}")

    # Check the raw hex of a few specific entries
    lines.append("\nFull 32-byte raw dump of first 5 active entries:")
    shown = 0
    for i in range(entry_count):
        off = TABLE_START + i * ENTRY_SIZE
        entry_raw = raw[off:off + ENTRY_SIZE]
        hash_crc = struct.unpack_from("<I", entry_raw, 0)[0]
        if hash_crc != 0:
            hex_str = " ".join(f"{b:02X}" for b in entry_raw)
            lines.append(f"  Entry {i}: {hex_str}")
            shown += 1
            if shown >= 5:
                break

    # Show the first few INACTIVE entries
    lines.append("\nFull 32-byte raw dump of first 5 INACTIVE entries:")
    shown = 0
    for i in range(entry_count):
        off = TABLE_START + i * ENTRY_SIZE
        entry_raw = raw[off:off + ENTRY_SIZE]
        hash_crc = struct.unpack_from("<I", entry_raw, 0)[0]
        if hash_crc == 0:
            hex_str = " ".join(f"{b:02X}" for b in entry_raw)
            lines.append(f"  Entry {i}: {hex_str}")
            shown += 1
            if shown >= 5:
                break

    return "\n".join(lines)


def compare_payloads_across_stages(sar_dir: str) -> str:
    """Compare entry tables and payloads across multiple stage SARs."""
    lines = []

    stage_files = sorted(
        f for f in os.listdir(sar_dir)
        if f.startswith("gbs_stage_") and f.endswith(".sar")
    )

    # Parse all stage SARs
    stage_sars = {}
    for fname in stage_files:
        path = os.path.join(sar_dir, fname)
        raw, magic, entry_count, data_size, entries, payload = parse_sar(path)
        stage_sars[fname] = {
            "entries": entries, "payload": payload, "raw": raw,
            "active": [e for e in entries if e["hash"] != 0],
        }

    # Find which entries are common to ALL stages
    all_hashes = set()
    for fname, sar in stage_sars.items():
        hashes = set(e["hash"] for e in sar["active"])
        if not all_hashes:
            all_hashes = hashes
        else:
            all_hashes &= hashes

    lines.append(f"\nEntries common to ALL {len(stage_files)} stage files: {len(all_hashes)}")
    for h in sorted(all_hashes):
        # Find which entry index has this hash in any file
        for fname, sar in stage_sars.items():
            for e in sar["active"]:
                if e["hash"] == h:
                    lines.append(f"  0x{h:08X} (idx={e['index']}, size={e['size']})")
                    break
            break

    # Find stage-specific entries
    lines.append(f"\nStage-specific entries (unique to one stage):")
    hash_to_stages = defaultdict(list)
    for fname, sar in stage_sars.items():
        for e in sar["active"]:
            hash_to_stages[e["hash"]].append(fname)

    unique_entries = {h: stages for h, stages in hash_to_stages.items() if len(stages) == 1}
    lines.append(f"  Unique to one stage: {len(unique_entries)}")
    for h, stages in sorted(unique_entries.items(), key=lambda x: x[1][0]):
        # Find the entry details
        for fname, sar in stage_sars.items():
            if fname == stages[0]:
                for e in sar["active"]:
                    if e["hash"] == h:
                        lines.append(f"    0x{h:08X} -> {stages[0]} (idx={e['index']}, size={e['size']})")
                        break
                break

    # Compare specific entry data between stages
    if all_hashes:
        lines.append(f"\nPayload data for a common entry (first 5 stages):")
        common_hash = sorted(all_hashes)[0]
        for fname in stage_files[:5]:
            sar = stage_sars[fname]
            for e in sar["active"]:
                if e["hash"] == common_hash:
                    data = sar["payload"][e["offset"]:e["offset"] + e["size"]]
                    hex_str = " ".join(f"{b:02X}" for b in data)
                    lines.append(f"  {fname}: [{e['size']}B] {hex_str}")
                    break

    return "\n".join(lines)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/decode_gbs_payload.py <game_root>")
        sys.exit(1)

    game_root = sys.argv[1]
    sar_dir = os.path.join(game_root, "assets", "sar", "us")

    # ─── CRC32 name matching ──────────────────────────────────────────────
    print("=" * 70)
    print("SECTION 1: CRC32 NAME MATCHING")
    print("=" * 70)

    known_crcs = try_crc32_names()

    # Parse base gbs.sar and a stage file
    base_path = os.path.join(sar_dir, "gbs.sar")
    stage_path = os.path.join(sar_dir, "gbs_stage_sp03a.sar")

    _, _, _, _, base_entries, _ = parse_sar(base_path)
    _, _, _, _, stage_entries, _ = parse_sar(stage_path)

    base_hashes = set(e["hash"] for e in base_entries if e["hash"] != 0)
    stage_hashes = set(e["hash"] for e in stage_entries if e["hash"] != 0)

    all_hashes = base_hashes | stage_hashes
    matched = 0
    for h in sorted(all_hashes):
        if h in known_crcs:
            print(f"  MATCH: 0x{h:08X} = {known_crcs[h]}")
            matched += 1

    print(f"\n  Matched {matched} / {len(all_hashes)} hashes")
    print(f"  (Trying CRC32 of stage names, paths, common resource names)")

    # Also try hashing with different encodings
    print(f"\n  Trying more patterns...")
    extra_names = []
    for s in ["a02a", "a12a", "a13a", "a20a", "a41a", "a45a", "sp03a", "w12a", "w16b"]:
        for pat in [
            f"pk{s}", f"stage_{s}", f"gbs_{s}", f"bgm_{s}", f"se_{s}",
            f"us/stage/{s}", f"stage/{s}", s,
            f"{s}_bgm", f"{s}_se", f"{s}_gbs",
            f"sound_{s}", f"music_{s}",
        ]:
            extra_names.append(pat)
    for name in extra_names:
        c = zlib.crc32(name.encode("ascii")) & 0xFFFFFFFF
        if c in all_hashes:
            print(f"  MATCH: CRC32({name!r}) = 0x{c:08X}")
            matched += 1

    # ─── Entry format deep-dive ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 2: ENTRY FORMAT DEEP-DIVE (gbs.sar)")
    print("=" * 70)

    raw, magic, entry_count, data_size, entries, payload = parse_sar(base_path)
    print(analyze_entry_format(raw, entry_count))

    # ─── Payload record parsing ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 3: PAYLOAD RECORD PARSING (gbs_stage_sp03a.sar)")
    print("=" * 70)

    raw, magic, entry_count, data_size, entries, payload = parse_sar(stage_path)
    print(f"Payload size: {len(payload):,} bytes")
    print(analyze_payload_records(payload, entries))

    # ─── Record pattern scanning ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 4: RECORD PATTERN SCANNING (gbs_stage_sp03a.sar)")
    print("=" * 70)
    print(scan_record_patterns(payload))

    # ─── Cross-stage comparison ──────────────────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 5: CROSS-STAGE COMPARISON")
    print("=" * 70)
    print(compare_payloads_across_stages(sar_dir))

    # ─── Hex dump of first payload records ───────────────────────────────
    print(f"\n{'='*70}")
    print("SECTION 6: PAYLOAD RECORD DUMP (first 10 active entries)")
    print("=" * 70)

    active = sorted(
        [e for e in entries if e["hash"] != 0],
        key=lambda e: e["offset"]
    )
    for e in active[:10]:
        data = payload[e["offset"]:e["offset"] + e["size"]]
        print(f"\n  Entry {e['index']} (hash=0x{e['hash']:08X}, offset=0x{e['offset']:X}, size={e['size']}):")
        print(hexdump(data, 0, e["size"]))

        # Try to interpret as records
        if e["size"] >= 8:
            n_words = e["size"] // 4
            words = [struct.unpack_from("<I", data, j * 4)[0] for j in range(n_words)]
            print(f"  As u32: {' '.join(f'0x{w:08X}' for w in words)}")


if __name__ == "__main__":
    main()
