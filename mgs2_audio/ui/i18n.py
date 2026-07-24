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
        "app_subtitle_mc": "EXTRACTION & DOUBLAGE — MASTER COLLECTION (PC)",
        "app_subtitle_substance": "EXTRACTION & DOUBLAGE — SUBSTANCE (2003)",
        "language_label": "Langue :",
        "mode_label": "Version :",
        "db_folder_label": "Base :",
        "mode_mc": "Master Collection",
        "mode_substance": "Substance (2003)",

        "lib_title": "BIBLIOTHÈQUE",
        "tab_sdt": "SDT · DIALOGUES",
        "tab_mcbgm": "MUSIQUE · BGM",
        "tab_sdx": "SDX · BRUITAGES",
        "tab_seq": "SÉQUENCEUR · CUES SDX",
        "tab_bgm": "MUSIQUE · BGM",
        "tab_vox": "VOX · VOIX",
        "tab_demos": "DÉMOS · CUTSCENES",
        "seq_open_title": "1 · OUVRIR UNE BANQUE",
        "seq_browse": "PARCOURIR…",
        "seq_no_file": "Aucune banque chargée",
        "seq_list_title": "MORCEAUX DE LA BANQUE",
        "seq_count": "{n} morceaux · {instruments} instruments",
        "seq_select_hint": "Sélectionnez un morceau dans la liste",
        "seq_filter_all": "Tous les morceaux",
        "seq_filter_music": "Au moins 8 notes",
        "seq_filter_long": "Au moins 20 notes",
        "seq_listen_title": "2 · ÉCOUTER LE MORCEAU",
        "seq_rendering": "Synthèse en cours…",
        "seq_export_title": "3 · EXPORTER",
        "seq_export": "EXPORTER EN WAV…",
        "seq_export_all": "EXPORTER TOUS LES MORCEAUX…",
        "seq_exporting": "Export… {n}/{total}",
        "seq_exported_all": "✓ {n} morceaux exportés",
        "seq_options_title": "4 · OPTIONS DE SYNTHÈSE",
        "seq_stereo": "Stéréo (panoramique)",
        "seq_tune": "Accorder les instruments (fidélité)",
        "seq_info": "Morceau #{i} · {tracks} piste(s) · {notes} notes",
        "seq_no_sequence": ("Cette banque ne contient pas de séquenceur "
                            "(pas de répertoire d\'instruments)."),
        "seq_hint": ("Deux sortes de banques partagent l\'extension .sdx : une banque "
                     "« musique » (256 cues, ~130-150 instruments) porte de vraies "
                     "pièces musicales ; une banque d\'effets porte surtout des SE "
                     "bruts du SPU. Une reverb logicielle est appliquée, mais le "
                     "preset exact du jeu n\'est pas stocké dans le fichier. "
                     "À noter : l\'onglet Musique · BGM ne concerne que la musique "
                     "du launcher, pas celle jouée en mission."),
        "bgm_list_title": "ENTRÉES DU FICHIER BGM",
        "bgm_browse": "PARCOURIR…",
        "bgm_no_file": "Aucune archive BGM chargée",
        "bgm_select_hint": "Sélectionnez une entrée dans la liste",
        "bgm_open_title": "1 · OUVRIR UNE ARCHIVE BGM",
        "bgm_hint": ("bgm.dat est une archive contenant les musiques pré-enregistrées "
                     "du jeu (BGM). Chaque entrée est codée en MS-ADPCM "
                     "(stéréo ou 4 canaux). Sélectionnez une entrée pour l\'écouter, "
                     "ou exportez-les toutes en WAV."),
        "bgm_listen_title": "2 · ÉCOUTER L\'ENTRÉE",
        "bgm_rendering": "Décodage en cours…",
        "bgm_export_title": "3 · EXPORTER",
        "bgm_export": "EXPORTER EN WAV…",
        "bgm_export_all": "EXPORTER TOUTES LES ENTRÉES…",
        "bgm_exporting": "Export… {n}/{total}",
        "bgm_exported_all": "✓ {n} entrées exportées",
        "bgm_count": "{n} entrées · {duration} d\'audio",
        "bgm_entry_info": "Entrée #{index} · {sr} Hz {ch}ch · {dur:.2f} s",
        "bgm_no_entries": "Ce fichier ne contient pas d\'entrée BGM.",
        "bgm_status_loaded": "Chargé : {name} · {n} entrées BGM",
        "dlg_open_bgm": "Ouvrir une archive BGM",
        "mcbgm_list_title": "MUSIQUES DU SCÉNARIO",
        "mcbgm_pick_game": "DOSSIER DU JEU (MC)…",
        "mcbgm_no_game": "Aucun dossier de jeu sélectionné",
        "mcbgm_hint": ("La musique du LAUNCHER de Master Collection vit dans "
                       "des AssetBundles Unity (un fichier .bundle par "
                       "morceau). Choisissez le dossier d\'installation du jeu "
                       "(celui qui contient launcher.exe) pour lister les 6 "
                       "morceaux du scénario plus la musique du menu et des "
                       "crédits, les écouter, les exporter — ou les remplacer "
                       "par vos propres WAV. Attention : ces fichiers ne "
                       "pilotent que le launcher, pas la musique en partie "
                       "(recherche en cours, voir docs/ORCHESTRATION.md)."),
        "mcbgm_select_hint": "Sélectionnez un morceau dans la liste",
        "mcbgm_no_unitypy": ("La librairie UnityPy est requise pour lire les "
                             "bundles Unity de Master Collection.\n"
                             "Installez-la avec :  pip install UnityPy"),
        "mcbgm_bad_folder": "Dossier de jeu invalide : {e}",
        "mcbgm_no_tracks": "Aucun morceau trouvé dans ce dossier.",
        "mcbgm_status_loaded": "✓ {n} musiques du scénario chargées",
        "mcbgm_count": "{n} morceaux · {duration} d\'audio",
        "mcbgm_track_title": "1 · MORCEAU",
        "mcbgm_track_info": "{name} · {sr} Hz {ch} · {dur:.1f} s",
        "mcbgm_rel_path": "Fichier dans le jeu : {path}",
        "mcbgm_listen_title": "2 · ÉCOUTER / EXPORTER",
        "mcbgm_rendering": "Extraction du bundle…",
        "mcbgm_ready": "Prêt : {name}",
        "mcbgm_export": "EXPORTER EN WAV…",
        "mcbgm_replace_title": "3 · REMPLACER (MODDING)",
        "mcbgm_pick_wav": "CHOISIR UN WAV…",
        "mcbgm_wav_info": ("{name} · {sr} Hz {ch}ch · {dur:.1f} s "
                           "(original : {orig:.1f} s)"),
        "mcbgm_generate": "GÉNÉRER LE BUNDLE…",
        "mcbgm_generating": "Reconstruction du bundle…",
        "mcbgm_generated": ("✓ Bundle généré : {path}\n"
                            "À placer dans le jeu à :\n{rel}"),
        "mcbgm_status_generated": "✓ Bundle généré : {name}",
        "mcbgm_use_install": ("Pour écrire directement dans le jeu, utilisez "
                              "le bouton INSTALLER (il crée d\'abord une "
                              "sauvegarde .bak)."),
        "mcbgm_install": "INSTALLER DANS LE JEU (.bak)",
        "mcbgm_install_title": "Installer dans le jeu",
        "mcbgm_install_confirm": ("Remplacer le fichier du jeu :\n{rel}\n\n"
                                  "L\'original sera conservé en .bak "
                                  "(s\'il n\'existe pas déjà), et la "
                                  "vérification CRC de ce bundle sera "
                                  "désactivée dans catalog.json (sauvegardé "
                                  "en .bak lui aussi).\n\nContinuer ?"),
        "mcbgm_installed": ("✓ Installé (original en .bak, CRC du catalogue "
                            "neutralisé) : {rel}"),
        "mcbgm_catalog_failed": ("Bundle installé, mais le patch du catalogue "
                                 "a échoué : {e}\nLe jeu refusera ce bundle "
                                 "tant que son CRC n\'est pas neutralisé dans "
                                 "catalog.json."),
        "dlg_pick_mc_game": "Choisir le dossier d\'installation de MGS2 Master Collection",
        "dlg_save_bundle": "Sauvegarder le bundle",
        "filter_bundle": "AssetBundles Unity (*.bundle);;Tous les fichiers (*)",
        "dlg_open_vox": "Ouvrir un fichier vox.dat",
        "dlg_open_demos": "Ouvrir un fichier demo.dat",
        "dlg_open_seq": "Ouvrir une banque SDX",
        "dlg_export_all": "Choisir le dossier d\'export",
        "seq_status_loaded": "Chargé : {name} · {n} morceaux",
        "dlg_save_script": "Sauvegarder le script",
        "dlg_open_script": "Ouvrir un script",
        "filter_script": "Script JSON (*.json);;Tous les fichiers (*)",
        "filter_dat": "Archives MGS2 (*.dat);;Tous les fichiers (*)",
        "vox_browse": "PARCOURIR\u2026",
        "vox_open_title": "1 \u00b7 OUVRIR UN FICHIER VOX.DAT",
        "vox_no_file": "Aucun vox.dat charg\u00e9",
        "vox_no_blocks": "Ce fichier ne contient pas de blocs audio.",
        "vox_select_hint": "S\u00e9lectionnez un bloc dans la liste",
        "vox_listen_title": "2 \u00b7 \u00c9COUTER LE BLOC",
        "vox_rendering": "D\u00e9codage en cours\u2026",
        "vox_export_title": "3 \u00b7 EXPORTER",
        "vox_export": "EXPORTER EN WAV\u2026",
        "vox_export_all": "EXPORTER TOUS LES BLOCS\u2026",
        "vox_exporting": "Export\u2026 {n}/{total}",
        "vox_exported_all": "\u2713 {n} blocs export\u00e9s",
        "vox_count": "{n} blocs \u00b7 {duration} d'audio",
        "vox_block_info": "Bloc #{index} \u00b7 {sr} Hz mono \u00b7 {dur:.2f} s",
        "vox_status_loaded": "Charg\u00e9 : {name} \u00b7 {n} blocs",
        "vox_hint": ("vox.dat contient toutes les voix du jeu (dialogues, "
                     "exclamations, bruits de pas\u2026). Chaque bloc est cod\u00e9 "
                     "en PS-ADPCM \u00e0 44100 Hz. S\u00e9lectionnez un bloc pour "
                     "l'\u00e9couter, ou exportez-les tous en WAV."),
        "vox_list_title": "BLOCS VOX",
        "demos_hint": ("demo.dat contient les audio des cutscenes et "
                       "démonstrations du jeu. Chaque entrée est codée en "
                       "MS-ADPCM (stéréo). Sélectionnez une entrée pour "
                       "l\'écouter, ou exportez-les toutes en WAV."),
        "demos_list_title": "ENTRÉES DÉMOS",
        "sdx_open_title": "1 · OUVRIR UNE BANQUE SDX",
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
        "sdx_done_partial": "⚠ {n} banques mises à jour, {failed} en échec (voir les logs)",
        "dlg_pick_stage": "Choisir le dossier du jeu MGS2",
        "sdx_no_file": "Aucune banque chargée",
        "sdx_list_title": "SONS DE LA BANQUE",
        "sdx_info_samples": "Sons",
        "sdx_info_region": "Zone audio",
        "sdx_count": "{n} sons · {bytes} octets d'audio",
        "sdx_select_hint": "Sélectionnez un son dans la liste",
        "sdx_listen_title": "2 · ÉCOUTER LE SON",
        "sdx_export": "EXPORTER EN WAV…",
        "sdx_replace_title": "3 · REMPLACER PAR VOTRE SON (WAV)",
        "sdx_hint": ("La durée du son est figée : un WAV plus long sera tronqué, "
                     "un plus court complété par du silence. Conversion auto "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "CHOISIR UN WAV…",
        "sdx_no_wav": "Aucun WAV choisi",
        "sdx_gen_title": "4 · GÉNÉRER LA BANQUE MODIFIÉE",
        "sdx_generate": "REMPLACER LE SON ET SAUVEGARDER…",
        "sdx_result": "✓ Banque générée — même taille ({size} octets)",
        "dlg_open_sdx": "Ouvrir une banque SDX",
        "dlg_save_sdx": "Sauvegarder la banque modifiée",
        "filter_sdx": "Banques SDX (*.sdx);;Tous les fichiers (*)",
        "sdx_status_loaded": "Chargé : {name} · {n} sons",
        "sdx_status_sample": "Son #{i} · {dur:.2f}s · {size} octets",
        "sdx_status_done": "Terminé : {name}",
        "sdx_warn_empty": "Cette banque ne contient aucun son exploitable.",
        "lib_pick_voice": "DOSSIER DE VOIX…",
        "lib_pick_db": "DOSSIER DE BASE…",
        "lib_no_voice": "Aucun dossier de voix",
        "lib_no_db": "Base non définie",
        "lib_search": "Rechercher…",
        "lib_filter_all": "Tout",
        "filter_all_tags": "Toutes les étiquettes",
        "lib_filter_todo": "À faire",
        "lib_filter_done": "Fait",
        "lib_show_backups": "Afficher l\'audio d\'origine (.vortex_backup)",
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

        "step1_title": "1 · OUVRIR UN FICHIER SDT",
        "step1_title_vox": "1 · OUVRIR UN FICHIER VOX.DAT",
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

        "step2_title": "2 · ÉCOUTER LE DIALOGUE ORIGINAL",
        "export_wav": "EXPORTER EN WAV…",

        "step3_title": "3 · CHOISIR VOTRE DOUBLAGE (WAV)",
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

        "step4_title": "4 · GÉNÉRER LE SDT MODIFIÉ",
        "step4_title_vox": "4 · GÉNÉRER LE VOX.DAT MODIFIÉ",
        "generate": "REMPLACER L'AUDIO ET SAUVEGARDER…",
        "result_ok": "✓ Fichier généré",
        "result_detail": ("Même taille que l'original ({size} octets) — "
                          "prêt à remettre dans le jeu."),

        "dlg_open_sdt": "Ouvrir un fichier SDT",
        "dlg_export_wav": "Exporter en WAV",
        "dlg_pick_wav": "Choisir votre doublage WAV",
        "dlg_save_sdt": "Sauvegarder le SDT modifié",
        "dlg_save_vox": "Sauvegarder le vox.dat modifié",
        "filter_sdt": "Fichiers SDT (*.sdt *.sdt.vortex_backup);;Tous les fichiers (*)",
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
        "xwma_need_ffmpeg": ("Audio d\'origine Konami XWMA (WMA). Le décodage "
                             "nécessite ffmpeg, introuvable. Installez-le "
                             "(ex. : winget install ffmpeg) puis relancez, ou "
                             "indiquez le ffmpeg.exe ci-dessous."),
        "xwma_locate_ffmpeg": "LOCALISER FFMPEG.EXE…",
        "xwma_pick_ffmpeg": "Sélectionner ffmpeg.exe",
        "filter_ffmpeg": "ffmpeg (ffmpeg.exe);;Tous les fichiers (*)",
        "xwma_replace_hint": ("Votre WAV sera réencodé en XWMA (via xWMAEncode) "
                              "et réinjecté dans le fichier du jeu, à taille "
                              "identique (audio plus court complété de "
                              "silence ; trop long ou trop lourd = refusé)."),
        "xwma_need_encoder": ("Le remplacement XWMA nécessite xWMAEncode.exe "
                              "(outil Microsoft du DirectX SDK, ffmpeg ne "
                              "convient pas ici). Indiquez-le à l\'étape "
                              "suivante."),
        "xwma_pick_encoder": "Sélectionner xWMAEncode.exe",
        "xwma_encoded_at": "Réencodé en XWMA à {kbps} kbps",
        "xwma_too_long": ("Audio trop long/lourd pour ce fichier même au débit "
                          "le plus bas. Utilisez un clip plus court."),
        "filter_xwmaencode": "xWMAEncode (xWMAEncode.exe);;Tous les fichiers (*)",
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
        "app_subtitle_mc": "EXTRACTION & DUBBING — MASTER COLLECTION (PC)",
        "app_subtitle_substance": "EXTRACTION & DUBBING — SUBSTANCE (2003)",
        "language_label": "Language:",
        "mode_label": "Version:",
        "db_folder_label": "Database:",
        "mode_mc": "Master Collection",
        "mode_substance": "Substance (2003)",

        "lib_title": "LIBRARY",
        "tab_sdt": "SDT · DIALOGUE",
        "tab_mcbgm": "MUSIC · BGM",
        "tab_sdx": "SDX · SOUND FX",
        "tab_seq": "SEQUENCER · SDX CUES",
        "tab_bgm": "MUSIC · BGM",
        "tab_vox": "VOX · VOICES",
        "tab_demos": "DEMOS · CUTSCENES",
        "seq_open_title": "1 · OPEN A BANK",
        "seq_browse": "BROWSE…",
        "seq_no_file": "No bank loaded",
        "seq_list_title": "PIECES IN THE BANK",
        "seq_count": "{n} pieces · {instruments} instruments",
        "seq_select_hint": "Select a piece from the list",
        "seq_filter_all": "All pieces",
        "seq_filter_music": "At least 8 notes",
        "seq_filter_long": "At least 20 notes",
        "seq_listen_title": "2 · LISTEN TO THE PIECE",
        "seq_rendering": "Synthesising…",
        "seq_export_title": "3 · EXPORT",
        "seq_export": "EXPORT TO WAV…",
        "seq_export_all": "EXPORT EVERY PIECE…",
        "seq_exporting": "Exporting… {n}/{total}",
        "seq_exported_all": "✓ {n} pieces exported",
        "seq_options_title": "4 · SYNTHESIS OPTIONS",
        "seq_stereo": "Stereo (panning)",
        "seq_tune": "Tune the instruments (faithful)",
        "seq_info": "Piece #{i} · {tracks} track(s) · {notes} notes",
        "seq_no_sequence": ("This bank carries no sequencer "
                            "(no instrument directory)."),
        "seq_hint": ("Two kinds of bank share the .sdx extension: a “music” "
                     "bank (256 cues, ~130-150 instruments) carries real musical "
                     "pieces, while an effects bank carries mostly raw SPU sound "
                     "effects. A software reverb is applied, but the game's exact "
                     "per-sound preset isn't stored in the file. Note: the "
                     "Musique · BGM tab only covers the launcher's music, not what "
                     "plays during a mission."),
        "bgm_list_title": "BGM ARCHIVE ENTRIES",
        "bgm_browse": "BROWSE…",
        "bgm_no_file": "No BGM archive loaded",
        "bgm_select_hint": "Select an entry from the list",
        "bgm_open_title": "1 · OPEN A BGM ARCHIVE",
        "bgm_hint": ("bgm.dat is an archive containing the game's pre-recorded "
                     "background music. Each entry is encoded in MS-ADPCM "
                     "(stereo or 4-channel). Select an entry to listen, "
                     "or export all to WAV."),
        "bgm_listen_title": "2 · LISTEN TO THE ENTRY",
        "bgm_rendering": "Decoding…",
        "bgm_export_title": "3 · EXPORT",
        "bgm_export": "EXPORT TO WAV…",
        "bgm_export_all": "EXPORT ALL ENTRIES…",
        "bgm_exporting": "Exporting… {n}/{total}",
        "bgm_exported_all": "✓ {n} entries exported",
        "bgm_count": "{n} entries · {duration} of audio",
        "bgm_entry_info": "Entry #{index} · {sr} Hz {ch}ch · {dur:.2f} s",
        "bgm_no_entries": "This file contains no BGM entries.",
        "bgm_status_loaded": "Loaded: {name} · {n} BGM entries",
        "dlg_open_bgm": "Open a BGM archive",
        "mcbgm_list_title": "SCENARIO MUSIC TRACKS",
        "mcbgm_pick_game": "GAME FOLDER (MC)…",
        "mcbgm_no_game": "No game folder selected",
        "mcbgm_hint": ("Master Collection's LAUNCHER music lives in Unity "
                       "AssetBundles (one .bundle file per track). Pick the "
                       "game's install folder (the one containing "
                       "launcher.exe) to list the 6 scenario tracks plus the "
                       "menu and credits music, listen to them, export them — "
                       "or replace them with your own WAVs. Note: these files "
                       "only drive the launcher, not the in-game gameplay "
                       "music (research ongoing, see docs/ORCHESTRATION.md)."),
        "mcbgm_select_hint": "Select a track from the list",
        "mcbgm_no_unitypy": ("The UnityPy library is required to read Master "
                             "Collection's Unity bundles.\n"
                             "Install it with:  pip install UnityPy"),
        "mcbgm_bad_folder": "Invalid game folder: {e}",
        "mcbgm_no_tracks": "No tracks found in this folder.",
        "mcbgm_status_loaded": "✓ {n} scenario tracks loaded",
        "mcbgm_count": "{n} tracks · {duration} of audio",
        "mcbgm_track_title": "1 · TRACK",
        "mcbgm_track_info": "{name} · {sr} Hz {ch} · {dur:.1f} s",
        "mcbgm_rel_path": "File in the game: {path}",
        "mcbgm_listen_title": "2 · LISTEN / EXPORT",
        "mcbgm_rendering": "Extracting from the bundle…",
        "mcbgm_ready": "Ready: {name}",
        "mcbgm_export": "EXPORT TO WAV…",
        "mcbgm_replace_title": "3 · REPLACE (MODDING)",
        "mcbgm_pick_wav": "PICK A WAV…",
        "mcbgm_wav_info": ("{name} · {sr} Hz {ch}ch · {dur:.1f} s "
                           "(original: {orig:.1f} s)"),
        "mcbgm_generate": "GENERATE THE BUNDLE…",
        "mcbgm_generating": "Rebuilding the bundle…",
        "mcbgm_generated": ("✓ Bundle generated: {path}\n"
                            "Place it in the game at:\n{rel}"),
        "mcbgm_status_generated": "✓ Bundle generated: {name}",
        "mcbgm_use_install": ("To write directly into the game, use the "
                              "INSTALL button (it creates a .bak backup "
                              "first)."),
        "mcbgm_install": "INSTALL INTO THE GAME (.bak)",
        "mcbgm_install_title": "Install into the game",
        "mcbgm_install_confirm": ("Replace the game's file:\n{rel}\n\n"
                                  "The original will be kept as .bak "
                                  "(unless one already exists), and this "
                                  "bundle's CRC check will be disabled in "
                                  "catalog.json (also backed up as .bak)."
                                  "\n\nContinue?"),
        "mcbgm_installed": ("✓ Installed (original kept as .bak, catalog CRC "
                            "disabled): {rel}"),
        "mcbgm_catalog_failed": ("Bundle installed, but patching the catalog "
                                 "failed: {e}\nThe game will refuse this "
                                 "bundle until its CRC is zeroed in "
                                 "catalog.json."),
        "dlg_pick_mc_game": "Pick the MGS2 Master Collection install folder",
        "dlg_save_bundle": "Save the bundle",
        "filter_bundle": "Unity AssetBundles (*.bundle);;All files (*)",
        "dlg_open_vox": "Open a vox.dat file",
        "dlg_open_demos": "Open a demo.dat file",
        "dlg_open_seq": "Open an SDX bank",
        "dlg_export_all": "Choose the export folder",
        "seq_status_loaded": "Loaded: {name} · {n} pieces",
        "dlg_save_script": "Save script",
        "dlg_open_script": "Open a script",
        "filter_script": "JSON script (*.json);;All files (*)",
        "filter_dat": "MGS2 archives (*.dat);;All files (*)",
        "vox_browse": "BROWSE\u2026",
        "vox_open_title": "1 \u00b7 OPEN A VOX.DAT FILE",
        "vox_no_file": "No vox.dat loaded",
        "vox_no_blocks": "This file contains no audio blocks.",
        "vox_select_hint": "Select a block from the list",
        "vox_listen_title": "2 \u00b7 LISTEN TO THE BLOCK",
        "vox_rendering": "Decoding\u2026",
        "vox_export_title": "3 \u00b7 EXPORT",
        "vox_export": "EXPORT TO WAV\u2026",
        "vox_export_all": "EXPORT ALL BLOCKS\u2026",
        "vox_exporting": "Exporting\u2026 {n}/{total}",
        "vox_exported_all": "\u2713 {n} blocks exported",
        "vox_count": "{n} blocks \u00b7 {duration} of audio",
        "vox_block_info": "Block #{index} \u00b7 {sr} Hz mono \u00b7 {dur:.2f} s",
        "vox_status_loaded": "Loaded: {name} \u00b7 {n} blocks",
        "vox_hint": ("vox.dat contains all the game's voices (dialogue, "
                     "exclamations, footsteps\u2026). Each block is encoded in "
                     "PS-ADPCM at 44100 Hz. Select a block to listen, "
                     "or export all to WAV."),
        "vox_list_title": "VOX BLOCKS",
        "demos_hint": ("demo.dat contains cutscene and demo audio. "
                       "Each entry is encoded in MS-ADPCM (stereo). "
                       "Select an entry to listen, "
                       "or export all to WAV."),
        "demos_list_title": "DEMO ENTRIES",
        "sdx_open_title": "1 · OPEN AN SDX BANK",
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
        "sdx_done_partial": "⚠ {n} banks updated, {failed} failed (see logs)",
        "dlg_pick_stage": "Choose your MGS2 game folder",
        "sdx_no_file": "No bank loaded",
        "sdx_list_title": "SOUNDS IN THE BANK",
        "sdx_info_samples": "Sounds",
        "sdx_info_region": "Audio region",
        "sdx_count": "{n} sounds · {bytes} bytes of audio",
        "sdx_select_hint": "Select a sound from the list",
        "sdx_listen_title": "2 · LISTEN TO THE SOUND",
        "sdx_export": "EXPORT TO WAV…",
        "sdx_replace_title": "3 · REPLACE WITH YOUR SOUND (WAV)",
        "sdx_hint": ("The sound's length is fixed: a longer WAV is trimmed, a "
                     "shorter one is padded with silence. Converted automatically "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "CHOOSE A WAV…",
        "sdx_no_wav": "No WAV chosen",
        "sdx_gen_title": "4 · GENERATE THE MODIFIED BANK",
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
        "lib_show_backups": "Show stock originals (.vortex_backup)",
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

        "step1_title": "1 · OPEN AN SDT FILE",
        "step1_title_vox": "1 · OPEN A VOX.DAT FILE",
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

        "step2_title": "2 · LISTEN TO THE ORIGINAL DIALOGUE",
        "export_wav": "EXPORT TO WAV…",

        "step3_title": "3 · CHOOSE YOUR DUB (WAV)",
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

        "step4_title": "4 · GENERATE THE MODIFIED SDT",
        "step4_title_vox": "4 · GENERATE THE MODIFIED VOX.DAT",
        "generate": "REPLACE AUDIO AND SAVE…",
        "result_ok": "✓ File generated",
        "result_detail": ("Same size as the original ({size} bytes) — "
                          "ready to put back into the game."),

        "dlg_open_sdt": "Open an SDT file",
        "dlg_export_wav": "Export to WAV",
        "dlg_pick_wav": "Choose your dub WAV",
        "dlg_save_sdt": "Save the modified SDT",
        "dlg_save_vox": "Save the modified vox.dat",
        "filter_sdt": "SDT files (*.sdt *.sdt.vortex_backup);;All files (*)",
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
        "xwma_need_ffmpeg": ("Stock Konami XWMA (WMA) audio. Decoding needs "
                             "ffmpeg, which wasn't found. Install it "
                             "(e.g. winget install ffmpeg) and reopen, or "
                             "point to your ffmpeg.exe below."),
        "xwma_locate_ffmpeg": "LOCATE FFMPEG.EXE…",
        "xwma_pick_ffmpeg": "Select ffmpeg.exe",
        "filter_ffmpeg": "ffmpeg (ffmpeg.exe);;All files (*)",
        "xwma_replace_hint": ("Your WAV will be re-encoded to XWMA (via "
                              "xWMAEncode) and put back into the game file at "
                              "the same size (shorter audio is padded with "
                              "silence; too long or too large is refused)."),
        "xwma_need_encoder": ("XWMA replacement needs xWMAEncode.exe (a "
                              "Microsoft DirectX SDK tool; ffmpeg won't work "
                              "here). Point to it in the next step."),
        "xwma_pick_encoder": "Select xWMAEncode.exe",
        "xwma_encoded_at": "Re-encoded to XWMA at {kbps} kbps",
        "xwma_too_long": ("Audio too long/large for this file even at the "
                          "lowest bitrate. Use a shorter clip."),
        "filter_xwmaencode": "xWMAEncode (xWMAEncode.exe);;All files (*)",
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
        "app_subtitle_mc": "EXTRACCIÓN Y DOBLAJE — MASTER COLLECTION (PC)",
        "app_subtitle_substance": "EXTRACCIÓN Y DOBLAJE — SUBSTANCE (2003)",
        "language_label": "Idioma:",
        "mode_label": "Versión:",
        "db_folder_label": "Base:",
        "mode_mc": "Master Collection",
        "mode_substance": "Substance (2003)",

        "lib_title": "BIBLIOTECA",
        "tab_sdt": "SDT · DIÁLOGOS",
        "tab_mcbgm": "MÚSICA · BGM",
        "tab_sdx": "SDX · EFECTOS",
        "tab_seq": "SECUENCIADOR · CUES SDX",
        "tab_bgm": "MÚSICA · BGM",
        "tab_vox": "VOX · VOCES",
        "tab_demos": "DEMOS · CUTSCENES",
        "seq_open_title": "1 · ABRIR UN BANCO",
        "seq_browse": "EXAMINAR…",
        "seq_no_file": "Ningún banco cargado",
        "seq_list_title": "PIEZAS DEL BANCO",
        "seq_count": "{n} piezas · {instruments} instrumentos",
        "seq_select_hint": "Selecciona una pieza de la lista",
        "seq_filter_all": "Todas las piezas",
        "seq_filter_music": "Al menos 8 notas",
        "seq_filter_long": "Al menos 20 notas",
        "seq_listen_title": "2 · ESCUCHAR LA PIEZA",
        "seq_rendering": "Sintetizando…",
        "seq_export_title": "3 · EXPORTAR",
        "seq_export": "EXPORTAR A WAV…",
        "seq_export_all": "EXPORTAR TODAS LAS PIEZAS…",
        "seq_exporting": "Exportando… {n}/{total}",
        "seq_exported_all": "✓ {n} piezas exportadas",
        "seq_options_title": "4 · OPCIONES DE SÍNTESIS",
        "seq_stereo": "Estéreo (paneo)",
        "seq_tune": "Afinar los instrumentos (fidelidad)",
        "seq_info": "Pieza #{i} · {tracks} pista(s) · {notes} notas",
        "seq_no_sequence": ("Este banco no contiene secuenciador "
                            "(sin directorio de instrumentos)."),
        "seq_hint": ("Dos tipos de banco comparten la extensión .sdx: un banco "
                     "«de música» (256 cues, ~130-150 instrumentos) contiene piezas "
                     "musicales reales, mientras que un banco de efectos contiene "
                     "sobre todo SE brutos del SPU. Se aplica una reverb por "
                     "software, pero el preset exacto del juego no se guarda en el "
                     "archivo. Nota: la pestaña Música · BGM solo cubre la música "
                     "del launcher, no la que suena durante una misión."),
        "bgm_list_title": "ENTRADAS DEL ARCHIVO BGM",
        "bgm_browse": "EXAMINAR…",
        "bgm_no_file": "Ninguna archivo BGM cargado",
        "bgm_select_hint": "Selecciona una entrada de la lista",
        "bgm_open_title": "1 · ABRIR UN ARCHIVO BGM",
        "bgm_hint": ("bgm.dat es un archivo que contiene la música de fondo "
                     "pre-grabada del juego. Cada entrada está codificada en "
                     "MS-ADPCM (estéreo o 4 canales). Selecciona una entrada para "
                     "escucharla, o exporta todas a WAV."),
        "bgm_listen_title": "2 · ESCUCHAR LA ENTRADA",
        "bgm_rendering": "Decodificando…",
        "bgm_export_title": "3 · EXPORTAR",
        "bgm_export": "EXPORTAR A WAV…",
        "bgm_export_all": "EXPORTAR TODAS LAS ENTRADAS…",
        "bgm_exporting": "Exportando… {n}/{total}",
        "bgm_exported_all": "✓ {n} entradas exportadas",
        "bgm_count": "{n} entradas · {duration} de audio",
        "bgm_entry_info": "Entrada #{index} · {sr} Hz {ch}ch · {dur:.2f} s",
        "bgm_no_entries": "Este archivo no contiene entradas BGM.",
        "bgm_status_loaded": "Cargado: {name} · {n} entradas BGM",
        "dlg_open_bgm": "Abrir un archivo BGM",
        "mcbgm_list_title": "MÚSICAS DEL ESCENARIO",
        "mcbgm_pick_game": "CARPETA DEL JUEGO (MC)…",
        "mcbgm_no_game": "Ninguna carpeta de juego seleccionada",
        "mcbgm_hint": ("La música del LAUNCHER de Master Collection vive en "
                       "AssetBundles de Unity (un archivo .bundle por pista). "
                       "Elige la carpeta de instalación del juego (la que "
                       "contiene launcher.exe) para listar las 6 pistas del "
                       "escenario más la música del menú y de los créditos, "
                       "escucharlas, exportarlas — o reemplazarlas con tus "
                       "propios WAV. Atención: estos archivos solo controlan "
                       "el launcher, no la música dentro de la partida "
                       "(investigación en curso, ver docs/ORCHESTRATION.md)."),
        "mcbgm_select_hint": "Selecciona una pista de la lista",
        "mcbgm_no_unitypy": ("Se necesita la librería UnityPy para leer los "
                             "bundles de Unity de Master Collection.\n"
                             "Instálala con:  pip install UnityPy"),
        "mcbgm_bad_folder": "Carpeta de juego no válida: {e}",
        "mcbgm_no_tracks": "No se encontraron pistas en esta carpeta.",
        "mcbgm_status_loaded": "✓ {n} pistas del escenario cargadas",
        "mcbgm_count": "{n} pistas · {duration} de audio",
        "mcbgm_track_title": "1 · PISTA",
        "mcbgm_track_info": "{name} · {sr} Hz {ch} · {dur:.1f} s",
        "mcbgm_rel_path": "Archivo en el juego: {path}",
        "mcbgm_listen_title": "2 · ESCUCHAR / EXPORTAR",
        "mcbgm_rendering": "Extrayendo del bundle…",
        "mcbgm_ready": "Listo: {name}",
        "mcbgm_export": "EXPORTAR A WAV…",
        "mcbgm_replace_title": "3 · REEMPLAZAR (MODDING)",
        "mcbgm_pick_wav": "ELEGIR UN WAV…",
        "mcbgm_wav_info": ("{name} · {sr} Hz {ch}ch · {dur:.1f} s "
                           "(original: {orig:.1f} s)"),
        "mcbgm_generate": "GENERAR EL BUNDLE…",
        "mcbgm_generating": "Reconstruyendo el bundle…",
        "mcbgm_generated": ("✓ Bundle generado: {path}\n"
                            "Colócalo en el juego en:\n{rel}"),
        "mcbgm_status_generated": "✓ Bundle generado: {name}",
        "mcbgm_use_install": ("Para escribir directamente en el juego, usa el "
                              "botón INSTALAR (crea antes una copia .bak)."),
        "mcbgm_install": "INSTALAR EN EL JUEGO (.bak)",
        "mcbgm_install_title": "Instalar en el juego",
        "mcbgm_install_confirm": ("¿Reemplazar el archivo del juego?\n{rel}\n\n"
                                  "El original se conservará como .bak "
                                  "(si no existe ya), y la verificación CRC "
                                  "de este bundle se desactivará en "
                                  "catalog.json (también respaldado como "
                                  ".bak).\n\n¿Continuar?"),
        "mcbgm_installed": ("✓ Instalado (original como .bak, CRC del "
                            "catálogo desactivado): {rel}"),
        "mcbgm_catalog_failed": ("Bundle instalado, pero el parche del "
                                 "catálogo falló: {e}\nEl juego rechazará "
                                 "este bundle hasta que su CRC sea 0 en "
                                 "catalog.json."),
        "dlg_pick_mc_game": "Elegir la carpeta de instalación de MGS2 Master Collection",
        "dlg_save_bundle": "Guardar el bundle",
        "filter_bundle": "AssetBundles de Unity (*.bundle);;Todos los archivos (*)",
        "dlg_open_vox": "Abrir un archivo vox.dat",
        "dlg_open_demos": "Abrir un archivo demo.dat",
        "dlg_open_seq": "Abrir un banco SDX",
        "dlg_export_all": "Elegir la carpeta de exportación",
        "seq_status_loaded": "Cargado: {name} · {n} piezas",
        "dlg_save_script": "Guardar script",
        "dlg_open_script": "Abrir un script",
        "filter_script": "Script JSON (*.json);;Todos los archivos (*)",
        "filter_dat": "Archivos MGS2 (*.dat);;Todos los archivos (*)",
        "vox_browse": "EXAMINAR\u2026",
        "vox_open_title": "1 \u00b7 ABRIR UN ARCHIVO VOX.DAT",
        "vox_no_file": "Ning\u00fan vox.dat cargado",
        "vox_no_blocks": "Este archivo no contiene bloques de audio.",
        "vox_select_hint": "Selecciona un bloque de la lista",
        "vox_listen_title": "2 \u00b7 ESCUCHAR EL BLOQUE",
        "vox_rendering": "Decodificando\u2026",
        "vox_export_title": "3 \u00b7 EXPORTAR",
        "vox_export": "EXPORTAR A WAV\u2026",
        "vox_export_all": "EXPORTAR TODOS LOS BLOQUES\u2026",
        "vox_exporting": "Exportando\u2026 {n}/{total}",
        "vox_exported_all": "\u2713 {n} bloques exportados",
        "vox_count": "{n} bloques \u00b7 {duration} de audio",
        "vox_block_info": "Bloque #{index} \u00b7 {sr} Hz mono \u00b7 {dur:.2f} s",
        "vox_status_loaded": "Cargado: {name} \u00b7 {n} bloques",
        "vox_hint": ("vox.dat contiene todas las voces del juego (di\u00e1logos, "
                     "exclamaciones, pasos\u2026). Cada bloque est\u00e1 codificado en "
                     "PS-ADPCM a 44100 Hz. Selecciona un bloque para "
                     "escucharlo, o exporta todos a WAV."),
        "vox_list_title": "BLOQUES VOX",
        "demos_hint": ("demo.dat contiene el audio de las cutscenes y "
                       "demostraciones. Cada entrada est\u00e1 codificada en "
                       "MS-ADPCM (est\u00e9reo). Selecciona una entrada para "
                       "escucharla, o exporta todas a WAV."),
        "demos_list_title": "ENTRADAS DEMOS",
        "sdx_open_title": "1 · ABRIR UN BANCO SDX",
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
        "sdx_done_partial": "⚠ {n} bancos actualizados, {failed} fallidos (ver logs)",
        "dlg_pick_stage": "Elegir la carpeta del juego MGS2",
        "sdx_no_file": "Ningún banco cargado",
        "sdx_list_title": "SONIDOS DEL BANCO",
        "sdx_info_samples": "Sonidos",
        "sdx_info_region": "Zona de audio",
        "sdx_count": "{n} sonidos · {bytes} bytes de audio",
        "sdx_select_hint": "Selecciona un sonido de la lista",
        "sdx_listen_title": "2 · ESCUCHAR EL SONIDO",
        "sdx_export": "EXPORTAR A WAV…",
        "sdx_replace_title": "3 · REEMPLAZAR CON TU SONIDO (WAV)",
        "sdx_hint": ("La duración del sonido es fija: un WAV más largo se recorta, "
                     "uno más corto se completa con silencio. Conversión automática "
                     "(mono, 22050 Hz)."),
        "sdx_pick_wav": "ELEGIR UN WAV…",
        "sdx_no_wav": "Ningún WAV elegido",
        "sdx_gen_title": "4 · GENERAR EL BANCO MODIFICADO",
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
        "lib_show_backups": "Mostrar originales de fábrica (.vortex_backup)",
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

        "step1_title": "1 · ABRIR UN ARCHIVO SDT",
        "step1_title_vox": "1 · ABRIR UN ARCHIVO VOX.DAT",
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

        "step2_title": "2 · ESCUCHAR EL DIÁLOGO ORIGINAL",
        "export_wav": "EXPORTAR A WAV…",

        "step3_title": "3 · ELEGIR TU DOBLAJE (WAV)",
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

        "step4_title": "4 · GENERAR EL SDT MODIFICADO",
        "step4_title_vox": "4 · GENERAR EL VOX.DAT MODIFICADO",
        "generate": "REEMPLAZAR AUDIO Y GUARDAR…",
        "result_ok": "✓ Archivo generado",
        "result_detail": ("Mismo tamaño que el original ({size} bytes) — "
                          "listo para volver al juego."),

        "dlg_open_sdt": "Abrir un archivo SDT",
        "dlg_export_wav": "Exportar a WAV",
        "dlg_pick_wav": "Elegir tu WAV de doblaje",
        "dlg_save_sdt": "Guardar el SDT modificado",
        "dlg_save_vox": "Guardar el vox.dat modificado",
        "filter_sdt": "Archivos SDT (*.sdt *.sdt.vortex_backup);;Todos los archivos (*)",
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
        "xwma_need_ffmpeg": ("Audio original Konami XWMA (WMA). La "
                             "decodificación necesita ffmpeg, no encontrado. "
                             "Instálalo (p. ej. winget install ffmpeg) y vuelve "
                             "a abrir, o indica tu ffmpeg.exe abajo."),
        "xwma_locate_ffmpeg": "LOCALIZAR FFMPEG.EXE…",
        "xwma_pick_ffmpeg": "Seleccionar ffmpeg.exe",
        "filter_ffmpeg": "ffmpeg (ffmpeg.exe);;Todos los archivos (*)",
        "xwma_replace_hint": ("Tu WAV se recodificará a XWMA (con xWMAEncode) "
                              "y se reinsertará en el archivo del juego con el "
                              "mismo tamaño (audio más corto se rellena con "
                              "silencio; demasiado largo o pesado se rechaza)."),
        "xwma_need_encoder": ("El reemplazo XWMA necesita xWMAEncode.exe "
                              "(herramienta del DirectX SDK de Microsoft; "
                              "ffmpeg no sirve aquí). Indícalo en el "
                              "siguiente paso."),
        "xwma_pick_encoder": "Seleccionar xWMAEncode.exe",
        "xwma_encoded_at": "Recodificado a XWMA a {kbps} kbps",
        "xwma_too_long": ("Audio demasiado largo/pesado para este archivo "
                          "incluso al bitrate más bajo. Usa un clip más corto."),
        "filter_xwmaencode": "xWMAEncode (xWMAEncode.exe);;Todos los archivos (*)",
        "err_wav_read": "WAV ilegible:\n{e}",
        "err_generate": "No se puede generar:\n{e}",
        "ok_export_title": "Exportación exitosa",
        "ok_export_body": "WAV guardado:\n{path}",
        "ok_dub_title": "Doblaje completado",
        "ok_dub_body": ("El archivo SDT modificado se ha guardado:\n{path}\n\n"
                        "Reemplaza el archivo original del juego por este "
                        "(recuerda hacer una copia de seguridad del original)."),
    },

    "ru": {
        "lang_name": "Русский",
        "window_title": "MGS2 SDT Tool — Озвучивание",
        "app_title": "MGS2 · SDT TOOL",
        "app_subtitle_mc": "ИЗВЛЕЧЕНИЕ И ОЗВУЧИВАНИЕ — MASTER COLLECTION (PC)",
        "app_subtitle_substance": "ИЗВЛЕЧЕНИЕ И ОЗВУЧИВАНИЕ — SUBSTANCE (2003)",
        "language_label": "Язык:",
        "mode_label": "Версия:",
        "db_folder_label": "База:",
        "mode_mc": "Master Collection",
        "mode_substance": "Substance (2003)",

        "lib_title": "БИБЛИОТЕКА",
        "tab_sdt": "SDT · ДИАЛОГИ",
        "tab_mcbgm": "МУЗЫКА · BGM",
        "tab_sdx": "SDX · ЗВУКИ",
        "tab_seq": "СЕКВЕНСОР · SDX-КЬЮ",
        "tab_bgm": "МУЗЫКА · BGM",
        "tab_vox": "VOX · ГОЛОСА",
        "tab_demos": "ДЕМО · КАТСЦЕНЫ",
        "seq_open_title": "1 · ОТКРЫТЬ БАНК",
        "seq_browse": "ОБЗОР…",
        "seq_no_file": "Банк не загружен",
        "seq_list_title": "ФРАГМЕНТЫ В БАНКЕ",
        "seq_count": "{n} фрагментов · {instruments} инструментов",
        "seq_select_hint": "Выберите фрагмент из списка",
        "seq_filter_all": "Все фрагменты",
        "seq_filter_music": "Не менее 8 нот",
        "seq_filter_long": "Не менее 20 нот",
        "seq_listen_title": "2 · ПРОСЛУШАТЬ ФРАГМЕНТ",
        "seq_rendering": "Синтез…",
        "seq_export_title": "3 · ЭКСПОРТ",
        "seq_export": "ЭКСПОРТ В WAV…",
        "seq_export_all": "ЭКСПОРТ ВСЕХ ФРАГМЕНТОВ…",
        "seq_exporting": "Экспорт… {n}/{total}",
        "seq_exported_all": "✓ Экспортировано фрагментов: {n}",
        "seq_options_title": "4 · ПАРАМЕТРЫ СИНТЕЗА",
        "seq_stereo": "Стерео (панорама)",
        "seq_tune": "Настроить инструменты (точность)",
        "seq_info": "Фрагмент #{i} · дорожек: {tracks} · нот: {notes}",
        "seq_no_sequence": ("В этом банке нет секвенсора "
                            "(нет каталога инструментов)."),
        "seq_hint": ("Расширение .sdx делят два вида банков: «музыкальный» банк "
                     "(256 кью, ~130-150 инструментов) содержит настоящие "
                     "музыкальные пьесы, а банк эффектов — в основном сырые "
                     "звуковые эффекты SPU. Применяется программная реверберация, "
                     "но точный игровой пресет в файле не хранится. Примечание: "
                     "вкладка Музыка · BGM относится только к музыке лаунчера, "
                     "а не к той, что звучит на миссии."),
        "bgm_list_title": "ЗАПИСИ АРХИВА BGM",
        "bgm_browse": "ОБЗОР…",
        "bgm_no_file": "Архив BGM не загружен",
        "bgm_select_hint": "Выберите запись из списка",
        "bgm_open_title": "1 · ОТКРЫТЬ АРХИВ BGM",
        "bgm_hint": ("bgm.dat — это архив с заранее записанной фоновой музыкой "
                     "игры. Каждая запись закодирована в MS-ADPCM "
                     "(стерео или 4 канала). Выберите запись для прослушивания "
                     "или экспортируйте все в WAV."),
        "bgm_listen_title": "2 · ПРОСЛУШАТЬ ЗАПИСЬ",
        "bgm_rendering": "Декодирование…",
        "bgm_export_title": "3 · ЭКСПОРТ",
        "bgm_export": "ЭКСПОРТ В WAV…",
        "bgm_export_all": "ЭКСПОРТ ВСЕХ ЗАПИСЕЙ…",
        "bgm_exporting": "Экспорт… {n}/{total}",
        "bgm_exported_all": "✓ Экспортировано записей: {n}",
        "bgm_count": "{n} записей · {duration} звука",
        "bgm_entry_info": "Запись #{index} · {sr} Гц {ch}ч · {dur:.2f} с",
        "bgm_no_entries": "В этом файле нет записей BGM.",
        "bgm_status_loaded": "Загружено: {name} · записей BGM: {n}",
        "dlg_open_bgm": "Открыть архив BGM",
        "mcbgm_list_title": "МУЗЫКА СЦЕНАРИЯ",
        "mcbgm_pick_game": "ПАПКА ИГРЫ (MC)…",
        "mcbgm_no_game": "Папка игры не выбрана",
        "mcbgm_hint": ("Музыка ЛАУНЧЕРА Master Collection хранится в Unity "
                       "AssetBundle (по одному файлу .bundle на трек). Выберите "
                       "папку установки игры (ту, что содержит launcher.exe), "
                       "чтобы увидеть 6 треков сценария плюс музыку меню и "
                       "титров, прослушать их, экспортировать — или заменить "
                       "своими WAV. Внимание: эти файлы управляют только "
                       "лаунчером, а не игровой музыкой (идёт исследование, "
                       "см. docs/ORCHESTRATION.md)."),
        "mcbgm_select_hint": "Выберите трек из списка",
        "mcbgm_no_unitypy": ("Для чтения Unity-бандлов Master Collection нужна "
                             "библиотека UnityPy.\n"
                             "Установите её командой:  pip install UnityPy"),
        "mcbgm_bad_folder": "Неверная папка игры: {e}",
        "mcbgm_no_tracks": "В этой папке треки не найдены.",
        "mcbgm_status_loaded": "✓ Загружено треков сценария: {n}",
        "mcbgm_count": "{n} треков · {duration} звука",
        "mcbgm_track_title": "1 · ТРЕК",
        "mcbgm_track_info": "{name} · {sr} Гц {ch} · {dur:.1f} с",
        "mcbgm_rel_path": "Файл в игре: {path}",
        "mcbgm_listen_title": "2 · ПРОСЛУШАТЬ / ЭКСПОРТ",
        "mcbgm_rendering": "Извлечение из бандла…",
        "mcbgm_ready": "Готово: {name}",
        "mcbgm_export": "ЭКСПОРТ В WAV…",
        "mcbgm_replace_title": "3 · ЗАМЕНИТЬ (МОДДИНГ)",
        "mcbgm_pick_wav": "ВЫБРАТЬ WAV…",
        "mcbgm_wav_info": ("{name} · {sr} Гц {ch}ч · {dur:.1f} с "
                           "(оригинал: {orig:.1f} с)"),
        "mcbgm_generate": "СОЗДАТЬ БАНДЛ…",
        "mcbgm_generating": "Пересборка бандла…",
        "mcbgm_generated": ("✓ Бандл создан: {path}\n"
                            "Поместите его в игру по пути:\n{rel}"),
        "mcbgm_status_generated": "✓ Бандл создан: {name}",
        "mcbgm_use_install": ("Чтобы записать прямо в игру, используйте кнопку "
                              "УСТАНОВИТЬ (она сначала создаёт резервную "
                              "копию .bak)."),
        "mcbgm_install": "УСТАНОВИТЬ В ИГРУ (.bak)",
        "mcbgm_install_title": "Установить в игру",
        "mcbgm_install_confirm": ("Заменить файл игры:\n{rel}\n\n"
                                  "Оригинал будет сохранён как .bak "
                                  "(если он ещё не существует), а проверка CRC "
                                  "этого бандла будет отключена в catalog.json "
                                  "(тоже с резервной копией .bak)."
                                  "\n\nПродолжить?"),
        "mcbgm_installed": ("✓ Установлено (оригинал сохранён как .bak, CRC "
                            "каталога отключён): {rel}"),
        "mcbgm_catalog_failed": ("Бандл установлен, но пропатчить каталог не "
                                 "удалось: {e}\nИгра будет отклонять этот "
                                 "бандл, пока его CRC не обнулён в "
                                 "catalog.json."),
        "dlg_pick_mc_game": "Выберите папку установки MGS2 Master Collection",
        "dlg_save_bundle": "Сохранить бандл",
        "filter_bundle": "Unity AssetBundle (*.bundle);;Все файлы (*)",
        "dlg_open_vox": "Открыть файл vox.dat",
        "dlg_open_demos": "Открыть файл demo.dat",
        "dlg_open_seq": "Открыть банк SDX",
        "dlg_export_all": "Выберите папку экспорта",
        "seq_status_loaded": "Загружено: {name} · фрагментов: {n}",
        "dlg_save_script": "Сохранить скрипт",
        "dlg_open_script": "Открыть скрипт",
        "filter_script": "JSON-скрипт (*.json);;Все файлы (*)",
        "filter_dat": "Архивы MGS2 (*.dat);;Все файлы (*)",
        "vox_browse": "ОБЗОР…",
        "vox_open_title": "1 · ОТКРЫТЬ ФАЙЛ VOX.DAT",
        "vox_no_file": "vox.dat не загружен",
        "vox_no_blocks": "В этом файле нет аудиоблоков.",
        "vox_select_hint": "Выберите блок из списка",
        "vox_listen_title": "2 · ПРОСЛУШАТЬ БЛОК",
        "vox_rendering": "Декодирование…",
        "vox_export_title": "3 · ЭКСПОРТ",
        "vox_export": "ЭКСПОРТ В WAV…",
        "vox_export_all": "ЭКСПОРТ ВСЕХ БЛОКОВ…",
        "vox_exporting": "Экспорт… {n}/{total}",
        "vox_exported_all": "✓ Экспортировано блоков: {n}",
        "vox_count": "{n} блоков · {duration} звука",
        "vox_block_info": "Блок #{index} · {sr} Гц моно · {dur:.2f} с",
        "vox_status_loaded": "Загружено: {name} · блоков: {n}",
        "vox_hint": ("vox.dat содержит все голоса игры (диалоги, восклицания, "
                     "шаги…). Каждый блок закодирован в PS-ADPCM на 44100 Гц. "
                     "Выберите блок для прослушивания или экспортируйте все "
                     "в WAV."),
        "vox_list_title": "БЛОКИ VOX",
        "demos_hint": ("demo.dat содержит звук катсцен и демо. "
                       "Каждая запись закодирована в MS-ADPCM (стерео). "
                       "Выберите запись для прослушивания или экспортируйте "
                       "все в WAV."),
        "demos_list_title": "ЗАПИСИ ДЕМО",
        "sdx_open_title": "1 · ОТКРЫТЬ БАНК SDX",
        "sdx_browse": "ОБЗОР…",
        "sdx_scan": "СКАНИРОВАТЬ ИГРУ (ВСЕ СТЕЙДЖИ)…",
        "sdx_stage_found": "Стейджи: {path}",
        "sdx_no_stage": ("В этой папке не найдено ни одного файла .sdx.\n\n"
                         "Выберите папку установки MGS2 "
                         "(ту, что содержит us\\stage)."),
        "sdx_scanning": "Сканирование банков… {n}/{total}",
        "sdx_scan_done": "{banks} банков · {sounds} различных звуков",
        "sdx_group_count": "присутствует в {n} банках",
        "sdx_replace_all": "ЗАМЕНИТЬ ВО ВСЕХ БАНКАХ…",
        "sdx_confirm_all_title": "Заменить везде?",
        "sdx_confirm_all": ("Этот звук встречается в {n} банках.\n\n"
                            "Все они будут изменены на диске "
                            "(оригиналы сохраняются как .bak).\n\nПродолжить?"),
        "sdx_done_all": "✓ Обновлено банков: {n} (созданы копии .bak)",
        "sdx_done_partial": "⚠ Обновлено банков: {n}, ошибок: {failed} (см. логи)",
        "dlg_pick_stage": "Выберите папку игры MGS2",
        "sdx_no_file": "Банк не загружен",
        "sdx_list_title": "ЗВУКИ В БАНКЕ",
        "sdx_info_samples": "Звуки",
        "sdx_info_region": "Аудиообласть",
        "sdx_count": "{n} звуков · {bytes} байт звука",
        "sdx_select_hint": "Выберите звук из списка",
        "sdx_listen_title": "2 · ПРОСЛУШАТЬ ЗВУК",
        "sdx_export": "ЭКСПОРТ В WAV…",
        "sdx_replace_title": "3 · ЗАМЕНИТЬ СВОИМ ЗВУКОМ (WAV)",
        "sdx_hint": ("Длина звука фиксирована: более длинный WAV обрезается, "
                     "более короткий дополняется тишиной. Конвертируется "
                     "автоматически (моно, 22050 Гц)."),
        "sdx_pick_wav": "ВЫБРАТЬ WAV…",
        "sdx_no_wav": "WAV не выбран",
        "sdx_gen_title": "4 · СОЗДАТЬ ИЗМЕНЁННЫЙ БАНК",
        "sdx_generate": "ЗАМЕНИТЬ ЗВУК И СОХРАНИТЬ…",
        "sdx_result": "✓ Банк создан — тот же размер ({size} байт)",
        "dlg_open_sdx": "Открыть банк SDX",
        "dlg_save_sdx": "Сохранить изменённый банк",
        "filter_sdx": "Банки SDX (*.sdx);;Все файлы (*)",
        "sdx_status_loaded": "Загружено: {name} · звуков: {n}",
        "sdx_status_sample": "Звук #{i} · {dur:.2f} с · {size} байт",
        "sdx_status_done": "Готово: {name}",
        "sdx_warn_empty": "В этом банке нет пригодных звуков.",
        "lib_pick_voice": "ПАПКА ГОЛОСОВ…",
        "lib_pick_db": "ПАПКА БАЗЫ ДАННЫХ…",
        "lib_no_voice": "Папка голосов не выбрана",
        "lib_no_db": "База данных не задана",
        "lib_search": "Поиск…",
        "lib_filter_all": "Все",
        "filter_all_tags": "Все метки",
        "lib_filter_todo": "К работе",
        "lib_filter_done": "Готово",
        "lib_show_backups": "Показывать оригиналы (.vortex_backup)",
        "lib_scan": "СКАНИРОВАТЬ ПАПКУ",
        "lib_scanning": "Сканирование… {n}/{total}",
        "lib_count": "{total} файлов · {done} готово · {todo} к работе",
        "lib_done": "Озвучено",
        "lib_tag": "Метка",
        "lib_tag_hint": "Солдат, Кодек… (произвольный текст)",
        "lib_speaker": "Говорящий",
        "lib_notes": "Заметки / реплика",
        "lib_save_entry": "СОХРАНИТЬ ЗАПИСЬ",
        "lib_saved": "Запись сохранена: {name}",
        "lib_select_hint": "Выберите файл из списка",
        "dlg_pick_voice": "Выберите папку голосов",
        "dlg_pick_db": "Выберите папку базы данных меток",

        "step1_title": "1 · ОТКРЫТЬ ФАЙЛ SDT",
        "step1_title_vox": "1 · ОТКРЫТЬ ФАЙЛ VOX.DAT",
        "browse": "ОБЗОР…",
        "no_file": "Файл не загружен",

        "info_file": "Файл",
        "info_size": "Размер",
        "info_rate": "Частота дискретизации",
        "info_blocks": "Аудиоблоки",
        "info_duration": "Длительность",
        "unit_bytes": "байт",
        "unit_mono": "моно",
        "unit_stereo": "стерео",
        "unit_seconds": "с",

        "step2_title": "2 · ПРОСЛУШАТЬ ОРИГИНАЛЬНЫЙ ДИАЛОГ",
        "export_wav": "ЭКСПОРТ В WAV…",

        "step3_title": "3 · ВЫБЕРИТЕ СВОЮ ОЗВУЧКУ (WAV)",
        "step3_hint": ("Запишите свой голос, по возможности той же длины, что "
                       "и оригинал. WAV конвертируется автоматически "
                       "(44100 Гц) под файл."),
        "wav_target_stereo_note": "ваш голос будет помещён на оба канала",
        "pick_wav": "ВЫБРАТЬ WAV…",
        "no_wav": "WAV не выбран",
        "wav_duration": "Длина",
        "wav_original": "оригинал",
        "wav_same": "идентично",
        "wav_longer": "длиннее",
        "wav_shorter": "короче",
        "wav_will_trim": "будет обрезано",
        "wav_will_pad": "будет дополнено тишиной",
        "wav_source": "Источник",
        "wav_converted": "конвертировано в",
        "wav_mono": "моно",

        "step4_title": "4 · СОЗДАТЬ ИЗМЕНЁННЫЙ SDT",
        "step4_title_vox": "4 · СОЗДАТЬ ИЗМЕНЁННЫЙ VOX.DAT",
        "generate": "ЗАМЕНИТЬ ЗВУК И СОХРАНИТЬ…",
        "result_ok": "✓ Файл создан",
        "result_detail": ("Тот же размер, что и оригинал ({size} байт) — "
                          "готов к возврату в игру."),

        "dlg_open_sdt": "Открыть файл SDT",
        "dlg_export_wav": "Экспорт в WAV",
        "dlg_pick_wav": "Выберите WAV с озвучкой",
        "dlg_save_sdt": "Сохранить изменённый SDT",
        "dlg_save_vox": "Сохранить изменённый vox.dat",
        "filter_sdt": "Файлы SDT (*.sdt *.sdt.vortex_backup);;Все файлы (*)",
        "filter_wav": "Файлы WAV (*.wav);;Все файлы (*)",

        "status_ready": "Готово · Откройте игровой файл .sdt, чтобы начать",
        "status_loaded": "Загружено: {name} · {dur:.1f} с · блоков: {blocks}",
        "status_exported": "Экспортировано: {name} (сэмплов: {n})",
        "status_dub_ready": "Озвучка готова: {name}",
        "status_encoding": "Кодирование PS-ADPCM…",
        "status_done": "Готово: {name}",
        "status_gen_failed": "Сбой создания",

        "err_title": "Ошибка",
        "err_read": "Не удаётся прочитать файл:\n{e}",
        "warn_no_audio": "В этом файле нет звука для редактирования (0 блоков).",
        "warn_unsupported": "Неподдерживаемый кодек (не PS-ADPCM) — этот файл нельзя редактировать.",
        "xwma_need_ffmpeg": ("Оригинальный звук Konami XWMA (WMA). Для "
                             "декодирования нужен ffmpeg, но он не найден. "
                             "Установите его (напр. winget install ffmpeg) и "
                             "откройте заново, либо укажите ffmpeg.exe ниже."),
        "xwma_locate_ffmpeg": "УКАЗАТЬ FFMPEG.EXE…",
        "xwma_pick_ffmpeg": "Выберите ffmpeg.exe",
        "filter_ffmpeg": "ffmpeg (ffmpeg.exe);;Все файлы (*)",
        "xwma_replace_hint": ("Ваш WAV будет перекодирован в XWMA (через "
                              "xWMAEncode) и вставлен обратно в файл игры того "
                              "же размера (более короткий звук дополняется "
                              "тишиной; слишком длинный или тяжёлый — отклонён)."),
        "xwma_need_encoder": ("Для замены XWMA нужен xWMAEncode.exe "
                              "(инструмент из DirectX SDK Microsoft; ffmpeg "
                              "здесь не подходит). Укажите его на следующем "
                              "шаге."),
        "xwma_pick_encoder": "Выберите xWMAEncode.exe",
        "xwma_encoded_at": "Перекодировано в XWMA на {kbps} кбит/с",
        "xwma_too_long": ("Звук слишком длинный/тяжёлый для этого файла даже "
                          "на минимальном битрейте. Используйте более короткий "
                          "фрагмент."),
        "filter_xwmaencode": "xWMAEncode (xWMAEncode.exe);;Все файлы (*)",
        "err_wav_read": "Нечитаемый WAV:\n{e}",
        "err_generate": "Не удаётся создать:\n{e}",
        "ok_export_title": "Экспорт выполнен",
        "ok_export_body": "WAV сохранён:\n{path}",
        "ok_dub_title": "Озвучка завершена",
        "ok_dub_body": ("Изменённый файл SDT сохранён:\n{path}\n\n"
                        "Замените им оригинальный файл игры "
                        "(не забудьте сделать резервную копию оригинала)."),
    },
}

LANGUAGE_ORDER = ["fr", "en", "es", "ru"]


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
