![GitHub release](https://img.shields.io/github/v/release/romerojopro-web/SDT-Tool-for-MGS2MCBetterAudioMod) ![Python](https://img.shields.io/badge/Python-3.10+-3776AB?logo=python&logoColor=white) ![Platform](https://img.shields.io/badge/Platform-Windows-0078D6) ![Codec](https://img.shields.io/badge/Codec-PS--ADPCM-success) ![License](https://img.shields.io/github/license/romerojopro-web/SDT-Tool-for-MGS2MCBetterAudioMod)

# MGS2 Audio Tool

> An audio-modding tool for **Metal Gear Solid 2: Sons of Liberty (Master Collection, PC)**.

Open the game's audio files, listen to them, export them to WAV, and replace them with your own — for custom dubs, parody voiceovers, restored voices, or reworked sound effects.

<img width="1904" height="1005" alt="image" src="https://github.com/user-attachments/assets/05ca1156-9f98-4709-96d4-3bf09d9682e1" />
<img width="1913" height="1000" alt="image" src="https://github.com/user-attachments/assets/56b7d44d-54ce-4932-9cc4-d63b550d3166" />

---

## Features

- Decode and play `.sdt` dialogue files
- Replace voices with automatic PS-ADPCM encoding
- Export every clip to WAV
- Browse thousands of dialogue files instantly
- Tag, search and organize dubbing progress
- Decode `.sdx` stage sound banks
- Detect duplicate sound effects across the entire game
- Replace every occurrence of a sound with a single operation
- Pure Python library with a graphical interface and command-line tools

---

# Supported formats

Two formats, two tabs:

- **`.sdt`** — dialogue, plus some music and sound effects.
- **`.sdx`** — stage sound-effect banks (footsteps, doors, weapons, ambience, etc.).

The game's main soundtrack has **not been found yet**.

The music accessible through this tool is only incidental audio, such as a cutscene background track or the VR Mission completion jingle.

Where the actual soundtrack is stored remains an open reverse-engineering question.

See **docs/FORMATS.md**, section 4.

The `.sdt` files supported by this project come from the **MGS2MC Better Audio Mod**, which restores the PS3 HD Collection audio in **PS-ADPCM**.

Many stock Steam `.sdt` files use a different codec. Those files are detected automatically and reported as unsupported rather than producing corrupted playback.

---

# Requirements

- Python 3.10+
- PyQt6 (`pip install PyQt6`) *(GUI only)*
- MGS2MC Better Audio Mod (for `.sdt` dialogue)
- A legal copy of the game

Use only files from your own installation.

---

# Install

```bash
pip install PyQt6
python run.py
```

The core engine (`mgs2_audio.codec` and `mgs2_audio.formats`) is pure Python and has **no external dependencies**.

The command-line tools work without PyQt6.

---

# What it does

## SDT — Dialogue

- Open an entire folder of `.sdt` files
- Instantly browse thousands of dialogue files
- Listen to any clip
- Export to WAV
- Replace dialogue with your own recording
- Automatically encode back to PS-ADPCM
- Organize your work with tags, speakers, notes and completion status

The tagging system is entirely manual.

The tool never tries to guess whether a line is finished.

---

## SDX — Stage sound effects

Open a single sound bank or scan the entire game.

Simply point the tool at your MGS2 installation and it automatically finds the `us/stage` folder, indexes every sound bank, detects identical sounds, and groups them into a single editable entry.

### Why this matters

Many sound effects are duplicated throughout the game.

For example, the same footstep may exist in dozens—or even hundreds—of different stage banks.

Editing only one copy often has **no audible effect**, because another stage bank supplies the version the game actually plays.

The tool solves this by:

- detecting every duplicate automatically
- displaying how many copies exist (for example **×47** or **×380**)
- replacing every occurrence in a single operation

Original files are automatically backed up as `.bak`.

---

# Command line

Everything is also available without the GUI.

```bash
python -m mgs2_audio.cli sdt info vc000101.sdt
python -m mgs2_audio.cli sdt export vc000101.sdt out.wav
python -m mgs2_audio.cli sdt replace vc000101.sdt dub.wav out.sdt

python -m mgs2_audio.cli sdx list pk000000.sdx
python -m mgs2_audio.cli sdx scan "C:/Games/.../MGS2"
python -m mgs2_audio.cli sdx export-key "C:/Games/.../MGS2" <key> sound.wav
python -m mgs2_audio.cli sdx replace-all "C:/Games/.../MGS2" <key> mine.wav
```

`scan` accepts:

- the game folder
- a language folder
- or the `stage` folder directly

---

# Tips

- Record using the original sample rate whenever possible.
  - `.sdt` → **44100 Hz**
  - `.sdx` → **22050 Hz**
- Otherwise the tool resamples automatically.
- Audio length is fixed.
    - Longer recordings are trimmed.
    - Shorter recordings are padded with silence.
- Output files always preserve the exact byte size expected by the game.
- Mono recordings replacing stereo dialogue are duplicated to both channels.
- Before using **replace-all**, keep a backup of your `stage/` folder.

---

# Project structure

```
run.py
    Launch the GUI

mgs2_audio/
    codec/
        PS-ADPCM codec and WAV support
        Independent from MGS2

    formats/
        sdt.py
        sdx.py
        MGS2 file formats

    library/
        Tagging database

    ui/
        PyQt6 interface

    cli.py
        Command-line interface

docs/
    FORMATS.md
        Reverse-engineering notes

tests/
    pytest suite
```

Each layer only depends on the layers beneath it.

Supporting another game would mainly require replacing the `formats/` package while keeping the rest of the architecture.

If you're interested in the reverse engineering behind these formats, start with **docs/FORMATS.md**.

> The code can always be rewritten. The knowledge required to understand the formats took much longer to discover.

---

# Running the tests

```bash
pip install pytest
python -m pytest
```

The tests generate synthetic `.sdt` and `.sdx` files entirely from scratch.

No game files are required.

---

# Known limitations

- Encoding is relatively slow.

  The PS-ADPCM encoder is written entirely in pure Python and brute-forces the optimal filter and shift for every 28 samples.

  Large dialogue files may therefore take some time to generate.

- Scanning the whole game reads roughly **200 sound banks** (~1 MB each).

  The progress bar reflects real progress and the scan can be cancelled.

- Stereo replacement currently duplicates mono audio to both channels.

  True stereo editing is not yet supported.

- `replace-all` modifies game files directly.

  Automatic `.bak` backups are created.

- Windows is the primary target platform.

  Other operating systems should work wherever PyQt6 runs but have not yet been tested.

---

# Disclaimer

This is an unofficial fan-made project.

It is not affiliated with, endorsed by, sponsored by, or connected to Konami Digital Entertainment.

Metal Gear Solid 2: Sons of Liberty and all related names, characters and assets remain the property of Konami.

- No game files are included.
- This repository contains only original source code.
- Use only files from your own legally obtained copy of the game.
- Intended for personal, non-commercial modding.
- Always keep backups of your files.

The software is provided **as is**, without warranty of any kind.

The author is not responsible for data loss or damage resulting from its use.

The file formats were determined through independent reverse engineering for interoperability purposes.

If you represent the rights holder and have concerns regarding this project, please open an issue.

---

# License

MIT — do what you like with it, just keep the copyright notice.



