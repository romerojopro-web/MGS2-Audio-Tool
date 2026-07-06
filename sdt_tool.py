#!/usr/bin/env python3
"""
sdt_tool.py — Interface graphique pour le doublage des dialogues de
              Metal Gear Solid 2 (Master Collection, PC).

Workflow prévu :
  1. Ouvrir un fichier .sdt du jeu.
  2. L'écouter / l'exporter en WAV pour identifier la réplique et sa durée.
  3. Enregistrer sa propre voix en WAV.
  4. Remplacer l'audio du .sdt par le nouveau WAV.
  5. Sauvegarder le .sdt modifié, prêt à être remis dans le jeu.

Dépendances : PyQt6 uniquement (le moteur sdt_core.py est en Python pur).
"""

import os
import sys
import struct
import tempfile

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFileDialog, QFrame, QMessageBox, QSlider,
    QStatusBar, QSizePolicy, QGridLayout,
)
from PyQt6.QtCore import Qt, QUrl, QTimer
from PyQt6.QtGui import QFont
from PyQt6.QtMultimedia import QMediaPlayer, QAudioOutput

import sdt_core as core


# ─────────────────────────────────────────────────────────────────────────────
# Thème visuel — inspiré des écrans tactiques MGS (Codec / vert-cyan sur noir)
# ─────────────────────────────────────────────────────────────────────────────

STYLE = """
* { font-family: 'Consolas', 'DejaVu Sans Mono', monospace; }

QMainWindow, QWidget { background-color: #04100c; color: #7fe0b0; }

QLabel#title {
    color: #4dffb0; font-size: 20px; font-weight: bold; letter-spacing: 4px;
}
QLabel#subtitle { color: #2f7a5a; font-size: 10px; letter-spacing: 3px; }
QLabel#step { color: #4dffb0; font-size: 12px; font-weight: bold; letter-spacing: 1px; }
QLabel#body { color: #7fe0b0; font-size: 11px; }
QLabel#dim  { color: #3f8060; font-size: 10px; }
QLabel#value { color: #b8ffdc; font-size: 12px; }

QFrame#card {
    background-color: #061a12;
    border: 1px solid #123a28;
    border-radius: 3px;
}
QFrame#sep { background-color: #123a28; max-height: 1px; }

QPushButton {
    background-color: #06251a;
    color: #4dffb0;
    border: 1px solid #1c5c40;
    border-radius: 2px;
    padding: 9px 16px;
    font-size: 11px;
    letter-spacing: 1px;
}
QPushButton:hover { background-color: #0a3626; border-color: #4dffb0; color: #86ffcb; }
QPushButton:pressed { background-color: #4dffb0; color: #04100c; }
QPushButton:disabled { background-color: #04140e; color: #245038; border-color: #143424; }

QPushButton#primary {
    background-color: #0a3626; border-color: #4dffb0; font-weight: bold;
}
QPushButton#primary:hover { background-color: #0e4a34; }

QPushButton#play {
    background-color: #06251a; border-color: #1c5c40;
    min-width: 44px; max-width: 44px; font-size: 14px;
}

QStatusBar {
    background-color: #020a07; border-top: 1px solid #123a28;
    color: #3f8060; font-size: 10px;
}

QSlider::groove:horizontal {
    height: 4px; background: #123a28; border-radius: 2px;
}
QSlider::sub-page:horizontal { background: #4dffb0; border-radius: 2px; }
QSlider::handle:horizontal {
    background: #4dffb0; width: 10px; height: 10px;
    margin: -4px 0; border-radius: 5px;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# Fenêtre principale
# ─────────────────────────────────────────────────────────────────────────────

class SDTToolWindow(QMainWindow):
    def __init__(self):
        super().__init__()

        self.sdt: core.SDTFile | None = None
        self.sdt_path = ""
        self.new_wav_path = ""
        self.preview_wav = ""          # WAV décodé temporaire pour l'écoute
        self.modified_raw: bytes | None = None

        # Lecteur audio pour la prévisualisation
        self.player = QMediaPlayer()
        self.audio_out = QAudioOutput()
        self.player.setAudioOutput(self.audio_out)
        self.audio_out.setVolume(0.9)
        self.player.positionChanged.connect(self._on_position)
        self.player.durationChanged.connect(self._on_duration)

        self._build_ui()
        self.setStyleSheet(STYLE)

    # ── Construction de l'interface ─────────────────────────────────────────

    def _build_ui(self):
        self.setWindowTitle("MGS2 SDT TOOL — Doublage")
        self.setMinimumSize(720, 640)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(20, 16, 20, 12)
        root.setSpacing(14)

        # En-tête
        header = QVBoxLayout()
        header.setSpacing(2)
        title = QLabel("MGS2 · SDT TOOL")
        title.setObjectName("title")
        sub = QLabel("EXTRACTION & DOUBLAGE — MASTER COLLECTION (PC)")
        sub.setObjectName("subtitle")
        header.addWidget(title)
        header.addWidget(sub)
        root.addLayout(header)

        root.addWidget(self._sep())

        # Étape 1 — Ouvrir un SDT
        root.addWidget(self._build_step1())

        # Étape 2 — Écouter / exporter
        root.addWidget(self._build_step2())

        # Étape 3 — Choisir le doublage
        root.addWidget(self._build_step3())

        # Étape 4 — Générer le SDT modifié
        root.addWidget(self._build_step4())

        root.addStretch()

        self.status = QStatusBar()
        self.setStatusBar(self.status)
        self.status.showMessage("Prêt · Ouvrez un fichier .sdt du jeu pour commencer")

    def _sep(self):
        f = QFrame()
        f.setObjectName("sep")
        f.setFrameShape(QFrame.Shape.HLine)
        return f

    def _card(self):
        f = QFrame()
        f.setObjectName("card")
        return f

    def _build_step1(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        lay.addWidget(self._label("① OUVRIR UN FICHIER SDT", "step"))
        row = QHBoxLayout()
        self.btn_open = QPushButton("PARCOURIR…")
        self.btn_open.setObjectName("primary")
        self.btn_open.clicked.connect(self.open_sdt)
        row.addWidget(self.btn_open)
        self.lbl_file = self._label("Aucun fichier chargé", "dim")
        self.lbl_file.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.lbl_file, 1)
        lay.addLayout(row)

        # Infos du fichier
        self.lbl_info = self._label("", "body")
        self.lbl_info.setWordWrap(True)
        lay.addWidget(self.lbl_info)
        return card

    def _build_step2(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        lay.addWidget(self._label("② ÉCOUTER LE DIALOGUE ORIGINAL", "step"))

        # Contrôles de lecture
        row = QHBoxLayout()
        self.btn_play = QPushButton("▶")
        self.btn_play.setObjectName("play")
        self.btn_play.setEnabled(False)
        self.btn_play.clicked.connect(self.toggle_play)
        row.addWidget(self.btn_play)

        self.slider = QSlider(Qt.Orientation.Horizontal)
        self.slider.setEnabled(False)
        self.slider.sliderMoved.connect(self._seek)
        row.addWidget(self.slider, 1)

        self.lbl_time = self._label("0:00 / 0:00", "value")
        self.lbl_time.setFixedWidth(90)
        self.lbl_time.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        row.addWidget(self.lbl_time)
        lay.addLayout(row)

        # Export WAV
        self.btn_export = QPushButton("EXPORTER EN WAV…")
        self.btn_export.setEnabled(False)
        self.btn_export.clicked.connect(self.export_wav)
        lay.addWidget(self.btn_export)
        return card

    def _build_step3(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        lay.addWidget(self._label("③ CHOISIR VOTRE DOUBLAGE (WAV)", "step"))
        hint = self._label(
            "Enregistrez votre voix, idéalement à la même durée que l'original. "
            "Le WAV sera converti automatiquement (mono, 44100 Hz).", "dim")
        hint.setWordWrap(True)
        lay.addWidget(hint)

        row = QHBoxLayout()
        self.btn_pick_wav = QPushButton("CHOISIR UN WAV…")
        self.btn_pick_wav.setEnabled(False)
        self.btn_pick_wav.clicked.connect(self.pick_wav)
        row.addWidget(self.btn_pick_wav)
        self.lbl_wav = self._label("Aucun WAV choisi", "dim")
        self.lbl_wav.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        row.addWidget(self.lbl_wav, 1)
        lay.addLayout(row)

        self.lbl_wav_info = self._label("", "body")
        self.lbl_wav_info.setWordWrap(True)
        lay.addWidget(self.lbl_wav_info)
        return card

    def _build_step4(self):
        card = self._card()
        lay = QVBoxLayout(card)
        lay.setContentsMargins(16, 12, 16, 12)
        lay.setSpacing(8)

        lay.addWidget(self._label("④ GÉNÉRER LE SDT MODIFIÉ", "step"))
        self.btn_generate = QPushButton("REMPLACER L'AUDIO ET SAUVEGARDER…")
        self.btn_generate.setObjectName("primary")
        self.btn_generate.setEnabled(False)
        self.btn_generate.clicked.connect(self.generate_sdt)
        lay.addWidget(self.btn_generate)

        self.lbl_result = self._label("", "value")
        self.lbl_result.setWordWrap(True)
        lay.addWidget(self.lbl_result)
        return card

    def _label(self, text, kind):
        lbl = QLabel(text)
        lbl.setObjectName(kind)
        return lbl

    # ── Étape 1 : ouverture ─────────────────────────────────────────────────

    def open_sdt(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Ouvrir un fichier SDT", "",
            "Fichiers SDT (*.sdt);;Tous les fichiers (*)")
        if not path:
            return

        try:
            self.sdt = core.parse_sdt(path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Lecture impossible :\n{e}")
            return

        self.sdt_path = path
        self.modified_raw = None
        self.new_wav_path = ""
        self.lbl_wav.setText("Aucun WAV choisi")
        self.lbl_wav_info.setText("")
        self.lbl_result.setText("")

        self.lbl_file.setText(os.path.basename(path))
        self.lbl_info.setText(core.describe(self.sdt))

        # Décoder pour la prévisualisation
        self._prepare_preview()

        # Activer la suite
        self.btn_play.setEnabled(True)
        self.slider.setEnabled(True)
        self.btn_export.setEnabled(True)
        self.btn_pick_wav.setEnabled(True)

        self.status.showMessage(
            f"Chargé : {os.path.basename(path)} · "
            f"{self.sdt.duration_seconds:.1f}s · {len(self.sdt.blocks)} blocs")

    def _prepare_preview(self):
        """Décode le SDT en WAV temporaire pour l'écoute."""
        if self.preview_wav and os.path.exists(self.preview_wav):
            try:
                os.unlink(self.preview_wav)
            except Exception:
                pass
        fd, self.preview_wav = tempfile.mkstemp(suffix=".wav")
        os.close(fd)
        samples = core.sdt_to_pcm(self.sdt)
        core.save_wav(samples, self.preview_wav, self.sdt.sample_rate)
        self.player.setSource(QUrl.fromLocalFile(self.preview_wav))

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
        if self.player.playbackState() != QMediaPlayer.PlaybackState.PlayingState \
           and pos >= self.player.duration() and self.player.duration() > 0:
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
        default = os.path.splitext(os.path.basename(self.sdt_path))[0] + ".wav"
        path, _ = QFileDialog.getSaveFileName(
            self, "Exporter en WAV", default, "Fichiers WAV (*.wav)")
        if not path:
            return
        try:
            n = core.sdt_to_wav(self.sdt, path)
            self.status.showMessage(f"Exporté : {os.path.basename(path)} ({n} samples)")
            QMessageBox.information(self, "Export réussi",
                                    f"WAV enregistré :\n{path}")
        except Exception as e:
            QMessageBox.critical(self, "Erreur", str(e))

    # ── Étape 3 : choix du doublage ─────────────────────────────────────────

    def pick_wav(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Choisir votre doublage WAV", "",
            "Fichiers WAV (*.wav);;Tous les fichiers (*)")
        if not path:
            return
        try:
            samples, rate = core.load_wav_mono(path, self.sdt.sample_rate)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"WAV illisible :\n{e}")
            return

        self.new_wav_path = path
        self.lbl_wav.setText(os.path.basename(path))

        dur = len(samples) / self.sdt.sample_rate
        orig = self.sdt.duration_seconds
        diff = dur - orig
        note = "identique" if abs(diff) < 0.1 else \
               (f"{abs(diff):.1f}s plus {'longue' if diff > 0 else 'courte'} "
                f"→ sera {'tronquée' if diff > 0 else 'complétée par du silence'}")
        self.lbl_wav_info.setText(
            f"Durée : {dur:.2f}s (original {orig:.2f}s · {note})\n"
            f"Source : {rate} Hz → converti en {self.sdt.sample_rate} Hz mono")

        self.btn_generate.setEnabled(True)
        self.status.showMessage(f"Doublage prêt : {os.path.basename(path)}")

    # ── Étape 4 : génération ────────────────────────────────────────────────

    def generate_sdt(self):
        if not self.sdt or not self.new_wav_path:
            return

        default = os.path.splitext(os.path.basename(self.sdt_path))[0] + "_fr.sdt"
        out_path, _ = QFileDialog.getSaveFileName(
            self, "Sauvegarder le SDT modifié", default,
            "Fichiers SDT (*.sdt)")
        if not out_path:
            return

        self.status.showMessage("Encodage PS-ADPCM en cours…")
        QApplication.processEvents()

        try:
            samples, _ = core.load_wav_mono(self.new_wav_path, self.sdt.sample_rate)
            new_raw = core.replace_audio(self.sdt, samples)
            core.save_sdt(new_raw, out_path)
        except Exception as e:
            QMessageBox.critical(self, "Erreur", f"Génération impossible :\n{e}")
            self.status.showMessage("Échec de la génération")
            return

        self.lbl_result.setText(
            f"✓ Fichier généré : {os.path.basename(out_path)}\n"
            f"  Même taille que l'original ({len(new_raw):,} octets) — "
            f"prêt à remettre dans le jeu.")
        self.status.showMessage(f"Terminé : {os.path.basename(out_path)}")
        QMessageBox.information(
            self, "Doublage terminé",
            f"Le fichier SDT modifié a été enregistré :\n{out_path}\n\n"
            f"Remplacez le fichier original du jeu par celui-ci "
            f"(pensez à faire une sauvegarde de l'original).")

    def closeEvent(self, event):
        # Nettoyer le WAV temporaire
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
    win.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
