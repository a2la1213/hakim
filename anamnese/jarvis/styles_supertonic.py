"""(04/11, Ahmed : « entraîne Supertonic avec les émotions de Chatterbox, qu'on sente ses émotions dans sa voix, et rattache-le
comme Chatterbox ») ses styles d'émotion pour la voix du téléphone (Supertonic 3, voix M1).

Un style Supertonic : un style de timbre (50 lignes de 256) et un style de durée (8 lignes de 16), chaque ligne sur la sphère
unité (vérifié sur les dix styles publiés). Une émotion = la voix M1 poussée dans la direction qui sépare, chez Chatterbox, cette
émotion de sa voix neutre (les deux styles retrouvés de la même façon, d'enregistrements de Chatterbox) ; le biais de la méthode
s'annule dans la différence. Le style de durée reste celui de M1 : son débit par émotion est déjà réglé (interieur.VOIX_EMOTION).
Le téléphone mélange M1 et le style d'une émotion selon son intensité (melanger), avec la même formule."""
import json
import time
from pathlib import Path

import numpy as np

FORMES = {"ttl": (50, 256), "dp": (8, 16)}
CLES = {"ttl": "style_ttl", "dp": "style_dp"}


def sur_la_sphere(x):
    x = np.asarray(x, dtype=np.float64)
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    return x / np.where(n > 0, n, 1.0)


def lire(chemin):
    brut = json.loads(Path(chemin).read_text())
    s = {}
    for k, forme in FORMES.items():
        a = np.asarray(brut[CLES[k]]["data"], dtype=np.float64)
        if a.size != forme[0] * forme[1]:
            raise ValueError(f"{chemin} : {CLES[k]} de {a.size} valeurs, {forme[0]}×{forme[1]} attendues")
        s[k] = a.reshape(forme)
    return s


def ecrire(style, chemin, source=""):
    brut = {CLES[k]: {"data": np.asarray(style[k], dtype=np.float32).reshape((1,) + forme).tolist(),
                      "dims": [1, *forme], "type": "float32"} for k, forme in FORMES.items()}
    brut["metadata"] = {"source": source, "cree": time.strftime("%Y-%m-%dT%H:%M:%S")}
    Path(chemin).write_text(json.dumps(brut))


def appliquer(base, emotion, neutre, force):
    """base + force × (émotion − neutre), chaque ligne ramenée sur la sphère ; la durée de la base"""
    return {"ttl": sur_la_sphere(base["ttl"] + force * (emotion["ttl"] - neutre["ttl"])), "dp": np.array(base["dp"])}


def melanger(base, emotion, t):
    """de la base (t = 0) au style de l'émotion (t = 1), chaque ligne sur la sphère ; la durée de la base"""
    return {"ttl": sur_la_sphere((1 - t) * base["ttl"] + t * emotion["ttl"]), "dp": np.array(base["dp"])}
