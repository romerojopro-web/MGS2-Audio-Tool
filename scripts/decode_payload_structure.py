#!/usr/bin/env python3
"""
Decode the payload structure - understand the FF FF 00 00 delimiters and record format.
"""
import struct
import os
from pathlib import Path

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

def decode_payload_block(data, offset, max_size):
    """Decode a payload block starting at offset."""
    result = {
        'offset': offset,
        'raw_bytes': [],
        'records': [],
        'trailer': None
    }
    
    # Read raw bytes
    block_data = data[offset:offset + max_size]
    result['raw_bytes'] = list(block_data)
    
    # Look for FF FF 00 00 delimiter
    delimiter_pos = None
    for i in range(len(block_data) - 3):
        if block_data[i:i+4] == b'\xff\xff\x00\x00':
            delimiter_pos = i
            break
    
    if delimiter_pos is not None:
        # Data before delimiter is the record data
        record_data = block_data[:delimiter_pos]
        
        # Parse records (8 bytes each)
        num_records = len(record_data) // 8
        for i in range(num_records):
            record_offset = i * 8
            if record_offset + 8 <= len(record_data):
                record = struct.unpack_from('<II', record_data, record_offset)
                result['records'].append({
                    'word0': record[0],
                    'word1': record[1]
                })
        
        # Trailer is after delimiter
        trailer_data = block_data[delimiter_pos + 4:]
        if len(trailer_data) >= 4:
            result['trailer'] = struct.unpack_from('<I', trailer_data, 0)[0]
    
    return result

def analyze_payload_structure(filepath):
    """Analyze the full payload structure."""
    entries, data = read_sar_entries(filepath)
    if not entries:
        return
    
    filename = os.path.basename(filepath)
    print(f"PAYLOAD STRUCTURE ANALYSIS: {filename}")
    print("=" * 80)
    
    # Calculate payload start
    payload_start = 0x40 + len(entries) * 32
    payload_size = len(data) - payload_start
    payload = data[payload_start:]
    
    print(f"Payload starts at file offset: 0x{payload_start:04X}")
    print(f"Payload size: {payload_size} bytes")
    
    # Find all FF FF 00 00 delimiters
    delimiters = []
    i = 0
    while i < len(payload) - 3:
        if payload[i:i+4] == b'\xff\xff\x00\x00':
            delimiters.append(i)
            i += 4
        else:
            i += 1
    
    print(f"Number of delimiters: {len(delimiters)}")
    
    # Analyze first few blocks
    print("\nFirst 5 blocks:")
    for block_num in range(min(5, len(delimiters))):
        if block_num == 0:
            block_start = 0
        else:
            block_start = delimiters[block_num - 1] + 4
        
        block_end = delimiters[block_num]
        block_size = block_end - block_start
        
        print(f"\n  Block {block_num} (offset 0x{block_start:04X} - 0x{block_end:04X}, {block_size} bytes):")
        
        # Read block data
        block_data = payload[block_start:block_end]
        
        # Parse records (8 bytes each)
        num_records = len(block_data) // 8
        print(f"    Records: {num_records}")
        
        for i in range(min(num_records, 3)):
            record_offset = i * 8
            if record_offset + 8 <= len(block_data):
                record = struct.unpack_from('<II', block_data, record_offset)
                print(f"      Record {i}: 0x{record[0]:08X} 0x{record[1]:08X}")
        
        # Show trailer
        trailer_pos = block_end + 4
        if trailer_pos + 4 <= len(payload):
            trailer = struct.unpack_from('<I', payload, trailer_pos)[0]
            print(f"    Trailer: 0x{trailer:08X}")
    
    # Analyze entry 0's payload in detail
    print("\n\nENTRY 0 PAYLOAD DETAIL:")
    entry0 = entries[0]
    entry0_payload_start = payload_start + entry0['offset']
    entry0_payload = data[entry0_payload_start:entry0_payload_start + entry0['field_18']]
    
    print(f"  Offset: 0x{entry0['offset']:04X}")
    print(f"  Size (field_18): 0x{entry0['field_18']:04X} ({entry0['field_18']} bytes)")
    print(f"  Raw bytes: {' '.join(f'{b:02X}' for b in entry0_payload)}")
    
    # Decode this block
    block = decode_payload_block(payload, entry0['offset'], entry0['field_18'])
    print(f"  Delimiter position: {block['offset'] + len(block['raw_bytes']) if block['raw_bytes'] else 'N/A'}")
    print(f"  Records: {len(block['records'])}")
    for i, record in enumerate(block['records']):
        print(f"    Record {i}: 0x{record['word0']:08X} 0x{record['word1']:08X}")
    if block['trailer'] is not None:
        print(f"  Trailer: 0x{block['trailer']:08X}")

def main():
    # Analyze a few files
    sar_files = [
        Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_a02a.sar"),
        Path(r"C:\Games\Steam\steamapps\common\MGS2\assets\sar\us\gbs_stage_sp03a.sar")
    ]
    
    for filepath in sar_files:
        if filepath.exists():
            analyze_payload_structure(filepath)
            print("\n" + "=" * 80 + "\n")

if __name__ == "__main__":
    main()