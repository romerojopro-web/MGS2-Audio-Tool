#!/usr/bin/env python3
"""
crossref_sar_sdx.py — Cross-reference gbs_stage_*.sar payload records with
.sdx cue IDs, and trace the field_18 linked-list chain.

Usage:
    python scripts/crossref_sar_sdx.py "C:/Games/Steam/steamapps/common/MGS2"
"""

import os
import struct
import sys
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

SAR_MAGIC = 0x000154F6
ENTRY_SIZE = 32
TABLE_START = 0x40
PAYLOAD_DELIMITER = b"\xFF\xFF\x00\x00"

SDX_CUE_TABLE_SIZE = 0x1000  # 256 cues × 16 bytes
SDX_CUE_RECORD_SIZE = 16


# ═══════════════════════════════════════════════════════════════════════════════
# SAR parsing
# ═══════════════════════════════════════════════════════════════════════════════

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
        entries.append({
            "index": i,
            "hash": struct.unpack_from("<I", entry_raw, 0)[0],
            "f04": struct.unpack_from("<I", entry_raw, 4)[0],
            "offset": struct.unpack_from("<I", entry_raw, 8)[0],
            "f0C": struct.unpack_from("<I", entry_raw, 0x0C)[0],
            "f10": struct.unpack_from("<I", entry_raw, 0x10)[0],
            "f14": struct.unpack_from("<I", entry_raw, 0x14)[0],
            "field_18": struct.unpack_from("<I", entry_raw, 0x18)[0],
            "size": struct.unpack_from("<I", entry_raw, 0x1C)[0],
            "raw": entry_raw,
        })

    table_end = TABLE_START + entry_count * ENTRY_SIZE
    payload = raw[table_end:]
    return raw, magic, entry_count, data_size, entries, payload


def extract_entry_payload(entries, payload, entry):
    """Extract the raw bytes for one entry from the payload."""
    off = entry["offset"]
    sz = entry["size"]
    if off + sz > len(payload):
        return b""
    return payload[off:off + sz]


# ═══════════════════════════════════════════════════════════════════════════════
# SDX cue table parsing
# ═══════════════════════════════════════════════════════════════════════════════

def parse_sdx_cues(path: str) -> List[dict]:
    """Parse the cue table from an .sdx file.
    Returns a list of {index, kind, track_count, flags, track_offsets}."""
    with open(path, "rb") as f:
        raw = f.read()

    fsize = len(raw)
    table_start = fsize - SDX_CUE_TABLE_SIZE - 0x5800
    if table_start < 0:
        return []

    cues = []
    for i in range(256):
        rec_off = table_start + i * SDX_CUE_RECORD_SIZE
        if rec_off + SDX_CUE_RECORD_SIZE > fsize:
            break
        kind = raw[rec_off]
        n_tracks = raw[rec_off + 1]
        flags = (raw[rec_off + 2], raw[rec_off + 3])
        track_offsets = []
        for t in range(3):
            toff = struct.unpack_from("<I", raw, rec_off + 4 + t * 4)[0]
            track_offsets.append(toff)

        if n_tracks in (1, 2, 3) and track_offsets[0] != 0xFFFFFFFF:
            cues.append({
                "index": i,
                "kind": kind,
                "track_count": n_tracks,
                "flags": flags,
                "track_offsets": track_offsets[:n_tracks],
            })
        else:
            cues.append({
                "index": i,
                "kind": kind,
                "track_count": 0,
                "flags": flags,
                "track_offsets": [],
            })
    return cues


# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Field_18 chain trace
# ═══════════════════════════════════════════════════════════════════════════════

def trace_field_18_chain(entries):
    """Trace the field_18 linked-list chain and identify active vs inactive entries."""
    active = [e for e in entries if e["hash"] != 0 and e["hash"] != 0x4C]

    # Build reverse map: field_18 value -> entry index
    # field_18 of entry X points to the NEXT entry in the chain
    # So if entry 0 has field_18=28 (0x1C), entry 28 is next after entry 0
    f18_targets = {}
    for e in active:
        f18_targets[e["field_18"]] = e["index"]

    # Find chain start: an entry whose index is NOT targeted by any other active entry
    targeted_indices = set(e["field_18"] for e in active)
    chain_starts = [e["index"] for e in active if e["index"] not in targeted_indices]

    # Trace chains
    chains = []
    for start in chain_starts:
        chain = [start]
        current = start
        visited = {start}
        while True:
            # Find the entry whose field_18 points to current
            found = False
            for e in active:
                if e["field_18"] == current and e["index"] not in visited:
                    current = e["index"]
                    chain.append(current)
                    visited.add(current)
                    found = True
                    break
            if not found:
                break
        chains.append(chain)

    return chains, active


# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Payload record parsing
# ═══════════════════════════════════════════════════════════════════════════════

def parse_payload_blocks(data: bytes) -> List[dict]:
    """Parse the payload into blocks separated by FF FF 00 00 delimiters."""
    blocks = []
    # Find all delimiter positions
    delim_positions = []
    for i in range(len(data) - 3):
        if data[i:i+4] == PAYLOAD_DELIMITER:
            delim_positions.append(i)

    for idx, pos in enumerate(delim_positions):
        # Data starts after delimiter (4 bytes) + count (4 bytes)
        block_start = pos + 4
        if block_start + 4 > len(data):
            break
        count = struct.unpack_from("<I", data, block_start)[0]
        record_start = block_start + 4

        records = []
        for r in range(count):
            r_off = record_start + r * 8
            if r_off + 8 > len(data):
                break
            rec = struct.unpack_from("<8B", data, r_off)
            records.append({
                "type": rec[0],
                "f01": rec[1],
                "flags": rec[2],
                "f03": rec[3],
                "value_lo": rec[4],
                "value_hi": rec[5],
                "f06": rec[6],
                "f07": rec[7],
                "value_u16": struct.unpack_from("<H", data, r_off + 4)[0],
                "value_u32": struct.unpack_from("<I", data, r_off + 4)[0],
            })

        # Also grab the "trailer" bytes after the records
        trailer_off = record_start + count * 8
        next_delim = delim_positions[idx + 1] if idx + 1 < len(delim_positions) else len(data)
        trailer = data[trailer_off:next_delim]

        blocks.append({
            "offset": pos,
            "count": count,
            "records": records,
            "trailer": trailer,
        })

    return blocks


def parse_payload_as_8byte_records(data: bytes) -> List[dict]:
    """Parse the entire payload as sequential 8-byte records (no delimiter assumption)."""
    records = []
    for i in range(0, len(data) - 7, 8):
        rec = struct.unpack_from("<8B", data, i)
        records.append({
            "offset": i,
            "type": rec[0],
            "f01": rec[1],
            "flags": rec[2],
            "f03": rec[3],
            "value_lo": rec[4],
            "value_hi": rec[5],
            "f06": rec[6],
            "f07": rec[7],
            "value_u16": struct.unpack_from("<H", data, i + 4)[0],
            "value_u32": struct.unpack_from("<I", data, i + 4)[0],
        })
    return records


# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Cross-reference
# ═══════════════════════════════════════════════════════════════════════════════

def crossref_values_with_cues(records, sdx_cues):
    """Check if any u16/u32 values in the records map to known .sdx cue indices."""
    active_cue_indices = {c["index"] for c in sdx_cues if c["track_count"] > 0}
    all_cue_kinds = Counter(c["kind"] for c in sdx_cues if c["track_count"] > 0)

    # Check each unique value from records
    value_counts = Counter()
    for rec in records:
        value_counts[rec["value_u16"]] += 1

    matches = []
    for val, count in value_counts.most_common():
        if val in active_cue_indices:
            matches.append((val, count, "cue_index"))
        # Also check if value is a plausible cue index (0-255)
        if val <= 255 and val in active_cue_indices:
            matches.append((val, count, "cue_index_low"))

    return matches, active_cue_indices, all_cue_kinds


# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Type analysis
# ═══════════════════════════════════════════════════════════════════════════════

def analyze_record_types(records):
    """Analyze each record type and its typical values."""
    type_groups = defaultdict(list)
    for rec in records:
        type_groups[rec["type"]].append(rec)

    analysis = {}
    for t, recs in sorted(type_groups.items()):
        vals = [r["value_u16"] for r in recs]
        flags = [r["flags"] for r in recs]
        f03s = [r["f03"] for r in recs]
        analysis[t] = {
            "count": len(recs),
            "unique_values": len(set(vals)),
            "common_values": Counter(vals).most_common(10),
            "flags_values": Counter(flags).most_common(5),
            "f03_values": Counter(f03s).most_common(5),
            "min_value": min(vals),
            "max_value": max(vals),
        }
    return analysis


# ═══════════════════════════════════════════════════════════════════════════════
# Main
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/crossref_sar_sdx.py <game_root>")
        sys.exit(1)

    game_root = sys.argv[1]
    sar_dir = os.path.join(game_root, "assets", "sar", "us")
    stage_dir = os.path.join(game_root, "us", "stage")

    if not os.path.isdir(sar_dir):
        print(f"ERROR: SAR directory not found: {sar_dir}")
        sys.exit(1)

    # ═══ Load SAR files ═══
    gbs_files = sorted(f for f in os.listdir(sar_dir)
                       if f.startswith("gbs_stage_") and f.endswith(".sar"))
    print(f"Found {len(gbs_files)} gbs_stage_*.sar files")

    sars = {}
    for fname in gbs_files:
        path = os.path.join(sar_dir, fname)
        try:
            raw, magic, ec, ds, entries, payload = parse_sar(path)
            sars[fname] = {
                "raw": raw, "magic": magic, "entry_count": ec,
                "data_size": ds, "entries": entries, "payload": payload,
            }
        except Exception as e:
            print(f"  ERROR parsing {fname}: {e}")

    # ═══ Load .sdx cue tables ═══
    sdx_cues = {}
    if os.path.isdir(stage_dir):
        for stage_name in os.listdir(stage_dir):
            stage_path = os.path.join(stage_dir, stage_name)
            if not os.path.isdir(stage_path):
                continue
            for f in os.listdir(stage_path):
                if f.endswith(".sdx"):
                    sdx_path = os.path.join(stage_path, f)
                    try:
                        cues = parse_sdx_cues(sdx_path)
                        active = [c for c in cues if c["track_count"] > 0]
                        if active:
                            sdx_cues[f"{stage_name}/{f}"] = cues
                    except Exception as e:
                        pass
    print(f"Loaded cue tables from {len(sdx_cues)} .sdx files")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 1: FIELD_18 CHAIN ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 1: FIELD_18 LINKED-LIST CHAIN ANALYSIS")
    print("=" * 70)

    for fname, sar in sorted(sars.items()):
        chains, active = trace_field_18_chain(sar["entries"])
        print(f"\n  {fname}:")
        print(f"    Active entries: {len(active)}")
        print(f"    Chain count: {len(chains)}")
        for ci, chain in enumerate(chains):
            # Walk each chain and show sizes + hashes
            entry_by_idx = {e["index"]: e for e in active}
            sizes = []
            for idx in chain:
                e = entry_by_idx.get(idx)
                if e:
                    sizes.append((idx, e["hash"], e["size"], e["field_18"]))
            print(f"    Chain {ci}: length={len(chain)}")
            if len(chain) <= 30:
                for idx, h, sz, f18 in sizes:
                    print(f"      [{idx:3d}] hash=0x{h:08X}  size={sz:10d}  next={f18}")
            else:
                for idx, h, sz, f18 in sizes[:10]:
                    print(f"      [{idx:3d}] hash=0x{h:08X}  size={sz:10d}  next={f18}")
                print(f"      ... ({len(chain) - 10} more)")
                for idx, h, sz, f18 in sizes[-5:]:
                    print(f"      [{idx:3d}] hash=0x{h:08X}  size={sz:10d}  next={f18}")

        # Just show first SAR's chain details
        if len(sars) > 1:
            break

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 2: PAYLOAD BLOCK STRUCTURE
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 2: PAYLOAD BLOCK STRUCTURE (gbs_stage_sp03a.sar)")
    print("=" * 70)

    # Use the first stage SAR with "sp03a" in name, or just the first one
    target = None
    for fname, sar in sars.items():
        if "sp03a" in fname:
            target = (fname, sar)
            break
    if target is None:
        target = next(iter(sars.items()))
    fname, sar = target

    blocks = parse_payload_blocks(sar["payload"])
    print(f"\n  {fname}: {len(blocks)} blocks found via FF FF 00 00 delimiters")

    # Block size distribution
    block_sizes = Counter(b["count"] for b in blocks)
    print(f"\n  Block record-count distribution:")
    for count, freq in sorted(block_sizes.items()):
        print(f"    {count} records: {freq} blocks")

    # Record type distribution across all blocks
    all_records = []
    for b in blocks:
        all_records.extend(b["records"])
    print(f"\n  Total records across all blocks: {len(all_records)}")

    type_dist = Counter(r["type"] for r in all_records)
    print(f"\n  Record type distribution:")
    for t, freq in sorted(type_dist.items()):
        print(f"    type=0x{t:02X}: {freq} records")

    # Show first 30 blocks in detail
    print(f"\n  First 30 blocks:")
    for bi, b in enumerate(blocks[:30]):
        rec_strs = []
        for r in b["records"]:
            rec_strs.append(f"(t=0x{r['type']:02X} f=0x{r['flags']:02X} v=0x{r['value_u16']:04X})")
        trailer_hex = b["trailer"].hex() if b["trailer"] else ""
        print(f"    [{bi:3d}] @0x{b['offset']:04X}  {b['count']} records: "
              f"{' '.join(rec_strs)}  trailer=[{trailer_hex}]")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 3: RECORD TYPE ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 3: RECORD TYPE ANALYSIS")
    print("=" * 70)

    type_analysis = analyze_record_types(all_records)
    for t, info in sorted(type_analysis.items()):
        print(f"\n  Type 0x{t:02X} ({info['count']} records):")
        print(f"    Value range: 0x{info['min_value']:04X} - 0x{info['max_value']:04X}")
        print(f"    Unique values: {info['unique_values']}")
        print(f"    Common values: ", end="")
        for val, cnt in info["common_values"][:5]:
            print(f"0x{val:04X}({cnt}) ", end="")
        print()
        print(f"    Flags: ", end="")
        for fl, cnt in info["flags_values"][:5]:
            print(f"0x{fl:02X}({cnt}) ", end="")
        print()
        print(f"    f03: ", end="")
        for f, cnt in info["f03_values"][:5]:
            print(f"0x{f:02X}({cnt}) ", end="")
        print()

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 4: CROSS-REFERENCE WITH SDX CUES
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 4: CROSS-REFERENCE WITH SDX CUE TABLES")
    print("=" * 70)

    if not sdx_cues:
        print("  No .sdx cue tables loaded.")
    else:
        # Collect all active cue indices across all sdx files
        all_active_cues = set()
        all_cue_kinds = Counter()
        for sdx_name, cues in sdx_cues.items():
            for c in cues:
                if c["track_count"] > 0:
                    all_active_cues.add(c["index"])
                    all_cue_kinds[c["kind"]] += 1

        print(f"\n  Active cue indices across all .sdx: {sorted(all_active_cues)}")
        print(f"  Cue kind distribution: {dict(all_cue_kinds.most_common())}")

        # Check SAR record values against cue indices
        print(f"\n  Checking if SAR record values match cue indices...")
        matches, _, _ = crossref_values_with_cues(all_records, [])

        # Do a manual check: for each unique u16 value in records, check if it
        # is an active cue index in ANY of the .sdx files
        val_u16_counts = Counter(r["value_u16"] for r in all_records)
        print(f"\n  Unique u16 values in SAR records: {len(val_u16_counts)}")
        print(f"\n  Checking overlap with active cue indices:")
        overlap_found = False
        for val in sorted(val_u16_counts.keys()):
            if val in all_active_cues:
                print(f"    MATCH: value 0x{val:04X} ({val}) = active cue index "
                      f"({val_u16_counts[val]} records)")
                overlap_found = True
        if not overlap_found:
            print(f"    No overlap found between SAR record values and .sdx cue indices")

        # Also check if any record value maps to a cue kind
        print(f"\n  Cue kinds present: {sorted(all_cue_kinds.keys())}")
        print(f"  SAR record types: {sorted(type_dist.keys())}")

        # Try to find any numeric correspondence
        print(f"\n  SAR value ranges vs .sdx cue count:")
        print(f"    SAR min u16 value: {min(val_u16_counts.keys()):#06x}")
        print(f"    SAR max u16 value: {max(val_u16_counts.keys()):#06x}")
        print(f"    .sdx active cue count: {len(all_active_cues)}")
        print(f"    .sdx max cue index: {max(all_active_cues) if all_active_cues else 'N/A'}")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 5: PER-ENTRY PAYLOAD ANALYSIS
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 5: PER-ENTRY PAYLOAD SIZE vs CONTENT")
    print("=" * 70)

    active_entries = [e for e in sar["entries"] if e["hash"] != 0 and e["hash"] != 0x4C]
    # Group by size
    size_groups = defaultdict(list)
    for e in active_entries:
        size_groups[e["size"]].append(e)

    print(f"\n  Size distribution of active entries in {fname}:")
    for sz, entries in sorted(size_groups.items()):
        hashes = [f"0x{e['hash']:08X}" for e in entries[:5]]
        print(f"    size={sz:6d}B: {len(entries)} entries  "
              f"idx={[e['index'] for e in entries[:8]]}"
              f"{'...' if len(entries) > 8 else ''}")

    # For each size class, show what the payload looks like
    print(f"\n  Payload content by size class:")
    for sz, entries in sorted(size_groups.items()):
        if sz == 0:
            continue
        e = entries[0]
        data = extract_entry_payload(sar["entries"], sar["payload"], e)
        if not data:
            continue
        # Parse as blocks
        blks = parse_payload_blocks(data)
        # Parse as 8-byte records
        recs = parse_payload_as_8byte_records(data)
        types = Counter(r["type"] for r in recs)

        print(f"\n    size={sz}B (example: idx={e['index']}, hash=0x{e['hash']:08X}):")
        print(f"      Blocks (via delimiter): {len(blks)}")
        print(f"      8-byte records: {len(recs)}")
        print(f"      Record types: {dict(types.most_common())}")
        if len(data) <= 64:
            print(f"      Hex: {data.hex()}")
        else:
            print(f"      Hex (first 64B): {data[:64].hex()}")

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 6: KEY INSIGHT - VALUE 0x1770 (6000)
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 6: THE 0x1770 (6000) VALUE - CONTEXT ANALYSIS")
    print("=" * 70)

    # Find all records containing 0x1770
    records_with_1770 = []
    for bi, b in enumerate(blocks):
        for ri, r in enumerate(b["records"]):
            if r["value_u16"] == 0x1770 or r["value_u32"] == 0x1770:
                records_with_1770.append((bi, ri, r))

    print(f"\n  Records containing 0x1770: {len(records_with_1770)}")
    print(f"\n  Context: which record types use 0x1770?")
    type_1770 = Counter(r["type"] for _, _, r in records_with_1770)
    for t, cnt in sorted(type_1770.items()):
        print(f"    type=0x{t:02X}: {cnt} times")

    # Show surrounding records for first few 0x1770 instances
    print(f"\n  Context around first 10 0x1770 records:")
    shown = 0
    for bi, ri, r in records_with_1770:
        if shown >= 10:
            break
        b = blocks[bi]
        ctx_before = b["records"][max(0, ri-2):ri]
        ctx_after = b["records"][ri+1:min(len(b["records"]), ri+3)]
        before_str = " ".join(f"(t={x['type']:02X} v={x['value_u16']:04X})" for x in ctx_before)
        after_str = " ".join(f"(t={x['type']:02X} v={x['value_u16']:04X})" for x in ctx_after)
        print(f"    block[{bi}] rec[{ri}]: ...{before_str} **(t=0x{r['type']:02X} v=0x{r['value_u16']:04X})** {after_str}...")
        shown += 1

    # ═════════════════════════════════════════════════════════════════════════
    # SECTION 7: CROSS-SAR ENTRY COMPARISON
    # ═════════════════════════════════════════════════════════════════════════
    print(f"\n{'='*70}")
    print("SECTION 7: CROSS-SAR PAYLOAD DIFF (first 2 stage files)")
    print("=" * 70)

    stage_list = sorted(sars.keys())
    if len(stage_list) >= 2:
        sar_a = sars[stage_list[0]]
        sar_b = sars[stage_list[1]]

        # Compare active entry hashes
        active_a = {e["index"]: e for e in sar_a["entries"] if e["hash"] != 0 and e["hash"] != 0x4C}
        active_b = {e["index"]: e for e in sar_b["entries"] if e["hash"] != 0 and e["hash"] != 0x4C}

        common_idx = set(active_a.keys()) & set(active_b.keys())
        same_hash = sum(1 for i in common_idx if active_a[i]["hash"] == active_b[i]["hash"])
        same_payload = 0
        diff_payload = 0
        for i in common_idx:
            pa = extract_entry_payload(sar_a["entries"], sar_a["payload"], active_a[i])
            pb = extract_entry_payload(sar_b["entries"], sar_b["payload"], active_b[i])
            if pa == pb:
                same_payload += 1
            else:
                diff_payload += 1

        print(f"\n  {stage_list[0]} vs {stage_list[1]}:")
        print(f"    Active entries: {len(active_a)} vs {len(active_b)}")
        print(f"    Common indices: {len(common_idx)}")
        print(f"    Same hash: {same_hash}")
        print(f"    Same payload: {same_payload}")
        print(f"    Different payload: {diff_payload}")

        # Show some differing payloads
        if diff_payload > 0:
            print(f"\n    Entries with different payloads:")
            shown = 0
            for i in sorted(common_idx):
                pa = extract_entry_payload(sar_a["entries"], sar_a["payload"], active_a[i])
                pb = extract_entry_payload(sar_b["entries"], sar_b["payload"], active_b[i])
                if pa != pb and shown < 5:
                    print(f"      idx={i} hash=0x{active_a[i]['hash']:08X}:")
                    print(f"        {stage_list[0]}: {pa[:32].hex()}... ({len(pa)}B)")
                    print(f"        {stage_list[1]}: {pb[:32].hex()}... ({len(pb)}B)")
                    shown += 1


if __name__ == "__main__":
    main()
