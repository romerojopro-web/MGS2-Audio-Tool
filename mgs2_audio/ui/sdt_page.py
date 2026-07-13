#!/usr/bin/env python3
"""
sdt_page.py — The SDT tab: dialogue, music and some sound effects.

A voice library on the left (a folder of `.sdt` files, manually tagged), and the
four dubbing steps on the right: open, listen, pick a replacement, generate.

The tool never guesses whether a line is done — that box is the user's to tick.
"""

import os
import tempfile

from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer

from PyQt6.QtWidgets import (
    QApplication, QCheckBox, QComboBox, QCompleter, QFileDialog, QFrame,
    QGridLayout, QHBoxLayout, QLabel, QLineEdit, QListWidgetItem, QMessageBox,
    QPlainTextEdit, QProgressDialog, QPushButton, QSizePolicy, QSlider,
    QSplitter, QVBoxLayout, QWidget,
)

from ..formats import sdt as core
from ..library import db as lib
from .config import save_config
from .widgets import PlayOnSpaceList, PlaybackMixin, PopupLineEdit


class SDTPage(PlaybackMixin, QWidget):
    """Voice library + the four dubbing steps."""

    def __init__(self, window, mode="mc"):
        super().__init__()
        self.win = window
        self.mode = mode

        # Folders remembered per section
        self.dir_open = self.win.cfg.get("dir_open", "")
        self.dir_export = self.win.cfg.get("dir_export", "")
        self.dir_dub = self.win.cfg.get("dir_dub", "")
        self.dir_save = self.win.cfg.get("dir_save", "")

        # Voice library (folder of .sdt lines + tagging database)
        self.voice_folder = self.win.cfg.get("voice_folder", "")
        self.library = {"version": lib.LIBRARY_VERSION, "entries": {}}
        self.lib_files = []          # filenames currently listed
        self.current_lib_file = ""   # selected filename in the library
        self._loading_entry = False  # guard against feedback while filling fields
        self._quick_ch = {}          # filename -> channel count (cheap header scan)

        # State
        self.sdt = None
        self.sdt_path = ""
        self.new_wav_path = ""
        self.preview_wav = ""
        self.new_wav_samples = None
        self.new_wav_rate = 0

        # Audio player
        self._init_playback()

        self._build()
        self.restore_folders()

    def _t(self, key, **kw):
        return self.win._t(key, **kw)

    @property
    def db_folder(self):
        """The tagging database folder is shared by every tab of this mode."""
        return self.win.db_folder

    # ── UI construction ─────────────────────────────────────────────────────

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 8, 0, 0)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        outer.addWidget(splitter)

        self._library_panel = self._build_library()
        splitter.addWidget(self._library_panel)

        right = QWidget()
        root = QVBoxLayout(right)
        root.setContentsMargins(16, 4, 4, 8)
        root.setSpacing(14)
        root.addWidget(self._build_step1())
        root.addWidget(self._build_step2())
        root.addWidget(self._build_step3())
        root.addWidget(self._build_step4())
        root.addStretch()

        splitter.addWidget(right)
        splitter.setStretchFactor(0, 0)
        splitter.setStretchFactor(1, 1)
        splitter.setSizes([340, 760])

    def _card(self):
        f = QFrame(); f.setObjectName("card")
        return f

    def _build_library(self):
        panel = QFrame(); panel.setObjectName("library")
        panel.setMinimumWidth(300)
        lay = QVBoxLayout(panel)
        lay.setContentsMargins(12, 12, 12, 12)
        lay.setSpacing(8)

        self.lbl_lib_title = QLabel(); self.lbl_lib_title.setObjectName("panel")
        lay.addWidget(self.lbl_lib_title)

        # Folder pickers
        self.btn_lib_voice = QPushButton(); self.btn_lib_voice.setObjectName("small")
        self.btn_lib_voice.clicked.connect(self.pick_voice_folder)
        lay.addWidget(self.btn_lib_voice)
        self.lbl_lib_voice = QLabel(); self.lbl_lib_voice.setObjectName("dim")
        self.lbl_lib_voice.setWordWrap(True)
        lay.addWidget(self.lbl_lib_voice)

        self.btn_lib_db = QPushButton(); self.btn_lib_db.setObjectName("small")
        self.btn_lib_db.clicked.connect(self.pick_db_folder)
        lay.addWidget(self.btn_lib_db)
        self.lbl_lib_db = QLabel(); self.lbl_lib_db.setObjectName("dim")
        self.lbl_lib_db.setWordWrap(True)
        lay.addWidget(self.lbl_lib_db)

        # Search + filters
        self.edit_search = PopupLineEdit()
        self.edit_search.textChanged.connect(self._refresh_list)
        lay.addWidget(self.edit_search)

        self.combo_filter = QComboBox()
        # items are (re)labelled in _retranslate; userData is the filter key
        self.combo_filter.addItem("", "all")
        self.combo_filter.addItem("", "todo")
        self.combo_filter.addItem("", "done")
        self.combo_filter.currentIndexChanged.connect(self._refresh_list)
        lay.addWidget(self.combo_filter)

        # Filter by tag: essential once a thousand files carry labels
        self.combo_tag = QComboBox()
        self.combo_tag.currentIndexChanged.connect(self._refresh_list)
        lay.addWidget(self.combo_tag)

        # File list
        self.list_files = PlayOnSpaceList(self.toggle_play)
        self.list_files.currentItemChanged.connect(self._on_lib_selected)
        self.list_files.itemDoubleClicked.connect(self._on_lib_activated)
        lay.addWidget(self.list_files, 1)

        self.lbl_lib_count = QLabel(); self.lbl_lib_count.setObjectName("dim")
        lay.addWidget(self.lbl_lib_count)

        self.btn_lib_scan = QPushButton(); self.btn_lib_scan.setObjectName("small")
        self.btn_lib_scan.clicked.connect(self.scan_folder)
        lay.addWidget(self.btn_lib_scan)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        lay.addWidget(sep)

        # Tagging fields for the selected file
        self.chk_done = QCheckBox()
        self.chk_done.stateChanged.connect(self._on_entry_edited)
        lay.addWidget(self.chk_done)

        self.lbl_tag = QLabel(); self.lbl_tag.setObjectName("dim")
        lay.addWidget(self.lbl_tag)
        self.edit_tag = PopupLineEdit()
        self.edit_tag.editingFinished.connect(self._on_entry_edited)
        lay.addWidget(self.edit_tag)

        self.lbl_speaker = QLabel(); self.lbl_speaker.setObjectName("dim")
        lay.addWidget(self.lbl_speaker)
        self.edit_speaker = QLineEdit()
        self.edit_speaker.editingFinished.connect(self._on_entry_edited)
        lay.addWidget(self.edit_speaker)

        self.lbl_notes = QLabel(); self.lbl_notes.setObjectName("dim")
        lay.addWidget(self.lbl_notes)
        self.edit_notes = QPlainTextEdit()
        self.edit_notes.setFixedHeight(70)
        lay.addWidget(self.edit_notes)

        self.btn_save_entry = QPushButton(); self.btn_save_entry.setObjectName("small")
        self.btn_save_entry.clicked.connect(self._save_current_entry)
        lay.addWidget(self.btn_save_entry)

        self._set_entry_fields_enabled(False)
        return panel

    def _build_step1(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.lbl_step1 = QLabel(); self.lbl_step1.setObjectName("step")
        lay.addWidget(self.lbl_step1)

        row = QHBoxLayout()
        self.btn_open = QPushButton(); self.btn_open.setObjectName("primary")
        self.btn_open.clicked.connect(self.open_sdt)
        row.addWidget(self.btn_open)
        self.lbl_file = QLabel(); self.lbl_file.setObjectName("dim")
        self.lbl_file.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.lbl_file, 1)
        lay.addLayout(row)

        # Metadata box laid out as a grid (readable, airy)
        self.metabox = QFrame(); self.metabox.setObjectName("metabox")
        self.metabox.setVisible(False)
        grid = QGridLayout(self.metabox)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        # 5 rows: key (right) + value (left)
        self.meta_keys = []
        self.meta_vals = []
        for i in range(5):
            k = QLabel(); k.setObjectName("metakey")
            k.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
            v = QLabel(); v.setObjectName("metaval")
            v.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            grid.addWidget(k, i, 0)
            grid.addWidget(v, i, 1)
            self.meta_keys.append(k)
            self.meta_vals.append(v)

        lay.addWidget(self.metabox)
        return card

    def _build_step2(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.lbl_step2 = QLabel(); self.lbl_step2.setObjectName("step")
        lay.addWidget(self.lbl_step2)

        row = QHBoxLayout()
        self.btn_play = QPushButton("▶"); self.btn_play.setObjectName("play")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)
        row.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self._seek)
        row.addWidget(self.slider, 1)

        self.lbl_time = QLabel("0:00 / 0:00"); self.lbl_time.setObjectName("value")
        self.lbl_time.setFixedWidth(90)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.lbl_time)
        lay.addLayout(row)

        self.btn_export = QPushButton(); self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_wav)
        lay.addWidget(self.btn_export)
        return card

    def _build_step3(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.lbl_step3 = QLabel(); self.lbl_step3.setObjectName("step")
        lay.addWidget(self.lbl_step3)
        self.lbl_step3_hint = QLabel(); self.lbl_step3_hint.setObjectName("dim")
        self.lbl_step3_hint.setWordWrap(True)
        lay.addWidget(self.lbl_step3_hint)

        row = QHBoxLayout()
        self.btn_pick_wav = QPushButton(); self.btn_pick_wav.setEnabled(False)
        self.btn_pick_wav.clicked.connect(self.pick_wav)
        row.addWidget(self.btn_pick_wav)
        self.lbl_wav = QLabel(); self.lbl_wav.setObjectName("dim")
        self.lbl_wav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.lbl_wav, 1)
        lay.addLayout(row)

        self.lbl_wav_info = QLabel(); self.lbl_wav_info.setObjectName("body")
        self.lbl_wav_info.setWordWrap(True)
        lay.addWidget(self.lbl_wav_info)
        return card

    def _build_step4(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(10)

        self.lbl_step4 = QLabel(); self.lbl_step4.setObjectName("step")
        lay.addWidget(self.lbl_step4)
        self.btn_generate = QPushButton(); self.btn_generate.setObjectName("primary")
        self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self.generate_sdt)
        lay.addWidget(self.btn_generate)

        self.lbl_result = QLabel(); self.lbl_result.setObjectName("value")
        self.lbl_result.setWordWrap(True)
        lay.addWidget(self.lbl_result)
        return card

    # ── Translation ──────────────────────────────────────────────────────────

    def retranslate(self):
        # Library panel
        self.lbl_lib_title.setText(self._t("lib_title"))
        self.btn_lib_voice.setText(self._t("lib_pick_voice"))
        self.btn_lib_db.setText(self._t("lib_pick_db"))
        self.lbl_lib_voice.setText(self.voice_folder or self._t("lib_no_voice"))
        self.lbl_lib_db.setText(self.db_folder or self._t("lib_no_db"))
        self.edit_search.setPlaceholderText(self._t("lib_search"))
        for i, key in enumerate(("lib_filter_all", "lib_filter_todo", "lib_filter_done")):
            self.combo_filter.setItemText(i, self._t(key))
        self._refresh_tag_filter()
        self.btn_lib_scan.setText(self._t("lib_scan"))
        self.chk_done.setText(self._t("lib_done"))
        self.lbl_tag.setText(self._t("lib_tag"))
        self.edit_tag.setPlaceholderText(self._t("lib_tag_hint"))
        self.lbl_speaker.setText(self._t("lib_speaker"))
        self.lbl_notes.setText(self._t("lib_notes"))
        self.btn_save_entry.setText(self._t("lib_save_entry"))
        self._update_count()

        self.lbl_step1.setText(self._t("step1_title"))
        self.btn_open.setText(self._t("browse"))
        if not self.sdt:
            self.lbl_file.setText(self._t("no_file"))

        self.lbl_step2.setText(self._t("step2_title"))
        self.btn_export.setText(self._t("export_wav"))

        self.lbl_step3.setText(self._t("step3_title"))
        self.lbl_step3_hint.setText(self._t("step3_hint"))
        self.btn_pick_wav.setText(self._t("pick_wav"))
        if not self.new_wav_path:
            self.lbl_wav.setText(self._t("no_wav"))

        self.lbl_step4.setText(self._t("step4_title"))
        self.btn_generate.setText(self._t("generate"))

        # Refresh the info if a file is loaded
        if self.sdt:
            self._show_metadata()
            if self.new_wav_path:
                self._show_wav_info()

        if not self.sdt:
            self.win.status.showMessage(self._t("status_ready"))

    def restore_folders(self):
        """Re-open the folders the user was last working in."""
        if self.db_folder:
            self.library = lib.load_library(self.db_folder)
            self._update_tag_completer()
        if self.voice_folder and os.path.isdir(self.voice_folder):
            self._load_library_folder()
        else:
            self._refresh_list()

    def cleanup(self):
        self._release_player()
        if self.preview_wav and os.path.exists(self.preview_wav):
            try:
                os.unlink(self.preview_wav)
            except Exception:
                pass
        self.preview_wav = ""
        self._destroy_playback()

    # ── Metadata display (grid) ─────────────────────────────────────────────

    def _show_metadata(self):
        if not self.sdt:
            return
        md = core.metadata(self.sdt)
        ch_label = self._t("unit_stereo") if md["channels"] == 2 else self._t("unit_mono")
        rows = [
            (self._t("info_file"), md["file"]),
            (self._t("info_size"), f"{md['size']:,} {self._t('unit_bytes')}"),
            (self._t("info_rate"), f"{md['sample_rate']} Hz ({ch_label})"),
            (self._t("info_blocks"), str(md["blocks"])),
            (self._t("info_duration"), f"{md['duration']:.2f} {self._t('unit_seconds')}"),
        ]
        for i, (k, v) in enumerate(rows):
            self.meta_keys[i].setText(k + " :")
            self.meta_vals[i].setText(v)
        self.metabox.setVisible(True)

    # ── Step 1: open ─────────────────────────────────────────────────────────

    def open_sdt(self):
        start_dir = self.dir_open or os.path.expanduser("~")
        dlg_title = self._t("dlg_open_sdt")
        file_filter = self._t("filter_sdt")
        path, _ = QFileDialog.getOpenFileName(
            self, dlg_title, start_dir, file_filter)
        if not path:
            return
        self._load_sdt_path(path)

    def _load_sdt_path(self, path) -> bool:
        """Load an SDT file into the workflow. Reused by the Browse button and
        by the library list. Returns True on success."""
        try:
            self.sdt = core.parse_sdt(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return False

        self.sdt_path = path
        self.dir_open = os.path.dirname(path)
        self.win.cfg["dir_open"] = self.dir_open
        save_config(self.win.cfg)

        self.new_wav_path = ""
        self.new_wav_samples = None
        self.lbl_wav.setText(self._t("no_wav"))
        self.lbl_wav_info.setText("")
        self.lbl_result.setText("")
        self.btn_generate.setEnabled(False)

        self.lbl_file.setText(os.path.basename(path))
        self._show_metadata()

        # Files that are not PS-ADPCM, or that contain no audio blocks, cannot
        # be previewed or edited — show a clear message and disable the actions.
        if not self.sdt.supported:
            msg = self._t("warn_no_audio") if not self.sdt.has_audio \
                else self._t("warn_unsupported")
            self.lbl_result.setText(msg)
            self.btn_play.setEnabled(False)
            self.slider.setEnabled(False)
            self.btn_export.setEnabled(False)
            self.btn_pick_wav.setEnabled(False)
            self.btn_generate.setEnabled(False)
            self.preview_wav = ""
            self.win.status.showMessage(msg)
            self._cache_current_into_library(path)
            return True

        self._prepare_preview()

        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_pick_wav.setEnabled(True)

        self.win.status.showMessage(self._t(
            "status_loaded", name=os.path.basename(path),
            dur=self.sdt.duration_seconds, blocks=len(self.sdt.blocks)))

        # Cache metadata for this file in the library, if it belongs to the
        # current voice folder (keeps the list display in sync).
        self._cache_current_into_library(path)
        return True

    # ── Library: folder pickers and loading ──────────────────────────────────

    def pick_voice_folder(self):
        start = self.voice_folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_pick_voice"), start)
        if not folder:
            return
        self.voice_folder = folder
        self.win.cfg["voice_folder"] = folder
        save_config(self.win.cfg)
        self._load_library_folder()

    def pick_db_folder(self):
        start = self.db_folder or self.voice_folder or os.path.expanduser("~")
        folder = QFileDialog.getExistingDirectory(
            self, self._t("dlg_pick_db"), start)
        if not folder:
            return
        self.win.db_folder = folder
        self.win.cfg["db_folder"] = folder
        save_config(self.win.cfg)
        self.library = lib.load_library(self.db_folder)
        self.lbl_lib_db.setText(folder)
        self._update_tag_completer()
        self._refresh_list()
        # the SDX tab keeps its own database in the same folder
        sdx_page = self.win._pages.get("sdx")
        if sdx_page:
            sdx_page.reload_library()

    def _load_library_folder(self):
        """List the voice folder and prefetch cheap per-file channel info."""
        self.lbl_lib_voice.setText(self.voice_folder or self._t("lib_no_voice"))
        if self.db_folder:
            self.library = lib.load_library(self.db_folder)
        self.lib_files = lib.list_sdt_files(self.voice_folder)

        # Cheap header scan (a few hundred bytes/file) for the mono/stereo tag
        self._quick_ch = {}
        for name in self.lib_files:
            try:
                info = lib.quick_header(os.path.join(self.voice_folder, name))
                self._quick_ch[name] = info["channels"]
            except Exception:
                pass

        self._update_tag_completer()
        self._refresh_list()

    # ── Library: list rendering + filtering ──────────────────────────────────

    def _row_text(self, name) -> str:
        entry = lib.get_entry(self.library, name)
        marker = "✓" if entry["done"] else "○"
        ch = self._quick_ch.get(name)
        chtxt = "ST" if ch == 2 else ("MO" if ch == 1 else "  ")
        dur = entry.get("duration")
        durtxt = f"{dur:4.0f}s" if isinstance(dur, (int, float)) else ""
        tag = (entry.get("tag") or "").strip()
        tagtxt = f"  [{tag}]" if tag else ""
        return f"{marker} {name}   {chtxt} {durtxt}{tagtxt}"

    def _passes_filter(self, name) -> bool:
        entry = lib.get_entry(self.library, name)
        # search text
        q = self.edit_search.text().strip().lower()
        if q:
            hay = f"{name} {entry.get('tag','')} {entry.get('speaker','')} {entry.get('notes','')}".lower()
            if q not in hay:
                return False
        # done/todo filter
        mode = self.combo_filter.currentData() or "all"
        if mode == "done" and not entry["done"]:
            return False
        if mode == "todo" and entry["done"]:
            return False
        # tag filter
        wanted_tag = self.combo_tag.currentData() if hasattr(self, "combo_tag") else ""
        if wanted_tag and (entry.get("tag") or "").strip() != wanted_tag:
            return False
        return True

    def _refresh_list(self):
        if not hasattr(self, "list_files"):
            return
        keep = self.current_lib_file
        found = False
        self.list_files.blockSignals(True)
        self.list_files.clear()
        for name in self.lib_files:
            if not self._passes_filter(name):
                continue
            it = QListWidgetItem(self._row_text(name))
            it.setData(Qt.ItemDataRole.UserRole, name)
            self.list_files.addItem(it)
            if name == keep:
                self.list_files.setCurrentItem(it)
                found = True
        self.list_files.blockSignals(False)
        if keep and not found:
            # The selected entry was filtered out from under it (e.g. ticking
            # "Done" while filtered to "Todo") — don't leave the tag panel live
            # on an entry that's no longer visible.
            self.current_lib_file = ""
            self._set_entry_fields_enabled(False)
        self._update_count()

    def _find_item(self, name):
        for i in range(self.list_files.count()):
            it = self.list_files.item(i)
            if it.data(Qt.ItemDataRole.UserRole) == name:
                return it
        return None

    def _update_row_inplace(self, name):
        it = self._find_item(name)
        if it is not None:
            it.setText(self._row_text(name))

    def _update_count(self):
        c = lib.counts(self.library, self.lib_files)
        self.lbl_lib_count.setText(self._t(
            "lib_count", total=c["total"], done=c["done"], todo=c["todo"]))

    def _update_tag_completer(self):
        tags = lib.collect_tags(self.library)       # most used first
        if hasattr(self, "edit_tag"):
            for field in (self.edit_tag, self.edit_search):
                comp = QCompleter(tags, self)
                comp.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
                comp.setFilterMode(Qt.MatchFlag.MatchContains)
                comp.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
                field.setCompleter(comp)
        self._refresh_tag_filter(tags)

    def _refresh_tag_filter(self, tags=None):
        """Rebuild the tag filter, keeping the current choice when possible."""
        if not hasattr(self, "combo_tag"):
            return
        if tags is None:
            tags = lib.collect_tags(self.library)
        current = self.combo_tag.currentData()
        counts = lib.tag_counts(self.library)

        self.combo_tag.blockSignals(True)
        self.combo_tag.clear()
        self.combo_tag.addItem(self._t("filter_all_tags"), "")
        for t in tags:
            self.combo_tag.addItem(f"{t} ({counts.get(t, 0)})", t)
        if current:
            i = self.combo_tag.findData(current)
            if i >= 0:
                self.combo_tag.setCurrentIndex(i)
        self.combo_tag.blockSignals(False)

    # ── Library: selection + entry editing ───────────────────────────────────

    def _on_lib_selected(self, current, previous):
        # Single selection just fills the (cheap) tag fields; the audio is only
        # loaded on double-click to keep arrowing through 1000 files snappy.
        if current is None:
            self.current_lib_file = ""
            self._set_entry_fields_enabled(False)
            return
        name = current.data(Qt.ItemDataRole.UserRole)
        self.current_lib_file = name
        self._fill_entry_fields(name)
        self._set_entry_fields_enabled(True)

    def _on_lib_activated(self, item):
        # Double-click / Enter: load the file into the dubbing workflow
        if item is None:
            return
        name = item.data(Qt.ItemDataRole.UserRole)
        path = os.path.join(self.voice_folder, name)
        self._load_sdt_path(path)

    def _fill_entry_fields(self, name):
        entry = lib.get_entry(self.library, name)
        self._loading_entry = True
        self.chk_done.setChecked(bool(entry["done"]))
        self.edit_tag.setText(entry.get("tag", "") or "")
        self.edit_speaker.setText(entry.get("speaker", "") or "")
        self.edit_notes.setPlainText(entry.get("notes", "") or "")
        self._loading_entry = False

    def _set_entry_fields_enabled(self, on):
        for w in (self.chk_done, self.edit_tag, self.edit_speaker,
                  self.edit_notes, self.btn_save_entry):
            w.setEnabled(on)

    def _on_entry_edited(self, *args):
        # Auto-save on checkbox toggle / tag / speaker editing finished
        if self._loading_entry or not self.current_lib_file:
            return
        self._persist_entry_from_fields(refresh=self.sender() is self.chk_done)

    def _save_current_entry(self):
        if not self.current_lib_file:
            return
        self._persist_entry_from_fields(refresh=True)
        self.win.status.showMessage(self._t("lib_saved", name=self.current_lib_file))

    def _persist_entry_from_fields(self, refresh=False):
        if not self.current_lib_file:
            return
        if not self.db_folder:
            self.win.status.showMessage(self._t("lib_no_db"))
            return
        lib.set_entry(
            self.library, self.current_lib_file,
            done=self.chk_done.isChecked(),
            tag=self.edit_tag.text().strip(),
            speaker=self.edit_speaker.text().strip(),
            notes=self.edit_notes.toPlainText(),
        )
        lib.save_library(self.db_folder, self.library)
        self._update_tag_completer()
        if refresh:
            # done-state may change filter membership → rebuild
            self._refresh_list()
        else:
            self._update_row_inplace(self.current_lib_file)
            self._update_count()

    def _cache_current_into_library(self, path):
        if not self.voice_folder or not self.sdt:
            return
        if os.path.normpath(os.path.dirname(path)) != os.path.normpath(self.voice_folder):
            return
        name = os.path.basename(path)
        lib.set_entry(
            self.library, name,
            channels=self.sdt.channels,
            duration=self.sdt.duration_seconds,
            size=len(self.sdt.raw),
            blocks=len(self.sdt.blocks),
            sample_rate=self.sdt.sample_rate,
        )
        self._quick_ch[name] = self.sdt.channels
        if self.db_folder:
            lib.save_library(self.db_folder, self.library)
        self._update_row_inplace(name)

    # ── Library: optional full folder scan (durations for every file) ────────

    def scan_folder(self):
        if not self.lib_files:
            return
        total = len(self.lib_files)
        dlg = QProgressDialog(self._t("lib_scanning", n=0, total=total),
                              "Cancel", 0, total, self)
        dlg.setWindowModality(Qt.WindowModality.WindowModal)
        dlg.setMinimumDuration(0)
        for i, name in enumerate(self.lib_files):
            if dlg.wasCanceled():
                break
            try:
                md = lib.scan_metadata(os.path.join(self.voice_folder, name))
                lib.set_entry(self.library, name, **md)
                self._quick_ch[name] = md["channels"]
            except Exception:
                pass
            dlg.setValue(i + 1)
            dlg.setLabelText(self._t("lib_scanning", n=i + 1, total=total))
        dlg.close()
        if self.db_folder:
            lib.save_library(self.db_folder, self.library)
        self._refresh_list()

    def _prepare_preview(self):
        # Release and delete the previous temporary file
        old = self.preview_wav
        self.preview_wav = ""
        if old and os.path.exists(old):
            self._release_player()
            try:
                os.unlink(old)
            except Exception:
                pass  # on Windows the file may stay locked for a moment

        # Create the preview WAV in a properly closed file
        samples = core.sdt_to_pcm(self.sdt)
        fd, path = tempfile.mkstemp(suffix=".wav")
        os.close(fd)  # important: close the handle before Qt reads the file
        try:
            core.save_wav(samples, path, self.sdt.sample_rate, channels=self.sdt.channels)
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

    # ── Step 2: playback / export ────────────────────────────────────────────

    def _on_player_error(self, *args):
        # Possible signatures: (error) or (error, error_string)
        error = args[0] if args else None
        error_string = args[1] if len(args) > 1 else ""
        if error == QMediaPlayer.Error.NoError:
            return
        self.btn_play.setText("▶")
        self._want_play = False
        msg = error_string or "playback failed"
        self.win.status.showMessage(f"Audio: {msg}")

    def _seek(self, pos):
        self.player.setPosition(pos)

    def export_wav(self):
        if not self.sdt:
            return
        default_name = os.path.splitext(os.path.basename(self.sdt_path))[0] + ".wav"
        start_dir = self.dir_export or self.dir_open or os.path.expanduser("~")
        path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_export_wav"),
            os.path.join(start_dir, default_name), self._t("filter_wav"))
        if not path:
            return
        try:
            n = core.sdt_to_wav(self.sdt, path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"), str(e))
            return
        self.dir_export = os.path.dirname(path)
        self.win.cfg["dir_export"] = self.dir_export
        save_config(self.win.cfg)
        self.win.status.showMessage(self._t(
            "status_exported", name=os.path.basename(path), n=n))
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    # ── Step 3: dubbing ──────────────────────────────────────────────────────

    def pick_wav(self):
        start_dir = self.dir_dub or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_pick_wav"), start_dir, self._t("filter_wav"))
        if not path:
            return
        try:
            samples, rate = core.load_wav_mono(path, self.sdt.sample_rate)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_wav_read", e=e))
            return

        self.new_wav_path = path
        self.new_wav_samples = samples
        self.new_wav_rate = rate
        self.dir_dub = os.path.dirname(path)
        self.win.cfg["dir_dub"] = self.dir_dub
        save_config(self.win.cfg)

        self.lbl_wav.setText(os.path.basename(path))
        self._show_wav_info()
        self.btn_generate.setEnabled(True)
        self.win.status.showMessage(self._t(
            "status_dub_ready", name=os.path.basename(path)))

    def _show_wav_info(self):
        if self.new_wav_samples is None or not self.sdt:
            return
        dur = len(self.new_wav_samples) / self.sdt.sample_rate
        orig = self.sdt.duration_seconds
        diff = dur - orig
        if abs(diff) < 0.1:
            note = self._t("wav_same")
        else:
            longer = diff > 0
            comp = self._t("wav_longer") if longer else self._t("wav_shorter")
            action = self._t("wav_will_trim") if longer else self._t("wav_will_pad")
            note = f"{abs(diff):.1f}s {comp} → {action}"

        # Announce the actual re-encoding target: the dub matches the source
        # file's channel layout. On a stereo SDT the mono recording is placed
        # on both channels (see core.replace_audio), so say "stereo" here.
        if self.sdt.channels == 2:
            target = f"{self._t('unit_stereo')} ({self._t('wav_target_stereo_note')})"
        else:
            target = self._t("unit_mono")

        self.lbl_wav_info.setText(
            f"{self._t('wav_duration')} : {dur:.2f}s "
            f"({self._t('wav_original')} {orig:.2f}s · {note})\n"
            f"{self._t('wav_source')} : {self.new_wav_rate} Hz → "
            f"{self._t('wav_converted')} {self.sdt.sample_rate} Hz {target}")

    # ── Step 4: generation ───────────────────────────────────────────────────

    def generate_sdt(self):
        if not self.sdt or not self.new_wav_path:
            return

        # SAME name as the original (for the game), in the remembered output folder
        original_name = os.path.basename(self.sdt_path)
        start_dir = self.dir_save or os.path.expanduser("~")
        save_title = self._t("dlg_save_sdt")
        save_filter = self._t("filter_sdt")
        out_path, _ = QFileDialog.getSaveFileName(
            self, save_title,
            os.path.join(start_dir, original_name), save_filter)
        if not out_path:
            return

        self.btn_generate.setEnabled(False)
        self.win.status.showMessage(self._t("status_encoding"))
        QApplication.processEvents()

        try:
            samples, _ = core.load_wav_mono(self.new_wav_path, self.sdt.sample_rate)
            new_raw = core.replace_audio(self.sdt, samples)
            core.save_sdt(new_raw, out_path)
        except Exception as e:
            self.btn_generate.setEnabled(True)
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_generate", e=e))
            self.win.status.showMessage(self._t("status_gen_failed"))
            return

        self.btn_generate.setEnabled(True)
        self.dir_save = os.path.dirname(out_path)
        self.win.cfg["dir_save"] = self.dir_save
        save_config(self.win.cfg)

        self.lbl_result.setText(
            f"{self._t('result_ok')} : {os.path.basename(out_path)}\n"
            f"{self._t('result_detail', size=f'{len(new_raw):,}')}")
        self.win.status.showMessage(self._t(
            "status_done", name=os.path.basename(out_path)))
        QMessageBox.information(self, self._t("ok_dub_title"),
                                self._t("ok_dub_body", path=out_path))

    # ── Shutdown ─────────────────────────────────────────────────────────────
