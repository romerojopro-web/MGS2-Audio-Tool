#!/usr/bin/env python3
"""
i18n.py — User-interface strings in French, English and Spanish.

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

        "lib_title": "BIBLIOTHÈQUE",
        "tab_sdt": "SDT · DIALOGUES",
        "tab_sdx": "SDX · BRUITAGES",
        "sdx_open_title": "① OUVRIR UNE BANQUE SDX",
        "sdx_browse": "PARCOURIR…",
        "sdx_scan": "SCANNER LE JEU (TOUS LES STAGES)…",
        "sdx_stage_found": "Stages : {path}",
        "sdx_no_stage": ("Aucun fichier .sdx trouvé dans ce dossier.\n\n"
                         "Choisissez le dossier d'installation de MGS2 "
                         "(celui qui contient us\\stage)."),
        "sdx_scanning": "Scan des banques… {n}/{total}",
        "sdx_scan_done": "{banks} banques · {sounds} sons distincts",
        "sdx_group_count": "présent dans {n} banques",
        "sdx_replace_all": "REMPLACER DANS TOUTES LES BANQUES…",
        "sdx_confirm_all_title": "Remplacer partout ?",
        "sdx_confirm_all": ("Ce son est présent dans {n} banques.\n\n"
                            "Elles seront toutes modifiées sur le disque "
                            "(les originaux sont conservés en .bak).\n\nContinuer ?"),
        "sdx_done_all": "✓ {n} banques mises à jour (sauvegardes .bak créées)",
        "dlg_pick_stage": "Choisir le dossier du jeu MGS2",
        "sdx_no_file": "Aucune banque chargée",
        "sdx_list_title": "SONS DE LA BANQUE",
        "sdx_info_samples": "Sons",
        "sdx_info_region": "Zone audio",
        "sdx_count": "{n} sons · {bytes} octets d'audio",
        "sdx_select_hint": "Sélectionnez un son dans la liste",
        "sdx_listen_title": "② ÉCOUTER LE SON",
        "sdx_export": "EXPORTER EN WAV…",
        "sdx_replace_title": "③ REMPLACER PAR VOTRE SON (WAV)",
        "sdx_hint": ("La durée du son est figée : un WAV plus long sera tronqué, "
                     "un plus court complété par du silence. Conversion auto "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "CHOISIR UN WAV…",
        "sdx_no_wav": "Aucun WAV choisi",
        "sdx_gen_title": "④ GÉNÉRER LA BANQUE MODIFIÉE",
        "sdx_generate": "REMPLACER LE SON ET SAUVEGARDER…",
        "sdx_result": "✓ Banque générée — même taille ({size} octets)",
        "dlg_open_sdx": "Ouvrir une banque SDX",
        "dlg_save_sdx": "Sauvegarder la banque modifiée",
        "filter_sdx": "Banques SDX (*.sdx);;Tous les fichiers (*)",
        "sdx_status_loaded": "Chargé : {name} · {n} sons",
        "sdx_status_sample": "Son #{i} · {dur:.2f}s · {size} octets",
        "sdx_status_done": "Terminé : {name}",
        "sdx_warn_empty": "Cette banque ne contient aucun son exploitable.",        "lib_pick_voice": "DOSSIER DE VOIX…",
        "lib_pick_db": "DOSSIER DE BASE…",
        "lib_no_voice": "Aucun dossier de voix",
        "lib_no_db": "Base non définie",
        "lib_search": "Rechercher…",
        "lib_filter_all": "Tout",
        "filter_all_tags": "Toutes les étiquettes",
        "lib_filter_todo": "À faire",
        "lib_filter_done": "Fait",
        "lib_scan": "SCANNER LE DOSSIER",
        "lib_scanning": "Scan en cours… {n}/{total}",
        "lib_count": "{total} fichiers · {done} faits · {todo} à faire",
        "lib_done": "Doublé",
        "lib_tag": "Étiquette",
        "lib_tag_hint": "Soldat, Codec… (texte libre)",
        "lib_speaker": "Personnage",
        "lib_notes": "Notes / réplique",
        "lib_save_entry": "ENREGISTRER LA FICHE",
        "lib_saved": "Fiche enregistrée : {name}",
        "lib_select_hint": "Sélectionnez un fichier dans la liste",
        "dlg_pick_voice": "Choisir le dossier de voix",
        "dlg_pick_db": "Choisir le dossier de la base d'étiquetage",

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
        "warn_no_audio": "Ce fichier ne contient pas d'audio à éditer (0 bloc).",
        "warn_unsupported": "Codec non pris en charge (pas du PS-ADPCM) — ce fichier ne peut pas être édité.",
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

        "lib_title": "LIBRARY",
        "tab_sdt": "SDT · DIALOGUE",
        "tab_sdx": "SDX · SOUND FX",
        "sdx_open_title": "① OPEN AN SDX BANK",
        "sdx_browse": "BROWSE…",
        "sdx_scan": "SCAN THE GAME (ALL STAGES)…",
        "sdx_stage_found": "Stages: {path}",
        "sdx_no_stage": ("No .sdx file found in that folder.\n\n"
                         "Pick your MGS2 installation folder "
                         "(the one containing us\\stage)."),
        "sdx_scanning": "Scanning banks… {n}/{total}",
        "sdx_scan_done": "{banks} banks · {sounds} distinct sounds",
        "sdx_group_count": "present in {n} banks",
        "sdx_replace_all": "REPLACE IN EVERY BANK…",
        "sdx_confirm_all_title": "Replace everywhere?",
        "sdx_confirm_all": ("This sound appears in {n} banks.\n\n"
                            "All of them will be modified on disk "
                            "(originals are kept as .bak).\n\nContinue?"),
        "sdx_done_all": "✓ {n} banks updated (.bak backups created)",
        "dlg_pick_stage": "Choose your MGS2 game folder",
        "sdx_no_file": "No bank loaded",
        "sdx_list_title": "SOUNDS IN THE BANK",
        "sdx_info_samples": "Sounds",
        "sdx_info_region": "Audio region",
        "sdx_count": "{n} sounds · {bytes} bytes of audio",
        "sdx_select_hint": "Select a sound from the list",
        "sdx_listen_title": "② LISTEN TO THE SOUND",
        "sdx_export": "EXPORT TO WAV…",
        "sdx_replace_title": "③ REPLACE WITH YOUR SOUND (WAV)",
        "sdx_hint": ("The sound's length is fixed: a longer WAV is trimmed, a "
                     "shorter one is padded with silence. Converted automatically "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "CHOOSE A WAV…",
        "sdx_no_wav": "No WAV chosen",
        "sdx_gen_title": "④ GENERATE THE MODIFIED BANK",
        "sdx_generate": "REPLACE SOUND AND SAVE…",
        "sdx_result": "✓ Bank generated — same size ({size} bytes)",
        "dlg_open_sdx": "Open an SDX bank",
        "dlg_save_sdx": "Save the modified bank",
        "filter_sdx": "SDX banks (*.sdx);;All files (*)",
        "sdx_status_loaded": "Loaded: {name} · {n} sounds",
        "sdx_status_sample": "Sound #{i} · {dur:.2f}s · {size} bytes",
        "sdx_status_done": "Done: {name}",
        "sdx_warn_empty": "This bank contains no usable sound.",
        "lib_pick_voice": "VOICE FOLDER…",
        "lib_pick_db": "DATABASE FOLDER…",
        "lib_no_voice": "No voice folder",
        "lib_no_db": "Database not set",
        "lib_search": "Search…",
        "lib_filter_all": "All",
        "filter_all_tags": "All tags",
        "lib_filter_todo": "To do",
        "lib_filter_done": "Done",
        "lib_scan": "SCAN FOLDER",
        "lib_scanning": "Scanning… {n}/{total}",
        "lib_count": "{total} files · {done} done · {todo} to do",
        "lib_done": "Dubbed",
        "lib_tag": "Tag",
        "lib_tag_hint": "Soldier, Codec… (free text)",
        "lib_speaker": "Speaker",
        "lib_notes": "Notes / line",
        "lib_save_entry": "SAVE ENTRY",
        "lib_saved": "Entry saved: {name}",
        "lib_select_hint": "Select a file from the list",
        "dlg_pick_voice": "Choose the voice folder",
        "dlg_pick_db": "Choose the tagging database folder",

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
        "warn_no_audio": "This file has no audio to edit (0 blocks).",
        "warn_unsupported": "Unsupported codec (not PS-ADPCM) — this file can't be edited.",
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

        "lib_title": "BIBLIOTECA",
        "tab_sdt": "SDT · DIÁLOGOS",
        "tab_sdx": "SDX · EFECTOS",
        "sdx_open_title": "① ABRIR UN BANCO SDX",
        "sdx_browse": "EXAMINAR…",
        "sdx_scan": "ESCANEAR EL JUEGO (TODOS LOS STAGES)…",
        "sdx_stage_found": "Stages: {path}",
        "sdx_no_stage": ("No se encontró ningún archivo .sdx en esa carpeta.\n\n"
                         "Elige la carpeta de instalación de MGS2 "
                         "(la que contiene us\\stage)."),
        "sdx_scanning": "Escaneando bancos… {n}/{total}",
        "sdx_scan_done": "{banks} bancos · {sounds} sonidos distintos",
        "sdx_group_count": "presente en {n} bancos",
        "sdx_replace_all": "REEMPLAZAR EN TODOS LOS BANCOS…",
        "sdx_confirm_all_title": "¿Reemplazar en todos?",
        "sdx_confirm_all": ("Este sonido aparece en {n} bancos.\n\n"
                            "Todos se modificarán en el disco "
                            "(los originales se guardan como .bak).\n\n¿Continuar?"),
        "sdx_done_all": "✓ {n} bancos actualizados (copias .bak creadas)",
        "dlg_pick_stage": "Elegir la carpeta del juego MGS2",
        "sdx_no_file": "Ningún banco cargado",
        "sdx_list_title": "SONIDOS DEL BANCO",
        "sdx_info_samples": "Sonidos",
        "sdx_info_region": "Zona de audio",
        "sdx_count": "{n} sonidos · {bytes} bytes de audio",
        "sdx_select_hint": "Selecciona un sonido de la lista",
        "sdx_listen_title": "② ESCUCHAR EL SONIDO",
        "sdx_export": "EXPORTAR A WAV…",
        "sdx_replace_title": "③ REEMPLAZAR CON TU SONIDO (WAV)",
        "sdx_hint": ("La duración del sonido es fija: un WAV más largo se recorta, "
                     "uno más corto se completa con silencio. Conversión automática "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "ELEGIR UN WAV…",
        "sdx_no_wav": "Ningún WAV elegido",
        "sdx_gen_title": "④ GENERAR EL BANCO MODIFICADO",
        "sdx_generate": "REEMPLAZAR SONIDO Y GUARDAR…",
        "sdx_result": "✓ Banco generado — mismo tamaño ({size} bytes)",
        "dlg_open_sdx": "Abrir un banco SDX",
        "dlg_save_sdx": "Guardar el banco modificado",
        "filter_sdx": "Bancos SDX (*.sdx);;Todos los archivos (*)",
        "sdx_status_loaded": "Cargado: {name} · {n} sonidos",
        "sdx_status_sample": "Sonido #{i} · {dur:.2f}s · {size} bytes",
        "sdx_status_done": "Hecho: {name}",
        "sdx_warn_empty": "Este banco no contiene ningún sonido utilizable.",
        "lib_pick_voice": "CARPETA DE VOCES…",
        "lib_pick_db": "CARPETA DE BASE…",
        "lib_no_voice": "Ninguna carpeta de voces",
        "lib_no_db": "Base no definida",
        "lib_search": "Buscar…",
        "lib_filter_all": "Todo",
        "filter_all_tags": "Todas las etiquetas",
        "lib_filter_todo": "Pendiente",
        "lib_filter_done": "Hecho",
        "lib_scan": "ESCANEAR CARPETA",
        "lib_scanning": "Escaneando… {n}/{total}",
        "lib_count": "{total} archivos · {done} hechos · {todo} pendientes",
        "lib_done": "Doblado",
        "lib_tag": "Etiqueta",
        "lib_tag_hint": "Soldado, Códec… (texto libre)",
        "lib_speaker": "Personaje",
        "lib_notes": "Notas / línea",
        "lib_save_entry": "GUARDAR FICHA",
        "lib_saved": "Ficha guardada: {name}",
        "lib_select_hint": "Selecciona un archivo de la lista",
        "dlg_pick_voice": "Elegir la carpeta de voces",
        "dlg_pick_db": "Elegir la carpeta de la base de etiquetado",

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
        "warn_no_audio": "Este archivo no tiene audio para editar (0 bloques).",
        "warn_unsupported": "Códec no compatible (no es PS-ADPCM) — este archivo no se puede editar.",
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
