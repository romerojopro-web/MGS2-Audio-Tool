#!/usr/bin/env python3
"""
app.py — The application shell.

Owns what the two tabs share: the config, the status bar, the language, and the
window itself. Everything format-specific lives in `sdt_page` and `sdx_page`.

Run it with `python run.py` from the project root.
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFrame, QHBoxLayout, QLabel, QMainWindow,
    QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from .config import load_config, save_config
from .i18n import LANGUAGE_ORDER, TRANSLATIONS, tr
from .sdt_page import SDTPage
from .sdx_page import SDXPage
from .theme import STYLE


class MainWindow(QMainWindow):
    """Two tabs, one status bar, one language."""

    def __init__(self):
        super().__init__()
        self.resize(1180, 860)

        self.cfg = load_config()
        self.lang = self.cfg.get("language", "fr")
        # The tagging database folder is shared by both tabs (two JSON files).
        self.db_folder = self.cfg.get("db_folder", "")

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._retranslate()

        if self.db_folder:
            self.sdx_page.reload_library()
        self.sdt_page.restore_folders()

    def _t(self, key, **kw):
        return tr(self.lang, key, **kw)

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 12, 20, 8)
        outer.setSpacing(10)

        # Header + language selector, above the tabs
        top = QHBoxLayout()
        header = QVBoxLayout()
        header.setSpacing(2)
        self.lbl_title = QLabel()
        self.lbl_title.setObjectName("title")
        self.lbl_subtitle = QLabel()
        self.lbl_subtitle.setObjectName("subtitle")
        header.addWidget(self.lbl_title)
        header.addWidget(self.lbl_subtitle)
        top.addLayout(header)
        top.addStretch()

        lang_col = QVBoxLayout()
        lang_col.setSpacing(2)
        self.lbl_lang = QLabel()
        self.lbl_lang.setObjectName("dim")
        self.lbl_lang.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.combo_lang = QComboBox()
        for code in LANGUAGE_ORDER:
            self.combo_lang.addItem(TRANSLATIONS[code]["lang_name"], code)
        idx = LANGUAGE_ORDER.index(self.lang) if self.lang in LANGUAGE_ORDER else 0
        self.combo_lang.setCurrentIndex(idx)
        self.combo_lang.currentIndexChanged.connect(self._on_language_changed)
        lang_col.addWidget(self.lbl_lang)
        lang_col.addWidget(self.combo_lang)
        top.addLayout(lang_col)
        outer.addLayout(top)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(sep)

        self.tabs = QTabWidget()
        outer.addWidget(self.tabs)

        self.sdt_page = SDTPage(self)
        self.tabs.addTab(self.sdt_page, "")
        self.sdx_page = SDXPage(self)
        self.tabs.addTab(self.sdx_page, "")

        # Come back to whichever tab was in use last time
        last = self.cfg.get("last_tab", 0)
        if 0 <= last < self.tabs.count():
            self.tabs.setCurrentIndex(last)
        self.tabs.currentChanged.connect(self._on_tab_changed)

    # ── Shell behaviour ──────────────────────────────────────────────────────

    def _on_tab_changed(self, index):
        self.cfg["last_tab"] = index
        save_config(self.cfg)

    def _on_language_changed(self, index):
        self.lang = self.combo_lang.itemData(index)
        self.cfg["language"] = self.lang
        save_config(self.cfg)
        self._retranslate()

    def _retranslate(self):
        self.setWindowTitle(self._t("window_title"))
        self.lbl_title.setText(self._t("app_title"))
        self.lbl_subtitle.setText(self._t("app_subtitle"))
        self.lbl_lang.setText(self._t("language_label"))
        self.tabs.setTabText(0, self._t("tab_sdt"))
        self.tabs.setTabText(1, self._t("tab_sdx"))
        self.sdt_page.retranslate()
        self.sdx_page.retranslate()

    def closeEvent(self, event):
        self.sdt_page.cleanup()
        self.sdx_page.cleanup()
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
