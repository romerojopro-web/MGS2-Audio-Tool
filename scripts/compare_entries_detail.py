#!/usr/bin/env python3
"""
Deep analysis: compare entries across files to find fixed vs variable entries.
Also check the special sp03a file with entry 379.
"""
import struct
import os
from pathlib import Path
from collections import Counter, defaultdict

def read_sar_entries(filepath):
    """Read all entries from a SAR file."""
    with open(filepath, 'rb') as f:
        data = f.read()
    
    if len(data) < 64:
        return None, data
    
    magic, entry_count, data_size = struct.unpack_from('<III', data, 0)
    
    entries = []
    for i in range(min(entry_count, 500)):
        offset = 0x40 + i * 32
        if offset + 32 > len(data):
            break
        
        entry = struct.unpack_from('<IIIIIIII', data, offset)
        entries.append({
            'index': i,
            'hash': entry[0],
            'f04': entry[1],
            'offset': entry[2],
            'f0C': entry[3],
            'f10': entry[4],
            'f14': entry[5],
            'field_18': entry[6],
            'size': entry[7]
        })
    
    return entries, data

def compare_entries_across_files(sar_files):
    """Compare entries at each index across all files."""
    all_entries = {}
    
    for filepath in sar_files:
        filename = os.path.basename(filepath)
        entries, _ = read_sar_entries(filepath)
        if entries:
            all_entries[filename] = entries
    
    if not all_entries:
        return
    
    # Get list of filenames
    filenames = list(all_entries.keys())
    
    print("ENTRY COMPARISON ACROSS FILES")
    print("=" * 80)
    
    # Check entries 0-20 in detail
    print("\nEntries 0-20:")
    for i in range(21):
        print(f"\n  Index {i}:")
        for fname in filenames[:5]:  # Show first 5 files
            entry = all_entries[fname][i]
            print(f"    {fname}: hash=0x{entry['hash']:08X} offset=0x{entry['offset']:08X} size=0x{entry['size']:08X}")
    
    # Find which entries are IDENTICAL across all files
    print("\n\nENTRIES IDENTICAL ACROSS ALL FILES:")
    identical_count = 0
    different_count = 0
    
    for i in range(380):
        first_entry = None
        is_identical = True
        
        for fname in filenames:
            entry = all_entries[fname][i]
            if first_entry is None:
                first_entry = entry
            else:
                # Compare all fields
                if (entry['hash'] != first_entry['hash'] or
                    entry['offset'] != first_entry['offset'] or
                    entry['size'] != first_entry['size']):
                    is_identical = False
                    break
        
        if is_identical:
            identical_count += 1
            if i < 30 or i > 370:  # Show first and last few
                print(f"  Index {i}: hash=0x{first_entry['hash']:08X} offset=0x{first_entry['offset']:08X} size=0x{first_entry['size']:08X}")
        else:
            different_count += 1
    
    print(f"\n  Identical: {identical_count}, Different: {different_count}")

def analyze_special_sar():
    """Analyze the special sp03a SAR file in detail."""
    filepath = Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_sp03a.sar")
    
    print("\n\nSPECIAL FILE: gbs_stage_sp03a.sar")
    print("=" * 80)
    
    entries, data = read_sar_entries(filepath)
    if not entries:
        return
    
    print(f"File size: {len(data):,} bytes")
    print(f"Entry count: {len(entries)}")
    
    # Show entry 379 in detail
    entry_379 = entries[379]
    print(f"\nEntry 379 (last entry):")
    print(f"  hash: 0x{entry_379['hash']:08X}")
    print(f"  f04: 0x{entry_379['f04']:08X}")
    print(f"  offset: 0x{entry_379['offset']:08X}")
    print(f"  f0C: 0x{entry_379['f0C']:08X}")
    print(f"  f10: 0x{entry_379['f10']:08X}")
    print(f"  f14: 0x{entry_379['f14']:08X}")
    print(f"  field_18: 0x{entry_379['field_18']:08X}")
    print(f"  size: 0x{entry_379['size']:08X} ({entry_379['size']:,} bytes)")
    
    # Compare entry 379 with other files
    other_files = [
        Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_a02a.sar"),
        Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_a12a.sar")
    ]
    
    print("\nEntry 379 comparison:")
    for other_file in other_files:
        other_entries, _ = read_sar_entries(other_file)
        if other_entries:
            other_379 = other_entries[379]
            print(f"  {other_file.name}: hash=0x{other_379['hash']:08X} size=0x{other_379['size']:08X}")
    
    # Show entries 375-379 to see the tail
    print("\nEntries 375-379 (tail of table):")
    for i in range(375, 380):
        entry = entries[i]
        print(f"  {i}: hash=0x{entry['hash']:08X} offset=0x{entry['offset']:08X} size=0x{entry['size']:08X}")

def analyze_field_18_pattern():
    """Analyze the field_18 values to understand their structure."""
    filepath = Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_a02a.sar")
    
    print("\n\nFIELD_18 ANALYSIS (from gbs_stage_a02a.sar)")
    print("=" * 80)
    
    entries, _ = read_sar_entries(filepath)
    if not entries:
        return
    
    # Collect all non-zero field_18 values
    field_18_values = []
    for entry in entries:
        if entry['field_18'] != 0:
            field_18_values.append(entry['field_18'])
    
    print(f"Non-zero field_18 values: {len(field_18_values)}")
    print(f"Unique values: {len(set(field_18_values))}")
    
    # Show some examples
    print("\nSample field_18 values:")
    for val in sorted(set(field_18_values))[:20]:
        # Break down into bytes
        b0 = val & 0xFF
        b1 = (val >> 8) & 0xFF
        b2 = (val >> 16) & 0xFF
        b3 = (val >> 24) & 0xFF
        print(f"  0x{val:08X}: bytes=[0x{b0:02X}, 0x{b1:02X}, 0x{b2:02X}, 0x{b3:02X}]")
    
    # Check if field_18 relates to offset or size
    print("\nCorrelation with offset/size:")
    for entry in entries[:10]:
        if entry['field_18'] != 0:
            print(f"  Index {entry['index']}: field_18=0x{entry['field_18']:08X}, offset=0x{entry['offset']:08X}, size=0x{entry['size']:08X}")

def main():
    # Find all SAR files
    sar_dir = Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us")
    sar_files = sorted(sar_dir.glob("gbs_stage_*.sar"))
    
    # Compare entries across first few files
    compare_entries_across_files(sar_files[:5])
    
    # Analyze special sp03a file
    analyze_special_sar()
    
    # Analyze field_18 pattern
    analyze_field_18_pattern()

if __name__ == "__main__":
    main()