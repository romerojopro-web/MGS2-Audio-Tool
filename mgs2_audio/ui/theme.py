#!/usr/bin/env python3
"""
theme.py — The Codec-screen look: cyan-green on near-black (Master Collection),
and an amber variant for Substance (2003).

Each mode gets a full stylesheet so the entire UI recolours — not just the tabs.
Widget object names (`card`, `step`, `panel`, `library`…) are the hooks the
pages use.
"""

# ── Master Collection — cyan-green on near-black ─────────────────────────────

STYLE = """
* { font-family: 'Consolas', 'DejaVu Sans Mono', monospace; }

QMainWindow, QWidget { background-color: #04100c; color: #7fe0b0; }

QLabel#title { color: #4dffb0; font-size: 22px; font-weight: bold; letter-spacing: 4px; }
QLabel#subtitle { color: #2f7a5a; font-size: 12px; letter-spacing: 3px; }
QLabel#step { color: #4dffb0; font-size: 17px; font-weight: bold; letter-spacing: 1px; }
QLabel#body { color: #7fe0b0; font-size: 13px; }
QLabel#dim  { color: #3f8060; font-size: 12px; }
QLabel#value { color: #b8ffdc; font-size: 14px; }
QLabel#metakey { color: #3f8060; font-size: 13px; }
QLabel#metaval { color: #b8ffdc; font-size: 13px; }
QLabel#panel { color: #4dffb0; font-size: 13px; font-weight: bold; letter-spacing: 2px; }

QFrame#card { background-color: #061a12; border: 1px solid #123a28; border-radius: 3px; }
QFrame#metabox { background-color: #04140e; border: 1px solid #0e2c1e; border-radius: 2px; }
QFrame#library { background-color: #051710; border: 1px solid #123a28; border-radius: 3px; }
QFrame#sep { background-color: #123a28; max-height: 1px; }

QPushButton {
    background-color: #06251a; color: #4dffb0;
    border: 1px solid #1c5c40; border-radius: 2px;
    padding: 9px 16px; font-size: 13px; letter-spacing: 1px;
}
QPushButton:hover { background-color: #0a3626; border-color: #4dffb0; color: #86ffcb; }
QPushButton:pressed { background-color: #4dffb0; color: #04100c; }
QPushButton:disabled { background-color: #04140e; color: #245038; border-color: #143424; }

QPushButton#primary { background-color: #0a3626; border-color: #4dffb0; font-weight: bold; }
QPushButton#primary:hover { background-color: #0e4a34; }

QPushButton#small {
    padding: 6px 10px; font-size: 12px; letter-spacing: 0px;
}

QPushButton#play {
    background-color: #06251a; border-color: #1c5c40;
    min-width: 44px; max-width: 44px; font-size: 16px;
}

QComboBox {
    background-color: #06251a; color: #86ffcb;
    border: 1px solid #1c5c40; border-radius: 2px;
    padding: 4px 8px; font-size: 13px; min-width: 110px;
}
QComboBox:hover { border-color: #4dffb0; }
QComboBox QAbstractItemView {
    background-color: #061a12; color: #7fe0b0;
    selection-background-color: #0a3626; selection-color: #86ffcb;
    border: 1px solid #1c5c40;
}

QLineEdit, QPlainTextEdit {
    background-color: #04140e; color: #b8ffdc;
    border: 1px solid #1c5c40; border-radius: 2px;
    padding: 5px 7px; font-size: 13px;
    selection-background-color: #0a3626;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #4dffb0; }

QCheckBox { color: #86ffcb; font-size: 13px; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #1c5c40;
    background: #04140e; border-radius: 2px;
}
QCheckBox::indicator:checked { background: #4dffb0; border-color: #4dffb0; }

QListWidget {
    background-color: #04140e; color: #9fe8c4;
    border: 1px solid #123a28; border-radius: 2px; font-size: 13px;
    outline: none;
}
QListWidget::item { padding: 4px 6px; border-bottom: 1px solid #0b241a; }
QListWidget::item:selected { background-color: #0a3626; color: #b8ffdc; }
QListWidget::item:hover { background-color: #072016; }

QTabWidget::pane { border: 1px solid #123a28; border-radius: 3px; top: -1px; }
QTabBar::tab {
    background: #061a12; color: #3f8060;
    border: 1px solid #123a28; border-bottom: none;
    padding: 8px 20px; margin-right: 3px;
    font-size: 13px; letter-spacing: 1px;
}
QTabBar::tab:selected { background: #0a3626; color: #4dffb0; border-color: #1c5c40; }
QTabBar::tab:hover:!selected { background: #072016; color: #7fe0b0; }

QStatusBar {
    background-color: #020a07; border-top: 1px solid #123a28;
    color: #3f8060; font-size: 12px;
}

QSlider::groove:horizontal { height: 4px; background: #123a28; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4dffb0; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #4dffb0; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px;
}
"""

# ── Substance (2003) — warm amber on near-black ─────────────────────────────
# Same structure as STYLE but every green is replaced by its amber equivalent
# so the whole UI recolours, not just the tab bar.

STYLE_SUBSTANCE = """
* { font-family: 'Consolas', 'DejaVu Sans Mono', monospace; }

QMainWindow, QWidget { background-color: #0a0804; color: #e0b87f; }

QLabel#title { color: #ffc44d; font-size: 22px; font-weight: bold; letter-spacing: 4px; }
QLabel#subtitle { color: #a07830; font-size: 12px; letter-spacing: 3px; }
QLabel#step { color: #ffc44d; font-size: 17px; font-weight: bold; letter-spacing: 1px; }
QLabel#body { color: #e0b87f; font-size: 13px; }
QLabel#dim  { color: #8a6a30; font-size: 12px; }
QLabel#value { color: #ffe0a0; font-size: 14px; }
QLabel#metakey { color: #8a6a30; font-size: 13px; }
QLabel#metaval { color: #ffe0a0; font-size: 13px; }
QLabel#panel { color: #ffc44d; font-size: 13px; font-weight: bold; letter-spacing: 2px; }

QFrame#card { background-color: #14100a; border: 1px solid #4a3a14; border-radius: 3px; }
QFrame#metabox { background-color: #0e0a06; border: 1px solid #3a2a10; border-radius: 2px; }
QFrame#library { background-color: #110c06; border: 1px solid #4a3a14; border-radius: 3px; }
QFrame#sep { background-color: #4a3a14; max-height: 1px; }

QPushButton {
    background-color: #1a1408; color: #ffc44d;
    border: 1px solid #5a4420; border-radius: 2px;
    padding: 9px 16px; font-size: 13px; letter-spacing: 1px;
}
QPushButton:hover { background-color: #2a1e0c; border-color: #ffc44d; color: #ffe0a0; }
QPushButton:pressed { background-color: #ffc44d; color: #0a0804; }
QPushButton:disabled { background-color: #0e0a06; color: #5a4420; border-color: #3a2a14; }

QPushButton#primary { background-color: #2a1e0c; border-color: #ffc44d; font-weight: bold; }
QPushButton#primary:hover { background-color: #3a2a10; }

QPushButton#small {
    padding: 6px 10px; font-size: 12px; letter-spacing: 0px;
}

QPushButton#play {
    background-color: #1a1408; border-color: #5a4420;
    min-width: 44px; max-width: 44px; font-size: 16px;
}

QComboBox {
    background-color: #1a1408; color: #ffe0a0;
    border: 1px solid #5a4420; border-radius: 2px;
    padding: 4px 8px; font-size: 13px; min-width: 110px;
}
QComboBox:hover { border-color: #ffc44d; }
QComboBox QAbstractItemView {
    background-color: #14100a; color: #e0b87f;
    selection-background-color: #2a1e0c; selection-color: #ffe0a0;
    border: 1px solid #5a4420;
}

QLineEdit, QPlainTextEdit {
    background-color: #0e0a06; color: #ffe0a0;
    border: 1px solid #5a4420; border-radius: 2px;
    padding: 5px 7px; font-size: 13px;
    selection-background-color: #2a1e0c;
}
QLineEdit:focus, QPlainTextEdit:focus { border-color: #ffc44d; }

QCheckBox { color: #ffe0a0; font-size: 13px; spacing: 8px; }
QCheckBox::indicator {
    width: 16px; height: 16px; border: 1px solid #5a4420;
    background: #0e0a06; border-radius: 2px;
}
QCheckBox::indicator:checked { background: #ffc44d; border-color: #ffc44d; }

QListWidget {
    background-color: #0e0a06; color: #dcc080;
    border: 1px solid #4a3a14; border-radius: 2px; font-size: 13px;
    outline: none;
}
QListWidget::item { padding: 4px 6px; border-bottom: 1px solid #2a1e10; }
QListWidget::item:selected { background-color: #2a1e0c; color: #ffe0a0; }
QListWidget::item:hover { background-color: #1a1408; }

QTabWidget::pane { border: 1px solid #4a3a14; border-radius: 3px; top: -1px; }
QTabBar::tab {
    background: #14100a; color: #8a6a30;
    border: 1px solid #4a3a14; border-bottom: none;
    padding: 8px 20px; margin-right: 3px;
    font-size: 13px; letter-spacing: 1px;
}
QTabBar::tab:selected { background: #2a1e0c; color: #ffc44d; border-color: #5a4420; }
QTabBar::tab:hover:!selected { background: #1a1408; color: #e0b87f; }

QStatusBar {
    background-color: #080604; border-top: 1px solid #4a3a14;
    color: #8a6a30; font-size: 12px;
}

QSlider::groove:horizontal { height: 4px; background: #4a3a14; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #ffc44d; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #ffc44d; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px;
}
"""
