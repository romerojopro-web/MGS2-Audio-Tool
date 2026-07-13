"""Tests for the .sdt format.

These lock down the discoveries that took the longest to make: the 0x800 stereo
interleave, the header variants that hide the channel count, and the fact that a
replacement must never change the file's size.
"""

import struct

import pytest

from conftest import (FRAMES_PER_CHUNK, adpcm_sweep, blank_header_fields,
                      build_sdt, build_stereo_sdt, speech_like)

from mgs2_audio.codec import psadpcm
from mgs2_audio.formats import sdt


def test_parses_mono_header(mono_sdt):
    f = sdt.parse_sdt(mono_sdt)
    assert f.channels == 1
    assert f.sample_rate == 44100
    assert f.supported
    assert f.duration_seconds > 0


def test_parses_stereo_header(stereo_sdt):
    f = sdt.parse_sdt(stereo_sdt)
    assert f.channels == 2
    assert f.supported


def test_stereo_duration_is_per_channel(tmp_path, stereo_sdt):
    """A stereo file holds two channels, so it is half as long as its byte count."""
    stereo = sdt.parse_sdt(stereo_sdt)
    mono = sdt.parse_sdt(build_sdt(
        tmp_path / "m.sdt", channels=1, blocks=len(stereo.blocks)))
    assert abs(stereo.duration_seconds - mono.duration_seconds / 2) < 0.01


def test_deinterleave_then_interleave_round_trips():
    a = bytes(range(256)) * 16          # 0x1000 bytes
    b = bytes(reversed(range(256))) * 16
    merged = sdt.interleave_channels([a, b])
    left, right = sdt.deinterleave_channels(merged, 2)
    assert left == a and right == b


def test_interleave_step_is_0x800():
    assert sdt.CHANNEL_INTERLEAVE == 0x800
    a = b"A" * 0x800 + b"C" * 0x800
    b = b"B" * 0x800 + b"D" * 0x800
    merged = sdt.interleave_channels([a, b])
    assert merged[:0x800] == b"A" * 0x800
    assert merged[0x800:0x1000] == b"B" * 0x800


def test_stereo_pcm_is_interleaved_lr(stereo_sdt):
    f = sdt.parse_sdt(stereo_sdt)
    pcm = sdt.sdt_to_pcm(f)
    assert len(pcm) % 2 == 0
    left, right = pcm[0::2], pcm[1::2]
    assert len(left) == len(right)
    assert left != right                # the fixture builds two distinct channels


def test_stereo_detected_from_content_distinct_channels(stereo_sdt):
    """'PACB' variants hide the channel count: recover it from the audio.

    Distinct channels are caught by the continuity signal — the audio of a chunk
    continues into the chunk after next, not into the next one.
    """
    assert sdt.parse_sdt(blank_header_fields(stereo_sdt)).channels == 2


def test_stereo_detected_from_content_duplicate_channels(dual_mono_sdt):
    """Centred voice puts the same audio on both channels: the duplication signal."""
    assert sdt.parse_sdt(blank_header_fields(dual_mono_sdt)).channels == 2


def test_mono_file_is_not_mistaken_for_stereo(mono_sdt):
    """The dangerous failure: a mono file wrongly split in two would double-speed."""
    assert sdt.parse_sdt(blank_header_fields(mono_sdt)).channels == 1


def test_non_psadpcm_is_reported_not_decoded(tmp_path):
    """Some stock files use another codec. Say so instead of playing noise."""
    junk = bytes((i * 37 + 11) % 256 for i in range(0x4000))
    path = build_sdt(tmp_path / "other.sdt", channels=1, blocks=1, audio=junk)
    f = sdt.parse_sdt(path)
    assert not f.is_psadpcm
    assert not f.supported


def test_file_without_audio_blocks_is_reported(tmp_path):
    path = tmp_path / "empty.sdt"
    path.write_bytes(b"\x00" * 0x200)
    f = sdt.parse_sdt(str(path))
    assert not f.has_audio
    assert not f.supported


def test_replace_keeps_exact_file_size(mono_sdt):
    f = sdt.parse_sdt(mono_sdt)
    before = len(f.raw)
    out = sdt.replace_audio(f, speech_like(1000))
    assert len(out) == before


def test_replace_preserves_block_structure(stereo_sdt):
    f = sdt.parse_sdt(stereo_sdt)
    out = sdt.replace_audio(f, speech_like(2000))
    for b in f.blocks:
        typ, size = struct.unpack_from("<II", out, b.file_offset)
        assert typ == 1 and size == b.total_size


def test_replace_on_stereo_puts_audio_on_both_channels(stereo_sdt):
    f = sdt.parse_sdt(stereo_sdt)
    out = sdt.replace_audio(f, speech_like(28 * 100))

    tmp = f.__class__(path="x", raw=out, sample_rate=f.sample_rate,
                      channels=f.channels, blocks=f.blocks)
    pcm = sdt.sdt_to_pcm(tmp)
    assert pcm[0::2] == pcm[1::2]       # the mono dub sits on L and R alike


def test_replace_pads_short_audio_and_trims_long(mono_sdt, tmp_path):
    f = sdt.parse_sdt(mono_sdt)
    assert len(sdt.replace_audio(f, [0] * 10)) == len(f.raw)

    # The "trims long" half needs input that exceeds capacity, which then
    # gets truncated *to* that capacity before encoding — so its cost is set
    # by the target's capacity, not by how much we overshoot it. Use a
    # single-block target (the smallest build_sdt makes) instead of the
    # shared 6-block mono_sdt fixture: same trim logic, ~6x less real (i.e.
    # non-silent, not fast-pathable) audio for the brute-force encoder.
    small = sdt.parse_sdt(build_sdt(tmp_path / "small.sdt", channels=1, blocks=1))
    huge = speech_like(28 * 1050)  # comfortably exceeds a 1-block capacity
    assert len(sdt.replace_audio(small, huge)) == len(small.raw)


# ─────────────────────────────────────────────────────────────────────────────
# Substance 2003: vox.dat
# ─────────────────────────────────────────────────────────────────────────────

VOX_DAT = "tests/mgs2_substance_2003/vox.dat"


def _vox_available():
    import os
    return os.path.exists(VOX_DAT)


@pytest.fixture(scope="module")
def vox_file(request):
    if not request.config.getoption("--realdata"):
        pytest.skip("real-data test — pass --realdata to run (1+ GB file, slow to parse)")
    if not _vox_available():
        pytest.skip("vox.dat test data not present")
    return sdt.parse_sdt(VOX_DAT)


def test_vox_dat_parses(vox_file):
    assert len(vox_file.blocks) > 0
    assert vox_file.sample_rate == 44100
    assert vox_file.channels == 1


def test_vox_dat_is_psadpcm(vox_file):
    assert vox_file.is_psadpcm
    assert vox_file.supported


def test_vox_dat_block_count(vox_file):
    assert len(vox_file.blocks) == 53146


def test_vox_dat_block_decoding(vox_file):
    from mgs2_audio.codec.psadpcm import decode_psadpcm
    block = vox_file.blocks[1]
    raw_adpcm = vox_file.raw[block.data_offset:block.data_offset + block.data_size]
    pcm = decode_psadpcm(raw_adpcm)
    assert len(pcm) > 0
    assert any(s != 0 for s in pcm)


def test_vox_dat_duration(vox_file):
    assert vox_file.duration_seconds > 1000
