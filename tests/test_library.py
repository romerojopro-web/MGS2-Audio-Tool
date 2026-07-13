"""Tests for the tagging databases.

Two files live side by side in one folder: the SDT one is keyed by filename, the
SDX one by sound hash (so tagging a sound tags every bank that shares it). They
stay separate on purpose — the SDX tags describe the game, not the user's work,
so they can be shared on their own.
"""

from mgs2_audio.library import db


def test_empty_folder_yields_empty_databases(tmp_path):
    assert db.load_library(str(tmp_path))["entries"] == {}
    assert db.load_sdx_library(str(tmp_path))["entries"] == {}


def test_missing_file_is_silent(tmp_path, caplog):
    # A database that doesn't exist yet is the normal state for any tab the
    # user hasn't tagged — it must not warn (the app loads 6+ of these at
    # startup, one per tab).
    with caplog.at_level("WARNING", logger="mgs2_audio.library.db"):
        data = db.load_library(str(tmp_path))
    assert data == {"version": db.LIBRARY_VERSION, "entries": {}}
    assert caplog.records == []


def test_sdt_entry_round_trips(tmp_path):
    folder = str(tmp_path)
    data = db.load_library(folder)
    db.set_entry(data, "vc000101.sdt", done=True, tag="Soldier",
                 speaker="Guard", notes="Who goes there?")
    assert db.save_library(folder, data)

    entry = db.get_entry(db.load_library(folder), "vc000101.sdt")
    assert entry["done"] is True
    assert entry["tag"] == "Soldier"
    assert entry["speaker"] == "Guard"
    assert entry["notes"] == "Who goes there?"


def test_sdx_entry_round_trips(tmp_path):
    folder = str(tmp_path)
    data = db.load_sdx_library(folder)
    db.set_sdx_entry(data, "ab12cd34", done=True, tag="Rain", banks=47)
    assert db.save_sdx_library(folder, data)

    entry = db.get_sdx_entry(db.load_sdx_library(folder), "ab12cd34")
    assert entry["done"] is True
    assert entry["tag"] == "Rain"
    assert entry["banks"] == 47


def test_the_two_databases_are_separate_files(tmp_path):
    folder = str(tmp_path)
    sdt_data = db.load_library(folder)
    db.set_entry(sdt_data, "a.sdt", tag="Codec")
    db.save_library(folder, sdt_data)

    sdx_data = db.load_sdx_library(folder)
    db.set_sdx_entry(sdx_data, "deadbeef", tag="Door")
    db.save_sdx_library(folder, sdx_data)

    names = sorted(p.name for p in tmp_path.iterdir())
    assert names == [db.LIBRARY_FILENAME, db.SDX_LIBRARY_FILENAME]
    assert "deadbeef" not in db.load_library(folder)["entries"]
    assert "a.sdt" not in db.load_sdx_library(folder)["entries"]


# ─────────────────────────────────────────────────────────────────────────────
# Every tab gets its own file — MC SDX, Substance SDX, VOX, BGM, Dém, Séquenceur
# ─────────────────────────────────────────────────────────────────────────────

# The full set of per-tab database filenames the tool writes today. If a new
# tab is added, extend this list — the point of the test below is that it's
# impossible to add one that collides with an existing one by accident.
ALL_LIBRARY_FILENAMES = [
    db.LIBRARY_FILENAME,
    db.SDX_LIBRARY_FILENAME,
    db.SUBSTANCE_SDX_LIBRARY_FILENAME,
    db.VOX_LIBRARY_FILENAME,
    db.BGM_LIBRARY_FILENAME,
    db.DEMOS_LIBRARY_FILENAME,
    db.SEQ_LIBRARY_FILENAME,
]


def test_all_library_filenames_are_distinct():
    assert len(ALL_LIBRARY_FILENAMES) == len(set(ALL_LIBRARY_FILENAMES))


def test_substance_sdx_entry_round_trips(tmp_path):
    folder = str(tmp_path)
    data = db.load_library(folder, db.SUBSTANCE_SDX_LIBRARY_FILENAME)
    db.set_entry(data, "cafef00d", db.SDX_ENTRY_DEFAULTS,
                 done=True, tag="Splash", banks=6)
    assert db.save_library(folder, data, db.SUBSTANCE_SDX_LIBRARY_FILENAME)

    reloaded = db.load_library(folder, db.SUBSTANCE_SDX_LIBRARY_FILENAME)
    entry = db.get_entry(reloaded, "cafef00d", db.SDX_ENTRY_DEFAULTS)
    assert entry["done"] is True
    assert entry["tag"] == "Splash"
    assert entry["banks"] == 6


def test_vox_entry_round_trips(tmp_path):
    folder = str(tmp_path)
    data = db.load_library(folder, db.VOX_LIBRARY_FILENAME)
    db.set_entry(data, "12", db.TAG_ENTRY_DEFAULTS,
                 done=True, tag="Codec", notes="Otacon line")
    assert db.save_library(folder, data, db.VOX_LIBRARY_FILENAME)

    entry = db.get_entry(db.load_library(folder, db.VOX_LIBRARY_FILENAME),
                         "12", db.TAG_ENTRY_DEFAULTS)
    assert entry["done"] is True
    assert entry["tag"] == "Codec"
    assert entry["notes"] == "Otacon line"


def test_bgm_and_demos_entries_use_separate_files(tmp_path):
    folder = str(tmp_path)
    bgm_data = db.load_library(folder, db.BGM_LIBRARY_FILENAME)
    db.set_entry(bgm_data, "bgm.dat#0", db.TAG_ENTRY_DEFAULTS, tag="Theme")
    db.save_library(folder, bgm_data, db.BGM_LIBRARY_FILENAME)

    demos_data = db.load_library(folder, db.DEMOS_LIBRARY_FILENAME)
    db.set_entry(demos_data, "demo.dat#0", db.TAG_ENTRY_DEFAULTS, tag="Intro")
    db.save_library(folder, demos_data, db.DEMOS_LIBRARY_FILENAME)

    assert "demo.dat#0" not in db.load_library(folder, db.BGM_LIBRARY_FILENAME)["entries"]
    assert "bgm.dat#0" not in db.load_library(folder, db.DEMOS_LIBRARY_FILENAME)["entries"]


def test_seq_entry_keyed_by_bank_and_cue(tmp_path):
    """Cue #0 of one bank must not collide with cue #0 of another."""
    folder = str(tmp_path)
    data = db.load_library(folder, db.SEQ_LIBRARY_FILENAME)
    db.set_entry(data, "pk000002.sdx#0", db.TAG_ENTRY_DEFAULTS, done=True, tag="Melody")
    db.set_entry(data, "pk000003.sdx#0", db.TAG_ENTRY_DEFAULTS, done=False, tag="SE")
    db.save_library(folder, data, db.SEQ_LIBRARY_FILENAME)

    reloaded = db.load_library(folder, db.SEQ_LIBRARY_FILENAME)
    a = db.get_entry(reloaded, "pk000002.sdx#0", db.TAG_ENTRY_DEFAULTS)
    b = db.get_entry(reloaded, "pk000003.sdx#0", db.TAG_ENTRY_DEFAULTS)
    assert a["done"] is True and a["tag"] == "Melody"
    assert b["done"] is False and b["tag"] == "SE"


def test_unknown_entry_returns_defaults(tmp_path):
    data = db.load_library(str(tmp_path))
    entry = db.get_entry(data, "never-seen.sdt")
    assert entry["done"] is False
    assert entry["tag"] == ""


def test_unknown_fields_are_ignored(tmp_path):
    data = db.load_library(str(tmp_path))
    db.set_entry(data, "a.sdt", tag="Codec", nonsense="boom")
    assert "nonsense" not in data["entries"]["a.sdt"]


def test_tags_are_ordered_by_frequency():
    data = {"entries": {}}
    for name, tag in [("a", "Soldier"), ("b", "Soldier"), ("c", "Soldier"),
                      ("d", "Codec"), ("e", "Codec"), ("f", "Boss")]:
        db.set_entry(data, name, tag=tag)
    assert db.collect_tags(data) == ["Soldier", "Codec", "Boss"]
    assert db.tag_counts(data) == {"Soldier": 3, "Codec": 2, "Boss": 1}


def test_blank_tags_are_not_collected():
    data = {"entries": {}}
    db.set_entry(data, "a", tag="  ")
    db.set_entry(data, "b", tag="Real")
    assert db.collect_tags(data) == ["Real"]


def test_counts_done_and_todo():
    data = {"entries": {}}
    db.set_entry(data, "a", done=True)
    db.set_entry(data, "b", done=False)
    db.set_entry(data, "c", done=True)
    assert db.counts(data, ["a", "b", "c"]) == {"total": 3, "done": 2, "todo": 1}


def test_corrupt_database_is_replaced_not_raised(tmp_path):
    (tmp_path / db.LIBRARY_FILENAME).write_text("{ this is not json")
    assert db.load_library(str(tmp_path))["entries"] == {}
