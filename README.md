# MGS2 Audio Tool

An audio-modding tool for **Metal Gear Solid** games on PC — currently
**Metal Gear Solid 2: Master Collection** (2023) and **Substance** (2003),
with an architecture designed to support more games in the future
(MGS3, ZoE, etc.).

Open the game's audio, listen, export to WAV, and (for dialogue) replace it
with your own. A **game selector** at the top switches which tabs are shown
and recolours the whole window. Each game gets its own colour theme: green for
Master Collection, amber for Substance.

## Project status

- **MGS2 Master Collection — stable.** Every MC tab works on real game data:
  dialogue browsing/export/replacement (SDT), sound-bank scan and replacement
  (SDX), the **Global Sound Archive** (the game's iconic UI/item/alarm sounds,
  decoded from `BP_SE.DAT` — see below), the cue sequencer, and **launcher**
  music replacement (BGM · Launcher) — confirmed working (the launcher plays the
  replaced audio), including the Unity FSB5/Addressables-CRC handling that makes
  replaced bundles load.
- **In-game music replacement is under active research** — the Unity bundles
  turned out to drive only the launcher's music; the gameplay music follows
  the original PS2 engine model (`gbs_stage_*.sar` files are the prime
  suspects, see `docs/ORCHESTRATION.md`). Other MC features are also in
  development (e.g. the launcher's 13 UI sounds share one bundle and can't
  be replaced individually yet).
- **MGS2 Substance (2003) — work in progress.** Browsing and WAV export work
  (VOX, BGM, Dém, SDX open-only), but several formats are still being
  reverse-engineered: the `vox.dat` codec is unconfirmed, `demo.dat` decodes
  with artefacts, the Substance `.sdx` layout diverges from MC's, and no
  Substance replacement path exists yet. See `docs/AUDIT.md` for the open
  questions.

### Master Collection tabs

- **SDT · Dialogues** — character voice lines (replaceable, for custom dubs).
- **BGM · Launcher** — the launcher's music: the 6 scenario tracks (ARMS
  DEPOT, BATTLE, INFILTRATION…) plus the main-menu and credits themes,
  stored as Unity AssetBundles. Listen, export to WAV, and **replace a track
  with your own WAV** — the tool rebuilds a valid `.bundle` and shows each
  file's exact path inside the game folder. Note: these bundles drive the
  **launcher**, not the in-game gameplay music (that one follows the original
  PS2 engine model and is under active research — see
  `docs/ORCHESTRATION.md`). Requires the optional `UnityPy` dependency.
- **SDX · Sound banks** — the stage sample banks (footsteps, doors, weapons…).
  Full scan mode: index every bank in the game, group identical sounds, edit
  one and rewrite all copies at once.
- **Global Sound Archive** — the game's **iconic global sounds**: item selection
  and pickup, using an item, interface blips, the alert-phase alarm. They live
  in `Misc/<lang>/BP_SE.DAT`, which the game loads **once at startup** and keeps
  resident — so they appear in **no `.sdx`**, and nothing could reach them until
  now. Point the tab at your game folder and it lists all **106** sounds to
  listen to, export (one or all), or **replace with your own WAV**. Replacements
  keep each sound's exact size, and the archive is backed up to `.bak` before
  the first write.
- **Séquenceur · Cues SDX** — the raven-accurate synth that renders the SE cue
  sequences hidden in the `.sdx` banks. **These are raw sound effects, not the
  game's full orchestrated music** — real orchestration needs a separate `mdx`
  file (see below) that has never been found; if one turns up, it would likely
  get its own dedicated tab rather than folding into this one.

### Substance (2003) tabs

- **VOX · Voices** — `vox.dat`, the game's full voice archive (53 K PS-ADPCM
  blocks at 44 100 Hz). Listen, export, or dub individual blocks.
- **SDX · Sound effects** — `pk000000`–`pk000005.sdx`, six banks of stage
  samples (22 050 Hz). Open one at a time.
- **Musique · BGM** — `bgm.dat`, `movie.dat`: pre-rendered MS-ADPCM music
  streams (98 + 90 entries), decoded straight to WAV.
- **Dém Cutscenes** — `demo.dat`: the cutscene and demo audio (135 MS-ADPCM
  entries), same decode-and-export workflow.

> **How the music works.** The `.sdx` cue sequences are driven like a MIDI file
> by the PS2 sound driver — faithfully reproduced here from the **`KieronJ/raven`**
> reference (tempo, pitch via `freq_tbl`, per-instrument tuning/pan/ADSR, sweep,
> glissandi, portamento, vibrato, reverb). Those cues are mostly **sound effects**;
> the actual orchestrated **BGM** is streamed as MS-ADPCM in `bgm.dat` on PC and
> extracted directly. See `docs/AUDIT_SDX.md`, `docs/ORCHESTRATION.md`, `docs/AUDIT.md`.
>
> Reading works everywhere. **Replacing** works for Master Collection music
> (the BGM · Launcher tab, via Unity bundles) and for dialogue — not yet for
> Substance's streamed `bgm.dat` music.

> **Two `.sdt` audio formats are supported.** The Better Audio Mod ships
> PS-ADPCM (PS3 HD Collection audio) — decoded in pure Python. The **stock**
> Steam `.sdt` files use **Konami XWMA** (a multiplexed container with an
> `AMWX`/WMA v2 stream) — the SDT tab de-interleaves and decodes those too,
> via **ffmpeg**. So the tool works whether or not you have the Better Audio
> Mod installed. **Replacing** stock XWMA audio is supported via
> **xWMAEncode** (your WAV is re-encoded, rebuilt into the Konami container,
> and re-muxed at the original size). PS-ADPCM replacement stays pure-Python.
> See Requirements for ffmpeg / xWMAEncode.

---

## Requirements

- **Python 3.10+**
- **PyQt6** — `pip install PyQt6` (only needed for the graphical interface)
- **UnityPy** — `pip install UnityPy` (optional; only needed by the Master
  Collection **BGM · Launcher** tab, which reads/rebuilds Unity AssetBundles)
- **ffmpeg** — optional; only needed to **decode** stock (un-modded) `.sdt`
  audio, which is Konami XWMA/WMA. Install it (e.g. `winget install ffmpeg`)
  and put it on your PATH, or point the SDT tab at your `ffmpeg.exe`. Not
  needed for Better Audio Mod (PS-ADPCM) files.
- **xWMAEncode.exe** — optional; only needed to **replace** stock XWMA audio.
  ffmpeg can't be used for this: its WMA needs codec-private data the Konami
  container can't store, so the game rejects it. Point the SDT tab at your
  `xWMAEncode.exe` (the path is remembered). It is a small Microsoft tool that
  **cannot be redistributed** with this project (it is not on the DirectX SDK's
  redistributable list), so you supply your own — see *Getting xWMAEncode.exe*
  below.
- **[MGS2MC Better Audio Mod](https://www.nexusmods.com/metalgearsolid2mc)** for
  the `.sdt` dialogue files
- A legal copy of the game. Use only files from your own installation.

The engine underneath (`mgs2_audio.codec`, `mgs2_audio.formats`) is pure Python
with **no third-party Python packages** — the command line works without PyQt6.
Two features reach outside that core when you use them: the BGM tab needs the
`UnityPy` package, and decoding stock XWMA audio shells out to the `ffmpeg`
binary. Both are optional; everything else is stdlib-only.

### Getting xWMAEncode.exe

Only needed if you want to **replace** stock (Konami XWMA) dialogue. It ships in
Microsoft's **DirectX SDK (June 2010)** but is not redistributable, so grab it
yourself — you do **not** need to install the whole SDK:

1. Download `DXSDK_Jun10.exe` from Microsoft's download center.
2. **If the installer fails with error `S1023`** (common on modern Windows,
   because a newer *Visual C++ 2010 Redistributable* is already installed),
   don't fight it — just **open `DXSDK_Jun10.exe` with [7-Zip]** (right-click →
   *7-Zip → Open archive*) and extract the single file
   `DXSDK\Utilities\bin\x86\xWMAEncode.exe`. No installation required.
3. Put `xWMAEncode.exe` anywhere you like and point the SDT tab at it the first
   time you replace an XWMA file; the tool remembers the path afterwards.

[7-Zip]: https://www.7-zip.org/

## Install and run

Download the project, then:

```bash
pip install PyQt6
python run.py
```

---

## What it does

### The SDT tab — dialogue (Master Collection)

1. **Voice folder** — point it at a folder of `.sdt` files. The list appears
   instantly, even for a thousand of them.
2. **Database folder** — where your tags and notes are stored, kept separate
   from the game files.
3. Single-click a file to tag it, double-click to load and hear it.
4. Mark it **done**, give it a free-text **tag**, a **speaker**, and **notes**.
5. Pick your recording, generate the modified `.sdt`, and drop it back in the game.

Search by name, tag, speaker or notes; filter by *done / to do* or by tag.
Tagging is entirely manual — the tool never guesses whether a line is finished.

> **Every tab can be tagged**, not just SDT — SDX, VOX, BGM, Dém and Séquenceur
> each keep a done/tag/notes panel and their own database file. The **database
> folder is picked once per game** (a control in the app header, next to the
> mode selector) — Master Collection and Substance never share tags.

### The VOX tab — voice archive (Substance)

Open `vox.dat` (the Substance voice archive). Its 53 K PS-ADPCM blocks are
listed; pick one to listen and export, or pick a WAV to dub it. The file
dialogue opens on `.dat` by default.

### The SDX tab — sound effects

**Master Collection** — open a single bank, or **scan the whole game**: point
it at your MGS2 folder and it finds `us/stage` on its own, indexes every bank,
and groups identical sounds.

**Substance** — open one of the six `pk*.sdx` banks (scan mode is not available:
Substance banks use a different internal layout). The open dialog filters on
`.sdx` by default.

### The BGM / Dém tabs — streamed music

**Master Collection** — open a `.sdx` bank and its musical pieces appear in a
list. Click one and it is synthesised and played, right there. Export a piece,
or every piece at once. Two options change the synthesis: **stereo** (uses each
track's pan) and **tune** (uses each instrument's base rate, 44 100 Hz).

**Substance** — the **BGM** tab opens `bgm.dat` or `movie.dat` (pre-rendered
MS-ADPCM streams). The **Dém** tab opens `demo.dat` (cutscene audio). Both
list entries with sample rate, channel count and duration; select one to listen
and export, or export all at once.

### The music sequencer, from the command line

The `.sdx` banks carry more than samples: they carry the score. List a bank's
cues and render them to WAV:

```bash
python -m mgs2_audio.cli seq cues   pk000002.sdx --min-notes 20
python -m mgs2_audio.cli seq render pk000002.sdx melody.wav
python -m mgs2_audio.cli seq render pk000002.sdx out/ --all --min-notes 8
```

Without `--cue`, the busiest cue is rendered — usually the music. Rendering is a
small software SPU: one voice per track, samples that loop while a note holds,
volume, pan, pitch bend, portamento and transpose.

It will sound thinner than the game. The PlayStation applied reverb in hardware,
and that was never stored in any file.

### The command line

No Qt, no GUI, scriptable:

```bash
python -m mgs2_audio.cli sdt info    vc000101.sdt
python -m mgs2_audio.cli sdt export  vc000101.sdt out.wav
python -m mgs2_audio.cli sdt replace vc000101.sdt dub.wav out.sdt

python -m mgs2_audio.cli sdx list        pk000000.sdx
python -m mgs2_audio.cli sdx scan        "C:/Games/.../MGS2"
python -m mgs2_audio.cli sdx export-key  "C:/Games/.../MGS2" <key> sound.wav
python -m mgs2_audio.cli sdx replace-all "C:/Games/.../MGS2" <key> mine.wav
```

`scan` accepts the game folder, a language folder, or the stage folder itself.

---

## Tips

- Record at the file's own rate if you can — **44100 Hz** for `.sdt`,
  **22050 Hz** for `.sdx`. Otherwise the tool resamples.
- **Length is fixed.** Longer audio is trimmed, shorter is padded with silence.
  The output keeps the original's exact byte size, which the game requires.
- On a stereo `.sdt`, your mono recording is placed on both channels.
- **Replacing stock XWMA dialogue:** your WAV is automatically conformed to the
  original clip's channel count and sample rate before encoding — a stereo WAV
  put where the game expects mono is rejected in-game (even though a lenient
  player would preview it fine), so the tool matches the original for you. If
  the re-encoded audio can't fit the original's byte capacity the replacement is
  refused with a clear message; shorten the recording or it drops to a lower
  bitrate automatically.
- **Back up before your first `replace-all`.** `.bak` files are written
  automatically, but a copy of `stage/` costs nothing.

---

## Architecture

```
run.py                 launch the GUI
mgs2_audio/
    codec/             PS-ADPCM, MS-ADPCM and WAV. Knows nothing about MGS2.
    formats/           sdt.py, sdx.py, sequence.py, bgm.py — the game's file formats.
                       detect.py does structural auto-detection.
    library/           the tagging databases.
    render.py          a small software SPU: plays a sequencer cue.
    core/              GamePlugin ABC, PageSpec, REGISTRY — the plugin interface.
        base.py        GamePlugin, PageSpec, AudioFormat, AudioContainer
        registry.py    Plugin discovery and global registry
    games/             Each game is a subpackage that registers itself.
        mgs2_mc/       MGS2 Master Collection (SDT, SDX, Sequencer)
        mgs2_substance/ MGS2 Substance 2003 (VOX, SDX, BGM, DEMOS)
    ui/                PyQt6 interface (app.py = shell, one page per tab).
    cli.py             the command line.
docs/FORMATS.md        the reverse-engineering notes.
tests/                 pytest suite, no game files needed.
```

Each layer only knows about the ones below it. Games are self-contained
plugins discovered at import time — the UI shell never imports game-specific
code directly. Adding a new game means creating a new subpackage in
`mgs2_audio/games/<id>/` with a `Plugin` class that extends `GamePlugin`.

**Read [`docs/FORMATS.md`](docs/FORMATS.md) first** if you want to understand the
files, contribute, or build something else on this. The code can be rewritten;
that knowledge took much longer to find.

Run the tests with:

```bash
pip install pytest
python -m pytest
```

They build synthetic `.sdt` and `.sdx` files from scratch — no game data needed,
and this default run stays deliberately light (a few seconds, no brute-force
PS-ADPCM encoding of anything but real test content). A handful of tests
additionally validate against real game files if you have them under
`tests/mgs2_substance_2003/` — those are opt-in (`python -m pytest --realdata`)
since parsing a 1+ GB file is slow and genuinely CPU-heavy; they're skipped by
default so a plain test run never pins a core for that long.

### Running just what you're touching

The suite is split one file per subsystem, so `pytest tests/test_X.py` runs
only what's relevant to `X` — no need for the full suite (or `--realdata`)
while iterating on one area. Cheaper on the CPU, and faster to read.

| Working on…                              | Run                          |
|-------------------------------------------|-------------------------------|
| PS-ADPCM / MS-ADPCM codecs                 | `pytest tests/test_codec.py` |
| `.sdt` format (dialogue) / `vox.dat`       | `pytest tests/test_sdt.py`   |
| `.sdx` format (sound banks)                | `pytest tests/test_sdx.py`   |
| `bgm.dat` / `movie.dat` / `demo.dat`       | `pytest tests/test_bgm.py`   |
| MC music bundles (`formats/mcbgm.py`)      | `pytest tests/test_mcbgm.py` |
| Stock XWMA `.sdt` (`formats/xwma.py`)       | `pytest tests/test_xwma.py`  |
| `BP_SE.DAT` global sounds (`formats/seo2.py`) | `pytest tests/test_seo2.py` |
| The sequencer / `render.py` (SPU, reverb)  | `pytest tests/test_sequence.py` |
| Tagging databases (`library/db.py`)        | `pytest tests/test_library.py` |
| The app shell (`ui/app.py`, `db_folder`)   | `pytest tests/test_app.py`   |

A single test also works (handy while chasing one failure):
`pytest tests/test_bgm.py::test_quad_matches_separate_stereo_decode`.

Reach for the full `pytest` (or `--realdata`) run before a release, or
whenever a change might have touched more than one subsystem — not as the
default while developing.

---

## Known limitations

- **Encoding is slow.** The PS-ADPCM encoder is pure Python and brute-forces the
  best filter and shift for every 28 samples of real audio. Generating a long
  dub can take a while and may look frozen. Silence is fast-pathed (a `.sdt`
  replacement always pads or trims to the target's exact byte size, and the
  padding/trimmed-away portion is often mostly silence), but the real recorded
  audio itself still goes through the full search. Decoding is fast.
- **Scanning the whole game** (Master Collection only) reads ~200 banks of about
  1 MB each. Give it a minute; the progress bar is honest, and you can cancel.
- **Substance `.sdx` banks** use a different internal layout (`voice_tbl` not at
  `0x800`); they don't parse in the raven sequencer yet. Open-only mode.
- **Substance `vox.dat` playback is suspect.** It's currently decoded as PS-ADPCM,
  but the container structure suggests the actual codec may be Konami's
  DPCM_KCEJ instead — unconfirmed by ear. See `docs/AUDIT.md` before relying on it.
- **Substance `codec.dat`** (`b9 2a 90 3d` header) is an unknown format; reverse
  engineering is still needed. It is excluded from the UI for now.
- **Stereo dubs are duplicated** across both channels. True left/right stereo
  replacement is not supported.
- **`replace-all` writes to your game files** in place (with `.bak` backups).
- **Windows-focused.** It should run anywhere PyQt6 does; other platforms are
  untested.

---

## Disclaimer

Unofficial, fan-made, and not affiliated with, endorsed by, or connected to
Konami Digital Entertainment. *Metal Gear Solid 2: Sons of Liberty* and all
related names, characters and assets are trademarks and copyrights of Konami.

- **No game files are included.** This project contains only original code.
- **Use your own copy.** You are responsible for how you use it.
- **For personal, non-commercial modding.**
- **Back up your files.** Provided as-is, without warranty of any kind; the
  author is not responsible for any damage or data loss arising from its use.

The file formats were determined through independent analysis for
interoperability. If you are a rights holder with a concern about this project,
please open an issue and it will be addressed.

## Acknowledgements

- **[KieronJ/raven](https://github.com/KieronJ/raven)** — the PS2 sound-driver
  reference that made the `.sdx` cue sequencer faithful (tempo, pitch tables,
  ADSR, reverb…).
- **[RockeyLol/RIFF-XWMA-Konami-XWMA-Converter](https://github.com/RockeyLol/RIFF-XWMA-Konami-XWMA-Converter)**
  — for documenting the **Konami XWMA** (`AMWX`) container format, which is what
  identified the stock MGS2 audio format and makes decoding/re-encoding it
  possible. Thank you! 🙏

## License

[MIT](LICENSE) — do what you like with it, keep the notice.
