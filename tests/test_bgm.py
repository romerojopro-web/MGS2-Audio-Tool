"""Tests for the bgm.dat archive and its auto-detection.

BGM is a flat concatenation of MS-ADPCM entries, each preceded by a 0x800-byte
big-endian header.  The codec is MS-ADPCM (Microsoft ADPCM), block size 0x800.
"""

import math
import struct

import pytest

from conftest import (
    build_bgm, build_bgm_entry, speech_like, _encode_stereo_to_msadpcm,
)

from mgs2_audio.codec import msadpcm
from mgs2_audio.codec.wav import save_wav
from mgs2_audio.formats import bgm as bgm_fmt
from mgs2_audio.formats.container import RavenContainer
from mgs2_audio.formats.detect import detect, detect_path, Format


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def test_parse_finds_entries(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    assert bgm.entry_count == 2


def test_parse_multi_entries(multi_bgm):
    bgm = bgm_fmt.parse_bgm(multi_bgm)
    assert bgm.entry_count == 3


def test_entry_metadata(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    e = bgm.entries[0]
    assert e.sample_rate == 44100
    assert e.channels == 2
    assert e.index == 0
    assert e.duration_seconds > 0


def test_entry_metadata_second(multi_bgm):
    bgm = bgm_fmt.parse_bgm(multi_bgm)
    second = bgm.entries[1]
    assert second.sample_rate == 44100
    assert second.channels == 2
    assert second.index == 1


def test_loop_fields(multi_bgm):
    bgm = bgm_fmt.parse_bgm(multi_bgm)
    e = bgm.entries[2]
    assert e.loop_start == 100
    assert e.loop_end == 500


def test_actual_data_size_matches_gap(stereo_bgm):
    """actual_data_size should equal the distance from data to next entry."""
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    for e in bgm.entries:
        expected = e.next_entry_offset - e.data_offset
        assert e.actual_data_size == expected


def test_data_offset_is_header_plus_0x800(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    for e in bgm.entries:
        assert e.data_offset == e.file_offset + 0x800


def test_getitem_by_index(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    assert bgm[0] is bgm.entries[0]
    assert bgm[1] is bgm.entries[1]


def test_empty_file(tmp_path):
    path = tmp_path / "empty.dat"
    path.write_bytes(b"\x00" * 0x100)
    bgm = bgm_fmt.parse_bgm(str(path))
    assert bgm.entry_count == 0


# ─────────────────────────────────────────────────────────────────────────────
# Decoding
# ─────────────────────────────────────────────────────────────────────────────

def test_decode_stereo_entry(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    pcm = bgm_fmt.bgm_entry_to_pcm(bgm, bgm.entries[0])
    assert len(pcm) > 0
    assert len(pcm) % 2 == 0  # stereo must be even


def test_decode_second_entry(multi_bgm):
    bgm = bgm_fmt.parse_bgm(multi_bgm)
    pcm = bgm_fmt.bgm_entry_to_pcm(bgm, bgm.entries[1])
    assert len(pcm) > 0
    assert len(pcm) % 2 == 0


def test_decode_produces_nonzero_audio(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    pcm = bgm_fmt.bgm_entry_to_pcm(bgm, bgm.entries[0])
    assert max(abs(s) for s in pcm) > 0


def test_decode_wav_round_trip(stereo_bgm, tmp_path):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    out = tmp_path / "test.wav"
    n = bgm_fmt.bgm_to_wav(bgm, 0, str(out))
    assert out.exists()
    assert n > 0


def test_decode_all_entries(multi_bgm):
    bgm = bgm_fmt.parse_bgm(multi_bgm)
    for entry in bgm.entries:
        pcm = bgm_fmt.bgm_entry_to_pcm(bgm, entry)
        assert len(pcm) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Detection
# ─────────────────────────────────────────────────────────────────────────────

def test_detect_bgm(stereo_bgm):
    with open(stereo_bgm, "rb") as f:
        raw = f.read()
    assert detect(raw) is Format.BGM


def test_detect_path_bgm(stereo_bgm):
    assert detect_path(stereo_bgm) is Format.BGM


def test_detect_empty_returns_none(tmp_path):
    path = tmp_path / "empty.dat"
    path.write_bytes(b"\x00" * 0x100)
    with open(str(path), "rb") as f:
        raw = f.read(0x10000)
    assert detect(raw) is None


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def test_describe(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    text = bgm_fmt.describe(bgm)
    assert "bgm.dat" in text
    assert "2" in text  # 2 entries


def test_describe_entry(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    text = bgm_fmt.describe_entry(bgm.entries[0])
    assert "44100" in text
    assert "stereo" in text


def test_metadata(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    md = bgm_fmt.metadata(bgm)
    assert md["entries"] == 2
    assert len(md["details"]) == 2
    assert md["details"][0]["sample_rate"] == 44100


# ─────────────────────────────────────────────────────────────────────────────
# Container integration
# ─────────────────────────────────────────────────────────────────────────────

def test_container_bgm(stereo_bgm):
    c = RavenContainer.from_path(stereo_bgm)
    assert c.format is Format.BGM
    assert c.entry_count == 2


def test_container_decode_pcm(stereo_bgm):
    c = RavenContainer.from_path(stereo_bgm)
    pcm = c.decode_pcm(0)
    assert len(pcm) > 0
    assert max(abs(s) for s in pcm) > 0


def test_container_describe(stereo_bgm):
    c = RavenContainer.from_path(stereo_bgm)
    text = c.describe()
    assert "bgm.dat" in text


def test_container_metadata(stereo_bgm):
    c = RavenContainer.from_path(stereo_bgm)
    md = c.entry_metadata(0)
    assert md["sample_rate"] == 44100
    assert md["channels"] == 2
    assert "duration" in md
    assert md["duration"] > 0


def test_container_metadata_oob(stereo_bgm):
    c = RavenContainer.from_path(stereo_bgm)
    md = c.entry_metadata(999)
    assert md == {"index": 999}


# ─────────────────────────────────────────────────────────────────────────────
# MS-ADPCM codec integration
# ─────────────────────────────────────────────────────────────────────────────

def test_samples_per_block():
    # stereo 0x800 block
    spf = msadpcm.samples_per_block(0x800, 2)
    assert spf == (0x800 - 14) * 2 // 2 + 2


def test_bytes_to_samples_matches_decode(stereo_bgm):
    bgm = bgm_fmt.parse_bgm(stereo_bgm)
    e = bgm.entries[0]
    estimated_per_ch = msadpcm.bytes_to_samples(
        e.actual_data_size, msadpcm.DEFAULT_BLOCK_SIZE, e.channels)
    pcm = bgm_fmt.bgm_entry_to_pcm(bgm, e)
    # bytes_to_samples returns per-channel count; decode returns interleaved
    estimated_interleaved = estimated_per_ch * e.channels
    # Allow 1 block of slack (remainder handling)
    assert abs(len(pcm) - estimated_interleaved) < msadpcm.samples_per_block(
        msadpcm.DEFAULT_BLOCK_SIZE, e.channels) * e.channels


def test_default_block_size():
    assert msadpcm.DEFAULT_BLOCK_SIZE == 0x800


# ─────────────────────────────────────────────────────────────────────────────
# "Quad" (4-channel) entries: two block-interleaved stereo pairs
# ─────────────────────────────────────────────────────────────────────────────

def _alternate_blocks(front_data, rear_data, block_size):
    """Two stereo MS-ADPCM streams, alternated one 0x800 block at a time —
    the layout confirmed against real bgm.dat quad entries (docs/AUDIT.md)."""
    n_blocks = min(len(front_data), len(rear_data)) // block_size
    out = bytearray()
    for i in range(n_blocks):
        out += front_data[i * block_size:(i + 1) * block_size]
        out += rear_data[i * block_size:(i + 1) * block_size]
    return bytes(out), n_blocks


def test_quad_matches_separate_stereo_decode():
    """The whole fix: a block-alternated quad stream must decode to exactly
    what decoding the front and rear stereo streams separately would give —
    4ch bgm.dat entries are two independent stereo streams, not one
    quad-nibble-interleaved stream (docs/AUDIT.md). This pins the decode
    logic itself, independent of how "realistic" the test audio is."""
    front_l, front_r = speech_like(280, base=150), speech_like(280, base=160)
    rear_l, rear_r = speech_like(280, base=250), speech_like(280, base=260)
    front_data = _encode_stereo_to_msadpcm(front_l, front_r)
    rear_data = _encode_stereo_to_msadpcm(rear_l, rear_r)
    block_size = msadpcm.DEFAULT_BLOCK_SIZE
    quad_data, n_blocks = _alternate_blocks(front_data, rear_data, block_size)
    assert n_blocks > 0

    quad_pcm = msadpcm.decode_msadpcm(quad_data, channels=4)
    expected_front = msadpcm.decode_msadpcm(
        front_data[:n_blocks * block_size], channels=2)
    expected_rear = msadpcm.decode_msadpcm(
        rear_data[:n_blocks * block_size], channels=2)

    got_front, got_rear = [], []
    for i in range(0, len(quad_pcm), 4):
        got_front.extend(quad_pcm[i:i + 2])
        got_rear.extend(quad_pcm[i + 2:i + 4])

    assert got_front == expected_front
    assert got_rear == expected_rear
    # And they must actually differ — front and rear are not the same audio.
    assert got_front != got_rear


def test_bytes_to_samples_quad_matches_decode():
    front_l, front_r = speech_like(280, base=150), speech_like(280, base=160)
    rear_l, rear_r = speech_like(280, base=250), speech_like(280, base=260)
    front_data = _encode_stereo_to_msadpcm(front_l, front_r)
    rear_data = _encode_stereo_to_msadpcm(rear_l, rear_r)
    block_size = msadpcm.DEFAULT_BLOCK_SIZE
    quad_data, _ = _alternate_blocks(front_data, rear_data, block_size)

    estimated_per_ch = msadpcm.bytes_to_samples(len(quad_data), block_size, 4)
    pcm = msadpcm.decode_msadpcm(quad_data, channels=4)
    assert estimated_per_ch * 4 == len(pcm)


# ─────────────────────────────────────────────────────────────────────────────
# Non-44100 sample rates (generalized anchor)
# ─────────────────────────────────────────────────────────────────────────────

def _build_raw_bgm_header(sample_rate=44100, channels=2, data_size=0x1000,
                          loop_start=0, loop_end=0):
    """Build a raw 0x800-byte BGM header without encoding audio."""
    hdr = bytearray(0x800)
    struct.pack_into(">I", hdr, 0, data_size)
    hdr[5] = 0x7F
    struct.pack_into(">H", hdr, 6, sample_rate)
    hdr[8] = channels
    hdr[9] = 0x00
    hdr[10] = 0x11
    hdr[11] = 0x00
    struct.pack_into(">I", hdr, 0x0C, loop_start)
    struct.pack_into(">I", hdr, 0x10, loop_end)
    return bytes(hdr)


def test_parse_22050_hz_entry(tmp_path):
    header = _build_raw_bgm_header(sample_rate=22050, channels=2, data_size=0x1000)
    path = tmp_path / "bgm_22k.dat"
    path.write_bytes(header + b"\xAA" * 0x1000)
    bgm = bgm_fmt.parse_bgm(str(path))
    assert bgm.entry_count == 1
    assert bgm.entries[0].sample_rate == 22050
    assert bgm.entries[0].channels == 2


def test_parse_mixed_rates(tmp_path):
    h1 = _build_raw_bgm_header(sample_rate=44100, data_size=0x1000)
    h2 = _build_raw_bgm_header(sample_rate=22050, data_size=0x1000)
    h3 = _build_raw_bgm_header(sample_rate=11025, data_size=0x1000)
    path = tmp_path / "bgm_mixed.dat"
    path.write_bytes(h1 + b"\xAA" * 0x1000 + h2 + b"\xBB" * 0x1000
                     + h3 + b"\xCC" * 0x1000)
    bgm = bgm_fmt.parse_bgm(str(path))
    assert bgm.entry_count == 3
    rates = [e.sample_rate for e in bgm.entries]
    assert rates == [44100, 22050, 11025]


def test_detect_non_44100_bgm(tmp_path):
    header = _build_raw_bgm_header(sample_rate=22050, data_size=0x8000)
    path = tmp_path / "bgm_22k.dat"
    path.write_bytes(header + b"\xAA" * 0x8000)
    assert detect_path(str(path)) is Format.BGM


def test_decode_non_44100_entry(tmp_path):
    pcm = [int(200 * math.sin(2 * math.pi * 440 * i / 22050))
           for i in range(44100)]
    entry = build_bgm_entry(pcm, sample_rate=22050, channels=2)
    path = tmp_path / "bgm_22k.dat"
    path.write_bytes(entry + b"\x00" * 0x800)
    bgm = bgm_fmt.parse_bgm(str(path))
    decoded = bgm_fmt.bgm_entry_to_pcm(bgm, bgm.entries[0])
    assert len(decoded) > 0
    assert max(abs(s) for s in decoded) > 0


# ─────────────────────────────────────────────────────────────────────────────
# Substance 2003: demo.dat
# ─────────────────────────────────────────────────────────────────────────────

DEMO_DAT = "tests/mgs2_substance_2003/demo.dat"


def _demo_available():
    import os
    return os.path.exists(DEMO_DAT)


@pytest.fixture(scope="module")
def demo_bgm(request):
    if not request.config.getoption("--realdata"):
        pytest.skip("real-data test — pass --realdata to run (1+ GB file, slow to parse)")
    if not _demo_available():
        pytest.skip("demo.dat test data not present")
    return bgm_fmt.parse_bgm(DEMO_DAT)


def test_demo_dat_parses(demo_bgm):
    assert demo_bgm.entry_count == 135


def test_demo_dat_entry_metadata(demo_bgm):
    e = demo_bgm.entries[0]
    assert e.sample_rate in (44100, 48000)
    assert e.channels == 2
    assert e.duration_seconds > 0


def test_demo_dat_decode(demo_bgm):
    pcm = bgm_fmt.bgm_entry_to_pcm(demo_bgm, demo_bgm.entries[0])
    assert len(pcm) > 0
    assert max(abs(s) for s in pcm) > 0


def test_demo_dat_all_entries_present(demo_bgm):
    for entry in demo_bgm.entries:
        assert entry.sample_rate in (44100, 48000)
        assert entry.channels == 2
        assert entry.actual_data_size > 0
