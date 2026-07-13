#!/usr/bin/env python3
"""
mcbgm.py — Master Collection scenario BGM (Unity AssetBundles).

Master Collection (2023) does not carry the PS2 `mdx` music system at all: its
scenario music is 6 standard Unity `AudioClip`s, one per `UnityFS` AssetBundle,
plus a catalog bundle whose `SoundData_ScenarioBGM` MonoBehaviour lists the
tracks by their real names (ARMS DEPOT, BATTLE, …) with the PathID of each clip.
See docs/ORCHESTRATION.md for the full discovery notes.

The launcher's own music follows the same scheme in two more folders: the
main-menu theme (+ its `sounddata_bgm.asset.bundle` catalog) under
`packedassetsmgs2_assets_launcher/bgm/mgs2/`, and the credits/license theme
under `packedassetsrc_assets_launcher/bgm/`.  The scenario tracks live under:

    <game root>/launcher_Data/StreamingAssets/aa/StandaloneWindows64/
        packedassetsmgs2_assets_scenarioapp/mgs2/bgm/

Replacement model (validated against the real bundles, then against the game
itself): the audio bytes are NOT in the serialized AudioClip — they live in a
`.resource` sub-file of the bundle's internal CAB archive, referenced by
`m_Resource` (StreamedResource: offset/size/source).  That resource is a
**FSB5 container** (FMOD Sound Bank: header + sample header + optional LOOP /
VORBIS chunks + audio data), NOT bare audio — an in-game test showed the
launcher black-screens on a resource FMOD cannot parse.  So a replacement must
stay in disguise:

- wrap the new audio in a valid FSB5 (codec PCM16, loop chunk mirrored from
  the original so looping tracks keep looping);
- conform it to the original clip exactly — same channel count, same sample
  rate (naive resampling), same sample count (padded with silence or trimmed);
- keep every serialized AudioClip field identical except `m_CompressionFormat`
  (Vorbis → PCM, must match the actual FSB contents) and the resource size.

UnityPy is imported lazily so the rest of the tool keeps working without it —
it is an optional dependency needed only by this module.
"""

import array
import base64
import json
import os
import shutil
import struct
import wave
from dataclasses import dataclass
from typing import List, Optional, Tuple

# Paths of the BGM folders relative to the game install root — these are also
# the information shown to the user so they know exactly which file to mod.
_AA = "launcher_Data/StreamingAssets/aa/StandaloneWindows64"
BGM_REL_DIR = f"{_AA}/packedassetsmgs2_assets_scenarioapp/mgs2/bgm"
LAUNCHER_BGM_REL_DIR = f"{_AA}/packedassetsmgs2_assets_launcher/bgm/mgs2"
RC_BGM_REL_DIR = f"{_AA}/packedassetsrc_assets_launcher/bgm"
CATALOG_FILENAME = "sounddata_scenariobgm.asset.bundle"
LAUNCHER_CATALOG_FILENAME = "sounddata_bgm.asset.bundle"

# Where clip bundles live, and which catalogs name them.  The launcher catalog
# references the credits clip across folders (it sits in RC_BGM_REL_DIR), so
# clips are indexed by PathID over every folder before the catalogs are read.
CLIP_DIRS = (BGM_REL_DIR, LAUNCHER_BGM_REL_DIR, RC_BGM_REL_DIR)
CATALOGS = (
    (BGM_REL_DIR, CATALOG_FILENAME),                    # 6 scenario tracks
    (LAUNCHER_BGM_REL_DIR, LAUNCHER_CATALOG_FILENAME),  # mainmenu/credits/license
)
_CATALOG_NAMES = frozenset(name for _, name in CATALOGS)

COMPRESSION_PCM = 0


class UnityPyMissing(RuntimeError):
    """UnityPy is not installed — this module cannot work without it."""

    def __init__(self):
        super().__init__(
            "UnityPy is required to read Master Collection BGM bundles "
            "(pip install UnityPy)")


def _unitypy():
    try:
        import UnityPy
        return UnityPy
    except ImportError:
        raise UnityPyMissing() from None


# ─────────────────────────────────────────────────────────────────────────────
# Representation
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class McBgmTrack:
    """One scenario BGM track = one AudioClip in its own AssetBundle."""
    name: str                 # catalog name, e.g. "INFILTRATION"
    bundle_path: str          # absolute path of the .wav.bundle on disk
    rel_path: str             # path relative to the game root ('/' separators)
    path_id: int              # AudioClip PathID (catalog → clip link)
    channels: int
    frequency: int
    bits: int
    length_sec: float


# ─────────────────────────────────────────────────────────────────────────────
# Locating and reading
# ─────────────────────────────────────────────────────────────────────────────

def find_bgm_dir(game_root: str) -> str:
    """Return the absolute BGM folder inside a Master Collection install.

    Raises ValueError when the folder (or the catalog bundle inside it) is
    missing — i.e. `game_root` does not look like an MGS2 Master Collection
    installation.
    """
    bgm_dir = os.path.join(game_root, *BGM_REL_DIR.split("/"))
    if not os.path.isdir(bgm_dir):
        raise ValueError(
            f"no {BGM_REL_DIR!r} folder under {game_root!r} — this does not "
            "look like an MGS2 Master Collection install")
    if not os.path.isfile(os.path.join(bgm_dir, CATALOG_FILENAME)):
        raise ValueError(
            f"found the BGM folder but not {CATALOG_FILENAME!r} inside it")
    return bgm_dir


def _first_audioclip(env):
    """Return the first AudioClip ObjectReader of a loaded bundle, or None."""
    for obj in env.objects:
        if obj.type.name == "AudioClip":
            return obj
    return None


def _read_catalog(catalog_path: str) -> List[dict]:
    """Read the SoundDatas MonoBehaviour catalog of a bundle.

    Returns the raw `SoundDatas` list: dicts with at least
    ``{"name": str, "audioClip": {"m_PathID": int}}``, in catalog order.
    """
    UnityPy = _unitypy()
    env = UnityPy.load(catalog_path)
    for obj in env.objects:
        if obj.type.name != "MonoBehaviour":
            continue
        tree = obj.read_typetree()
        if "SoundDatas" in tree:
            return tree["SoundDatas"]
    raise ValueError(
        f"{os.path.basename(catalog_path)} contains no SoundDatas catalog — "
        "unexpected bundle layout")


def parse_catalog(game_root: str) -> List[McBgmTrack]:
    """List the BGM tracks of a Master Collection install.

    Covers the 6 scenario tracks plus the launcher music (main menu, credits).
    Clip bundles from every known BGM folder are indexed by PathID first, then
    the catalogs are read in order for the names — the launcher catalog
    references the credits clip in a *different* folder, hence the two passes.
    Catalog entries that share one clip (credits/license) merge into a single
    track with the names joined.
    """
    UnityPy = _unitypy()
    find_bgm_dir(game_root)     # validate this is really an MC install

    # PathID → (bundle path, rel dir, clip metadata) across every clip bundle.
    clips = {}
    for rel_dir in CLIP_DIRS:
        folder = os.path.join(game_root, *rel_dir.split("/"))
        if not os.path.isdir(folder):
            continue
        for name in sorted(os.listdir(folder)):
            if name in _CATALOG_NAMES or not name.endswith(".bundle"):
                continue
            bundle_path = os.path.join(folder, name)
            obj = _first_audioclip(UnityPy.load(bundle_path))
            if obj is None:
                continue
            clips[obj.path_id] = (bundle_path, rel_dir, obj.read())

    tracks: List[McBgmTrack] = []
    by_path_id = {}
    for rel_dir, catalog_name in CATALOGS:
        catalog_path = os.path.join(game_root, *rel_dir.split("/"), catalog_name)
        if not os.path.isfile(catalog_path):
            continue
        for sound in _read_catalog(catalog_path):
            path_id = (sound.get("audioClip") or {}).get("m_PathID", 0)
            if path_id not in clips:
                continue
            name = sound.get("name", "")
            if path_id in by_path_id:
                # Same clip under several catalog names (credits + license).
                seen = by_path_id[path_id]
                if name and name not in seen.name.split(" / "):
                    seen.name = f"{seen.name} / {name}"
                continue
            bundle_path, clip_dir, clip = clips[path_id]
            track = McBgmTrack(
                name=name or os.path.basename(bundle_path),
                bundle_path=bundle_path,
                rel_path=f"{clip_dir}/{os.path.basename(bundle_path)}",
                path_id=path_id,
                channels=clip.m_Channels or 2,
                frequency=clip.m_Frequency or 44100,
                bits=clip.m_BitsPerSample or 16,
                length_sec=float(clip.m_Length or 0.0),
            )
            by_path_id[path_id] = track
            tracks.append(track)
    return tracks


def extract_wav(track: McBgmTrack, out_path: str) -> None:
    """Decode a track's AudioClip and write it as a WAV file.

    Everything in a proper FSB5 resource (the game's own Vorbis clips as well
    as our PCM16 replacements) decodes through ``clip.samples`` (real FMOD).
    Resources written by an early build of this module were bare headerless
    PCM — those get wrapped in a WAV header by hand instead.
    """
    UnityPy = _unitypy()
    env = UnityPy.load(track.bundle_path)
    obj = _first_audioclip(env)
    if obj is None:
        raise ValueError(f"no AudioClip in {track.bundle_path!r}")
    clip = obj.read()

    if clip.m_CompressionFormat == COMPRESSION_PCM and clip.m_Resource:
        from UnityPy.helpers.ResourceReader import get_resource_data
        res = clip.m_Resource
        data = bytes(get_resource_data(
            res.m_Source, obj.assets_file, res.m_Offset, res.m_Size))
        if parse_fsb5_info(data) is None:
            # Legacy bare PCM (pre-FSB5 build) — wrap it ourselves.
            with wave.open(out_path, "wb") as w:
                w.setnchannels(clip.m_Channels or 2)
                w.setsampwidth(2)
                w.setframerate(clip.m_Frequency or 44100)
                w.writeframes(data)
            return

    samples = clip.samples          # {filename: decoded bytes}
    if not samples:
        raise ValueError(f"AudioClip in {track.bundle_path!r} decoded empty")
    data = next(iter(samples.values()))
    with open(out_path, "wb") as f:
        f.write(data)


# ─────────────────────────────────────────────────────────────────────────────
# FSB5 container (what actually lives in the .resource)
# ─────────────────────────────────────────────────────────────────────────────

# FSB5 sample headers store the rate as an index into FMOD's fixed table.
FSB5_FREQUENCIES = {8000: 1, 11000: 2, 11025: 3, 16000: 4, 22050: 5,
                    24000: 6, 32000: 7, 44100: 8, 48000: 9}
FSB5_CODEC_PCM16 = 2
FSB5_CHUNK_LOOP = 3
_FSB5_HEADER_SIZE = 0x3C


def parse_fsb5_info(data: bytes) -> Optional[dict]:
    """Read the header of a FSB5 resource: codec, frames, loop points.

    Returns None when `data` is not a FSB5 container (e.g. a resource written
    by an early version of this module, before the in-game format was known).
    """
    if data[:4] != b"FSB5":
        return None
    codec = struct.unpack_from("<I", data, 0x18)[0]
    raw = struct.unpack_from("<Q", data, _FSB5_HEADER_SIZE)[0]
    info = {
        "codec": codec,
        "channels": ((raw >> 5) & 1) + 1,
        "frames": (raw >> 34) & 0x3FFFFFFF,
        "loop": None,
    }
    pos = _FSB5_HEADER_SIZE + 8
    next_chunk = raw & 1
    while next_chunk:
        flag = struct.unpack_from("<I", data, pos)[0]
        next_chunk = flag & 1
        size = (flag >> 1) & 0x00FFFFFF
        ctype = (flag >> 25) & 0x7F
        if ctype == FSB5_CHUNK_LOOP and size >= 8:
            info["loop"] = struct.unpack_from("<II", data, pos + 4)
        pos += 4 + size
    return info


def build_fsb5_pcm16(pcm: bytes, channels: int, frequency: int,
                     loop: Optional[Tuple[int, int]] = None) -> bytes:
    """Wrap raw interleaved 16-bit PCM in a minimal, valid FSB5 container.

    This is what the game's FMOD runtime actually parses — handing it bare
    PCM makes the launcher hang on a black screen.  `loop` (start, end in
    frames) mirrors the original clip's LOOP chunk so looping BGM keeps
    looping.
    """
    if channels not in (1, 2):
        raise ValueError(f"FSB5 sample header carries 1 or 2 channels, not {channels}")
    freq_index = FSB5_FREQUENCIES.get(frequency)
    if freq_index is None:
        raise ValueError(f"{frequency} Hz is not an FSB5 table rate "
                         f"({sorted(FSB5_FREQUENCIES)})")
    frames = len(pcm) // (2 * channels)

    chunks = b""
    if loop is not None:
        flag = 0 | (8 << 1) | (FSB5_CHUNK_LOOP << 25)   # last chunk, 8 bytes
        chunks = struct.pack("<III", flag, loop[0], loop[1])

    raw = ((1 if chunks else 0)
           | (freq_index << 1)
           | ((channels - 1) << 5)
           | (0 << 6)                  # data offset 0 (single sample)
           | (frames << 34))
    sample_headers = struct.pack("<Q", raw) + chunks

    header = struct.pack(
        "<4sIIIIII", b"FSB5", 1, 1, len(sample_headers), 0, len(pcm),
        FSB5_CODEC_PCM16) + bytes(0x3C - 0x1C)   # zero flags/hash/dummy
    return header + sample_headers + pcm


# ─────────────────────────────────────────────────────────────────────────────
# Conforming user audio to the original clip (the "infiltration" pass)
# ─────────────────────────────────────────────────────────────────────────────

def conform_pcm(pcm: bytes, channels: int, frequency: int,
                target_channels: int, target_frequency: int,
                target_frames: int) -> bytes:
    """Fit interleaved 16-bit PCM to the original clip's exact shape.

    Mixes mono↔stereo, resamples (nearest neighbour — same approach as
    `codec/wav.py`), then pads with silence or trims so the result has
    exactly `target_frames` frames.  The game never sees a duration change.
    """
    chans = [array.array("h", pcm[:])[c::channels] for c in range(channels)]

    if channels == 1 and target_channels == 2:
        chans = [chans[0], chans[0]]
    elif channels == 2 and target_channels == 1:
        chans = [array.array("h", ((l + r) // 2 for l, r in zip(*chans)))]

    if frequency != target_frequency:
        ratio = target_frequency / frequency
        n_out = int(len(chans[0]) * ratio)
        chans = [array.array("h", (c[min(len(c) - 1, int(i / ratio))]
                                   for i in range(n_out)))
                 for c in chans]

    frames = len(chans[0])
    if frames > target_frames:
        chans = [c[:target_frames] for c in chans]
    elif frames < target_frames:
        pad = array.array("h", bytes(2 * (target_frames - frames)))
        chans = [c + pad for c in chans]

    out = array.array("h", bytes(2 * target_frames * target_channels))
    for c, chan in enumerate(chans):
        out[c::target_channels] = chan
    return out.tobytes()


# ─────────────────────────────────────────────────────────────────────────────
# Replacement (the modding path)
# ─────────────────────────────────────────────────────────────────────────────

def load_wav_pcm(path: str):
    """Read a WAV file into raw 16-bit PCM for a Unity clip.

    Accepts mono/stereo, 8- or 16-bit PCM (8-bit is widened to 16).  Any
    sample rate is fine — Unity plays the clip at whatever ``m_Frequency``
    says, so no resampling is needed.

    Returns ``(pcm_bytes, channels, frequency, length_seconds)``.
    """
    with wave.open(path, "rb") as w:
        channels = w.getnchannels()
        width = w.getsampwidth()
        frequency = w.getframerate()
        frames = w.getnframes()
        data = w.readframes(frames)

    if channels not in (1, 2):
        raise ValueError(f"{channels}-channel WAV not supported (mono/stereo only)")
    if width == 1:
        # 8-bit WAV is unsigned; widen to signed 16-bit.
        data = struct.pack(f"<{len(data)}h", *((b - 128) << 8 for b in data))
    elif width != 2:
        raise ValueError(f"{width * 8}-bit WAV not supported (8- or 16-bit only)")

    length_sec = frames / frequency if frequency else 0.0
    return data, channels, frequency, length_sec


def replace_audio(track: McBgmTrack, wav_path: str, out_dir: str) -> str:
    """Rebuild a track's bundle with the audio of `wav_path`, into `out_dir`.

    The user's WAV is conformed to the original clip's exact shape first
    (channels, sample rate, frame count — padded with silence or trimmed),
    wrapped in a valid FSB5 container, and only then swapped in: apart from
    the audio itself (and the PCM compression format), the game sees a clip
    identical to its own.

    The source bundle is never touched: the rewritten bundle is written as
    ``out_dir/<original bundle name>`` (the exact name the game expects) and
    that path is returned.  Refuses to write into the source folder so the
    game's own file can never be overwritten by accident — installing the
    replacement is a deliberate separate step.
    """
    UnityPy = _unitypy()
    from UnityPy.classes.generated import StreamedResource
    from UnityPy.helpers.ResourceReader import get_resource_data
    from UnityPy.streams import EndianBinaryReader

    if (os.path.abspath(out_dir)
            == os.path.abspath(os.path.dirname(track.bundle_path))):
        raise ValueError("refusing to overwrite the game's own bundle — "
                         "choose a different output folder")

    pcm, channels, frequency, _ = load_wav_pcm(wav_path)

    env = UnityPy.load(track.bundle_path)
    obj = _first_audioclip(env)
    if obj is None:
        raise ValueError(f"no AudioClip in {track.bundle_path!r}")
    clip = obj.read()
    if clip.m_Resource is None or not clip.m_Resource.m_Source:
        raise ValueError("AudioClip has no streamed .resource — unexpected "
                         "bundle layout")

    # The original clip is the mould: same channels/rate/frame count, and the
    # loop chunk (if any) is carried over so looping BGM keeps looping.
    orig_channels = clip.m_Channels or 2
    orig_frequency = clip.m_Frequency or 44100
    res = clip.m_Resource
    orig_fsb = parse_fsb5_info(bytes(get_resource_data(
        res.m_Source, obj.assets_file, res.m_Offset, res.m_Size)))
    if orig_fsb is not None:
        orig_frames = orig_fsb["frames"]
        had_loop = orig_fsb["loop"] is not None
    else:                         # resource from an early build of this module
        orig_frames = int(round(float(clip.m_Length or 0.0) * orig_frequency))
        had_loop = True

    pcm = conform_pcm(pcm, channels, frequency,
                      orig_channels, orig_frequency, orig_frames)
    fsb = build_fsb5_pcm16(
        pcm, orig_channels, orig_frequency,
        loop=(0, max(0, orig_frames - 1)) if had_loop else None)

    # The audio bytes live in the CAB's .resource sub-file, not in the
    # serialized clip: swap that sub-file for our rebuilt FSB5.
    res_name = res.m_Source.split("/")[-1]
    bundle = next(iter(env.files.values()))
    if res_name not in bundle.files:
        raise ValueError(f"resource {res_name!r} not found inside the bundle")
    reader = EndianBinaryReader(fsb)
    reader.flags = 0                 # BundleFile.save_fs reads f.flags
    bundle.files[res_name] = reader

    # Everything the game can compare stays as-is (m_Length, m_Channels,
    # m_Frequency, load type…) — only the resource size and the compression
    # format (which must describe the actual FSB contents) change.
    clip.m_Resource = StreamedResource(
        m_Offset=0, m_Size=len(fsb), m_Source=res.m_Source)
    clip.m_CompressionFormat = COMPRESSION_PCM
    clip.save()
    # clip.save() marks the SerializedFile, but swapping a bundle sub-file by
    # hand marks nothing — without this the bundle silently isn't written.
    bundle.mark_changed()

    os.makedirs(out_dir, exist_ok=True)
    env.save(pack="none", out_path=out_dir)
    return os.path.join(out_dir, os.path.basename(track.bundle_path))


# ─────────────────────────────────────────────────────────────────────────────
# Addressables catalog (the game's per-bundle CRC check)
# ─────────────────────────────────────────────────────────────────────────────

# The launcher loads bundles through Unity Addressables, whose catalog stores
# an AssetBundleRequestOptions JSON per bundle — including a CRC32 the engine
# verifies at load time.  A rebuilt bundle therefore fails to load (black
# screen at boot) no matter how correct its contents are, until its catalog
# entry says CRC 0 ("don't check").
CATALOG_REL_PATH = "launcher_Data/StreamingAssets/aa/catalog.json"


def catalog_path(game_root: str) -> str:
    return os.path.join(game_root, *CATALOG_REL_PATH.split("/"))


def _catalog_entry_blob(cat: dict, bundle_basename: str):
    """Locate a bundle's AssetBundleRequestOptions JSON inside the catalog.

    Returns ``(extra_data: bytes, json_offset: int, json_len: int, options:
    dict)`` — enough to read the options and to rewrite them in place.
    """
    ids = cat["m_InternalIds"]
    target = next((i for i, s in enumerate(ids)
                   if s.replace("\\", "/").endswith("/" + bundle_basename)),
                  None)
    if target is None:
        raise ValueError(f"{bundle_basename!r} not found in the catalog")

    extra = base64.b64decode(cat["m_ExtraDataString"])
    entries = base64.b64decode(cat["m_EntryDataString"])
    count = struct.unpack_from("<I", entries, 0)[0]
    for e in range(count):
        iid, _prov, _dep, _dh, data_index, _pk, _rt = struct.unpack_from(
            "<7i", entries, 4 + e * 28)
        if iid != target or data_index < 0:
            continue
        # ObjectInitializationData: type byte (7 = JsonObject), then
        # 1-byte-length ASCII assembly + class names, then a 4-byte length
        # and the options JSON in UTF-16.
        if extra[data_index] != 7:
            continue
        p = data_index + 1
        p += 1 + extra[p]                      # assembly name
        p += 1 + extra[p]                      # class name
        json_len = struct.unpack_from("<i", extra, p)[0]
        p += 4
        options = json.loads(extra[p:p + json_len].decode("utf-16-le"))
        if "m_Crc" in options:
            return extra, p, json_len, options
    raise ValueError(f"no AssetBundleRequestOptions entry for "
                     f"{bundle_basename!r} in the catalog")


def read_catalog_options(game_root: str, track: McBgmTrack) -> dict:
    """Return a track's AssetBundleRequestOptions from the catalog (read-only)."""
    with open(catalog_path(game_root), encoding="utf-8") as f:
        cat = json.load(f)
    _, _, _, options = _catalog_entry_blob(
        cat, os.path.basename(track.bundle_path))
    return options


def patch_catalog(game_root: str, track: McBgmTrack,
                  new_size: Optional[int] = None) -> bool:
    """Disable the CRC check for one bundle in the Addressables catalog.

    Sets the bundle's ``m_Crc`` to 0 (and ``m_BundleSize`` to `new_size` when
    given) by rewriting the options JSON in place, space-padded to its exact
    original byte length so no offset elsewhere in the catalog moves.  A
    ``catalog.json.bak`` backup is written next to the catalog the first time.

    Returns True when the catalog was modified, False when the entry was
    already as requested.
    """
    path = catalog_path(game_root)
    with open(path, encoding="utf-8") as f:
        cat = json.load(f)

    extra, offset, json_len, options = _catalog_entry_blob(
        cat, os.path.basename(track.bundle_path))

    wanted = dict(options)
    wanted["m_Crc"] = 0
    if new_size is not None:
        wanted["m_BundleSize"] = new_size
    if wanted == options:
        return False

    new_json = json.dumps(wanted, separators=(",", ":"))
    new_bytes = new_json.encode("utf-16-le")
    if len(new_bytes) > json_len:
        # Dropping the size update always fits: zeroing the CRC frees more
        # digits than any realistic size gains.
        wanted["m_BundleSize"] = options["m_BundleSize"]
        new_bytes = json.dumps(wanted, separators=(",", ":")).encode("utf-16-le")
        if len(new_bytes) > json_len:
            raise ValueError("patched catalog options do not fit in place")
    new_bytes += " ".encode("utf-16-le") * ((json_len - len(new_bytes)) // 2)

    cat["m_ExtraDataString"] = base64.b64encode(
        extra[:offset] + new_bytes + extra[offset + json_len:]).decode("ascii")

    bak = path + ".bak"
    if not os.path.exists(bak):
        shutil.copy2(path, bak)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(cat, f, separators=(",", ":"))
    os.replace(tmp, path)
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Display helpers
# ─────────────────────────────────────────────────────────────────────────────

def describe_track(track: McBgmTrack) -> str:
    ch = "stereo" if track.channels == 2 else f"{track.channels}ch"
    return (f"  {track.name:<24} {track.frequency} Hz {ch}  "
            f"{track.length_sec:.1f} s  {track.rel_path}")


def describe(tracks: List[McBgmTrack]) -> str:
    lines = [f"BGM tracks : {len(tracks)}"]
    lines += [describe_track(t) for t in tracks]
    return "\n".join(lines)
