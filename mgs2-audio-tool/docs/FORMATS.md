# MGS2 audio formats

Reverse-engineering notes for the audio files of **Metal Gear Solid 2: Sons of
Liberty** (Master Collection, PC). Everything here was found by analysing files
and confirmed by ear; none of it comes from official documentation.

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
to be WMA-family audio wrapped in a Konami container. Those files cannot be
decoded by a PS-ADPCM decoder and should be reported, not played.

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
0x0000 .. 0x1000   header (mostly zero; a handful of u32 fields at the start)
0x1000 .. <pad>    audio: PS-ADPCM samples laid end to end
<pad>              0xFF padding, frame-aligned, marks the end of the audio
<table>            the bank table
<tail>             sequence / sound-program data
```

Audio always begins at **`0x1000`**.

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

## 4. What is still unknown

- **Music.** Not found. The `.sdt` music encountered so far is incidental — a
  cutscene where a track plays under dialogue, a VR mission's end jingle. Where
  the game's actual soundtrack lives is an open question. The `.sdx` tail
  (the sequence data) is the most likely lead: if the music is sequenced from the
  same sample banks, there may be no separate music files at all.
- **The `.sdx` header** (`0x0000`–`0x1000`): a handful of small u32 values are
  used, the rest is zero. Their meaning is unknown.
- **The `.sdx` bank table record types.** Only the pointer field is understood.
- **The `.sdx` tail.** Untouched, undecoded.
- **The non-PS-ADPCM `.sdt` files.** Structurally mapped, codec not decoded. The
  most promising route is Microsoft's `xWMAEncode.exe`, since ffmpeg rejects the
  padded bitstream.
- **The `.sdx` sample rate.** Confirmed by ear at 22050 Hz, not read from the
  file. It may vary per bank or per sample.

---

## 5. Acknowledgements

The stereo interleave was found because a listener said the voices sounded like
they were "jumping left and right five or six times a second" — a description
worth more than any statistic. Several of the findings above came from someone
listening to files one by one and noticing what was wrong.
