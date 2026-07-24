# MGS2 audio formats

Reverse-engineering notes for the audio files of **Metal Gear Solid 2: Sons of
Liberty** (Master Collection 2023 and Substance 2003, PC). Everything here was
found by analysing files, confirmed by ear, and cross-referenced against
**KieronJ/raven** — a C port of **Kazuki Muraoka's PS2 sound library**, the
same driver that powers MGS2 and Zone of Enders.

This document is deliberately independent of the code. If the tool disappears,
this is what you need to write another one — for MGS2, or as a starting point
for a different Konami title of the same era.

Byte offsets are hexadecimal. Multi-byte integers are little-endian unless
stated otherwise.

---

## 1. The codec: PS-ADPCM

Both formats store audio as PlayStation 4-bit ADPCM (PS-ADPCM, also called VAG).
A **frame** is 16 bytes and decodes to **28 samples**:

| Offset | Meaning |
|--------|---------|
| `0`    | high nibble = predictor filter (0–4), low nibble = shift (0–12) |
| `1`    | flags (see below) |
| `2–15` | 28 samples, two signed 4-bit nibbles per byte, low nibble first |

Decoding a nibble `n` (sign-extended from 4 bits):

```
sample = (n << 12) >> shift
sample += coef0 * previous1 + coef1 * previous2
clamp to [-32768, 32767]
```

The Sony prediction coefficients, scaled by 1/64:

| filter | coef0    | coef1    |
|--------|----------|----------|
| 0      | 0        | 0        |
| 1      | 60/64    | 0        |
| 2      | 115/64   | −52/64   |
| 3      | 98/64    | −55/64   |
| 4      | 122/64   | −60/64   |

### Flag byte

Standard SPU semantics. Only bit 0 matters for splitting a stream into samples;
the rest must be preserved when rewriting audio in place.

| Bit | Value | Meaning |
|-----|-------|---------|
| 0   | `0x01` | end of sample |
| 1   | `0x02` | loop rather than stop |
| 2   | `0x04` | loop restarts here |

`.sdt` files carry `0x02` on nearly every frame. `.sdx` banks use `0x00`, `0x01`,
`0x02`, `0x04` and `0x07`.

### Telling PS-ADPCM from something else

A cheap and reliable check: in valid PS-ADPCM, the filter nibble is always 0–4
and the flag byte is small (≤ 7). Sample a few thousand frames and count the
violations. Real PS-ADPCM scores ~0 %. Files using another codec score high — one
tested file (`t10a1d.sdt`, from stock Steam data) scored **73 %**, and turned out
to be **Konami XWMA** (`AMWX`, WMA v2 wrapped in a multiplexed container). Those
files aren't PS-ADPCM, so the PS-ADPCM path reports them rather than playing
noise — but they are now decoded via a separate path (see §XWMA below and
`formats/xwma.py`).

---

## 2. The `.sdt` format — dialogue, music, some effects

Found under `us/vox/` and elsewhere. **44100 Hz.** Mono or stereo.

> **Important.** The `.sdt` files this tool was developed against are the ones
> shipped by the *Better Audio Mod*, which restores the PS3 HD Collection audio
> in PS-ADPCM. Stock Steam files often use the other codec described above.

### Structure

```
0x0000            header: table of contents and metadata
<blocks>          a series of "MG blocks", back to back
```

Each block:

```
+0x00  u32   type — audio blocks are type 1
+0x04  u32   total block size, header included (usually 0x4010)
+0x08  8 bytes  (sequence counter and unknown fields)
+0x10  audio payload, up to 0x4000 bytes
```

The last block may be shorter. Concatenating every audio block's payload gives
one continuous PS-ADPCM stream.

Blocks of other types (notably type 5, thousands of them in large dialogue
files) sit between the audio blocks and carry metadata. A parser can simply skip
anything that is not `type == 1` with a plausible size.

### Sample rate and channel count

Usually at fixed offsets in the header:

| Offset | Type | Meaning |
|--------|------|---------|
| `0x96` | u16 **big-endian** | sample rate (e.g. `0xAC44` = 44100) |
| `0x98` | u8   | channel count: 1 or 2 |

### Header variants

Some files insert an extra sub-header — recognisable by the ASCII tag **`PACB`**
near `0x20` — which shifts everything. Two sub-variants were seen:

1. **Shifted, fields still present.** Music and VR files. The rate/channel pair
   moves (to `0xB6`/`0xB8` in the observed files). A reliable way to find it is
   to scan the first `0x400` bytes for the anchor `7F <rate big-endian> <channels>`,
   which appears in both layouts. (`0x7F` is the byte immediately preceding the
   rate in the normal layout too.)

2. **Shifted, fields absent.** Cutscene files carrying embedded Japanese text
   (subtitles). Neither the anchor nor the fixed offsets yield anything usable.
   The channel count must be recovered from the audio itself — see §2.2.

Getting this wrong is audible: a **stereo file read as mono** plays both channels
end to end, so it is twice as long and sounds like slow motion.

### 2.1 Stereo interleave — the source of the "echo" bug

On 2-channel files the channels are interleaved in chunks of **`0x800` bytes**:

```
L(0x800) R(0x800) L(0x800) R(0x800) ...
```

One `0x4000` payload therefore holds eight chunks: `L R L R L R L R`.

`0x800` bytes = 128 frames = **3584 samples ≈ 81 ms** at 44100 Hz.

Decoding the raw stream as a single mono flow glues channel R about 81 ms behind
channel L. The result is a distinct echo on the voice. It shows up clearly as a
peak in the signal's autocorrelation at lag 3584 (measured ≈ 0.47 on a real file;
it falls to ≈ 0.04 once the channels are separated).

A cautionary note for anyone re-deriving this: deinterleaving at the wrong
granularity — per 16-byte ADPCM frame instead of per `0x800` chunk — halves each
channel's duration and produces a fast, high-pitched "chipmunk" voice. If you
hear that, your chunk size is too small.

Correct handling: read the channel count, split the stream at `0x800`, decode
each channel independently, then interleave the PCM samples as a normal stereo
WAV (`L R L R` per sample).

### 2.2 Recovering the channel count from the audio

When the header hides it, two complementary signals each imply stereo. Either is
enough; a mono file triggers neither. Work on a few windows spread across the
file — the opening is often silence, and long files mix passages of both kinds.

**Signal A — duplication.** Dialogue is usually centred, so both channels carry
nearly the same audio. Chunk `2i` and chunk `2i+1` are then near-identical:
their PCM correlation approaches +1. A mono file's consecutive chunks are
different moments of the same take, so the correlation stays near 0.

**Signal B — continuity.** When the channels genuinely differ, compare the
spectrum at the end of chunk `k` against the start of chunk `k+1` (call the
distance `D1`) and against the start of chunk `k+2` (`D2`). In an interleaved
stereo stream, chunk `k` continues into chunk `k+2` (same channel), so `D2 < D1`.
In a mono stream the next chunk really is the next moment, so `D1 < D2`. This is
a *relative* test, with no absolute threshold.

> **Known limitation.** Signal B is guarded against pathological cases by
> requiring `D1` to fall in a moderate range. Two wildly dissimilar channels push
> `D1` past that guard and the file is read as mono. Real dialogue and music have
> similar channels, so this has not been observed in practice — but it is a real
> hole, and worth revisiting if a file ever plays back at double length.

### 2.3 Replacing audio

The game expects the file's size and block layout to be unchanged. So:

- encode the new audio to PS-ADPCM;
- pad with silence if it is shorter, truncate if longer;
- for stereo, encode once and write the same audio to both channels, then
  re-interleave at `0x800`;
- write the result back into the existing block payloads, block by block.

The file's byte size never changes.

---

## 3. The `.sdx` format — stage sound banks

One per stage folder (`us/stage/<stage>/pk000000.sdx`). These hold the stage's
sound effects: footsteps, doors, weapons, ambience. **22050 Hz, mono.**

### Structure

```
0x0000 .. 0x0800   header (mostly zero; a handful of u32 fields at the start)
0x0800 .. <audio>  16-byte-record table (see "Two kinds of bank" below)
<audio> .. <pad>   audio: PS-ADPCM samples laid end to end
<pad>              frame-aligned padding — 0xFF or 0xFE — ends the audio
<table>            the bank table
<tail>             sequence / sound-program data
```

**Audio does not reliably begin at `0x1000`.** Measured over the **600** stage
banks of a real install, the audio starts where the `0x800` table ends, which
ranges **`0x9E0` .. `0x1070`** (72–135 records). Only **12 of 600** banks land
exactly on `0x1000` (the 128-record case). The sample partition below re-syncs
on the end-flag, so using `0x1000` as a nominal start is harmless in practice —
but the fixed offset itself is not a fact about the format.

**The padding byte is 0xFF *or* 0xFE.** All ~80 music/sequencer banks use
`0xFE`. A parser that only recognises `0xFF` runs straight past the end of the
audio on those banks and carves phantom "samples" out of the cue table and
sequence that follow (which then pollute the cross-bank scan).

### Two kinds of bank

The same `.sdx` container is used for two different things, and they must be
told apart — the `0x800` table means something different in each:

| | **SE banks** (~520) | **Music banks** (~80) |
|---|---|---|
| `0x800` table | **SPU voice table** — addresses in SPU space (≥`0x150000`), *not* file offsets | the sequencer's **instrument directory** (§4.2), file offsets |
| Padding | `0xFF` | `0xFE` |
| Cue table | usually absent (0 cues) | 256 cues |
| Read with | `sdx.py` (end-flag partition) | `sequence.py` (directory + cues) |

Telling them apart: in a music bank essentially **100 %** of the `0x800`
records' offsets land inside the audio region; in an SE bank barely **1 %** do
(the rest are SPU addresses). The `0x800` record signature is identical in both,
so the directory-detection heuristic alone cannot distinguish them.

### Samples

Samples are concatenated with no separator. A sample runs up to **and including**
the first frame whose flag has bit 0 (`0x01`) set. In one measured bank this
partition covered the audio region exactly, to the byte.

Runs of isolated 16-byte "samples" appear between real ones: these are
terminator frames. Ignoring anything below ~256 bytes gives a clean list (126
usable sounds in the bank that was analysed, out of 361 flagged boundaries).

The sample rate is not stored anywhere obvious. **22050 Hz** was established by
ear and is consistent across the effects tested.

### The bank table

Around `0x101800` in the analysed bank, a series of 16-byte records:

```
50 01 01 <n>   <u32 address>   FF FF FF FF FF FF FF FF
```

Other record signatures exist (`10 01 01`, `30 01 01`, `20 01 01`, `30 02 01`…),
some carrying two or three addresses — presumably start, loop and end points.

**Addresses are counted in 8-byte units**, relative to the start of the audio
region: `byte_offset = 0x1000 + address * 8`. Every address in the analysed bank
pointed inside the audio region, in increasing order.

This table is why a replacement must keep the sample's exact byte size. Changing
a sample's length would invalidate every address that follows it.

### The tail

From roughly `0x110000` the data is not audio. It reads as a sequence of small
values progressing in regular steps — most likely SPU register writes: the
program that decides when and how the samples are played. **Not decoded.** The
tool does not touch it, which is why replacing a sample is safe.

### 3.1 Replacing a sample

Two constraints, both mandatory:

1. **Exact size.** Encode the new audio into exactly the original frame count
   (pad with silence, or truncate).
2. **Preserve the flags.** After encoding, copy each original frame's flag byte
   (offset `+1` within the frame) back into the new frames. This keeps the end
   marker and any loop points intact.

Done this way, only the sample's bytes change; the table and the tail are
untouched, and the game loads the bank without complaint (verified in game).

### 3.2 Sounds are shared across banks

This matters more than it sounds. Common effects — rain, footsteps, gunshots —
are duplicated across dozens of stage banks. Editing one stage's bank often has
**no audible effect**, because the game may play the copy stored in another
stage's bank.

To find the duplicates, hash each sample's audio payload **with the per-frame
flag bytes zeroed**. Two banks may give the same sound different loop markers;
zeroing the flags makes them hash alike. When rewriting, restore each
occurrence's own flags.

In the analysed data, a single bank contained no internal duplicates: all the
repetition is between banks.

---

## 4. The music: a sequencer inside `.sdx`

MGS2 ships no music files. Its in-game music is **played, not streamed**: a small
program picks samples out of the bank and plays them as notes, the way a MIDI
file drives a synthesiser. That program is the region at the end of every `.sdx`
that §3 leaves alone.

Everything below was found by reading bytes and confirmed by **listening**. Each
rule was implemented, rendered to a WAV, and judged by ear. Rules that sounded
wrong were thrown away, however convincing they looked on paper.

### 4.1 Layout of a sequencer bank

Banks that carry a sequence have a richer structure than §3 describes. The cue
table and sequence data sit at **fixed offsets from the end of the file**, not
directly after the audio padding:

```
0x0800 .. <audio>       instrument directory, 16 bytes per entry
<audio> .. <pad>        the PS-ADPCM samples
<pad>                   frame-aligned 0xFF (or 0xFE) padding
<garbage>               unused bytes, zero or uninitialised
<table>                 fsize − 0x6800:  256 × 16‑byte cue records  (0x1000 B)
<sequence>              fsize − 0x5800:  the events                 (0x5800 B)
```

The "after padding" heuristic used by early parsers fails because real files
leave a gap of uninitialised bytes between the padding and the cue table. The
table is reliably found at `fsize − 0x6800`.

**The audio does not start at `0x1000`.** It starts where the directory stops.
Assuming a fixed offset makes every sample land mid-frame and decode to noise.

### 4.2 The instrument directory

Sixteen bytes per entry, starting at `0x800`. The directory ends where the
records stop matching — typically 129–150 entries.

| Offset | Type | Meaning | Constant? |
|--------|------|---------|-----------|
| `+0`  | u32 | sample offset, relative to the start of the audio | `+3` = `0x00` |
| `+4`  | u16 | base rate in Hz — the rate the sample plays at untransposed | no |
| `+6`  | u8  | `a_mode` (envelope attack mode) | **`0x00`** |
| `+7`  | u8  | **attack rate** | **no** — usually `0x7F` |
| `+8`  | u8  | decay rate | **`0x00`** |
| `+9`  | u8  | `s_mode` | **`0x00`** |
| `+10` | u8  | sustain rate | **`0x00`** |
| `+11` | u8  | sustain level | **`0x0F`** |
| `+12` | u8  | `r_mode` | **`0x00`** |
| `+13` | u8  | **release rate** | **no** — usually `0x19` |
| `+14` | u8  | **default pan** | **no** — usually `0x0A` |
| `+15` | u8  | — | **`0x00`** |

**Only the eight bytes marked constant may be used to find the directory's
end.** `+7`, `+13` and `+14` are the entry's attack, release and pan: they hold
the common defaults for *most* instruments but not all. Measured on one bank's
149 entries, `+7` is `0x7F` for 147, `+13` is `0x19` for 145, `+14` is `0x0A`
for 146.

Treating those defaults as format constants is a trap that costs far more than
the entries it drops: the directory ends at the first instrument with a custom
envelope, **and the audio starts where the directory ends**, so every sample
offset shifts too. On the game's music banks that misread **23 of 68**
directories — e.g. `a01a/pk000011.sdx` read 135 entries instead of 150 and
placed the audio at `0x1070` instead of `0x1160`, leaving nearly every
instrument reading 15 frames into the previous sample.

**The directory closes with a terminator record** — one slot that carries none
of the structural bytes (e.g. `00 00 00 00 00 10 0D 70 00…` in
`a14a/pk000012.sdx`). It is not an instrument, but it *occupies a record*, and
since the audio begins where the directory ends, overlooking it starts the audio
one frame early and every instrument decodes from the tail of its neighbour.

Don't guess the end — **measure it**. The format gives every sample a silent
lead-in frame, so the correct length is the one where that holds throughout:

| Bank | signature walk | with terminator |
|---|---|---|
| `a01a/pk000011.sdx` | 150 records → 23.5 % aligned | **151 → 150/150 = 100 %** |
| `a14a/pk000012.sdx` | 129 records → 7.0 % aligned | **130 → 129/129 = 100 %** |

The measure is decisive rather than marginal — the right length scores ~100 %
and every neighbour under 25 % — and it also tells the two bank kinds apart on
its own: **all 68 music banks** take the terminator, **none of the 532 SE banks**
do (their table holds SPU addresses, so the lead-in measure does not apply).

A sample **starts with a silent frame**, the VAG convention, and **ends at its
end flag** — not at the next directory offset. Several entries may point into
the same region. Ignoring the end flag makes instruments a handful of frames
long, and melodies come out as clicks.

The base rate matters: instruments are tuned relative to each other by it.
`44100 Hz` — the SPU's own reference — is the value at which a sample plays
unshifted. Confirmed by ear: with any other reference, the melody drifts out of
tune.

Many instruments are **tiny looped waveforms** (6 to 14 frames). They are
oscillators, not clicks. A note holds by looping between the loop-start frame
(flag `0x04`) and the end. Without looping, a sustained note lasts ten
milliseconds and the music sounds like a beeping cash register.

### 4.3 The cue table

256 records of 16 bytes. Records whose second byte is not 1, 2 or 3 are unused.

| Offset | Type | Meaning |
|--------|------|---------|
| `+0`  | u8  | kind (`0x10`, `0x20`, … `0xF0`) |
| `+1`  | u8  | number of tracks, 1..3 |
| `+2`  | u8  | flag |
| `+3`  | u8  | flag |
| `+4`  | u32 ×3 | track offsets into the sequence; `0xFFFFFFFF` = unused |

A cue is one playable thing: a musical phrase, a jingle, a layered sound effect.
Its tracks are stored back to back — the first track's end marker sits exactly
where the second begins, in all 108 multi-track cues of the bank analysed.

The tracks of a cue play **simultaneously** — the renderer mixes them into a
single stereo buffer. Their durations differ by ~25 % on average simply because
each voice finishes playing its events at its own pace.

### 4.4 Events

Every event is **4 bytes**, and the **opcode is the last one**:

```
b0 b1 b2 opcode
```

Track offsets are always multiples of 4. `00 00 FE FF` ends a track: in the bank
analysed, **382 of 382** table offsets pointed to the byte right after one.

#### Notes — opcode below `0x80`

| Field | Meaning |
|-------|---------|
| opcode | pitch, in semitones. Note 60 plays the sample at its base rate |
| `b0` | volume / velocity, 0..127. A value of 0 plays nothing |
| `b1` | gate percentage, 0..100 (fraction of the length before key-off) |
| `b2` | note length in ticks — also how far the timeline advances |

**Tick length is set by the tempo** (opcode `0xD0`): `ticks/s = (44100/448) * tmp/256`.
Real banks run at roughly 24–49 ticks/s. The old fixed 1/30 s was only a fallback.

**Each track owns one voice.** A new note silences whatever the track was still
playing. Letting notes pile up turns a repeated figure into a smear of echo.

#### Commands — opcode `0xD0` and above

All opcodes decoded from **KieronJ/raven** (the official PS2 sound driver), then
cross-referenced by listening. The parameter column uses the event byte order
`b0 b1 b2` (raven's `mdata4 mdata3 mdata2`):

| Opcode | Function (raven) | Parameters | Description |
|--------|------------------|------------|-------------|
| `0xD0` | `tempo_set` | `b2 = tempo` | Tempo: `ticks/s = (44100/448) * b2/256` |
| `0xD1` | `tempo_move` | `b2 = target` `b1 = speed` | Tempo slide |
| `0xD2` | `sno_set` | `b2 = program` | Instrument index into the directory |
| `0xD3` | `svl_set` | `b2 = value` | Set voice level (retrigger) |
| `0xD4` | `svp_set` | `b2 = value` | Set voice pan (retrigger) |
| `0xD5` | `vol_chg` | `b2 = volume` | Per-voice/track volume (`pvod = b2 << 8`) |
| `0xD6` | `vol_move` | `b1 = target` `b2 = speed` | Volume slide, linear ramp |
| `0xD7` | `ads_set` | `b0 = sustain(4b)` `b1 = decay(4b)` `b2 = attack(7b inv)` | ADSR: attack rate, decay rate, sustain level |
| `0xD8` | `srs_set` | `b2 = rate(7b inv)` | Sustain decay rate |
| `0xD9` | `rrs_set` | `b2 = rate(5b inv)` | Release rate, 0..31 |
| `0xDA` | `no_cmd` | — | No-op |
| `0xDB` | `no_cmd` | — | No-op |
| `0xDC` | `no_cmd` | — | No-op |
| `0xDD` | `pan_set` | `b1 = signed pan` `b2 = mode` | `panf = signed(b1)+20` on 0..40 (20=centre); `b0` unused |
| `0xDE` | `pan_move` | `b1 = target` `b2 = speed` | Pan slide, linear ramp |
| `0xDF` | `trans_set` | `b2 = semitones (signed)` | Global transpose |
| `0xE0` | `detune_set` | `b2 = signed` | Fine detune: `signed(b2)/64` semitones (`tund = signed(b2)<<2`) |
| `0xE1` | `vib_set` | `b0 = depth` `b1 = rate` `b2 = speed` | Vibrato (64-entry sine LUT) |
| `0xE2` | `vib_change` | `b2 = speed` | Vibrato change (adjust rate) |
| `0xE3` | `rdm_set` | `b0 = range` | Random pitch offset (LFSR) |
| `0xE4` | `swp_set` | `b0 = target` `b1 = ticks` | Portamento / note slide (no-op in driver) |
| `0xE5` | `sws_set` | `b2 = hold` `b1 = count` `b0 = speed` | Pitch **sweep** (not a static transpose) |
| `0xE6` | `por_set` | `b2 = speed` (0 disables) | Portamento: geometric approach from the previous note's pitch to this one, `swpd += (target−swpd)·b2/256` per tick — no separate target parameter, the target is the note's own pitch |
| `0xE7` | `lp1_start` | — | Loop 1 start marker |
| `0xE8` | `lp1_end` | `b0 = freq_delta` `b1 = vol_delta` `b2 = count` | Loop 1 end: repeat `b2` times |
| `0xE9` | `lp2_start` | — | Loop 2 start (nested in loop 1) |
| `0xEA` | `lp2_end` | `b0 = freq_delta` `b1 = vol_delta` `b2 = count` | Loop 2 end |
| `0xEB` | `l3s_set` | — | Loop 3 start (song-level loop) |
| `0xEC` | `l3e_set` | — | Loop 3 end (jump to l3s or end) |
| `0xED` | `kakko_start` | — | Bracket loop start (A-A-B form) |
| `0xEE` | `kakko_end` | `b2 = flag` | 0 → repeat A, 1 → continue to B |
| `0xEF` | `no_cmd` | — | No-op |
| `0xF0` | `no_cmd` | — | No-op |
| `0xF1` | `use_set` | — | No-op (unused in driver) |
| `0xF2` | `rest_set` | `b2 = ticks` | Advance timeline (wait) |
| `0xF3` | `tie_set` | `b2 = mode` | Tie/slur: 0 = off, 1 = on (no keyoff) |
| `0xF4` | `echo_set1` | — | No-op (echo set 1) |
| `0xF5` | `echo_set2` | — | No-op (echo set 2) |
| `0xF6` | `eon_set` | `b2 = voice_mask` | Reverb ON for selected voices |
| `0xF7` | `eof_set` | `b2 = voice_mask` | Reverb OFF for selected voices |
| `0xF8` | `no_cmd` | — | No-op |
| `0xF9` | `no_cmd` | — | No-op |
| `0xFA` | `no_cmd` | — | No-op |
| `0xFB` | `no_cmd` | — | No-op |
| `0xFC` | `no_cmd` | — | No-op |
| `0xFD` | `no_cmd` | — | No-op |
| `0xFE` | `no_cmd` | — | No-op |
| `0xFF` | `block_end` | — | End of track |

**Parameter convention** — every event is 4 bytes `b0 b1 b2 opcode`. Three
bytes of parameters match the raven source as:

```
mdata4 = b0    mdata3 = b1    mdata2 = b2
```

**After each `0xD2`** the sequence writes a setup block: `0xD7`, `0xD8`,
`0xD9`, sometimes `0xE5`. `0xD0` and `0xD5` appear once per track, at the top.

**No-ops** (`0xDA`, `0xDB`, `0xDC`, `0xEF`, `0xF0`, `0xF1`, `0xF4`, `0xF5`,
`0xF8`–`0xFE`) are present in the driver dispatch table with empty handlers.
`0xDC` appears ~35× per bank with `b0=15..254, b1=0..150` — possibly
repurposed in MGS2, but the renderer currently ignores it.

### 4.5 Reverb

Reverb in the PlayStation's SPU is a hardware effect — a configurable
multi-tap DSP (IIR + 4 comb filters + 2 all-pass filters). The sequence only
sends a voice to the reverb bus (`0xF6` flag per voice); the reverb parameters
themselves are set once per stage by the game engine and never stored in the SDX.

The renderer implements the authentic SPU reverb formula (psx-spx §7.12) in
`SPU_Reverb`. Seven presets are provided:

| Preset | Buffer size | Character |
|--------|-------------|-----------|
| `off` | 16 bytes | Bypass / silence |
| `room` | 0x26C0 | Small natural room |
| `studio_small` | 0x1F40 | Bright small studio |
| `studio_medium` | 0x4840 | Balanced medium studio |
| `studio_large` | 0x6FE0 | Wide studio space |
| `hall` | 0xADE0 | Concert hall |
| `space_echo` | 0xF6C0 | Long delay / echo chamber |

Each preset is a 32-register configuration (dAPF1 … vRIN) matching the SPU's
hardware register layout at `1F801DC0h`–`1F801DFEh`. The default is `hall`.

In `render_cue()`, each track accumulates its reverb bus signal into shared
buffers. After all tracks are mixed, the accumulated signal is processed through
`SPU_Reverb.process()` and mixed back into the output at the dry/wet ratio
set by the preset's vLOUT/vROUT volumes.

### 4.6 The shared instrument bank (programs beyond the directory)

Banks contain program-change events whose `b2` points **past the end of the
per-stage instrument directory**. These reference **instruments shared across
all stages**. In the original game they came from `wv00007f.wvx`, a common
sample bank loaded by the "init stage" of the PS2 sound library.

**Careful — "missing" programs are usually a parser bug, not a missing bank.**
Two false alarms were raised here before the directory parsing was fixed (§4.2):

- *"Programs 139–142 are missing."* No: the directory was **truncated** at the
  first custom envelope, so entries 135–149 were never read. Read correctly,
  `a01a/pk000011.sdx` holds **150** instruments and 139–142 resolve inside it.
- *"Programs reach 249."* No: that came from **phantom cues**. When a bank's
  directory and audio start are misread, the cue-table scan can latch onto
  noise, and the "program" bytes harvested from it are meaningless. Re-measured
  with the directory fixed, the **highest program actually referenced is 132**.

With the parser corrected, banks holding **150** instruments reference **no**
out-of-directory program at all — they are self-contained. Only the smaller
(~129-entry) banks still reach past their own directory, and only to
**129–132** — which is exactly the four common instruments this section
originally described. Establish the directory length before concluding anything
is missing.

The Master Collection does not ship these samples in a separate file. The
renderer stubs them with silence rather than dropping the events — the
sequencer still processes all note-on/off and envelope opcodes correctly, but
those instruments are simply **absent from every render**. Locating this shared
bank is the single biggest blocker to reproducing the game's music faithfully;
if it is found, the stub can be replaced by loading the samples into
`voice_tbl[129..]`.

### 4.7 A note on method

Three separate attempts at the envelope opcodes produced files that were
*bit-for-bit identical* to the control. The theory was coherent each time; the
cue being rendered simply contained no envelope opcodes at all. The lesson, paid
for in three rounds of listening:

**Before testing a hypothesis about an opcode, check that the data you are
testing on actually contains it.**

Likewise, every "it sounds better" here was checked against a control render,
and the two files compared byte by byte before anyone was asked to listen.

---

## 5. SPU ADSR envelope

The PlayStation 1's SPU contains a hardware ADSR envelope unit with four
phases: Attack → Decay → Sustain → Release → Off. Each phase runs at a
per-sample tick rate derived from a counter + step scheme (nocash psx-spx §5).

### 5.1 Opcodes

| Opcode | Name (raven) | Parameters | Effect |
|--------|--------------|------------|--------|
| `0xD7` | `ads_set` | `b0 = sus_lvl(4b)` `b1 = dec_rate(4b inv)` `b2 = atk_rate(7b inv)` | Set attack rate, decay rate, sustain level |
| `0xD8` | `srs_set` | `b2 = sus_rate(7b inv)` | Set sustain decay rate |
| `0xD9` | `rrs_set` | `b2 = rel_rate(5b inv)` | Set release rate |

Rates are **inverted**: 0 = slowest/hold, max = fastest. The renderer applies
`(~bX) & mask` to recover the internal rate value.

### 5.2 Phase behaviour

**Attack** — counter steps toward 0x7FFF; linear or exponential (`mode` flag).
Rate 0 (hold) = counter never changes, envelope stays at 0 (silent note).
Rate 127 (fastest) reaches peak in ≈3 samples.

**Decay** — steps from 0x7FFF down to target `(sus_lvl+1) × 0x800`.
Rate 0 (hold) = never decays. Rate 15 (fastest) drops in ≈5 samples.

**Sustain** — holds at the decay target. If `sus_rate` > 0, the envelope
continues to decay toward 0 at that rate (linear or exponential). The default
`sus_rate = 0x7F` means infinite hold (no sustain decay, matching the SPU
convention that `(rate & rate_mask) == rate_mask` = hold).

**Release** — triggered by note key-off (`gate_pct`). Steps from current
envelope value down to 0. Rate 0x1F (default) = hold (never releases). Rate 0
(fastest) fades in ≈5 samples.

### 5.3 Default values

When a track starts without `0xD7`/`0xD8`/`0xD9`, the renderer uses:

| Parameter | Value | Meaning |
|-----------|-------|---------|
| `atk_rate` | 0 | Fastest attack |
| `dec_rate` | 0 | Fastest decay |
| `sus_lvl`  | 15 | Maximum sustain (no drop) |
| `sus_rate` | 0x7F | Hold (no sustain decay) |
| `rel_rate` | 0 | Fastest release |

### 5.4 Implementation

The SPU_ADSR class in `render.py` mirrors DuckStation's `VolumeEnvelope`
(`TickADSR` method). Its key design points:

- **Per-sample tick**: every output sample calls `tick()` which checks the
  current phase, computes the step (from counter + rate decode LUT), and
  advances the envelope by that step.
- **Counter-increment decode**: Attack rates use a different LUT than
  decay/sustain/release rates, matching the PS1 SPU hardware. This is
  responsible for the distinctive "fast then slow" shape of real SPU envelopes.
- **Linear / exponential**: Each phase can run in linear or exponential mode.
  Exponential mode scales the step by the current envelope value, creating a
  concave shape typical of analogue synthesizers.

---

## 6. Substance (2003) — PC audio formats

The Substance release (2003) uses a different set of audio files from the Master
Collection. The underlying codecs are the same (PS-ADPCM, MS-ADPCM) but the
container layout differs.

### 6.1 `vox.dat` — voice archive

PAC-wrapped file containing all character voices, exclamations, footsteps, etc.

| Offset | Field |
|--------|-------|
| `0x00` | PAC header `10 00 00 00` (not the usual SDT `01` header) |
| `0x04+` | SDT blocks, each a standard PS-ADPCM stream at 44 100 Hz mono |

- **53 601 blocks** in the tested file, ~2.7 MB total.
- `parse_sdt()` works directly on each block's offset; the PAC header is
  skipped automatically.
- Each block decodes like a standard `.sdt` file (PS-ADPCM, 28 samples/frame).
- `detect_path()` returns `None` because the outer header is PAC, not SDT.
  The VOX tab opens the file directly without auto-detection.

### 6.2 `bgm.dat` — streamed music

Pre-rendered MS-ADPCM music, same container format as the Master Collection
`bgm.dat`. Parsed by `parse_bgm()` unchanged.

- **98 entries**, 44 100 Hz stereo, MS-ADPCM.
- Total duration ~25 minutes.
- Also used for `movie.dat` (90 entries, same format).

### 6.3 `demo.dat` — cutscene / demo audio

Same MS-ADPCM format as `bgm.dat` but dedicated to cutscenes and
demonstrations.

- **135 entries**, MS-ADPCM, stereo.
- Parsed by `parse_bgm()`; the DEMOS tab opens it with a dedicated
  `.dat` file filter.

### 6.4 `pk000000`–`pk000005.sdx` — stage banks

Six sound-effect banks, same SDX container format as Master Collection but
with a different internal layout:

- `voice_tbl` (instrument directory) is **not at offset `0x800`**.
- Scan mode is not supported (the directory-finding heuristic from
  `find_stage_folder()` is Master Collection–specific).
- Open-only mode: browse, listen to samples, replace a sample in a single bank.
- 22 050 Hz mono, PS-ADPCM. 126 samples total across the six banks.

### 6.5 `codec.dat` — unknown format

Header `b9 2a 90 3d`. Not parsed by any existing reader. Reverse engineering
is still needed. Excluded from the UI for now.

### 6.6 Other Substance files

- `face.dat` — face animation data (not audio).
- `movievr.dat` — small (32 KB) index file, not audio.
- `cache.dar` / `cache.qar` — archive containers, not directly audio.

---

## 7. What is still unknown

- **Song orchestration is in the Unity binary** — for Master Collection (2023),
  the release this section documents. The `.sdx` files contain only individual
  cues (phrases, jingles, layers); their ordering into a complete stage song is
  compiled into `METAL GEAR SOLID 2.exe` (il2cpp). There are no JSON, XML, or
  Lua config files to read. This is not in tension with `docs/ORCHESTRATION.md`'s
  external **`mdx`** file hypothesis — that file belongs to the original PS2
  driver (`raven`), which MC's Unity reimplementation doesn't necessarily carry
  forward in the same form. Whether an `mdx`-equivalent still exists somewhere in
  MC's data (or only in the original PS2/Substance release) is exactly what's
  still unresolved.
- **The `.sdx` header** below `0x800`: a handful of small u32 values, the rest
  zero. Their meaning is unknown.
- **The cue table's `kind` byte** and its two flags.
- **The bank table of §3**, whose record types beyond the pointer are opaque.
- ~~**The non-PS-ADPCM `.sdt` files.**~~ **RESOLVED** — they are Konami XWMA
  (`AMWX`, WMA v2) inside a multiplexed container. De-interleave the audio
  stream, strip the 16-byte packet padding, rewrap as standard RIFF xWMA, and
  ffmpeg decodes it cleanly. **Replacement** is also supported: a WAV encoded
  by **xWMAEncode** → RIFF xWMA → `AMWX` (`riff_to_amwx`) → re-muxed into the
  container at its exact original size (`replace_amwx_in_sdt`). ffmpeg cannot
  encode this — its wmav2 needs codec-private extradata the `AMWX` header
  can't store, so the game rejects ffmpeg output; xWMAEncode's does not.
  See `formats/xwma.py` (adapted from RockeyLol's MIT converter), `ffmpeg.py`,
  and `xwmaencode.py`.
- **The `.sdx` sample rate for effects.** Confirmed by ear at 22050 Hz, not read
  from the file. It may vary per bank.
- **Where cutscene music lives.** It appears to be mixed into the dialogue audio
  rather than sequenced.
- **What the `0xDC` no-op does.** It appears ~35× per bank with non‑zero
  parameters (`b0=15..254, b1=0..150`), suggesting MGS2 may repurpose it.

### 7.1 How the opcodes were cracked

The **KieronJ/raven** repository (`kieronj/raven` on GitHub) is a C port of the
PS2 sound library written by **Kazuki Muraoka** — the same library used by
Konami in MGS2, MGS1, and Zone of Enders. The relevant source files are:

| File | Contents |
|------|----------|
| `sd_sub1.c` | `tx_read()` — the main sequencer dispatch loop |
| `sd_sub2.c` | Opcode handlers (`cntl_tbl` dispatch table)  |
| `sd_incl.h` | Data structures, constants, macros |
| `spu.h` | SPU register layout and LUTs (sine, pan) |

The 18 formerly-unknown opcodes were identified by matching byte values against
the `cntl_tbl` dispatch table. Every opcode from `0xD0`–`0xFF` has a named
handler there; the renderer now implements all 29 of them.

---

## 8. Acknowledgements

The stereo interleave was found because a listener said the voices sounded like
they were "jumping left and right five or six times a second" — a description
worth more than any statistic. The sequencer was cracked the same way: someone
listened to a render and said "the notes don't last as long as they should",
which is how the sample loops were found.

SpaceCore0352 confirmed early on that the music was "constructed using samples
from the sdx files, similar to a midi file, but so far nobody has completely
cracked it". Several of the findings above came from someone playing files one
by one and noticing what was wrong.
