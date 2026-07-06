#!/usr/bin/env python3
"""
sdt_core.py — Moteur de conversion pour les fichiers SDT de Metal Gear Solid 2
              (Master Collection, version PC).

Format découvert par analyse (rétro-ingénierie) :
  - Codec audio : PlayStation 4-bit ADPCM (PS-ADPCM / VAG)
  - Fréquence   : 44100 Hz, mono
  - Structure   : en-tête (TOC + méta) puis une suite de "MG blocks"
                  (blocs Metal Gear). Chaque bloc = 16 octets d'en-tête
                  + 0x4000 octets de données audio (le dernier bloc peut
                  être plus court). Les blocs mis bout à bout forment le
                  flux audio complet.

Ce module ne dépend d'aucune bibliothèque externe : le décodage et
l'encodage PS-ADPCM sont implémentés en Python pur.
"""

import struct
import wave
from dataclasses import dataclass, field
from typing import List, Optional, Tuple


# ─────────────────────────────────────────────────────────────────────────────
# Constantes du format
# ─────────────────────────────────────────────────────────────────────────────

BLOCK_HEADER_SIZE = 16          # en-tête de chaque MG block
FULL_BLOCK_DATA = 0x4000        # taille des données d'un bloc plein
DEFAULT_SAMPLE_RATE = 44100

# Coefficients de prédiction Sony PS-ADPCM (échelle /64)
VAG_COEFS = [
    (0.0, 0.0),
    (60.0 / 64.0, 0.0),
    (115.0 / 64.0, -52.0 / 64.0),
    (98.0 / 64.0, -55.0 / 64.0),
    (122.0 / 64.0, -60.0 / 64.0),
]


# ─────────────────────────────────────────────────────────────────────────────
# Représentation d'un fichier SDT
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AudioBlock:
    """Un bloc audio dans le fichier."""
    file_offset: int      # position de l'en-tête du bloc dans le fichier
    total_size: int       # taille totale (en-tête + données)
    data_offset: int      # position des données (file_offset + 16)
    data_size: int        # taille des données audio


@dataclass
class SDTFile:
    """Un fichier SDT parsé."""
    path: str
    raw: bytes
    sample_rate: int = DEFAULT_SAMPLE_RATE
    blocks: List[AudioBlock] = field(default_factory=list)

    @property
    def total_audio_bytes(self) -> int:
        return sum(b.data_size for b in self.blocks)

    @property
    def duration_seconds(self) -> float:
        # PS-ADPCM : 16 octets -> 28 samples
        n_samples = (self.total_audio_bytes // 16) * 28
        return n_samples / self.sample_rate


# ─────────────────────────────────────────────────────────────────────────────
# Parsing
# ─────────────────────────────────────────────────────────────────────────────

def parse_sdt(path: str) -> SDTFile:
    """Lit un fichier SDT et repère ses blocs audio."""
    with open(path, "rb") as f:
        raw = f.read()

    sdt = SDTFile(path=path, raw=raw)

    # Fréquence d'échantillonnage : stockée en big-endian à 0x96 dans l'en-tête
    if len(raw) >= 0x98:
        sr = (raw[0x96] << 8) | raw[0x97]
        if sr in (8000, 11025, 16000, 22050, 24000, 32000, 44100, 48000):
            sdt.sample_rate = sr

    # Repérer les blocs audio (type 1). Le dernier peut être plus petit.
    pos = 0
    while pos < len(raw) - 8:
        typ = struct.unpack_from("<I", raw, pos)[0]
        sz = struct.unpack_from("<I", raw, pos + 4)[0]
        if typ == 1 and 0x1000 <= sz <= 0x4010 and pos + sz <= len(raw):
            sdt.blocks.append(AudioBlock(
                file_offset=pos,
                total_size=sz,
                data_offset=pos + BLOCK_HEADER_SIZE,
                data_size=sz - BLOCK_HEADER_SIZE,
            ))
            pos += sz
        else:
            pos += 4

    return sdt


def get_audio_stream(sdt: SDTFile) -> bytes:
    """Concatène les données de tous les blocs = flux PS-ADPCM complet."""
    return b"".join(
        sdt.raw[b.data_offset:b.data_offset + b.data_size]
        for b in sdt.blocks
    )


# ─────────────────────────────────────────────────────────────────────────────
# Décodage PS-ADPCM  →  PCM 16 bits
# ─────────────────────────────────────────────────────────────────────────────

def decode_psadpcm(adpcm: bytes) -> List[int]:
    """Décode un flux PS-ADPCM (blocs de 16 octets) en samples PCM 16 bits."""
    samples: List[int] = []
    hist1 = 0.0
    hist2 = 0.0

    for off in range(0, len(adpcm) - 15, 16):
        header = adpcm[off]
        shift = header & 0x0F
        filt = (header >> 4) & 0x0F
        if filt >= len(VAG_COEFS):
            filt = 0
        c0, c1 = VAG_COEFS[filt]

        # flag = adpcm[off + 1]  (0x07 = fin de flux ; ignoré ici)

        for i in range(14):
            byte = adpcm[off + 2 + i]
            for nibble in (byte & 0x0F, (byte >> 4) & 0x0F):
                # signe sur 4 bits
                s = nibble - 16 if nibble >= 8 else nibble
                # remise à l'échelle
                sample = (s << 12) >> shift if shift <= 12 else 0
                sample += c0 * hist1 + c1 * hist2
                sample = max(-32768.0, min(32767.0, sample))
                samples.append(int(round(sample)))
                hist2 = hist1
                hist1 = sample

    return samples


def sdt_to_pcm(sdt: SDTFile) -> List[int]:
    """Décode le fichier SDT complet en samples PCM 16 bits mono."""
    return decode_psadpcm(get_audio_stream(sdt))


def save_wav(samples: List[int], path: str, sample_rate: int = DEFAULT_SAMPLE_RATE):
    """Écrit une liste de samples 16 bits dans un fichier WAV mono."""
    with wave.open(path, "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        clamped = [max(-32768, min(32767, s)) for s in samples]
        wf.writeframes(struct.pack(f"<{len(clamped)}h", *clamped))


def sdt_to_wav(sdt: SDTFile, out_path: str):
    """Convertit un fichier SDT en WAV."""
    samples = sdt_to_pcm(sdt)
    save_wav(samples, out_path, sdt.sample_rate)
    return len(samples)


# ─────────────────────────────────────────────────────────────────────────────
# Encodage PCM 16 bits  →  PS-ADPCM
# ─────────────────────────────────────────────────────────────────────────────

def _encode_block(samples28: List[int], prev1: float, prev2: float
                  ) -> Tuple[bytes, float, float]:
    """Encode 28 samples en un bloc PS-ADPCM de 16 octets."""
    best = None
    for filt in range(5):
        c0, c1 = VAG_COEFS[filt]
        for shift in range(13):
            p1, p2 = prev1, prev2
            encoded = []
            max_err = 0.0
            for s in samples28:
                predicted = p1 * c0 + p2 * c1
                diff = s - predicted
                q = int(round(diff * (1 << shift) / 4096.0))
                q = max(-8, min(7, q))
                dec = (q * 4096.0) / (1 << shift) + predicted
                dec = max(-32768.0, min(32767.0, dec))
                err = abs(dec - s)
                if err > max_err:
                    max_err = err
                encoded.append(q & 0xF)
                p2, p1 = p1, dec
            if best is None or max_err < best[0]:
                best = (max_err, filt, shift, encoded, p1, p2)

    _, filt, shift, encoded, np1, np2 = best
    block = bytearray(16)
    block[0] = (filt << 4) | shift
    block[1] = 0
    for i in range(0, 28, 2):
        block[2 + i // 2] = (encoded[i] & 0xF) | ((encoded[i + 1] & 0xF) << 4)
    return bytes(block), np1, np2


def encode_psadpcm(samples: List[int]) -> bytes:
    """Encode des samples PCM 16 bits en flux PS-ADPCM."""
    out = bytearray()
    p1 = p2 = 0.0
    # Compléter à un multiple de 28
    padded = list(samples)
    if len(padded) % 28 != 0:
        padded += [0] * (28 - len(padded) % 28)
    for i in range(0, len(padded), 28):
        blk, p1, p2 = _encode_block(padded[i:i + 28], p1, p2)
        out += blk
    return bytes(out)


def load_wav_mono(path: str, target_rate: int = DEFAULT_SAMPLE_RATE) -> Tuple[List[int], int]:
    """
    Charge un WAV en samples mono 16 bits.
    Convertit stéréo→mono et rééchantillonne si nécessaire (simple, sans filtre).
    Retourne (samples, sample_rate_original).
    """
    with wave.open(path, "r") as wf:
        n_ch = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        n = wf.getnframes()
        raw = wf.readframes(n)

    # Convertir en samples 16 bits
    if width == 2:
        data = list(struct.unpack(f"<{len(raw)//2}h", raw))
    elif width == 1:
        data = [(b - 128) * 256 for b in raw]
    else:
        # 24/32 bits : ne garder que les 2 octets de poids fort
        step = width
        data = []
        for i in range(0, len(raw), step):
            data.append(struct.unpack_from("<h", raw, i + step - 2)[0])

    # Stéréo → mono
    if n_ch > 1:
        mono = []
        for i in range(0, len(data) - n_ch + 1, n_ch):
            mono.append(sum(data[i:i + n_ch]) // n_ch)
        data = mono

    # Rééchantillonnage naïf (plus proche voisin) si besoin
    if rate != target_rate and rate > 0:
        ratio = target_rate / rate
        new_len = int(len(data) * ratio)
        resampled = [data[min(len(data) - 1, int(i / ratio))] for i in range(new_len)]
        data = resampled

    return data, rate


# ─────────────────────────────────────────────────────────────────────────────
# Remplacement audio : injecter un nouveau WAV dans un SDT existant
# ─────────────────────────────────────────────────────────────────────────────

def replace_audio(sdt: SDTFile, new_samples: List[int]) -> bytes:
    """
    Remplace l'audio du SDT par de nouveaux samples PCM 16 bits.

    L'audio est réencodé en PS-ADPCM puis redistribué dans les blocs
    existants (mêmes tailles). Si le nouvel audio est plus court, on
    complète avec du silence ; s'il est plus long, il est tronqué à la
    capacité totale des blocs, de façon à conserver EXACTEMENT la même
    structure de fichier (indispensable pour que le jeu le relise).

    Retourne les octets du nouveau fichier SDT.
    """
    total_capacity = sdt.total_audio_bytes  # octets PS-ADPCM disponibles
    # 16 octets ADPCM = 28 samples
    max_samples = (total_capacity // 16) * 28

    samples = list(new_samples)
    if len(samples) < max_samples:
        samples += [0] * (max_samples - len(samples))
    else:
        samples = samples[:max_samples]

    new_adpcm = encode_psadpcm(samples)
    # Ajuster à la capacité exacte
    if len(new_adpcm) < total_capacity:
        new_adpcm += b"\x00" * (total_capacity - len(new_adpcm))
    else:
        new_adpcm = new_adpcm[:total_capacity]

    # Réinjecter bloc par bloc
    raw = bytearray(sdt.raw)
    cursor = 0
    for b in sdt.blocks:
        chunk = new_adpcm[cursor:cursor + b.data_size]
        raw[b.data_offset:b.data_offset + b.data_size] = chunk
        cursor += b.data_size

    return bytes(raw)


def save_sdt(raw: bytes, path: str):
    with open(path, "wb") as f:
        f.write(raw)


# ─────────────────────────────────────────────────────────────────────────────
# Résumé lisible
# ─────────────────────────────────────────────────────────────────────────────

def describe(sdt: SDTFile) -> str:
    return (
        f"Fichier : {sdt.path.split('/')[-1]}\n"
        f"Taille  : {len(sdt.raw):,} octets\n"
        f"Fréquence : {sdt.sample_rate} Hz (mono)\n"
        f"Blocs audio : {len(sdt.blocks)}\n"
        f"Durée : {sdt.duration_seconds:.2f} s"
    )


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1:
        s = parse_sdt(sys.argv[1])
        print(describe(s))
        if len(sys.argv) > 2:
            sdt_to_wav(s, sys.argv[2])
            print(f"→ WAV écrit : {sys.argv[2]}")
