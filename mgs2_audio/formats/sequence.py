#!/usr/bin/env python3
"""
sequence.py — The music sequencer hidden in the `.sdx` banks.

Metal Gear Solid 2 ships no music files. Its in-game music is *played*, not
streamed: a small program picks samples out of the bank and plays them as notes,
the way a MIDI file drives a synthesiser. That program lives at the end of every
`.sdx`, in the region `sdx.py` leaves alone.

Layout of a bank that carries a sequence
----------------------------------------

    0x0800 .. <audio>   instrument directory, 16 bytes per entry
    <audio> .. <pad>    the PS-ADPCM samples themselves
    <pad>               0xFE (sometimes 0xFF) padding, frame-aligned
    <table>             0x1000 bytes: 256 cue records of 16 bytes
    <sequence>          0x6800 bytes: the events

An instrument directory entry:

    +0  u32  sample offset, relative to the start of the audio
    +4  u16  base rate in Hz — the rate at which the sample plays untransposed
    +6  u8   0
    +7  u8   0x7F                    (the pattern used to find the directory)
    +8  u32  0x0F000000              (constant)
    +12 4B   00 19 0A 00             (constant)

A cue record:

    +0  u8   kind
    +1  u8   number of tracks, 1..3
    +2  u8   flag        +3  u8   flag
    +4  u32  track offset into the sequence  (x3; 0xFFFFFFFF marks unused)

An event is always 4 bytes and the **opcode is the last one**:

    b0 b1 b2 opcode

    opcode < 0x80      a note.  opcode = pitch in semitones
                       b0 = volume/velocity (0..127), b1 = gate percentage (0..100),
                       b2 = note length in ticks (ngs) — also the timeline advance
                       (raven note_set: vol=b0, ngg=b1, ngs=b2)
    opcode >= 0xD0     a command; see OPCODE_NAMES
    00 00 FE FF        end of track

Opcode semantics decoded from KieronJ/raven, a C port of Kazuki Muraoka's PS2
sound library — the same driver used in MGS2 and Zone of Enders.
"""

import os
import struct
from dataclasses import dataclass, field
from typing import List, Optional, Tuple

from ..codec import psadpcm

# ─────────────────────────────────────────────────────────────────────────────
# Constants
# ─────────────────────────────────────────────────────────────────────────────

DIRECTORY_START = 0x800
RECORD_SIZE = 16
TABLE_SIZE = 0x1000          # 256 cue records
SEQUENCE_SIZE = 0x6800
EVENT_SIZE = 4

TICKS_PER_SECOND = 30        # fallback only; real tempo comes from opcode 0xD0 (tempo_set)
MIDDLE_NOTE = 44             # deprecated: pitch now uses raven's freq_tbl (native at ~47.27)
SPU_BASE_RATE = 44100        # the PlayStation SPU's reference rate

END_EVENT = (0x00, 0x00, 0xFE, 0xFF)

# ── Known opcodes ────────────────────────────────────────────────────────────
# Parameter mapping from raven source (sd_sub1.c / cntl_tbl):
#   mdata2 = b2    mdata3 = b1    mdata4 = b0
# Opcodes below 0x80 are note-on events: opcode = pitch.

OP_TEMPO = 0xD0             # raven: tempo_set       — b2 = tempo (ticks/s = 44100/448 * b2/256)
OP_TEMPO_MOVE = 0xD1         # raven: tempo_move      — tempo slide
OP_PROGRAM = 0xD2            # raven: sno_set         — b2 = instrument
OP_SVL_SET = 0xD3            # raven: svl_set         — set voice level (retrigger)
OP_SVP_SET = 0xD4            # raven: svp_set         — set voice pan (retrigger)
OP_VOL_CHG = 0xD5           # raven: vol_chg         — b2 = track/voice volume (pvod = b2 << 8)
OP_VOL_MOVE = 0xD6           # raven: vol_move        — volume slide: b0 = target, b1 = speed
OP_ADS_SET = 0xD7            # raven: ads_set         — b0=sustain(4b), b1=decay(4b), b2=attack(7b inv)
OP_SRS_SET = 0xD8            # raven: srs_set         — b2=sustain_rate(7b inv)
OP_RRS_SET = 0xD9            # raven: rrs_set         — b2=release_rate(5b inv)

OP_PAN_SET = 0xDD           # raven: pan_set         — panf = signed(b1)+20 (0..40, 20=centre); b2=mode; b0 unused
OP_PAN_MOVE = 0xDE           # raven: pan_move        — pan slide: b0 = target, b1 = speed
OP_TRANS_SET = 0xDF         # raven: trans_set       — transpose: ptps = signed(b2) semitones (global)

OP_PITCH_BEND = 0xE0        # raven: detune_set      — tund = signed(b2)<<2 in 1/256-semitone → signed(b2)/64 semitones
OP_VIB_SET = 0xE1            # raven: vib_set         — vibrato: b0 = depth, b1 = rate, b2 = speed
OP_VIB_CHANGE = 0xE2         # raven: vib_change      — vibrato depth change
OP_RDM_SET = 0xE3            # raven: rdm_set         — random pitch: b0 = range
OP_PORTAMENTO = 0xE4         # raven: swp_set (no-op) — b0 = target pitch, b1 = glide time in ticks
OP_SWS_SET = 0xE5           # raven: sws_set         — pitch SWEEP: b2 hold, b1 count, b0 speed<<8 (not a transpose)
OP_POR_SET = 0xE6            # raven: por_set         — portamento: b0 = target, b1 = speed

OP_LP1_START = 0xE7          # raven: lp1_start       — loop 1 start (no params)
OP_LP1_END = 0xE8            # raven: lp1_end         — loop 1 end: b0 = freq_delta, b1 = vol_delta, b2 = count
OP_LP2_START = 0xE9          # raven: lp2_start       — loop 2 start (nested in loop 1)
OP_LP2_END = 0xEA            # raven: lp2_end         — loop 2 end: same layout as LP1_END
OP_LP3_START = 0xEB          # raven: l3s_set         — loop 3 start (song-level loop)
OP_LP3_END = 0xEC            # raven: l3e_set         — loop 3 end (jump to l3s or end)

OP_KAKKO_START = 0xED        # raven: kakko_start     — A-A-B bracket start
OP_KAKKO_END = 0xEE          # raven: kakko_end       — A-A-B bracket end

OP_TIE_SET = 0xF3            # raven: tie_set         — tie: b2 = mode (0=off, 1=on)
OP_WAIT = 0xF2               # raven: rest_set        — b2 = ticks
OP_REVERB_ON = 0xF6          # raven: eon_set         — reverb on per voice
OP_REVERB_OFF = 0xF7         # raven: eof_set         — reverb off

OP_END = 0xFF                # raven: block_end       — end of track

# Confirmed no-ops (explicit no_cmd or /* do nothing */ in raven's cntl_tbl)
OP_NOP_DA = 0xDA
OP_NOP_DB = 0xDB
OP_NOP_DC = 0xDC
OP_NOP_EF = 0xEF
OP_NOP_F0 = 0xF0
OP_NOP_F1 = 0xF1             # raven: use_set (no-op)
OP_NOP_F4 = 0xF4             # raven: echo_set1 (no-op)
OP_NOP_F5 = 0xF5             # raven: echo_set2 (no-op)
OP_NOP_F8 = 0xF8
OP_NOP_F9 = 0xF9
OP_NOP_FA = 0xFA
OP_NOP_FB = 0xFB
OP_NOP_FC = 0xFC
OP_NOP_FD = 0xFD
OP_NOP_FE = 0xFE

OPCODE_NAMES = {
    OP_TEMPO: "tempo set",
    OP_TEMPO_MOVE: "tempo move",
    OP_PROGRAM: "program (sno set)",
    OP_SVL_SET: "svl set",
    OP_SVP_SET: "svp set",
    OP_VOL_CHG: "volume change (vol chg)",
    OP_VOL_MOVE: "vol move",
    OP_ADS_SET: "ads set (sustain/decay/attack)",
    OP_SRS_SET: "srs set (sustain rate)",
    OP_RRS_SET: "rrs set (release rate)",
    OP_NOP_DA: "no-op",
    OP_NOP_DB: "no-op",
    OP_NOP_DC: "no-op",
    OP_PAN_SET: "pan set",
    OP_PAN_MOVE: "pan move",
    OP_TRANS_SET: "trans set",
    OP_PITCH_BEND: "pitch bend (detune set)",
    OP_VIB_SET: "vibrato",
    OP_VIB_CHANGE: "vib change",
    OP_RDM_SET: "random pitch",
    OP_PORTAMENTO: "portamento (no-op)",
    OP_SWS_SET: "pitch sweep (sws set)",
    OP_POR_SET: "por set",
    OP_LP1_START: "loop 1 start",
    OP_LP1_END: "loop 1 end",
    OP_LP2_START: "loop 2 start",
    OP_LP2_END: "loop 2 end",
    OP_LP3_START: "loop 3 start",
    OP_LP3_END: "loop 3 end",
    OP_KAKKO_START: "kakko start",
    OP_KAKKO_END: "kakko end",
    OP_NOP_EF: "no-op",
    OP_NOP_F0: "no-op",
    OP_NOP_F1: "no-op (use set)",
    OP_WAIT: "wait (rest set)",
    OP_TIE_SET: "tie",
    OP_NOP_F4: "no-op (echo set 1)",
    OP_NOP_F5: "no-op (echo set 2)",
    OP_REVERB_ON: "reverb on",
    OP_REVERB_OFF: "reverb off",
    OP_NOP_F8: "no-op",
    OP_NOP_F9: "no-op",
    OP_NOP_FA: "no-op",
    OP_NOP_FB: "no-op",
    OP_NOP_FC: "no-op",
    OP_NOP_FD: "no-op",
    OP_NOP_FE: "no-op",
    OP_END: "end of track",
}


def to_signed(value: int) -> int:
    """A parameter byte read as a signed semitone offset."""
    return value - 256 if value > 127 else value


# ─────────────────────────────────────────────────────────────────────────────
# Representation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class Instrument:
    """One entry of the directory: where a sample lives, and how it is tuned."""
    index: int
    offset: int              # relative to the start of the audio
    tune: float = 0.0        # semitones correction; signed fixed point (sample_note/tune)
    default_pan: int = 10    # WAVE_W.pan (byte 14); panf = pan*2 on the 0..40 scale
    adsr: tuple = (0x7F, 0x00, 0x00, 0x0F, 0x19)   # WAVE_W (ar, dr, sr, sl, rr) defaults
    env_modes: tuple = (0, 0, 0)   # WAVE_W (a_mode, s_mode, r_mode): linear/exponential
    size: int = 0            # bytes, found by walking to the VAG end flag
    loop_frame: int = 0      # frame the sample loops back to while a note holds
    end_flag: int = 0        # flags of the sample's final frame

    @property
    def loop_sample(self) -> int:
        return self.loop_frame * psadpcm.SAMPLES_PER_FRAME

    @property
    def loops(self) -> bool:
        """Only samples whose final frame carries FLAG_LOOP repeat.

        Voices and one-shot effects end on FLAG_END alone and must fall silent;
        a stray FLAG_LOOP_START earlier in the sample does not make them loop.
        """
        return bool(self.end_flag & psadpcm.FLAG_LOOP)


@dataclass
class Event:
    b0: int
    b1: int
    b2: int
    opcode: int

    @property
    def is_note(self) -> bool:
        return self.opcode < 0x80

    # Note fields, named for what they mean in the PC Master Collection layout
    @property
    def pitch(self) -> int:
        return self.opcode

    @property
    def velocity(self) -> int:
        return self.b0

    @property
    def gate_pct(self) -> int:
        """Percentage of the gate before key-off.  100 = full sustain."""
        return self.b1

    @property
    def length(self) -> int:
        """Note length in ticks (raven `ngs`); also how far the timeline advances."""
        return self.b2


@dataclass
class Cue:
    """One playable thing: a jingle, a musical phrase, a layered sound effect."""
    index: int
    kind: int
    flags: Tuple[int, int]
    tracks: List[int]        # offsets into the sequence

    @property
    def track_count(self) -> int:
        return len(self.tracks)


@dataclass
class SequenceBank:
    """A `.sdx` seen as a sequencer: instruments, cues, and their events."""
    path: str
    raw: bytes
    audio_start: int
    audio_end: int
    table_start: int
    sequence_start: int
    sequence_end: int
    instruments: List[Instrument] = field(default_factory=list)
    cues: List[Cue] = field(default_factory=list)

    def track(self, addr: int, limit: int = 4096) -> List[Event]:
        """The events of one track, stopping at (and excluding) its end marker."""
        events = []
        pos = self.sequence_start + addr
        while pos + EVENT_SIZE <= self.sequence_end and len(events) < limit:
            b0, b1, b2, op = self.raw[pos:pos + EVENT_SIZE]
            if op == OP_END:
                break
            events.append(Event(b0, b1, b2, op))
            pos += EVENT_SIZE
        return events

    def note_count(self, cue: Cue) -> int:
        return sum(1 for addr in cue.tracks for e in self.track(addr)
                   if e.is_note and e.velocity > 0)

    def sample_bytes(self, instrument: Instrument) -> bytes:
        start = self.audio_start + instrument.offset
        return self.raw[start:start + instrument.size]

    def decode_instrument(self, instrument: Instrument) -> List[int]:
        return psadpcm.decode_psadpcm(self.sample_bytes(instrument))


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def _is_directory_record(raw: bytes, off: int) -> bool:
    """The directory's genuinely fixed fields, used to find where it stops.

    Only these eight bytes are invariant across a real directory. An earlier
    version also demanded `+7 == 0x7F` and `+13/+14 == 0x19/0x0A`, but those are
    the entry's **attack rate, release rate and pan** — merely the values most
    instruments happen to use. Measured over one bank's 149 entries: `+7` is
    0x7F for 147 of them, `+13` is 0x19 for 145, `+14` is 0x0A for 146.

    Treating those defaults as constants ended the directory at the first
    instrument with a custom envelope, which lost every entry after it *and* —
    because the audio begins where the directory ends — shifted every sample
    offset by the missing entries. On the game's music banks that misread 23 of
    68 directories and left almost every instrument reading 15 frames into the
    previous sample.
    """
    if off + RECORD_SIZE > len(raw):
        return False
    return (raw[off + 3] == 0x00         # high byte of the sample offset
            and raw[off + 6] == 0x00     # a_mode
            and raw[off + 8] == 0x00     # dr
            and raw[off + 9] == 0x00     # s_mode
            and raw[off + 10] == 0x00    # sr
            and raw[off + 11] == 0x0F    # sl
            and raw[off + 12] == 0x00    # r_mode
            and raw[off + 15] == 0x00)


def _find_padding(raw: bytes, audio_start: int) -> Optional[int]:
    """The frame-aligned run of 0xFE (or 0xFF) that closes the audio."""
    for off in range(audio_start, len(raw) - psadpcm.FRAME_SIZE + 1, psadpcm.FRAME_SIZE):
        frame = raw[off:off + psadpcm.FRAME_SIZE]
        if frame in (b"\xfe" * psadpcm.FRAME_SIZE, b"\xff" * psadpcm.FRAME_SIZE):
            return off
    return None


def _walk_sample(raw: bytes, start: int, limit: int) -> Tuple[int, int, int]:
    """Follow a sample to its end flag.

    Returns (size in bytes, loop frame, flags of the final frame). A sample opens
    with a silent frame — the VAG convention — so the walk starts at frame 1. It
    ends on the first frame whose flag carries the end bit.
    """
    frame = 1
    loop = 0
    while start + (frame + 1) * psadpcm.FRAME_SIZE <= limit:
        flags = raw[start + frame * psadpcm.FRAME_SIZE + 1]
        if flags & psadpcm.FLAG_LOOP_START and loop == 0:
            loop = frame
        if flags & psadpcm.FLAG_END:
            return (frame + 1) * psadpcm.FRAME_SIZE, loop, flags
        frame += 1
    return 0, 0, 0


# A directory closes with a **terminator record** that occupies a slot without
# carrying the structural signature. It is easy to overlook and expensive to
# miss: the audio begins where the directory ends, so skipping the terminator
# starts the audio one frame early and every instrument decodes from the tail of
# its neighbour.
#
# It is detected by measuring, not guessing. The format gives each sample a
# silent lead-in frame (the VAG convention), so with the right end the lead-in
# holds for essentially every instrument. On the game's banks the split is
# absolute: all 68 music banks reach ~100 % aligned with the terminator counted,
# and none of the 532 SE banks qualify (their 0x800 table holds SPU addresses,
# so the measure does not apply to them at all).
_LEAD_IN_MIN = 0.9


def _lead_in_fraction(raw: bytes, records: int) -> float:
    """How many of the directory's samples begin on a silent VAG lead-in frame."""
    audio_start = DIRECTORY_START + records * RECORD_SIZE
    silent = total = 0
    blank = b"\x00" * (psadpcm.FRAME_SIZE - 2)
    for i in range(1, records):
        off = struct.unpack_from("<I", raw, DIRECTORY_START + i * RECORD_SIZE)[0]
        start = audio_start + off
        frame = raw[start:start + psadpcm.FRAME_SIZE]
        if len(frame) < psadpcm.FRAME_SIZE:
            continue
        total += 1
        if frame[2:] == blank:
            silent += 1
    return silent / total if total else 0.0


def _audio_start(raw: bytes, count: int) -> int:
    """Where the audio begins, counting the directory's terminator record."""
    plain = DIRECTORY_START + count * RECORD_SIZE
    with_terminator = plain + RECORD_SIZE
    aligned = _lead_in_fraction(raw, count + 1)
    if aligned >= _LEAD_IN_MIN and aligned > _lead_in_fraction(raw, count):
        return with_terminator
    return plain


def has_sequence(raw: bytes) -> bool:
    """True when the bank carries an instrument directory, and so a sequence."""
    return _is_directory_record(raw, DIRECTORY_START + RECORD_SIZE)


def _cue_run_length(raw: bytes, t: int) -> int:
    """How many valid cue records sit at table offset `t` (0 if it isn't a table).

    A real table is a run of cue records (n∈1..3, the first n track pointers set
    and the rest 0xFFFFFFFF, pointers landing inside the sequence that follows),
    padded out with empty 0xFFFFFFFF slots. Used to locate the table generically
    when it isn't at the usual fixed offset from the end (varies across stages).
    """
    fsize = len(raw)
    seq_start = t + TABLE_SIZE
    if seq_start >= fsize:
        return 0
    seq_span = fsize - seq_start
    valid = 0
    for r in range(256):
        rec = t + r * 16
        if rec + 16 > fsize:
            break
        n = raw[rec + 1]
        addrs = struct.unpack_from("<III", raw, rec + 4)
        if n in (1, 2, 3):
            if any(a == 0xFFFFFFFF for a in addrs[:n]):
                break
            if any(a != 0xFFFFFFFF for a in addrs[n:]):
                break
            if any(a >= seq_span for a in addrs[:n]):
                break
            valid += 1
        elif raw[rec:rec + 16] == b"\xff" * 16:
            continue            # empty slot — fine inside the table
        else:
            break
    return valid


def _events_look_valid(raw: bytes, seq_start: int, addr: int, n: int = 12) -> bool:
    """True if `n` events read at seq_start+addr look like a real track."""
    pos = seq_start + addr
    real = 0
    for _ in range(n):
        if pos + 4 > len(raw):
            break
        op = raw[pos + 3]
        if op == 0xFF:          # block end
            break
        if not (op < 0x80 or 0xD0 <= op <= 0xFE):
            return False        # not a note and not a command opcode
        if op != 0:
            real += 1
        pos += 4
    return real >= 3            # at least a few genuine events


def _scan_cue_table(raw: bytes, audio_end: int) -> int:
    """Find the cue table by structure when the fixed offset misses it.

    Requires both a run of valid cue records *and* that the sequence they point
    into actually contains events — this rejects table-shaped noise elsewhere.
    """
    fsize = len(raw)
    lo = max(audio_end, fsize - 0x12000)
    best_t, best_run = -1, 0
    for t in range(lo, fsize - TABLE_SIZE, 0x10):
        run = _cue_run_length(raw, t)
        if run <= best_run:
            continue
        seq_start = t + TABLE_SIZE
        first_addr = struct.unpack_from("<I", raw, t + 4)[0]      # cue 0, track 0
        if first_addr == 0xFFFFFFFF or not _events_look_valid(raw, seq_start, first_addr):
            continue
        best_run, best_t = run, t
    return best_t if best_run >= 1 else -1


def _find_cue_table(raw: bytes, audio_end: int = 0) -> int:
    """Locate the cue table, either at a fixed offset from the end or after the audio padding.

    Real MGS2 banks place the table at `fsize - 0x6800`; other stages vary, so a
    structural scan is used as a fallback.  Returns the byte offset, or -1.
    """
    fsize = len(raw)

    # Preferred: fixed offset from end (used by the MGS2 pk banks)
    table = fsize - 0x6800
    if table >= 0 and table + TABLE_SIZE <= fsize:
        for i in range(min(5, 256)):
            if raw[table + i * 16 + 1] in (1, 2, 3):
                return table

    # Fallback: after the 0xFE/0xFF padding (used by synthetic test fixtures)
    for audio_start in range(0x800, min(0x2000, fsize - 0x200), 0x10):
        pad = _find_padding(raw, audio_start)
        if pad is not None:
            pad_byte = raw[pad]
            t = pad
            while t < fsize and raw[t] == pad_byte:
                t += 1
            if t + TABLE_SIZE <= fsize:
                if raw[t + 1] in (1, 2, 3):
                    return t

    # Last resort: scan for the table by its record structure (variable offset)
    return _scan_cue_table(raw, audio_end)


def _parse_instruments(raw: bytes, bank: "SequenceBank", count: int,
                       audio_start: int, padding: int) -> None:
    """Fill bank.instruments from the WAVE_W directory."""
    for i in range(count):
        rec = DIRECTORY_START + i * RECORD_SIZE
        offset = struct.unpack_from("<I", raw, rec)[0]
        # Bytes 4 and 5 are the instrument's pitch correction, both signed
        # (raven WAVE_W.sample_note / sample_tune): byte 4 = whole semitones
        # (macro), byte 5 = fine tune in 1/256 semitone (micro).
        coarse = to_signed(raw[rec + 4])
        tune = coarse + to_signed(raw[rec + 5]) / 256.0
        default_pan = raw[rec + 14]                       # WAVE_W.pan
        # WAVE_W default envelope: ar(+7) dr(+8) sr(+10) sl(+11) rr(+13)
        adsr = (raw[rec + 7], raw[rec + 8], raw[rec + 10], raw[rec + 11], raw[rec + 13])
        env_modes = (raw[rec + 6], raw[rec + 9], raw[rec + 12])   # a_mode, s_mode, r_mode
        size, loop, end = _walk_sample(raw, audio_start + offset, padding)
        bank.instruments.append(
            Instrument(index=i, offset=offset, tune=tune, default_pan=default_pan,
                       adsr=adsr, env_modes=env_modes, size=size, loop_frame=loop,
                       end_flag=end))


def parse_sequence(path: str) -> SequenceBank:
    """Read a `.sdx` as a sequencer bank. Raises ValueError when it isn't one."""
    with open(path, "rb") as f:
        raw = f.read()

    if not has_sequence(raw):
        raise ValueError(f"{path}: no instrument directory — not a sequencer bank")

    # The directory runs until its fixed fields stop matching; the audio follows.
    count = 1
    off = DIRECTORY_START + RECORD_SIZE
    while _is_directory_record(raw, off):
        count += 1
        off += RECORD_SIZE
    # `count` is the number of instruments; the audio starts after the
    # directory, which may close with a terminator record (see _audio_start).
    audio_start = _audio_start(raw, count)

    padding = _find_padding(raw, audio_start)
    if padding is None:
        raise ValueError(f"{path}: no padding after the audio")

    table = _find_cue_table(raw, padding if padding is not None else 0)

    # Build the bank; instruments are always parsed. If no cue table can be found
    # (SE-only stage banks, or an unrecognised layout), degrade to zero cues
    # rather than raising, so sample-level features still work.
    if table < 0:
        bank = SequenceBank(path=path, raw=raw, audio_start=audio_start,
                            audio_end=padding, table_start=-1,
                            sequence_start=len(raw), sequence_end=len(raw))
        _parse_instruments(raw, bank, count, audio_start, padding)
        return bank

    sequence = table + TABLE_SIZE
    seq_end = min(len(raw), sequence + SEQUENCE_SIZE)

    bank = SequenceBank(path=path, raw=raw, audio_start=audio_start,
                        audio_end=padding, table_start=table,
                        sequence_start=sequence, sequence_end=seq_end)

    _parse_instruments(raw, bank, count, audio_start, padding)

    index = 0
    for rec in range(table, sequence, RECORD_SIZE):
        kind, n, f1, f2 = raw[rec:rec + 4]
        if n not in (1, 2, 3):
            continue
        addrs = [struct.unpack_from("<I", raw, rec + 4 + 4 * k)[0] for k in range(3)]
        if any(a == 0xFFFFFFFF for a in addrs[:n]):
            continue
        if any(a != 0xFFFFFFFF for a in addrs[n:]):
            continue
        bank.cues.append(Cue(index=index, kind=kind, flags=(f1, f2),
                             tracks=addrs[:n]))
        index += 1

    return bank


# ─────────────────────────────────────────────────────────────────────────────
# Human-readable summary
# ─────────────────────────────────────────────────────────────────────────────

def describe(bank: SequenceBank) -> str:
    playable = sum(1 for i in bank.instruments if i.size > 0)
    return (
        f"File        : {os.path.basename(bank.path)}\n"
        f"Instruments : {playable} of {len(bank.instruments)} directory slots\n"
        f"Audio       : {bank.audio_start:#x} .. {bank.audio_end:#x}\n"
        f"Cue table   : {bank.table_start:#x}\n"
        f"Sequence    : {bank.sequence_start:#x} .. {bank.sequence_end:#x}\n"
        f"Cues        : {len(bank.cues)}"
    )


def list_cues(bank: SequenceBank, min_notes: int = 1) -> str:
    rows = [f"{'cue':>4}  {'kind':>5}  {'tracks':>7}  notes"]
    for cue in bank.cues:
        n = bank.note_count(cue)
        if n < min_notes:
            continue
        rows.append(f"{cue.index:>4}  {cue.kind:#05x}  {cue.track_count:>7}  {n}")
    return "\n".join(rows)
