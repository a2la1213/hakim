"""Trois nombres par morceau de voix, sans garder le son (demande de Hakim, accord d'Ahmed, 2026-10-23 : « suivre ma voix
dans le temps ») : la durée, l'énergie (dB), la hauteur médiane (autocorrélation, 70–400 Hz). Avec les réglages que la
synthèse a reçus (expressivité, guidage), une ligne par morceau dans ~/AIOS/jarvis/voix-mesures.jsonl. Quelques octets,
quelques millisecondes ; jamais bloquant pour la voix.
"""
import json
import os
import time
from pathlib import Path

import numpy as np

FICHIER = Path(os.environ.get("JARVIS_VOIX_MESURES", Path.home() / "AIOS" / "jarvis" / "voix-mesures.jsonl"))


def mesurer(audio, sr):
    """{"duree_s", "energie_db", "hauteur_hz"} d'un signal mono en flottants (−1 à 1)."""
    x = np.asarray(audio, dtype=np.float64).reshape(-1)
    duree = len(x) / float(sr) if sr else 0.0
    rms = float(np.sqrt(np.mean(x ** 2))) if len(x) else 0.0
    hauteurs, n = [], int(0.04 * sr)
    lo, hi = int(sr / 400), int(sr / 70)
    for i in range(0, max(0, len(x) - n), n):
        f = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt(np.mean(f ** 2)) < 0.02:
            continue
        ac = np.correlate(f, f, "full")[n - 1:]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[0] > 0 and ac[k] > 0.3 * ac[0]:
            hauteurs.append(sr / k)
    return {"duree_s": round(duree, 3), "energie_db": round(20 * float(np.log10(max(rms, 1e-9))), 1),
            "hauteur_hz": round(float(np.median(hauteurs)), 1) if hauteurs else None}


def noter(audio, sr, texte="", langue="fr", reglages=None, fichier=None):
    try:
        o = {"ts": round(time.time(), 3), **mesurer(audio, sr), "mots": len(str(texte or "").split()), "langue": langue,
             **{k: v for k, v in (reglages or {}).items() if k in ("exaggeration", "cfg_weight")}}
        f = Path(fichier or FICHIER)
        with f.open("a", encoding="utf-8") as h:
            h.write(json.dumps(o) + "\n")
        return o
    except Exception:
        return None
