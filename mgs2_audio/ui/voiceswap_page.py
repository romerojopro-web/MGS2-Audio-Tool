#!/usr/bin/env python3
"""
voiceswap_page.py — the "Swap JP → US voices" tab (Phase 1).

Point it at the MGS2 folder; it pairs every Japanese voice file with its US
namesake and copies the JP audio over the US one, so the game speaks Japanese
while your subtitles stay in whatever language the game is set to.

The value over a blind file copy is the **detection**: codec calls (which embed
their multilingual subtitle text) and non-voice data are recognised and left
untouched, so a wholesale swap never turns your subtitles Japanese by accident.

Requires both the US and JP *Better Audio* mods installed (both sides PS-ADPCM).
No backups are written — restore with Steam's "Verify integrity of game files".
"""
import os

from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtWidgets import (
    QApplication, QFileDialog, QFrame, QLabel, QMessageBox,
    QProgressBar, QPushButton, QVBoxLayout, QWidget,
)

from ..formats import voiceswap as V
from .config import save_config


class VoiceSwapPage(QWidget):
    """Swap Japanese voices into a US install, protecting the subtitles."""

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode
        self.game_root = ""
        self.pairs = []

        self._build()

        saved = self.win.cfg.get("dir_voiceswap_game", "")
        if saved:
            QTimer.singleShot(50, lambda: self._load(saved))

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    def _card(self):
        f = QFrame(); f.setObjectName("card")
        return f

    # ── Construction ─────────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(16, 12, 16, 12)
        outer.setSpacing(14)

        self.lbl_title = QLabel(); self.lbl_title.setObjectName("title")
        outer.addWidget(self.lbl_title)
        self.lbl_intro = QLabel(); self.lbl_intro.setObjectName("body")
        self.lbl_intro.setWordWrap(True)
        outer.addWidget(self.lbl_intro)

        # Step 1 — pick the game folder
        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step1 = QLabel(); self.lbl_step1.setObjectName("step")
        c.addWidget(self.lbl_step1)
        self.btn_pick = QPushButton(); self.btn_pick.setObjectName("small")
        self.btn_pick.clicked.connect(self.pick_game_folder)
        c.addWidget(self.btn_pick)
        self.lbl_game = QLabel(); self.lbl_game.setObjectName("dim")
        self.lbl_game.setWordWrap(True)
        c.addWidget(self.lbl_game)
        outer.addWidget(card)

        # Step 2 — scan result
        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step2 = QLabel(); self.lbl_step2.setObjectName("step")
        c.addWidget(self.lbl_step2)
        self.lbl_scan = QLabel(); self.lbl_scan.setObjectName("value")
        self.lbl_scan.setWordWrap(True)
        c.addWidget(self.lbl_scan)
        outer.addWidget(card)

        # Step 3 — swap
        card = self._card()
        c = QVBoxLayout(card); c.setContentsMargins(16, 12, 16, 12); c.setSpacing(8)
        self.lbl_step3 = QLabel(); self.lbl_step3.setObjectName("step")
        c.addWidget(self.lbl_step3)
        self.lbl_warn = QLabel(); self.lbl_warn.setObjectName("dim")
        self.lbl_warn.setWordWrap(True)
        c.addWidget(self.lbl_warn)
        self.btn_swap = QPushButton(); self.btn_swap.setObjectName("primary")
        self.btn_swap.setEnabled(False)
        self.btn_swap.clicked.connect(self.do_swap)
        c.addWidget(self.btn_swap)
        self.progress = QProgressBar(); self.progress.setVisible(False)
        c.addWidget(self.progress)
        self.lbl_result = QLabel(); self.lbl_result.setObjectName("value")
        self.lbl_result.setWordWrap(True)
        c.addWidget(self.lbl_result)
        outer.addWidget(card)

        outer.addStretch(1)

    # ── Translation ──────────────────────────────────────────────────────────

    def retranslate(self):
        self.lbl_title.setText(self._t("vsw_title"))
        self.lbl_intro.setText(self._t("vsw_intro"))
        self.lbl_step1.setText(self._t("vsw_step1"))
        self.btn_pick.setText(self._t("vsw_pick_game"))
        if not self.game_root:
            self.lbl_game.setText(self._t("vsw_no_game"))
        self.lbl_step2.setText(self._t("vsw_step2"))
        self.lbl_step3.setText(self._t("vsw_step3"))
        self.lbl_warn.setText(self._t("vsw_warn"))
        self.btn_swap.setText(self._t("vsw_swap"))
        self._refresh_scan()

    # ── Loading / scanning ─────────────────────────────────────────────────────

    def pick_game_folder(self):
        start = self.win.cfg.get("dir_voiceswap_game", "") or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, self._t("vsw_pick_game"), start)
        if folder:
            self._load(folder)

    def _load(self, game_root):
        if not os.path.isdir(game_root):
            return
        self.game_root = game_root
        self.lbl_game.setText(game_root)
        self.win.cfg["dir_voiceswap_game"] = game_root
        save_config(self.win.cfg)
        self.pairs = V.find_pairs(game_root)
        self.lbl_result.setText("")
        self.btn_swap.setEnabled(bool(self.pairs))
        self._refresh_scan()

    def _refresh_scan(self):
        if not self.game_root:
            self.lbl_scan.setText(self._t("vsw_scan_none"))
            return
        by = {}
        for p in self.pairs:
            top = p.rel.replace("\\", "/").split("/")[0]
            by[top] = by.get(top, 0) + 1
        if not self.pairs:
            self.lbl_scan.setText(self._t("vsw_scan_empty"))
            return
        folders = ", ".join(f"{k} {v}" for k, v in sorted(by.items()))
        self.lbl_scan.setText(self._t("vsw_scan_result",
                                      total=len(self.pairs), folders=folders))

    # ── Swap ────────────────────────────────────────────────────────────────

    def do_swap(self):
        if not self.pairs:
            return
        ok = QMessageBox.question(
            self, self._t("vsw_confirm_title"),
            self._t("vsw_confirm", total=len(self.pairs)),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        if ok != QMessageBox.StandardButton.Yes:
            return

        self.btn_swap.setEnabled(False)
        self.btn_pick.setEnabled(False)
        self.lbl_result.setText("")
        total = len(self.pairs)
        self.progress.setVisible(True)
        self.progress.setRange(0, total)
        written = 0
        try:
            for i, pair in enumerate(self.pairs):
                written += V.swap_pair(pair)
                if i % 25 == 0 or i == total - 1:
                    self.progress.setValue(i + 1)
                    self.win.status.showMessage(self._t("vsw_swapping",
                                                        done=i + 1, total=total))
                    QApplication.processEvents()
        except Exception as e:
            self.progress.setVisible(False)
            self.btn_swap.setEnabled(True)
            self.btn_pick.setEnabled(True)
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("vsw_failed", e=e))
            return

        self.progress.setValue(total)
        self.progress.setVisible(False)
        self.btn_pick.setEnabled(True)
        self.btn_swap.setEnabled(True)
        self.win.status.showMessage(self._t("vsw_done_status"))
        self.lbl_result.setText(self._t("vsw_done",
                                        total=total, gb=written / 1e9))
