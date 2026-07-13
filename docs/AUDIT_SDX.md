# Audit du format SDX — état vs raven

Comparaison systématique de `mgs2-audio-tool` avec le driver de référence
`KieronJ/raven`, sur toute la chaîne : banque `.sdx` → répertoire d'instruments →
séquenceur → moteur SPU. Mesuré sur les 6 banques `pk00000x.sdx` (1536 cues,
7730 notes, 786 entrées d'instrument).

**Verdict : fidèle à raven sur tout ce que ces banques utilisent, à une exception
audible près — la courbe de pan (`pant[]`).** Les fonctionnalités non implémentées
ne sont jamais employées par ces banques (impact nul, chiffres à l'appui).

---

## 1. Fidèle et vérifié ✅

| Domaine | État |
|---------|------|
| **Codec PS-ADPCM** | Coefficients {60,0} {115,−52} {98,−55} {122,−60} = identiques à `adpcm_filters` de raven. Décodage correct. |
| **Layout banque** | Répertoire à 0x800, audio après padding, table de cues à `fsize−0x6800`, séquence à `fsize−0x5800`. |
| **Répertoire = `WAVE_W`** | 16 octets : addr, sample_note, sample_tune, ADSR, pan, modes. Tous lus. |
| **Table d'opcodes** | Les 128 entrées `cntl_tbl[opcode−0x80]`, assignations d'octets `b0 b1 b2 opcode`. |
| **Tempo** | `0xD0` = tempo ; `ticks/s = (44100/448)·tmp/256`. |
| **Modèle de note** | b0 = volume, b1 = gate %, b2 = longueur. |
| **Hauteur** | `freq_tbl` de raven + interpolation `freq_set` ; correction par instrument `sample_note`/`sample_tune`. |
| **Enveloppe** | ADSR par défaut de l'instrument + opcodes `0xD7/D8/D9` ; inversions correctes ; modes lin/exp (`a/s/r_mode`). |
| **Pan (valeur)** | `panf = signed(b1)+20` sur 0..40 ; `panmod` + pan par défaut de l'instrument. |
| **Sweep** | `0xE5 sws_set` : scoop `−signed(b0)` demi-tons, hold b2, rampe b1. |
| **Glissandos** | `0xD1/D6/DE` : rampe linéaire par tick, snap final (`_Move`). |
| **Portamento** | `0xE6 por_set` : glisse depuis la note précédente (voir §2 pour la courbe). |
| **Boucles** | L1/L2/L3, crochet A-A-B (`kakko`), offsets volume/fréquence par passe. |
| **Divers** | `tie`, reverb on/off, transpose `0xDF`, detune fin `0xE0`, `rdm` pitch. |

---

## 2. Approximations (audibles) ⚠️

### 2.1 Courbe de pan — la seule qui compte vraiment
raven mappe pan→volume L/R via une **table** `pant[41]`, pas une loi `sqrt` :

```
vol_r = vol · pant[pan]        vol_l = vol · pant[40−pan]
pant = [0,2,4,7,10,13,16,20,24,28,32,36,40,45,50,55,60,65,70,75,
        80,84,88,92,96,100,104,107,110,112,114,116,118,120,122,123,124,125,126,127,127]
```

Au centre (pan 20) : `pant[20]/127 = 0.63` de chaque côté. Notre `sqrt(0.5) = 0.707`.
La table est plus creusée au centre et sa pente diffère → image stéréo et niveau
central légèrement faux sur **chaque note pannée**. **Correction propre : remplacer
`sqrt` par la table.** (Correctif recommandé n°1.)

### 2.2 Portamento — linéaire vs exponentiel
Notre glissando note-à-note est une rampe **linéaire** dont la durée dérive de la
vitesse. raven (`por_compute`) fait une **approche exponentielle** : chaque tick,
`swpd += (cible−swpd)·b2/256`. À corriger pour matcher la courbe (prochain réglage).

### 2.3 Vibrato — LFO approximé
`vib_set`/`vib_change` sont branchés, mais la forme/l'échelle exacte du LFO de raven
n'a pas été vérifiée au détail. À revoir au raffinement.

---

## 3. Non implémenté — mais INUTILISÉ par ces banques 🟦

Impact mesuré = nul sur `pk00000x` :

| Élément | raven | Usage mesuré | Impact |
|---------|-------|--------------|--------|
| `decl_vol` (octet 15) | `vol −= dec_vol` | tous à **0** | nul |
| `svl_set`/`svp_set` (0xD3/D4) | keyoff + `tone_set` (≈ prog change) | **0 event** | nul |
| Notes batterie (≥0x48) | `drum_set` (samples 263+), pitch fixe 0x24 | **0 / 7730 notes** | nul |

À câbler seulement si d'autres stages du jeu les emploient (ex. `us/stage/*`).

---

## 4. Nettoyage fait

- Supprimé un `vol_move_target = None` orphelin (variable disparue depuis le
  refactor des glissandos).

---

## 5. Généralisation multi-stages (test `us/stage/tales/`)

Testé sur 10 banques du dossier `tales`. Le dossier contient **deux sous-formats** :

| Sous-format | Fichiers tales | Adressage samples | Table de cues | État |
|-------------|----------------|-------------------|---------------|------|
| Musique (comme MGS2) | 003,004,005,007,008,009 | offsets fichier | à `fsize−0x6800` | **OK, audible** |
| SE / adressage SPU | 000,001,002,006 | **adresses SPU absolues** (0x150000…) | offset variable ou absente | partiel |

Constats et corrections apportées :
- **Table de cues à offset variable.** Notre `fsize−0x6800` est spécifique aux banques
  MGS2. Ajout d'un **scanner structurel** de secours (`_scan_cue_table`) : cherche un
  run de records de cues valides dont les pointeurs tombent sur de vrais événements.
  Rescape la localisation ; MGS2 et les 6 banques musique tales restent inchangés.
- **Dégradation gracieuse.** Si aucune table n'est trouvable (banque SE pure comme
  `000`), le parsing renvoie désormais 0 cue au lieu de lever une exception — les
  fonctions au niveau sample continuent de marcher.
- **Gap restant : adressage SPU.** Les banques `000/001/002/006` stockent l'adresse
  du sample en **espace SPU** (≥0x150000), pas en offset fichier. Nos samples ne se
  résolvent donc pas (rendu silencieux) même quand la séquence est correctement
  localisée. Support complet = convertir adresse SPU → offset fichier (chantier à part).

Le détecteur de répertoire (`WAVE_W`), lui, généralise correctement sur les 10 fichiers.

## 6. Feuille de route proposée

1. **Courbe de pan `pant[]`** (§2.1) — correctif de fidélité, ~5 lignes, impact sur
   chaque note pannée. *Le plus rentable.*
2. **Portamento exponentiel** (§2.2) — matcher `por_compute`.
3. **Raffinement** — vibrato (§2.3), et vérifs fines (reverb, offsets de boucle L3).
4. **Optimisation** — le rendu est lent (Python pur, échantillon par échantillon).
   Pistes : vectoriser `_play`/l'ADSR (numpy), précalculer les samples décodés par
   instrument, réduire les boucles chaudes. Objectif : écouter une partition sans
   faire chauffer le CPU. 🥵
