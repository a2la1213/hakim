"""(04/11, Ahmed : « le background qui contient des voix est aussi séparé en voix et background, et ainsi de suite jusqu'à 8 voix » ;
« 2 process : un pour background = voix + bruit, un pour la musique » ; « un instrument par cœur CPU, en premier les basses » ;
« chaque voix est séparée selon le volume et le timbre ») la séparation en cascade (jarvis/cascade.py) et son protocole
(separation.traiter), sans modèle : des voix fabriquées (une hauteur chacune), une fausse empreinte (l'énergie par bande de hauteur :
le « timbre » d'une voix fabriquée), un faux Demucs qui rend les pistes vraies. Aucun fichier hors de tmp_path."""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import cascade as C  # noqa: E402
import separation  # noqa: E402

SR = 16000


def _voix(f0, duree, amp=0.1, sr=SR):
    t = np.arange(int(duree * sr)) / sr
    env = np.minimum(1, np.minimum(t, duree - t) / 0.05)                  # fondu de 50 ms
    s = np.sin(2 * np.pi * f0 * t) + 0.3 * np.sin(2 * np.pi * 2 * f0 * t) + 0.1 * np.sin(2 * np.pi * 3 * f0 * t)
    return (amp * env * s).astype(np.float32)


def _scene(*tours, sr=SR, fin=0.3):
    """tours : (f0, début, durée, amplitude) ; rend le son."""
    n = int((max(d + l for _, d, l, _ in tours) + fin) * sr)
    x = np.zeros(n, np.float32)
    for f0, d, l, a in tours:
        v = _voix(f0, l, a, sr)
        x[int(d * sr):int(d * sr) + len(v)] += v
    return x


BANDES = np.geomspace(60, 700, 25)


def _empreintes(audios):
    """L'énergie par bande de hauteur (24 bandes entre 60 et 700 Hz), normée : deux voix fabriquées de hauteurs différentes ne se
    ressemblent pas, une fenêtre à cheval sur deux voix ressemble un peu aux deux."""
    out = []
    for a in audios:
        a = np.asarray(a, np.float64)
        S = np.abs(np.fft.rfft(a * np.hanning(len(a)))) ** 2
        f = np.fft.rfftfreq(len(a), 1 / SR)
        m = (f >= 60) & (f < 700)
        v = np.bincount(np.digitize(f[m], BANDES) - 1, weights=S[m], minlength=24)[:24]
        out.append(v / (np.linalg.norm(v) or 1.0))
    return np.array(out)


def _dans(masque, debut, fin):
    """La part des trames d'un masque entre debut et fin (s)."""
    i = np.flatnonzero(masque) / 100
    return float(((i >= debut) & (i <= fin)).mean()) if len(i) else 0.0


def test_trois_voix_qui_se_suivent_sont_trois_voix_chacune_a_son_moment():
    x = _scene((120, 0.3, 2.0, 0.1), (230, 2.5, 2.0, 0.1), (370, 4.7, 2.0, 0.1))
    vs = C.cascade(x, _empreintes)
    assert len(vs) == 3
    moments = sorted((np.flatnonzero(v["masque"])[0] / 100, v) for v in vs)
    for (debut, v), (d, l) in zip(moments, [(0.3, 2.0), (2.5, 2.0), (4.7, 2.0)]):
        assert _dans(v["masque"], d - 0.15, d + l + 0.15) >= 0.9, (d, C.segments(v["masque"]))
        assert v["masque"][int((d + 0.2) * 100):int((d + l - 0.2) * 100)].mean() >= 0.9


def test_la_plus_forte_sort_d_abord():
    x = _scene((230, 0.3, 2.0, 0.03), (120, 2.5, 2.0, 0.2))
    vs = C.cascade(x, _empreintes)
    assert len(vs) == 2
    assert _dans(vs[0]["masque"], 2.4, 4.6) >= 0.9 and vs[0]["rms_db"] > vs[1]["rms_db"] + 10


def test_un_murmure_trente_db_sous_les_autres_n_est_pas_une_voix():
    """Anti-objectif : Hakim qui répond à une voix fantôme (mesuré : un bout de bruit lu « Thank you. » par Whisper)."""
    x = _scene((120, 0.3, 2.0, 0.2), (230, 2.5, 2.0, 0.2), (370, 4.7, 2.0, 0.005))
    vs = C.cascade(x, _empreintes)
    assert len(vs) == 2 and all(_dans(v["masque"], 0.0, 4.6) > 0.8 for v in vs)


def test_la_meme_voix_qui_revient_reste_une_seule_voix():
    """Anti-objectif : la voix de papa coupée en plusieurs voix."""
    x = _scene((120, 0.3, 2.0, 0.1), (300, 2.5, 2.0, 0.1), (120, 4.7, 2.0, 0.1))
    vs = C.cascade(x, _empreintes)
    assert len(vs) == 2
    a = next(v for v in vs if _dans(v["masque"], 0.0, 2.5) > 0.3)
    assert C.segments(a["masque"])[0][0] < 0.5 and C.segments(a["masque"])[-1][1] > 6.4


def test_deux_voix_sorties_au_meme_timbre_n_en_font_qu_une():
    u = np.array([1.0, 0.0, 0.0])
    proche = np.array([0.8, 0.6, 0.0])                                   # cosinus 0,8 avec u
    autre = np.array([0.0, 0.0, 1.0])
    m = lambda a, b: np.r_[np.zeros(a, bool), np.ones(b - a, bool), np.zeros(300 - b, bool)]   # noqa: E731
    lin = np.ones(300)
    vs = C.fusionner([{"masque": m(0, 100), "c": u, "rms_db": 0.0}, {"masque": m(120, 160), "c": proche, "rms_db": 0.0},
                      {"masque": m(200, 280), "c": autre, "rms_db": 0.0}], lin)
    assert len(vs) == 2 and vs[0]["masque"].sum() == 140 and vs[1]["masque"].sum() == 80


def test_un_bruit_seul_ne_fait_aucune_voix_ni_aucun_travail():
    appels = []

    def emp(a):
        appels.append(len(a))
        return _empreintes(a)
    bruit = (0.05 * np.random.default_rng(1).standard_normal(8 * SR)).astype(np.float32)
    assert C.cascade(bruit, emp) == [] and appels == []
    assert C.cascade(np.zeros(8 * SR, np.float32), emp) == [] and appels == []


def test_au_plus_huit_voix():
    tours = [(f0, 0.2 + 1.9 * i, 1.7, 0.1) for i, f0 in enumerate([75, 95, 120, 150, 190, 240, 300, 380, 480, 600])]
    vs = C.cascade(_scene(*tours), _empreintes)
    assert 6 <= len(vs) <= 8
    assert len(C.cascade(_scene(*tours), _empreintes, max_voix=3)) == 3


def test_le_court_fichier_d_une_voix_ses_moments_bout_a_bout():
    x = np.ones(10 * SR, np.float32) * 0.1
    m = np.zeros(1000, bool)
    m[100:200] = True                                                    # 1,0 s → 2,0 s
    m[700:750] = True                                                    # 7,0 s → 7,5 s
    assert C.segments(m) == [[1.0, 2.0], [7.0, 7.5]]
    y = C.compacter(x, m)
    # 3 silences de 0,25 s + 1,2 s + 0,7 s (0,1 s de marge de chaque côté)
    assert abs(len(y) / SR - (3 * 0.25 + 1.2 + 0.7)) < 0.02
    assert np.abs(y[:int(0.2 * SR)]).max() == 0 and np.abs(y).max() > 0.09
    assert C.segments(np.r_[np.ones(50, bool), np.zeros(20, bool), np.ones(50, bool)]) == [[0.0, 1.2]]   # 0,2 s : un seul


def _musique(duree=4.0, sr=44100):
    t = np.arange(int(duree * sr)) / sr
    return sum(0.05 * np.sin(2 * np.pi * f * t) for f in (261.6, 329.6, 392.0, 130.8)).astype(np.float32)


def test_l_aiguillage_voix_musique_bruit():
    sr = 44100
    rien = np.zeros(4 * sr, np.float32)
    bruit = (0.02 * np.random.default_rng(2).standard_normal(4 * sr)).astype(np.float32)
    voix = _voix(150, 4.0, 0.1, sr)
    m = C.aiguiller(_musique(), rien, _musique(), sr)
    assert m["musique"] and not m["bruit"] and not m["voix"], m
    b = C.aiguiller(bruit, rien, bruit, sr)
    assert b["bruit"] and not b["musique"] and not b["voix"], b
    v = C.aiguiller(voix, voix, rien, sr)
    assert v["voix"] and not v["musique"] and not v["bruit"], v
    assert not any(C.aiguiller(rien, rien, rien, sr)[k] for k in ("voix", "musique", "bruit"))
    # une batterie seule (sans hauteur tenue) : de la musique, par sa piste
    coups = np.zeros(4 * sr, np.float32)
    for i in range(8):
        coups[i * sr // 2:i * sr // 2 + 2000] = 0.3 * np.random.default_rng(i).standard_normal(2000)
    assert C.aiguiller(coups, rien, coups, sr, {"drums": coups, "bass": rien})["musique"]


def test_les_instruments_dans_l_ordre_la_basse_d_abord():
    sr = 44100
    fort = _musique(2.0)
    p = {"guitar": fort, "drums": fort, "bass": fort, "piano": fort * 1e-3, "vocals": fort}
    assert C.instruments_presents(p, C._db(fort)) == ["bass", "drums", "guitar"]


def test_la_basse_ses_notes_et_ses_mots():
    sr = 44100
    t = np.arange(sr) / sr
    do, sol = (0.3 * np.sin(2 * np.pi * f * t) for f in (65.4, 98.0))
    basse = np.concatenate([do, sol, do, sol]).astype(np.float32)
    a = C.analyser_instrument("bass", basse, sr, separation._tonalite, separation.analyser_fond)
    assert set(a["notes"][:2]) == {"Do", "Sol"}, a
    assert a["bandes"]["graves"] == "forts"
    mots = C.instrument_en_mots("bass", a)
    assert mots.startswith("la basse : Do") or mots.startswith("la basse : Sol"), mots
    assert "graves forts" in mots
    json.dumps(a)                                                        # ce qui part au cockpit : du JSON


def _ecrire_empreintes(tmp_path):
    rng = np.random.default_rng(3)
    vec = lambda: (lambda v: v / np.linalg.norm(v))(rng.standard_normal(24))   # noqa: E731
    papa, karim, moi = vec(), vec(), vec()
    fa, fk, fm = tmp_path / "empreinte-vocale.json", tmp_path / "voix-connues.json", tmp_path / "empreinte-moi.json"
    fa.write_text(json.dumps({"vecteurs": [papa.tolist(), papa.tolist()], "moyenne": papa.tolist()}))
    fk.write_text(json.dumps([{"nom": "Karim", "moyenne": karim.tolist(), "n": 3}]))
    fm.write_text(json.dumps({"vecteurs": [moi.tolist()] * 3, "moyenne": moi.tolist()}))
    return (fa, fk, fm), (papa, karim, moi)


def test_un_nom_sur_une_voix_papa_une_voix_connue_sa_propre_voix(tmp_path):
    fichiers, (papa, karim, moi) = _ecrire_empreintes(tmp_path)
    avant = [f.read_bytes() for f in fichiers]
    refs = C.references(*fichiers)
    assert C.nommer(papa, refs)["nom"] == "papa"
    assert C.nommer(0.9 * karim + 0.1 * papa, refs)["nom"] == "Karim"
    assert C.nommer(moi, refs)["nom"] == "moi"
    inconnue = np.random.default_rng(9).standard_normal(24)
    assert C.nommer(inconnue, refs)["nom"] is None
    assert C.nommer(papa, [])["nom"] is None
    assert [f.read_bytes() for f in fichiers] == avant                   # lues, jamais écrites


class _Outils:
    """Un faux Demucs : les pistes vraies d'une scène fabriquée (16 kHz partout)."""
    taux = SR

    def __init__(self, voix, accompagnement=None, pistes6=None, coeurs=None, refs=()):
        self.v, self.a = voix, accompagnement if accompagnement is not None else np.zeros_like(voix)
        self.p6, self.coeurs, self.refs = pistes6, coeurs, list(refs)
        self.ecrits, self.appels = [], []

    def lire(self, f):
        return self.v + self.a, SR

    def pistes(self, x):
        return {"vocals": self.v, "drums": self.a * 0, "bass": self.a * 0, "other": self.a}

    def pistes6(self, x):
        self.appels.append("pistes6")
        return self.p6

    def vers16(self, x):
        return x

    def empreintes(self, a):
        self.appels.append("empreintes")
        return _empreintes(a)

    def references(self):
        return self.refs

    def ecrire(self, f, son, taux):
        self.ecrits.append(f)
        Path(f).write_bytes(b"")                                         # le nom seulement : aucun son gardé, même fabriqué


def test_sans_cascade_la_reponse_d_avant_rien_de_plus():
    """Le cockpit (separationRecue) lit {id, voix, fond, texte, ms} : une demande sans « cascade » rend exactement cela."""
    o = _Outils(_scene((120, 0.3, 2.0, 0.1), (230, 2.5, 2.0, 0.1)))
    r = separation.traiter({"id": 1, "fichier": "x.wav"}, o)
    assert set(r) == {"voix", "fond", "texte", "ms"}
    assert r["texte"] == separation.en_mots(r["voix"], r["fond"])
    assert o.ecrits == [] and o.appels == []


def test_la_cascade_dans_la_reponse_chaque_voix_son_numero_son_volume_son_fichier(tmp_path):
    x = _scene((120, 0.3, 2.0, 0.2), (230, 2.5, 2.0, 0.05))
    o = _Outils(x)
    r = separation.traiter({"id": 7, "fichier": "x.wav", "cascade": True, "voix_dossier": str(tmp_path)}, o)
    assert {"voix", "fond", "texte", "ms"} <= set(r)                     # compatible
    assert r["texte"] == separation.en_mots(r["voix"], r["fond"])        # son texte d'avant, inchangé
    assert r["aiguillage"]["voix"] and not r["aiguillage"]["musique"]
    vs = r["voix_separees"]
    assert [v["numero"] for v in vs] == [1, 2] and [v["timbre"] for v in vs] == ["voix 1", "voix 2"]
    assert vs[0]["volume_db"] > vs[1]["volume_db"] + 6                   # la plus forte d'abord
    assert vs[0]["segments"][0][1] <= 2.5 and vs[1]["segments"][0][0] >= 2.3
    for v in vs:
        f = Path(v["wav"])
        assert f.parent == tmp_path and f.exists() and f.name.startswith("jarvis-sep-")
        assert v["nom"] is None and v["moi"] is False and v["mots"] is None
    assert r["instruments"] == [] and "pistes6" not in o.appels
    assert r["texte_cascade"] == "2 voix : voix 1, voix 2"
    json.dumps(r)


def test_sans_dossier_aucun_fichier_de_voix():
    o = _Outils(_scene((120, 0.3, 2.0, 0.1)))
    r = separation.traiter({"id": 2, "fichier": "x.wav", "cascade": True, "voix_dossier": "pas/absolu"}, o)
    assert len(r["voix_separees"]) == 1 and "wav" not in r["voix_separees"][0] and o.ecrits == []


def test_un_bruit_ne_reveille_aucun_coeur():
    bruit = (0.01 * np.random.default_rng(4).standard_normal(8 * SR)).astype(np.float32)
    o = _Outils(np.zeros(8 * SR, np.float32), bruit)
    r = separation.traiter({"id": 3, "fichier": "x.wav", "cascade": True}, o)
    assert r["aiguillage"]["bruit"] and r["voix_separees"] == [] and r["instruments"] == []
    assert o.appels == [] and r["texte_cascade"] == ""


def test_papa_nomme_et_son_propre_echo_mis_de_cote(tmp_path):
    x = _scene((120, 0.3, 2.0, 0.1), (300, 2.5, 2.0, 0.1))
    e = _empreintes([x[int(0.5 * SR):int(2.0 * SR)], x[int(2.7 * SR):int(4.2 * SR)]])
    fa, fk, fm = tmp_path / "a.json", tmp_path / "k.json", tmp_path / "m.json"
    fa.write_text(json.dumps({"vecteurs": [e[0].tolist()] * 2, "moyenne": e[0].tolist()}))
    fm.write_text(json.dumps({"vecteurs": [e[1].tolist()] * 3, "moyenne": e[1].tolist()}))
    o = _Outils(x, refs=C.references(fa, fk, fm))
    vs = separation.traiter({"id": 4, "fichier": "x.wav", "cascade": True}, o)["voix_separees"]
    par = {v["timbre"]: v for v in vs}
    assert set(par) == {"papa", "sa voix"} and par["sa voix"]["moi"] and par["sa voix"]["nom"] is None
    assert separation.en_cascade.__doc__ and C.voix_en_mots(vs) == "1 voix : papa"


def test_voix_et_musique_un_instrument_par_coeur_la_basse_d_abord():
    sr = SR
    t = np.arange(4 * sr) / sr
    basse = (0.2 * np.sin(2 * np.pi * 65.4 * t)).astype(np.float32)
    guitare = (0.05 * np.sin(2 * np.pi * 329.6 * t) + 0.05 * np.sin(2 * np.pi * 392.0 * t)).astype(np.float32)
    acc = basse + guitare
    p6 = {"bass": basse, "guitar": guitare, "drums": np.zeros_like(t, dtype=np.float32), "piano": guitare * 1e-4,
          "other": np.zeros_like(basse), "vocals": np.zeros_like(basse)}
    v = np.pad(_scene((120, 0.3, 2.0, 0.1), (230, 2.5, 1.4, 0.1), fin=0.0), (0, 4 * sr))[:4 * sr]
    with ThreadPoolExecutor(max_workers=3) as coeurs:
        o = _Outils(v, acc, p6, coeurs)
        r = separation.traiter({"id": 5, "fichier": "x.wav", "cascade": True}, o)
    assert r["aiguillage"]["voix"] and r["aiguillage"]["musique"], r["aiguillage"]
    assert [i["instrument"] for i in r["instruments"]] == ["bass", "guitar"]
    assert r["instruments"][0]["texte"].startswith("la basse : Do")
    assert len(r["voix_separees"]) == 2
    assert r["texte_cascade"].startswith("2 voix : voix 1, voix 2 · la basse : Do")
    assert set(r["cascade_ms"]) >= {"premiere_ecoute", "voix", "musique"}
    json.dumps(r)


def test_sans_empreinte_la_reponse_d_avant_reste():
    """(l'onnxruntime vient du venv de jarvis : s'il manque, la cascade le dit, la réponse d'avant part quand même)"""
    o = _Outils(_scene((120, 0.3, 2.0, 0.1)))

    def casse(a):
        raise ImportError("No module named 'onnxruntime'")
    o.empreintes = casse
    r = separation.traiter({"id": 6, "fichier": "x.wav", "cascade": True}, o)
    assert {"voix", "fond", "texte", "ms"} <= set(r) and r["voix_separees"] == []
    assert "onnxruntime" in r["cascade_erreurs"]["voix"]


def test_les_notes_du_temps_nomment_chaque_note_avec_son_octave_a_sa_seconde():
    """(06/11, Ahmed : « il sait que c'est telle note, ou telle note et tel piano ») une basse La2 puis Fa2 ; un piano Do4 + Mi4"""
    import cascade as C2
    sr = 22050

    def note(midi, d):
        t = np.arange(int(d * sr)) / sr
        return (0.3 * np.sin(2 * np.pi * 440 * 2 ** ((midi - 69) / 12) * t)).astype(np.float32)
    basse = np.concatenate([note(45, 2.0), note(41, 2.0)])
    l = C2.notes_du_temps("bass", basse, sr)
    assert [n for _, n in l] == [["La2"], ["La2"], ["Fa2"], ["Fa2"]], l
    assert [t for t, _ in l] == [0.0, 1.0, 2.0, 3.0]
    piano = note(60, 1.0) + note(64, 1.0)
    assert sorted(C2.notes_du_temps("piano", piano, sr)[0][1]) == ["Do4", "Mi4"]
    assert C2.notes_du_temps("drums", basse, sr) == []
