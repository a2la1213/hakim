"""(07/11, Hakim, accord d'Ahmed « lance tout, a b c d ») écouter vraiment un morceau : tempo et tonalité uniques, rythme sur la grille,
la 808 et ses glissés, la bibliothèque d'instruments, la légende et la ressemblance — les parties numpy, sans modèle."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import instruments as I  # noqa: E402

SR = 22050


def clics(bpm, duree=12.0, sr=SR, freq=60.0):
    x = np.zeros(int(duree * sr), np.float32)
    pas = 60.0 / bpm
    t = np.arange(int(0.05 * sr)) / sr
    coup = (np.sin(2 * np.pi * freq * t) * np.exp(-t * 60)).astype(np.float32)
    for k in range(int(duree / pas)):
        i = int(k * pas * sr)
        x[i:i + len(coup)] += coup[: len(x) - i]
    return x


def test_un_tempo():
    for bpm in (90, 140, 160):
        e, fps = I.enveloppe(clics(bpm), SR, 30, 8000)
        assert abs(I.tempo(e, fps) - bpm) <= 3, bpm


def test_une_tonalite():
    t = np.arange(int(3 * SR)) / SR
    la_mineur = sum(np.sin(2 * np.pi * f * t) for f in (220.0, 261.63, 329.63, 440.0))   # La, Do, Mi
    assert I.tonalite(I.chroma(la_mineur, SR))[:2] == ("A", "minor")


def test_le_rythme_sur_la_grille_et_les_roulements():
    bpm, mesure = 120.0, 2.0                               # 16 cases de 0,125 s
    kick = [b * mesure + c * 0.125 for b in range(4) for c in (0, 8)]
    assert I.grille(kick, bpm) == "x.......x......."
    hh = [i * 0.125 for i in range(64)]
    assert I.roulements(hh, bpm) == 0.0
    rouleau = hh + [k * 0.125 + 0.0625 for k in range(0, 64, 2)]
    assert I.roulements(sorted(rouleau), bpm) > 0.3


def test_la_808_glisse_mais_un_saut_franc_non():
    la, mi = 55.0, 82.41
    glisse = [la * 2 ** (k / 12 * 7 / 5) for k in range(6)] + [mi] * 4   # 7 demi-tons en 5 petits pas
    saut = [la] * 5 + [mi] * 5
    assert I.glisses(glisse) == 1
    assert I.glisses(saut) == 0
    assert I.notes_principales([la] * 6 + [mi] * 3 + [None]) == ["A", "E"]


def test_la_bibliotheque_apprend_et_reconnait(tmp_path):
    f = tmp_path / "instruments-connus.json"
    b = I.apprendre_empreinte([], "darbuka de papa", [1.0, 0.0, 0.0])
    b = I.apprendre_empreinte(b, "Darbuka de papa", [0.8, 0.2, 0.0])
    assert len(b) == 1 and b[0]["n"] == 2, "le même nom : son empreinte s'affine"
    I.ecrire_bibliotheque(b, f)
    l = I.lire_bibliotheque(f)
    assert I.reconnaitre([0.95, 0.1, 0.0], l)[0] == "darbuka de papa"
    assert I.reconnaitre([0.0, 0.0, 1.0], l) is None, "loin de tout : pas reconnu"


def test_legende_mots_et_ressemblance():
    a = {"tempo": 140.0, "tonalite": ("A", "minor", 0.8), "rythme": {"motifs": {"kick": "x.......x.......", "caisse": "....x.......x...",
         "hihats": "x.x.x.x.x.x.x.x."}, "roulements_hihats": 0.3}, "basse": {"notes": ["A", "F"], "glisses": 4},
         "instruments": [{"piste": "other", "noms": [["mandolin", 0.8]], "notes": ["A", "C", "E"]}, {"piste": "drums", "noms": [["trap hi-hats", 0.9]]}]}
    l = I.legende(a)
    assert l.startswith("140 BPM, A minor") and "rolling trap hi-hat" in l and "sliding 808 bass on A, F" in l and "mandolin melody (A, C, E)" in l
    assert "La mineur" in I.en_mots(a)
    assert I.ressemblance(a, a)["score"] == 1.0
    b = {**a, "tempo": 70.0, "tonalite": ("C", "major", 0.7)}
    r = I.ressemblance(a, b)
    assert r["tempo"] == 1.0, "la moitié du tempo : le même groove"
    assert r["tonalite"] == 0.7, "la relative majeure"
    c = {**a, "tempo": 100.0, "tonalite": ("D", "major", 0.7), "instruments": [{"piste": "other", "noms": [["piano", 0.9]]}],
         "rythme": {"motifs": {"kick": "x...x...x...x...", "caisse": "................", "hihats": "................"}}}
    assert I.ressemblance(a, c)["score"] < 0.4
