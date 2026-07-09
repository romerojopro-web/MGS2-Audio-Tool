# MGS2 Audio Tool

An audio-modding tool for **Metal Gear Solid 2: Sons of Liberty** (Master
Collection, PC). Open the game's audio files, listen to them, export them to
WAV, and replace them with your own — for custom dubs, parody voiceovers, or
reworked sound effects.

Two formats, two tabs:

- **`.sdt`** — dialogue, and some music and effects.
- **`.sdx`** — the stage sound-effect banks (footsteps, doors, weapons, ambience).

> **The game's music has not been found yet.** The music this tool can reach is
> incidental: a track playing under a cutscene, a VR mission's end jingle. Where
> the actual soundtrack lives is still an open question — see
> [`docs/FORMATS.md`](docs/FORMATS.md) §4.

> **The `.sdt` files come from the Better Audio Mod.** That mod restores the PS3
> HD Collection audio in PS-ADPCM, which is what this tool decodes. Many stock
> Steam `.sdt` files use a different codec; the tool detects them and says so
> rather than playing noise.

---

## Requirements

- **Python 3.10+**
- **PyQt6** — `pip install PyQt6` (only needed for the graphical interface)
- **[MGS2MC Better Audio Mod](https://www.nexusmods.com/metalgearsolid2mc)** for
  the `.sdt` dialogue files
- A legal copy of the game. Use only files from your own installation.

The engine underneath (`mgs2_audio.codec`, `mgs2_audio.formats`) is pure Python
with **no dependencies at all** — the command line works without PyQt6.

## Install and run

Download the project, then:

```bash
pip install PyQt6
python run.py
```

---

## What it does

### The SDT tab — dialogue

1. **Voice folder** — point it at a folder of `.sdt` files. The list appears
   instantly, even for a thousand of them.
2. **Database folder** — where your tags and notes are stored, kept separate
   from the game files.
3. Single-click a file to tag it, double-click to load and hear it.
4. Mark it **done**, give it a free-text **tag**, a **speaker**, and **notes**.
5. Pick your recording, generate the modified `.sdt`, and drop it back in the game.

Search by name, tag, speaker or notes; filter by *done / to do* or by tag.
Tagging is entirely manual — the tool never guesses whether a line is finished.

### The SDX tab — sound effects

Open a single bank, or **scan the whole game**: point it at your MGS2 folder and
it finds `us/stage` on its own, indexes every bank, and groups identical sounds.

This matters. The same footstep lives in dozens of stage banks, so editing one
of them often changes nothing you can hear — the game plays the copy from
another stage. The list shows how many banks share each sound (`×47`), and one
edit can rewrite all of them at once. Originals are kept as `.bak`.

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
- **Back up before your first `replace-all`.** `.bak` files are written
  automatically, but a copy of `stage/` costs nothing.

---

## How it's put together

```
run.py                 launch the GUI
mgs2_audio/
    codec/             PS-ADPCM and WAV. Knows nothing about MGS2.
    formats/           sdt.py, sdx.py — the game's file formats.
    library/           the tagging databases.
    ui/                PyQt6 interface.
    cli.py             the command line.
docs/FORMATS.md        the reverse-engineering notes.
tests/                 pytest suite, no game files needed.
```

Each layer only knows about the ones below it. Adapting this to another game
means rewriting `formats/` and keeping the rest.

**Read [`docs/FORMATS.md`](docs/FORMATS.md) first** if you want to understand the
files, contribute, or build something else on this. The code can be rewritten;
that knowledge took much longer to find.

Run the tests with:

```bash
pip install pytest
python -m pytest
```

They build synthetic `.sdt` and `.sdx` files from scratch — no game data needed.

---

## Known limitations

- **Encoding is slow.** The PS-ADPCM encoder is pure Python and brute-forces the
  best filter and shift for every 28 samples. Generating a long dub can take a
  while and may look frozen. Decoding is fast.
- **Scanning the whole game** reads ~200 banks of about 1 MB each. Give it a
  minute; the progress bar is honest, and you can cancel.
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

## License

[MIT](LICENSE) — do what you like with it, keep the notice.
