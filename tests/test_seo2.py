"""Tests for BP_SE.DAT, the global sound container.

These build a SEO2 file from scratch — no game data. The rule that makes the
format certain is the chain: each entry's data ends exactly where the next one
begins, counting `length * channels`.
"""

import struct

import pytest

from conftest import tone

from mgs2_audio.codec import psadpcm
from mgs2_audio.formats import seo2


def build_seo2(path, sounds):
    """A SEO2 container. `sounds` is a list of (sound_id, channels, pcm)."""
    payloads = []
    for sid, channels, pcm in sounds:
        data = bytearray(psadpcm.encode_psadpcm(pcm))
        # pad to a whole frame count so a channel is frame-aligned
        while len(data) % psadpcm.FRAME_SIZE:
            data += b"\x00"
        payloads.append((sid, channels, bytes(data)))

    count = len(payloads)
    head = bytearray(seo2.MAGIC + struct.pack("<II", 1, count))
    head += b"\x00" * (count * seo2.RECORD_SIZE)

    body = bytearray()
    offset = len(head)
    for i, (sid, channels, data) in enumerate(payloads):
        rec = seo2.HEADER_SIZE + i * seo2.RECORD_SIZE
        struct.pack_into("<IIII", head, rec,
                         0x02000000 | sid, channels, offset, len(data))
        body += data * channels
        offset += len(data) * channels

    path.write_bytes(bytes(head) + bytes(body))
    return str(path)


@pytest.fixture
def container(tmp_path):
    return build_seo2(tmp_path / "BP_SE.DAT", [
        (0x07, 1, tone(2000, 440)),
        (0x0B, 2, tone(1500, 300)),
        (0x9B, 1, tone(3000, 220)),
    ])


def test_parses_every_sound(container):
    f = seo2.parse_seo2(container)
    assert f.has_audio
    assert [s.sound_id for s in f.sounds] == [0x07, 0x0B, 0x9B]
    assert [s.channels for s in f.sounds] == [1, 2, 1]
    assert f.sample_rate == 44100


def test_entries_chain_exactly(container):
    """offset + length*channels == next offset — what proves the layout."""
    f = seo2.parse_seo2(container)
    for a, b in zip(f.sounds, f.sounds[1:]):
        assert a.offset + a.total_bytes == b.offset


def test_rejects_a_file_that_is_not_seo2(tmp_path):
    p = tmp_path / "not_seo2.dat"
    p.write_bytes(b"NOPE" + b"\x00" * 64)
    with pytest.raises(ValueError):
        seo2.parse_seo2(str(p))


def test_stereo_decodes_to_interleaved_pairs(container):
    f = seo2.parse_seo2(container)
    mono, stereo = f.sounds[0], f.sounds[1]
    assert len(seo2.decode_sound(f, mono)) == mono.frames * psadpcm.SAMPLES_PER_FRAME
    # stereo yields two samples per frame-sample, and both channels are identical
    pcm = seo2.decode_sound(f, stereo)
    assert len(pcm) == 2 * stereo.frames * psadpcm.SAMPLES_PER_FRAME
    assert pcm[0::2] == pcm[1::2]


def test_replace_keeps_file_size_and_neighbours(container):
    f = seo2.parse_seo2(container)
    target = f.sounds[1]                      # the stereo one, in the middle
    before = f.raw[:target.offset]
    after = f.raw[target.offset + target.total_bytes:]

    out = seo2.replace_sound(f, target, tone(4000, 700))
    assert len(out) == len(f.raw)
    assert out[:target.offset] == before      # earlier sounds untouched
    assert out[target.offset + target.total_bytes:] == after   # and later ones
    assert out[target.offset:target.offset + target.total_bytes] != \
        f.raw[target.offset:target.offset + target.total_bytes]


def test_replace_fills_both_channels_of_a_stereo_sound(container):
    f = seo2.parse_seo2(container)
    target = f.sounds[1]
    out = seo2.replace_sound(f, target, tone(4000, 700))
    left = out[target.offset:target.offset + target.length]
    right = out[target.offset + target.length:target.offset + 2 * target.length]
    assert left == right


def test_replace_preserves_frame_flags(container):
    """Whatever flags a sound carries belong to it, not to our re-encoding."""
    f = seo2.parse_seo2(container)
    target = f.sounds[0]
    raw = bytearray(f.raw)
    raw[target.offset + psadpcm.FRAME_SIZE + 1] = psadpcm.FLAG_LOOP_START
    f.raw = bytes(raw)

    out = seo2.replace_sound(f, target, tone(4000, 700))
    assert out[target.offset + psadpcm.FRAME_SIZE + 1] == psadpcm.FLAG_LOOP_START


def test_short_recording_is_padded_not_overflowed(container):
    f = seo2.parse_seo2(container)
    target = f.sounds[2]
    out = seo2.replace_sound(f, target, tone(64, 440))
    assert len(out) == len(f.raw)


def test_describe_and_list_do_not_crash(container):
    f = seo2.parse_seo2(container)
    assert "Sounds" in seo2.describe(f)
    assert "duration" in seo2.list_sounds(f)
