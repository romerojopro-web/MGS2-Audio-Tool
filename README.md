# MGS2 SDT Tool

Outil de doublage pour les fichiers audio `.sdt` de **Metal Gear Solid 2 : Sons of Liberty** (Master Collection, version PC).

Il permet d'ouvrir un fichier `.sdt` du jeu, d'écouter le dialogue original, de l'exporter en WAV, puis de **remplacer la voix par la vôtre** pour créer un doublage maison.

---

## Fonctionnalités

- **Ouvrir** un fichier `.sdt` et afficher sa durée et ses infos.
- **Écouter** le dialogue original directement dans l'application.
- **Exporter** l'audio en `.wav` (pour identifier la réplique ou l'éditer).
- **Remplacer** l'audio par votre propre enregistrement `.wav`.
- **Sauvegarder** un `.sdt` modifié qui garde exactement la même structure que l'original — prêt à être remis dans le jeu.

La conversion de format (mono, 44100 Hz) et l'encodage sont automatiques.

---

## Le format SDT (notes techniques)

Ces informations ont été obtenues par rétro-ingénierie du format et validées à l'oreille sur des dialogues connus du jeu.

- **Codec** : PlayStation 4-bit ADPCM (PS-ADPCM / VAG).
- **Fréquence** : 44100 Hz, mono.
- **Structure** : un en-tête (table + métadonnées) suivi d'une série de blocs (« MG blocks »). Chaque bloc = 16 octets d'en-tête + jusqu'à 0x4000 octets de données audio. Le dernier bloc peut être plus court. Mis bout à bout, les blocs forment le flux audio complet.

Le décodeur/encodeur PS-ADPCM est implémenté en Python pur dans `sdt_core.py`, sans dépendance externe.

---

## Installation

Nécessite **Python 3.10+** et **PyQt6**.

```bash
pip install PyQt6
```

## Utilisation

```bash
python sdt_tool.py
```

Puis, dans l'application :

1. **Ouvrir un fichier SDT** — sélectionnez un `.sdt` du jeu (ex. `vc000101.sdt`).
2. **Écouter** — lisez le dialogue pour l'identifier, ou exportez-le en WAV.
3. **Choisir votre doublage** — un fichier `.wav` de votre voix (idéalement de même durée).
4. **Générer** — enregistrez le `.sdt` modifié.

Remplacez ensuite le fichier original du jeu par le vôtre.
**Faites toujours une sauvegarde du fichier d'origine avant de le remplacer.**

### Ligne de commande (bonus)

Le moteur peut aussi être utilisé seul :

```bash
# Afficher les infos et exporter en WAV
python sdt_core.py vc000101.sdt sortie.wav
```

---

## Conseils pour le doublage

- Enregistrez votre voix à **44100 Hz** si possible (sinon l'outil rééchantillonne).
- Visez la **même durée** que l'original : un enregistrement plus long est tronqué, un plus court est complété par du silence.
- Le fichier de sortie conserve la taille exacte de l'original, ce qui est nécessaire pour que le jeu le relise correctement.

---

## Avertissement

Projet non officiel, sans lien avec Konami. Fourni tel quel, à des fins de création et de modding personnel. Utilisez uniquement avec des fichiers issus de votre propre copie du jeu.

## Licence

Libre — faites-en ce que vous voulez.
