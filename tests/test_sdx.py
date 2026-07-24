"""Tests for the .sdx sound banks.

The two rules the game imposes: a replaced sample must keep its exact byte size
(the bank table stores addresses), and each frame's flag byte must survive
(loop and end markers).
"""

import os

from conftest import build_sdx, build_stage_tree, tone

from mgs2_audio.codec import psadpcm
from mgs2_audio.formats import sdx


def test_parses_samples(bank):
    b = sdx.parse_sdx(bank)
    assert b.has_audio
    assert len(b.samples) == 3
    assert b.sample_rate == 22050
    assert all(s.size % psadpcm.FRAME_SIZE == 0 for s in b.samples)


def test_samples_do_not_overlap_and_start_after_header(bank):
    b = sdx.parse_sdx(bank)
    assert b.samples[0].offset == sdx.DATA_START
    for prev, nxt in zip(b.samples, b.samples[1:]):
        assert prev.offset + prev.size == nxt.offset


def test_audio_region_stops_at_padding(bank):
    b = sdx.parse_sdx(bank)
    assert b.raw[b.data_end:b.data_end + 16] == b"\xff" * 16


def test_music_bank_0xfe_padding_is_recognised(tmp_path):
    """Music/sequencer banks close their audio with 0xFE, not 0xFF.

    Measured across the game's 600 stage banks: every music bank pads with
    0xFE. Recognising only 0xFF made this parser miss the end of the audio and
    carve bogus "samples" out of the cue table and sequence that follow it —
    which then polluted the cross-bank scan. The tail below is shaped so those
    phantom samples would appear if the padding were ever missed again.
    """
    raw = bytearray(sdx.DATA_START)
    for pcm in (tone(2000, 300), tone(1500, 440)):
        data = bytearray(psadpcm.encode_psadpcm(pcm))
        data[-psadpcm.FRAME_SIZE + 1] = psadpcm.FLAG_END
        raw += data
    audio_end = len(raw)
    raw += b"\xfe" * 0x100                       # the music-bank padding
    tail = bytearray(0x400)                      # stand-in cue table + sequence
    for i in range(0, len(tail), psadpcm.FRAME_SIZE):
        tail[i + 1] = psadpcm.FLAG_END           # would look like sample ends
    raw += tail
    path = tmp_path / "pk000011.sdx"
    path.write_bytes(bytes(raw))

    b = sdx.parse_sdx(str(path))
    assert b.data_end == audio_end               # stopped at the 0xFE padding
    assert len(b.samples) == 2                   # and carved no phantom samples
    assert all(s.offset + s.size <= audio_end for s in b.samples)


def test_each_sample_ends_on_a_flagged_frame(bank):
    b = sdx.parse_sdx(bank)
    for s in b.samples:
        flags = sdx.sample_flags(b, s)
        assert flags[-1] & psadpcm.FLAG_END
        assert not any(f & psadpcm.FLAG_END for f in flags[:-1])


def test_decode_length_matches_frames(bank):
    b = sdx.parse_sdx(bank)
    s = b.samples[0]
    assert len(sdx.decode_sample(b, s)) == s.frames * psadpcm.SAMPLES_PER_FRAME


def test_replace_keeps_file_size_and_neighbours(bank):
    b = sdx.parse_sdx(bank)
    target = b.samples[1]
    out = sdx.replace_sample(b, target, tone(3000, 500))

    assert len(out) == len(b.raw)
    assert out[:target.offset] == b.raw[:target.offset]
    assert out[target.offset + target.size:] == b.raw[target.offset + target.size:]


def test_replace_preserves_flags(bank):
    b = sdx.parse_sdx(bank)
    target = b.samples[1]
    before = sdx.sample_flags(b, target)

    out = sdx.replace_sample(b, target, tone(3000, 500))
    after = [out[target.offset + i * psadpcm.FRAME_SIZE + 1]
             for i in range(target.frames)]
    assert after == before


def test_replace_pads_and_trims(bank):
    b = sdx.parse_sdx(bank)
    target = b.samples[0]
    assert len(sdx.replace_sample(b, target, [0] * 5)) == len(b.raw)
    assert len(sdx.replace_sample(b, target, tone(200000, 440))) == len(b.raw)


def test_sample_key_ignores_flags(bank):
    """The same sound with different loop markers must hash the same."""
    b = sdx.parse_sdx(bank)
    s = b.samples[0]
    key = sdx.sample_key(b.raw, s)

    tweaked = bytearray(b.raw)
    tweaked[s.offset + 1] = psadpcm.FLAG_LOOP_START
    assert sdx.sample_key(bytes(tweaked), s) == key


def test_sample_key_changes_with_audio(bank):
    b = sdx.parse_sdx(bank)
    s = b.samples[0]
    key = sdx.sample_key(b.raw, s)
    changed = bytearray(b.raw)
    changed[s.offset + 5] ^= 0xFF
    assert sdx.sample_key(bytes(changed), s) != key


# ─────────────────────────────────────────────────────────────────────────────
# Cross-bank scanning
# ─────────────────────────────────────────────────────────────────────────────

def test_find_stage_folder_from_game_root(tmp_path):
    shared = tone(4000, 300)
    root = build_stage_tree(tmp_path / "MGS2", {"a00a": [shared], "a00b": [shared]})
    assert sdx.find_stage_folder(root) == os.path.join(root, "us", "stage")


def test_find_stage_folder_accepts_stage_folder_itself(tmp_path):
    root = build_stage_tree(tmp_path / "MGS2", {"a00a": [tone(4000, 300)]})
    stage = os.path.join(root, "us", "stage")
    assert sdx.find_stage_folder(stage) == stage


def test_find_stage_folder_returns_none_when_empty(tmp_path):
    assert sdx.find_stage_folder(str(tmp_path)) is None
    assert sdx.find_stage_folder("/definitely/not/here") is None
    assert sdx.find_stage_folder("") is None


def test_scan_groups_identical_sounds_across_banks(tmp_path):
    shared = tone(4000, 300)
    only_a = tone(5000, 700)
    root = build_stage_tree(tmp_path / "MGS2", {
        "a00a": [shared, only_a],
        "a00b": [shared],
        "a00c": [shared],
    })
    groups = sdx.scan_banks(sdx.find_banks(sdx.find_stage_folder(root)))

    counts = sorted(g.count for g in groups)
    assert counts == [1, 3]                       # one unique sound, one in all three
    assert groups[0].count == 3                   # most shared comes first
    assert len(groups[0].banks) == 3


def test_replace_group_rewrites_every_bank_and_backs_up(tmp_path):
    shared = tone(4000, 300)
    root = build_stage_tree(tmp_path / "MGS2", {"a00a": [shared], "a00b": [shared]})
    paths = sdx.find_banks(sdx.find_stage_folder(root))
    before = {p: open(p, "rb").read() for p in paths}

    group = sdx.scan_banks(paths)[0]
    changed = sdx.replace_group(group, tone(4000, 900), backup=True)

    assert changed == 2
    for p in paths:
        with open(p, "rb") as f:
            assert len(f.read()) == len(before[p])   # size preserved
        with open(p + ".bak", "rb") as f:
            assert f.read() == before[p]    # backup is faithful
        with open(p, "rb") as f:
            assert f.read() != before[p]             # and the audio changed


def test_replace_group_keeps_per_occurrence_flags(tmp_path):
    shared = tone(4000, 300)
    root = build_stage_tree(tmp_path / "MGS2", {"a00a": [shared], "a00b": [shared]})
    paths = sdx.find_banks(sdx.find_stage_folder(root))

    # give one bank a loop-start marker the other does not have
    with open(paths[1], "rb") as f:
        raw = bytearray(f.read())
    raw[sdx.DATA_START + 1] = psadpcm.FLAG_LOOP_START
    with open(paths[1], "wb") as f:
        f.write(bytes(raw))

    group = next(g for g in sdx.scan_banks(paths) if g.count == 2)
    sdx.replace_group(group, tone(4000, 900), backup=False)

    a = sdx.parse_sdx(paths[0])
    b = sdx.parse_sdx(paths[1])
    assert sdx.sample_flags(a, a.samples[0])[0] == 0
    assert sdx.sample_flags(b, b.samples[0])[0] == psadpcm.FLAG_LOOP_START
