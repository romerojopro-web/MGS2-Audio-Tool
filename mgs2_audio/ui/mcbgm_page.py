#!/usr/bin/env python3
"""
mcbgm_page.py — The BGM (MC) tab: Master Collection's real scenario music.

Browses the 6 Unity AssetBundle tracks of the Master Collection install,
plays/exports them, and — the modding core — replaces a track's audio with a
user-chosen WAV, producing a bundle that substitutes the game's own file.
Each track shows its path relative to the game root so the modder knows
exactly which file to swap.
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

from ..formats import mcbgm
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin


class McBgmPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse, listen to, export and replace Master Collection BGM tracks."""

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.game_root = ""
        self.tracks = []
        self.track = None
        self.preview_wav = ""
        self.new_wav_path = ""
        self.new_wav_secs = 0.0
        self.last_generated = ""

        self._init_playback()
        self._init_tagging(lib.MCBGM_LIBRARY_FILENAME)
        self._build()
        self.reload_library()
        # Re-scan the last install automatically, off the constructor so the
        # window appears before the 7 bundle loads happen.
        saved = self.win.cfg.get("dir_mc_game", "")
        if saved and os.path.isdir(saved):
            QTimer.singleShot(50, lambda: self._scan(saved, quiet=True))

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        # Left: game folder + track list + tagging
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

        self.lbl_game = QLabel(); self.lbl_game.setObjectName("dim")
        self.lbl_game.setWordWrap(True)
        lay.addWidget(self.lbl_game)

        self.list_tracks = PlayOnSpaceList(self.toggle_play)
        self.list_tracks.currentItemChanged.connect(self._on_track_selected)
        lay.addWidget(self.list_tracks, 1)

        self.lbl_count = QLabel(); self.lbl_count.setObjectName("dim")
        lay.addWidget(self.lbl_count)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)
        lay.addLayout(self._build_tagging_panel())

        splitter.addWidget(panel)

        # Right: info, play, export, replace
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
        # The modding info: exact path of this file inside the game install.
        self.lbl_rel_path = QLabel(); self.lbl_rel_path.setObjectName("dim")
        self.lbl_rel_path.setWordWrap(True)
        self.lbl_rel_path.setTextInteractionFlags(
            Qt.TextInteractionFlag.TextSelectableByMouse)
        c.addWidget(self.lbl_rel_path)
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
        self.btn_generate = QPushButton(); self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self.generate_bundle)
        c.addWidget(self.btn_generate)
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
        """Rebuild the info line (and the file path under it) for the current
        state, so both follow a language change rather than staying frozen in
        whichever language was active when the game folder was scanned."""
        if not self.tracks:
            self.lbl_info.setText(self._t("mcbgm_hint"))
            self.lbl_rel_path.setText("")
            return
        if self.track is None:
            self.lbl_info.setText(self._t("mcbgm_select_hint"))
            self.lbl_rel_path.setText("")
            return
        t = self.track
        ch = "stereo" if t.channels == 2 else f"{t.channels}ch"
        self.lbl_info.setText(self._t("mcbgm_track_info", name=t.name,
                                      sr=t.frequency, ch=ch, dur=t.length_sec))
        self.lbl_rel_path.setText(self._t("mcbgm_rel_path", path=t.rel_path))

    def retranslate(self):
        self.lbl_list_title.setText(self._t("mcbgm_list_title"))
        self.btn_pick_game.setText(self._t("mcbgm_pick_game"))
        if not self.tracks:
            self.lbl_game.setText(self._t("mcbgm_no_game"))
        self._update_info()
        self.lbl_step1.setText(self._t("mcbgm_track_title"))
        self.lbl_step2.setText(self._t("mcbgm_listen_title"))
        self.lbl_step3.setText(self._t("mcbgm_replace_title"))
        self.btn_export.setText(self._t("mcbgm_export"))
        self.btn_pick_wav.setText(self._t("mcbgm_pick_wav"))
        self.btn_generate.setText(self._t("mcbgm_generate"))
        self.btn_install.setText(self._t("mcbgm_install"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading ──────────────────────────────────────────────────────────────

    def pick_game_folder(self):
        start = self.win.cfg.get("dir_mc_game", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_pick_mc_game"), start)
        if not folder:
            return
        self._scan(folder)

    def _scan(self, game_root: str, quiet: bool = False):
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            tracks = mcbgm.parse_catalog(game_root)
        except mcbgm.UnityPyMissing:
            QApplication.restoreOverrideCursor()
            self.lbl_info.setText(self._t("mcbgm_no_unitypy"))
            if not quiet:
                QMessageBox.critical(self, self._t("err_title"),
                                     self._t("mcbgm_no_unitypy"))
            return
        except Exception as e:
            QApplication.restoreOverrideCursor()
            if not quiet:
                QMessageBox.critical(self, self._t("err_title"),
                                     self._t("mcbgm_bad_folder", e=e))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        if not tracks:
            if not quiet:
                QMessageBox.information(self, self._t("err_title"),
                                        self._t("mcbgm_no_tracks"))
            return

        self.game_root = game_root
        self.tracks = tracks
        self.win.cfg["dir_mc_game"] = game_root
        save_config(self.win.cfg)
        self._reset_selection()

        self.lbl_game.setText(game_root)
        self._update_info()
        self._fill_list()
        self.win.status.showMessage(self._t("mcbgm_status_loaded",
                                            n=len(tracks)))

    def _fill_list(self):
        self.list_tracks.blockSignals(True)
        self.list_tracks.clear()
        for i, track in enumerate(self.tracks):
            item = QListWidgetItem(self._row_text(track))
            item.setData(Qt.ItemDataRole.UserRole, i)
            self.list_tracks.addItem(item)
        self.list_tracks.blockSignals(False)
        self._refresh_count()

    def _row_text(self, track) -> str:
        tag_entry = lib.get_entry(self._tag_library, self._track_key(track),
                                  self._tag_entry_defaults)
        marker = "✓" if tag_entry["done"] else "○"
        tag = (tag_entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return f"{marker} {track.name}   {track.length_sec:.0f} s{tagtxt}"

    def _update_row_inplace(self, key):
        for row in range(self.list_tracks.count()):
            it = self.list_tracks.item(row)
            i = it.data(Qt.ItemDataRole.UserRole)
            track = self.tracks[i]
            if self._track_key(track) == key:
                it.setText(self._row_text(track))
                return

    def _refresh_count(self):
        if self.tracks:
            total = sum(t.length_sec for t in self.tracks)
            self.lbl_count.setText(self._t("mcbgm_count", n=len(self.tracks),
                                           duration=f"{total:.0f}s"))
        else:
            self.lbl_count.setText("")

    def _reset_selection(self):
        self.track = None
        self.new_wav_path = ""
        self.last_generated = ""
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_pick_wav.setEnabled(False)
        self.btn_generate.setEnabled(False)
        self.btn_install.setEnabled(False)
        self.lbl_wav.setText("")
        self.lbl_result.setText("")
        self.lbl_rel_path.setText("")
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Selection and decoding ───────────────────────────────────────────────

    def _on_track_selected(self, current, previous):
        if current is None or not self.tracks:
            return
        i = current.data(Qt.ItemDataRole.UserRole)
        self.track = self.tracks[i]
        self._update_info()
        self.new_wav_path = ""
        self.last_generated = ""
        self.lbl_wav.setText("")
        self.lbl_result.setText("")
        self.btn_pick_wav.setEnabled(True)
        self.btn_generate.setEnabled(False)
        self.btn_install.setEnabled(False)
        self._fill_tag_fields()
        self._set_tag_fields_enabled(True)
        self._decode_track()

    def _decode_track(self):
        if self.track is None:
            return
        self.win.status.showMessage(self._t("mcbgm_rendering"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            mcbgm.extract_wav(self.track, path)
        except Exception as e:
            QApplication.restoreOverrideCursor()
            try:
                os.unlink(path)
            except OSError:
                pass
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

        self._release_preview(keep=path)
        self.preview_wav = path
        self._want_play = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.btn_play.setText("▶")
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.win.status.showMessage(self._t("mcbgm_ready", name=self.track.name))

    # ── Tagging ──────────────────────────────────────────────────────────────

    def _track_key(self, track) -> str:
        return os.path.basename(track.bundle_path)

    def _tag_key(self):
        return self._track_key(self.track) if self.track else None

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

    def export_wav(self):
        if not self.preview_wav or not self.track:
            return
        start = self.win.cfg.get("dir_mcbgm_export", "") or os.path.expanduser("~")
        safe = self.track.name.replace('"', "").replace("'", "")
        suggested = os.path.join(
            start, f"{safe.lower().replace(' ', '_')}.wav")
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_mcbgm_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        with open(self.preview_wav, "rb") as src, open(path, "wb") as dst:
            dst.write(src.read())
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    # ── Replacement (the modding core) ───────────────────────────────────────

    def pick_wav(self):
        if not self.track:
            return
        start = self.win.cfg.get("dir_mcbgm_dub", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_pick_wav"), start, self._t("filter_wav"))
        if not path:
            return
        try:
            _, ch, freq, secs = mcbgm.load_wav_pcm(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_wav_read", e=e))
            return

        self.win.cfg["dir_mcbgm_dub"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self.new_wav_path = path
        self.new_wav_secs = secs

        # The bundle is always conformed to the original's exact duration —
        # say what will happen, same wording as the SDX dub workflow.
        diff = secs - self.track.length_sec
        if abs(diff) < 0.05:
            note = self._t("wav_same")
        else:
            comp = self._t("wav_longer") if diff > 0 else self._t("wav_shorter")
            action = (self._t("wav_will_trim") if diff > 0
                      else self._t("wav_will_pad"))
            note = f"{abs(diff):.1f}s {comp} → {action}"
        self.lbl_wav.setText(self._t(
            "mcbgm_wav_info", name=os.path.basename(path), sr=freq, ch=ch,
            dur=secs, orig=self.track.length_sec) + f" · {note}")
        self.btn_generate.setEnabled(True)

    def generate_bundle(self):
        if not (self.track and self.new_wav_path):
            return
        original_name = os.path.basename(self.track.bundle_path)
        start = self.win.cfg.get("dir_mcbgm_save", "") or os.path.expanduser("~")
        out, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_save_bundle"),
            os.path.join(start, original_name), self._t("filter_bundle"))
        if not out:
            return
        if os.path.abspath(out) == os.path.abspath(self.track.bundle_path):
            # Overwriting the game's file directly bypasses the .bak safety —
            # that is what the install button is for.
            QMessageBox.warning(self, self._t("err_title"),
                                self._t("mcbgm_use_install"))
            return
        self.win.cfg["dir_mcbgm_save"] = os.path.dirname(out)
        save_config(self.win.cfg)

        self.btn_generate.setEnabled(False)
        self.win.status.showMessage(self._t("mcbgm_generating"))
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        QApplication.processEvents()
        tmp_dir = tempfile.mkdtemp(prefix="mcbgm_")
        try:
            # replace_audio names its output after the original bundle;
            # generate into a temp dir, then move to wherever the user chose.
            produced = mcbgm.replace_audio(self.track, self.new_wav_path, tmp_dir)
            if os.path.exists(out):
                os.unlink(out)
            shutil.move(produced, out)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_generate", e=e))
            self.win.status.showMessage(self._t("status_gen_failed"))
            return
        finally:
            QApplication.restoreOverrideCursor()
            self.btn_generate.setEnabled(True)
            shutil.rmtree(tmp_dir, ignore_errors=True)

        self.last_generated = out
        self.btn_install.setEnabled(True)
        self.lbl_result.setText(self._t("mcbgm_generated",
                                        path=out, rel=self.track.rel_path))
        self.win.status.showMessage(self._t("mcbgm_status_generated",
                                            name=os.path.basename(out)))

    def install_in_game(self):
        if not (self.track and self.last_generated
                and os.path.isfile(self.last_generated)):
            return
        target = self.track.bundle_path
        answer = QMessageBox.question(
            self, self._t("mcbgm_install_title"),
            self._t("mcbgm_install_confirm", rel=self.track.rel_path),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            bak = target + ".bak"
            if not os.path.exists(bak):
                shutil.copy2(target, bak)
            shutil.copy2(self.last_generated, target)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_generate", e=e))
            return
        # The Addressables catalog checks each bundle's CRC32 at load time —
        # without this the game black-screens on any modified bundle.
        try:
            mcbgm.patch_catalog(self.game_root, self.track,
                                new_size=os.path.getsize(target))
        except Exception as e:
            QMessageBox.warning(self, self._t("err_title"),
                                self._t("mcbgm_catalog_failed", e=e))
            return
        self.lbl_result.setText(self._t("mcbgm_installed", rel=self.track.rel_path))
        self.win.status.showMessage(self._t("mcbgm_installed",
                                            rel=self.track.rel_path))

    # ── Cleanup ──────────────────────────────────────────────────────────────

    def cleanup(self):
        self._release_player()
        self._release_preview()
        self._destroy_playback()
