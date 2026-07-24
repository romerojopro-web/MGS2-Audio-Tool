#!/usr/bin/env python3
"""
gsa_page.py — The Global Sound Archive tab.

`Misc/<lang>/BP_SE.DAT` holds the sounds the game keeps resident for the whole
session: item selection and pickup, using an item, interface blips, the
alert-phase alarm. They live in no `.sdx`, so until now nothing could reach
them — which is why players recognise them instantly but modders never found
them.

Point the tab at the game folder; it finds the archive, lists every sound, and
lets you listen, export to WAV, or replace one with your own recording. A
replacement keeps the sound's exact byte size, so every offset in the archive
stays valid and the game loads it without complaint.
"""

import os
import shutil
import tempfile

from PyQt6.QtCore import Qt, QTimer, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QHBoxLayout,
    QLabel, QListWidgetItem, QMessageBox, QPushButton,
    QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..formats import seo2
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin


class GsaPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse, listen to, export and replace the game's global sounds."""

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.archive_path = ""
        self.archive = None
        self.sound = None
        self.preview_wav = ""
        self.new_wav_path = ""

        self._init_playback()
        self._init_tagging(lib.GSA_LIBRARY_FILENAME)
        self._build()
        self.reload_library()

        saved = self.win.cfg.get("dir_gsa_game", "")
        if saved:
            QTimer.singleShot(50, lambda: self._load(saved, quiet=True))

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        panel = QFrame(); panel.setObjectName("library")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.lbl_list_title = QLabel(); self.lbl_list_title.setObjectName("panel")
        lay.addWidget(self.lbl_list_title)

        self.btn_pick_game = QPushButton(); self.btn_pick_game.setObjectName("small")
        self.btn_pick_game.clicked.connect(self.pick_game_folder)
        lay.addWidget(self.btn_pick_game)

        self.lbl_archive = QLabel(); self.lbl_archive.setObjectName("dim")
        self.lbl_archive.setWordWrap(True)
        lay.addWidget(self.lbl_archive)

        self.list_sounds = PlayOnSpaceList(self.toggle_play)
        self.list_sounds.currentItemChanged.connect(self._on_sound_selected)
        lay.addWidget(self.list_sounds, 1)

        self.lbl_count = QLabel(); self.lbl_count.setObjectName("dim")
        lay.addWidget(self.lbl_count)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        lay.addLayout(self._build_tagging_panel())

        splitter.addWidget(panel)

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
        self.btn_export = QPushButton(); self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_wav)
        c.addWidget(self.btn_export)
        self.btn_export_all = QPushButton(); self.btn_export_all.setEnabled(False)
        self.btn_export_all.clicked.connect(self.export_all)
        c.addWidget(self.btn_export_all)
        root.addWidget(card)

        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step3 = QLabel(); self.lbl_step3.setObjectName("step")
        c.addWidget(self.lbl_step3)
        self.btn_pick_wav = QPushButton(); self.btn_pick_wav.setEnabled(False)
        self.btn_pick_wav.clicked.connect(self.pick_wav)
        c.addWidget(self.btn_pick_wav)
        self.lbl_wav = QLabel(); self.lbl_wav.setObjectName("dim")
        self.lbl_wav.setWordWrap(True)
        c.addWidget(self.lbl_wav)
        self.btn_install = QPushButton(); self.btn_install.setEnabled(False)
        self.btn_install.clicked.connect(self.install_in_game)
        c.addWidget(self.btn_install)
        self.lbl_result = QLabel(); self.lbl_result.setObjectName("dim")
        self.lbl_result.setWordWrap(True)
        self.lbl_result.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        c.addWidget(self.lbl_result)
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
        """Rebuild the info line for the current state.

        Called on selection *and* on retranslate, so the line follows a language
        change instead of staying frozen in whichever language was active when
        the archive was opened.
        """
        if self.sound is None:
            self.lbl_info.setText(self._t("gsa_select_hint"))
            return
        s = self.sound
        self.lbl_info.setText(self._t(
            "gsa_sound_info", index=s.index, id=f"{s.sound_id:#05x}",
            ch=("stereo" if s.channels == 2 else "mono"),
            dur=s.duration_seconds, bytes=f"{s.total_bytes:,}"))

    def retranslate(self):
        self.lbl_list_title.setText(self._t("gsa_list_title"))
        self.btn_pick_game.setText(self._t("gsa_pick_game"))
        if not self.archive:
            self.lbl_archive.setText(self._t("gsa_no_archive"))
        self._update_info()
        self.lbl_hint.setText(self._t("gsa_hint"))
        self.lbl_step1.setText(self._t("gsa_open_title"))
        self.lbl_step2.setText(self._t("gsa_listen_title"))
        self.lbl_step3.setText(self._t("gsa_replace_title"))
        self.btn_export.setText(self._t("gsa_export"))
        self.btn_export_all.setText(self._t("gsa_export_all"))
        self.btn_pick_wav.setText(self._t("gsa_pick_wav"))
        self.btn_install.setText(self._t("gsa_install"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading ──────────────────────────────────────────────────────────────

    def pick_game_folder(self):
        start = self.win.cfg.get("dir_gsa_game", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("gsa_pick_game"), start)
        if folder:
            self._load(folder)

    def _load(self, game_root: str, quiet: bool = False):
        path = seo2.find_bp_se(game_root)
        if not path:
            if not quiet:
                QMessageBox.information(self, self._t("err_title"),
                                        self._t("gsa_not_found"))
            return
        try:
            archive = seo2.parse_seo2(path)
        except Exception as e:
            if not quiet:
                QMessageBox.critical(self, self._t("err_title"),
                                     self._t("err_read", e=e))
            return
        if not archive.has_audio:
            if not quiet:
                QMessageBox.information(self, self._t("err_title"),
                                        self._t("gsa_not_found"))
            return

        self.archive = archive
        self.archive_path = path
        self.win.cfg["dir_gsa_game"] = game_root
        save_config(self.win.cfg)
        self._reset_selection()

        self.lbl_archive.setText(path)
        self._update_info()
        self.btn_export_all.setEnabled(True)
        self._fill_list()
        self.win.status.showMessage(
            self._t("gsa_status_loaded", n=len(archive.sounds)))

    def _fill_list(self):
        if not self.archive:
            return
        self.list_sounds.blockSignals(True)
        self.list_sounds.clear()
        for s in self.archive.sounds:
            item = QListWidgetItem(self._row_text(s))
            item.setData(Qt.ItemDataRole.UserRole, s.index)
            self.list_sounds.addItem(item)
        self.list_sounds.blockSignals(False)
        self._refresh_count()

    def _row_text(self, sound) -> str:
        entry = lib.get_entry(self._tag_library, self._sound_key(sound),
                              self._tag_entry_defaults)
        marker = "✓" if entry["done"] else "○"
        tag = (entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        ch = "st" if sound.channels == 2 else "mo"
        return (f"{marker} #{sound.index:>3}  id {sound.sound_id:#05x}  {ch}  "
                f"{sound.duration_seconds:5.1f}s{tagtxt}")

    def _update_row_inplace(self, key):
        for row in range(self.list_sounds.count()):
            it = self.list_sounds.item(row)
            i = it.data(Qt.ItemDataRole.UserRole)
            sound = self._sound_by_index(i)
            if sound is not None and self._sound_key(sound) == key:
                it.setText(self._row_text(sound))
                return

    def _sound_by_index(self, index):
        for s in self.archive.sounds:
            if s.index == index:
                return s
        return None

    def _refresh_count(self):
        if self.archive and self.archive.sounds:
            total = sum(s.duration_seconds for s in self.archive.sounds)
            self.lbl_count.setText(self._t("gsa_count",
                                           n=len(self.archive.sounds),
                                           duration=f"{total:.0f}s"))
        else:
            self.lbl_count.setText("")

    def _reset_selection(self):
        self.sound = None
        self.new_wav_path = ""
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_pick_wav.setEnabled(False)
        self.btn_install.setEnabled(False)
        self.lbl_wav.setText("")
        self.lbl_result.setText("")
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Selection ────────────────────────────────────────────────────────────

    def _on_sound_selected(self, current, previous):
        if current is None or not self.archive:
            return
        self.sound = self._sound_by_index(current.data(Qt.ItemDataRole.UserRole))
        if self.sound is None:
            return
        self._update_info()
        self.new_wav_path = ""
        self.lbl_wav.setText("")
        self.lbl_result.setText("")
        self.btn_pick_wav.setEnabled(True)
        self.btn_install.setEnabled(False)
        self._fill_tag_fields()
        self._set_tag_fields_enabled(True)
        self._decode_sound()

    def _decode_sound(self):
        if self.sound is None:
            return
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            seo2.sound_to_wav(self.archive, self.sound, path)
        except Exception as e:
            try:
                os.unlink(path)
            except OSError:
                pass
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return

        self._release_preview(keep=path)
        self.preview_wav = path
        self._want_play = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.btn_play.setText("▶")
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)

    # ── Tagging ──────────────────────────────────────────────────────────────

    def _sound_key(self, sound) -> str:
        return f"{sound.index}"

    def _tag_key(self):
        return self._sound_key(self.sound) if self.sound else None

    def _on_tag_saved(self, key, refresh):
        self._update_row_inplace(key)

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

    def _default_name(self, sound) -> str:
        ch = 2 if sound.channels == 2 else 1
        return (f"gsa_{sound.index:03d}_id{sound.sound_id:02X}"
                f"_{ch}ch_{sound.duration_seconds:04.1f}s.wav")

    def export_wav(self):
        if not self.preview_wav or not self.sound:
            return
        start = self.win.cfg.get("dir_gsa_export", "") or os.path.expanduser("~")
        suggested = os.path.join(start, self._default_name(self.sound))
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_gsa_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        shutil.copyfile(self.preview_wav, path)
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    def export_all(self):
        if not self.archive:
            return
        start = self.win.cfg.get("dir_gsa_export", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("gsa_export_all"), start)
        if not folder:
            return
        self.win.cfg["dir_gsa_export"] = folder
        save_config(self.win.cfg)
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        written = 0
        try:
            for s in self.archive.sounds:
                seo2.sound_to_wav(self.archive, s,
                                  os.path.join(folder, self._default_name(s)))
                written += 1
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_read", e=e))
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self.win.status.showMessage(self._t("gsa_exported_all", n=written))

    # ── Replacement ──────────────────────────────────────────────────────────

    def pick_wav(self):
        if not self.sound:
            return
        start = self.win.cfg.get("dir_gsa_dub", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_pick_wav"), start, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_gsa_dub"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self.new_wav_path = path
        self.lbl_wav.setText(os.path.basename(path))
        self.btn_install.setEnabled(True)

    def install_in_game(self):
        """Rewrite the archive in place, backing it up the first time."""
        if not self.sound or not self.new_wav_path:
            return
        if QMessageBox.question(
                self, self._t("gsa_install"),
                self._t("gsa_confirm_install",
                        path=self.archive_path)) != QMessageBox.StandardButton.Yes:
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            pcm = seo2.load_wav_mono(self.new_wav_path)
            raw = seo2.replace_sound(self.archive, self.sound, pcm)
            bak = self.archive_path + ".bak"
            if not os.path.exists(bak):
                shutil.copyfile(self.archive_path, bak)
            seo2.save_seo2(raw, self.archive_path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_write", e=e))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        # Re-read so the tab reflects what is now on disk, and re-bind the
        # selection to the reloaded archive — keeping the old object would leave
        # us decoding through a stale handle.
        try:
            self.archive = seo2.parse_seo2(self.archive_path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_read", e=e))
            return
        self.sound = self._sound_by_index(self.sound.index)
        self.lbl_result.setText(self._t("gsa_installed", path=self.archive_path))
        self.new_wav_path = ""
        self.lbl_wav.setText("")
        self.btn_install.setEnabled(False)
        self._decode_sound()
