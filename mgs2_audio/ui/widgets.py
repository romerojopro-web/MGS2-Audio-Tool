#!/usr/bin/env python3
"""
widgets.py — Small Qt widgets and mixins shared by all pages.
"""

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QAudioOutput, QMediaPlayer
from PyQt6.QtWidgets import (
    QCheckBox, QCompleter, QLabel, QLineEdit, QListWidget, QPlainTextEdit,
    QPushButton, QVBoxLayout,
)

from ..library import db as lib


class PopupLineEdit(QLineEdit):
    """A line edit that shows its whole completion list on click / focus.

    The tag list is only useful if it is easy to reach: clicking the field pops
    the full list of labels already used, so a label can be reused without
    remembering how it was spelled.
    """

    def _popup(self):
        completer = self.completer()
        if completer and completer.model() and completer.model().rowCount():
            completer.setCompletionPrefix("")
            completer.complete()

    def mousePressEvent(self, event):
        super().mousePressEvent(event)
        if not self.text():
            self._popup()

    def focusInEvent(self, event):
        super().focusInEvent(event)
        if not self.text():
            self._popup()


class PlayOnSpaceList(QListWidget):
    """A list where the space bar plays / pauses the selected sound.

    Auditioning hundreds of files means living in this list: arrows to move,
    space to listen. Without it, every preview costs a trip to the mouse.
    """

    def __init__(self, on_space):
        super().__init__()
        self._on_space = on_space

    def keyPressEvent(self, event):
        if event.key() == Qt.Key.Key_Space:
            self._on_space()
            event.accept()
            return
        super().keyPressEvent(event)


class PlaybackMixin:
    """Mixin that provides audio playback for pages with btn_play, slider, lbl_time.

    Subclasses must call ``self._init_playback()`` in their ``__init__`` and
    set up ``self.btn_play``, ``self.slider``, and ``self.lbl_time`` before
    calling it.  They should also set ``self.preview_wav`` to the path of the
    current temp WAV (or ``""`` when nothing is loaded).
    """

    def _init_playback(self):
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(0.9)
        self._want_play = False

        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)
        self.player.mediaStatusChanged.connect(self._on_media_status)
        self.player.errorOccurred.connect(self._on_player_error)

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("\u25b6")
            return
        status = self.player.mediaStatus()
        not_ready = status in (
            QMediaPlayer.MediaStatus.NoMedia,
            QMediaPlayer.MediaStatus.LoadingMedia,
            QMediaPlayer.MediaStatus.InvalidMedia,
        )
        if not_ready and getattr(self, "preview_wav", ""):
            self._want_play = True
            self.player.setSource(QUrl.fromLocalFile(self.preview_wav))
            return
        self.player.play()
        self.btn_play.setText("\u23f8")

    def _on_media_status(self, status):
        ready = status in (
            QMediaPlayer.MediaStatus.LoadedMedia,
            QMediaPlayer.MediaStatus.BufferedMedia,
        )
        if ready and self._want_play:
            self._want_play = False
            self.player.play()
            self.btn_play.setText("\u23f8")
        if status == QMediaPlayer.MediaStatus.EndOfMedia:
            self.btn_play.setText("\u25b6")

    def _on_position(self, pos):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        self._update_time(pos, self.player.duration())

    def _on_duration(self, dur):
        self.slider.setRange(0, dur)
        self._update_time(self.player.position(), dur)

    def _update_time(self, pos, dur):
        def fmt(ms):
            s = ms // 1000
            return f"{s // 60}:{s % 60:02d}"
        self.lbl_time.setText(f"{fmt(pos)} / {fmt(dur)}")

    def _on_player_error(self, *args):
        """Default error handler; subclasses may override for a custom message."""
        error = args[0] if args else None
        error_string = args[1] if len(args) > 1 else ""
        if error == QMediaPlayer.Error.NoError:
            return
        self.btn_play.setText("▶")
        self._want_play = False
        if hasattr(self, "win"):
            self.win.status.showMessage(f"Audio: {error_string or 'playback failed'}")

    def _release_player(self):
        """Release the current media source (call before deleting temp files).

        Called on every file/sample change within a page's lifetime — must NOT
        disconnect the position/duration/status signals, or the slider and time
        label go dead after the first file swap. Signals are only disconnected
        in `_destroy_playback`, when the page itself is being torn down.
        """
        try:
            self.player.setSource(QUrl())
            self.player.stop()
        except Exception:
            pass

    def _destroy_playback(self):
        """Fully destroy the player and audio output (call in page cleanup)."""
        self._release_player()
        try:
            self.player.positionChanged.disconnect(self._on_position)
            self.player.durationChanged.disconnect(self._on_duration)
            self.player.mediaStatusChanged.disconnect(self._on_media_status)
            self.player.errorOccurred.disconnect(self._on_player_error)
        except (TypeError, RuntimeError):
            pass
        try:
            self.player.deleteLater()
        except Exception:
            pass
        try:
            self.audio_out.deleteLater()
        except Exception:
            pass


class TaggingMixin:
    """Mixin that provides a done/tag/notes panel backed by a JSON database.

    Subclasses call ``self._init_tagging(library_filename, entry_defaults)`` in
    their ``__init__``, then ``self._build_tagging_panel()`` while building their
    UI to get a ready-to-insert layout (checkbox, tag field with autocomplete,
    notes, save button). They must implement:

    - ``_tag_key()`` — the database key for whatever is currently selected, or
      ``None`` when nothing selects to a taggable entry (extend/replace tags of
      the SAME target, but keyed however the page's format needs — a filename,
      a content hash, ``"{archive}#{index}"``, …).
    - ``_on_tag_saved(key, refresh)`` — refresh whatever the page shows for
      that row (list text, marker) after a save. ``refresh`` is True when the
      save should also restore selection (e.g. after a filter-affecting field
      like "done" changed).

    And may override ``_tag_extra_fields()`` to persist extra cached fields
    beyond done/tag/notes (SDX caches duration/size/bank count, for instance).
    """

    def _init_tagging(self, library_filename: str, entry_defaults: dict = None):
        self._tag_library_filename = library_filename
        self._tag_entry_defaults = entry_defaults or lib.TAG_ENTRY_DEFAULTS
        self._tag_library = {"version": lib.LIBRARY_VERSION, "entries": {}}
        self._loading_tag_entry = False

    def _build_tagging_panel(self) -> QVBoxLayout:
        lay = QVBoxLayout()
        lay.setSpacing(8)

        self.chk_done = QCheckBox()
        self.chk_done.stateChanged.connect(self._on_tag_edited)
        lay.addWidget(self.chk_done)

        self.lbl_tag = QLabel(); self.lbl_tag.setObjectName("dim")
        lay.addWidget(self.lbl_tag)
        self.edit_tag = PopupLineEdit()
        self.edit_tag.editingFinished.connect(self._on_tag_edited)
        lay.addWidget(self.edit_tag)

        self.lbl_notes = QLabel(); self.lbl_notes.setObjectName("dim")
        lay.addWidget(self.lbl_notes)
        self.edit_notes = QPlainTextEdit()
        self.edit_notes.setFixedHeight(60)
        lay.addWidget(self.edit_notes)

        self.btn_save_entry = QPushButton(); self.btn_save_entry.setObjectName("small")
        self.btn_save_entry.clicked.connect(self._save_tag_entry)
        lay.addWidget(self.btn_save_entry)

        self._set_tag_fields_enabled(False)
        return lay

    def _retranslate_tag_fields(self):
        self.chk_done.setText(self._t("lib_done"))
        self.lbl_tag.setText(self._t("lib_tag"))
        self.edit_tag.setPlaceholderText(self._t("lib_tag_hint"))
        self.lbl_notes.setText(self._t("lib_notes"))
        self.btn_save_entry.setText(self._t("lib_save_entry"))

    # ── Extension points (subclasses implement/override) ───────────────────

    def _tag_key(self):
        raise NotImplementedError

    def _tag_extra_fields(self) -> dict:
        return {}

    def _on_tag_saved(self, key, refresh: bool):
        pass

    # ── Generic load/save/display ───────────────────────────────────────────

    def reload_library(self):
        folder = self.win.db_folder
        if folder:
            self._tag_library = lib.load_library(folder, self._tag_library_filename)
        self._update_tag_completer()

    def _update_tag_completer(self):
        if not hasattr(self, "edit_tag"):
            return
        tags = lib.collect_tags(self._tag_library)       # most used first
        comp = QCompleter(tags, self)
        comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        comp.setFilterMode(Qt.MatchFlag.MatchContains)
        comp.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.edit_tag.setCompleter(comp)

    def _set_tag_fields_enabled(self, on: bool):
        for w in (self.chk_done, self.edit_tag, self.edit_notes, self.btn_save_entry):
            w.setEnabled(on)

    def _fill_tag_fields(self):
        key = self._tag_key()
        entry = (lib.get_entry(self._tag_library, key, self._tag_entry_defaults)
                 if key is not None else dict(self._tag_entry_defaults))
        self._loading_tag_entry = True
        self.chk_done.setChecked(bool(entry.get("done")))
        self.edit_tag.setText(entry.get("tag", "") or "")
        self.edit_notes.setPlainText(entry.get("notes", "") or "")
        self._loading_tag_entry = False

    def _on_tag_edited(self, *args):
        if self._loading_tag_entry or self._tag_key() is None:
            return
        self._persist_tag_entry(refresh=self.sender() is self.chk_done)

    def _save_tag_entry(self):
        key = self._tag_key()
        if key is None:
            return
        self._persist_tag_entry(refresh=True)
        self.win.status.showMessage(self._t("lib_saved", name=str(key)))

    def _persist_tag_entry(self, refresh: bool = False):
        folder = self.win.db_folder
        if not folder:
            self.win.status.showMessage(self._t("lib_no_db"))
            return
        key = self._tag_key()
        if key is None:
            return
        lib.set_entry(
            self._tag_library, key, self._tag_entry_defaults,
            done=self.chk_done.isChecked(),
            tag=self.edit_tag.text().strip(),
            notes=self.edit_notes.toPlainText(),
            **self._tag_extra_fields(),
        )
        lib.save_library(folder, self._tag_library, self._tag_library_filename)
        self._update_tag_completer()
        self._on_tag_saved(key, refresh)
