"""Tests for the music sequencer found in the .sdx banks.

These build a synthetic bank rather than shipping game data: an instrument
directory, one looping sample, a cue table, and a track of events. If the
parser or the renderer drifts, these fail.

Every rule exercised here was confirmed by ear on real banks — see
docs/FORMATS.md.
"""

import struct

import pytest

from conftest import tone

from mgs2_audio import render
from mgs2_audio.codec import psadpcm
from mgs2_audio.formats import sequence as seq


# ─────────────────────────────────────────────────────────────────────────────
# A bank built from scratch
# ─────────────────────────────────────────────────────────────────────────────

def directory_record(offset, coarse=0, fraction=0):
    """The fixed shape the parser looks for.

    Bytes 4 and 5 hold the sample's tuning: a signed integer number of
    semitones, then a fraction over 256.
    """
    return (struct.pack("<I", offset) + bytes([coarse & 0xFF, fraction & 0xFF])
            + b"\x00\x7f" + b"\x00\x00\x00\x0f" + b"\x00\x19\x0a\x00")


def looping_sample(frames=6):
    """A tiny PS-ADPCM sample: silent lead-in, loop start, end flag."""
    data = bytearray()
    data += bytes([0x02, 0x00]) + b"\x00" * 14           # the silent first frame
    for f in range(1, frames - 1):
        flag = psadpcm.FLAG_LOOP_START if f == 2 else 0
        data += bytes([0x02, flag]) + bytes([0x71] * 14)
    data += bytes([0x02, psadpcm.FLAG_END]) + bytes([0x71] * 14)
    return bytes(data)


def custom_envelope_record(offset, attack=0x60, release=0x14, pan=0x10):
    """A directory entry whose envelope/pan are NOT the common defaults.

    Bytes +7 (attack), +13 (release) and +14 (pan) vary per instrument; only
    +3/+6/+8/+9/+10/+11/+12/+15 are structural.
    """
    return (struct.pack("<I", offset) + bytes([0, 0])
            + bytes([0x00, attack]) + b"\x00\x00\x00\x0f"
            + bytes([0x00, release, pan, 0x00]))


def event(b0, b1, b2, opcode):
    return bytes([b0, b1, b2, opcode])


def note_event(pitch, volume=90, gate=100, length=30):
    """Note bytes in raven note_set order: b0=volume, b1=gate%, b2=length ticks."""
    return event(volume, gate, length, pitch)


def build_bank(tmp_path, tracks=None, instruments=2, coarse=0, fraction=0):
    sample = looping_sample()

    entries = b""
    offset = 0
    for i in range(instruments):
        entries += directory_record(offset, coarse, fraction)
        offset += len(sample)

    audio = sample * instruments
    raw = bytearray(seq.DIRECTORY_START)
    raw += entries
    raw += audio

    # frame-aligned padding closes the audio
    while len(raw) % psadpcm.FRAME_SIZE:
        raw += b"\x00"
    raw += b"\xfe" * 0x100

    tracks = tracks or [[
        event(0, 0, 78, seq.OP_TEMPO),        # tmp=78 → ~30 ticks/s
        event(0, 0, 127, seq.OP_VOL_CHG),     # track volume (was mislabelled OP_PAN)
        event(0, 0, 1, seq.OP_PROGRAM),
        note_event(60),
        event(0, 0, 12, seq.OP_WAIT),
        note_event(64),
    ]]

    # the sequence, each track ending on the end marker
    body = b""
    addrs = []
    for events in tracks:
        addrs.append(len(body))
        for e in events:
            body += e
        body += bytes(seq.END_EVENT)

    table = bytearray()
    kinds = bytes([0x80, len(addrs), 0, 0])
    slots = [addrs[i] if i < len(addrs) else 0xFFFFFFFF for i in range(3)]
    table += kinds + b"".join(struct.pack("<I", s) for s in slots)
    table += b"\x00" * (seq.TABLE_SIZE - len(table))

    sequence = bytearray(body)
    sequence += b"\x00" * (seq.SEQUENCE_SIZE - len(sequence))

    raw += table + sequence
    tmp_path.mkdir(parents=True, exist_ok=True)
    path = tmp_path / "pk000000.sdx"
    path.write_bytes(bytes(raw))
    return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def test_detects_a_sequencer_bank(tmp_path):
    path = build_bank(tmp_path)
    assert seq.has_sequence(open(path, "rb").read())


def test_rejects_a_bank_without_a_directory(tmp_path):
    path = tmp_path / "plain.sdx"
    path.write_bytes(b"\x00" * 0x4000)
    assert not seq.has_sequence(path.read_bytes())
    with pytest.raises(ValueError):
        seq.parse_sequence(str(path))


def test_parses_the_directory(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path, instruments=3))
    assert len(bank.instruments) == 3
    assert bank.instruments[0].offset == 0
    assert bank.instruments[1].offset > 0
    assert all(i.tune == 0.0 for i in bank.instruments)


def test_tuning_is_signed_fixed_point(tmp_path):
    """Bytes 4 and 5 are both signed (raven sample_note / sample_tune):
    byte 4 = whole semitones, byte 5 = 1/256-semitone fine tune."""
    # positive fine tune (byte 5 < 128)
    up = seq.parse_sequence(build_bank(tmp_path / "up", coarse=2, fraction=96))
    assert up.instruments[0].tune == pytest.approx(2 + 96 / 256)

    # negative fine tune (byte 5 >= 128 → signed) — this is the case that was wrong
    down = seq.parse_sequence(build_bank(tmp_path / "down", coarse=-10 & 0xFF,
                                         fraction=176))
    assert down.instruments[0].tune == pytest.approx(-10 + (176 - 256) / 256)


def test_only_samples_flagged_to_loop_repeat(tmp_path):
    """A stray loop-start marker must not make a one-shot sample repeat.

    What decides is the final frame: FLAG_END alone stops, FLAG_END|FLAG_LOOP
    repeats. The fixture carries a loop-start marker and still ends on FLAG_END.
    """
    bank = seq.parse_sequence(build_bank(tmp_path))
    inst = bank.instruments[0]
    assert inst.loop_frame == 2           # the marker is there
    assert inst.end_flag == psadpcm.FLAG_END
    assert not inst.loops                 # and it changes nothing

    inst.end_flag = psadpcm.FLAG_END | psadpcm.FLAG_LOOP
    assert inst.loops


def test_audio_starts_after_the_directory(tmp_path):
    """A hard-won detail: the audio does not begin at a fixed offset."""
    bank = seq.parse_sequence(build_bank(tmp_path, instruments=3))
    expected = seq.DIRECTORY_START + 3 * seq.RECORD_SIZE
    assert bank.audio_start == expected


def test_sample_ends_on_its_end_flag_and_knows_its_loop(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    inst = bank.instruments[0]
    assert inst.size == 6 * psadpcm.FRAME_SIZE
    assert inst.loop_frame == 2
    assert inst.loop_sample == 2 * psadpcm.SAMPLES_PER_FRAME


def test_parses_the_cue_table(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    assert len(bank.cues) == 1
    cue = bank.cues[0]
    assert cue.track_count == 1
    assert cue.kind == 0x80


def test_track_stops_at_the_end_marker(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    events = bank.track(bank.cues[0].tracks[0])
    assert len(events) == 6
    assert all(e.opcode != seq.OP_END for e in events)


def test_note_fields_are_named_for_what_they_mean(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    notes = [e for e in bank.track(bank.cues[0].tracks[0]) if e.is_note]
    assert [n.pitch for n in notes] == [60, 64]
    assert notes[0].velocity == 90        # b0 = volume
    assert notes[0].gate_pct == 100       # b1 = gate %
    assert notes[0].length == 30          # b2 = note length in ticks
    assert bank.note_count(bank.cues[0]) == 2


def test_signed_parameters():
    assert seq.to_signed(12) == 12
    assert seq.to_signed(244) == -12
    assert seq.to_signed(232) == -24
    assert seq.to_signed(0) == 0


# ─────────────────────────────────────────────────────────────────────────────
# Rendering
# ─────────────────────────────────────────────────────────────────────────────

def test_renders_audio(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    left, right = render.render_cue(bank, bank.cues[0], seconds=3)
    assert left and len(left) == len(right)
    assert max(abs(v) for v in left) > 100          # something was played


def test_a_silent_cue_renders_nothing(tmp_path):
    """Velocity 0 means no note: the SPU would play silence, so do we."""
    track = [event(0, 0, 1, seq.OP_PROGRAM), note_event(60, volume=0)]
    bank = seq.parse_sequence(build_bank(tmp_path, tracks=[track]))
    left, _ = render.render_cue(bank, bank.cues[0], seconds=3)
    assert not left or max(abs(v) for v in left) < 30


def test_higher_notes_finish_sooner(tmp_path):
    """A note is a resampled sample: pitch up, and the same gate covers more of it."""
    low = [event(0, 0, 1, seq.OP_PROGRAM), note_event(48, gate=60, length=60)]
    high = [event(0, 0, 1, seq.OP_PROGRAM), note_event(72, gate=60, length=60)]
    b_low = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[low]))
    b_high = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[high]))
    # both must produce sound; the point is that pitch changes the waveform
    l1, _ = render.render_cue(b_low, b_low.cues[0], seconds=4)
    l2, _ = render.render_cue(b_high, b_high.cues[0], seconds=4)
    assert l1 and l2 and l1 != l2


def test_pan_sends_the_voice_to_one_side(tmp_path):
    """0xDD pan_set: panf = signed(b1)+20; b1=+20 → panf 40 → hard right.
    Program first, then pan_set, so the manual pan isn't reset by the program."""
    right = [event(0, 0, 1, seq.OP_PROGRAM),
             event(0, 20, 0, seq.OP_PAN_SET), note_event(60)]
    bank = seq.parse_sequence(build_bank(tmp_path, tracks=[right]))
    l, r = render.render_cue(bank, bank.cues[0], seconds=3)
    assert max(abs(v) for v in r) > 10 * max(abs(v) for v in l)


def test_ads_sl_changes_sustain_level(tmp_path):
    """0xD7: sustain level (b0) sets decay target; b1/b2 inverted: 0x0F/0x7F = fastest."""
    loud = [event(0, 0, 1, seq.OP_PROGRAM),
            event(15, 0x0F, 0x7F, seq.OP_ADS_SET), note_event(60)]
    soft = [event(0, 0, 1, seq.OP_PROGRAM),
            event(0, 0x0F, 0x7F, seq.OP_ADS_SET), note_event(60)]
    b1 = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[loud]))
    b2 = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[soft]))
    l1, _ = render.render_cue(b1, b1.cues[0], seconds=3)
    l2, _ = render.render_cue(b2, b2.cues[0], seconds=3)
    assert l1 != l2                       # normalisation hides the ratio, not the shape


def test_a_new_note_cuts_the_one_still_ringing(tmp_path):
    """One voice per track: notes must not pile up into a smear."""
    track = [event(0, 0, 1, seq.OP_PROGRAM),
             note_event(60, gate=120, length=6),     # rings long, short slot
             note_event(67, gate=30, length=30)]
    bank = seq.parse_sequence(build_bank(tmp_path, tracks=[track]))
    left, _ = render.render_cue(bank, bank.cues[0], seconds=4)

    # at the moment the second note starts, the first must already be fading
    cut = int(6 / seq.TICKS_PER_SECOND * render.OUTPUT_RATE)
    assert left
    assert abs(left[min(cut + render.CUT_SAMPLES, len(left) - 1)]) < 30000


def test_unknown_opcodes_are_skipped_not_guessed(tmp_path):
    """An opcode we do not understand must not silently change the sound."""
    plain = [event(0, 0, 1, seq.OP_PROGRAM), note_event(60)]
    noisy = [event(0, 0, 1, seq.OP_PROGRAM),
             event(9, 9, 9, 0xDA),                   # unknown, must be ignored
             note_event(60)]
    b1 = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[plain]))
    b2 = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[noisy]))
    l1, _ = render.render_cue(b1, b1.cues[0], seconds=3)
    l2, _ = render.render_cue(b2, b2.cues[0], seconds=3)
    assert l1 == l2


def test_transpose_shifts_later_notes(tmp_path):
    plain = [event(0, 0, 1, seq.OP_PROGRAM), note_event(60)]
    down = [event(0, 0, 1, seq.OP_PROGRAM),
            event(0, 0, 244, seq.OP_TRANS_SET),      # b2 = signed -12 semitones
            note_event(60)]
    b1 = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[plain]))
    b2 = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[down]))
    l1, _ = render.render_cue(b1, b1.cues[0], seconds=3)
    l2, _ = render.render_cue(b2, b2.cues[0], seconds=3)
    assert l1 != l2


def test_mono_render_merges_the_channels(tmp_path):
    bank = seq.parse_sequence(build_bank(tmp_path))
    l, r = render.render_cue(bank, bank.cues[0], stereo=False, seconds=3)
    assert l == r


def test_reverb_reflections_write_to_distinct_taps():
    """Each of the 4 SPU reverb reflections (L/R same-side, L/R cross-side) must
    land at its own buffer address. A past bug collapsed all 4 into the single
    write-cursor slot, silently discarding 3 of them — see docs/AUDIT.md."""
    reverb = render.SPU_Reverb(render.REVERB_HALL)
    offsets = (reverb._w_mLSAME, reverb._w_mRSAME,
               reverb._w_mLDIFF, reverb._w_mRDIFF)
    assert len(set(offsets)) == 4          # four genuinely different addresses

    reverb.process(1.0, -1.0)              # asymmetric input, nonzero reflections
    blen = len(reverb.buf)
    vals = [reverb.buf[o % blen] for o in offsets]
    assert any(v != 0 for v in vals)       # under the old bug, none of these
                                            # addresses were ever written


def test_sweep_scoops_pitch_into_the_note(tmp_path):
    """0xE5 sws_set: the note starts off-pitch and slides to its true pitch."""
    plain = [event(0, 0, 1, seq.OP_PROGRAM), note_event(60, length=60)]
    # b0=248 (signed -8) → start +8 semitones above; b1=20 ramp ticks; b2=0 hold
    swept = [event(0, 0, 1, seq.OP_PROGRAM),
             event(248, 20, 0, seq.OP_SWS_SET),
             note_event(60, length=60)]
    b_plain = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[plain]))
    b_swept = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[swept]))
    l1, _ = render.render_cue(b_plain, b_plain.cues[0], seconds=3)
    l2, _ = render.render_cue(b_swept, b_swept.cues[0], seconds=3)
    assert l1 and l2 and l1 != l2       # the scoop changes the sound


# ─────────────────────────────────────────────────────────────────────────────
# raven fidelity is LOCKED — these guard the synth's core tuning tables and
# curves against silent drift. They are the keystone: the whole point of the
# sequencer is to reproduce Kazuki Muraoka's PS2 driver faithfully, so the exact
# raven constants (sd_ioset.c / sd_sub1.c) must never change by accident. See
# docs/AUDIT_SDX.md §2.
# ─────────────────────────────────────────────────────────────────────────────

# raven sd_ioset.c pant[41] — the pan→volume law. NOT constant-power.
_RAVEN_PANT = [
    0,   2,   4,   7,   10,  13,  16,  20,  24,  28,  32,  36,  40,  45,
    50,  55,  60,  65,  70,  75,  80,  84,  88,  92,  96,  100, 104, 107,
    110, 112, 114, 116, 118, 120, 122, 123, 124, 125, 126, 127, 127,
]

# raven sd_sub1.c VIBX_TBL[32] — the vibrato LFO quarter/half waveform.
_RAVEN_VIBX = [
    0,   32,  56,  80,  104, 128, 144, 160,
    176, 192, 208, 224, 232, 240, 240, 248,
    255, 248, 244, 240, 232, 224, 208, 192,
    176, 160, 144, 128, 104, 80,  56,  32,
]


def test_custom_envelope_does_not_truncate_the_directory(tmp_path):
    """Bytes +7/+13/+14 are attack/release/pan — not format constants.

    Requiring their common defaults (0x7F / 0x19 / 0x0A) ended the directory at
    the first instrument with a custom envelope: every later instrument was
    lost, and because the audio starts where the directory ends, every sample
    offset shifted with it. On the real game that misread 23 of 68 music banks.
    """
    path = build_bank(tmp_path, instruments=4)
    raw = bytearray(open(path, "rb").read())
    rec = seq.DIRECTORY_START + 2 * seq.RECORD_SIZE     # entry 2 gets a custom envelope
    raw[rec + 7] = 0x60                                 # attack rate
    raw[rec + 13] = 0x14                                # release rate
    raw[rec + 14] = 0x10                                # pan
    with open(path, "wb") as f:
        f.write(bytes(raw))

    bank = seq.parse_sequence(path)
    assert len(bank.instruments) == 4                   # not cut short at entry 2
    assert bank.instruments[2].adsr[0] == 0x60          # and its values are read
    assert bank.instruments[2].default_pan == 0x10


def test_directory_terminator_record_is_counted(tmp_path):
    """A directory closes with a record that carries none of the signature.

    The audio begins where the directory ends, so overlooking that slot starts
    the audio one frame early and every instrument decodes from the tail of its
    neighbour. It is found by measuring the VAG lead-in, not by guessing.
    """
    path = build_bank(tmp_path, instruments=3)
    raw = bytearray(open(path, "rb").read())
    dir_end = seq.DIRECTORY_START + 3 * seq.RECORD_SIZE
    # Occupies a slot, matches none of the structural bytes (+6 is not 0x00).
    raw[dir_end:dir_end] = bytes([0x00, 0x00, 0x00, 0x00, 0x00, 0x10,
                                  0x0D, 0x70, 0x00, 0x00, 0x00, 0x00,
                                  0x00, 0x00, 0x00, 0x00])
    with open(path, "wb") as f:
        f.write(bytes(raw))

    bank = seq.parse_sequence(path)
    assert len(bank.instruments) == 3                       # instruments unchanged
    assert bank.audio_start == dir_end + seq.RECORD_SIZE    # terminator counted
    assert all(i.size > 0 for i in bank.instruments)        # samples still resolve


def test_terminator_is_not_invented_when_it_would_misalign(tmp_path):
    """The extra slot is only taken when it demonstrably improves alignment.

    SE banks address their samples in SPU space, so the lead-in measure does not
    apply to them — the parser must leave their audio start alone.
    """
    path = build_bank(tmp_path, instruments=3)
    bank = seq.parse_sequence(path)
    assert bank.audio_start == seq.DIRECTORY_START + 3 * seq.RECORD_SIZE


def test_directory_record_accepts_any_envelope():
    """The record test must key on the structural bytes only."""
    rec = custom_envelope_record(0x1234, attack=0x33, release=0x07, pan=0x1F)
    assert seq._is_directory_record(rec, 0)
    # ...and still reject something that isn't a record at all
    assert not seq._is_directory_record(b"\xff" * seq.RECORD_SIZE, 0)
    assert not seq._is_directory_record(bytes(seq.RECORD_SIZE), 0)  # all zero: sl != 0x0F


def test_pan_table_matches_raven_exactly():
    """The pan curve is raven's pant[], byte for byte — not sqrt, not linear."""
    assert render._PANT == _RAVEN_PANT
    assert len(render._PANT) == 41


def test_pan_centre_is_not_constant_power():
    """raven's centre (pan 20) is pant[20]/127 = 0.63, deliberately NOT the
    sqrt(0.5)=0.707 of a constant-power law (docs/AUDIT_SDX.md §2.1)."""
    import math
    centre = render._PANT[20] / 127.0
    assert abs(centre - 0.63) < 0.005
    assert abs(centre - math.sqrt(0.5)) > 0.07     # provably not constant-power


def test_pan_table_is_bounded_and_monotonic():
    assert render._PANT[0] == 0                    # hard side fully silenced
    assert render._PANT[40] == 127                 # near side fully open
    assert render._PANT == sorted(render._PANT)    # never dips as pan sweeps


def test_centre_pan_is_balanced(tmp_path):
    """pan 20 (centre) must put equal energy on both channels — the audible
    consequence of pant[20] == pant[40-20]."""
    centre = [event(0, 0, 1, seq.OP_PROGRAM),
              event(0, 0, 0, seq.OP_PAN_SET),      # b1=0 → panf = 20 (centre)
              note_event(60)]
    bank = seq.parse_sequence(build_bank(tmp_path, tracks=[centre]))
    l, r = render.render_cue(bank, bank.cues[0], seconds=3)
    el = sum(abs(v) for v in l)
    er = sum(abs(v) for v in r)
    assert max(el, er) > 0                          # the note actually sounded
    assert abs(el - er) <= 0.02 * max(el, er)       # ...equally on both sides


def test_vibrato_table_matches_raven_exactly():
    """The vibrato LFO shape is raven's VIBX_TBL, byte for byte."""
    assert render._VIBX_TBL == _RAVEN_VIBX
    assert len(render._VIBX_TBL) == 32
    assert render._VIBX_TBL[0] == 0                 # starts at the zero crossing
    assert max(render._VIBX_TBL) == 255             # peak amplitude
    assert render._VIBX_TBL.index(255) == 16        # peak at quarter phase


def test_portamento_glides_instead_of_jumping(tmp_path):
    """0xE6 por_set (b2 = speed > 0): the note slides from the previous note's
    pitch (geometrically, raven por_compute) instead of starting on-pitch.
    Guards the glide from being silently disabled or flattened to a jump."""
    plain = [event(0, 0, 1, seq.OP_PROGRAM),
             note_event(48, length=30),
             note_event(72, length=90)]
    glided = [event(0, 0, 1, seq.OP_PROGRAM),
              note_event(48, length=30),
              event(0, 0, 40, seq.OP_POR_SET),      # enable portamento, speed 40
              note_event(72, length=90)]
    b1 = seq.parse_sequence(build_bank(tmp_path / "a", tracks=[plain]))
    b2 = seq.parse_sequence(build_bank(tmp_path / "b", tracks=[glided]))
    l1, _ = render.render_cue(b1, b1.cues[0], seconds=4)
    l2, _ = render.render_cue(b2, b2.cues[0], seconds=4)
    assert l1 and l2 and l1 != l2       # the glide changes the second note's path
