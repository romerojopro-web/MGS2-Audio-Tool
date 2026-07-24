# Reverse-engineering the in-game music engine (MGS2 MC exe)

Working notes from disassembling `METAL GEAR SOLID2.exe` to find where the
**in-game (mission) music** comes from and how it is driven. This is the deep
follow-up to `docs/ORCHESTRATION.md`; that file has the high-level synthesis,
this one has the addresses.

**Bottom line so far:** the PlayStation-2 **`raven` sound driver is compiled into
the PC exe**, and the in-game music runs on it — not Unity, not a stream. The
command flow, the SPU voice table and the playback cursor are located. The one
remaining unknown is the **`sng_data` song-table pointer** (where the music bytes
live and who loads them).

> **Legal basis.** This is **reverse engineering for interoperability** — study
> of the game's audio engine so that this tool (a mod utility for a game you own)
> can work with it. That purpose is permitted under the EU Software Directive
> (2009/24/EC, Art. 6) and French law (CPI L122-6-1), and is performed on the
> user's own legally-owned copy. **No game executable — protected or not — and
> no game data are included in or distributed by this repository.** Obtaining a
> statically-readable image of a retail binary, and the means of doing so, are
> the reader's own responsibility and outside the scope of this repo.

---

## Setup

- The retail exe applies a **technical protection measure**: `.text` is not
  readable at rest (entropy 7.999; entry point sits inside a `.bind` section).
  That is why an early plaintext string-scan found the strings but **zero** code
  references.
- All addresses below are for a **locally-readable image** of the executable —
  one whose `.text` is real x64 code (entropy ~6.5). How such an image is
  obtained is outside this repo's scope.
- Analysed with **capstone + pefile** in Python (Ghidra needs JDK 21; only a
  JRE 17 was on the machine). Tools live in `scripts/re/`:
  - `pe_map.py` — sections, image base, file-offset ↔ VA.
  - `xrefs.py` — RIP-relative `lea` references to a string/address.
  - `hunt.py` — occurrences of the raven sound-code immediates; call xrefs.
  - `data_xrefs.py` — read/write references to a data global (per-`.pdata` fn).
  - `analyze.py <VA>` — disassemble the function containing VA, resolving
    strings / data / call targets, using the `.pdata` function table.
  - `summarize.py <VA>` — same, but print only calls + string/data refs.

- Image base `0x140000000`. Sections: `.text` `0x140001000`, `.rdata`
  `0x140722000`, `.data` `0x1407CD000`, `.pdata` `0x1417E0000` (23112
  `RUNTIME_FUNCTION` entries — exact function boundaries).

## Key strings (in `.rdata`, plaintext)

| VA | String | Notes |
|----|--------|-------|
| `0x14072FAC0` | `%s/stage/%s/pk%06x.sdx` | the SDX filename pattern; referenced 3× at `0x6135F`, `0x61B4A`, `0x62021` |
| `0x14072FB00` | `*** ERROR: SoundData(voi):mtrack=%x` | loaded by stub `0x1400692E6` → `jmp` debug-printf `sub_1400492B0` |
| `0x14072FA48..A8` | `host0:./sound/{vox1,wvx1,mdx1,efx1,sdx1}/` | **0 references** — dead PS2 dev strings |

## The sound-code command system (raven survives)

raven drives everything with 32-bit **sound codes**, present as literal immediates
in `.text`:

| Code | Meaning |
|------|---------|
| `0x01000001`..`0x01000008` | PLAY song 1..8 |
| `0x01FFFF01` / `0x01FFFF02` | PAUSE / RESUME |
| `0x01FFFFFF` | STOP |
| `0x01FFFF20` | First-Person mode on |
| `0x01FFFF10` | (raven: Evasion/ALERT — not yet confirmed as a literal here) |

Game code sends them from many sites (`sub_140120xxx`, `sub_140130xxx`, …).

## Command flow

```
game event ──▶ sound code (ecx)
   │
   ▼
sub_14006F8D0   command intake
   - recognises PLAY-song  (ecx-0x1000001 <= 7)
   - stores the code to global  0x141540854  ("current music code")
   - jmp sub_14005D740 ─▶ sub_14005E080 ─▶ … (thunk chain into the handler)
   │
   ▼
sub_14006225B   the big dispatcher (~5 KB, one function)
   - cmp 0x1000001 ; 8 identical cases (PLAY song1..8) ─▶ common handler 0x140062B1D
   - cmp 0x1FFFF01 (PAUSE) … etc.
   - a block of `movups` into 0x141783xxx = driver-state init
```

## The SPU voice table (raven `voi_data[24]`)

In the PLAY common handler at `0x140062B1D`:

```asm
lea  r14, [0x14177EB00]      ; voice-table base
cmp  eax, 0x18               ; 24 voices
lea  rcx, [rax + rax*8]      ; index * 9
shl  rcx, 5                  ; * 32   → index * 0x120 (288 bytes/voice)
add  rcx, r14                ; &voice[index]
mov  [0x14177EAF8], rcx      ; "current voice" cursor (a POINTER, not a struct)
mov  rax, [rcx]              ; voice->[+0] = a pointer
```

So:
- **`0x14177EB00`** = base of **24 SPU voices, 288 (`0x120`) bytes each**.
- **`0x14177EAF8`** = a global cursor holding `&voice[current]` (85 reads across
  the driver's operation functions; written only inside `sub_14006225B`).
- **voice field `+0` = the playback cursor**: the current read position in the
  track's event stream (same opcode/note format the tool's sequencer decodes).

Driver-state field offsets seen: `+0x50`, `+0x54`, `+0x58` (clamped to ±`0x7f0`),
`+0x101`. Other audio globals cluster at `0x141540048..8C`, `0x1417831xx..3xx`,
`0x1417DBC7C`, `0x14177E6A0..A8`.

## What remains — the last piece

Find the **`sng_data` base pointer** (raven's song table: `n_songs`, then a
per-song table, then up to 13 track addresses stored as 24-bit values) — the
value that gets written into `voice[+0]` when a song starts — and **who writes
it**, i.e. where the music bytes come from (embedded in the exe? generated? a file
we have been misreading?).

Two ways in, and the readers are now located:

- **Reads of the current-code global `0x141540854`** (found via a generalised
  RIP-relative scan): in **`sub_14006F610`** (a small wrapper, `jmp
  sub_14006F8D0`) and around **`0x14006F670`** — the per-frame consumer that
  reacts to "play song N". Start here.
- **References to the voice-table base `0x14177EB00`**: in the dispatcher
  `sub_14006225B` (known) and in **`sub_1400643E0`** — a large function that is
  almost certainly the **per-frame voice/sequence tick** (reads each voice's
  `+0` cursor, advances it through the event stream). That is the driver's own
  sequencer running; trace what sets a voice's `+0` and you have the song data.

### Strong hypothesis to test next

The exe builds **only one** audio filename pattern — `pk%06x.sdx` — and loads
nothing else per stage (ProcMon confirmed). The voices read event streams in the
**same opcode format as the `.sdx` cues**. So the 13-track song data very likely
lives **inside the loaded `.sdx`** (in the sequence region past the cue table,
`fsize-0x5800`), and `sng_data` is a pointer *into* a loaded `.sdx` — not a
separate file. If true, we already have the bytes; we just need the song-table
layout (which cue/track offsets a "song" strings together). Confirm by seeing
whether the pointer written into `voice[+0]` lands inside a loaded `.sdx` image.

**Ruled out (2026-07-25):** the BGM is **not embedded in the exe as raw event
streams**. Scanning `.rdata` and `.data` with raven's event grammar (4-byte
events, opcode last, tempo/program present, pitches in register) yields only tiny
noise-level blobs (≤47 "events", no tempo/program density) — no song-sized
sequence data. Combined with the earlier `.text` scan (also nothing), the music
bytes are not sitting in the exe in the sequencer's own format. So either they
live in the loaded `.sdx` (the strong hypothesis above), or they are stored
compressed / in a transformed layout that this grammar can't see. The
`0x14006F680` routine copies a `.rdata` template (`0x140947230`) into the audio
state — a config/default block, not song data.

Once `sng_data` and its loader are known, the whole chain is closed and the
tool's existing sequencer/synth can render a real in-game song — likely a new
**Orchestration** tab (up to 13 simultaneous tracks + the transition sound
codes), separate from the current cue Sequencer.

## Reproducing / continuing

```bash
pip install capstone pefile      # already present on the dev machine
# set EXE at the top of the scripts/re/ tools to a locally-readable image
python scripts/re/analyze.py 0x14006225B   # the dispatcher
python scripts/re/analyze.py 0x140062B1D   # PLAY-song common handler (voice setup)
```

> Any local image of the executable stays on the dev machine; it is **not** in
> the repo (no game files are ever committed — `.gitignore` blocks `*.exe`).
