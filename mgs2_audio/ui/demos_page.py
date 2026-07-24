#!/usr/bin/env python3
"""
demos_page.py — The DEMOS tab: browse, listen and export `demo.dat` cutscene
audio from MGS2 Substance (2003).

Same format as bgm.dat (MS-ADPCM archive) but dedicated to cutscene audio.
Inherits all playback/export logic from BGMPage; only the labels and file
filter differ.
"""

from ..library import db as lib
from .bgm_page import BGMPage


class DEMOSPage(BGMPage):
    """Browse a demo.dat archive, listen to entries, export them."""

    # Same tab shape as BGMPage, but demo.dat tags don't belong in the same
    # file as bgm.dat/movie.dat tags.
    _LIBRARY_FILENAME = lib.DEMOS_LIBRARY_FILENAME

    # ── Translation ──────────────────────────────────────────────────────────

    def retranslate(self):
        self.lbl_list_title.setText(self._t("demos_list_title"))
        self.btn_open.setText(self._t("bgm_browse"))
        if not self.bgm:
            self.lbl_archive.setText(self._t("bgm_no_file"))
        self._update_info()
        self.lbl_step1.setText(self._t("bgm_open_title"))
        self.lbl_hint.setText(self._t("demos_hint"))
        self.lbl_step2.setText(self._t("bgm_listen_title"))
        self.lbl_step3.setText(self._t("bgm_export_title"))
        self.btn_export.setText(self._t("bgm_export"))
        self.btn_export_all.setText(self._t("bgm_export_all"))
        self._retranslate_tag_fields()
        self._refresh_count()

    # ── Loading ──────────────────────────────────────────────────────────────

    def open_archive(self):
        from PyQt6.QtWidgets import QFileDialog, QMessageBox
        import os
        from ..formats import bgm as bgm_fmt
        from .config import save_config

        start = self.win.cfg.get("dir_demos", "") or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_demos"), start,
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
        self.win.cfg["dir_demos"] = os.path.dirname(path)
        save_config(self.win.cfg)
        self._reset_selection()

        self.lbl_archive.setText(path)
        self._update_info()
        self.lbl_hint.setText(self._t("demos_hint"))
        self.btn_export_all.setEnabled(True)
        self._fill_list()
        self.win.status.showMessage(self._t(
            "bgm_status_loaded", name=os.path.basename(path),
            n=bgm.entry_count))
