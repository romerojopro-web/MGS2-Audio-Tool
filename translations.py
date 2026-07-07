#!/usr/bin/env python3
"""
translations.py — User-interface strings in French, English and Spanish.

Each language is a dictionary sharing the same keys. The tr() helper returns
the string for the current language, falling back to French if a key is missing.

Note: these dictionaries are the *interface* text and are intentionally kept
multilingual. Everything else in the codebase (comments, docstrings, internal
messages) is in English.
"""

TRANSLATIONS = {
    "fr": {
        "lang_name": "Français",
        "window_title": "MGS2 SDT Tool — Doublage",
        "app_title": "MGS2 · SDT TOOL",
        "app_subtitle": "EXTRACTION & DOUBLAGE — MASTER COLLECTION (PC)",
        "language_label": "Langue :",

        "step1_title": "① OUVRIR UN FICHIER SDT",
        "browse": "PARCOURIR…",
        "no_file": "Aucun fichier chargé",

        "info_file": "Fichier",
        "info_size": "Taille",
        "info_rate": "Fréquence",
        "info_blocks": "Blocs audio",
        "info_duration": "Durée",
        "unit_bytes": "octets",
        "unit_mono": "mono",
        "unit_stereo": "stéréo",
        "unit_seconds": "s",

        "step2_title": "② ÉCOUTER LE DIALOGUE ORIGINAL",
        "export_wav": "EXPORTER EN WAV…",

        "step3_title": "③ CHOISIR VOTRE DOUBLAGE (WAV)",
        "step3_hint": ("Enregistrez votre voix, idéalement à la même durée que "
                       "l'original. Le WAV sera converti automatiquement "
                       "(44100 Hz) pour correspondre au fichier."),
        "wav_target_stereo_note": "votre voix sera placée sur les deux canaux",
        "pick_wav": "CHOISIR UN WAV…",
        "no_wav": "Aucun WAV choisi",
        "wav_duration": "Durée",
        "wav_original": "original",
        "wav_same": "identique",
        "wav_longer": "plus longue",
        "wav_shorter": "plus courte",
        "wav_will_trim": "sera tronquée",
        "wav_will_pad": "sera complétée par du silence",
        "wav_source": "Source",
        "wav_converted": "converti en",
        "wav_mono": "mono",

        "step4_title": "④ GÉNÉRER LE SDT MODIFIÉ",
        "generate": "REMPLACER L'AUDIO ET SAUVEGARDER…",
        "result_ok": "✓ Fichier généré",
        "result_detail": ("Même taille que l'original ({size} octets) — "
                          "prêt à remettre dans le jeu."),

        "dlg_open_sdt": "Ouvrir un fichier SDT",
        "dlg_export_wav": "Exporter en WAV",
        "dlg_pick_wav": "Choisir votre doublage WAV",
        "dlg_save_sdt": "Sauvegarder le SDT modifié",
        "filter_sdt": "Fichiers SDT (*.sdt);;Tous les fichiers (*)",
        "filter_wav": "Fichiers WAV (*.wav);;Tous les fichiers (*)",

        "status_ready": "Prêt · Ouvrez un fichier .sdt du jeu pour commencer",
        "status_loaded": "Chargé : {name} · {dur:.1f}s · {blocks} blocs",
        "status_exported": "Exporté : {name} ({n} samples)",
        "status_dub_ready": "Doublage prêt : {name}",
        "status_encoding": "Encodage PS-ADPCM en cours…",
        "status_done": "Terminé : {name}",
        "status_gen_failed": "Échec de la génération",

        "err_title": "Erreur",
        "err_read": "Lecture impossible :\n{e}",
        "err_wav_read": "WAV illisible :\n{e}",
        "err_generate": "Génération impossible :\n{e}",
        "ok_export_title": "Export réussi",
        "ok_export_body": "WAV enregistré :\n{path}",
        "ok_dub_title": "Doublage terminé",
        "ok_dub_body": ("Le fichier SDT modifié a été enregistré :\n{path}\n\n"
                        "Remplacez le fichier original du jeu par celui-ci "
                        "(pensez à faire une sauvegarde de l'original)."),
    },

    "en": {
        "lang_name": "English",
        "window_title": "MGS2 SDT Tool — Dubbing",
        "app_title": "MGS2 · SDT TOOL",
        "app_subtitle": "EXTRACTION & DUBBING — MASTER COLLECTION (PC)",
        "language_label": "Language:",

        "step1_title": "① OPEN AN SDT FILE",
        "browse": "BROWSE…",
        "no_file": "No file loaded",

        "info_file": "File",
        "info_size": "Size",
        "info_rate": "Sample rate",
        "info_blocks": "Audio blocks",
        "info_duration": "Duration",
        "unit_bytes": "bytes",
        "unit_mono": "mono",
        "unit_stereo": "stereo",
        "unit_seconds": "s",

        "step2_title": "② LISTEN TO THE ORIGINAL DIALOGUE",
        "export_wav": "EXPORT TO WAV…",

        "step3_title": "③ CHOOSE YOUR DUB (WAV)",
        "step3_hint": ("Record your voice, ideally at the same length as the "
                       "original. The WAV is converted automatically "
                       "(44100 Hz) to match the file."),
        "wav_target_stereo_note": "your voice will be placed on both channels",
        "pick_wav": "CHOOSE A WAV…",
        "no_wav": "No WAV chosen",
        "wav_duration": "Length",
        "wav_original": "original",
        "wav_same": "identical",
        "wav_longer": "longer",
        "wav_shorter": "shorter",
        "wav_will_trim": "will be trimmed",
        "wav_will_pad": "will be padded with silence",
        "wav_source": "Source",
        "wav_converted": "converted to",
        "wav_mono": "mono",

        "step4_title": "④ GENERATE THE MODIFIED SDT",
        "generate": "REPLACE AUDIO AND SAVE…",
        "result_ok": "✓ File generated",
        "result_detail": ("Same size as the original ({size} bytes) — "
                          "ready to put back into the game."),

        "dlg_open_sdt": "Open an SDT file",
        "dlg_export_wav": "Export to WAV",
        "dlg_pick_wav": "Choose your dub WAV",
        "dlg_save_sdt": "Save the modified SDT",
        "filter_sdt": "SDT files (*.sdt);;All files (*)",
        "filter_wav": "WAV files (*.wav);;All files (*)",

        "status_ready": "Ready · Open a game .sdt file to begin",
        "status_loaded": "Loaded: {name} · {dur:.1f}s · {blocks} blocks",
        "status_exported": "Exported: {name} ({n} samples)",
        "status_dub_ready": "Dub ready: {name}",
        "status_encoding": "Encoding PS-ADPCM…",
        "status_done": "Done: {name}",
        "status_gen_failed": "Generation failed",

        "err_title": "Error",
        "err_read": "Cannot read file:\n{e}",
        "err_wav_read": "Unreadable WAV:\n{e}",
        "err_generate": "Cannot generate:\n{e}",
        "ok_export_title": "Export successful",
        "ok_export_body": "WAV saved:\n{path}",
        "ok_dub_title": "Dub complete",
        "ok_dub_body": ("The modified SDT file has been saved:\n{path}\n\n"
                        "Replace the game's original file with this one "
                        "(remember to back up the original)."),
    },

    "es": {
        "lang_name": "Español",
        "window_title": "MGS2 SDT Tool — Doblaje",
        "app_title": "MGS2 · SDT TOOL",
        "app_subtitle": "EXTRACCIÓN Y DOBLAJE — MASTER COLLECTION (PC)",
        "language_label": "Idioma:",

        "step1_title": "① ABRIR UN ARCHIVO SDT",
        "browse": "EXAMINAR…",
        "no_file": "Ningún archivo cargado",

        "info_file": "Archivo",
        "info_size": "Tamaño",
        "info_rate": "Frecuencia",
        "info_blocks": "Bloques de audio",
        "info_duration": "Duración",
        "unit_bytes": "bytes",
        "unit_mono": "mono",
        "unit_stereo": "estéreo",
        "unit_seconds": "s",

        "step2_title": "② ESCUCHAR EL DIÁLOGO ORIGINAL",
        "export_wav": "EXPORTAR A WAV…",

        "step3_title": "③ ELEGIR TU DOBLAJE (WAV)",
        "step3_hint": ("Graba tu voz, idealmente con la misma duración que el "
                       "original. El WAV se convierte automáticamente "
                       "(44100 Hz) para coincidir con el archivo."),
        "wav_target_stereo_note": "tu voz se colocará en ambos canales",
        "pick_wav": "ELEGIR UN WAV…",
        "no_wav": "Ningún WAV elegido",
        "wav_duration": "Duración",
        "wav_original": "original",
        "wav_same": "idéntica",
        "wav_longer": "más larga",
        "wav_shorter": "más corta",
        "wav_will_trim": "se recortará",
        "wav_will_pad": "se completará con silencio",
        "wav_source": "Fuente",
        "wav_converted": "convertido a",
        "wav_mono": "mono",

        "step4_title": "④ GENERAR EL SDT MODIFICADO",
        "generate": "REEMPLAZAR AUDIO Y GUARDAR…",
        "result_ok": "✓ Archivo generado",
        "result_detail": ("Mismo tamaño que el original ({size} bytes) — "
                          "listo para volver al juego."),

        "dlg_open_sdt": "Abrir un archivo SDT",
        "dlg_export_wav": "Exportar a WAV",
        "dlg_pick_wav": "Elegir tu WAV de doblaje",
        "dlg_save_sdt": "Guardar el SDT modificado",
        "filter_sdt": "Archivos SDT (*.sdt);;Todos los archivos (*)",
        "filter_wav": "Archivos WAV (*.wav);;Todos los archivos (*)",

        "status_ready": "Listo · Abre un archivo .sdt del juego para empezar",
        "status_loaded": "Cargado: {name} · {dur:.1f}s · {blocks} bloques",
        "status_exported": "Exportado: {name} ({n} muestras)",
        "status_dub_ready": "Doblaje listo: {name}",
        "status_encoding": "Codificando PS-ADPCM…",
        "status_done": "Hecho: {name}",
        "status_gen_failed": "Falló la generación",

        "err_title": "Error",
        "err_read": "No se puede leer el archivo:\n{e}",
        "err_wav_read": "WAV ilegible:\n{e}",
        "err_generate": "No se puede generar:\n{e}",
        "ok_export_title": "Exportación exitosa",
        "ok_export_body": "WAV guardado:\n{path}",
        "ok_dub_title": "Doblaje completado",
        "ok_dub_body": ("El archivo SDT modificado se ha guardado:\n{path}\n\n"
                        "Reemplaza el archivo original del juego por este "
                        "(recuerda hacer una copia de seguridad del original)."),
    },
}

LANGUAGE_ORDER = ["fr", "en", "es"]


def tr(lang: str, key: str, **kwargs) -> str:
    """Return a translated string; fall back to French if the key is missing."""
    text = TRANSLATIONS.get(lang, {}).get(key)
    if text is None:
        text = TRANSLATIONS["fr"].get(key, key)
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, IndexError):
            return text
    return text
