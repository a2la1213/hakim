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


# ---- (06/11, Ahmed : « parole, musique ou background, calés sur les mots ») les trois pistes : le fond, seconde par seconde ----

def _accord(fondamentale, mineur, duree, sr=SR):
    return sum(_note(fondamentale + k, duree, sr) for k in (0, 3 if mineur else 4, 7)) / 3


def test_un_accord_se_reconnait_majeur_ou_mineur():
    nom, s = separation.accord(separation._chroma(_accord(57, True, 1.0), SR))      # La mineur
    assert nom == "Lam" and s >= separation.SEUIL_ACCORD, (nom, s)
    nom, s = separation.accord(separation._chroma(_accord(53, False, 1.0), SR))     # Fa majeur
    assert nom == "Fa" and s >= separation.SEUIL_ACCORD, (nom, s)


def test_un_bruit_blanc_n_est_pas_un_accord():
    rng = np.random.default_rng(1)
    _, s = separation.accord(separation._chroma(rng.normal(0, 0.1, SR).astype(np.float32), SR))
    assert s < separation.SEUIL_ACCORD, s


def test_les_pistes_du_fond_disent_musique_et_accord_puis_bruit_et_chocs_a_leur_seconde():
    """2 s de La mineur puis 2 s de Fa, puis 2 s de bruit de pièce traversé de deux chocs : chaque seconde à sa place."""
    rng = np.random.default_rng(2)
    bruit = (0.02 * rng.normal(0, 1, SR * 2)).astype(np.float32)
    for a in (int(0.3 * SR), int(1.4 * SR)):
        bruit[a:a + 80] += 0.9
    fond = np.concatenate([_accord(57, True, 2.0), _accord(53, False, 2.0), bruit])
    voix = np.zeros_like(fond)
    p = separation.pistes_du_fond(fond + voix, voix, fond, SR)
    assert [w["quoi"] for w in p] == ["musique"] * 4 + ["bruit"] * 2, p
    assert [w.get("accord") for w in p[:4]] == ["Lam", "Lam", "Fa", "Fa"], p
    assert p[4]["chocs"] >= 1 and p[5]["chocs"] >= 1 and p[4]["nature"] == "chocs", p
    assert p[2]["t0"] == 2.0 and p[5]["t1"] == 6.0


def test_un_silence_reste_un_silence():
    fond = np.concatenate([_accord(60, False, 2.0), np.zeros(SR, np.float32)])
    p = separation.pistes_du_fond(fond, np.zeros_like(fond), fond, SR)
    assert p[-1]["quoi"] == "silence", p


def test_traiter_rend_les_pistes_quand_on_les_demande_et_seulement_alors():
    fond = _accord(57, True, 3.0)
    voix = (0.2 * _note(64, 3.0)).astype(np.float32)

    class O:
        taux = SR
        lire = staticmethod(lambda f: (fond + voix, SR))
        pistes = staticmethod(lambda x: {"vocals": voix, "drums": fond * 0, "bass": fond * 0, "other": fond})
    sans = separation.traiter({"fichier": "x.wav"}, O())
    assert "pistes" not in sans
    avec = separation.traiter({"fichier": "x.wav", "pistes": True}, O())
    assert avec["pistes"]["fenetres"][0]["accord"] == "Lam", avec["pistes"]
    assert avec["pistes"]["duree_s"] == 3.0 and avec["pistes"]["voix"] is True


def test_les_pistes_portent_la_melodie_de_la_voix_separee_a_sa_place_dans_le_bloc():
    """(11/11, Ahmed : « cale la hauteur de chaque syllabe sur la note du morceau ») Do4, Mi4, Sol4 (0,5 s chacune) puis 0,5 s de silence :
    chaque trame de 40 ms garde sa hauteur à sa place ; témoin : sans voix, pas de mélodie."""
    voix = np.concatenate([_note(60, 0.5), _note(64, 0.5), _note(67, 0.5), np.zeros(SR // 2, np.float32)])
    fond = (0.1 * _accord(57, True, 2.0)).astype(np.float32)

    class O:
        taux = SR
        lire = staticmethod(lambda f: (fond + voix, SR))
        pistes = staticmethod(lambda x: {"vocals": voix, "drums": fond * 0, "bass": fond * 0, "other": fond})
    m = separation.traiter({"fichier": "x.wav", "pistes": True}, O())["pistes"]["melodie"]
    assert m["pas_ms"] == 40
    hz = np.array(m["hz"], float)
    a_ = lambda t0, t1: np.median(hz[int(t0 / 0.04) + 1:int(t1 / 0.04) - 1])   # noqa: E731
    for (t0, t1), f in [((0, 0.5), 261.6), ((0.5, 1.0), 329.6), ((1.0, 1.5), 392.0)]:
        assert abs(1200 * np.log2(a_(t0, t1) / f)) < 30, (t0, a_(t0, t1), f)
    assert (hz[int(1.55 / 0.04):] == 0).all()

    class Sans(O):
        pistes = staticmethod(lambda x: {"vocals": voix * 0, "drums": fond * 0, "bass": fond * 0, "other": fond})
    assert "melodie" not in separation.traiter({"fichier": "x.wav", "pistes": True}, Sans())["pistes"]


def test_avec_la_cascade_les_pistes_et_la_voix_partent_avant_elle():
    """(06/11, mesuré : la cascade rajoutait 4 s avant que la grande oreille ait sa voix séparée) une réponse partielle d'abord"""
    fond = _accord(57, True, 3.0)
    voix = (0.2 * _note(64, 3.0)).astype(np.float32)
    envois, ordre = [], []

    class O:
        taux = SR
        lire = staticmethod(lambda f: (fond + voix, SR))
        pistes = staticmethod(lambda x: {"vocals": voix, "drums": fond * 0, "bass": fond * 0, "other": fond})
        ecrire = staticmethod(lambda f, son, taux: ordre.append("ecrit"))
        tot = staticmethod(lambda s: (envois.append(s), ordre.append("tot")))
    import types
    sep = types.ModuleType("x")
    orig = separation.en_cascade
    separation.en_cascade = lambda *a: (ordre.append("cascade"), {"instruments": []})[1]
    try:
        s = separation.traiter({"fichier": "x.wav", "pistes": True, "cascade": True, "voix_wav": "/tmp/v.wav"}, O())
    finally:
        separation.en_cascade = orig
    assert ordre == ["ecrit", "tot", "cascade"], ordre
    assert envois[0]["partiel"] and envois[0]["pistes"]["fenetres"] and envois[0]["voix_wav"] == "/tmp/v.wav"
    assert "pistes" not in s and "voix_wav" not in s


def test_vider_caches_rend_le_cache_du_gpu_quand_rien_n_attend():
    """(09/11) 3,4 Go de cache MPS gardés par Demucs : vidés après la réponse si aucune demande n'attend ; gardés sinon."""
    import os
    vides = []

    class _Mps:
        @staticmethod
        def is_available():
            return True

    class _Torch:
        class backends:
            mps = _Mps
        class mps:
            @staticmethod
            def empty_cache():
                vides.append(1)

    r, w = os.pipe()
    with os.fdopen(r) as entree, os.fdopen(w, "w") as sortie:
        assert separation.vider_caches(_Torch, entree) is True and vides == [1]
        sortie.write("{}\n"); sortie.flush()                          # une demande attend : on ne vide pas
        assert separation.vider_caches(_Torch, entree) is False and vides == [1]
