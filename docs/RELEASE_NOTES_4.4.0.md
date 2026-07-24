# MGS2 Audio Tool — 4.4.0

**Everything that changed since 4.0.0** (covering 4.1.0, 4.2.0, 4.3.0 and 4.4.0),
written for the release page rather than the commit log.

---

## The headline

Two things you could not do before this run of releases:

1. **Work with the game's stock audio, with no mod installed.** The tool now
   reads *and replaces* the Master Collection's own dialogue audio, so the
   Better Audio Mod is no longer a prerequisite for dubbing.
2. **Reach the game's iconic global sounds** — picking up an item, the
   interface, the alert alarm. They are in no `.sdx`; they live in a container
   the game loads once at startup, and nothing could touch them until now.

---

## New: stock (un-modded) `.sdt` audio — listen, export **and replace**

The Master Collection's own dialogue is **Konami XWMA**, not the PS-ADPCM the
Better Audio Mod ships. The SDT tab now handles both:

- **Decoding** (4.1.0) — de-interleaves the container and plays or exports any
  stock voice line. Needs **ffmpeg**.
- **Replacing** (4.2.0) — your WAV is re-encoded and rebuilt into the Konami
  container at the original size. Needs **xWMAEncode.exe**. **Confirmed working
  in-game.**

Two details that make it work rather than merely look right:

- Your WAV is automatically conformed to the original clip's **channel count and
  sample rate**. A stereo file where the game expects mono is rejected in-game
  even though it previews fine in any player.
- If the re-encoded audio does not fit the original's byte capacity, the tool
  steps down through the available bitrates automatically, and refuses clearly
  if nothing fits.

On a Vortex-modded install the stock originals sit next to the mod's files as
`*.sdt.vortex_backup`; those are listed and open normally, and are saved back
under their real `.sdt` name. A checkbox hides them if you only want the mod's
files.

## New: Global Sound Archive tab (4.4.0)

`Misc/<lang>/BP_SE.DAT` holds the sounds the game keeps in memory for the whole
session: item selection and pickup, using an item, interface blips, the
alert-phase alarm. Point the tab at your game folder and it finds the archive
and lists all **106** sounds — listen, export one or all, or replace one with
your own WAV.

Replacements keep each sound's exact byte size so the archive stays valid, and
a `.bak` is written before the first change.

## New: Russian interface (4.1.0)

A full fourth translation alongside French, English and Spanish.

## Fixed: the sequencer was reading every sample slightly wrong (4.3.0)

The instrument directory was being cut short, because the end-of-directory test
keyed on three bytes that are **not** format constants — they are the
instrument's attack rate, release rate and pan, and merely the values most
instruments happen to use. The directory therefore ended at the first
instrument with a custom envelope, and since the audio begins where the
directory ends, **every sample offset shifted with it**.

Measured against the game: **23 of 68 music banks** were misread; one bank gave
135 instruments instead of 150, with nearly every instrument decoded 15 frames
into the previous sample. A skipped terminator record was costing one more
frame on top. Both are fixed, and sample alignment is now essentially perfect.

If you use the sequencer, it will sound different — and correct.

## Fixed: the SDX parser invented samples in music banks (4.3.0)

Stage banks end their audio with padding, and the parser only recognised one of
the two bytes the game uses. On the ~80 music banks it therefore ran past the
end of the audio and carved phantom "samples" out of the data behind it, which
then polluted the cross-bank scan. Both padding bytes are now accepted.

## Fixed: upgrading never costs you your tags (4.2.0)

If you already had a tag database from an earlier version, loading and saving on
the new one is strictly additive — your hand-typed done/tag/speaker/notes are
preserved, and a folder rescan only refreshes the automatic fields. Pinned by
regression tests so it stays true.

## Changed: clearer names and honest labels

- The Master Collection music tab is now **"BGM · Launcher"**. It used to share
  a name with Substance's tab while doing something quite different: those Unity
  bundles drive the **launcher's** music, not what plays during a mission.
- The sequencer tab no longer claims its cues are "not the game's music, see the
  BGM tab for that" — both halves of that were wrong.
- The sequencer's "tune the instruments" checkbox is gone. Tuning is not a
  preference; switching it off only produced a knowingly wrong render. It stays
  in the command line (`--no-tune`) as a diagnostic.

## New: open a whole stage in the sequencer (4.3.0)

A stage folder holds several `.sdx` and finding the musical ones meant opening
them one at a time. "Open a stage…" now lists a folder's banks, musical ones
first, each labelled with what it is:

```
pk000011.sdx · music   · 256 pieces · 150 instruments
pk000000.sdx · effects ·   0 pieces ·  99 instruments
```

Opening a single file still works exactly as before.

## Corrected: the Unity music bundles drive the launcher, not gameplay (4.1.0)

4.0.0 claimed in-game music replacement was confirmed. A second test — replacing
a track, then actually playing a mission — showed those bundles only feed the
**launcher**. The gameplay music follows the original PS2 engine model and is
still being researched. The tool says so plainly now.

---

## Requirements

- **Python 3.10+** and **PyQt6** (`pip install PyQt6`)
- **UnityPy** — optional, only for the BGM · Launcher tab
- **ffmpeg** — optional, only to **decode** stock XWMA dialogue
- **xWMAEncode.exe** — optional, only to **replace** stock XWMA dialogue.
  It is a Microsoft tool that cannot be redistributed, so you supply your own;
  the README explains how to extract it from the DirectX SDK with 7-Zip when the
  installer fails with error `S1023`.

Everything else is pure Python, and no game files are included in the download.

## Still open

In-game (gameplay) music remains unlocated. This round established a lot of what
it is *not*: there is no `mdx` file on PC, no sequence data compiled into the
executable, and it is not in the global sound archive. `docs/ORCHESTRATION.md`
records the ground already covered so the search does not repeat itself.

## Thanks

- **KieronJ/raven** — the PS2 sound-driver reference behind the sequencer.
- **RockeyLol/RIFF-XWMA-Konami-XWMA-Converter** — for documenting the Konami
  XWMA container, which is what made stock audio support possible.
