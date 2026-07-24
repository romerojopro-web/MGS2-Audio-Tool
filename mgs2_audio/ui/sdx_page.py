#!/usr/bin/env python3
"""
sdx_page.py — The SDX tab: stage sound-effect banks.

Two modes share one list:

* **bank** — one `.sdx` opened on its own, its samples listed;
* **scan** — the whole game indexed, identical sounds grouped, so an edit can
  reach every bank that shares the sound.

Tagging only exists in scan mode: outside it there is no sound key to tag.
"""

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame,
    QHBoxLayout, QLabel, QListWidgetItem, QMessageBox,
    QProgressDialog, QPushButton, QSlider, QSplitter, QVBoxLayout, QWidget,
)

from ..codec.wav import save_wav
from ..formats import sdx
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, TaggingMixin


class SDXPage(PlaybackMixin, TaggingMixin, QWidget):
    """Browse a .sdx sound bank: list its samples, play them, replace one.

    Mirrors the SDT workflow — list on the left, four steps on the right — but
    the unit of work is a *sample inside a bank* rather than a whole file.
    """

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window                 # to reach _t(), status bar, config
        self.game_mode = mode             # "mc" or "substance" — the game version
        self.mode = "bank"                # "bank" (one .sdx) or "scan" (whole folder)
        self.bank = None                  # sdx.SDXFile
        self.bank_path = ""
        self.sample = None                # selected sdx.SDXSample
        self.groups = []                  # sdx.SoundGroup list, in scan mode
        self.group = None                 # selected group
        self.new_wav_path = ""
        self.new_pcm = None
        self.preview_wav = ""

        self._init_playback()
        self._init_tagging(self._sdx_library_filename(), lib.SDX_ENTRY_DEFAULTS)

        self._build()

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        # Left: the bank's sample list
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

        self.btn_scan = QPushButton(); self.btn_scan.setObjectName("small")
        self.btn_scan.clicked.connect(self.scan_stage_folder)
        lay.addWidget(self.btn_scan)
        if self.game_mode == "substance":
            self.btn_scan.hide()

        self.lbl_bank = QLabel(); self.lbl_bank.setObjectName("dim")
        self.lbl_bank.setWordWrap(True)
        lay.addWidget(self.lbl_bank)

        self.list_samples = PlayOnSpaceList(self.toggle_play)
        self.list_samples.currentItemChanged.connect(self._on_sample_selected)
        lay.addWidget(self.list_samples, 1)

        self.lbl_count = QLabel(); self.lbl_count.setObjectName("dim")
        lay.addWidget(self.lbl_count)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # Tagging a sound tags every bank that shares it: entries are keyed by
        # the sound's content hash, not by a file path.
        lay.addLayout(self._build_tagging_panel())

        splitter.addWidget(panel)

        # Right: listen / replace / generate
        right = QWidget()
        root = QVBoxLayout(right)
        root.setContentsMargins(16, 4, 4, 8)
        root.setSpacing(14)

        # Step 1 — the loaded bank
        card = QFrame(); card.setObjectName("card")
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step1 = QLabel(); self.lbl_step1.setObjectName("step")
        c.addWidget(self.lbl_step1)
        self.lbl_info = QLabel(); self.lbl_info.setObjectName("body")
        self.lbl_info.setWordWrap(True)
        c.addWidget(self.lbl_info)
        root.addWidget(card)

        # Step 2 — playback
        card = QFrame(); card.setObjectName("card")
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

        # Step 3 — pick replacement audio
        card = QFrame(); card.setObjectName("card")
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step3 = QLabel(); self.lbl_step3.setObjectName("step")
        c.addWidget(self.lbl_step3)
        self.lbl_hint = QLabel(); self.lbl_hint.setObjectName("dim")
        self.lbl_hint.setWordWrap(True)
        c.addWidget(self.lbl_hint)
        row = QHBoxLayout()
        self.btn_pick_wav = QPushButton(); self.btn_pick_wav.setEnabled(False)
        self.btn_pick_wav.clicked.connect(self.pick_wav)
        row.addWidget(self.btn_pick_wav)
        self.lbl_wav = QLabel(); self.lbl_wav.setObjectName("value")
        row.addWidget(self.lbl_wav, 1)
        c.addLayout(row)
        self.lbl_wav_info = QLabel(); self.lbl_wav_info.setObjectName("dim")
        c.addWidget(self.lbl_wav_info)
        root.addWidget(card)

        # Step 4 — generate
        card = QFrame(); card.setObjectName("card")
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step4 = QLabel(); self.lbl_step4.setObjectName("step")
        c.addWidget(self.lbl_step4)
        self.btn_generate = QPushButton(); self.btn_generate.setObjectName("primary")
        self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self.generate)
        c.addWidget(self.btn_generate)
        self.lbl_result = QLabel(); self.lbl_result.setObjectName("value")
        self.lbl_result.setWordWrap(True)
        c.addWidget(self.lbl_result)
        root.addWidget(card)

        root.addStretch()
        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])

    # ── Translation ──────────────────────────────────────────────────────────

    def _update_info(self):
        """Rebuild the info line for the current state, so it follows a language
        change instead of staying in whichever language opened the bank."""
        if self.mode == "scan":
            g = self.group
            if g is None:
                self.lbl_info.setText(self._t("sdx_select_hint"))
                return
            self.lbl_info.setText(
                f"{g.key} · {g.duration_seconds:.2f} {self._t('unit_seconds')} · "
                f"{g.size:,} {self._t('unit_bytes')} · "
                f"{self._t('sdx_group_count', n=g.count)}")
            return
        s = self.sample
        if not self.bank or s is None:
            self.lbl_info.setText(self._t("sdx_select_hint"))
            return
        self.lbl_info.setText(
            f"{self._t('sdx_info_samples')} #{s.index} · "
            f"{s.duration_seconds:.2f} {self._t('unit_seconds')} · "
            f"{s.size:,} {self._t('unit_bytes')} · "
            f"{self.bank.sample_rate} Hz {self._t('unit_mono')}")

    def retranslate(self):
        self.lbl_list_title.setText(self._t("sdx_list_title"))
        self.btn_open.setText(self._t("sdx_browse"))
        self.btn_scan.setText(self._t("sdx_scan"))
        if not self.bank and self.mode != "scan":
            self.lbl_bank.setText(self._t("sdx_no_file"))
        self._update_info()
        self.lbl_step1.setText(self._t("sdx_open_title"))
        self.lbl_step2.setText(self._t("sdx_listen_title"))
        self.btn_export.setText(self._t("sdx_export"))
        self.lbl_step3.setText(self._t("sdx_replace_title"))
        self.lbl_hint.setText(self._t("sdx_hint"))
        self.btn_pick_wav.setText(self._t("sdx_pick_wav"))
        if not self.new_wav_path:
            self.lbl_wav.setText(self._t("sdx_no_wav"))
        self.lbl_step4.setText(self._t("sdx_gen_title"))
        self.btn_generate.setText(
            self._t("sdx_replace_all") if self.mode == "scan"
            else self._t("sdx_generate"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Bank loading ─────────────────────────────────────────────────────────

    def open_bank(self):
        start = self.win.cfg.get("dir_sdx", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_sdx"), start, self._t("filter_sdx"))
        if not path:
            return
        try:
            self.bank = sdx.parse_sdx(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_read", e=e))
            return

        self.bank_path = path
        self.mode = "bank"
        self.groups = []
        self.win.cfg["dir_sdx"] = os.path.dirname(path)
        save_config(self.win.cfg)

        self.lbl_bank.setText(path)
        self._reset_sample_state()
        self._fill_list()

        if not self.bank.has_audio:
            self.lbl_info.setText(self._t("sdx_warn_empty"))
            self.win.status.showMessage(self._t("sdx_warn_empty"))
            return

        self.lbl_info.setText(self._t("sdx_select_hint"))
        self.win.status.showMessage(self._t(
            "sdx_status_loaded", name=os.path.basename(path), n=len(self.bank.samples)))

    def _fill_list(self):
        if not self.bank:
            return
        self.list_samples.blockSignals(True)
        self.list_samples.clear()
        for s in self.bank.samples:
            item = QListWidgetItem(f"#{s.index:>3}   {s.duration_seconds:5.2f}s   {s.size:>8,} o")
            item.setData(Qt.ItemDataRole.UserRole, s.index)
            self.list_samples.addItem(item)
        self.list_samples.blockSignals(False)
        self._refresh_count()

    # ── Scan a whole stage folder ────────────────────────────────────────────

    def scan_stage_folder(self):
        """Index every .sdx of the game and group identical sounds.

        The user points at their MGS2 installation; the stage folder (the only
        one holding .sdx banks) is resolved from there. The same effect — rain,
        footsteps… — is duplicated across dozens of stage banks, so editing a
        single bank often has no audible effect in game. Scanning shows how many
        banks share each sound, and lets one edit reach all of them at once.
        """
        start = self.win.cfg.get("dir_game", "") or os.path.expanduser("~")
        chosen = QFileDialog.getExistingDirectory(
            self, self._t("dlg_pick_stage"), start)
        if not chosen:
            return

        folder = sdx.find_stage_folder(chosen)
        if folder is None:
            QMessageBox.warning(self, self._t("err_title"), self._t("sdx_no_stage"))
            return

        paths = sdx.find_banks(folder)
        self.win.cfg["dir_game"] = chosen
        save_config(self.win.cfg)

        dlg = QProgressDialog(self._t("sdx_scanning", n=0, total=len(paths)),
                              "Cancel", 0, len(paths), self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        cancelled = {"flag": False}

        def progress(n, total, path):
            if dlg.wasCanceled():
                cancelled["flag"] = True
            dlg.setValue(n)
            dlg.setLabelText(self._t("sdx_scanning", n=n, total=total))
            QApplication.processEvents()
            return cancelled["flag"]

        self.groups = sdx.scan_banks(paths, progress)
        dlg.close()
        if cancelled["flag"]:
            self.groups = []
            return

        self.mode = "scan"
        self.bank = None
        self.bank_path = folder
        self.lbl_bank.setText(self._t("sdx_stage_found", path=folder))
        self._reset_sample_state()
        self.reload_library()
        self._fill_group_list()

        self.lbl_info.setText(self._t("sdx_select_hint"))
        self.win.status.showMessage(self._t(
            "sdx_scan_done", banks=len(paths), sounds=len(self.groups)))

    def _fill_group_list(self):
        self.list_samples.blockSignals(True)
        self.list_samples.clear()
        for g in self.groups:
            item = QListWidgetItem(self._group_row_text(g))
            item.setData(Qt.ItemDataRole.UserRole, g.key)
            self.list_samples.addItem(item)
        self.list_samples.blockSignals(False)
        self._refresh_count()

    def _refresh_count(self):
        if self.mode == "scan":
            if self.groups:
                c = lib.counts(self._tag_library, [g.key for g in self.groups],
                               lib.SDX_ENTRY_DEFAULTS)
                self.lbl_count.setText(self._t(
                    "lib_count", total=c["total"], done=c["done"], todo=c["todo"]))
            else:
                self.lbl_count.setText("")
            return
        if not self.bank or not self.bank.has_audio:
            self.lbl_count.setText("")
            return
        total = sum(s.size for s in self.bank.samples)
        self.lbl_count.setText(self._t(
            "sdx_count", n=len(self.bank.samples), bytes=f"{total:,}"))

    def _reset_sample_state(self):
        self.sample = None
        self.group = None
        self.new_wav_path = ""
        self.new_pcm = None
        self.lbl_wav.setText(self._t("sdx_no_wav"))
        self.lbl_wav_info.setText("")
        self.lbl_result.setText("")
        self.btn_play.setEnabled(False)
        self.slider.setEnabled(False)
        self.btn_export.setEnabled(False)
        self.btn_pick_wav.setEnabled(False)
        self.btn_generate.setEnabled(False)
        self.btn_generate.setText(
            self._t("sdx_replace_all") if self.mode == "scan"
            else self._t("sdx_generate"))
        self._set_tag_fields_enabled(False)
        self._release_preview()

    # ── Sample selection ─────────────────────────────────────────────────────

    def _on_sample_selected(self, current, previous):
        if current is None:
            return
        self.new_wav_path = ""
        self.new_pcm = None
        self.lbl_wav.setText(self._t("sdx_no_wav"))
        self.lbl_wav_info.setText("")
        self.lbl_result.setText("")
        self.btn_generate.setEnabled(False)

        if self.mode == "scan":
            key = current.data(Qt.ItemDataRole.UserRole)
            self.group = next((g for g in self.groups if g.key == key), None)
            if not self.group:
                return
            g = self.group
            self._update_info()
            self._prepare_preview_pcm(sdx.read_group_sample(g))
            self._fill_tag_fields()
            self._set_tag_fields_enabled(True)
            self.win.status.showMessage(self._t("sdx_group_count", n=g.count))
        else:
            if not self.bank:
                return
            idx = current.data(Qt.ItemDataRole.UserRole)
            self.sample = self.bank.samples[idx]
            s = self.sample
            self._update_info()
            self._prepare_preview_pcm(sdx.decode_sample(self.bank, s))
            self.win.status.showMessage(self._t(
                "sdx_status_sample", i=s.index, dur=s.duration_seconds,
                size=f"{s.size:,}"))

        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_pick_wav.setEnabled(True)

    def _current_duration(self) -> float:
        if self.mode == "scan":
            return self.group.duration_seconds if self.group else 0.0
        return self.sample.duration_seconds if self.sample else 0.0

    # ── Tagging (scan mode only: sounds are identified by their hash) ────────
    # Load/save/panel logic lives in TaggingMixin; this page only supplies the
    # key, the extra cached fields, and how to redraw a row after a save.

    def _sdx_library_filename(self) -> str:
        """MC and Substance banks are unrelated — keep their tags in separate
        files so a shared db_folder doesn't co-mingle the two games' sounds."""
        if self.game_mode == "substance":
            return lib.SUBSTANCE_SDX_LIBRARY_FILENAME
        return lib.SDX_LIBRARY_FILENAME

    def _tag_key(self):
        return self.group.key if self.mode == "scan" and self.group else None

    def _tag_extra_fields(self) -> dict:
        if not self.group:
            return {}
        g = self.group
        return {"duration": g.duration_seconds, "size": g.size, "banks": g.count}

    def _on_tag_saved(self, key, refresh):
        if refresh:
            self._fill_group_list()
            self._select_key(key)
        else:
            self._update_row_inplace(key)

    def _select_key(self, key):
        for i in range(self.list_samples.count()):
            it = self.list_samples.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == key:
                self.list_samples.setCurrentItem(it)
                return

    def _group_row_text(self, g) -> str:
        entry = lib.get_entry(self._tag_library, g.key, lib.SDX_ENTRY_DEFAULTS)
        marker = "✓" if entry["done"] else "○"
        tag = (entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return f"{marker} ×{g.count:<3} {g.duration_seconds:5.2f}s{tagtxt}"

    def _update_row_inplace(self, key):
        for i in range(self.list_samples.count()):
            it = self.list_samples.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == key:
                g = next((x for x in self.groups if x.key == key), None)
                if g:
                    it.setText(self._group_row_text(g))
                return

    # ── Playback ─────────────────────────────────────────────────────────────

    def _release_preview(self):
        old = self.preview_wav
        self.preview_wav = ""
        if old and os.path.exists(old):
            self._release_player()
            try:
                os.unlink(old)
            except Exception:
                pass

    def _prepare_preview_pcm(self, pcm):
        """Write a decoded sound to a temp WAV and hand it to the player."""
        self._release_preview()
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        try:
            save_wav(pcm, path, sdx.SDX_SAMPLE_RATE, channels=1)
        except Exception:
            try:
                os.unlink(path)
            except OSError:
                pass
            raise
        self.preview_wav = path
        self._want_play = False
        self.player.setSource(QUrl.fromLocalFile(path))
        self.btn_play.setText("▶")

    # ── Export ───────────────────────────────────────────────────────────────

    def export_wav(self):
        if self.mode == "scan":
            if not self.group:
                return
            base = self.group.key
            pcm = sdx.read_group_sample(self.group)
        else:
            if not self.sample:
                return
            base = (os.path.splitext(os.path.basename(self.bank_path))[0]
                    + f"_{self.sample.index:03d}")
            pcm = sdx.decode_sample(self.bank, self.sample)

        start = self.win.cfg.get("dir_sdx_export", "") or os.path.expanduser("~")
        suggested = os.path.join(start, f"{base}.wav")
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"), suggested, self._t("filter_wav"))
        if not path:
            return
        self.win.cfg["dir_sdx_export"] = os.path.dirname(path)
        save_config(self.win.cfg)
        save_wav(pcm, path, sdx.SDX_SAMPLE_RATE, channels=1)
        self.win.status.showMessage(self._t(
            "status_exported", name=os.path.basename(path), n=len(pcm)))
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    # ── Replacement ──────────────────────────────────────────────────────────

    def pick_wav(self):
        start = self.win.cfg.get("dir_sdx_dub", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_pick_wav"), start, self._t("filter_wav"))
        if not path:
            return
        try:
            pcm = sdx.load_wav_mono(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), self._t("err_wav_read", e=e))
            return

        self.win.cfg["dir_sdx_dub"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self.new_wav_path = path
        self.new_pcm = pcm
        self.lbl_wav.setText(os.path.basename(path))

        incoming = len(pcm) / sdx.SDX_SAMPLE_RATE
        original = self._current_duration()
        diff = incoming - original
        if abs(diff) < 0.01:
            note = self._t("wav_same")
        else:
            longer = diff > 0
            comp = self._t("wav_longer") if longer else self._t("wav_shorter")
            action = self._t("wav_will_trim") if longer else self._t("wav_will_pad")
            note = f"{abs(diff):.2f}s {comp} → {action}"
        self.lbl_wav_info.setText(
            f"{self._t('wav_duration')} : {incoming:.2f}s "
            f"({self._t('wav_original')} {original:.2f}s · {note})")
        self.btn_generate.setEnabled(True)

    def generate(self):
        if self.new_pcm is None:
            return
        if self.mode == "scan":
            self._replace_everywhere()
        else:
            self._replace_single_bank()

    def _replace_everywhere(self):
        """Rewrite the selected sound in every bank that contains it."""
        if not self.group:
            return
        answer = QMessageBox.question(
            self, self._t("sdx_confirm_all_title"),
            self._t("sdx_confirm_all", n=len(self.group.banks)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No)
        if answer != QMessageBox.StandardButton.Yes:
            return

        banks = len(self.group.banks)
        dlg = QProgressDialog(self._t("status_encoding"), None, 0, banks, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)

        def progress(n, total, path):
            dlg.setValue(n)
            dlg.setLabelText(os.path.basename(os.path.dirname(path)))
            QApplication.processEvents()

        try:
            changed = sdx.replace_group(self.group, self.new_pcm,
                                        backup=True, progress=progress)
        except sdx.ReplaceGroupError as e:
            dlg.close()
            # Partial success: everything that could be written already was —
            # report exactly what happened instead of hiding the successful part.
            msg = self._t("sdx_done_partial", n=len(e.changed), failed=len(e.failed))
            self.lbl_result.setText(msg)
            self.win.status.showMessage(msg)
            QMessageBox.warning(self, self._t("err_title"), msg)
            return
        except Exception as e:
            dlg.close()
            QMessageBox.critical(self, self._t("err_title"), self._t("err_generate", e=e))
            self.win.status.showMessage(self._t("status_gen_failed"))
            return
        dlg.close()

        self.lbl_result.setText(self._t("sdx_done_all", n=changed))
        self.win.status.showMessage(self._t("sdx_done_all", n=changed))

    def _replace_single_bank(self):
        if not (self.bank and self.sample):
            return
        original_name = os.path.basename(self.bank_path)
        start = self.win.cfg.get("dir_sdx_save", "") or os.path.dirname(self.bank_path)
        out, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_save_sdx"), os.path.join(start, original_name),
            self._t("filter_sdx"))
        if not out:
            return
        self.win.cfg["dir_sdx_save"] = os.path.dirname(out)
        save_config(self.win.cfg)

        self.btn_generate.setEnabled(False)
        try:
            self.win.status.showMessage(self._t("status_encoding"))
            QApplication.processEvents()
            new_raw = sdx.replace_sample(self.bank, self.sample, self.new_pcm)
            sdx.save_sdx(new_raw, out)
        except Exception as e:
            self.btn_generate.setEnabled(True)
            QMessageBox.critical(self, self._t("err_title"), self._t("err_generate", e=e))
            self.win.status.showMessage(self._t("status_gen_failed"))
            return

        self.btn_generate.setEnabled(True)

        self.lbl_result.setText(self._t("sdx_result", size=f"{len(new_raw):,}"))
        self.win.status.showMessage(self._t("sdx_status_done", name=os.path.basename(out)))
        QMessageBox.information(self, self._t("ok_dub_title"),
                                self._t("ok_dub_body", path=out))

    def cleanup(self):
        self._release_player()
        self._release_preview()
        self._destroy_playback()
