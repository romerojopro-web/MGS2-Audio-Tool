#!/usr/bin/env python3
"""
vox_page.py — The VOX tab: browse, listen and export `vox.dat` voice audio
from MGS2 Substance (2003).

vox.dat is a PAC-wrapped archive of PS-ADPCM blocks (44 100 Hz mono).
Each block is one voice clip.  The layout mirrors the BGM tab: list on the
left, player + export on the right.
"""

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidgetItem, QMessageBox, QProgressDialog, QPushButton,
    QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..formats import sdt as sdt_fmt
from ..codec.psadpcm import decode_psadpcm
from ..codec.wav import save_wav
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin


class VoxPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse a vox.dat archive, listen to individual blocks, export them."""

    def __init__(self, window, mode="substance"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.sdt = None
        self.vox_path = ""
        self.block_index = -1
        self.preview_wav = ""

        self._init_playback()
        self._init_tagging(lib.VOX_LIBRARY_FILENAME)
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

        # Left: list of blocks
        panel = QFrame(); panel.setObjectName("library")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.lbl_list_title = QLabel(); self.lbl_list_title.setObjectName("panel")
        lay.addWidget(self.lbl_list_title)

        self.btn_open = QPushButton(); self.btn_open.setObjectName("small")
        self.btn_open.clicked.connect(self.open_vox)
        lay.addWidget(self.btn_open)

        self.lbl_archive = QLabel(); self.lbl_archive.setObjectName("dim")
        self.lbl_archive.setWordWrap(True)
        lay.addWidget(self.lbl_archive)

        self.list_blocks = PlayOnSpaceList(self.toggle_play)
        self.list_blocks.currentItemChanged.connect(self._on_block_selected)
        lay.addWidget(self.list_blocks, 1)

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
        if not self.sdt or self.block_index is None:
            self.lbl_info.setText(self._t("vox_select_hint"))
            return
        block = self.sdt.blocks[self.block_index]
        dur = (block.data_size // 16) * 28 / self.sdt.sample_rate
        self.lbl_info.setText(self._t(
            "vox_block_info", index=self.block_index,
            sr=self.sdt.sample_rate, dur=dur))

    def retranslate(self):
        self.lbl_list_title.setText(self._t("vox_list_title"))
        self.btn_open.setText(self._t("vox_browse"))
        if not self.sdt:
            self.lbl_archive.setText(self._t("vox_no_file"))
        self._update_info()
        self.lbl_step1.setText(self._t("vox_open_title"))
        self.lbl_hint.setText(self._t("vox_hint"))
        self.lbl_step2.setText(self._t("vox_listen_title"))
        self.lbl_step3.setText(self._t("vox_export_title"))
        self.btn_export.setText(self._t("vox_export"))
        self.btn_export_all.setText(self._t("vox_export_all"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading ──────────────────────────────────────────────────────────────

    def open_vox(self):
        start = self.win.cfg.get("dir_vox", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_vox"), start,
            self._t("filter_dat"))
        if not path:
            return

        try:
            sdt = sdt_fmt.parse_sdt(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return

        if len(sdt.blocks) == 0:
            QMessageBox.information(self, self._t("err_title"),
                                    self._t("vox_no_blocks"))
            return

        if not sdt.supported:
            QMessageBox.information(self, self._t("err_title"),
                                    self._t("warn_unsupported"))
            return

        self.sdt = sdt
        self.vox_path = path
        self.win.cfg["dir_vox"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self._reset_selection()

        self.lbl_archive.setText(path)
        self.lbl_info.setText(self._t("vox_select_hint"))
        self.lbl_hint.setText(self._t("vox_hint"))
        self.btn_export_all.setEnabled(True)
        self._fill_list()
        self.win.status.showMessage(self._t(
            "vox_status_loaded", name=os.path.basename(path),
            n=len(sdt.blocks)))

    def _fill_list(self):
        self.list_blocks.blockSignals(True)
        self.list_blocks.clear()
        if self.sdt:
            for i, block in enumerate(self.sdt.blocks):
                item = QListWidgetItem(self._row_text(i))
                item.setData(Qt.ItemDataRole.UserRole, i)
                self.list_blocks.addItem(item)
        self.list_blocks.blockSignals(False)
        self._refresh_count()

    def _row_text(self, i) -> str:
        block = self.sdt.blocks[i]
        dur = (block.data_size // 16) * 28 / self.sdt.sample_rate
        entry = lib.get_entry(self._tag_library, str(i), self._tag_entry_defaults)
        marker = "✓" if entry["done"] else "○"
        tag = (entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return (f"{marker} #{i:<5}  {self.sdt.sample_rate} Hz mono  "
                f"{dur:.2f} s{tagtxt}")

    def _update_row_inplace(self, key):
        i = int(key)
        for row in range(self.list_blocks.count()):
            it = self.list_blocks.item(row)
            if it.data(Qt.ItemDataRole.UserRole) == i:
                it.setText(self._row_text(i))
                return

    def _refresh_count(self):
        if self.sdt:
            total = len(self.sdt.blocks)
            total_dur = self.sdt.duration_seconds
            self.lbl_count.setText(self._t(
                "vox_count", n=total,
                duration=f"{total_dur:.0f}s"))
        else:
            self.lbl_count.setText("")

    def _reset_selection(self):
        self.block_index = -1
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Tagging ──────────────────────────────────────────────────────────────

    def _tag_key(self):
        return str(self.block_index) if self.sdt and self.block_index >= 0 else None

    def _on_tag_saved(self, key, refresh):
        self._update_row_inplace(key)

    # ── Selection and decoding ───────────────────────────────────────────────

    def _on_block_selected(self, current, previous):
        if current is None or not self.sdt:
            return
        index = current.data(Qt.ItemDataRole.UserRole)
        if index < 0 or index >= len(self.sdt.blocks):
            return
        self.block_index = index
        self._update_info()
        self._fill_tag_fields()
        self._set_tag_fields_enabled(True)
        self._decode_block()

    def _decode_block(self):
        if self.block_index < 0 or not self.sdt:
            return
        self.win.status.showMessage(self._t("vox_rendering"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        try:
            block = self.sdt.blocks[self.block_index]
            raw_adpcm = self.sdt.raw[
                block.data_offset:block.data_offset + block.data_size]
            pcm = decode_psadpcm(raw_adpcm)
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
            save_wav(pcm, path, self.sdt.sample_rate, channels=1)
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
        dur = (self.sdt.blocks[self.block_index].data_size // 16) * 28 / self.sdt.sample_rate
        self.win.status.showMessage(self._t(
            "vox_block_info", index=self.block_index,
            sr=self.sdt.sample_rate, dur=dur))

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
        if self.block_index < 0 or not self.sdt:
            return
        base = os.path.splitext(os.path.basename(self.vox_path))[0]
        start = self.win.cfg.get("dir_vox_export", "") or os.path.expanduser("~")
        suggested = os.path.join(
            start, f"{base}_block{self.block_index:05d}.wav")

        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_vox_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        with open(self.preview_wav, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    def export_all(self):
        if not self.sdt:
            return
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_export_all"),
            self.win.cfg.get("dir_vox_export", "") or os.path.expanduser("~"))
        if not folder:
            return
        self.win.cfg["dir_vox_export"] = folder
        save_config(self.win.cfg)

        base = os.path.splitext(os.path.basename(self.vox_path))[0]
        blocks = self.sdt.blocks
        dlg = QProgressDialog(self._t("vox_exporting", n=0, total=len(blocks)),
                              "Cancel", 0, len(blocks), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)

        written = 0
        for n, block in enumerate(blocks, 1):
            if dlg.wasCanceled():
                break
            dlg.setValue(n - 1)
            dlg.setLabelText(self._t("vox_exporting", n=n, total=len(blocks)))
            QApplication.processEvents()
            try:
                raw_adpcm = self.sdt.raw[
                    block.data_offset:block.data_offset + block.data_size]
                pcm = decode_psadpcm(raw_adpcm)
                dur = (block.data_size // 16) * 28 / self.sdt.sample_rate
                name = os.path.join(
                    folder,
                    f"{base}_block{n-1:05d}_{dur:.2f}s.wav")
                save_wav(pcm, name, self.sdt.sample_rate, channels=1)
                written += 1
            except Exception:
                continue
        dlg.close()
        self.win.status.showMessage(self._t("vox_exported_all", n=written))

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def cleanup(self):
        self._release_player()
        self._release_preview()
        self._destroy_playback()
