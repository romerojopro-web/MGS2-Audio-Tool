# MGS2 SDT Tool

A dubbing tool for the `.sdt` audio files of **Metal Gear Solid 2: Sons of Liberty** (Master Collection, PC version).

It lets you open a game `.sdt` file, listen to the original dialogue, export it to WAV, then **replace the voice with your own** to create a home-made dub.

---

## Features

- **Open** an `.sdt` file and show its duration and info.
- **Listen** to the original dialogue directly in the app.
- **Export** the audio to `.wav` (to identify the line or edit it).
- **Replace** the audio with your own `.wav` recording.
- **Save** a modified `.sdt` that keeps exactly the same structure AND the same name as the original — ready to drop back into the game.

Format conversion (44100 Hz) and encoding are automatic. On a mono file the dub is encoded as mono; on a stereo file your recording is placed on both channels — the app tells you which, so there are no surprises.

### What's new in 1.5.0

- **Full stereo support.** Stereo `.sdt` files (the "dialogue bank" files) are now decoded and re-encoded correctly, with **no echo** and at the right speed. See the technical notes below for what was going on.
- **Clear stereo/mono messaging.** When you pick your dub, the app states whether it will be re-encoded as mono or stereo, matching the source file.
- **Richer command line.** The engine can now be driven entirely from the terminal with `info`, `export` and `replace` sub-commands (see below).
- Interface still fully multilingual: Français / English / Español (top-right selector, remembered between sessions).

Settings are stored in `~/.mgs2_sdt_tool.json`.

---

## The SDT format (technical notes)

These findings were obtained by reverse-engineering the format and validated by ear on known game dialogue.

- **Codec**: PlayStation 4-bit ADPCM (PS-ADPCM / VAG).
- **Sample rate**: 44100 Hz.
- **Channels**: 1 (mono) or 2 (stereo), read from the byte at offset `0x98` in the header.
- **Structure**: a header (table + metadata) followed by a series of blocks ("MG blocks"). Each block = 16-byte header + up to 0x4000 bytes of audio data. The last block may be shorter. Concatenated, the blocks form the complete audio stream.
- **Stereo interleave**: on 2-channel files, the two channels are interleaved in chunks of **0x800 bytes** (`L, R, L, R…`). One 0x4000 data block therefore holds 8 chunks (`L R L R L R L R`).

### The echo bug (and how it was fixed)

Early versions decoded the raw stream as a single mono flow. On stereo files this flattened the two channels together: channel R ended up "glued" 0x800 bytes — about **81 ms** — behind channel L, which was heard as a distinct echo/overlap on the voice. An earlier attempt to deinterleave at the wrong granularity (per 16-byte ADPCM unit) halved the duration instead, producing a fast, high-pitched "chipmunk" voice.

The fix: read the channel count at `0x98`, deinterleave stereo files at the correct **0x800** step, decode each channel separately, and output proper stereo (`L, R, L, R…`). The 81 ms self-similarity that caused the echo drops away and playback runs at the correct speed.

The PS-ADPCM decoder/encoder is implemented in pure Python in `sdt_core.py`, with no external dependency.

---

## Installation

Requires **Python 3.10+** and **PyQt6**.

```bash
pip install PyQt6
```

The project has three files:

- `sdt_tool.py` — the graphical interface (run this).
- `sdt_core.py` — the engine (PS-ADPCM decoding/encoding, pure Python; also a CLI).
- `translations.py` — the interface strings (FR / EN / ES).

## Usage (GUI)

```bash
python sdt_tool.py
```

Then, in the app:

1. **Open an SDT file** — pick a game `.sdt` (e.g. `vc000101.sdt`).
2. **Listen** — play the dialogue to identify it, or export it to WAV.
3. **Choose your dub** — a `.wav` of your voice (ideally the same length).
4. **Generate** — save the modified `.sdt`.

Then replace the game's original file with yours.
**Always back up the original file before replacing it.**

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

## Dubbing tips

- Record your voice at **44100 Hz** if you can (otherwise the tool resamples it).
- Aim for the **same length** as the original: a longer recording is trimmed, a shorter one is padded with silence.
- The output file keeps the exact size of the original, which is required for the game to read it back correctly.
- On a stereo file, your (mono) recording is duplicated onto both channels. This is expected and matches how the game reads centered dialogue.

### A note on speed

The PS-ADPCM encoder is pure Python and brute-forces the best filter/shift per 28-sample block. On a large stereo file (several minutes), generating the dub can take a while and may look frozen — it isn't. Decoding for preview is much faster (a few seconds even for the biggest files).

---

## Disclaimer

Unofficial project, not affiliated with Konami. Provided as-is, for personal creation and modding. Use only with files from your own copy of the game.

## License

Free — do whatever you want with it.
