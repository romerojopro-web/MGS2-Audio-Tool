#!/usr/bin/env python3
"""
seq_page.py — The music tab: the sequencer hidden in the `.sdx` banks.

MGS2 ships no music files. Each bank carries a small program that plays its
samples as notes, and this page renders those pieces so they can be heard.

Rendering is a pure-Python software SPU, so it costs a few seconds for a long
piece. Results are cached: a piece is only synthesised once per set of options.
"""

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QFileDialog, QFrame, QHBoxLayout,
    QInputDialog,
    QLabel, QListWidgetItem, QMessageBox, QProgressDialog, QPushButton,
    QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..formats import sequence as seq
from ..library import db as lib
from .. import render as synth
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin

# Bump this when render.py changes to invalidate cached renders
_CACHE_VERSION = 2


class SeqPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse a bank's musical pieces, listen to them, export them."""

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.bank = None
        self.bank_path = ""
        self.cue = None
        self.preview_wav = ""
        self._cache = {}          # (cue index, stereo) -> wav path

        self._init_playback()
        self._init_tagging(lib.SEQ_LIBRARY_FILENAME)

        self._build()
        self.reload_library()

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        # Left: the bank's pieces
        panel = QFrame(); panel.setObjectName("library")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.lbl_list_title = QLabel(); self.lbl_list_title.setObjectName("panel")
        lay.addWidget(self.lbl_list_title)

        self.btn_open = QPushButton(); self.btn_open.setObjectName("small")
        self.btn_open.clicked.connect(self.open_bank)
        lay.addWidget(self.btn_open)

        # Opening a stage is a convenience, not a requirement: a music bank
        # carries its own instruments. It just saves hunting for which of a
        # stage's .sdx files are musical.
        self.btn_open_stage = QPushButton(); self.btn_open_stage.setObjectName("small")
        self.btn_open_stage.clicked.connect(self.open_stage)
        lay.addWidget(self.btn_open_stage)

        self.lbl_bank = QLabel(); self.lbl_bank.setObjectName("dim")
        self.lbl_bank.setWordWrap(True)
        lay.addWidget(self.lbl_bank)

        self.combo_filter = QComboBox()
        for key in ("seq_filter_music", "seq_filter_long", "seq_filter_all"):
            self.combo_filter.addItem("", key)
        self.combo_filter.currentIndexChanged.connect(self._fill_list)
        lay.addWidget(self.combo_filter)

        self.list_cues = PlayOnSpaceList(self.toggle_play)
        self.list_cues.currentItemChanged.connect(self._on_cue_selected)
        lay.addWidget(self.list_cues, 1)

        self.lbl_count = QLabel(); self.lbl_count.setObjectName("dim")
        lay.addWidget(self.lbl_count)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        lay.addLayout(self._build_tagging_panel())

        splitter.addWidget(panel)

        # Right: listen, export, options
        right = QWidget()
        root = QVBoxLayout(right)
        root.setContentsMargins(16, 4, 4, 8)
        root.setSpacing(14)

        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step1 = QLabel(); self.lbl_step1.setObjectName("step")
        c.addWidget(self.lbl_step1)
        self.lbl_info = QLabel(); self.lbl_info.setObjectName("body")
        self.lbl_info.setWordWrap(True)
        c.addWidget(self.lbl_info)
        self.lbl_hint = QLabel(); self.lbl_hint.setObjectName("dim")
        self.lbl_hint.setWordWrap(True)
        c.addWidget(self.lbl_hint)
        root.addWidget(card)

        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step2 = QLabel(); self.lbl_step2.setObjectName("step")
        c.addWidget(self.lbl_step2)
        row = QHBoxLayout()
        self.btn_play = QPushButton("▶"); self.btn_play.setObjectName("play")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)
        row.addWidget(self.btn_play)
        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self.player.setPosition)
        row.addWidget(self.slider, 1)
        self.lbl_time = QLabel("0:00 / 0:00"); self.lbl_time.setObjectName("dim")
        row.addWidget(self.lbl_time)
        c.addLayout(row)
        root.addWidget(card)

        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step3 = QLabel(); self.lbl_step3.setObjectName("step")
        c.addWidget(self.lbl_step3)
        self.btn_export = QPushButton(); self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_wav)
        c.addWidget(self.btn_export)
        self.btn_export_all = QPushButton(); self.btn_export_all.setEnabled(False)
        self.btn_export_all.clicked.connect(self.export_all)
        c.addWidget(self.btn_export_all)
        root.addWidget(card)

        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step4 = QLabel(); self.lbl_step4.setObjectName("step")
        c.addWidget(self.lbl_step4)
        self.chk_stereo = QCheckBox(); self.chk_stereo.setChecked(True)
        self.chk_stereo.stateChanged.connect(self._options_changed)
        c.addWidget(self.chk_stereo)
        root.addWidget(card)

        root.addStretch()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])

    def _card(self):
        f = QFrame(); f.setObjectName("card")
        return f

    # ── Translation ──────────────────────────────────────────────────────────

    def _update_info(self):
        """Rebuild the info line for the current state, so it follows a language
        change instead of staying in whichever language opened the bank."""
        if not self.bank or self.cue is None:
            self.lbl_info.setText(self._t("seq_select_hint"))
            return
        self.lbl_info.setText(self._t(
            "seq_info", i=self.cue.index, tracks=self.cue.track_count,
            notes=self.bank.note_count(self.cue)))

    def retranslate(self):
        self.lbl_list_title.setText(self._t("seq_list_title"))
        self.btn_open.setText(self._t("seq_browse"))
        self.btn_open_stage.setText(self._t("seq_open_stage"))
        if not self.bank:
            self.lbl_bank.setText(self._t("seq_no_file"))
        self._update_info()
        for i in range(self.combo_filter.count()):
            self.combo_filter.setItemText(i, self._t(self.combo_filter.itemData(i)))
        self.lbl_step1.setText(self._t("seq_open_title"))
        self.lbl_hint.setText(self._t("seq_hint"))
        self.lbl_step2.setText(self._t("seq_listen_title"))
        self.lbl_step3.setText(self._t("seq_export_title"))
        self.btn_export.setText(self._t("seq_export"))
        self.btn_export_all.setText(self._t("seq_export_all"))
        self.lbl_step4.setText(self._t("seq_options_title"))
        self.chk_stereo.setText(self._t("seq_stereo"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading a bank ───────────────────────────────────────────────────────

    def open_bank(self):
        start = self.win.cfg.get("dir_sdx", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_seq"), start, self._t("filter_sdx"))
        if path:
            self._load_bank(path)

    def open_stage(self):
        """Pick a bank from a stage folder, musical ones first.

        Purely a shortcut: a music bank holds its own instruments, so nothing
        here depends on the rest of the folder. It only spares the user from
        opening `.sdx` files one by one to find which carry music.
        """
        start = self.win.cfg.get("dir_sdx", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("seq_open_stage"), start)
        if not folder:
            return

        entries = []
        for name in sorted(os.listdir(folder)):
            if not name.lower().endswith(".sdx"):
                continue
            path = os.path.join(folder, name)
            try:
                bank = seq.parse_sequence(path)
            except Exception:
                continue
            entries.append((bank.is_music, len(bank.cues), len(bank.instruments),
                            name, path))
        if not entries:
            QMessageBox.information(self, self._t("err_title"),
                                    self._t("seq_no_banks"))
            return

        entries.sort(key=lambda e: (not e[0], e[3]))     # music banks first
        labels = [
            self._t("seq_bank_row", name=name,
                    kind=self._t("seq_kind_music" if music else "seq_kind_se"),
                    cues=cues, instruments=instruments)
            for music, cues, instruments, name, _ in entries
        ]
        choice, ok = QInputDialog.getItem(
            self, self._t("seq_open_stage"), self._t("seq_pick_bank"),
            labels, 0, False)
        if ok and choice in labels:
            self._load_bank(entries[labels.index(choice)][4])

    def _load_bank(self, path):
        try:
            bank = seq.parse_sequence(path)
        except ValueError:
            QMessageBox.information(self, self._t("err_title"),
                                    self._t("seq_no_sequence"))
            return
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_read", e=e))
            return

        self.bank = bank
        self.bank_path = path
        self.win.cfg["dir_sdx"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self._purge_cache()
        self._reset_selection()

        self.lbl_bank.setText(path)
        self.lbl_info.setText(self._t("seq_select_hint"))
        self.btn_export_all.setEnabled(True)
        self._fill_list()
        self.win.status.showMessage(self._t(
            "seq_status_loaded", name=os.path.basename(path), n=len(self.bank.cues)))

    def _min_notes(self) -> int:
        key = self.combo_filter.currentData()
        return {"seq_filter_music": 8, "seq_filter_long": 20}.get(key, 1)

    def _visible_cues(self):
        if not self.bank:
            return []
        floor = self._min_notes()
        return [c for c in self.bank.cues if self.bank.note_count(c) >= floor]

    def _fill_list(self):
        if not self.bank:
            return
        self.list_cues.blockSignals(True)
        self.list_cues.clear()
        for cue in self._visible_cues():
            item = QListWidgetItem(self._row_text(cue))
            item.setData(Qt.ItemDataRole.UserRole, cue.index)
            self.list_cues.addItem(item)
        self.list_cues.blockSignals(False)
        self._refresh_count()

    def _row_text(self, cue) -> str:
        notes = self.bank.note_count(cue)
        tag_entry = lib.get_entry(self._tag_library, self._entry_key(cue),
                                  self._tag_entry_defaults)
        marker = "✓" if tag_entry["done"] else "○"
        tag = (tag_entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return (f"{marker} #{cue.index:>3}   {cue.track_count} trk   "
                f"{notes:>3} notes{tagtxt}")

    def _update_row_inplace(self, key):
        for row in range(self.list_cues.count()):
            it = self.list_cues.item(row)
            index = it.data(Qt.ItemDataRole.UserRole)
            cue = next((c for c in self.bank.cues if c.index == index), None)
            if cue and self._entry_key(cue) == key:
                it.setText(self._row_text(cue))
                return

    def _refresh_count(self):
        if not self.bank:
            self.lbl_count.setText("")
            return
        playable = sum(1 for i in self.bank.instruments if i.size > 0)
        self.lbl_count.setText(self._t(
            "seq_count", n=len(self._visible_cues()), instruments=playable))

    def _reset_selection(self):
        self.cue = None
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Tagging ──────────────────────────────────────────────────────────────

    def _entry_key(self, cue) -> str:
        # MC has dozens of .sdx banks (one per stage) — a cue #5 in one bank
        # is unrelated to cue #5 in another.
        return f"{os.path.basename(self.bank_path)}#{cue.index}"

    def _tag_key(self):
        return self._entry_key(self.cue) if self.cue else None

    def _on_tag_saved(self, key, refresh):
        self._update_row_inplace(key)

    # ── Selection and synthesis ──────────────────────────────────────────────

    def _options_changed(self):
        """Changing an option invalidates what was already synthesised."""
        self._purge_cache()
        if self.cue is not None:
            self._render_current()

    def _purge_cache(self):
        """Delete all cached temp files and clear the dict."""
        # Stop the player first: the currently loaded render may be one of the
        # cached files about to be unlinked.
        self._release_player()
        for path in self._cache.values():
            if os.path.exists(path):
                try:
                    os.unlink(path)
                except Exception:
                    pass
        self._cache.clear()

    def _on_cue_selected(self, current, previous):
        if current is None or not self.bank:
            return
        index = current.data(Qt.ItemDataRole.UserRole)
        self.cue = next((c for c in self.bank.cues if c.index == index), None)
        if self.cue is None:
            return
        self._update_info()
        self._fill_tag_fields()
        self._set_tag_fields_enabled(True)
        self._render_current()

    def _render_current(self):
        """Synthesise the selected piece, or reuse it if already done."""
        stereo = self.chk_stereo.isChecked()
        key = (_CACHE_VERSION, self.cue.index, stereo)

        path = self._cache.get(key)
        if path is None or not os.path.exists(path):
            self.win.status.showMessage(self._t("seq_rendering"))
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            QApplication.processEvents()
            try:
                left, right = synth.render_cue(self.bank, self.cue,
                                               stereo=stereo)
            except Exception as e:
                QApplication.restoreOverrideCursor()
                QMessageBox.critical(self, self._t("err_title"),
                                     self._t("err_generate", e=e))
                return
            finally:
                QApplication.restoreOverrideCursor()

            if not left:
                self.win.status.showMessage(self._t("seq_select_hint"))
                return
            fd, path = tempfile.mkstemp(suffix=".wav")
            os.close(fd)
            synth.save_cue(left, right, path, stereo=stereo)
            self._cache[key] = path

        self._release_preview(keep=path)
        self.preview_wav = path
        self._want_play = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.btn_play.setText("▶")
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.win.status.showMessage(self._t(
            "seq_info", i=self.cue.index, tracks=self.cue.track_count,
            notes=self.bank.note_count(self.cue)))

    # ── Playback ─────────────────────────────────────────────────────────────

    def _release_preview(self, keep=None):
        if self.preview_wav and self.preview_wav != keep:
            self._release_player()
        self.preview_wav = ""

    # ── Export ───────────────────────────────────────────────────────────────

    def export_wav(self):
        if not (self.cue and self.preview_wav):
            return
        base = os.path.splitext(os.path.basename(self.bank_path))[0]
        start = self.win.cfg.get("dir_sdx_export", "") or os.path.expanduser("~")
        suggested = os.path.join(start, f"{base}_cue{self.cue.index:03d}.wav")
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_sdx_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        with open(self.preview_wav, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    def export_all(self):
        if not self.bank:
            return
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_export_all"),
            self.win.cfg.get("dir_sdx_export", "") or os.path.expanduser("~"))
        if not folder:
            return
        self.win.cfg["dir_sdx_export"] = folder
        save_config(self.win.cfg)

        cues = self._visible_cues()
        stereo = self.chk_stereo.isChecked()
        base = os.path.splitext(os.path.basename(self.bank_path))[0]

        dlg = QProgressDialog(self._t("seq_exporting", n=0, total=len(cues)),
                              "Cancel", 0, len(cues), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)

        written = 0
        for n, cue in enumerate(cues, 1):
            if dlg.wasCanceled():
                break
            dlg.setValue(n - 1)
            dlg.setLabelText(self._t("seq_exporting", n=n, total=len(cues)))
            QApplication.processEvents()
            try:
                left, right = synth.render_cue(self.bank, cue, stereo=stereo)
            except Exception:
                continue
            if not left:
                continue
            notes = self.bank.note_count(cue)
            name = os.path.join(folder, f"{base}_cue{cue.index:03d}_{notes}notes.wav")
            synth.save_cue(left, right, name, stereo=stereo)
            written += 1
        dlg.close()
        self.win.status.showMessage(self._t("seq_exported_all", n=written))

    def cleanup(self):
        self._release_player()
        self._release_preview()
        self._purge_cache()
        self._destroy_playback()
