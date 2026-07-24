# Changelog

## Unreleased

### Fixed — the SDX parser no longer invents samples in music banks
Stage banks close their audio with frame-aligned padding, and the parser only
recognised `0xFF`. A sweep of all **600** stage banks of a real install showed
the ~80 **music/sequencer** banks pad with **`0xFE`** instead — so on those the
scan ran past the end of the audio and carved phantom "samples" out of the cue
table and sequence behind it (~32 KB per bank), which then polluted the
cross-bank scan and grouping. Both padding bytes are now accepted; verified on
the real banks (audio now ends at the padding, SE banks unchanged).

### Documented — the SDX format, measured over 600 real banks
The format notes were written from six banks and generalised too far:
- **Audio does not reliably start at `0x1000`.** It starts where the `0x800`
  table ends: `0x9E0`–`0x1070` in practice, and only **12 of 600** banks land on
  `0x1000` exactly.
- **There are two kinds of `.sdx`.** In **SE banks** (~520) the `0x800` table is
  an **SPU voice table** (addresses in SPU space, not file offsets — ~98 of 99
  entries do not resolve); in **music banks** (~80) it is the sequencer's
  instrument directory. The record signature is identical, so they can only be
  told apart by whether the offsets land inside the audio region.
- **The shared instrument bank is far bigger than "programs 129–132".** The
  out-of-directory programs actually referenced reach **249** (program 139:
  6987 refs, program 249: 6539), and **392 of 600** banks use at least one.
  They render as silence — locating that bank is the main blocker to
  reproducing the game's music faithfully.

## 4.2.0 — 2026-07-23

### Added — replace stock XWMA audio (via xWMAEncode)
The SDT tab can now **replace** stock (Konami XWMA) `.sdt` audio, not just
decode it. Pick a WAV; it is re-encoded to XWMA and re-injected into the
game's multiplexed container **at the exact original size** (shorter audio is
zero-padded; audio too long or too large to fit is refused with a clear
message).
- New `formats/xwma.py` functions `riff_to_amwx`, `replace_amwx_in_sdt`,
  `build_replacement_sdt`, `xwma_capacity` (adapted from RockeyLol's
  RifftoKon.py + SDT_buld.py, MIT) — validated by rebuilding real game files
  byte-for-byte and decoding them back identically.
- Encoding uses **xWMAEncode.exe** (Microsoft DirectX SDK tool), not ffmpeg:
  ffmpeg's wmav2 needs codec-private extradata the `AMWX` container has no
  slot for, so the game can't decode it — proven during development. New
  optional bridge `mgs2_audio/xwmaencode.py`; the SDT tab prompts for the exe.
- The container re-mux preserves every other stream and the file's exact size.
- The WAV is first conformed (via ffmpeg) to the original clip's channel count
  and sample rate: a stereo WAV dropped where the game expects mono is rejected
  in-game even though a lenient player would preview it fine.
- A stock original opened as `*.sdt.vortex_backup` is saved back under its real
  `*.sdt` name, so the file the game loads is named correctly.

**Confirmed in-game:** a replaced voice line was re-encoded, re-injected, and
played back correctly in the running game — the full WAV→game path works, not
just the offline round-trip.

### Fixed — upgraders keep their tagging work
Loading and saving the SDT tag database on this version is now guaranteed
additive: the new `*.sdt.vortex_backup` entries are an independent key, and a
folder rescan only ever refreshes cache fields, so a user's hand-typed
done/tag/speaker/notes from a previous version are never overwritten. Pinned
by regression tests.

## 4.1.0 — 2026-07-21

Decode the game's **stock** audio without any mod, a **Russian** interface, and
a correction on where the Unity music actually plays. Master Collection stays
the stable focus; Substance remains work-in-progress.

### Added — Russian interface language
The UI is now available in **Russian** (Русский) alongside French, English and
Spanish — a full fourth translation of all 236 strings, selectable from the
language dropdown.

### Added — stock (un-modded) `.sdt` audio now decodes: Konami XWMA via ffmpeg
The stock MGS2 MC `.sdt` audio is **Konami XWMA**, not PS-ADPCM — a multiplexed
container whose `AMWX`/WMA v2 stream is interleaved with other streams. The SDT
tab now **de-interleaves and decodes it** (listen + export to WAV), so the tool
works whether or not the Better Audio Mod is installed:
- New `formats/xwma.py` (container de-interleaving + AMWX→standard RIFF xWMA)
  and `ffmpeg.py` (optional external-binary bridge — the first in the project;
  found via PATH or a path you set in the SDT tab).
- The SDT tab auto-detects the codec and routes stock files through ffmpeg;
  when ffmpeg is missing it explains how to install it and offers a
  "Locate ffmpeg.exe…" button.
- The de-interleaving and AMWX→RIFF conversion are adapted, with thanks, from
  **RockeyLol/RIFF-XWMA-Konami-XWMA-Converter** (MIT) — see the README
  acknowledgements. Confirmed decoding real voice/cutscene files end to end.
- **Replacing** stock XWMA (re-encoding) is not implemented yet; export works,
  replacement remains PS-ADPCM-only.
- On a Vortex-modded install the stock originals are `*.sdt.vortex_backup`;
  the voice-folder scan and the Browse dialog now list those too (verified
  they decode identically to the Better Audio Mod's audio across 20 files).
  A checkbox in the SDT tab hides them so you can work on just the mod's
  PS-ADPCM files.

### Corrected — the Unity music bundles drive the LAUNCHER, not gameplay
A second in-game test (replace INFILTRATION, then actually play a mission)
showed the 4.0.0 claim "music replacement confirmed in-game" was
over-generalised: **the Unity `.wav.bundle`s only feed the launcher**
(pre-launcher/menu music, credits, the scenario app's music player). The
replacement pipeline itself (FSB5 rebuild, audio conforming, Addressables
catalog CRC patch) works exactly as described — the launcher does play the
replaced audio — but gameplay music is served elsewhere. README,
`docs/ORCHESTRATION.md` and the tab's interface text now say so.

The in-game music trail is under active research: `METAL GEAR SOLID2.exe`
still contains the PS2 path `host0:./sound/mdx1/`, and the per-stage
`assets/sar/us/gbs_stage_*.sar` files (15-18 KB — the predicted `mdx`
size) contain records typed in the raven expression-opcode range
(pan/transpose/detune/vibrato/random-pitch) plus `.sdx` cue references.
Analysis scripts live in `scripts/`.

## 4.0.0 — 2026-07-13

The tool grows from an SDT dialogue editor into a full audio suite — hence
the major bump. Master Collection support is stable (all tabs verified
against the real game, music replacement confirmed in-game); the Substance
(2003) side is a work in progress (browse/export only). See the project
status section of the README.

### Added — Musique · BGM tab for Master Collection (listen, export, **replace**)
**Confirmed working in the real game** (2026-07-13): a replaced track plays
in Master Collection once both locks below are handled — the FSB5 container
and the Addressables catalog CRC.
Master Collection's real scenario music turned out not to use the PS2 `mdx`
system at all: it's 6 standard Unity `AudioClip`s in `UnityFS` AssetBundles
under `launcher_Data/StreamingAssets/…/mgs2/bgm/` (full discovery notes in
`docs/ORCHESTRATION.md`). A new MC-only tab exposes them, built for modding:
- **Browse** the 6 tracks by their real catalog names (ARMS DEPOT, BATTLE,
  COUNTDOWN TO DISASTER, INFILTRATION, IT'S THE HARRIER, YELL "DEAD CELL")
  after picking the game's install folder once (remembered). The launcher's
  own music is included too: the main-menu theme and the credits theme
  (one clip shared by the `credits` and `license` catalog entries — shown as
  a single merged track), discovered from a full 404-bundle scan of the
  install. The remaining audio bundle — 13 launcher UI sounds sharing one
  `.resource` — is out of scope for now (replacing one clip means repacking
  the whole shared resource).
- **Each track shows its exact path relative to the game root** — the modder
  always knows which file to swap.
- **Listen / export to WAV**, same workflow as the other tabs (tagging too,
  own database file `mgs2_mc_bgm_library.json`).
- **Replace a track with any 16-bit WAV**: the tool rewrites the bundle's
  internal `.resource`, updates the AudioClip metadata, and produces a
  drop-in `.bundle` under the game's expected filename. An optional
  "install into the game" button copies it into place with a `.bak` backup
  of the original first; generating never touches the game's files.
- **The replacement is disguised as the original** (learned from a real
  in-game test that black-screened the launcher): the `.resource` is not
  bare audio but a **FSB5 container** (FMOD Sound Bank), so the tool now
  builds a valid FSB5 (codec PCM16, loop chunk carried over from the
  original so looping BGM keeps looping) and **conforms the user's WAV to
  the original clip exactly** — mixed to the same channel count, resampled
  to the same rate, padded with silence or trimmed to the same frame count.
  `m_Length` and every other serialized field stay untouched; only the
  compression format (Vorbis → PCM, describing the actual contents) and the
  resource size change. Verified locally by decoding the rebuilt bundle
  through real FMOD — the same engine the game runs.
- **The Addressables catalog CRC check is disabled per installed bundle**
  (the second in-game blocker): `aa/catalog.json` stores a CRC32 and size
  per bundle, and the game refuses any modified bundle whose CRC no longer
  matches. "Install into the game" now also patches that catalog entry
  (`m_Crc` → 0, `m_BundleSize` updated) via constant-length in-place JSON
  surgery — no other catalog offset moves — with a `catalog.json.bak`
  backup the first time.
- New format module `formats/mcbgm.py` + `ui/mcbgm_page.py`; needs the
  **optional `UnityPy` dependency** (the rest of the tool still runs without
  it — the tab explains how to install it instead of crashing).
- Tests in `tests/test_mcbgm.py`: WAV loader / folder discovery run by
  default with no game data; the full replace round-trip against a real
  install is `--realdata`-gated (and light — seconds of PCM, no heavy decode).

### Fixed — wasted CPU on silence, real-data tests no longer run by default
Found while investigating the test suite pinning a CPU core hard enough to hit
100°C on a real machine.
- **`replace_audio()` always pads/trims to the target `.sdt`'s exact capacity
  before encoding** (required — the game needs the file size unchanged) —
  meaning even a one-second dub triggered a brute-force PS-ADPCM search
  (5 filters × 13 shifts per 28 samples) across tens of thousands of *silent
  padding* samples. `codec/psadpcm.py`'s encoder now fast-paths any all-zero
  28-sample block straight to filter 0 / shift 0 (provably lossless — filter 0
  predicts zero regardless of history), skipping the search entirely for
  silence. This speeds up real dubbing, not just tests.
- **Tests against real game files (`vox.dat`, `demo.dat`) are now opt-in**
  (`pytest --realdata`) instead of running automatically whenever the files
  happen to be present — parsing a 1+ GB file in pure Python is slow and
  genuinely CPU-heavy, and doing it on every plain `pytest` run doesn't match
  the project's "no game data needed" testing philosophy. Skipped by default.
- One test (`test_replace_pads_short_audio_and_trims_long`) was asserting the
  same size-preservation invariant against a needlessly large target — its
  "trims long audio" half now uses a dedicated single-block target instead of
  the shared 6-block fixture (same coverage, ~6× less real, non-silent audio
  for the encoder to search).
- Net effect: the default `python -m pytest` run went from ~56s to ~14s.

### Added — tagging on every tab, one database folder per game
- **The tagging database folder is now per game/mode**, not one setting shared
  by everything. `MainWindow.db_folder` is a property backed by
  `{mode_id: path}` in the config (transparently migrated from the old flat
  string, so existing users keep their folder on upgrade). A new picker in the
  app header (next to the mode/language selectors) is always visible, fixing
  the fact that **Substance mode previously had no way to pick a database
  folder at all** — only the MC-only SDT tab had that button.
- **Tagging (done / tag / notes) now exists on every tab that can use it**:
  VOX, BGM, Dém (Substance) and Séquenceur (MC) join SDT and SDX. Each tab
  keeps its own JSON file in the chosen folder (`mgs2_vox_library.json`,
  `mgs2_bgm_library.json`, `mgs2_demos_library.json`, `mgs2_seq_library.json`)
  so tags never bleed between tabs or between MC/Substance.
- The shared panel (checkbox, tag field with autocomplete, notes, save button)
  is now a reusable `TaggingMixin` (`ui/widgets.py`), extracted from `SDXPage`
  and applied to the four new tabs — one implementation instead of five
  near-identical copies.

### Fixed — full audit pass (interface, logic, architecture)
A full read-through of every file in `mgs2_audio/` against real game data
(`scripts/sdx_mgs2_MC/`, `tests/mgs2_substance_2003/`), done before starting new
reverse-engineering work. Full detail in `docs/AUDIT.md`.
- **Reverb was structurally wrong on every cue rendered with a non-`off` preset**
  (default `hall`): the SPU reverb's four reflection taps all overwrote the same
  buffer slot, discarding three of them. Fixed to match the psx-spx formula already
  documented in `docs/FORMATS.md` §4.5 — changes the sound of reverberated renders.
- **A track's ringing note wasn't cut when the next note-on fired**, contradicting
  the documented "one voice per track" rule; could smear into audible overlap on a
  slow release. Fixed.
- **The playback slider/time/auto-play broke after the first file change in every
  tab** (SDT, SDX, VOX, BGM, Dém, Séquenceur) — a signal-disconnect bug that had been
  there since the shared `PlaybackMixin` was introduced. Fixed.
- **`sdx replace-all` could silently back up an already-modified file as if it were
  the pristine original**, and wrote game files non-atomically (no protection against
  a crash or full disk mid-write). Writes are now atomic; a batch reports exactly
  which banks changed and which failed instead of dying silently mid-way.
- Smaller fixes: temp-file leaks on the VOX/BGM tabs, scan Cancel not actually
  stopping, the voice folder not reloading on startup, an endianness bug in Sequence
  format detection, an off-by-one that dropped a legitimate final audio block, a
  trailing-chunk drop on odd-length stereo streams, PS-ADPCM edge cases (invalid
  shift, encoder/decoder rounding mismatch), a 32-bit float WAV import giving a
  cryptic error, and non-ASCII characters crashing the CLI on a default Windows
  console.
- Dead code removed: unused `REGISTRY` imports in both game plugins, four unused
  `GamePlugin` attributes (`default_theme`, `themes`, `formats`, `detect`), and the
  never-wired `library_filenames` attribute — replaced by giving Substance its own
  SDX tag database file instead of sharing Master Collection's.
- **Docs restructured**: `REPRISE.md`, `SESSION_DECOUVERTES.md` and `AUDIT_REPRISE.md`
  (three overlapping, partly stale session logs) replaced by a single living
  `docs/AUDIT.md`. Fixed a stale opcode table row and a CLI example in `README.md`
  that referenced commands that don't exist (`sdx cues`/`sdx render` → `seq cues`/
  `seq render`).

### Architecture — plugin system for multi-game support
- **Plugin architecture** replaces monolithic game-specific code. Each game is
  a subpackage in `mgs2_audio/games/<id>/` that exports a `GamePlugin` subclass
  and registers itself with the global `REGISTRY` on import. The UI shell
  (`app.py`, `cli.py`) never imports game-specific code directly.
- **Core interfaces** (`mgs2_audio/core/`): `GamePlugin` ABC, `PageSpec`,
  `AudioFormat`, `AudioContainer`, and the `REGISTRY` discovery mechanism.
  `discover()` scans `games/` subpackages via `pkgutil.iter_modules` at import
  time — new games are picked up automatically.
- **Architecture migration**: existing `mgs2_mc` and `mgs2_substance` plugins
  were moved into `games/` as self-contained plugins. All imports use absolute
  paths (`from mgs2_audio.library.db import ...`) rather than fragile relative
  imports that break outside an installed package.
- The tool is now positioned for **any Metal Gear Solid game** (MGS3, Portable
  Ops, etc.) or even Zone of Enders — each gets its own mode, colour theme,
  tabs and CLI subcommands.

### UI — Substance (2003) gets its own four tabs
- **MODE_REGISTRY** replaces the old `MODE_TABS` mapping. Each mode now declares
  its own list of pages, subtitle key, and a complete stylesheet — zero state
  leakage when switching.
- **Substance mode** shows four dedicated tabs: **VOX** (vox.dat), **SDX**
  (pk*.sdx banks), **BGM** (bgm.dat / movie.dat), **Dém** (demo.dat cutscenes).
  Master Collection keeps its three tabs (SDT, SDX, Sequencer).
- New `DEMOSPage` (`demos_page.py`): thin subclass of `BGMPage` that reuses all
  playback and export logic, overriding only the labels and file dialog filter.
- `SDTPage` in Substance mode: hides the voice-folder library panel (not
  applicable to a single vox.dat), opens `.dat` files via `dlg_open_vox`, shows
  a vox.dat-specific hint when no file is loaded.
- `SDXPage` in Substance mode: hides the scan button (Substance's internal
  layout differs; scan mode is not supported).

### UI — full per-mode stylesheet recolour
- `STYLE_SUBSTANCE` in `theme.py` is a complete amber CSS for every widget
  (buttons, sliders, lists, inputs, checkboxes, tabs, status bar). Switching
  mode recolours the entire window — the active release is always obvious.
- `STYLE` (green, Master Collection) is unchanged.

### Added — Substance audio formats
- **vox.dat**: PAC-wrapped PS-ADPCM (44 100 Hz mono). 53 601 SDT blocks.
  `parse_sdt()` works directly (PAC header is skipped).
- **bgm.dat**: MS-ADPCM streamed music (98 entries, 44 100 Hz stereo).
  `parse_bgm()` works unchanged.
- **demo.dat**: MS-ADPCM cutscene audio (135 entries). Same format as bgm.dat.
- **movie.dat**: MS-ADPCM movie audio (90 entries). Same format as bgm.dat.
- **pk000000–000005.sdx**: six stage banks (22 050 Hz, 126 samples total).
  Standard SDX format; scan mode hidden (different internal layout).
- **codec.dat**: unknown header `b9 2a 90 3d`, not parsed yet. Excluded from UI.

### UI — visual & functional separation between game modes
- Switching to **Substance** now recolours the tab bar to amber (Master Collection stays green), so the active release is always obvious.
- Changing mode resets the sample/cue/BGM selection and stops playback, so the previous release's file doesn't linger in the new mode.

### UI — game-version modes and clearer step numbers
- Added a **game-version selector** (Master Collection / Substance) that rebuilds
  all tabs per mode via `MODE_REGISTRY` in `app.py`, so the raven cue sequencer
  and the bgm.dat music tab no longer sit side by side.
- Step numbers are now plain digits (`1 ·`, `2 ·` …) instead of thin circled glyphs, and the step-title font is larger (17px).

### Added — BGM (bgm.dat) music extraction, merged in
- Merged the `bgm.dat` support (MS-ADPCM streamed music) into the optimized raven build: new `formats/bgm.py`, `formats/container.py`, `formats/detect.py` (structural format auto-detection SDT/SDX/SEQUENCE/BGM), `codec/msadpcm.py`, and a **MUSIQUE · BGM** tab. The PC music (BGM) is pre-rendered MS-ADPCM in bgm.dat, not real-time orchestration — so it extracts directly.
- Four clear tabs now: SDT · DIALOGUES, SDX · banques son, SÉQUENCEUR · CUES SDX (raven synth), MUSIQUE · BGM (streamed). The two are independent — the BGM tab does not touch the SDX sequencer.
- Note: Substance (2003) `.sdx` have a different internal layout (voice_tbl not at 0x800); they don't parse in the sequencer yet (separate RE task). Their music is covered by the BGM tab.

### Performance — ~3.5–5× faster rendering (output unchanged)
- `_play`: fast path for unmodulated notes (constant rate — no per-sample branch checks or `2**` calls) and clamp-free sample fetch in the bulk of the loop. ~2× on note synthesis.
- SPU reverb `process`: inlined the buffer taps, precomputed word offsets, bound registers to locals, replaced `max/min` clamps with branches. ~3×, and the millions of `_buf`/`_set` method calls are gone. Bit-exact output.

### Changed — faithful vibrato
- Vibrato (`0xE1 vib_set`) rebuilt to match raven: real `VIBX_TBL` LFO waveform (was a plain sine), correct byte roles (b0 = depth, b1 = cadence with raven's range-scaling + `vib_tc_ofst`, b2 = hold — previously b2 was misused as speed), and the depth applied via `vib_compute` in the 1/256-semitone domain. `vib_change` (depth fade-in) is unused by these banks and left as a no-op.

### Changed — faithful pan curve and exponential portamento
- **Pan** now uses raven's `pant[41]` table (`vol_r = vol·pant[pan]`, `vol_l = vol·pant[40−pan]`) instead of a sqrt law. The centre sits at 80/127 ≈ 0.63 and the taper matches the driver, affecting every panned note.
- **Portamento** (`0xE6`) now approaches the target **geometrically** (offset decays by b2/256 per tick, raven `por_compute`), replacing the linear glide.

### Changed — robust cross-stage parsing (tested on `us/stage/tales/`)
- Cue table located by a **structural scan** when it isn't at the fixed
  `fsize−0x6800` (offset varies between stages); MGS2 banks unchanged.
- Parsing now **degrades to zero cues** instead of raising when no cue table can
  be found (SE-only banks), so sample-level features keep working.
- Audit note: some tales SE banks address samples in **SPU space** (not file
  offsets); their samples don't yet resolve. See docs/AUDIT_SDX.md §5.
- Removed a dead `vol_move_target` assignment left over from the glissando refactor.

### Added — glissandi, real portamento, and envelope curves
- **Tempo / volume / pan glissandi** (`0xD1` / `0xD6` / `0xDE`) now ramp raven-style:
  a shared `_Move` steps the value linearly toward the target over `count` ticks
  (b1 = target, b2 = ticks) and snaps at the end, advancing over both notes and
  rests. Replaces the old rest-only approximation.
- **Portamento** is now on the right opcode. raven's `por_set` (`0xE6`) makes each
  following note glide from the *previous* note's pitch to its own, at speed b2;
  `0xE4` (`swp_set`) is correctly a no-op. The old glide keyed on `0xE4` is gone.
- **Envelope curves.** The instrument's `a_mode` / `s_mode` / `r_mode` (`WAVE_W`
  bytes 6/9/12) now select linear vs exponential attack/sustain/release, mapped as
  raven's `tone_set` does. Not cosmetic: some instruments carry `a_mode` 8/9, i.e.
  an exponential attack.

### Added — per-instrument default envelope (completes the voice table)
On a program change, the instrument's default ADSR (`WAVE_W` bytes 7/8/10/11/13:
ar, dr, sr, sl, rr) is now loaded with raven's `tone_set` inversions, then any
`ads_set`/`srs_set`/`rrs_set` opcodes override it. Notes without an explicit
envelope now use the real instrument defaults instead of hardcoded ones — most
audibly a gradual release (rel ≈ 6) instead of a hard cut. Every `voice_tbl` /
`WAVE_W` field (offset, sample_note, sample_tune, envelope, pan) is now wired.

### Changed — pitch now follows raven's `freq_tbl` exactly
Replaced the ear-tuned global `MIDDLE_NOTE = 44` with raven's actual semitone→rate
table (`sd_ioset.c` `freq_tbl` + `freq_set`). The native-rate reference (0x1000)
sits at index ~47.27, so playback is a uniform ~3.2 semitones lower than before —
this is the correct absolute tuning per the driver. `MIDDLE_NOTE` is retired from
the ratio; per-instrument `sample_note`/`sample_tune` still apply on top.

### Added — default pan and `panmod` (0xDD b2)
The directory's default pan (`WAVE_W.pan`, byte 14) is now read and wired to raven's
`tone_set`/`panmod` behaviour: on a program change, if `panmod == 0` the voice takes
the instrument's default pan; a `pan_set` (0xDD) with `panmod != 0` makes the manual
pan persist across program changes. Stereo doublings like cue 58 (pan_set after the
program change) are preserved.

### Fixed — per-instrument tuning (the directory is raven's `WAVE_W`)
The 16-byte directory entry is exactly raven's `WAVE_W` voice-table record:

    +0  u32  addr          sample offset
    +4  s8   sample_note   per-instrument pitch correction (whole semitones)
    +5  s8   sample_tune   fine tune (1/256 semitone)
    +6..13   a_mode,ar,dr,s_mode,sr,sl,r_mode,rr   default ADSR envelope
    +14 u8   pan           default pan (pan*2 on the 0..40 scale; 10 → centre)
    +15 u8   decl_vol      declared volume

- **Byte 5 (`sample_tune`) is signed.** It was read unsigned, so ~30% of
  instruments (byte 5 ≥ 128) were a full semitone sharp — the "some notes sound
  a bit off, others perfect" symptom. Now read as a signed char, matching raven.
- Noted for later: raven's `freq_tbl` puts the native-rate reference at index
  ~47.2; our ear-tuned global `MIDDLE_NOTE = 44` is ~3 semitones under. Left as-is
  pending an A/B by ear (changing it shifts every instrument uniformly).
- The default pan (byte 14 = centre here) and default ADSR (bytes 6–13) are now
  understood; wiring them in (and `panmod`) is the next step.

### Fixed — sequencer opcodes re-verified against the raven source
Read directly from `KieronJ/raven` (`sd_sub1.c` control table + `sd_sub2.c`),
several opcodes were mis-identified or mis-scaled:

- **`0xD0` is tempo, not a master volume.** `tempo_set` sets the tick rate:
  `ticks/s = (44100/448) * b2/256`. Real banks run at ~24–49 ticks/s, not the
  hardcoded 30 — this is why the music played back slowed down. The renderer now
  reads the tempo from `0xD0` per track.
- **`0xD5` is per-voice volume, not pan.** `vol_chg` sets volume from `b2`; it was
  being applied to pan, so pan and volume were effectively swapped.
- **`0xDD` is the pan (confirmed).** `pan_set`: `panf = signed(b1) + 20` on a 0–40
  scale (20 = centre); `b2` is the modulation mode, `b0` is unused. The earlier
  detune/volume hypothesis is dropped. Mirror-track pairs (cue 58, 247) render as
  L/R doubling.
- **Note bytes:** length is `b2` (ticks), volume is `b0`, gate% is `b1`. The
  renderer had used `b0` as the length and never applied the note volume.
- **`0xDF` transpose reads `b2`** (was `b0`).
- **`0xE0` detune is fine:** `signed(b2)/64` semitones (±2 max), not whole
  semitones — a factor-of-64 correction.
- **`0xE5` is a pitch sweep, not a static transpose.** Now implemented as a scoop
  into each following note: the note starts `-signed(b0)` semitones off its true
  pitch, holds for `b2` ticks, then slides to pitch over `b1` ticks (raven
  `sws_set` + `note_compute`/`keych`). It was previously mis-applied as a transpose,
  then neutralised; ~31% of cues use it.
- ADSR opcodes (`0xD7/D8/D9`) verified correct, unchanged.

### Removed
- **The cue-sequence tab** (and `sequencer.py`, `sdx sequence`): a stop-gap for
  arranging cues by hand. The Music tab and `sdx render` cover reading/exporting.

### Added
- **The music sequencer.** MGS2 ships no music files: the in-game music is a
  program inside the `.sdx` banks that plays their samples as notes. That region
  is now parsed (`formats/sequence.py`) and playable (`render.py`), with eleven
  opcodes understood and confirmed by ear.
- **A Music tab** in the interface: browse a bank's pieces, listen to them,
  export one or all of them. Synthesis is cached, so a piece is only rendered
  once per set of options.
- `sdx cues` lists a bank's cues; `sdx render` writes them to WAV, one at a time
  or all at once.
- `docs/FORMATS.md` §4 documents the sequencer, and §5 what is still unknown.

### Notes
- Rendered music sounds thinner than the game's: the PlayStation's SPU applied
  reverb in hardware, and it was never stored in the files.
- Reading the music works. Replacing it does not, yet.

## 2.0.0 — MGS2 Audio Tool

The project outgrew its old name. It now handles two formats and ships as a
package, with tests and a written record of the file formats.

### Added
- **`.sdx` support** — the stage sound-effect banks. Browse a bank, listen to
  its samples, replace one, or scan the whole game and rewrite a sound in every
  bank that shares it (with `.bak` backups).
- **Voice library** for `.sdt`: point at a folder, tag files manually (done,
  tag, speaker, notes), filter and search. Tags are ordered by how often you
  use them.
- **Music and sound effects** in `.sdt`: the "PACB" header variant no longer
  plays back at half speed.
- **Unsupported files are reported**, not mangled: files using another codec,
  and files with no audio at all.
- **`docs/FORMATS.md`** — the reverse-engineering notes, independent of the code.
- **A test suite** (`pytest`) that needs no game files.
- **A unified command line**: `python -m mgs2_audio.cli sdt|sdx …`

### Changed
- Renamed from *MGS2 SDT Tool*. Restructured into layers: `codec/`, `formats/`,
  `library/`, `ui/`.
- Licensed under MIT.
- Bigger, more readable interface; the codebase is in English.
- Settings move to `~/.mgs2_audio_tool.json` (the old file is read once, so
  your folders and language carry over).

## 1.5.0

### Fixed
- **Stereo `.sdt` files no longer echo.** Their two channels are interleaved in
  0x800-byte chunks; decoding the raw stream as mono glued channel R about 81 ms
  behind channel L. The channel count is now read from the header, the channels
  are separated, and each is decoded on its own.

### Added
- Clear mono/stereo feedback when picking a replacement.
- A command line for the engine.

## 1.0.0

First release: open, listen to, export and replace `.sdt` dialogue.
