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
