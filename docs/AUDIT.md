# Audit — state of the codebase

Living punch-list for `mgs2_audio/`. Replaces `REPRISE.md`, `SESSION_DECOUVERTES.md`
and `AUDIT_REPRISE.md` (three overlapping, partly-contradicting session logs) with one
place to check what's fixed, what's verified-fine, and what's still open. Historical
narrative stays in `CHANGELOG.md`; format/reverse-engineering knowledge stays in
`docs/FORMATS.md`, `docs/AUDIT_SDX.md`, `docs/ORCHESTRATION.md`.

This audit was produced by reading every file in `mgs2_audio/` end to end (UI, codec,
formats, render, cli) against real game data (`scripts/sdx_mgs2_MC/`,
`tests/mgs2_substance_2003/`), not by inspection of a diff.

---

## Fixed this pass

### Interface (UI)

| Severity | File | Fix |
|---|---|---|
| Critical | `ui/widgets.py` `PlaybackMixin._release_player` | Stopped disconnecting the player's `positionChanged`/`durationChanged`/`mediaStatusChanged` signals on every file swap — it only ran once per page and then never reconnected, so the slider, time label, end-of-track detection and auto-play broke for the rest of the session after the *first* file change in any tab. Disconnection now only happens in `_destroy_playback()` (page teardown). |
| Major | `ui/widgets.py` | `player.errorOccurred` was never connected anywhere except `SDTPage` (whose own handler was itself never wired). Added a default handler in `PlaybackMixin._init_playback()` so every tab surfaces playback errors in the status bar instead of silently doing nothing. |
| Major | `ui/vox_page.py`, `ui/bgm_page.py` (+ `demos_page.py` via inheritance) | `_release_preview()` stopped the player but never deleted the outgoing temp WAV — one orphaned file per list selection. Now matches `sdx_page.py`'s existing correct pattern. |
| Major | `formats/sdx.py` `scan_banks`, `ui/sdx_page.py` | Scan "Cancel" set a flag the scan loop never checked, so it always ran to completion. `scan_banks()` now takes the progress callback's return value as a stop signal. |
| Major | `ui/sdt_page.py` | `restore_folders()` existed but was never called — on restart, the remembered voice folder showed in the label but the file list stayed empty until manually re-picked. Now called at the end of `__init__`. |
| Minor | `ui/seq_page.py` `_purge_cache` | Deleted cached render files (including the one currently loaded/playing) before releasing the player. Now releases first. |
| Minor | `ui/sdt_page.py` `_refresh_list` | Editing an entry so it no longer matches the active filter (e.g. ticking "Done" under a "Todo" filter) left the tag panel live on a now-invisible entry. Selection and panel are now cleared when this happens. |
| Minor | `ui/sdx_page.py` | The "replace everywhere" confirmation dialog showed the sound's occurrence count instead of the number of distinct bank files that would actually be rewritten. Fixed to `len(group.banks)`. |

### Logic (codec/formats/render/cli)

| Severity | File | Fix |
|---|---|---|
| Critical | `render.py` `SPU_Reverb.process` | The four SPU reverb reflection outputs (same-side L/R, cross-side L/R) were all written to the same buffer slot (`buf[cur]`), each overwriting the previous — three of four were silently discarded on every sample, for every cue rendered with a non-`off` reverb preset (default `hall`). Added the missing `_w_mLSAME`/`_w_mRSAME`/`_w_mLDIFF`/`_w_mRDIFF` write offsets and gave each reflection its own address and its own "old" history sample, per the psx-spx §7.12 formula already documented in `docs/FORMATS.md` §4.5. **Changes the audio of every reverberated render** — regression test added (`tests/test_sequence.py::test_reverb_reflections_write_to_distinct_taps`); a before/after render of a real cue was generated for a human listening check. |
| Major | `render.py` `_render_track` | Nothing cut a track's still-ringing note when a new note-on started on the same track, contradicting the documented rule ("each track owns one voice — a new note silences whatever was still playing", `docs/FORMATS.md` §4.4) — a slow release could bleed into the next note, doubling audio. Now mutes the track's dry output from the new note's start up to wherever the previous note had written; the shared reverb bus is left alone (real hardware reverb keeps ringing what was already sent to it, regardless of the source voice being cut). |
| Major | `formats/sdx.py` `replace_group`, `cli.py replace-all` | Writes went straight to `open(path, "wb")` with no temp-file safety net (a crash or full disk mid-write could corrupt a game file), and a `.bak` was only ever skipped-if-exists — if a bank had ever been touched before with `backup=False` (or its `.bak` deleted), the next `backup=True` run would silently back up the *already-modified* file as if it were pristine. Writes are now atomic (temp file + `os.replace`); failures during a multi-bank batch are collected and reported (`ReplaceGroupError`) instead of aborting mid-batch with no record of what succeeded — everything that could be written still is. |
| Minor | `formats/detect.py` `is_sequence` | Endianness bug: the docstring says the header is `11 00 00 00`, but the code recomposed the four bytes little-endian, so it only matched the reverse (`00 00 00 11`). Fixed to match the documented intent. Also added the missing `Format.SEQUENCE` case in `container.RavenContainer.from_path()` (it raised `ValueError` before; `detect.open_file()` already handled it). |
| Minor | `formats/sdt.py` (block scan) | `while pos < len(raw) - 8` skipped a legitimate final MG block sitting exactly on the file's last 8 bytes. Off-by-one fixed to `<=`. |
| Minor | `formats/sdt.py` `deinterleave_channels` | A trailing partial interleave group (stream length not a multiple of `channels`) was dropped entirely, losing up to one `0x800` chunk of real trailing audio per channel. Now keeps whatever channel(s) have a final chunk and pads the rest with one silent chunk so all channels stay equal length. |
| Minor | `codec/psadpcm.py` `decode_psadpcm` | An invalid `shift > 12` decoded to hard digital silence, masking file corruption as a clean-looking empty frame. Now clamps `shift` to 12 instead. |
| Minor | `codec/psadpcm.py` `_encode_block` | The encoder's internal filter/shift search carried forward an un-rounded float as prediction history, while the real decoder rounds to an int between samples — a small, avoidable extra quantization error on every re-encode (`replace_audio`/`replace_sample`/`replace_group`). Encoder history is now rounded the same way. |
| Minor | `codec/wav.py` `load_wav_mono` | A 32-bit IEEE float WAV (common from modern DAWs) hit the stdlib `wave` module's own refusal (`wave.Error: unknown format: 3`) with no context. Added a `fmt` chunk pre-check that raises a clear, actionable message instead. (The originally suspected "silently misread as noise" did not reproduce — `wave.open` already refuses non-PCM formats outright.) |
| Minor | `cli.py`, `formats/sdx.py` (`ReplaceGroupError`) | Non-ASCII characters (`→`, `…`, `—`) in `print()` output and one `argparse` help string crashed the CLI outright on a default Windows console (`cp1252`), including in `seq render` and `sdx scan` — reproduced live while verifying the fixes above. Replaced with ASCII equivalents (`_bgm_export` already did this; the rest now match). |

### Architecture hygiene (`AUDIT_REPRISE.md` H1–H4)

- **H1** — removed the dead `from ...core.registry import REGISTRY` import in both
  `games/mgs2_mc/__init__.py` and `games/mgs2_substance/__init__.py` (registration goes
  through `GamePlugin.register()`, which imports `REGISTRY` itself).
- **H2 (corrected)** — the original audit claimed `cli_register` was never consumed;
  it is (`cli.py` calls `plugin.cli_register(fmt)`). What actually is dead:
  `default_theme`, `themes`, `formats`, `detect` on `GamePlugin` — the shell reads
  `plugin.modes[mode]["style"]`, never `plugin.default_theme`/`themes`, and nothing
  reads `formats`/`detect`. Removed all four from the ABC and the two plugins instead
  of wiring them for a hypothetical use.
- **H3** — `library_filenames` on `GamePlugin` was *also* dead (never read anywhere;
  the real filenames were hardcoded constants in `library/db.py`), so namespacing it
  wouldn't have fixed anything. Instead: Substance now has its own SDX tag database
  (`mgs2_substance_sdx_library.json`, via `SDXPage._sdx_library_filename()`) so a
  shared `db_folder` no longer co-mingles Master Collection and Substance sound tags.
  Master Collection keeps its original filename unchanged. The dead
  `library_filenames` attribute was removed from the ABC and both plugins.
- **H4** — `last_tab_key` is shared across modes by design-accident, not a bug: both
  modes happen to have a `"sdx"` tab key, so switching modes lands back on SDX. Left
  as-is; noted here rather than "fixed" because the behavior is harmless and arguably
  reasonable (both games' SDX tabs are the analogous view).

---

## Verified during this pass, not a bug

- **`sequence.py` `_walk_sample` skipping frame 0** — `AUDIT_REPRISE.md` flagged this
  as a possible bug (an instrument whose real end-of-sample flag lands on frame 0,
  the VAG silent lead-in, would never be detected). Checked against all 786
  instruments across the 6 real MC banks and 6 real Substance banks now available:
  **512 of 786 (65%)** carry the end-of-sample flag on frame 0 as a boilerplate
  convention on the lead-in frame, unrelated to the sample's real length (e.g. a
  9,968-byte / 623-frame instrument still has `flag0 = 0x07`). If the walker checked
  frame 0, the majority of real instruments would truncate to one silent frame. The
  code's choice to start at frame 1 is correct and load-bearing — not changed.

---

## Open — carried over from `AUDIT_REPRISE.md`

These are real, code-grounded findings but are **reverse-engineering work, not bug
fixes** — left for the next phase (the "évolution / recherche" the cleanup was meant
to precede). `AUDIT_REPRISE.md`'s citations to "REPRISE §6/§7" were wrong (those
sections don't say what was attributed to them, and REPRISE.md is now deleted anyway);
citations below point at code instead.

- **C1 — `vox.dat` uses the wrong codec (codec confirmed, container still open).**
  `ui/vox_page.py` calls `sdt_fmt.parse_sdt()` + `decode_psadpcm()` on Substance's
  `vox.dat`. **2026-07-13 update:** pulled the real `DPCM_KCEJ` decode algorithm
  straight from vgmstream's source (`src/coding/dpcm_kcej_decoder.c`) — confirms the
  original hypothesis almost byte-for-byte:
  ```python
  def expand_code(code):
      neg, cmd = code & 0x80, code & 0x07
      v = (code & 0x78) << 8 if cmd == 7 else ((code & 0x78) | 0x80) << 7
      v >>= cmd
      return -v if neg else v
  # hist += expand_code(byte); sample = int16(hist)  — 1 byte in, 1 sample out, mono
  ```
  What's still open: the real `vox.dat` (not the old `vox_slice.dat`, which starts
  mid-silence and isn't representative) has its true file header at `0x20`–`0x30`,
  using the *same* `00 7F` + big-endian-rate mini-header convention as `bgm.dat`
  (see the new bgm.dat finding below) — but a much larger zero-padded region than a
  simple "silent lead-in" would explain follows before real per-clip audio data
  starts. Needs the real clip/entry boundaries mapped out before the KCEJ decoder can
  be wired in and validated by ear.
- **`bgm.dat` "4-channel" entries — FIXED (2026-07-13).** 14 of 98 real `bgm.dat`
  entries declare `channels=4`. The old `codec/msadpcm.py` `_decode_quad_block`
  guessed a single stream with 4 interleaved-nibble channels sharing one block
  header — confirmed wrong: decoding a real entry that way clipped ~15% of samples
  at full scale (vs 0% for known-good stereo entries). Cross-checked against
  vgmstream's actual `msadpcm_decoder.c`: **standard MS-ADPCM has no native
  >2-channel mode at all** — Microsoft's own spec tops out at stereo. Replaced with
  the correct model — **two independent stereo MS-ADPCM streams, block-interleaved
  every `0x800` bytes** (even blocks = front L/R, odd blocks = rear L/R), decoded
  with the existing, already-correct `_decode_stereo_block`. `_decode_quad_block`
  deleted; `decode_msadpcm`/`bytes_to_samples`/`samples_per_block` updated for
  `channels=4`. Verified on real data: 0% clipping on all 4 channels of every
  entry checked, decoded duration now matches the declared duration exactly.
  Regression tests added (`tests/test_bgm.py`): the block-alternated decode is
  checked byte-for-byte against decoding front/rear as separate stereo streams.
  **Listening test (user, 2026-07-13):** clean, no artifacts. A fast (~4/s) L/R
  "bounce" is present in the exported front-channel audio, but a control file
  (entry 0, plain stereo, never touched by this fix) doesn't show it in the same
  way — narrowed to being a property of the quad/surround content itself (this
  game's real-time sequencer is independently documented to use an actual
  auto-pan ping-pong effect elsewhere, `docs/FORMATS.md` §4.4, cue 15), not a
  decode bug. Quantitative check (windowed L/R RMS + autocorrelation over the
  full track) found no digital, block-boundary-locked periodicity to contradict
  that. Accepted as correct, not investigated further.
- **`demo.dat` — confirmed broken, root cause not yet found (2026-07-13).** Every
  entry tested decodes with 26–53% of samples clipped at full scale regardless of
  which block size is tried (`0x200` through `0x2000`), ruling out a simple
  block-size mismatch. Two more anomalies: the header's own `size_field` (e.g.
  2,744,320 bytes for entry 0) diverges ~30% from the anchor-scanner's computed entry
  size (gap to the next detected header, 3,910,560 bytes) — for `bgm.dat` these two
  numbers are supposed to be close; and `loop_end` reads as the identical suspicious
  value `0x1000000` (16,777,216 — an exact power of two) on every entry checked
  regardless of the track's real length, which cannot be a real per-track loop point.
  Together this suggests `demo.dat` isn't simply "the same flat format as `bgm.dat`"
  the way the anchor-scanner currently assumes — there's likely additional internal
  structure (mixed block/sub-stream types, matching the older KCEJ-mixing hypothesis)
  that a flat MS-ADPCM decode can't account for. Needs focused follow-up before any
  fix is attempted.
- **M1 — `detect.py` doesn't recognise `vox.dat` or `demo.dat`.** `open_file()` (CLI)
  can't auto-open them; `VoxPage` bypasses detection entirely by hardcoding
  `parse_sdt`. Add `Format.VOX` once C1 is resolved.
- **M3 — Substance `.sdx` banks use a different internal layout** (`voice_tbl` not at
  `0x800`), so `SDXPage`'s scan mode (built for Master Collection) doesn't work on
  them. Open-only mode is correct for now; full support needs its own RE pass.
- **`codec.dat` — identified, not raw audio (2026-07-13).** Per the community
  [KCEJ-Wiki](https://github.com/Joy-Division/KCEJ-Wiki) (`Common/GCL/ReadMe.md`),
  Konami's in-house scripting language **GCL** ("Game Command Language") compiles to
  `.gcx` bytecode via a tool called `GCLCONV`; from MGS2 onward, `codec.dat` is "GCX
  scripts concatenated into a streaming-type DAT archive along with various other
  data, usually an additional font for Japanese characters." **Verified against our
  own files**: a compiled `.gcx` is documented to start with a 4-byte little-endian
  Unix timestamp — our own `tests/mgs2_substance_2003/scenerio.gcx` does exactly
  that, decoding to **2002-09-24**, a fully plausible compile date for a game that
  shipped in early 2003. This also explains the `b9 2a 90 3d` "magic header" noted
  in earlier docs: it isn't a fixed magic number at all, it's the (little-endian)
  timestamp of whichever GCX script happens to start there — scripts compiled within
  the same few months of development naturally share the same high-order bytes.
  So: `codec.dat` is mostly compiled script bytecode + dialogue/subtitle text +
  font glyph data, not PCM audio — matches the user's own suspicion. Full parsing
  (finding real record boundaries, decoding GCL bytecode itself) is unstarted.
  **On hold (user decision, 2026-07-13): out of scope for this project — it's text/
  script data, not audio. Revisit at the end of the project, if at all.**
- **The `mdx` orchestration file — RESOLVED for MC, still open for Substance
  (2026-07-13).** MC (2023) never ported the legacy PS2 `mdx` system at all — its
  scenario BGM is 6 standard Unity `AudioClip`s in `UnityFS` AssetBundles
  (`<install>/launcher_Data/StreamingAssets/aa/StandaloneWindows64/
  packedassetsmgs2_assets_scenarioapp/mgs2/bgm/*.wav.bundle`), extracted cleanly
  with the public `UnityPy` library — confirmed on `INFILTRATION` (clean 44.1kHz/
  16-bit/stereo PCM WAV, ~120s). A companion `MonoBehaviour` catalog
  (`sounddata_scenariobgm.asset.bundle`) lists all 6 named tracks (`ARMS DEPOT`,
  `BATTLE`, `COUNTDOWN TO DISASTER`, `INFILTRATION`, `IT'S THE HARRIER`,
  `YELL "DEAD CELL"`) by name, readable via `obj.read_typetree()`. Full details
  and the extraction recipe: `docs/ORCHESTRATION.md`'s new top section. What
  decides *when* each track plays (infiltration/alert/evasion) is still
  unconfirmed — likely a C# script (Mono runtime, not IL2CPP), not decoded yet.
  For **Substance**, the `mdx` (if it exists at all in that release) is still
  unfound; `cache.dar`/`cache.qar`/`scenerio.gcx`/`data.cnf` were all checked
  this session and ruled out (confirmed to be mission/script data via
  `idlist.txt` cross-reference and the KCEJ-Wiki, not audio-related) — no
  remaining unexplored candidate in that folder.
  Confirmed by measurement (RMS per channel across all significant cues in
  `pk000002.sdx`): the Séquenceur tab's pan handling itself is correct (matches
  the documented reference cue 58 exactly, 1:1 balance); a few cues (155, 160,
  205, 206) are just authored hard-panned in the game data, expected for SE
  rather than balanced music. The tab's in-app hint and README say explicitly
  these are raw SE cues, not full music.

---

## Noticed, not touched this pass

- `core.base.AudioFormat` / `AudioContainer` are defined as ABCs but nothing in the
  codebase subclasses either — `formats/container.py`'s `RavenContainer` is an
  independent dataclass, not a subclass. Dead abstraction; candidate for removal or
  for actually wiring the format modules through it in a future pass. Left alone here
  since deleting public ABCs is a bigger call than this pass's scope.
