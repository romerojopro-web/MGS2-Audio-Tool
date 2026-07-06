#!/usr/bin/env python3
"""
sdt_tool.py — Interface graphique pour le doublage des dialogues de
              Metal Gear Solid 2 (Master Collection, PC).

Nouveautés v2 :
  • Dossiers par défaut mémorisés pour chaque section (retenus d'une
    session à l'autre) : moins de navigation, un clic suffit.
  • Le SDT généré conserve exactement le nom du fichier original
    (nécessaire pour le jeu) — plus de suffixe « _fr ».
  • Interface multilingue : Français / English / Español.
  • Affichage des métadonnées revu (grille lisible, plus à l'étroit).

Dépendances : PyQt6 (le moteur sdt_core.py est en Python pur).
"""

import os
import sys
import json
import tempfile

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QMessageBox, QSlider,
    QStatusBar, QSizePolicy, QGridLayout, QComboBox,
)
from PyQt6.QtCore import Qt, QUrl
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

import sdt_core as core
from translations import tr, LANGUAGE_ORDER, TRANSLATIONS


# Fichier de configuration (chemins mémorisés + langue), dans le dossier utilisateur
CONFIG_PATH = os.path.join(
    os.path.expanduser("~"), ".mgs2_sdt_tool.json")


# ─────────────────────────────────────────────────────────────────────────────
# Thème visuel — écran tactique / Codec (vert-cyan sur noir)
# ─────────────────────────────────────────────────────────────────────────────

STYLE = """
* { font-family: 'Consolas', 'DejaVu Sans Mono', monospace; }

QMainWindow, QWidget { background-color: #04100c; color: #7fe0b0; }

QLabel#title { color: #4dffb0; font-size: 20px; font-weight: bold; letter-spacing: 4px; }
QLabel#subtitle { color: #2f7a5a; font-size: 10px; letter-spacing: 3px; }
QLabel#step { color: #4dffb0; font-size: 12px; font-weight: bold; letter-spacing: 1px; }
QLabel#body { color: #7fe0b0; font-size: 11px; }
QLabel#dim  { color: #3f8060; font-size: 10px; }
QLabel#value { color: #b8ffdc; font-size: 12px; }
QLabel#metakey { color: #3f8060; font-size: 11px; }
QLabel#metaval { color: #b8ffdc; font-size: 11px; }

QFrame#card { background-color: #061a12; border: 1px solid #123a28; border-radius: 3px; }
QFrame#metabox { background-color: #04140e; border: 1px solid #0e2c1e; border-radius: 2px; }
QFrame#sep { background-color: #123a28; max-height: 1px; }

QPushButton {
    background-color: #06251a; color: #4dffb0;
    border: 1px solid #1c5c40; border-radius: 2px;
    padding: 9px 16px; font-size: 11px; letter-spacing: 1px;
}
QPushButton:hover { background-color: #0a3626; border-color: #4dffb0; color: #86ffcb; }
QPushButton:pressed { background-color: #4dffb0; color: #04100c; }
QPushButton:disabled { background-color: #04140e; color: #245038; border-color: #143424; }

QPushButton#primary { background-color: #0a3626; border-color: #4dffb0; font-weight: bold; }
QPushButton#primary:hover { background-color: #0e4a34; }

QPushButton#play {
    background-color: #06251a; border-color: #1c5c40;
    min-width: 44px; max-width: 44px; font-size: 14px;
}

QComboBox {
    background-color: #06251a; color: #86ffcb;
    border: 1px solid #1c5c40; border-radius: 2px;
    padding: 4px 8px; font-size: 11px; min-width: 110px;
}
QComboBox:hover { border-color: #4dffb0; }
QComboBox QAbstractItemView {
    background-color: #061a12; color: #7fe0b0;
    selection-background-color: #0a3626; selection-color: #86ffcb;
    border: 1px solid #1c5c40;
}

QStatusBar {
    background-color: #020a07; border-top: 1px solid #123a28;
    color: #3f8060; font-size: 10px;
}

QSlider::groove:horizontal { height: 4px; background: #123a28; border-radius: 2px; }
QSlider::sub-page:horizontal { background: #4dffb0; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #4dffb0; width: 10px; height: 10px; margin: -4px 0; border-radius: 5px;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Gestion de la configuration persistante
# ─────────────────────────────────────────────────────────────────────────────

def load_config() -> dict:
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(cfg: dict):
    try:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass  # échec silencieux : les réglages ne sont pas critiques


# ─────────────────────────────────────────────────────────────────────────────
# Fenêtre principale
# ─────────────────────────────────────────────────────────────────────────────

class SDTToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.cfg = load_config()
        self.lang = self.cfg.get("language", "fr")
        if self.lang not in TRANSLATIONS:
            self.lang = "fr"

        # Dossiers mémorisés par section
        self.dir_open = self.cfg.get("dir_open", "")
        self.dir_export = self.cfg.get("dir_export", "")
        self.dir_dub = self.cfg.get("dir_dub", "")
        self.dir_save = self.cfg.get("dir_save", "")

        # État
        self.sdt: core.SDTFile | None = None
        self.sdt_path = ""
        self.new_wav_path = ""
        self.preview_wav = ""
        self.new_wav_samples = None
        self.new_wav_rate = 0

        # Lecteur audio
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(0.9)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)

        self._build_ui()
        self.setStyleSheet(STYLE)
        self._retranslate()

    # ── Construction ────────────────────────────────────────────────────────

    def _build_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(14)

        # En-tête + sélecteur de langue
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
        root.addLayout(top)

        sep = QFrame(); sep.setObjectName("sep"); sep.setFrameShape(QFrame.Shape.HLine)
        root.addWidget(sep)

        root.addWidget(self._build_step1())
        root.addWidget(self._build_step2())
        root.addWidget(self._build_step3())
        root.addWidget(self._build_step4())
        root.addStretch()

        self.status = QStatusBar()
        self.setStatusBar(self.status)

    def _card(self):
        f = QFrame(); f.setObjectName("card")
        return f

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

        # Boîte de métadonnées en grille (lisible, aérée)
        self.metabox = QFrame(); self.metabox.setObjectName("metabox")
        self.metabox.setVisible(False)
        grid = QGridLayout(self.metabox)
        grid.setContentsMargins(14, 12, 14, 12)
        grid.setHorizontalSpacing(18)
        grid.setVerticalSpacing(7)
        grid.setColumnStretch(1, 1)

        # 5 lignes : clé (droite) + valeur (gauche)
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

    # ── Traduction dynamique ────────────────────────────────────────────────

    def _t(self, key, **kw):
        return tr(self.lang, key, **kw)

    def _retranslate(self):
        self.setWindowTitle(self._t("window_title"))
        self.lbl_title.setText(self._t("app_title"))
        self.lbl_subtitle.setText(self._t("app_subtitle"))
        self.lbl_lang.setText(self._t("language_label"))

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

        # Rafraîchir les infos si un fichier est chargé
        if self.sdt:
            self._show_metadata()
            if self.new_wav_path:
                self._show_wav_info()

        if not self.sdt:
            self.status.showMessage(self._t("status_ready"))

    def _on_language_changed(self, index):
        self.lang = self.combo_lang.itemData(index)
        self.cfg["language"] = self.lang
        save_config(self.cfg)
        self._retranslate()

    # ── Affichage des métadonnées (grille) ──────────────────────────────────

    def _show_metadata(self):
        if not self.sdt:
            return
        md = core.metadata(self.sdt)
        rows = [
            (self._t("info_file"), md["file"]),
            (self._t("info_size"), f"{md['size']:,} {self._t('unit_bytes')}"),
            (self._t("info_rate"), f"{md['sample_rate']} Hz ({self._t('unit_mono')})"),
            (self._t("info_blocks"), str(md["blocks"])),
            (self._t("info_duration"), f"{md['duration']:.2f} {self._t('unit_seconds')}"),
        ]
        for i, (k, v) in enumerate(rows):
            self.meta_keys[i].setText(k + " :")
            self.meta_vals[i].setText(v)
        self.metabox.setVisible(True)

    # ── Étape 1 : ouverture ─────────────────────────────────────────────────

    def open_sdt(self):
        start_dir = self.dir_open or os.path.expanduser("~")
        path, _ = QFileDialog.getOpenFileName(
            self, self._t("dlg_open_sdt"), start_dir, self._t("filter_sdt"))
        if not path:
            return

        try:
            self.sdt = core.parse_sdt(path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_read", e=e))
            return

        self.sdt_path = path
        self.dir_open = os.path.dirname(path)
        self.cfg["dir_open"] = self.dir_open
        save_config(self.cfg)

        self.new_wav_path = ""
        self.new_wav_samples = None
        self.lbl_wav.setText(self._t("no_wav"))
        self.lbl_wav_info.setText("")
        self.lbl_result.setText("")

        self.lbl_file.setText(os.path.basename(path))
        self._show_metadata()
        self._prepare_preview()

        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_pick_wav.setEnabled(True)

        self.status.showMessage(self._t(
            "status_loaded", name=os.path.basename(path),
            dur=self.sdt.duration_seconds, blocks=len(self.sdt.blocks)))

    def _prepare_preview(self):
        if self.preview_wav and os.path.exists(self.preview_wav):
            try:
                self.player.setSource(QUrl())
                os.unlink(self.preview_wav)
            except Exception:
                pass
        fd, self.preview_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        samples = core.sdt_to_pcm(self.sdt)
        core.save_wav(samples, self.preview_wav, self.sdt.sample_rate)
        self.player.setSource(QUrl.fromLocalFile(self.preview_wav))
        self.btn_play.setText("▶")

    # ── Étape 2 : lecture / export ──────────────────────────────────────────

    def toggle_play(self):
        if self.player.playbackState() == QMediaPlayer.PlaybackState.PlayingState:
            self.player.pause()
            self.btn_play.setText("▶")
        else:
            self.player.play()
            self.btn_play.setText("⏸")

    def _on_position(self, pos):
        if not self.slider.isSliderDown():
            self.slider.setValue(pos)
        self._update_time(pos, self.player.duration())
        if (self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState
                and self.player.duration() > 0 and pos >= self.player.duration()):
            self.btn_play.setText("▶")

    def _on_duration(self, dur):
        self.slider.setRange(0, dur)
        self._update_time(self.player.position(), dur)

    def _seek(self, pos):
        self.player.setPosition(pos)

    def _update_time(self, pos, dur):
        def fmt(ms):
            s = ms // 1000
            return f"{s//60}:{s%60:02d}"
        self.lbl_time.setText(f"{fmt(pos)} / {fmt(dur)}")

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
        self.cfg["dir_export"] = self.dir_export
        save_config(self.cfg)
        self.status.showMessage(self._t(
            "status_exported", name=os.path.basename(path), n=n))
        QMessageBox.information(self, self._t("ok_export_title"),
                                self._t("ok_export_body", path=path))

    # ── Étape 3 : doublage ──────────────────────────────────────────────────

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
        self.cfg["dir_dub"] = self.dir_dub
        save_config(self.cfg)

        self.lbl_wav.setText(os.path.basename(path))
        self._show_wav_info()
        self.btn_generate.setEnabled(True)
        self.status.showMessage(self._t(
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
        self.lbl_wav_info.setText(
            f"{self._t('wav_duration')} : {dur:.2f}s "
            f"({self._t('wav_original')} {orig:.2f}s · {note})\n"
            f"{self._t('wav_source')} : {self.new_wav_rate} Hz → "
            f"{self._t('wav_converted')} {self.sdt.sample_rate} Hz "
            f"{self._t('wav_mono')}")

    # ── Étape 4 : génération ────────────────────────────────────────────────

    def generate_sdt(self):
        if not self.sdt or not self.new_wav_path:
            return

        # Nom IDENTIQUE à l'original (pour le jeu), dans le dossier de sortie mémorisé
        original_name = os.path.basename(self.sdt_path)
        start_dir = self.dir_save or os.path.expanduser("~")
        out_path, _ = QFileDialog.getSaveFileName(
            self, self._t("dlg_save_sdt"),
            os.path.join(start_dir, original_name), self._t("filter_sdt"))
        if not out_path:
            return

        self.status.showMessage(self._t("status_encoding"))
        QApplication.processEvents()

        try:
            samples, _ = core.load_wav_mono(self.new_wav_path, self.sdt.sample_rate)
            new_raw = core.replace_audio(self.sdt, samples)
            core.save_sdt(new_raw, out_path)
        except Exception as e:
            QMessageBox.critical(self, self._t("err_title"),
                                 self._t("err_generate", e=e))
            self.status.showMessage(self._t("status_gen_failed"))
            return

        self.dir_save = os.path.dirname(out_path)
        self.cfg["dir_save"] = self.dir_save
        save_config(self.cfg)

        self.lbl_result.setText(
            f"{self._t('result_ok')} : {os.path.basename(out_path)}\n"
            f"{self._t('result_detail', size=f'{len(new_raw):,}')}")
        self.status.showMessage(self._t(
            "status_done", name=os.path.basename(out_path)))
        QMessageBox.information(self, self._t("ok_dub_title"),
                                self._t("ok_dub_body", path=out_path))

    # ── Fermeture ───────────────────────────────────────────────────────────

    def closeEvent(self, event):
        if self.preview_wav and os.path.exists(self.preview_wav):
            try:
                self.player.setSource(QUrl())
                os.unlink(self.preview_wav)
            except Exception:
                pass
        super().closeEvent(event)


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("MGS2 SDT Tool")
    win = SDTToolWindow()
    win.resize(720, 680)
    win.setMinimumSize(720, 660)
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
