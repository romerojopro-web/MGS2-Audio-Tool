# Changelog

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
