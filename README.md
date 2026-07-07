# MGS2 SDT Tool for MGS2MC Better Audio Mod

A dubbing tool for `.sdt` audio files from     MGS2MCBetterAudioMod

**Metal Gear Solid 2: Sons of Liberty** (Master Collection, PC version).

It lets you open an `.sdt` file from the game, listen to the original dialogue, export it as a WAV file, then **replace the voice with your own** to create custom voice-overs.

---

## Features

- **Open** an `.sdt` file and display its duration and metadata.
- **Listen** to the original dialogue directly inside the application.
- **Export** the audio as a `.wav` file (to identify or edit the voice line).
- **Replace** the audio with your own `.wav` recording.
- **Save** a modified `.sdt` file that preserves the exact same structure **and filename** as the original—ready to be dropped back into the game.

Audio conversion (mono, 44100 Hz) and encoding are handled automatically.

- **Remembered folders**: each section (Open, Export, Dub, Save) remembers the last folder you used, even across sessions. One click, no need to browse again.
- **Original filename preserved**: generated `.sdt` files keep the exact same filename as the original (required by the game).
- **Multilingual interface**: French, English, and Spanish (language selector in the top-right corner, remembered between sessions).
- **Improved metadata display** for better readability.

Settings are stored in `~/.mgs2_sdt_tool.json`.

---

## The SDT Format (Technical Notes)

The following information was obtained through reverse engineering of the format and validated by listening to known dialogue from the game.

- **Codec**: PlayStation 4-bit ADPCM (PS-ADPCM / VAG).
- **Sample rate**: 44100 Hz, mono.
- **Structure**: a header (table + metadata) followed by a series of "MG blocks." Each block consists of a 16-byte header followed by up to `0x4000` bytes of audio data. The final block may be shorter. When concatenated, the blocks form the complete audio stream.

The PS-ADPCM decoder/encoder is implemented entirely in pure Python inside `sdt_core.py`, with no external dependencies.

---

## Installation

Requires **Python 3.10+** and **PyQt6**.

```bash
pip install PyQt6
```

The project contains three files:

- `sdt_tool.py` — the graphical interface (launch this file).
- `sdt_core.py` — the engine (PS-ADPCM decoding/encoding, pure Python).
- `translations.py` — interface translations (French / English / Spanish).

---

## Usage

```bash
python sdt_tool.py
```

Then, inside the application:

1. **Open an SDT file** — select an `.sdt` file from the game (e.g. `vc000101.sdt`).
2. **Listen** — play the original dialogue to identify it, or export it as a WAV file.
3. **Choose your dub** — select a `.wav` recording of your own voice (ideally with the same duration).
4. **Generate** — save the modified `.sdt` file.

Replace the original game file with your modified version.

**Always back up the original file before replacing it.**

### Command Line (Bonus)

The engine can also be used on its own:

```bash
# Display information and export to WAV
python sdt_core.py vc000101.sdt output.wav
```

---

<img width="1915" height="1004" alt="image" src="https://github.com/user-attachments/assets/119f23aa-2fe5-4c53-8bd6-51ecd8ced318" />


## Dubbing Tips

- Record your voice at **44100 Hz** whenever possible (otherwise the tool will automatically resample it).
- Aim for the **same duration** as the original clip: longer recordings are trimmed, shorter ones are padded with silence.
- The output file keeps the exact same size as the original.

---

## Disclaimer

This is an unofficial project and is not affiliated with Konami in any way.

It is provided as-is for personal creativity and modding purposes only.

Please use it only with files extracted from your own legitimate copy of the game.

---

## License

Free to use—do whatever you want with it.
