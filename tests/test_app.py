"""Tests for the application shell (`ui/app.py`).

Only `MainWindow.db_folder` is covered here: each game/mode has to keep its
own tagging database folder, with a transparent migration for configs saved
before that was true (a single shared string).

Building a real `MainWindow()` also builds every page for whatever mode is in
the *real* user config on disk (plugin discovery, folder restore, …) — that's
unavoidable since the property lives on the class, but harmless: each test
immediately replaces `cfg` with an isolated dict before touching `db_folder`,
so nothing here reads or writes the user's actual `~/.mgs2_audio_tool.json`.
"""

from PyQt6.QtWidgets import QApplication

from mgs2_audio.ui.app import MainWindow

_app = QApplication.instance() or QApplication([])


def _window() -> MainWindow:
    w = MainWindow()
    w.cfg = {}  # isolate from the real on-disk config for this test
    return w


def test_db_folder_empty_by_default():
    w = _window()
    w.mode = "mc"
    assert w.db_folder == ""


def test_db_folder_is_isolated_per_mode():
    w = _window()
    w.mode = "mc"
    w.db_folder = "C:/tags/mc"
    w.mode = "substance"
    assert w.db_folder == ""          # untouched by the mc-mode write

    w.db_folder = "C:/tags/substance"
    w.mode = "mc"
    assert w.db_folder == "C:/tags/mc"  # untouched by the substance-mode write

    assert w.cfg["db_folder"] == {"mc": "C:/tags/mc", "substance": "C:/tags/substance"}


def test_db_folder_migrates_legacy_flat_string():
    """Configs saved before per-mode folders existed had a single string."""
    w = _window()
    w.cfg = {"db_folder": "C:/legacy/shared"}
    w.mode = "mc"
    assert w.db_folder == "C:/legacy/shared"
    w.mode = "substance"
    assert w.db_folder == "C:/legacy/shared"  # same value, applied to every mode

    # Migrated in place: subsequent per-mode writes no longer affect each other.
    w.db_folder = "C:/new/substance"
    w.mode = "mc"
    assert w.db_folder == "C:/legacy/shared"


def test_db_folder_ignores_malformed_cfg_value():
    w = _window()
    w.cfg = {"db_folder": 12345}  # neither a str nor a dict
    w.mode = "mc"
    assert w.db_folder == ""
