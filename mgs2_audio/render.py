#!/usr/bin/env python3
"""
render.py — Play a cue from a `.sdx` sequencer bank.

A small software SPU: each track owns one voice, samples loop while a note is
held, tracks play simultaneously, gate percentage key-off shapes note duration,
and all 29 opcodes shape volume, pitch, stereo position, loops, vibrato,
portamento, and reverb — decoded from the KieronJ/raven C port of Kazuki
Muraoka's PS2 sound library (the same driver used in MGS2 and ZOE).

Note field usage (raven note_set): `b0` = volume/velocity (0..127), `b1` = gate
percentage (when to key off during the note), `b2` = note length in ticks — the
length also governs how far the timeline advances to the next event.

Tempo (raven): opcode 0xD0 sets `tmp`; the driver's per-frame accumulator raises
a musical tick whenever it overflows 8 bits, so with sd_tick running once every
STEP_SIZE (448) samples of 44100 Hz output:
    ticks_per_second = (44100 / 448) * tmp / 256

Pure Python, no dependencies.
"""

import math
from typing import List, Optional, Tuple

from .formats import sequence as seq
from .formats.sequence import Cue, SequenceBank

OUTPUT_RATE = 22050
CUT_SAMPLES = 120
MAX_SECONDS = 120
_LOOP_MAX_PASSES = 1024      # safety cap for infinite (count=0) loops
_MAX_EVENTS = 100000         # abort if a track processes more than this

# Tempo → tick rate.  raven's sd_tick() runs once per STEP_SIZE (448) samples of
# 44100 Hz SPU output, i.e. at 44100/448 ≈ 98.44 Hz.  A musical tick elapses when
# the per-frame accumulator (tmpd += tmp) overflows 8 bits, every 256/tmp frames.
_DRIVER_RATE = 44100 / 448
def _tempo_to_tps(tempo: int) -> float:
    return _DRIVER_RATE * max(1, tempo) / 256.0

# raven's pan→volume table (sd_ioset.c `pant[41]`), indexed by pan 0..40.
# vol_r = vol * pant[pan] ; vol_l = vol * pant[40-pan]. Not constant-power: the
# centre (pan 20) sits at 80/127 ≈ 0.63, and the taper is a specific curve.
_PANT = [
    0,   2,   4,   7,   10,  13,  16,  20,  24,  28,  32,  36,  40,  45,
    50,  55,  60,  65,  70,  75,  80,  84,  88,  92,  96,  100, 104, 107,
    110, 112, 114, 116, 118, 120, 122, 123, 124, 125, 126, 127, 127,
]

# raven's semitone → SPU-pitch table (sd_ioset.c freq_tbl). 0x1000 = native rate,
# which falls at index ~47.27 — that is the true global reference, replacing the
# old ear-tuned MIDDLE_NOTE. Indices 72+ are raven's low "wrap" region.
_FREQ_TBL = [
    0x010B, 0x011B, 0x012C, 0x013E, 0x0151, 0x0165, 0x017A, 0x0191,
    0x01A9, 0x01C2, 0x01DD, 0x01F9, 0x0217, 0x0237, 0x0259, 0x027D,
    0x02A3, 0x02CB, 0x02F5, 0x0322, 0x0352, 0x0385, 0x03BA, 0x03F3,
    0x042F, 0x046F, 0x04B2, 0x04FA, 0x0546, 0x0596, 0x05EB, 0x0645,
    0x06A5, 0x070A, 0x0775, 0x07E6, 0x085F, 0x08DE, 0x0965, 0x09F4,
    0x0A8C, 0x0B2C, 0x0BD6, 0x0C8B, 0x0D4A, 0x0E14, 0x0EEA, 0x0FCD,
    0x10BE, 0x11BD, 0x12CB, 0x13E9, 0x1518, 0x1659, 0x17AD, 0x1916,
    0x1A94, 0x1C28, 0x1DD5, 0x1F9B, 0x217C, 0x237A, 0x2596, 0x27D2,
    0x2A30, 0x2CB2, 0x2F5A, 0x322C, 0x3528, 0x3850, 0x3BAC, 0x3F36,
    0x0021, 0x0023, 0x0026, 0x0028, 0x002A, 0x002D, 0x002F, 0x0032,
    0x0035, 0x0038, 0x003C, 0x003F, 0x0042, 0x0046, 0x004B, 0x004F,
    0x0054, 0x0059, 0x005E, 0x0064, 0x006A, 0x0070, 0x0077, 0x007E,
    0x0085, 0x008D, 0x0096, 0x009F, 0x00A8, 0x00B2, 0x00BD, 0x00C8,
    0x00D4, 0x00E1, 0x00EE, 0x00FC,
]

def _freq_ratio(index_semitones: float) -> float:
    """Playback ratio for a note index, via raven's freq_tbl (freq_set)."""
    base = int(round(index_semitones * 256.0))
    if base < 0:
        base = 0
    frac = base & 0xFF
    idx = (base >> 8) & 0x7F
    if idx > len(_FREQ_TBL) - 2:
        idx = len(_FREQ_TBL) - 2
    delta = _FREQ_TBL[idx + 1] - _FREQ_TBL[idx]
    if delta < 0:                      # raven's cliff guard at the 71→72 boundary
        delta = 0xC9
    freq = _FREQ_TBL[idx] + (delta * frac) / 256.0
    return freq / 4096.0               # 0x1000 = native rate


class _Move:
    """A tempo/volume/pan glissando (raven *_move): the value ramps linearly to
    `target` over `count` ticks in <<8 fixed point, then snaps to it."""
    __slots__ = ("value", "target", "ad", "count")

    def __init__(self, current: float, target: float, count: int):
        self.value = current * 256.0
        self.target = target
        if count > 0:
            self.count = count
            self.ad = (target * 256.0 - self.value) / count
        else:
            self.count = 0
            self.value = target * 256.0
            self.ad = 0.0

    def advance(self, ticks: int) -> None:
        if self.count <= 0:
            return
        n = ticks if ticks < self.count else self.count
        self.count -= n
        self.value = self.target * 256.0 if self.count <= 0 else self.value + self.ad * n

    @property
    def current(self) -> float:
        return self.value / 256.0

    @property
    def done(self) -> bool:
        return self.count <= 0

# 64-entry sine LUT (scaled [-32768, 32767]) matching the PS2 SPU
# raven's vibrato LFO waveform (sd_sub1.c VIBX_TBL, 32 entries, second half mirrored).
_VIBX_TBL = [
    0,   32,  56,  80,  104, 128, 144, 160,
    176, 192, 208, 224, 232, 240, 240, 248,
    255, 248, 244, 240, 232, 224, 208, 192,
    176, 160, 144, 128, 104, 80,  56,  32,
]

# PS1 SPU 512-entry gaussian interpolation table for pitch-shifted playback.
# Generated from the formula posted by Ryphecha/nocash (nesdev 2020):
#   k = 0.5 + n
#   s = sin(pi * k * 2.048 / 1024)
#   t = (cos(pi * k * 2.000 / 1023) - 1) * 0.50
#   u = (cos(pi * k * 4.000 / 1023) - 1) * 0.08
#   r = s * (t + u + 1.0) / k
# Scaled so that for any phase, gauss[a] + gauss[b] + gauss[c] + gauss[d] ≈ 0x7F80.
def _build_gauss_table():
    _t = [0.0] * 512
    for n in range(512):
        k = 0.5 + n
        s = math.sin(math.pi * k * 2.048 / 1024.0)
        t = (math.cos(math.pi * k * 2.000 / 1023.0) - 1.0) * 0.50
        u = (math.cos(math.pi * k * 4.000 / 1023.0) - 1.0) * 0.08
        r = s * (t + u + 1.0) / k
        _t[511 - n] = r
    total = sum(_t)
    scale = 0x7f80 * 128 / total
    for n in range(512):
        _t[n] *= scale
    g = [0] * 512
    for p in range(128):
        s = _t[p] + _t[p + 256] + _t[511 - p] + _t[255 - p]
        diff = (s - 0x7f80) / 4.0
        g[p]         = int(round(_t[p] - diff))
        g[p + 256]   = int(round(_t[p + 256] - diff))
        g[511 - p]   = int(round(_t[511 - p] - diff))
        g[255 - p]   = int(round(_t[255 - p] - diff))
    return tuple(g)

_GAUSS_TABLE = _build_gauss_table()


# ─────────────────────────────────────────────────────────────────────────────
# PS1 SPU ADSR envelope (authentic state machine)
# ─────────────────────────────────────────────────────────────────────────────

class SPU_ADSR:
    """Authentic PS1 SPU ADSR envelope generator.

    Matches DuckStation's VolumeEnvelope / TickADSR logic, which is derived
    from nocash's psx-spx docs and hardware tests.  Uses the same step +
    counter-increment rate decode that the real SPU hardware implements.
    """

    # Modes — same constants as spu.h
    LIN_INC = 1
    LIN_DEC = 3
    EXP_INC = 5
    EXP_DEC = 7

    ATTACK, DECAY, SUSTAIN, RELEASE, OFF = range(5)

    def __init__(self):
        self.reset()

    def reset(self):
        self.phase = self.OFF
        self.env = 0                # 0–0x7FFF  (signed 16-bit range)
        self.counter = 0
        self.rate = 0
        self._step = 0              # signed step applied per update
        self._incr = 0x8000         # counter increment per tick
        self.decreasing = False
        self.exponential = False
        self._rate_mask = 0x7F
        # cached target for phase-transition checks
        self._target = 0

    # ── SPU rate→step/internals  (VolumeEnvelope::Reset) ─────────────────

    def _set_rate(self, rate, rate_mask, decreasing, exponential, target):
        self.rate = rate
        self._rate_mask = rate_mask
        self.decreasing = decreasing
        self.exponential = exponential
        self._target = target
        self.counter = 0
        self._incr = 0x8000

        base = 7 - (rate & 3)
        if decreasing:
            step = -base
        else:
            step = base

        if rate < 44:
            step <<= (11 - (rate >> 2))
        elif rate >= 48:
            self._incr >>= ((rate >> 2) - 11)
            if (rate & rate_mask) != rate_mask:
                self._incr = max(self._incr, 1)

        self._step = step

    # ── Phase transitions ────────────────────────────────────────────────

    def key_on(self, ar, dr, sl, mode=LIN_INC):
        self.phase = self.ATTACK
        self.env = 0
        self.counter = 0
        self._ar = ar & 0x7F
        self._dr = dr & 0x0F
        self._sl = sl & 0x0F
        self._a_mode = mode
        self._s_mode = self.LIN_DEC
        self._sr = 0x7F        # default: hold (no sustain decay)
        self._rr = 0x1F        # default: hold (no release)
        self._r_mode = self.LIN_DEC
        self._config_phase()

    def key_off(self, rr, r_mode=LIN_DEC):
        self._rr = rr & 0x1F
        self._r_mode = r_mode
        if self.env == 0 or self.phase == self.OFF:
            self.phase = self.OFF
        else:
            self.phase = self.RELEASE
        self._config_phase()

    def set_sustain(self, sr, s_mode=LIN_DEC):
        self._sr = sr & 0x7F
        self._s_mode = s_mode
        if self.phase == self.SUSTAIN:
            self._config_phase()

    def set_decay_sl(self, sl):
        self._sl = sl & 0x0F
        if self.phase == self.DECAY:
            self._config_phase()

    def _config_phase(self):
        if self.phase == self.ATTACK:
            self._set_rate(self._ar, 0x7F, False,
                           self._a_mode == self.EXP_INC, 0x7FFF)
        elif self.phase == self.DECAY:
            t = min((self._sl + 1) * 0x800, 0x7FFF)
            self._set_rate(self._dr << 2, 0x7C, True, True, t)
        elif self.phase == self.SUSTAIN:
            inc = self._s_mode in (self.LIN_INC, self.EXP_INC)
            exp = self._s_mode in (self.EXP_INC, self.EXP_DEC)
            self._set_rate(self._sr, 0x7F, not inc, exp, 0)
        elif self.phase == self.RELEASE:
            self._set_rate(self._rr << 2, 0x7C, True,
                           self._r_mode == self.EXP_DEC, 0)
        else:
            pass  # OFF

    # ── Per-sample tick ──────────────────────────────────────────────────

    def tick(self):
        if self.phase == self.OFF:
            if self.env > 0:
                self.env = 0
            return

        incr = self._incr
        step = self._step

        if self.exponential:
            if self.decreasing:
                step = (step * self.env) >> 15
            elif self.env >= 0x6000:
                if self.rate < 40:
                    step >>= 2
                elif self.rate >= 44:
                    incr >>= 2
                else:
                    step >>= 1
                    incr >>= 1

        self.counter += incr
        if not (self.counter & 0x8000):
            return

        self.counter = 0
        self.env += step

        if self.decreasing:
            self.env = max(0, self.env)
        else:
            self.env = max(-0x8000, min(0x7FFF, self.env))

        if self.phase == self.ATTACK and self.env >= 0x7FFF:
            self.phase = self.DECAY
            self._config_phase()
        elif self.phase == self.DECAY and self.env <= self._target:
            self.phase = self.SUSTAIN
            self._config_phase()
        elif self.phase == self.RELEASE and self.env <= 0:
            self.phase = self.OFF

    @property
    def env_norm(self):
        return max(0, self.env) / 32767.0

    @property
    def is_active(self):
        return self.phase != self.OFF


# ─────────────────────────────────────────────────────────────────────────────
# PS1 SPU Reverb (authentic multi-tap hardware reverb)
# ─────────────────────────────────────────────────────────────────────────────

# Reverb presets from psx-spx: each is 22 u16 values:
#   dAPF1 dAPF2 vIIR vCOMB1 vCOMB2 vCOMB3 vCOMB4 vWALL
#   vAPF1 vAPF2 mLSAME mRSAME mLCOMB1 mRCOMB1 mLCOMB2 mRCOMB2
#   dLSAME dRSAME mLDIFF mRDIFF mLCOMB3 mRCOMB3 mLCOMB4 mRCOMB4
#   dLDIFF dRDIFF mLAPF1 mRAPF1 mLAPF2 mRAPF2 vLIN vRIN
# vLOUT, vROUT, mBASE are set separately.


def _reverb_preset(bufsize, vLOUT, vROUT, *rows):
    """Build a preset dict from 3 or 4 rows of 8 hex register values."""
    regs = []
    for r in rows:
        if isinstance(r, str):
            regs.extend(int(x, 16) for x in r.split(","))
        else:
            regs.extend(r)
    if len(regs) >= 32:
        return {"bufsize": bufsize, "regs": regs,
                "vLOUT": vLOUT, "vROUT": vROUT, "mBASE": 0x1000}
    # Pad to 32 with zeros; default vLIN/vRIN to 0x8000 (inverted unity)
    regs_32 = list(regs) + [0] * (32 - len(regs))
    regs_32[30] = 0x8000  # vLIN
    regs_32[31] = 0x8000  # vRIN
    return {"bufsize": bufsize, "regs": regs_32,
            "vLOUT": vLOUT, "vROUT": vROUT, "mBASE": 0x1000}

R = _reverb_preset

REVERB_OFF = R(0x10, 0, 0,
    "0001,0001,7FFF,7FFF,0000,0000,0000,0000",
    "0000,0000,0000,0000,0000,0000,0000,0000",
    "0000,0000,0000,0000,0000,0000,0000,0000",
    "0000,0000,0000,0000,0000,0000,0000,0000")

REVERB_ROOM = R(0x26C0, 0x4000, 0x4000,
    "007D,005B,6D80,54B8,BED0,0000,0000,BA80",
    "5800,5300,04D6,0333,03F0,0227,0374,01EF",
    "0334,01B5,0000,0000,0000,0000,0000,0000")

REVERB_STUDIO_SMALL = R(0x1F40, 0x4000, 0x4000,
    "0033,0025,70F0,4FA8,BCE0,4410,C0F0,9C00",
    "5280,4EC0,03E4,031B,03A4,02AF,0372,0266",
    "031C,025D,025C,018E,022F,0135,0000,0000")

REVERB_STUDIO_MEDIUM = R(0x4840, 0x4000, 0x4000,
    "00B1,007F,70F0,4FA8,BCE0,4510,BEF0,B4C0",
    "5280,4EC0,0904,076B,0824,065F,07A2,0616",
    "076C,05ED,05EC,042E,050F,0305,0000,0000")

REVERB_STUDIO_LARGE = R(0x6FE0, 0x4000, 0x4000,
    "00E3,00A9,6F60,4FA8,BCE0,4510,BEF0,A680",
    "5680,52C0,0DFB,0B58,0D09,0A3C,0BD9,0973",
    "0B59,08DA,08D9,05E9,07EC,04B0,06EF,03D2",
    "05EA,031D,031C,0238,0154,00AA,8000,8000")

REVERB_HALL = R(0xADE0, 0x4000, 0x4000,
    "01A5,0139,6000,5000,4C00,B800,BC00,C000",
    "6000,5C00,15BA,11BB,14C2,10BD,11BC,0DC1",
    "11C0,0DC3,0DC0,09C1,0BC4,07C1,0A00,06CD",
    "09C2,05C1,05C0,041A,0274,013A,8000,8000")

REVERB_SPACE_ECHO = R(0xF6C0, 0x4000, 0x4000,
    "033D,0231,7E00,5000,B400,B000,4C00,B000",
    "6000,5400,1ED6,1A31,1D14,183B,1BC2,16B2",
    "1A32,15EF,15EE,1055,1334,0F2D,11F6,0C5D",
    "0D1E,086D,086C,05D5,0395,01CA,8000,8000")

REVERB_PRESETS = {
    "off": REVERB_OFF,
    "room": REVERB_ROOM,
    "studio_small": REVERB_STUDIO_SMALL,
    "studio_medium": REVERB_STUDIO_MEDIUM,
    "studio_large": REVERB_STUDIO_LARGE,
    "hall": REVERB_HALL,
    "space_echo": REVERB_SPACE_ECHO,
}


class SPU_Reverb:
    """PS1 SPU authentic reverb unit (multi-tap IIR + comb + APF)."""

    def __init__(self, preset: dict = None):
        p = preset or REVERB_HALL
        regs = p["regs"]
        if len(regs) < 32:
            regs = list(regs) + [0] * (32 - len(regs))
        self.bufsize = p["bufsize"]
        # All 32 registers as signed 16-bit
        (self.dAPF1, self.dAPF2, self.vIIR, self.vCOMB1,
         self.vCOMB2, self.vCOMB3, self.vCOMB4, self.vWALL,
         self.vAPF1, self.vAPF2, self.mLSAME, self.mRSAME,
         self.mLCOMB1, self.mRCOMB1, self.mLCOMB2, self.mRCOMB2,
         self.dLSAME, self.dRSAME, self.mLDIFF, self.mRDIFF,
         self.mLCOMB3, self.mRCOMB3, self.mLCOMB4, self.mRCOMB4,
         self.dLDIFF, self.dRDIFF, self.mLAPF1, self.mRAPF1,
         self.mLAPF2, self.mRAPF2, self.vLIN, self.vRIN) = (_s16n(r) for r in regs)
        self.vLOUT = _s16n(p.get("vLOUT", 0x4000))
        self.vROUT = _s16n(p.get("vROUT", 0x4000))

        # Buffer of 16-bit signed samples, zero-filled
        self.buf = [0] * (max(self.bufsize, 4) // 2)  # word (16-bit) units
        self.pos = 0  # current word offset into buffer

        # Precompute read/write taps as WORD offsets (process is per-sample; this
        # hoists the `//2` and cuts attribute lookups out of the hot loop).
        self._w_dLSAME = self.dLSAME // 2
        self._w_dRSAME = self.dRSAME // 2
        self._w_dRDIFF = self.dRDIFF // 2
        self._w_dLDIFF = self.dLDIFF // 2
        self._w_mLSAME = self.mLSAME // 2
        self._w_mRSAME = self.mRSAME // 2
        self._w_mLDIFF = self.mLDIFF // 2
        self._w_mRDIFF = self.mRDIFF // 2
        self._w_mLCOMB1 = self.mLCOMB1 // 2
        self._w_mLCOMB2 = self.mLCOMB2 // 2
        self._w_mLCOMB3 = self.mLCOMB3 // 2
        self._w_mLCOMB4 = self.mLCOMB4 // 2
        self._w_mRCOMB1 = self.mRCOMB1 // 2
        self._w_mRCOMB2 = self.mRCOMB2 // 2
        self._w_mRCOMB3 = self.mRCOMB3 // 2
        self._w_mRCOMB4 = self.mRCOMB4 // 2
        self._w_mLAPF1 = self.mLAPF1 // 2
        self._w_mRAPF1 = self.mRAPF1 // 2
        self._w_mLAPF2 = self.mLAPF2 // 2
        self._w_mRAPF2 = self.mRAPF2 // 2
        self._w_rdLAPF1 = (self.mLAPF1 - self.dAPF1) // 2
        self._w_rdRAPF1 = (self.mRAPF1 - self.dAPF1) // 2
        self._w_rdLAPF2 = (self.mLAPF2 - self.dAPF2) // 2
        self._w_rdRAPF2 = (self.mRAPF2 - self.dAPF2) // 2

    def _buf(self, offset: int) -> int:
        """Read a 16-bit sample at byte offset `offset` from buffer base."""
        idx = (self.pos + offset // 2) % len(self.buf)
        return self.buf[idx]

    def _set(self, offset: int, val: int):
        """Write a 16-bit sample at byte offset `offset`."""
        idx = (self.pos + offset // 2) % len(self.buf)
        self.buf[idx] = max(-32768, min(32767, val))

    def process(self, left_in: float, right_in: float) -> tuple:
        """One tick at 22050 Hz. Returns (left_out, right_out) as floats."""
        buf = self.buf
        blen = len(buf)
        pos = self.pos
        vw = self.vWALL
        viir = self.vIIR

        Lin = int(left_in * self.vLIN / 32768.0)
        Rin = int(right_in * self.vRIN / 32768.0)
        if Lin < -32768: Lin = -32768
        elif Lin > 32767: Lin = 32767
        if Rin < -32768: Rin = -32768
        elif Rin > 32767: Rin = 32767

        # Same-side reflection (L→L, R→R) and cross-side (L→R, R→L). Each of
        # the 4 outputs is written to its OWN address (mLSAME/mRSAME/mLDIFF/
        # mRDIFF) and reads its own "old" value at that address minus one word
        # (psx-spx §7.12) — they are four independent taps, not one shared slot.
        w_mLSAME = (pos + self._w_mLSAME) % blen
        old = buf[(w_mLSAME - 1) % blen]
        s = buf[(pos + self._w_dLSAME) % blen]
        v = ((Lin + (s * vw >> 15) - old) * viir >> 15) + old
        buf[w_mLSAME] = -32768 if v < -32768 else (32767 if v > 32767 else v)

        w_mRSAME = (pos + self._w_mRSAME) % blen
        old = buf[(w_mRSAME - 1) % blen]
        s = buf[(pos + self._w_dRSAME) % blen]
        v = ((Rin + (s * vw >> 15) - old) * viir >> 15) + old
        buf[w_mRSAME] = -32768 if v < -32768 else (32767 if v > 32767 else v)

        w_mLDIFF = (pos + self._w_mLDIFF) % blen
        old = buf[(w_mLDIFF - 1) % blen]
        s = buf[(pos + self._w_dRDIFF) % blen]
        v = ((Lin + (s * vw >> 15) - old) * viir >> 15) + old
        buf[w_mLDIFF] = -32768 if v < -32768 else (32767 if v > 32767 else v)

        w_mRDIFF = (pos + self._w_mRDIFF) % blen
        old = buf[(w_mRDIFF - 1) % blen]
        s = buf[(pos + self._w_dLDIFF) % blen]
        v = ((Rin + (s * vw >> 15) - old) * viir >> 15) + old
        buf[w_mRDIFF] = -32768 if v < -32768 else (32767 if v > 32767 else v)

        vc1, vc2, vc3, vc4 = self.vCOMB1, self.vCOMB2, self.vCOMB3, self.vCOMB4
        Lout = ((buf[(pos + self._w_mLCOMB1) % blen] * vc1 >> 15)
              + (buf[(pos + self._w_mLCOMB2) % blen] * vc2 >> 15)
              + (buf[(pos + self._w_mLCOMB3) % blen] * vc3 >> 15)
              + (buf[(pos + self._w_mLCOMB4) % blen] * vc4 >> 15))
        Rout = ((buf[(pos + self._w_mRCOMB1) % blen] * vc1 >> 15)
              + (buf[(pos + self._w_mRCOMB2) % blen] * vc2 >> 15)
              + (buf[(pos + self._w_mRCOMB3) % blen] * vc3 >> 15)
              + (buf[(pos + self._w_mRCOMB4) % blen] * vc4 >> 15))
        if Lout < -32768: Lout = -32768
        elif Lout > 32767: Lout = 32767
        if Rout < -32768: Rout = -32768
        elif Rout > 32767: Rout = 32767

        # All-pass 1
        va1 = self.vAPF1
        d = buf[(pos + self._w_rdLAPF1) % blen]
        new = Lout - (va1 * d >> 15)
        buf[(pos + self._w_mLAPF1) % blen] = -32768 if new < -32768 else (32767 if new > 32767 else new)
        Lout = (new * va1 >> 15) + d
        if Lout < -32768: Lout = -32768
        elif Lout > 32767: Lout = 32767
        d = buf[(pos + self._w_rdRAPF1) % blen]
        new = Rout - (va1 * d >> 15)
        buf[(pos + self._w_mRAPF1) % blen] = -32768 if new < -32768 else (32767 if new > 32767 else new)
        Rout = (new * va1 >> 15) + d
        if Rout < -32768: Rout = -32768
        elif Rout > 32767: Rout = 32767

        # All-pass 2
        va2 = self.vAPF2
        d = buf[(pos + self._w_rdLAPF2) % blen]
        new = Lout - (va2 * d >> 15)
        buf[(pos + self._w_mLAPF2) % blen] = -32768 if new < -32768 else (32767 if new > 32767 else new)
        Lout = (new * va2 >> 15) + d
        if Lout < -32768: Lout = -32768
        elif Lout > 32767: Lout = 32767
        d = buf[(pos + self._w_rdRAPF2) % blen]
        new = Rout - (va2 * d >> 15)
        buf[(pos + self._w_mRAPF2) % blen] = -32768 if new < -32768 else (32767 if new > 32767 else new)
        Rout = (new * va2 >> 15) + d
        if Rout < -32768: Rout = -32768
        elif Rout > 32767: Rout = 32767

        left_out = Lout * self.vLOUT >> 15
        right_out = Rout * self.vROUT >> 15
        self.pos = (pos + 1) % blen
        return left_out / 32768.0, right_out / 32768.0


def _s16n(v: int) -> int:
    """Convert unsigned 16-bit to signed."""
    return v - 65536 if v >= 32768 else v


# ─────────────────────────────────────────────────────────────────────────────
# One voice
# ─────────────────────────────────────────────────────────────────────────────

def _play(pcm: List[int], loop: int, ratio_from: float, ratio_to: float,
          glide: int, count: int, vib_phase: float = 0.0,
          vib_depth: int = 0, vib_step: float = 0.0, rdm_offset: float = 0.0,
          sweep_semis: float = 0.0, sweep_hold: int = 0,
          sweep_ramp: int = 0, porta_decay: float = 0.0,
          porta_spt: float = 1.0) -> Tuple[List[float], float]:
    """`count` output samples, looping the tail, sliding pitch, vibrato.

    A pitch sweep (0xE5) starts the note `sweep_semis` semitones off its true
    pitch, holds for `sweep_hold` samples, then ramps to pitch over `sweep_ramp`.

    Returns (samples, new_vib_phase).
    """
    if not pcm or count <= 0:
        return [], vib_phase
    out = []
    out_append = out.append
    pos = 0.0
    end = len(pcm)
    end1 = end - 1
    gauss = _GAUSS_TABLE

    modulated = (porta_decay > 0.0 or glide > 0 or rdm_offset
                 or (vib_step > 0.0 and vib_depth > 0)
                 or (sweep_ramp > 0 and sweep_semis != 0.0))

    if not modulated:
        # Common case: constant playback rate — tight loop, no per-sample branches.
        r = ratio_from
        for _ in range(count):
            while pos >= end1:
                if loop >= end1:
                    return out, vib_phase
                pos = loop + (pos - end1)
            k = int(pos)
            frac = int((pos - k) * 256.0) & 0xFF
            if k >= 3:
                s0, s1, s2, s3 = pcm[k - 3], pcm[k - 2], pcm[k - 1], pcm[k]
            else:
                s0, s1, s2, s3 = pcm[max(0, k - 3)], pcm[max(0, k - 2)], pcm[max(0, k - 1)], pcm[k]
            out_append((gauss[0xFF - frac] * s0 + gauss[0x1FF - frac] * s1
                        + gauss[0x100 + frac] * s2 + gauss[frac] * s3) / 32768.0)
            pos += r
        return out, vib_phase

    # Modulated notes (vibrato / sweep / portamento / rdm / glide): full path.
    for i in range(count):
        while pos >= end1:
            if loop >= end1:
                return out, vib_phase
            pos = loop + (pos - end1)
        k = int(pos)
        frac = int((pos - k) * 256.0) & 0xFF
        if k >= 3:
            s0, s1, s2, s3 = pcm[k - 3], pcm[k - 2], pcm[k - 1], pcm[k]
        else:
            s0, s1, s2, s3 = pcm[max(0, k - 3)], pcm[max(0, k - 2)], pcm[max(0, k - 1)], pcm[k]
        out_append((gauss[0xFF - frac] * s0 + gauss[0x1FF - frac] * s1
                    + gauss[0x100 + frac] * s2 + gauss[frac] * s3) / 32768.0)

        ratio = ratio_from
        if porta_decay > 0.0 and ratio_to > 0.0 and ratio_from > 0.0:
            remaining = (1.0 - porta_decay) ** (i / porta_spt)
            ratio = ratio_to * (ratio_from / ratio_to) ** remaining
        elif glide > 0:
            ratio += (ratio_to - ratio_from) * min(1.0, i / glide)
        if vib_step > 0.0 and vib_depth > 0:
            cnt = int(vib_phase) & 0x3F
            tbl = _VIBX_TBL[cnt & 0x1F]
            dv = (vib_depth * 2) & 0xFE
            vv = (dv * tbl) >> 8
            if cnt >= 32:
                vv = -vv
            ratio *= 2.0 ** ((vv / 256.0) / 12.0)
            vib_phase += vib_step
        if rdm_offset:
            ratio *= 2.0 ** (rdm_offset / 12.0)
        if sweep_ramp > 0 and sweep_semis != 0.0:
            if i < sweep_hold:
                off = sweep_semis
            elif i < sweep_hold + sweep_ramp:
                off = sweep_semis * (1.0 - (i - sweep_hold) / sweep_ramp)
            else:
                off = 0.0
            if off:
                ratio *= 2.0 ** (off / 12.0)
        pos += ratio
    return out, vib_phase


# ─────────────────────────────────────────────────────────────────────────────
# Track rendering
# ─────────────────────────────────────────────────────────────────────────────

def _render_track(events: list, bank: SequenceBank, total: int,
                  ticks_per_second: float, middle_note: int,
                  tune: bool, stereo: bool,
                  reverb_in_l: list = None,
                  reverb_in_r: list = None) -> Tuple[List[float], List[float], bool]:
    """Render one track. Returns (left, right, had_reverb).

    If `reverb_in_l/r` arrays are provided, reverb-enabled samples are
    accumulated into them (for post-processing by `SPU_Reverb`).
    """
    track_l = [0.0] * total
    track_r = [0.0] * total
    had_reverb = False

    samples = {}
    _SILENT = ([0.0], 0, 0)  # dummy silent sample for out-of-range programs

    def get_sample(index: int):
        if index not in samples:
            if index < len(bank.instruments):
                inst = bank.instruments[index]
                pcm = bank.decode_instrument(inst)
                loop = inst.loop_sample if inst.loops else len(pcm)
                samples[index] = (pcm, loop, inst.tune)
            else:
                samples[index] = _SILENT
        return samples[index]

    cursor = 0
    program: Optional[int] = None
    master, pan = 127, 20            # pan on raven's 0..40 scale (20 = centre)
    panmod = 0                       # 0 = follow instrument default pan on program change
    # ADSR (raw opcode values, inverted per the SPU convention)
    atk_rate = 0       # 0-127  (0=fastest, 0x7F=hold)
    dec_rate = 0       # 0-15   (0=fastest, 0x0F=hold)
    sus_lvl = 15       # 0-15   (4-bit sustain level, 15=max)
    sus_rate = 0x7F    # 0-127  (0=fastest sustain decay, 0x7F=hold)
    rel_rate = 0       # 0-31   (0=fastest release, 0x1F=hold; raven/SPU default)
    atk_mode = SPU_ADSR.LIN_INC     # instrument a_mode → attack curve
    sus_mode = SPU_ADSR.LIN_DEC     # instrument s_mode → sustain curve
    rel_mode = SPU_ADSR.LIN_DEC     # instrument r_mode → release curve
    bend, transpose = 0, 0
    tie = False
    reverb_on = False

    # Loop state (stack-based instruction-pointer jumps)
    loop_stack: list = []       # [(jump_idx, count, vol_acc, freq_acc, passes), ...]
    loop_vol_offset = 0
    loop_freq_offset = 0
    kakko_target = -1

    # Glissandi (tempo/vol/pan move) — raven's per-tick linear ramps
    tempo = int(round(ticks_per_second * 256 / _DRIVER_RATE))  # raw tmp; default ≈ tps
    tempo_mv: Optional[_Move] = None
    vol_mv: Optional[_Move] = None
    pan_mv: Optional[_Move] = None

    # Portamento (0xE6 por_set): glide from the previous note's pitch
    porta_speed = 0
    prev_ratio: Optional[float] = None

    # Vibrato (raven vib_set): b0 depth, b1 cadence (range-scaled), b2 hold
    vib_depth = 0          # b0 (0 = off)
    vib_cad = 0            # scaled cadence (LFO phase speed)
    vib_ofst = 8          # vib_tc_ofst (table step per cadence overflow)
    vib_phase: float = 0.0

    # Random pitch
    rdm_range: float = 0.0
    rdm_lfsr = 0xACE1

    # Pitch sweep (0xE5 sws_set): scoop into each following note
    sweep_count = 0        # b1: ramp length in ticks (0 = disabled)
    sweep_hold = 0         # b2: hold in ticks before the ramp starts
    sweep_offset = 0.0     # -signed(b0): start = target + this, in semitones

    _processed = 0          # guard against runaway processing
    voice_end = 0            # samples index up to which the last note-on wrote
    i = 0
    while i < len(events):
        _processed += 1
        if _processed > _MAX_EVENTS:
            break            # safety: cap total event dispatches

        e = events[i]
        op = e.opcode

        if op == seq.OP_PROGRAM:
            program = e.b2
            # raven tone_set: a program change loads the instrument's defaults —
            # its envelope (later ads_set/srs_set/rrs_set opcodes override) and,
            # when panmod is 0, its default pan.
            if program is not None and program < len(bank.instruments):
                inst = bank.instruments[program]
                ar, dr, sr, sl, rr = inst.adsr
                atk_rate = (~ar) & 0x7F
                dec_rate = (~dr) & 0x0F
                sus_rate = (~sr) & 0x7F
                sus_lvl = sl & 0x0F
                rel_rate = (~rr) & 0x1F
                a_mode, s_mode, r_mode = inst.env_modes
                atk_mode = SPU_ADSR.EXP_INC if a_mode else SPU_ADSR.LIN_INC
                sus_mode = {0: SPU_ADSR.LIN_DEC, 1: SPU_ADSR.EXP_DEC,
                            2: SPU_ADSR.LIN_INC}.get(s_mode, SPU_ADSR.EXP_INC)
                rel_mode = SPU_ADSR.EXP_DEC if r_mode else SPU_ADSR.LIN_DEC
                if panmod == 0:
                    pan = max(0, min(40, inst.default_pan * 2))

        elif op == seq.OP_TEMPO:
            tempo = e.b2                             # 0xD0 tempo_set: tmp = b2
            ticks_per_second = _tempo_to_tps(tempo)
            tempo_mv = None

        elif op == seq.OP_TEMPO_MOVE:
            tempo_mv = _Move(tempo, e.b1, e.b2)      # 0xD1: target=b1, count=b2 ticks

        elif op == seq.OP_SVL_SET:
            pass  # voice level retrigger — not yet implemented

        elif op == seq.OP_SVP_SET:
            pass  # voice pan retrigger — not yet implemented

        elif op == seq.OP_VOL_CHG:
            master = e.b2                    # 0xD5 vol_chg: track/voice volume
            vol_mv = None

        elif op == seq.OP_VOL_MOVE:
            vol_mv = _Move(master, e.b1, e.b2)   # 0xD6: target=b1, count=b2 ticks

        elif op == seq.OP_ADS_SET:
            sus_lvl = e.b0 & 0x0F                  # 4-bit sustain level
            dec_rate = (~e.b1) & 0x0F              # 4-bit decay rate (inverted)
            atk_rate = (~e.b2) & 0x7F              # 7-bit attack rate (inverted)

        elif op == seq.OP_SRS_SET:
            sus_rate = (~e.b2) & 0x7F              # 7-bit sustain rate (inverted)

        elif op == seq.OP_RRS_SET:
            rel_rate = (~e.b2) & 0x1F              # 5-bit release rate (inverted)

        elif op == seq.OP_PAN_SET:
            # raven pan_set: panf = signed(b1) + 20 (0..40, 20 = centre), and
            # panmod = b2 — when non-zero the manual pan sticks across program
            # changes; when 0 the next program change resets it to the default.
            pan = max(0, min(40, seq.to_signed(e.b1) + 20))
            panmod = e.b2
            pan_mv = None

        elif op == seq.OP_PAN_MOVE:
            # 0xDE pan_move: target = signed(b1)+20 (0..40), count = b2 ticks
            pan_mv = _Move(pan, max(0, min(40, seq.to_signed(e.b1) + 20)), e.b2)

        elif op == seq.OP_TRANS_SET:
            transpose = seq.to_signed(e.b2)     # 0xDF trans_set: ptps = signed(b2)

        elif op == seq.OP_PITCH_BEND:
            # 0xE0 detune_set: tund = signed(b2) << 2 in 1/256-semitone units
            bend = seq.to_signed(e.b2) * 4 / 256.0    # → signed(b2)/64 semitones

        elif op == seq.OP_VIB_SET:
            # raven vib_set: b0 = depth, b1 = cadence (range-scaled), b2 = hold.
            vib_depth = e.b0
            cad = e.b1
            if cad < 32:
                vib_ofst, vib_cad = 1, cad << 3
            elif cad < 64:
                vib_ofst, vib_cad = 2, cad << 2
            elif cad < 128:
                vib_ofst, vib_cad = 4, cad << 1
            elif cad < 255:
                vib_ofst, vib_cad = 8, cad
            else:
                vib_ofst, vib_cad = 16, cad
            vib_phase = 0.0

        elif op == seq.OP_VIB_CHANGE:
            pass  # depth fade-in — unused by these banks

        elif op == seq.OP_RDM_SET:
            rdm_range = e.b0

        elif op == seq.OP_PORTAMENTO:
            pass

        elif op == seq.OP_SWS_SET:
            # 0xE5 sws_set: arm a pitch scoop into each following note.
            # b1 = ramp length in ticks (0 disables), b2 = hold before the ramp,
            # b0 = signed start offset: the note starts -signed(b0) semitones from
            # its true pitch and slides to it (raven note_compute + keych).
            sweep_count = e.b1
            sweep_hold = e.b2
            sweep_offset = -seq.to_signed(e.b0)

        elif op == seq.OP_POR_SET:
            porta_speed = e.b2   # 0xE6 por_set: b2 = glide speed (0 disables)

        elif op == seq.OP_LP1_START or op == seq.OP_LP2_START or op == seq.OP_LP3_START:
            loop_stack.append([i + 1, 0, 0, 0, 0])

        elif op in (seq.OP_LP1_END, seq.OP_LP2_END, seq.OP_LP3_END):
            if loop_stack:
                entry = loop_stack[-1]
                count = e.b2
                if count == 0:
                    count = _LOOP_MAX_PASSES   # cap infinite loops
                vd = seq.to_signed(e.b1)
                fd = seq.to_signed(e.b0)
                entry[2] += vd
                entry[3] += fd
                entry[4] += 1
                loop_vol_offset += vd
                loop_freq_offset += fd
                if entry[4] < count:
                    i = entry[0]
                    continue
                else:
                    loop_stack.pop()

        elif op == seq.OP_KAKKO_START:
            kakko_target = i + 1

        elif op == seq.OP_KAKKO_END:
            # b2=0 → repeat A section once; b2=1 → continue to B
            if e.b2 == 0 and kakko_target >= 0:
                # mark that we've done the jump so a second b2=0 is safe
                i = kakko_target
                kakko_target = -1  # prevent re-entry
                continue
            else:
                kakko_target = -1

        elif op == seq.OP_TIE_SET:
            tie = (e.b2 != 0)

        elif op == seq.OP_REVERB_ON:
            reverb_on = True
            had_reverb = True

        elif op == seq.OP_REVERB_OFF:
            reverb_on = False

        elif op == seq.OP_WAIT:
            ticks = e.b2
            cursor += int(ticks / ticks_per_second * OUTPUT_RATE)
            # advance any active glissandi over the rest
            if tempo_mv is not None:
                tempo_mv.advance(ticks); tempo = tempo_mv.current
                ticks_per_second = _tempo_to_tps(tempo)
                if tempo_mv.done: tempo_mv = None
            if vol_mv is not None:
                vol_mv.advance(ticks); master = vol_mv.current
                if vol_mv.done: vol_mv = None
            if pan_mv is not None:
                pan_mv.advance(ticks); pan = max(0, min(40, pan_mv.current))
                if pan_mv.done: pan_mv = None

        elif e.is_note:
            if program is not None and e.velocity > 0:
                pcm, loop, offset = get_sample(program)
                if pcm:
                    # Each track owns one SPU voice: a new note-on retriggers it
                    # immediately, cutting whatever dry tail the previous note
                    # was still ringing (docs/FORMATS.md §4.4). Only the dry
                    # track output is muted — any reverb that tail already sent
                    # to the shared reverb bus keeps ringing there, as it would
                    # on real hardware (the reverb network doesn't know its
                    # source voice was just cut).
                    if voice_end > cursor:
                        mute_to = min(voice_end, total)
                        for q in range(cursor, mute_to):
                            track_l[q] = 0.0
                            track_r[q] = 0.0
                        voice_end = cursor

                    detune = offset if tune else 0.0
                    # raven: index = note + transpose + detune + fine tune; the
                    # native-rate reference lives inside freq_tbl (no MIDDLE_NOTE).
                    index = e.pitch + bend + transpose + loop_freq_offset + detune
                    this_ratio = _freq_ratio(index)

                    rdm_off = 0.0
                    if rdm_range:
                        rdm_lfsr = (rdm_lfsr >> 1) ^ (-(rdm_lfsr & 1) & 0xB400)
                        r = rdm_lfsr % (int(rdm_range) * 2 + 1)
                        rdm_off = (r - rdm_range) / 100.0

                    # portamento (0xE6 por_set): glide from the previous note's
                    # pitch to this one, approaching geometrically (raven por_compute).
                    porta_decay = 0.0
                    porta_spt = 1.0
                    if porta_speed > 0 and prev_ratio is not None:
                        start_ratio, target_ratio, glide = prev_ratio, this_ratio, 0
                        porta_decay = min(1.0, porta_speed / 256.0)
                        porta_spt = OUTPUT_RATE / ticks_per_second
                    else:
                        start_ratio, target_ratio, glide = this_ratio, this_ratio, 0
                    prev_ratio = this_ratio

                    # raven note_set: length (timeline + gate) = b2; volume = b0
                    gate_total = int(e.length / ticks_per_second * OUTPUT_RATE)
                    keyoff = int(gate_total * min(e.gate_pct, 100) / 100)

                    vol_off = max(0, min(15, loop_vol_offset))
                    sl_used = max(0, min(15, sus_lvl + vol_off))
                    gain = (master / 127.0) * (e.velocity / 127.0)   # b0 = note volume

                    if stereo:
                        pi = max(0, min(40, int(round(pan))))     # raven's 0..40 index
                        gr = _PANT[pi] / 127.0
                        gl = _PANT[40 - pi] / 127.0
                    else:
                        gl = gr = _PANT[20] / 127.0               # centre (mono)

                    # pitch sweep (0xE5): scoop into the note over `sweep_count` ticks
                    sw_semis = sweep_offset if sweep_count > 0 else 0.0
                    sw_hold_s = int(sweep_hold / ticks_per_second * OUTPUT_RATE)
                    sw_ramp_s = int(sweep_count / ticks_per_second * OUTPUT_RATE)

                    # vibrato LFO advance per output sample (raven: vib_tbl_cnt
                    # steps vib_ofst each time vib_cad overflows 0xFF, per tick)
                    spt = OUTPUT_RATE / ticks_per_second
                    vib_step = (vib_ofst * vib_cad / 256.0) / spt if vib_depth else 0.0

                    max_count = min(total - cursor, gate_total * 4 + OUTPUT_RATE)
                    voice, vib_phase = _play(
                        pcm, loop, start_ratio, target_ratio, glide, max_count,
                        vib_phase=vib_phase, vib_depth=vib_depth, vib_step=vib_step,
                        rdm_offset=rdm_off,
                        sweep_semis=sw_semis, sweep_hold=sw_hold_s,
                        sweep_ramp=sw_ramp_s,
                        porta_decay=porta_decay, porta_spt=porta_spt)

                    adsr = SPU_ADSR()
                    adsr.key_on(atk_rate, dec_rate, sl_used, mode=atk_mode)
                    adsr.set_sustain(sus_rate, s_mode=sus_mode)

                    written = 0
                    for j, x in enumerate(voice):
                        q = cursor + j
                        if q >= total:
                            break
                        if j == keyoff:
                            adsr.key_off(rel_rate, r_mode=rel_mode)
                        adsr.tick()
                        env = adsr.env_norm
                        a = x * gain * env
                        track_l[q] += a * gl
                        track_r[q] += a * gr
                        written = j + 1

                        if reverb_on and reverb_in_l is not None:
                            if q < total:
                                reverb_in_l[q] += a * gl
                                reverb_in_r[q] += a * gr

                        if not adsr.is_active:
                            break
                    # Watermark for the next note-on on this track to cut against.
                    voice_end = cursor + written

            if not tie:
                cursor += int(e.length / ticks_per_second * OUTPUT_RATE)
                # advance active glissandi over the note's length
                if tempo_mv is not None:
                    tempo_mv.advance(e.length); tempo = tempo_mv.current
                    ticks_per_second = _tempo_to_tps(tempo)
                    if tempo_mv.done: tempo_mv = None
                if vol_mv is not None:
                    vol_mv.advance(e.length); master = vol_mv.current
                    if vol_mv.done: vol_mv = None
                if pan_mv is not None:
                    pan_mv.advance(e.length); pan = max(0, min(40, pan_mv.current))
                    if pan_mv.done: pan_mv = None

        i += 1

    return track_l, track_r, had_reverb


# ─────────────────────────────────────────────────────────────────────────────
# Cue rendering
# ─────────────────────────────────────────────────────────────────────────────

def render_cue(bank: SequenceBank, cue: Cue,
               ticks_per_second: float = seq.TICKS_PER_SECOND,
               middle_note: int = seq.MIDDLE_NOTE,
               tune: bool = True, stereo: bool = True,
               seconds: int = 40,
               reverb_preset: Optional[str] = "hall") -> Tuple[List[float], List[float]]:
    """Render one cue. Returns (left, right); both are the same when mono.

    `reverb_preset` — one of 'off', 'room', 'studio_small', 'studio_medium',
    'studio_large', 'hall', 'space_echo'.  Set to 'off' or None to disable.
    """
    total = min(seconds, MAX_SECONDS) * OUTPUT_RATE
    left = [0.0] * total
    right = [0.0] * total

    # Shared reverb input accumulators (one per sample)
    reverb_in_l = [0.0] * total if reverb_preset else None
    reverb_in_r = [0.0] * total if reverb_preset else None

    for addr in cue.tracks:
        events = bank.track(addr)
        tl, tr, rh = _render_track(events, bank, total, ticks_per_second,
                                    middle_note, tune, stereo,
                                    reverb_in_l, reverb_in_r)
        for j in range(total):
            left[j] += tl[j]
            right[j] += tr[j]

    # Apply reverb
    if reverb_preset and reverb_preset != "off":
        preset = REVERB_PRESETS.get(reverb_preset, REVERB_HALL)
        reverb = SPU_Reverb(preset)
        for j in range(total):
            rl, rr = reverb.process(reverb_in_l[j], reverb_in_r[j])
            left[j] += rl
            right[j] += rr

    peak = max(max((abs(v) for v in left), default=0.0),
               max((abs(v) for v in right), default=0.0))
    if peak > 0:
        gain = min(1.0, 26000.0 / peak)
        left = [v * gain for v in left]
        right = [v * gain for v in right]

    last = max((i for i in range(total) if abs(left[i]) > 30 or abs(right[i]) > 30),
               default=0)
    cut = last + OUTPUT_RATE // 4
    return left[:cut], right[:cut]


def save_cue(left: List[float], right: List[float], path: str, stereo: bool = True):
    """Write a rendered cue to a WAV file."""
    from .codec.wav import save_wav
    if stereo:
        interleaved = []
        for a, b in zip(left, right):
            interleaved.append(int(a))
            interleaved.append(int(b))
        save_wav(interleaved, path, OUTPUT_RATE, channels=2)
    else:
        save_wav([int(v) for v in left], path, OUTPUT_RATE, channels=1)
