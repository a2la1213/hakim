"""Baselines circadiennes — corrélat physiologique du moment de la journée.

`baselines_now(hour)` renvoie les baselines de cortisol et de mélatonine en
fonction de l'heure locale (0..24). Pur, déterministe, stdlib seulement (math) :
aucun I/O, 100% offline. Placé dans `modules/proposed/` (NON chargé par le
registry) ; `affect.py` l'importe directement via importlib et retombe sur des
baselines statiques si ce fichier manque (dégradation propre).

Modèle : cosinus lisse (continu, périodique 24h → pas de saut au wrap).
  * cortisol   : pic le matin (~8h, ~0.35), plancher soir/nuit (~0.10)
                 [rythme HPA, réveil]. Un cosinus unique met le nadir ~12h
                 après le pic ; approximation assumée d'un profil réel asymétrique.
  * mélatonine : inverse — haute la nuit (pic ~3h, ~0.70), basse le jour (~0.05),
                 montée le soir (DLMO ~21h) [marqueur SCN nocturne].
"""

import math

_TWO_PI = 2.0 * math.pi


def _cosine(hour, peak_hour, low, high):
    """Cosinus lisse valant `high` à `peak_hour`, `low` au point opposé (±12h)."""
    mean = (high + low) / 2.0
    amp = (high - low) / 2.0
    val = mean + amp * math.cos(_TWO_PI * (hour - peak_hour) / 24.0)
    return max(0.0, min(1.0, val))


def baselines_now(hour: float) -> dict:
    """Baselines circadiennes {cortisol, melatonine} pour l'heure locale donnée."""
    h = float(hour) % 24.0
    return {
        "cortisol":   _cosine(h, peak_hour=8.0, low=0.10, high=0.35),
        "melatonine": _cosine(h, peak_hour=3.0, low=0.05, high=0.70),
    }
