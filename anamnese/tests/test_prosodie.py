"""La prosodie d'Ahmed mot par mot (jarvis/prosodie.py) : sur des voix synthétiques (des sons voisés à hauteur connue)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import prosodie as P  # noqa: E402

SR = 16000


def voix(f0s, duree=0.4, blanc=0.1, fin=None):
    """Une « phrase » : un son voisé (harmoniques) par mot, à la hauteur donnée, séparés de silences ; fin : glissando final."""
    morceaux, mots, t = [], [], 0.0
    for k, f0 in enumerate(f0s):
        n = int(duree * SR)
        tt = np.arange(n) / SR
        frequence = np.full(n, f0, dtype=float)
        if fin and k == len(f0s) - 1:
            frequence = np.linspace(f0, f0 * fin, n)
        phase = 2 * np.pi * np.cumsum(frequence) / SR
        s = sum(np.sin(h * phase) / h for h in range(1, 6)) * 0.2
        morceaux += [s, np.zeros(int(blanc * SR))]
        mots.append((f"mot{k}", t, t + duree))
        t += duree + blanc
    return np.concatenate(morceaux).astype(np.float32), mots


def test_hauteur_estimee():
    a, _ = voix([150.0], duree=1.0)
    f0, _db = P.trames(a)
    assert abs(np.nanmedian(f0) - 150) < 6


def test_mot_appuye_et_fin_montante_avec_les_temps_exacts():
    a, mots = voix([120, 118, 175, 116, 114, 115], fin=1.6)
    p = P.analyser(a, [], mots=mots)
    assert p["appuyes"] == ["mot2"] and p["fin"] == "montante" and p["approche"] is False


def test_prorata_sur_un_segment_et_fin_descendante():
    a, mots = voix([130, 128, 190, 126, 125, 124], fin=0.6)
    seg = [{"start": 0.0, "end": mots[-1][2], "text": "un deux trois quatre cinq six"}]
    seg[0]["text"] = "allo merci genial bravo cinqx sixxx"          # mots de même longueur : le prorata tombe juste
    p = P.analyser(a, seg)
    assert p["approche"] and p["appuyes"] == ["genial"] and p["fin"] == "descendante"
    assert P.texte(p) == "appuyé vers : genial ; fin descendante"


def test_rien_sans_voix():
    assert P.analyser(np.zeros(SR * 2, dtype=np.float32), []) is None
