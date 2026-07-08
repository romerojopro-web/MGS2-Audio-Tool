# MGS2 SDT Tool

An audio-modding tool for the `.sdt` files of **Metal Gear Solid 2: Sons of Liberty** (Master Collection, PC version).

It lets you open a game `.sdt` file — **dialogue, music or sound effects** — listen to it, export it to WAV, then **replace it with your own audio** to create home-made dubs, custom music swaps or reworked sound effects.

---

## Features

- **Open** an `.sdt` file (voice, music or SFX) and show its duration and info.
- **Listen** to the original audio directly in the app.
- **Export** the audio to `.wav` (to identify the line or edit it).
- **Replace** the audio with your own `.wav` recording.
- **Save** a modified `.sdt` that keeps exactly the same structure AND the same name as the original — ready to drop back into the game.

Format conversion (44100 Hz) and encoding are automatic. On a mono file the audio is encoded as mono; on a stereo file your recording is placed on both channels — the app tells you which, so there are no surprises.

### What's new in v3

- **Voice library panel.** Point the app at a folder of `.sdt` files (a hundred, or a thousand) and browse them in a side panel: click to select, double-click to load. Each file can be **manually tagged** — mark it as done, give it a free-text label (Soldier, Codec, Music…), note the speaker, and jot down what is said. Everything is saved to a small local database in a folder **you** choose, so your progress and notes survive across sessions. Filter by *done / to do* or search by name, tag, speaker or notes.
- **Music and sound effects supported.** Beyond dialogue, the tool now reads the game's music and SFX `.sdt` files too — including a header variant (a "PACB" sub-header) that previously made them play back slowed-down. This opens the door to custom music swaps and reworked sound effects.
- **Full stereo support.** Stereo `.sdt` files (the "dialogue bank" files and most music) are now decoded and re-encoded correctly, with **no echo** and at the right speed. See the technical notes below for what was going on.
- **Clear stereo/mono messaging.** When you pick your replacement audio, the app states whether it will be re-encoded as mono or stereo, matching the source file.
- **Richer command line.** The engine can now be driven entirely from the terminal with `info`, `export` and `replace` sub-commands (see below).
- **Bigger, more readable interface**, an English codebase (comments/docstrings), with the FR / EN / ES interface translations kept intact.

Settings are stored in `~/.mgs2_sdt_tool.json`. Your library tags/notes live in the database folder you pick (a `mgs2_sdt_library.json` file).

---

## The SDT format (technical notes)

These findings were obtained by reverse-engineering the format and validated by ear on known game audio.

- **Codec**: PlayStation 4-bit ADPCM (PS-ADPCM / VAG).
- **Sample rate**: 44100 Hz.
- **Channels**: 1 (mono) or 2 (stereo).
- **Structure**: a header (table + metadata) followed by a series of blocks ("MG blocks"). Each block = 16-byte header + up to 0x4000 bytes of audio data. The last block may be shorter. Concatenated, the blocks form the complete audio stream.
- **Stereo interleave**: on 2-channel files, the two channels are interleaved in chunks of **0x800 bytes** (`L, R, L, R…`). One 0x4000 data block therefore holds 8 chunks (`L R L R L R L R`).
- **Header variants**: dialogue files carry the sample rate and channel count at fixed offsets (`0x96` / `0x98`), but some files (music / VR "PACB" variants) insert an extra sub-header that shifts those fields. The tool detects the format robustly (anchor `0x7F <rate> <channels>`), so both layouts are read correctly.

### The bugs, and how they were fixed

Two symptoms, same family of cause — a stereo file being treated as mono:

- **Echo (dialogue).** Early versions decoded the raw stream as a single mono flow. On stereo files this glued channel R about 0x800 bytes — roughly **81 ms** — behind channel L, heard as an echo/overlap. (An earlier attempt to deinterleave at the wrong granularity, per 16-byte ADPCM unit, instead halved the duration and produced a fast, high-pitched "chipmunk" voice.)
- **Slowed-down (music / SFX).** These files use the shifted "PACB" header, so the channel count was misread as mono. A stereo file decoded as mono plays both channels end to end, doubling the length — heard as slow-motion audio.

The fix: detect the sample rate and channel count robustly regardless of header layout, deinterleave stereo files at the correct **0x800** step, decode each channel separately, and output proper stereo (`L, R, L, R…`). Echo gone, correct speed, and music/SFX now supported.

The PS-ADPCM decoder/encoder is implemented in pure Python in `sdt_core.py`, with no external dependency.

---

## Installation

Requires **Python 3.10+** and **PyQt6**.

```bash
pip install PyQt6
```

The project has four files:

- `sdt_tool.py` — the graphical interface (run this).
- `sdt_core.py` — the engine (PS-ADPCM decoding/encoding, pure Python; also a CLI).
- `library.py` — the voice-library database (tagging + metadata, pure Python).
- `translations.py` — the interface strings (FR / EN / ES).

## Usage (GUI)

```bash
python sdt_tool.py
```

Then, in the app:

1. **Open an SDT file** — pick a game `.sdt` (voice, music or SFX, e.g. `vc000101.sdt`).
2. **Listen** — play it to identify it, or export it to WAV.
3. **Choose your audio** — a `.wav` to replace it with (ideally the same length).
4. **Generate** — save the modified `.sdt`.

Then replace the game's original file with yours.
**Always back up the original file before replacing it.**

### Voice library (side panel)

For bulk work, use the library panel on the left:

1. **Voice folder** — pick the folder that contains your `.sdt` files. The list appears instantly, even for a thousand files.
2. **Database folder** — pick where to store your tags and notes (kept separate from the game files). A `mgs2_sdt_library.json` is created there.
3. **Single-click** a file to edit its tags; **double-click** to load it into the workflow and hear it.
4. For each file you can mark **Done**, add a free-text **tag**, a **speaker**, and **notes** — then Save.
5. Use the **search box** and the **All / To do / Done** filter to find your way around.
6. Mono/stereo is detected automatically; **Scan folder** (optional) pre-computes every duration in one pass. Run it to refresh a folder after updating the tool.

Tagging is fully manual — the tool never guesses whether a file is done, so you stay in control.

## Usage (command line)

The engine can be used on its own, without the GUI:

```bash
# Show metadata (size, sample rate, channels, blocks, duration)
python sdt_core.py info vc000101.sdt

# Decode an SDT to WAV
python sdt_core.py export vc000101.sdt output.wav

# Inject your dub WAV into an SDT (output keeps the exact file size)
python sdt_core.py replace vc000101.sdt my_dub.wav vc000101_new.sdt
```

A legacy positional form is still accepted for convenience:

```bash
# Show info, and export to WAV if a second argument is given
python sdt_core.py vc000101.sdt output.wav
```

---

## Tips

- Use **44100 Hz** source audio if you can (otherwise the tool resamples it).
- Aim for the **same length** as the original: a longer recording is trimmed, a shorter one is padded with silence.
- The output file keeps the exact size of the original, which is required for the game to read it back correctly.
- On a stereo file, your (mono) audio is duplicated onto both channels. This is expected and works well for voices; for true left/right stereo music, note that both channels will carry the same signal.

### A note on speed

The PS-ADPCM encoder is pure Python and brute-forces the best filter/shift per 28-sample block. On a large stereo file (several minutes), generating the dub can take a while and may look frozen — it isn't. Decoding for preview is much faster (a few seconds even for the biggest files).

---

## Disclaimer

Unofficial project, not affiliated with Konami. Provided as-is, for personal creation and modding. Use only with files from your own copy of the game.

## License

Free — do whatever you want with it.
