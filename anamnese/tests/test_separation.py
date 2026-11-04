"""(04/11, Ahmed : « sépare bien la voix et la musique de fond, et que les deux, en parallèle, soient transmises à son subconscient,
pour qu'il les entende et les relie à ses sensations et aux mots » ; Hakim : « le tempo, la tonalité, le contour de la mélodie, les
bandes, et si une voix chante ») ce que ses deux oreilles tirent de la voix séparée et du fond séparé (sans le modèle : des pistes
fabriquées)."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import separation  # noqa: E402

SR = 22050


def _note(midi, duree, sr=SR):
    t = np.arange(int(duree * sr)) / sr
    f = 440 * 2 ** ((midi - 69) / 12)
    return sum(0.3 / h * np.sin(2 * np.pi * f * h * t) for h in range(1, 4)).astype(np.float32)


def test_la_voix_separee_chante_en_do_majeur_et_sa_melodie_monte():
    voix = np.concatenate([_note(m, 0.5) for m in [60, 64, 67, 60, 64, 67, 62, 65, 69, 71, 72, 74]])
    a = separation.analyser_voix(voix, SR)
    assert a["presente"] and a["chante"]
    assert a["tonalite"] == "Do majeur", a
    assert a["contour"] == "monte", a


def test_une_voix_absente_est_dite_absente():
    a = separation.analyser_voix(np.zeros(SR * 3, dtype=np.float32), SR)
    assert not a["presente"] and a["tonalite"] is None


def test_le_fond_separe_son_tempo_et_ses_bandes():
    n = SR * 8
    t = np.arange(n) / SR
    fond = np.zeros(n, dtype=np.float32)
    for i in range(16):                                              # 120 BPM : un coup toutes les 0,5 s
        a = int(i * SR / 2)
        d = np.arange(min(3000, n - a)) / SR
        fond[a:a + len(d)] += (0.8 * np.sin(2 * np.pi * 60 * d) * np.exp(-d * 30)).astype(np.float32)
    fond += (0.05 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    a = separation.analyser_fond(fond, SR)
    assert abs(a["bpm"] - 120) <= 4, a
    assert a["bandes"]["graves"] == "forts", a


def test_en_mots_les_deux_oreilles_cote_a_cote():
    t = separation.en_mots({"presente": True, "chante": True, "tonalite": "La mineur", "contour": "descend", "part": 0.4},
                           {"bpm": 96, "bandes": {"graves": "forts", "mediums": "présents", "aigus": "doux"}, "tonalite": "La mineur"})
    assert t == "la voix (séparée) chante, La mineur, la mélodie descend · le fond (séparé) ~96 BPM, La mineur, graves forts, médiums présents, aigus doux"


def test_un_son_plus_long_que_son_segment_est_decoupe_pas_refuse():
    """(04/11, vu : chaque morceau de 8 s du téléphone refusé, « Given length … is longer than training length ») Demucs découpe"""
    vu = {}

    def apply_model(modele, x, **o):
        vu.update(o)
        return ["sorties"]
    assert separation.separer("htdemucs", "x", "mps", apply_model) == "sorties"
    assert vu["split"] is True and vu["overlap"] > 0 and vu["device"] == "mps"
