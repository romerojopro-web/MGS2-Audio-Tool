#!/usr/bin/env python3
"""
Compare entry structures across multiple gbs_stage_*.sar files
to find common patterns and understand the format better.
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
        return None, None
    
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
    
    return entries, data_size

def analyze_sar_file(filepath):
    """Analyze a single SAR file and return statistics."""
    entries, payload_size = read_sar_entries(filepath)
    if entries is None:
        return None
    
    stats = {
        'filename': os.path.basename(filepath),
        'file_size': os.path.getsize(filepath),
        'entry_count': len(entries),
        'payload_size': payload_size,
        'active_entries': 0,
        'hashes': Counter(),
        'offsets': [],
        'sizes': [],
        'field_18_values': Counter(),
        'type_bytes': Counter(),
        'special_entries': []
    }
    
    for entry in entries:
        if entry['hash'] != 0:
            stats['active_entries'] += 1
        
        stats['hashes'][entry['hash']] += 1
        stats['offsets'].append(entry['offset'])
        stats['sizes'].append(entry['size'])
        stats['field_18_values'][entry['field_18']] += 1
        
        # Extract type byte from field_18
        type_byte = (entry['field_18'] >> 8) & 0xFF
        stats['type_bytes'][type_byte] += 1
        
        # Track special entries (non-zero hash or large size)
        if entry['hash'] != 0 or entry['size'] > 0x100000:
            stats['special_entries'].append(entry)
    
    return stats

def compare_sar_files(sar_files):
    """Compare multiple SAR files to find common patterns."""
    all_stats = []
    
    for filepath in sar_files:
        stats = analyze_sar_file(filepath)
        if stats:
            all_stats.append(stats)
            print(f"\n{'='*60}")
            print(f"FILE: {stats['filename']}")
            print(f"{'='*60}")
            print(f"  File size: {stats['file_size']:,} bytes")
            print(f"  Entry count: {stats['entry_count']}")
            print(f"  Payload size: {stats['payload_size']:,} bytes")
            print(f"  Active entries: {stats['active_entries']}")
            print(f"  Unique hashes: {len(stats['hashes'])}")
            
            # Show most common hashes
            print(f"\n  Most common hashes:")
            for hash_val, count in stats['hashes'].most_common(5):
                print(f"    0x{hash_val:08X}: {count}")
            
            # Show type bytes
            print(f"\n  Type bytes (from field_18):")
            for type_byte, count in stats['type_bytes'].most_common(10):
                print(f"    0x{type_byte:02X}: {count}")
            
            # Show special entries
            if stats['special_entries']:
                print(f"\n  Special entries (non-zero hash or large size):")
                for entry in stats['special_entries'][:5]:
                    print(f"    Index {entry['index']}: hash=0x{entry['hash']:08X}, offset=0x{entry['offset']:08X}, size=0x{entry['size']:08X}")
    
    return all_stats

def find_common_patterns(all_stats):
    """Find common patterns across all SAR files."""
    print(f"\n{'='*60}")
    print("COMMON PATTERNS ACROSS ALL FILES")
    print(f"{'='*60}")
    
    # Check if all files have similar entry counts
    entry_counts = [s['entry_count'] for s in all_stats]
    print(f"\n  Entry counts: {entry_counts}")
    print(f"  Min: {min(entry_counts)}, Max: {max(entry_counts)}, Average: {sum(entry_counts)/len(entry_counts):.1f}")
    
    # Check if all files have the same special entry pattern
    special_entry_patterns = []
    for stats in all_stats:
        pattern = []
        for entry in stats['special_entries'][:3]:  # Top 3 special entries
            pattern.append(f"hash=0x{entry['hash']:08X}")
        special_entry_patterns.append(tuple(pattern))
    
    print(f"\n  Special entry patterns:")
    for pattern, count in Counter(special_entry_patterns).most_common():
        print(f"    {pattern}: {count} files")
    
    # Check if all files have similar type byte distributions
    type_byte_sets = []
    for stats in all_stats:
        type_byte_sets.append(frozenset(stats['type_bytes'].keys()))
    
    common_type_bytes = set.intersection(*[set(s) for s in type_byte_sets]) if type_byte_sets else set()
    print(f"\n  Common type bytes across all files: {[f'0x{b:02X}' for b in sorted(common_type_bytes)]}")

def analyze_payload_delimiters(sar_files):
    """Analyze payload delimiters across files."""
    print(f"\n{'='*60}")
    print("PAYLOAD DELIMITER ANALYSIS")
    print(f"{'='*60}")
    
    delimiter_patterns = []
    
    for filepath in sar_files:
        with open(filepath, 'rb') as f:
            data = f.read()
        
        # Find payload start (after entry table)
        entries, payload_size = read_sar_entries(filepath)
        if entries is None:
            continue
        
        payload_start = 0x40 + len(entries) * 32
        payload = data[payload_start:payload_start + payload_size]
        
        # Find FF FF 00 00 delimiters
        delimiter_positions = []
        i = 0
        while i < len(payload) - 3:
            if payload[i:i+4] == b'\xff\xff\x00\x00':
                delimiter_positions.append(i)
                i += 4
            else:
                i += 1
        
        delimiter_patterns.append({
            'filename': os.path.basename(filepath),
            'delimiter_count': len(delimiter_positions),
            'first_few': delimiter_positions[:5]
        })
        
        print(f"\n  {os.path.basename(filepath)}:")
        print(f"    Delimiter count: {len(delimiter_positions)}")
        print(f"    First few positions: {[f'0x{pos:04X}' for pos in delimiter_positions[:5]]}")

def main():
    # Find all SAR files
    sar_dir = Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us")
    sar_files = sorted(sar_dir.glob("gbs_stage_*.sar"))
    
    print(f"Found {len(sar_files)} gbs_stage_*.sar files")
    
    # Analyze first few files
    all_stats = compare_sar_files(sar_files[:5])
    
    # Find common patterns
    find_common_patterns(all_stats)
    
    # Analyze payload delimiters
    analyze_payload_delimiters(sar_files[:5])

if __name__ == "__main__":
    main()