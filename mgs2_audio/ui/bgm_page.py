#!/usr/bin/env python3
"""
bgm_page.py — The BGM tab: browse, listen and export `bgm.dat` archives.

A flat archive of pre-recorded MS-ADPCM music entries.  No synthesis,
no filter — just decode, play, export.
"""

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidgetItem, QMessageBox, QProgressDialog, QPushButton,
    QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..formats import bgm as bgm_fmt
from ..codec.wav import save_wav
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin


class BGMPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse a bgm.dat archive, listen to entries, export them."""

    # Overridden by DEMOSPage — same tab shape, separate tag table.
    _LIBRARY_FILENAME = lib.BGM_LIBRARY_FILENAME

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.bgm = None
        self.bgm_path = ""
        self.bgm_entry = None
        self.preview_wav = ""

        self._init_playback()
        self._init_tagging(self._LIBRARY_FILENAME)
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

        # Left: list of entries
        panel = QFrame(); panel.setObjectName("library")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.lbl_list_title = QLabel(); self.lbl_list_title.setObjectName("panel")
        lay.addWidget(self.lbl_list_title)

        self.btn_open = QPushButton(); self.btn_open.setObjectName("small")
        self.btn_open.clicked.connect(self.open_archive)
        lay.addWidget(self.btn_open)

        self.lbl_archive = QLabel(); self.lbl_archive.setObjectName("dim")
        self.lbl_archive.setWordWrap(True)
        lay.addWidget(self.lbl_archive)

        self.list_entries = PlayOnSpaceList(self.toggle_play)
        self.list_entries.currentItemChanged.connect(self._on_entry_selected)
        lay.addWidget(self.list_entries, 1)

        self.lbl_count = QLabel(); self.lbl_count.setObjectName("dim")
        lay.addWidget(self.lbl_count)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        lay.addLayout(self._build_tagging_panel())

        splitter.addWidget(panel)

        # Right: info, play, export
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
        self.btn_play = QPushButton("\u25b6"); self.btn_play.setObjectName("play")
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
        change instead of staying in whichever language opened the archive."""
        if not self.bgm or self.bgm_entry is None:
            self.lbl_info.setText(self._t("bgm_select_hint"))
            return
        e = self.bgm_entry
        self.lbl_info.setText(self._t(
            "bgm_entry_info", index=e.index, sr=e.sample_rate,
            ch=e.channels, dur=e.duration_seconds))

    def retranslate(self):
        self.lbl_list_title.setText(self._t("bgm_list_title"))
        self.btn_open.setText(self._t("bgm_browse"))
        if not self.bgm:
            self.lbl_archive.setText(self._t("bgm_no_file"))
        self._update_info()
        self.lbl_step1.setText(self._t("bgm_open_title"))
        self.lbl_hint.setText(self._t("bgm_hint"))
        self.lbl_step2.setText(self._t("bgm_listen_title"))
        self.lbl_step3.setText(self._t("bgm_export_title"))
        self.btn_export.setText(self._t("bgm_export"))
        self.btn_export_all.setText(self._t("bgm_export_all"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading ──────────────────────────────────────────────────────────────

    def open_archive(self):
        start = self.win.cfg.get("dir_bgm", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_bgm"), start,
            self._t("filter_dat"))
        if not path:
            return

        try:
            bgm = bgm_fmt.parse_bgm(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return

        if bgm.entry_count == 0:
            QMessageBox.information(self, self._t("err_title"),
                                    self._t("bgm_no_entries"))
            return

        self.bgm = bgm
        self.bgm_path = path
        self.win.cfg["dir_bgm"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self._reset_selection()

        self.lbl_archive.setText(path)
        self.lbl_info.setText(self._t("bgm_select_hint"))
        self.lbl_hint.setText(self._t("bgm_hint"))
        self.btn_export_all.setEnabled(True)
        self._fill_list()
        self.win.status.showMessage(self._t(
            "bgm_status_loaded", name=os.path.basename(path),
            n=bgm.entry_count))

    def _fill_list(self):
        self.list_entries.blockSignals(True)
        self.list_entries.clear()
        if self.bgm:
            for entry in self.bgm.entries:
                item = QListWidgetItem(self._row_text(entry))
                item.setData(Qt.ItemDataRole.UserRole, entry.index)
                self.list_entries.addItem(item)
        self.list_entries.blockSignals(False)
        self._refresh_count()

    def _row_text(self, entry) -> str:
        ch = "stereo" if entry.channels == 2 else f"{entry.channels}ch"
        tag_entry = lib.get_entry(self._tag_library, self._entry_key(entry),
                                  self._tag_entry_defaults)
        marker = "✓" if tag_entry["done"] else "○"
        tag = (tag_entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return (f"{marker} #{entry.index:>3}   {entry.sample_rate} Hz {ch}   "
                f"{entry.duration_seconds:.2f} s{tagtxt}")

    def _update_row_inplace(self, key):
        for row in range(self.list_entries.count()):
            it = self.list_entries.item(row)
            index = it.data(Qt.ItemDataRole.UserRole)
            entry = next((e for e in self.bgm.entries if e.index == index), None)
            if entry and self._entry_key(entry) == key:
                it.setText(self._row_text(entry))
                return

    def _refresh_count(self):
        if self.bgm:
            total_dur = sum(e.duration_seconds for e in self.bgm.entries)
            self.lbl_count.setText(self._t(
                "bgm_count", n=self.bgm.entry_count,
                duration=f"{total_dur:.0f}s"))
        else:
            self.lbl_count.setText("")

    def _reset_selection(self):
        self.bgm_entry = None
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Selection and decoding ───────────────────────────────────────────────

    def _on_entry_selected(self, current, previous):
        if current is None or not self.bgm:
            return
        index = current.data(Qt.ItemDataRole.UserRole)
        self.bgm_entry = next(
            (e for e in self.bgm.entries if e.index == index), None)
        if self.bgm_entry is None:
            return
        self._update_info()
        self._fill_tag_fields()
        self._set_tag_fields_enabled(True)
        self._decode_entry()

    # ── Tagging ──────────────────────────────────────────────────────────────

    def _entry_key(self, entry) -> str:
        # The tab can open bgm.dat or movie.dat — prefix so entry #0 of one
        # never collides with entry #0 of the other.
        return f"{os.path.basename(self.bgm_path)}#{entry.index}"

    def _tag_key(self):
        return self._entry_key(self.bgm_entry) if self.bgm_entry else None

    def _on_tag_saved(self, key, refresh):
        self._update_row_inplace(key)

    def _decode_entry(self):
        if self.bgm_entry is None:
            return
        self.win.status.showMessage(self._t("bgm_rendering"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            pcm = bgm_fmt.bgm_entry_to_pcm(self.bgm, self.bgm_entry)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_generate", e=e))
            return
        finally:
            QApplication.restoreOverrideCursor()

        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            save_wav(pcm, path, self.bgm_entry.sample_rate,
                     channels=self.bgm_entry.channels)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise

        self._release_preview(keep=path)
        self.preview_wav = path
        self._want_play = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.btn_play.setText("\u25b6")
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        e = self.bgm_entry
        self.win.status.showMessage(self._t(
            "bgm_entry_info", index=e.index, sr=e.sample_rate,
            ch=e.channels, dur=e.duration_seconds))

    # ── Playback ─────────────────────────────────────────────────────────────

    def _release_preview(self, keep=None):
        old = self.preview_wav
        self.preview_wav = ""
        if old and old != keep:
            self._release_player()
            if os.path.exists(old):
                try:
                    os.unlink(old)
                except Exception:
                    pass

    def toggle_play(self):
        if not self.preview_wav:
            return
        super().toggle_play()

    # ── Export ───────────────────────────────────────────────────────────────

    def export_wav(self):
        if not self.preview_wav or not self.bgm_entry:
            return
        base = os.path.splitext(os.path.basename(self.bgm_path))[0]
        start = self.win.cfg.get("dir_bgm_export", "") or os.path.expanduser("~")
        suggested = os.path.join(
            start, f"{base}_entry{self.bgm_entry.index:03d}.wav")

        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_bgm_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        with open(self.preview_wav, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    def export_all(self):
        if not self.bgm:
            return
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_export_all"),
            self.win.cfg.get("dir_bgm_export", "") or os.path.expanduser("~"))
        if not folder:
            return
        self.win.cfg["dir_bgm_export"] = folder
        save_config(self.win.cfg)

        base = os.path.splitext(os.path.basename(self.bgm_path))[0]
        entries = self.bgm.entries
        dlg = QProgressDialog(self._t("bgm_exporting", n=0, total=len(entries)),
                              "Cancel", 0, len(entries), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)

        written = 0
        for n, entry in enumerate(entries, 1):
            if dlg.wasCanceled():
                break
            dlg.setValue(n - 1)
            dlg.setLabelText(self._t("bgm_exporting", n=n, total=len(entries)))
            QApplication.processEvents()
            try:
                pcm = bgm_fmt.bgm_entry_to_pcm(self.bgm, entry)
                name = os.path.join(
                    folder,
                    f"{base}_entry{entry.index:03d}_{entry.duration_seconds:.1f}s.wav")
                save_wav(pcm, name, entry.sample_rate, channels=entry.channels)
                written += 1
            except Exception:
                continue
        dlg.close()
        self.win.status.showMessage(self._t("bgm_exported_all", n=written))

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def cleanup(self):
        self._release_player()
        self._release_preview()
        self._destroy_playback()
