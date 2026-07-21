#!/usr/bin/env python3
"""Tests for formats/xwma.py — stock Konami XWMA `.sdt` handling.

The default run is pure Python (no ffmpeg, no game data): it exercises the
container de-interleaving and the AMWX→RIFF conversion on synthetic data.
The full decode of a real file is gated behind ``--realdata`` and needs ffmpeg.
"""

import os
import struct
import wave

import pytest

from mgs2_audio.formats import xwma
from mgs2_audio import ffmpeg as ffmpeg_bridge

MC_INSTALL = r"C:\Games\Steam\steamapps\common\MGS2"


# ─────────────────────────────────────────────────────────────────────────────
# Synthetic builders
# ─────────────────────────────────────────────────────────────────────────────

def build_amwx(data, channels=1, rate=44100, block_align=30, seek=None):
    """Build a minimal Konami AMWX stream (magic at offset 0)."""
    seek = seek or [len(data)]
    hdr = bytearray(b"AMWX")
    hdr += struct.pack("<I", 0x0161)          # 0x04 codec
    hdr += struct.pack("<I", channels)        # 0x08
    hdr += struct.pack("<I", rate)            # 0x0C
    hdr += struct.pack("<I", len(data))       # 0x10 data_size
    hdr += struct.pack("<I", 6000)            # 0x14 avg
    hdr += struct.pack("<I", block_align)     # 0x18 block_align
    hdr += b"\x00" * 4                         # 0x1C pad -> 0x20
    # WAVEFORMATEX at 0x20 (its rate field at 0x24 triggers seek detection)
    hdr += struct.pack("<HHIIHH", 0x0161, channels, rate, 6000, block_align, 16)
    hdr += struct.pack("<H", 0)               # 0x30 cbSize
    hdr += struct.pack("<H", len(seek))       # 0x32 seek count
    hdr += b"\x00\x00"                         # 0x34 gap -> entries at 0x36
    for e in seek:                             # 0x36 entries
        hdr += struct.pack("<I", e)
    # pad up to a 16-byte boundary, then store data padded per block to 16
    while len(hdr) % 0x10 != 0:
        hdr += b"\x00"
    body = bytearray()
    off = 0
    while off < len(data):
        chunk = data[off:off + block_align]
        body += chunk
        off += block_align
        while len(body) % 0x10 != 0:
            body += b"\xAA"                    # padding the extractor must strip
    return bytes(hdr) + bytes(body)


def build_muxed_sdt(streams):
    """Build a multiplexed .sdt. `streams` = list of (sid, [chunk, chunk...])."""
    out = bytearray()
    for sid, _ in streams:
        rec = bytearray(16)
        struct.pack_into("<I", rec, 0x00, xwma.MUX_REGISTER)
        struct.pack_into("<I", rec, 0x0C, sid)
        out += rec
    # interleave chunks round-robin
    queues = {sid: list(chunks) for sid, chunks in streams}
    while any(queues.values()):
        for sid, _ in streams:
            if queues[sid]:
                chunk = queues[sid].pop(0)
                hdr = bytearray(16)
                struct.pack_into("<I", hdr, 0x00, sid)
                struct.pack_into("<I", hdr, 0x04, 16 + len(chunk))
                out += hdr + chunk
    end = bytearray(16)
    struct.pack_into("<I", end, 0x00, xwma.MUX_END)
    out += end
    return bytes(out)


# ─────────────────────────────────────────────────────────────────────────────
# De-interleaving
# ─────────────────────────────────────────────────────────────────────────────

def test_demux_reassembles_interleaved_streams():
    sdt = build_muxed_sdt([
        (1, [b"AAA", b"BBB", b"CCC"]),
        (2, [b"xxxx", b"yyyy"]),
    ])
    streams = xwma.demux_streams(sdt)
    assert streams[1] == b"AAABBBCCC"
    assert streams[2] == b"xxxxyyyy"


def test_find_amwx_stream_picks_the_audio():
    amwx = build_amwx(b"\x01\x02\x03\x04" * 8)
    sdt = build_muxed_sdt([(2, [b"subtitle-data"]),
                           (0x40001, [amwx[:20], amwx[20:]])])
    assert xwma.is_xwma_sdt(sdt)
    assert xwma.find_amwx_stream(sdt) == amwx


def test_non_xwma_sdt_not_detected():
    sdt = build_muxed_sdt([(1, [b"no audio magic here"])])
    assert not xwma.is_xwma_sdt(sdt)
    assert xwma.find_amwx_stream(sdt) is None


# ─────────────────────────────────────────────────────────────────────────────
# AMWX parsing + RIFF assembly
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_amwx_strips_alignment_padding():
    data = bytes(range(0, 90))            # 90 bytes, block_align 30 -> 3 blocks
    amwx = build_amwx(data, block_align=30)
    clip = xwma.parse_amwx(amwx)
    assert clip.data == data              # padding (0xAA) stripped, exact recovery
    assert clip.channels == 1
    assert clip.sample_rate == 44100
    assert clip.codec == 0x0161


def test_parse_amwx_reads_seek_table():
    clip = xwma.parse_amwx(build_amwx(b"\x00" * 60, seek=[100, 200, 300]))
    assert clip.seek_table == [100, 200, 300]


def test_to_riff_xwma_structure():
    clip = xwma.parse_amwx(build_amwx(b"\x11\x22\x33\x44" * 10, seek=[500, 1000]))
    riff = xwma.to_riff_xwma(clip)
    assert riff[:4] == b"RIFF"
    assert riff[8:12] == b"XWMA"
    assert b"fmt " in riff and b"dpds" in riff and b"data" in riff
    # fmt chunk is exactly 16 bytes of data (no cbSize) — what ffmpeg expects
    i = riff.index(b"fmt ")
    assert struct.unpack_from("<I", riff, i + 4)[0] == 16
    # data chunk holds the recovered WMA bytes
    j = riff.index(b"data")
    size = struct.unpack_from("<I", riff, j + 4)[0]
    assert riff[j + 8:j + 8 + size] == clip.data


def test_sdt_to_riff_xwma_end_to_end_synthetic():
    amwx = build_amwx(b"\xDE\xAD\xBE\xEF" * 16, seek=[256, 512])
    sdt = build_muxed_sdt([(0x40001, [amwx])])
    riff = xwma.sdt_to_riff_xwma(sdt)
    assert riff[:4] == b"RIFF" and riff[8:12] == b"XWMA"


# ─────────────────────────────────────────────────────────────────────────────
# Real decode (opt-in: --realdata, needs ffmpeg + the install)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture
def _realdata(request):
    if not request.config.getoption("--realdata"):
        pytest.skip("real-data test — pass --realdata to run")
    if not ffmpeg_bridge.available():
        pytest.skip("ffmpeg not found on PATH")
    if not os.path.isdir(MC_INSTALL):
        pytest.skip("Master Collection install not found")


def test_real_vox_decodes_full_length(_realdata, tmp_path):
    p = os.path.join(MC_INSTALL, "us", "vox", "vc000101.sdt.vortex_backup")
    if not os.path.isfile(p):
        pytest.skip("test vox file not present")
    raw = open(p, "rb").read()
    assert xwma.is_xwma_sdt(raw)
    clip = xwma.parse_amwx(xwma.find_amwx_stream(raw))
    riff = xwma.sdt_to_riff_xwma(raw)
    out = str(tmp_path / "out.wav")
    ffmpeg_bridge.decode_to_wav(riff, out)
    with wave.open(out, "rb") as w:
        dur = w.getnframes() / w.getframerate()
        assert w.getnchannels() == clip.channels
    # within a frame of the seek-table duration = fully decoded, not truncated
    assert dur == pytest.approx(clip.duration_seconds, abs=0.1)
