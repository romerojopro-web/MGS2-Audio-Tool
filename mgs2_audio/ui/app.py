#!/usr/bin/env python3
"""
app.py — The application shell.

Owns what the tabs share: the config, the status bar, the language, and the
window itself.  Each mode (Master Collection, Substance, …) gets its own set of
dedicated page instances — when the mode changes all pages are destroyed and
recreated so there is zero state leakage between modes.

Game plugins register themselves via the core REGISTRY; the shell never
imports game-specific page classes directly.

Run it with `python run.py` from the project root.
"""

import os
import sys

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QApplication, QComboBox, QFileDialog, QFrame, QHBoxLayout, QLabel,
    QMainWindow, QPushButton, QStatusBar, QTabWidget, QVBoxLayout, QWidget,
)

from .config import load_config, save_config
from .i18n import LANGUAGE_ORDER, TRANSLATIONS, tr
from .theme import STYLE, STYLE_SUBSTANCE

# ── Game plugin discovery ────────────────────────────────────────────────────
# Importing ``games`` triggers discover(), which imports every game subpackage
# and registers its plugin with the core REGISTRY.
from .. import games  # noqa: F401  (side-effect: registers plugins)
from ..core import REGISTRY


def _build_mode_index():
    """Flatten every plugin's modes into a global mode list.

    Returns:
        mode_order: list of mode_ids in display order
        mode_map:   mode_id -> {"plugin": GamePlugin, "mode_data": dict}
    """
    mode_order = []
    mode_map = {}
    for plugin in REGISTRY:
        for mode_id, mode_data in plugin.modes.items():
            mode_order.append(mode_id)
            mode_map[mode_id] = {"plugin": plugin, "mode_data": mode_data}
    return mode_order, mode_map


# Theme lookup: mode_data["style"] -> stylesheet (see each plugin's `modes`)
_THEME_MAP = {
    "": STYLE,
    "substance": STYLE_SUBSTANCE,
}


class MainWindow(QMainWindow):
    """One status bar, one language, one mode — pages are rebuilt on mode switch."""

    def __init__(self):
        super().__init__()
        self.resize(1180, 860)

        self.cfg = load_config()
        self.lang = self.cfg.get("language", "fr")

        # Build the global mode index from plugins
        self._mode_order, self._mode_map = _build_mode_index()

        self.mode = self.cfg.get("mode", "")
        if self.mode not in self._mode_map:
            self.mode = self._mode_order[0] if self._mode_order else ""

        self._pages = {}   # key -> page instance (e.g. "sdt" -> SDTPage)

        self.status = QStatusBar()
        self.setStatusBar(self.status)

        self._build_ui()
        self._retranslate()

    def _t(self, key, **kw):
        return tr(self.lang, key, **kw)

    # ── Tagging database folder (per game/mode) ─────────────────────────────────

    @property
    def db_folder(self) -> str:
        """The tagging database folder for the *current* mode.

        Each game/mode has its own folder — tagging Substance sounds must not
        write into the same place as Master Collection's tags. Stored as
        {mode_id: path} in the config; older configs stored a single shared
        string, migrated in place here on first access so existing users keep
        their folder (applied to every mode) until they pick separate ones.
        """
        d = self.cfg.get("db_folder")
        if isinstance(d, str):
            d = {m: d for m in self._mode_order}
            self.cfg["db_folder"] = d
        if not isinstance(d, dict):
            return ""
        return d.get(self.mode, "")

    @db_folder.setter
    def db_folder(self, value: str):
        d = self.cfg.get("db_folder")
        if not isinstance(d, dict):
            d = {}
        d[self.mode] = value
        self.cfg["db_folder"] = d

    def pick_db_folder(self):
        """Choose the tagging database folder for the current mode, and
        refresh every open page's library so the change takes effect at once."""
        start = self.db_folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(self, self._t("dlg_pick_db"), start)
        if not folder:
            return
        self.db_folder = folder
        save_config(self.cfg)
        self._retranslate()
        for page in self._pages.values():
            if hasattr(page, "reload_library"):
                page.reload_library()

    # ── Construction ─────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        outer = QVBoxLayout(central)
        outer.setContentsMargins(20, 12, 20, 8)
        outer.setSpacing(10)

        # Header + selectors, above the tabs
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

        mode_col = QVBoxLayout()
        mode_col.setSpacing(2)
        self.lbl_mode = QLabel()
        self.lbl_mode.setObjectName("dim")
        self.lbl_mode.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.combo_mode = QComboBox()
        for code in self._mode_order:
            self.combo_mode.addItem(self._t("mode_" + code), code)
        midx = (self._mode_order.index(self.mode)
                if self.mode in self._mode_order else 0)
        self.combo_mode.setCurrentIndex(midx)
        self.combo_mode.currentIndexChanged.connect(self._on_mode_changed)
        mode_col.addWidget(self.lbl_mode)
        mode_col.addWidget(self.combo_mode)
        top.addLayout(mode_col)

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

        # Tagging database folder — one per game/mode (see the db_folder
        # property). Always visible, unlike the per-page pickers some tabs
        # also offer, so every mode has a way to set its own.
        db_col = QVBoxLayout()
        db_col.setSpacing(2)
        self.lbl_db_folder = QLabel()
        self.lbl_db_folder.setObjectName("dim")
        self.lbl_db_folder.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.btn_db_folder = QPushButton()
        self.btn_db_folder.setObjectName("small")
        self.btn_db_folder.clicked.connect(self.pick_db_folder)
        db_col.addWidget(self.lbl_db_folder)
        db_col.addWidget(self.btn_db_folder)
        top.addLayout(db_col)
        outer.addLayout(top)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        outer.addWidget(sep)

        self.tabs = QTabWidget()
        self.tabs.currentChanged.connect(self._on_tab_changed)
        outer.addWidget(self.tabs)

        # Build pages for the initial mode
        self._build_pages(self.mode)

    # ── Page lifecycle ───────────────────────────────────────────────────────

    def _destroy_pages(self):
        """Clean up and remove all current pages from the tab widget."""
        # Cleanup pages that have a cleanup() method
        for page in self._pages.values():
            if hasattr(page, "cleanup") and not getattr(page, "_cleaned_up", False):
                try:
                    page.cleanup()
                    page._cleaned_up = True
                except Exception:
                    pass
        # Remove all tabs
        while self.tabs.count() > 0:
            widget = self.tabs.widget(0)
            self.tabs.removeTab(0)
            widget.setParent(None)
            widget.deleteLater()
        self._pages.clear()

    def _build_pages(self, mode):
        """Destroy old pages and create fresh ones for *mode*."""
        self._destroy_pages()

        entry = self._mode_map.get(mode)
        if entry is None:
            return

        for spec in entry["mode_data"]["pages"]:
            page = spec.cls(self, mode=mode)
            self._pages[spec.key] = page
            self.tabs.addTab(page, "")

        # Restore the last-used tab if it exists in the new mode
        last_key = self.cfg.get("last_tab_key", "")
        if last_key and last_key in self._pages:
            idx = list(self._pages.keys()).index(last_key)
            self.tabs.setCurrentIndex(idx)
        elif self.tabs.count() > 0:
            self.tabs.setCurrentIndex(0)

        self._apply_mode()

    def _apply_mode(self):
        """Apply the full per-mode stylesheet and update the subtitle."""
        entry = self._mode_map.get(self.mode)
        if entry is None:
            return
        mode_data = entry["mode_data"]
        theme_key = mode_data.get("style", "")
        self.setStyleSheet(_THEME_MAP.get(theme_key, STYLE))
        sub_key = mode_data.get("subtitle_key", "")
        if sub_key:
            self.lbl_subtitle.setText(self._t(sub_key))

    # ── Mode / tab / language signals ────────────────────────────────────────

    def _on_mode_changed(self, index):
        new_mode = self.combo_mode.itemData(index)
        if new_mode == self.mode:
            return
        self.mode = new_mode
        self.cfg["mode"] = self.mode
        save_config(self.cfg)
        self._build_pages(self.mode)
        self._retranslate()

    def _on_tab_changed(self, index):
        # Store the mode-specific key, not the tab index (which changes per mode)
        keys = list(self._pages.keys())
        if 0 <= index < len(keys):
            self.cfg["last_tab_key"] = keys[index]
            save_config(self.cfg)

    def _on_language_changed(self, index):
        self.lang = self.combo_lang.itemData(index)
        self.cfg["language"] = self.lang
        save_config(self.cfg)
        self._retranslate()

    # ── Translation ──────────────────────────────────────────────────────────

    def _retranslate(self):
        self.setWindowTitle(self._t("window_title"))
        self.lbl_title.setText(self._t("app_title"))
        self.lbl_lang.setText(self._t("language_label"))
        self.lbl_mode.setText(self._t("mode_label"))
        for i, code in enumerate(self._mode_order):
            self.combo_mode.setItemText(i, self._t("mode_" + code))

        self.lbl_db_folder.setText(self._t("db_folder_label"))
        folder = self.db_folder
        self.btn_db_folder.setText(
            os.path.basename(folder.rstrip("/\\")) if folder else self._t("lib_pick_db"))
        self.btn_db_folder.setToolTip(folder or self._t("lib_no_db"))

        # Update subtitle for current mode
        self._apply_mode()

        # Update tab labels and retranslate all pages
        entry = self._mode_map.get(self.mode)
        if entry:
            for i, spec in enumerate(entry["mode_data"]["pages"]):
                self.tabs.setTabText(i, self._t(spec.tab_key))
        for page in self._pages.values():
            if hasattr(page, "retranslate"):
                page.retranslate()

    # ── Shutdown ─────────────────────────────────────────────────────────────

    def closeEvent(self, event):
        for page in self._pages.values():
            if hasattr(page, "cleanup") and not getattr(page, "_cleaned_up", False):
                try:
                    page.cleanup()
                    page._cleaned_up = True
                except Exception:
                    pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
