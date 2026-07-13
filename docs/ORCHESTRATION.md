# Le chaînon manquant : l'orchestrateur musical

> Note : ce document est spécifique à MGS2. La nouvelle architecture du projet
> (`mgs2_audio/core/`, `games/`) permet d'ajouter d'autres jeux avec leurs
> propres formats — chaque jeu est un plugin indépendant.

## ⚠️ CORRECTION MAJEURE (2026-07-13, soir) — les bundles Unity = LAUNCHER seulement

Un test in-game généralisé trop vite avait fait conclure « musique du jeu
remplaçable via les bundles Unity ». **C'est faux** : un second test (remplacer
INFILTRATION, lancer une partie) a montré que **les bundles Unity ne pilotent
que le launcher** (musique du pré-launcher/menu, crédits, et le lecteur de
musiques de l'app scénario). **La musique in-game vient d'ailleurs** — et
l'investigation qui a suivi pointe fort vers la survie du système PS2 :

- **`METAL GEAR SOLID2.exe`** (le moteur du jeu porté, hors Unity) contient
  les chemins PS2 d'origine en dur, dont **`host0:./sound/mdx1/`** — le jeu
  attend toujours des données MDX, réempaquetées quelque part.
- **Candidats n°1 : `assets/sar/us/gbs_stage_*.sar`** — 17 fichiers, un par
  stage, **15-18 Ko chacun : pile la taille prédite plus bas pour un `mdx`**
  (`sng_data` ≤ 16 Ko). Format SAR décodé : en-tête 64 o (magic
  `0x000154F6`) + table de 380 entrées × 32 o (identique dans tous les
  fichiers) + payload par stage (3-6 Ko) découpé en blocs délimités par
  `FF FF 00 00` : chaque bloc = compteur u32 + N records de 8 o + tuples
  de 4 o `(val, type, 0x04, flag)`.
- **Indices forts dans les records** : des types dans la plage
  **0xDD-0xE3 = exactement les opcodes raven d'expression** (`0xDD` pan_set,
  `0xDE` pan_move, `0xDF` trans_set, `0xE0` detune_set, `0xE1` vib_set,
  `0xE3` rdm_set — le « random pitch » qui simule des prises multiples) ;
  la valeur `0x000A` correspond à l'index de cue 10 des `.sdx` ; la constante
  `0x1770` (6000, ×265 occurrences) évoque du timing. Hypothèse de travail :
  **tables de déclenchement** (« quelle cue, avec quel pan/transposition/
  random, quand ») plutôt que flux d'événements bruts — le payload ne parse
  pas comme des événements raven à aucun alignement.
- Autres pièces : `gbs.sar` (fichier « base », 155 entrées actives),
  `gbs.var`, et `Misc/us/BP_SE.DAT` (4 Mo, header `SEO2` — base des SE,
  référencée par les `.sdt` via leur header `LCGB`).
- Scripts d'analyse dans `scripts/` (`analyze_gbs_sar.py` et compagnons).
- Prochaines étapes : croiser les records avec les cues des `pk*.sdx` du même
  stage ; Process Monitor pendant une partie pour confirmer le chargement des
  `.sar` ; en dernier recours, désassembler la routine de parsing dans l'EXE.

**Ce qui reste vrai et confirmé** : le pipeline de remplacement Unity
(FSB5 + conformation + patch CRC du catalogue, détails ci-dessous) fonctionne
— le launcher joue bien l'audio remplacé. C'est l'étiquette « musique du jeu »
qui était fausse, pas la technique.

---

Toute la section historique ci-dessous (hypothèse `mdx`, structure `sng_data`,
codes son PS2) décrit comment **la version PS2/raven originale** orchestre sa
musique — et la correction ci-dessus la remet au centre du jeu : le moteur
in-game de MC en descend directement. La partie Unity suivante ne concerne
que **le launcher** :

```
<install MC>/launcher_Data/StreamingAssets/aa/StandaloneWindows64/
    packedassetsmgs2_assets_scenarioapp/mgs2/bgm/
        sounddata_scenariobgm.asset.bundle   ← catalogue (MonoBehaviour)
        mg35_mgs2_arms_depot_lp.wav.bundle
        mg35_mgs2_battle_lp.wav.bundle
        mg35_mgs2_countdown_to_disaster_lp.wav.bundle
        mg35_mgs2_infiltration_lp.wav.bundle
        mg35_mgs2_it's_the_harrier_lp.wav.bundle
        mg35_mgs2_yell_dead_cell_lp.wav.bundle
```

Chaque `.wav.bundle` est un **AssetBundle Unity standard** (signature `UnityFS`,
moteur 2021.3.16f1) contenant un `AudioClip` — extractible directement avec la
librairie publique **`UnityPy`** (`pip install UnityPy`, déjà présente dans cet
environnement). Confirmé sur `..._infiltration_lp.wav.bundle` : `AudioClip.samples`
donne un WAV PCM propre, stéréo, 44 100 Hz, 16 bits, ~120 s — pile le morceau
*Infiltration*, sans aucune perte ni ambiguïté de format.

Le catalogue `sounddata_scenariobgm.asset.bundle` (un `MonoBehaviour` lisible via
`obj.read_typetree()`) liste les **6 morceaux du scénario principal, avec leurs
vrais noms** : `ARMS DEPOT`, `BATTLE`, `COUNTDOWN TO DISASTER`, `INFILTRATION`,
`IT'S THE HARRIER`, `YELL "DEAD CELL"` — chacun pointant vers son `AudioClip`
par `m_PathID`. Catalogue fermé et complet pour cette scène (`ScenarioApp`).

**Portée réelle (corrigée)** : ces bundles sont **la musique du launcher** —
le remplacement est l'onglet « Musique · BGM » du mode MC (`formats/mcbgm.py`
+ `ui/mcbgm_page.py`). Le remplacement réécrit le sous-fichier `.resource` du
CAB interne du bundle et met à jour les métadonnées de l'`AudioClip` —
round-trip vérifié par test (`tests/test_mcbgm.py`).
**Verdict in-game (2026-07-13) : ✅ confirmé pour le LAUNCHER** (musique du
pré-launcher remplacée et jouée) — **pas pour la musique in-game**, voir la
correction en tête de document. Les tests sur `mainmenu` avaient révélé
**deux verrous**, tous deux levés :

1. **Le conteneur FSB5.** Le `.resource` n'est pas de l'audio brut mais un
   FSB5 (FMOD Sound Bank : en-tête, sample header, chunks LOOP/VORBIS) — le
   FMOD du jeu ne pouvait pas parser notre PCM nu → écran noir. L'outil
   construit maintenant un FSB5 valide (codec PCM16, chunk LOOP hérité) et
   **conforme le WAV utilisateur à l'original** (mêmes canaux, même fréquence
   par rééchantillonnage, même nombre de frames — silence si trop court,
   coupé si trop long ; `m_Length` et tous les champs sérialisés inchangés).
   Validé en décodant le bundle reconstruit via le vrai FMOD.
2. **Le CRC du catalogue Addressables.** `aa/catalog.json` porte, par bundle,
   un blob `AssetBundleRequestOptions` (JSON UTF-16 dans
   `m_ExtraDataString`) avec `m_Crc` (CRC32 vérifié au chargement) et
   `m_BundleSize`. Un bundle modifié est rejeté même parfait tant que ce CRC
   ne correspond pas. `mcbgm.patch_catalog()` met `m_Crc` à 0 (= pas de
   vérification) et ajuste `m_BundleSize`, par réécriture *in place* à
   longueur d'octets constante (aucun offset du catalogue ne bouge),
   avec `catalog.json.bak`. Le bouton « Installer dans le jeu » applique ce
   patch automatiquement.

Tous les sons du jeu (launcher) sont en Vorbis dans leurs FSB5 ; nos
remplacements sont en PCM16 (pas d'encodeur Vorbis en Python pur) — FMOD lit
les deux nativement, seule la taille du fichier diffère (~3×).

**Encore ouvert** : quel mécanisme décide QUAND jouer quelle piste (infiltration
→ alerte → évasion) — mais la correction en tête de document change la donne :
le moteur in-game est **le jeu d'origine porté** (`METAL GEAR SOLID2.exe`, avec
ses chemins `host0:` en dur), pas du C# Unity. Les codes son PS2 du système
`raven` décrits plus bas (`0x01FFFF10` = alerte, etc.) sont donc probablement
**toujours le mécanisme réel** in-game. (Le runtime Mono du launcher, lui, ne
concerne que l'enrobage Unity.)

**Ce qui reste vrai pour Substance (2003, PS2→PC)** : cette version-là suit
réellement les conventions `raven` (voir plus bas), et son `mdx` — s'il existe —
n'a toujours pas été trouvé. La piste `cache.dar`/`cache.qar` reste ouverte
mais spéculative pour Substance uniquement.

---

Recherche déclenchée par l'hypothèse (juste !) que les Snake Tales, niveaux bonus
autonomes, contiendraient l'orchestration musicale en données. Trouvé dans raven.

## Ce qu'on cherchait

On savait : décoder les `.sdx` → samples ; jouer une « cue » → le séquenceur assemble
1-3 pistes. Manquait : **qui enchaîne tout ça en musique complète ?**

## La réponse : trois fichiers séparés

raven charge **trois types de données distincts** (`raven.c`) :

| Fichier | Rôle | Chez nous |
|---------|------|-----------|
| **`mdx`** | **données MUSIQUE** — l'orchestrateur (`sng_data`) | **manquant** |
| `wvx` (×1-3) | données WAVE — `voice_tbl` + samples | **nos `.sdx`** |
| `efx` | données SE | — |

**Donc nos `.sdx` sont les fichiers WAVE.** Ils portent les samples et des séquences
par piste, mais la vraie musique (BGM) vit dans un fichier **`mdx` séparé**, petit
(`sng_data` fait au plus **0x4000 = 16 Ko**). Aucun des 10 fichiers tales (≥500 Ko)
n'est un `mdx`.

Corollaire : nos « cues » à 1-3 pistes sont vraisemblablement des **effets sonores
(SE)** — d'où les « passages de phase d'alerte » que tu as entendus en brut. La
musique orchestrée, elle, assemble jusqu'à **13 pistes** par morceau.

## L'orchestration est pilotée par l'état du jeu

Le driver (`sd_drv.c`) reçoit des **codes son** 32 bits envoyés par le jeu :

| Code | Effet |
|------|-------|
| `0x01000001`..`0x01000008` | jouer la song 1 à 8 |
| `0x01FFFF01` / `02` | pause / reprise |
| `0x01FFFF03`..`05` | fade in |
| `0x01FFFF06`..`0D` | fade out (+ pause / stop) |
| **`0x01FFFF10`** | **Evasion Mode (ALERTE)** ← le passage d'alerte |
| `0x01FFFF20` / `21` | First-Person Mode on/off |
| `0x01FFFFFF` | stop |

C'est le système de musique dynamique de MGS : la musique change selon l'état
(infiltration → alerte → évasion), via ces codes. La transition « alerte » est
littéralement `0x01FFFF10`.

## Structure de `sng_data` (le format `mdx`) — prête à décoder

De `sng_adrs_set` (`sd_drv.c`). Tout est little-endian, offsets en octets dans le fichier :

```
sng_data[0]                      = n_songs (1..8)
pour la song `num` (1..n_songs):
    song_addr = sng_data[num*4] | (sng_data[num*4+1] << 8)      # pointeur 16 bits
    pour i in 0..12 (SD_BGM_VOICES = 13 pistes):
        base = song_addr + i*4
        track_addr = sng_data[base] | (sng_data[base+1]<<8) | (sng_data[base+2]<<16)  # 24 bits
        si track_addr != 0:
            la piste i = flux d'événements à sng_data[track_addr]
            (mêmes opcodes/notes que ceux qu'on décode déjà)
```

Une **song = jusqu'à 13 pistes simultanées**, chacune un flux d'événements du même
format que nos cues. Dès qu'on a un `mdx`, notre séquenceur+moteur sait déjà tout
jouer — il suffit de brancher ce décodeur d'en-tête devant.

## Prochaine étape concrète

Chercher le/les fichier(s) **`mdx`** :
- **petits** (≤ 16 Ko), à côté des `pk*.sdx` wave dans les dossiers de stage/son ;
- peut-être un préfixe/dossier différent (bgm, music, sng…), pas forcément `.sdx` ;
- premier octet = petit nombre (n_songs, 1..8), suivi d'une table de pointeurs.

Si tu en trouves un dans `us/stage/tales/` (ou ailleurs), envoie-le : on branche le
décodeur ci-dessus et on écoute une **vraie musique orchestrée** pour la première fois.

Candidats jamais explorés pour le moment (dump Substance réel disponible depuis peu) :
`tests/mgs2_substance_2003/cache.dar`, `cache.qar`, `scenerio.gcx`, `data.cnf`.

**Attention, Substance PC ≠ Master Collection — et c'est MC qui colle au PS2, pas
Substance.** Contre-intuitif vu les dates (2003 vs 2023), mais c'est ce que l'audit
confirme sur les données réelles : les `.sdx` de **Master Collection suivent fidèlement
le driver PS2 `raven`** (`docs/AUDIT_SDX.md` : les 6 banques réelles collent à raven
sur quasiment tout). **Substance (2003), pourtant le portage PS2→PC le plus ancien, a
son propre layout `.sdx` divergent** (répertoire `voice_tbl` pas à `0x800` — M3 dans
`docs/AUDIT.md`), qu'on n'a même pas encore fini de reverse. Donc un `mdx` trouvé côté
Substance **ne sera probablement pas le fichier ni le format de MC** — Substance a déjà
montré qu'elle ne suit pas les mêmes conventions que MC sur ce point précis du format.
Ce que ça peut quand même apporter : comprendre à quoi ressemble *un vrai mécanisme
d'orchestration mdx qui fonctionne* (structure `sng_data`, codes son, 13 pistes) donne
un modèle conceptuel à chercher dans les données MC elles-mêmes, même si le format
byte-à-byte ne sera pas transposable tel quel.

**Ce chantier (orchestration native, modifier la musique du jeu) est un objectif à
très long terme du projet** — pas la prochaine étape. Pour l'instant, la piste
Substance (`cache.dar`/`cache.qar`/`scenerio.gcx`) reste une curiosité à explorer
« si l'occasion se présente », pas une priorité active.

**Si un `mdx` est trouvé et décodé**, ça ira probablement dans un **nouvel onglet
dédié** (« Orchestration » ou équivalent) plutôt que dans l'onglet Séquenceur actuel :
le séquenceur rend des *cues* isolées (1-3 pistes, surtout des SE), alors qu'une song
`mdx` assemble jusqu'à 13 pistes simultanées avec les codes son de transition
(alerte, évasion, first-person…) — un modèle de données et une UI assez différents
pour mériter leur propre onglet plutôt que d'être forcés dans l'existant.
