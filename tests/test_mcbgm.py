#!/usr/bin/env python3
"""Tests for formats/mcbgm.py — Master Collection Unity BGM bundles.

The default run is light and needs neither UnityPy nor a game install: it
covers the WAV loader, folder discovery and relative-path construction.
The full replace round-trip against the real game install is gated behind
``--realdata`` (and skipped when the install or UnityPy is absent).
"""

import json
import os
import struct
import wave

import pytest

from mgs2_audio.formats import mcbgm

MC_INSTALL = r"C:\Games\Steam\steamapps\common\MGS2"


def _has_unitypy() -> bool:
    try:
        import UnityPy  # noqa: F401
        return True
    except ImportError:
        return False


def write_wav(path, frames, channels=2, width=2, rate=44100):
    with wave.open(str(path), "wb") as w:
        w.setnchannels(channels)
        w.setsampwidth(width)
        w.setframerate(rate)
        w.writeframes(frames)
    return str(path)


# ─────────────────────────────────────────────────────────────────────────────
# WAV loading (pure stdlib, always runs)
# ─────────────────────────────────────────────────────────────────────────────

def test_load_wav_pcm_stereo_16bit(tmp_path):
    frames = struct.pack("<4h", 100, -100, 200, -200)  # 2 stereo frames
    path = write_wav(tmp_path / "s16.wav", frames, channels=2, rate=48000)
    pcm, ch, freq, secs = mcbgm.load_wav_pcm(path)
    assert (pcm, ch, freq) == (frames, 2, 48000)
    assert secs == pytest.approx(2 / 48000)


def test_load_wav_pcm_mono_supported(tmp_path):
    frames = struct.pack("<3h", 1, 2, 3)
    path = write_wav(tmp_path / "mono.wav", frames, channels=1, rate=22050)
    pcm, ch, freq, secs = mcbgm.load_wav_pcm(path)
    assert (pcm, ch, freq) == (frames, 1, 22050)


def test_load_wav_pcm_widens_8bit(tmp_path):
    # 8-bit WAV is unsigned: 128 is silence, 255 is max positive.
    path = write_wav(tmp_path / "u8.wav", bytes([128, 255, 0]),
                     channels=1, width=1)
    pcm, ch, freq, secs = mcbgm.load_wav_pcm(path)
    assert struct.unpack("<3h", pcm) == (0, 127 << 8, -128 << 8)


def test_load_wav_pcm_rejects_unsupported(tmp_path):
    path24 = write_wav(tmp_path / "s24.wav", b"\x00" * 6, channels=1, width=3)
    with pytest.raises(ValueError, match="24-bit"):
        mcbgm.load_wav_pcm(path24)
    path5ch = write_wav(tmp_path / "5ch.wav", b"\x00" * 10, channels=5)
    with pytest.raises(ValueError, match="5-channel"):
        mcbgm.load_wav_pcm(path5ch)


# ─────────────────────────────────────────────────────────────────────────────
# Folder discovery (fake tree, always runs)
# ─────────────────────────────────────────────────────────────────────────────

def _fake_install(root, with_catalog=True):
    bgm_dir = os.path.join(str(root), *mcbgm.BGM_REL_DIR.split("/"))
    os.makedirs(bgm_dir)
    if with_catalog:
        open(os.path.join(bgm_dir, mcbgm.CATALOG_FILENAME), "wb").close()
    return bgm_dir


def test_find_bgm_dir_locates_the_folder(tmp_path):
    bgm_dir = _fake_install(tmp_path)
    assert mcbgm.find_bgm_dir(str(tmp_path)) == bgm_dir


def test_find_bgm_dir_rejects_wrong_folder(tmp_path):
    with pytest.raises(ValueError, match="Master Collection"):
        mcbgm.find_bgm_dir(str(tmp_path))


def test_find_bgm_dir_requires_the_catalog(tmp_path):
    _fake_install(tmp_path, with_catalog=False)
    with pytest.raises(ValueError, match=mcbgm.CATALOG_FILENAME):
        mcbgm.find_bgm_dir(str(tmp_path))


def test_rel_paths_use_forward_slashes():
    # rel_path is user-facing modding info: game-root-relative, '/'-separated.
    assert "\\" not in mcbgm.BGM_REL_DIR
    assert mcbgm.BGM_REL_DIR.startswith("launcher_Data/")


# ─────────────────────────────────────────────────────────────────────────────
# FSB5 container + conforming (pure byte-work, always runs)
# ─────────────────────────────────────────────────────────────────────────────

def test_fsb5_round_trips_through_parse():
    pcm = struct.pack("<8h", *range(8))          # 4 stereo frames
    data = mcbgm.build_fsb5_pcm16(pcm, 2, 44100, loop=(0, 3))
    assert data[:4] == b"FSB5"
    info = mcbgm.parse_fsb5_info(data)
    assert info == {"codec": mcbgm.FSB5_CODEC_PCM16, "channels": 2,
                    "frames": 4, "loop": (0, 3)}
    assert data.endswith(pcm)


def test_fsb5_without_loop():
    pcm = struct.pack("<4h", 1, 2, 3, 4)
    info = mcbgm.parse_fsb5_info(mcbgm.build_fsb5_pcm16(pcm, 1, 48000))
    assert info["channels"] == 1
    assert info["frames"] == 4
    assert info["loop"] is None


def test_fsb5_rejects_unknown_rate():
    with pytest.raises(ValueError, match="44101"):
        mcbgm.build_fsb5_pcm16(b"\x00\x00", 1, 44101)


def test_parse_fsb5_info_rejects_bare_pcm():
    assert mcbgm.parse_fsb5_info(b"\x00" * 64) is None


def test_conform_pads_short_audio():
    pcm = struct.pack("<4h", 100, 200, 300, 400)     # 2 stereo frames
    out = mcbgm.conform_pcm(pcm, 2, 44100, 2, 44100, 5)
    assert len(out) == 5 * 2 * 2
    assert out[:8] == pcm[:8]
    assert out[8:] == bytes(12)                      # silence padding


def test_conform_trims_long_audio():
    pcm = struct.pack("<6h", 1, 2, 3, 4, 5, 6)       # 3 stereo frames
    out = mcbgm.conform_pcm(pcm, 2, 44100, 2, 44100, 2)
    assert out == pcm[:8]


def test_conform_mono_to_stereo_duplicates():
    pcm = struct.pack("<2h", 7, -7)
    out = mcbgm.conform_pcm(pcm, 1, 44100, 2, 44100, 2)
    assert struct.unpack("<4h", out) == (7, 7, -7, -7)


def test_conform_resamples_to_target_rate():
    pcm = struct.pack("<4h", 10, 20, 30, 40)         # 4 mono frames @ 22050
    out = mcbgm.conform_pcm(pcm, 1, 22050, 1, 44100, 8)
    # nearest-neighbour doubling: each source sample appears twice
    assert struct.unpack("<8h", out) == (10, 10, 20, 20, 30, 30, 40, 40)


def test_replace_refuses_the_games_own_folder(tmp_path):
    # The guard fires before any UnityPy work, so a dummy track suffices.
    bundle = tmp_path / "x.bundle"
    bundle.write_bytes(b"")
    track = mcbgm.McBgmTrack(
        name="X", bundle_path=str(bundle), rel_path="x", path_id=1,
        channels=2, frequency=44100, bits=16, length_sec=1.0)
    wav = write_wav(tmp_path / "in.wav", struct.pack("<2h", 0, 0))
    with pytest.raises(ValueError, match="own bundle"):
        mcbgm.replace_audio(track, wav, str(tmp_path))


# ─────────────────────────────────────────────────────────────────────────────
# Addressables catalog patching (synthetic catalog, always runs)
# ─────────────────────────────────────────────────────────────────────────────

def _fake_catalog(root, bundle_name, crc=123456789, size=1000):
    """Build a minimal Addressables catalog with one bundle entry."""
    import base64 as b64
    options = ('{"m_Hash":"abc","m_Crc":%d,"m_BundleName":"x",'
               '"m_BundleSize":%d}' % (crc, size))
    js = options.encode("utf-16-le")
    blob = (bytes([7])
            + bytes([4]) + b"Asm."
            + bytes([3]) + b"Cls"
            + struct.pack("<i", len(js)) + js)
    entries = struct.pack("<I", 1) + struct.pack("<7i", 0, 0, -1, 0, 0, 0, 0)
    cat = {
        "m_InternalIds": [f"{{Runtime}}\\StandaloneWindows64\\bgm/{bundle_name}"],
        "m_EntryDataString": b64.b64encode(entries).decode(),
        "m_ExtraDataString": b64.b64encode(blob).decode(),
    }
    path = os.path.join(str(root), *mcbgm.CATALOG_REL_PATH.split("/"))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(cat, f)
    return path


def _dummy_track(root, bundle_name):
    return mcbgm.McBgmTrack(
        name="X", bundle_path=os.path.join(str(root), bundle_name),
        rel_path=bundle_name, path_id=1, channels=2, frequency=44100,
        bits=16, length_sec=1.0)


def test_patch_catalog_zeroes_crc_in_place(tmp_path):
    import base64 as b64
    path = _fake_catalog(tmp_path, "music.bundle", crc=987654321, size=1000)
    track = _dummy_track(tmp_path, "music.bundle")
    with open(path, encoding="utf-8") as f:
        before = len(b64.b64decode(json.load(f)["m_ExtraDataString"]))

    assert mcbgm.patch_catalog(str(tmp_path), track, new_size=2000) is True
    options = mcbgm.read_catalog_options(str(tmp_path), track)
    assert options["m_Crc"] == 0
    assert options["m_BundleSize"] == 2000
    assert options["m_Hash"] == "abc"            # untouched
    # In-place surgery: the binary blob keeps its exact byte length (nothing
    # else in the catalog points at shifted offsets), and a .bak is written.
    with open(path, encoding="utf-8") as f:
        after = len(b64.b64decode(json.load(f)["m_ExtraDataString"]))
    assert after == before
    assert os.path.exists(path + ".bak")


def test_patch_catalog_is_idempotent(tmp_path):
    _fake_catalog(tmp_path, "music.bundle")
    track = _dummy_track(tmp_path, "music.bundle")
    assert mcbgm.patch_catalog(str(tmp_path), track, new_size=2000) is True
    assert mcbgm.patch_catalog(str(tmp_path), track, new_size=2000) is False


def test_patch_catalog_unknown_bundle(tmp_path):
    _fake_catalog(tmp_path, "music.bundle")
    with pytest.raises(ValueError, match="not found"):
        mcbgm.patch_catalog(str(tmp_path), _dummy_track(tmp_path, "other.bundle"))


# ─────────────────────────────────────────────────────────────────────────────
# Real game install (opt-in: --realdata, needs UnityPy + the install)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def mc_tracks(request):
    if not request.config.getoption("--realdata"):
        pytest.skip("real-data test — pass --realdata to run "
                    "(reads the actual game install)")
    if not _has_unitypy():
        pytest.skip("UnityPy not installed")
    if not os.path.isdir(MC_INSTALL):
        pytest.skip(f"Master Collection install not found at {MC_INSTALL}")
    return mcbgm.parse_catalog(MC_INSTALL)


def test_catalog_lists_all_named_tracks(mc_tracks):
    # 6 scenario tracks + launcher music (mainmenu, credits/license merged).
    assert len(mc_tracks) == 8
    names = {t.name for t in mc_tracks}
    assert "INFILTRATION" in names
    assert "mainmenu" in names
    assert "credits / license" in names
    for t in mc_tracks:
        assert os.path.isfile(t.bundle_path)
        assert any(t.rel_path.startswith(d + "/") for d in mcbgm.CLIP_DIRS)
        assert t.channels == 2
        assert t.length_sec > 0


def test_replace_round_trips(mc_tracks, tmp_path):
    """The replacement must be indistinguishable from the original clip.

    A deliberately non-conform WAV (mono, 22 050 Hz, 2 s of silence) must come
    out as a valid FSB5 with the original's channels, rate and exact frame
    count, an untouched m_Length — and decode through real FMOD (the same
    engine the game uses), which is what black-screened when the resource was
    bare PCM.
    """
    import UnityPy
    from UnityPy.helpers.ResourceReader import get_resource_data

    track = next(t for t in mc_tracks if t.name == "INFILTRATION")
    wav = write_wav(tmp_path / "in.wav", b"\x00" * (22050 * 2 * 2),
                    channels=1, rate=22050)

    out = mcbgm.replace_audio(track, wav, str(tmp_path / "out"))
    assert os.path.basename(out) == os.path.basename(track.bundle_path)

    env = UnityPy.load(out)
    obj = next(o for o in env.objects if o.type.name == "AudioClip")
    clip = obj.read()
    assert clip.m_CompressionFormat == mcbgm.COMPRESSION_PCM
    assert clip.m_Channels == track.channels          # original, not the WAV's
    assert clip.m_Frequency == track.frequency
    assert clip.m_Length == pytest.approx(track.length_sec, abs=0.1)

    res = clip.m_Resource
    info = mcbgm.parse_fsb5_info(bytes(get_resource_data(
        res.m_Source, obj.assets_file, res.m_Offset, res.m_Size)))
    assert info["codec"] == mcbgm.FSB5_CODEC_PCM16
    assert info["frames"] == pytest.approx(
        track.length_sec * track.frequency, rel=0.01)
    assert info["loop"] is not None                   # _lp track keeps looping

    # Real FMOD must accept the container — extract_wav goes through
    # clip.samples for FSB5 resources.
    new_track = mcbgm.McBgmTrack(
        name=track.name, bundle_path=out, rel_path=track.rel_path,
        path_id=track.path_id, channels=track.channels,
        frequency=track.frequency, bits=16, length_sec=track.length_sec)
    round_wav = str(tmp_path / "roundtrip.wav")
    mcbgm.extract_wav(new_track, round_wav)
    with wave.open(round_wav, "rb") as w:
        assert w.getnframes() == info["frames"]
        assert w.getframerate() == track.frequency
        assert w.getnchannels() == track.channels
