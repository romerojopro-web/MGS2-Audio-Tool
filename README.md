# MGS2 SDT Tool

A voice dubbing tool for `.sdt` audio files from **Metal Gear Solid 2: Sons of Liberty** (Master Collection, PC version).

It allows you to open an `.sdt` file from the game, listen to the original dialogue, export it as a WAV file, and **replace the original voice with your own** to create custom voice dubbing.

---

## Features

- **Open** an `.sdt` file and display its duration and metadata.
- **Listen** to the original dialogue directly within the application.
- **Export** the audio as a `.wav` file (to identify or edit the dialogue).
- **Replace** the audio with your own `.wav` recording.
- **Save** a modified `.sdt` file that preserves the exact same structure as the original, ready to be used in-game.

Audio conversion (mono, 44100 Hz) and encoding are handled automatically.

---

## SDT Format (Technical Notes)

The following information was obtained through reverse engineering and validated by comparing the output with known in-game dialogue.

- **Codec:** PlayStation 4-bit ADPCM (PS-ADPCM / VAG).
- **Sample Rate:** 44100 Hz, mono.
- **Structure:** A header (tables + metadata) followed by a sequence of "MG blocks". Each block consists of a 16-byte header followed by up to `0x4000` bytes of audio data. The final block may be shorter. When concatenated, these blocks form the complete audio stream.

The PS-ADPCM decoder/encoder is implemented entirely in pure Python inside `sdt_core.py`, with no external dependencies.

---

## Installation

Requires **Python 3.10+** and **PyQt6**.

```bash
pip install PyQt6
```

---

## Usage

```bash
python sdt_tool.py
```

Then, in the application:

1. **Open an SDT file** — select an `.sdt` file from the game (e.g. `vc000101.sdt`).
2. **Listen** — play the original dialogue or export it as a WAV file.
3. **Choose your dub** — select a `.wav` recording of your own voice (ideally with the same duration).
4. **Generate** — save the modified `.sdt` file.

Finally, replace the original game file with your modified version.

**Always back up the original file before replacing it.**

### Command Line (Bonus)

The core engine can also be used directly:

```bash
# Display information and export to WAV
python sdt_core.py vc000101.sdt output.wav
```

---

## Dubbing Tips

- Record your voice at **44100 Hz** whenever possible (otherwise the tool will automatically resample it).
- Try to **match the original duration**. Longer recordings will be truncated, while shorter ones will be padded with silence.
- The generated file preserves the exact size of the original, which is required for the game to read it correctly.

---

## Disclaimer

This is an unofficial project and is not affiliated with or endorsed by Konami.

It is provided for personal modding and creative purposes only.

Please use it only with files extracted from your own legally owned copy of the game.

---

## License

Free to use, modify, and distribute.
