"""Le studio multipiste (13/11, Ahmed : « un vrai studio complet avec différentes pistes et différents réglages, un peu comme Logic Pro
simplifié […] mix et mastering piste par piste »). Sur de vrais petits sons synthétiques (ffmpeg) : chaque mécanisme a son test, et
chaque test a son TÉMOIN (le même calcul, le mécanisme coupé, doit échouer à l'assertion)."""
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import studio  # noqa: E402
import studio_mesures as M  # noqa: E402
import studio_projet as SP  # noqa: E402

FFMPEG = studio.FFMPEG
pytestmark = pytest.mark.skipif(not Path(FFMPEG).exists(), reason="ffmpeg absent")
SR = 44100


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    """Jamais le vrai téléphone, le vrai studio ni les vraies tâches."""
    monkeypatch.setattr(studio, "TELEPHONE", tmp_path / "telephone" / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "DOCUMENTS", tmp_path / "telephone" / "Hakim")
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", tmp_path / "telephone-ecritures.jsonl")
    monkeypatch.setattr(studio, "STUDIO", tmp_path / "chansons" / "studio")
    monkeypatch.setattr(studio, "CHANSONS", tmp_path / "chansons")
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)


def _ecrire(f, x):
    return M.ecrire_wav(f, x, SR, 32)


def _sinus(f, duree, amp=0.3, debut=0.0, fin=None, canaux=2):
    t = np.arange(int(duree * SR)) / SR
    x = amp * np.sin(2 * np.pi * f * t)
    x[t < debut] = 0
    if fin is not None:
        x[t >= fin] = 0
    return np.repeat(x[:, None], canaux, axis=1)


def _bruit(duree, amp=0.1, graine=1):
    r = np.random.default_rng(graine)
    return amp * r.standard_normal((int(duree * SR), 2))


def _niveau(x, a, b, canal=None):
    s = x[int(a * SR): int(b * SR)]
    s = s[:, canal] if canal is not None else s
    return M.db(s)


def _bande(x, f, a, b):
    """Le niveau (dB) autour d'une fréquence, entre a et b secondes (FFT de la tranche)."""
    s = x[int(a * SR): int(b * SR)].mean(axis=1)
    w = np.hanning(len(s))
    S = np.abs(np.fft.rfft(s * w)) * 2 / w.sum()                  # l'amplitude d'un sinus, quelle que soit la longueur de la tranche
    fr = np.fft.rfftfreq(len(s), 1 / SR)
    sel = (fr > f * 0.97) & (fr < f * 1.03)
    return 20 * np.log10(S[sel].max() + 1e-12)


@pytest.fixture
def projet(tmp_path):
    """Un projet : une « voix » (sinus 660 Hz de 1 à 5 s) et une « instru » (sinus 110 Hz + bruit, 8 s)."""
    p = SP.nouveau("Essai", tempo=120, tonalite="A minor")
    d = SP.dossier(p["id"])
    _ecrire(d / "pistes" / "voix.wav", _sinus(660, 8, 0.3, 1.0, 5.0))
    _ecrire(d / "pistes" / "instru.wav", _sinus(110, 8, 0.3) + _bruit(8, 0.02))

    def remplir(q):
        SP.ajouter_piste(q, "pistes/voix.wav", "voix_hakim", "Voix de Hakim", duree_s=8)
        SP.ajouter_piste(q, "pistes/instru.wav", "instru", "Instru", duree_s=8)
        for t in q["pistes"]:                               # réglages neutres : on teste un mécanisme à la fois
            t["eq"]["coupe_bas_hz"] = 0
            t["comp"]["actif"] = False
            t["reverb"] = 0
        q["duree_s"] = 8.0
    SP.modifier(p["id"], remplir)
    return p["id"]


def _rendre(pid, tmp_path, version="complet", nom="bus.wav", **kw):
    p = SP.lire(pid)
    f = tmp_path / nom
    SP.rendre_bus(p, SP.dossier(pid), f, version, **kw)
    return M.lire(f)[0]


# ------------------------------------------------------------------------------------------------ le projet et ses réglages
def test_projet_sur_le_disque_et_reglages_bornes(projet):
    p = SP.lire(projet)
    assert [t["id"] for t in p["pistes"]] == ["t1", "t2"] and p["rev"] == 2
    q = SP.modifier(projet, lambda x: SP.regler_piste(SP.piste(x, "voix de hakim"), {"volume_db": 99, "pan": -5, "eq": {"medium_db": -40},
                                                                                       "reverb": 3, "autotune": "léger", "inconnu": 1}))
    t = q["pistes"][0]
    assert t["volume_db"] == 12 and t["pan"] == -1 and t["eq"]["medium_db"] == -12 and t["reverb"] == 1 and t["autotune"] == "leger"
    assert "inconnu" not in t and q["rev"] == 3
    with pytest.raises(SP.Refus, match="a changé"):                 # une page restée sur une version d'avant
        SP.modifier(projet, lambda x: None, rev=2)
    assert SP.trouver("essai") == projet and SP.lister()[0]["pistes"] == 2
    with pytest.raises(SP.Refus):
        SP.dossier("../../etc")


def test_lire_reglages_en_mots():
    r = SP.lire_reglages("volume=-3, pan=0.2, muet=oui, medium=-2, medium_hz=300, ratio=4, réverb=0.2, autotune=léger, sidechain=t3:2")
    assert r["volume_db"] == -3 and r["pan"] == 0.2 and r["muet"] is True and r["eq"] == {"medium_db": -2, "medium_hz": 300}
    assert r["comp"] == {"ratio": 4} and r["reverb"] == 0.2 and r["autotune"] == "leger" and r["sidechain"] == {"cle": "t3", "db": "2"}
    assert SP.lire_reglages('{"volume_db": 1}') == {"volume_db": 1}
    with pytest.raises(SP.Refus):
        SP.lire_reglages("n'importe quoi")


def test_zones_en_secondes_et_en_mesures(projet):
    p = SP.lire(projet)
    p["premier_temps_s"] = 0.5                                       # 120 BPM : une mesure = 2 s
    z = SP.lire_zones(p, "couplet de papa : 1:17-1:41 ; refrain Hakim : m9-m13 ; outro : 2:10.5-2:20")
    assert [(x["nom"], x["qui"], x["debut_s"], x["fin_s"]) for x in z] == [
        ("couplet de papa", "papa", 77.0, 101.0), ("refrain Hakim", "hakim", 16.5, 24.5), ("outro", "instru", 130.5, 140.0)]
    with pytest.raises(SP.Refus):
        SP.lire_zones(p, "couplet : 1:40-1:20")
    p["tempo"] = 0
    with pytest.raises(SP.Refus, match="tempo"):
        SP.lire_zones(p, "m1-m2")


# ------------------------------------------------------------------------------------------------ le rendu, mécanisme par mécanisme
def test_rendu_les_deux_pistes_et_le_muet(projet, tmp_path):
    x = _rendre(projet, tmp_path)
    assert _bande(x, 660, 2, 4) > _bande(x, 660, 6, 7.5) + 40       # la voix sonne de 1 à 5 s seulement
    assert _bande(x, 110, 2, 4) > -13                               # l'instru sonne (un sinus de 0,3 : −10,5 dB)
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"muet": True}))
    y = _rendre(projet, tmp_path, nom="b2.wav")
    assert _bande(y, 660, 2, 4) < _bande(x, 660, 2, 4) - 40          # témoin : la piste muette ne sonne plus
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"muet": False, "solo": True}))
    z = _rendre(projet, tmp_path, nom="b3.wav")
    assert _bande(z, 110, 2, 4) < _bande(x, 110, 2, 4) - 40 and _bande(z, 660, 2, 4) > _bande(x, 660, 2, 4) - 1   # solo


def test_volume_et_panoramique(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "instru"), {"muet": True}))
    a = _rendre(projet, tmp_path, nom="a.wav")
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"volume_db": -6, "pan": -1}))
    b = _rendre(projet, tmp_path, nom="b.wav")
    assert abs((_niveau(b, 2, 4, 0) - _niveau(a, 2, 4, 0)) - (-6 + 10 * math.log10(2))) < 0.3   # −6 dB, et tout à gauche (+3 dB)
    assert _niveau(b, 2, 4, 1) < -80                                # témoin : rien à droite


def test_regions_placees_sur_la_ligne_du_temps(projet, tmp_path):
    """La voix (de 1 à 5 s dans son fichier), découpée de 2 à 3 s de son fichier et posée à 6 s : elle sonne de 6 à 7 s seulement."""
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"regions": [{"debut_s": 6, "source_debut_s": 2, "duree_s": 1}]}))
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"muet": True}))
    x = _rendre(projet, tmp_path)
    assert _bande(x, 660, 6.1, 6.9) > -20 and _bande(x, 660, 2, 4) < -60 and _bande(x, 660, 7.1, 7.9) < -60


def test_automation_de_volume(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"muet": True}))
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"automation": [{"t": 2.5, "db": 0}, {"t": 3, "db": -20}]}))
    x = _rendre(projet, tmp_path)
    assert abs((_niveau(x, 3.5, 4.5) - _niveau(x, 1.5, 2.4)) + 20) < 0.5      # −20 dB après la rampe (témoin : 0 sans automation)


def test_zones_de_papa_les_voix_se_taisent(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_zones(q, [{"nom": "couplet de papa", "debut_s": 2, "fin_s": 4, "qui": "papa"}]))
    complet = _rendre(projet, tmp_path, "complet", "c.wav")
    papa = _rendre(projet, tmp_path, "papa", "p.wav")
    assert _bande(complet, 660, 2.2, 3.8) > -20                    # témoin : la voix chante dans la zone du son entier
    assert _bande(papa, 660, 2.2, 3.8) < _bande(complet, 660, 2.2, 3.8) - 50   # la version pour papa : sa zone en instru seule
    assert abs(_bande(papa, 660, 4.3, 4.8) - _bande(complet, 660, 4.3, 4.8)) < 0.5   # hors de la zone : la voix intacte
    assert abs(_bande(papa, 110, 2.2, 3.8) - _bande(complet, 110, 2.2, 3.8)) < 0.5   # l'instru intacte dans la zone


def test_egaliseur_et_coupe_bas(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"muet": True}))
    a = _rendre(projet, tmp_path, nom="a.wav")
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"eq": {"coupe_bas_hz": 300}}))
    b = _rendre(projet, tmp_path, nom="b.wav")
    assert _bande(b, 110, 2, 4) < _bande(a, 110, 2, 4) - 12        # 110 Hz coupé (témoin : a)
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"eq": {"coupe_bas_hz": 0, "grave_db": 6, "grave_hz": 110}}))
    c = _rendre(projet, tmp_path, nom="c.wav")
    assert 3 < _bande(c, 110, 2, 4) - _bande(a, 110, 2, 4) < 7


def test_envoi_de_reverberation(projet, tmp_path):
    """La queue après la fin de la voix (5 s) : présente avec la réverb, absente sans."""
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"muet": True}))
    sec = _rendre(projet, tmp_path, nom="sec.wav")
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t1"), {"reverb": 0.5}))
    rv = _rendre(projet, tmp_path, nom="rv.wav")
    assert _niveau(sec, 5.1, 5.6) < -90 and _niveau(rv, 5.1, 5.6) > -60


def test_delai_cale_sur_le_tempo(projet, tmp_path):
    """Une impulsion à 1 s ; délai à la croche pointée (120 BPM : 375 ms) : un écho vers 1,375 s."""
    p = SP.lire(projet)
    d = SP.dossier(projet)
    x = np.zeros((int(3 * SR), 2))
    x[SR: SR + 200] = 0.8
    _ecrire(d / "pistes" / "clic.wav", x)

    def r(q):
        q["pistes"] = []
        t = SP.ajouter_piste(q, "pistes/clic.wav", "voix", "Clic", duree_s=3)
        t["eq"]["coupe_bas_hz"] = 0
        t["comp"]["actif"] = False
        t["reverb"] = 0
        t["delai"] = 0.8
        q["duree_s"] = 3
    SP.modifier(projet, r)
    y = _rendre(projet, tmp_path)
    e = np.abs(y.mean(axis=1))
    i = int(1.2 * SR) + int(np.argmax(e[int(1.2 * SR): int(1.6 * SR)]))
    assert abs(i / SR - 1.375) < 0.01 and e[i] > 0.05
    assert p["tempo"] == 120


def test_sidechain_creuse_l_instru_sous_la_voix(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"sidechain": {"cle": "t1", "db": 6}}))
    x = _rendre(projet, tmp_path)
    sous = _bande(x, 110, 2, 4)                                   # la voix chante : l'instru creusée
    libre = _bande(x, 110, 6, 7.5)                                # la voix se tait : l'instru pleine
    SP.modifier(projet, lambda q: SP.regler_piste(SP.piste(q, "t2"), {"sidechain": {"cle": "", "db": 0}}))
    y = _rendre(projet, tmp_path, nom="t.wav")
    assert libre - sous > 2.5                                     # creusée de quelques dB
    assert abs(_bande(y, 110, 6, 7.5) - _bande(y, 110, 2, 4)) < 0.5   # témoin : sans sidechain, rien ne bouge


def test_master_lufs_et_crete_vraie_sur_wav_et_mp3(projet, tmp_path):
    """Un son très crêté poussé à −10 LUFS : le master tient −10 ± 0,3 LUFS et la crête vraie ≤ −1 dBTP (WAV et MP3)."""
    d = SP.dossier(projet)
    x = _bruit(8, 0.05, 3)
    x[::4410] = 0.95                                              # des crêtes isolées (le pire pour un limiteur)
    _ecrire(d / "pistes" / "instru.wav", x)
    SP.modifier(projet, lambda q: (SP.regler_piste(SP.piste(q, "t1"), {"muet": True}), q["master"].update(lufs=-10)))
    bus = tmp_path / "bus.wav"
    p = SP.lire(projet)
    SP.rendre_bus(p, d, bus)
    params = SP.chaine_master_params(bus, p)
    assert params["lufs"] == -10
    r = SP.masteriser(bus, tmp_path / "m.wav", params, tmp_path / "m.mp3", "Essai")
    w, m3 = M.ebur128(tmp_path / "m.wav"), M.ebur128(tmp_path / "m.mp3")
    assert abs(w["lufs"] + 10) <= 0.35 and w["crete_dbtp"] <= -1.0 and m3["crete_dbtp"] <= -1.0, (w, m3, r["essais"])
    brut = M.ebur128(bus)
    assert brut["crete_dbtp"] - brut["lufs"] > 12                 # témoin : sans limiteur, à −10 LUFS les crêtes passeraient 0 dBTP


def test_rendre_projet_complet_zones_instru_et_telephone(projet, tmp_path):
    SP.modifier(projet, lambda q: SP.regler_zones(q, [{"nom": "papa", "debut_s": 2, "fin_s": 4, "qui": "papa"}]))
    etapes = []
    r = SP.rendre_projet(projet, "tout", mix_auto=True, envoyer=True, pistes_separees=True, progres=lambda n, s: etapes.append(n))
    f = r["fichiers"]
    for k in ("complet", "zones_papa", "instru"):
        assert Path(f[k]["wav"]).is_file() and Path(f[k]["mp3"]).is_file(), k
    assert len(f["pistes"]) == 2
    m = r["mesures"]["master"]
    assert abs(m["lufs"] + 14) <= 0.35 and m["crete_dbtp"] <= -1.0 and r["mesures"]["mp3"]["crete_dbtp"] <= -1.0
    tel = list(studio.TELEPHONE.glob("*.mp3"))
    # (14/11) chaque rendu est une version : « Titre v1 », jamais écrasé par le suivant
    assert {p.name for p in tel} == {"Essai v1.mp3", "Essai v1 (zones de papa).mp3", "Essai v1 (instru).mp3"}
    assert len(list((studio.TELEPHONE / "Essai v1 (pistes)").glob("*.mp3"))) == 2
    q = SP.lire(projet)
    assert q["rendus"][-1]["nom"] == r["nom"] and r["avis"] and etapes[0] == 1
    v = q["pistes"][0]                                            # le mix piste par piste a réglé la voix
    assert v["comp"]["actif"] and v["eq"]["coupe_bas_hz"] == 90 and v["reverb"] > 0
    assert q["pistes"][1]["sidechain"]["cle"] == "t1"
    e = r["mix_auto"]["t1"]["equilibre"][-1]
    assert abs(e["ecart_lu"] - e["vise_lu"]) <= 0.6, r["mix_auto"]
    assert not list(SP.dossier(projet).glob(".rendu-*"))          # le dossier de travail effacé


def test_commande_du_cockpit(projet, tmp_path):
    r = SP.commande({"action": "regler", "id": projet, "rev": SP.lire(projet)["rev"], "piste": "t1", "reglages": {"volume_db": -2}, "par": "papa"})
    assert r["ok"] and r["projet"]["pistes"][0]["volume_db"] == -2 and "papa règle t1" in r["projet"]["journal"][-1]["quoi"]
    assert not SP.commande({"action": "regler", "id": projet, "rev": 1, "piste": "t1", "reglages": {}})["ok"]   # version d'avant
    assert SP.commande({"action": "zones", "id": projet, "zones": "couplet de papa : 0:01-0:03"})["projet"]["zones"][0]["qui"] == "papa"
    prise = studio.STUDIO / "prises" / "P-1.wav"
    prise.parent.mkdir(parents=True, exist_ok=True)
    _ecrire(prise, _sinus(330, 3, 0.2))
    r = SP.commande({"action": "importer", "id": projet, "fichier": str(prise), "debut_s": 2.0, "latence_ms": 120})
    t = r["projet"]["pistes"][-1]
    assert r["ok"] and t["role"] == "voix_papa" and t["regions"][0] == {"debut_s": 2.0, "source_debut_s": 0.12, "duree_s": None, "gain_db": 0.0}
    assert not SP.commande({"action": "importer", "id": projet, "fichier": "/etc/hosts"})["ok"]
    vus = []
    j = SP.commande({"action": "rendre", "id": projet, "params": {"projet": projet, "mix_auto": True, "rm": "-rf"}}, demarrer=vus.append)
    assert j["ok"] and "rm" not in j["travail"]["params"] and len(vus) == 1


def test_la_file_cree_un_projet_separe(tmp_path, monkeypatch):
    """La file : un projet depuis une chanson, séparé (un faux Demucs : il écrit des pistes connues) ; la somme de ses pistes refait
    l'instru exacte (mélange − voix), et « garder » rend muettes les pistes non gardées."""
    src = tmp_path / "chanson.wav"
    voix, bat, bas, autre = _sinus(660, 4, 0.2), _sinus(80, 4, 0.2), _sinus(55, 4, 0.2), _sinus(440, 4, 0.1)
    _ecrire(src, voix + bat + bas + autre)
    faux = tmp_path / "faux-demucs.py"
    faux.write_text(f"""import json, sys, numpy as np
sys.path.insert(0, {str(Path(SP.__file__).parent)!r})
import studio_mesures as M
from pathlib import Path
d = Path(sys.argv[4]); d.mkdir(parents=True, exist_ok=True)
x, _ = M.lire(sys.argv[3])
t = np.arange(len(x)) / 44100
s = lambda f, a: np.repeat((a * np.sin(2 * np.pi * f * t))[:, None], 2, axis=1)
p = {{"vocals": s(660, .2), "drums": s(80, .2), "bass": s(55, .2), "other": s(440, .05)}}
out = {{k: str(M.ecrire_wav(d / (k + ".flac"), v, 44100, 16)) for k, v in p.items()}}
M.ecrire_wav(d / "instru.flac", x - p["vocals"], 44100, 16)
print(json.dumps({{"pistes": out, "instru": str(d / "instru.flac")}}))
""")
    lanceur = tmp_path / "py"
    lanceur.write_text(f"#!/bin/sh\nshift; shift; shift; exec {sys.executable} {faux} \"$@\"\n")
    lanceur.chmod(0o755)
    monkeypatch.setattr(studio, "PYTHON_SEPARATION", lanceur)
    vus = []
    j = studio.lancer("projet", {"source": str(src), "titre": "Moujahid", "separer": "4", "garder": ["batterie", "basse"]}, demarrer=vus.append)
    assert len(vus) == 1 and j["etapes"] == 3
    assert studio.travailleur(studio.STUDIO / "travaux") == 1
    fin = json.loads((studio.STUDIO / "travaux" / f"{j['id']}.json").read_text())
    assert fin["etat"] == "fini", fin.get("erreur")
    p = SP.lire(fin["resultat"]["projet"])
    roles = {t["role"]: t for t in p["pistes"]}
    assert set(roles) == {"batterie", "basse", "melodie", "voix_hakim"}
    assert not roles["batterie"]["muet"] and not roles["basse"]["muet"] and roles["melodie"]["muet"]   # « garde la batterie et la basse »
    d = SP.dossier(p["id"])
    somme = sum(M.lire(d / roles[r]["fichier"])[0] for r in ("batterie", "basse", "melodie"))
    exacte = M.lire(src)[0] - M.lire(d / roles["voix_hakim"]["fichier"])[0]
    assert M.db(somme - exacte) < M.db(exacte) - 60                # la mélodie a pris le reste : rien n'est perdu (16 bits près)
    assert abs(_bande(M.lire(d / roles["melodie"]["fichier"])[0], 440, 1, 3) - _bande(autre, 440, 1, 3)) < 0.5   # « other » + le reste


# ------------------------------------------------------------------------------------------------ les mesures
def test_mesure_de_separation_contre_une_verite():
    r = np.random.default_rng(0)
    i, v = r.standard_normal((SR * 4, 2)) * 0.1, np.repeat(_sinus(330, 4, 0.1)[:, :1], 2, axis=1)
    parfait = M.separation_contre_verite(i, i, v)
    fuite = M.separation_contre_verite(i + 0.1 * v, i, v)
    abime = M.separation_contre_verite(0.9 * i, i, v)
    assert parfait["sdr_db"] > 100 and parfait["fuite_voix_db"] < -100
    assert abs(fuite["fuite_voix_db"] + 20) < 0.5 and fuite["artefacts_db"] < -60       # 10 % de la voix restée : −20 dB
    assert abs(abime["artefacts_db"] + 20) < 0.5 and abime["fuite_voix_db"] < -25        # l'instru à 90 % : artefacts −20 dB


def test_tempo_calage_et_decalage():
    x = np.zeros((SR * 12, 2))
    for k in range(24):                                          # 120 BPM, premier temps à 0,25 s
        a = int((0.25 + k * 0.5) * SR)
        x[a: a + 300] = 0.8 * np.hanning(600)[300:, None]
    t = M.tempo_et_phase(x)
    assert abs(t["bpm"] - 120) < 0.6 and abs(t["premier_temps_s"] - 0.25) < 0.012, t
    y = np.roll(x, int(0.030 * SR), axis=0)                       # une voix 30 ms en retard sur les temps
    c = M.calage_sur_grille(y, SR, 120, 0.25)
    assert abs(c["mediane_ms"] - 30) <= 6 and c["attaques"] >= 20
    assert abs(M.calage_sur_grille(x, SR, 120, 0.25)["mediane_ms"]) <= 6       # témoin : à l'heure
    ms, n = M.decalage_entre(x, np.roll(x, int(0.080 * SR), axis=0))
    assert abs(ms - 80) <= 5 and n > 0.3


def test_porte_de_la_voix_garde_l_instru_ou_personne_ne_chante():
    import studio_separation as S
    v = np.vstack([_sinus(330, 3, 0.3), _sinus(880, 3, 0.003)])  # chantée 3 s, puis un ney à −40 dB pris pour de la voix
    g = S.porte_voix(v + 0.0, v, seuil_db=-30)
    assert M.db(g[: int(2.5 * SR)]) > M.db(v[: int(2.5 * SR)]) - 0.5
    assert M.db(g[int(4 * SR):]) < M.db(v[int(4 * SR):]) - 40     # le ney reste dans l'instru (témoin : sans porte, 0 dB d'écart)


def test_bilan_et_reference_du_genre(tmp_path):
    f = tmp_path / "b.wav"
    _ecrire(f, _bruit(5, 0.1))
    b = M.bilan(f)
    assert b["lufs"] is not None and len(b["bandes_db"]) == 10 and -1.01 <= b["correlation"] <= 1.0
    ref = M.references()
    assert "trap" in ref.get("genres", {}) and len(ref["genres"]["trap"]["bandes"]) == 10
    eq = M.correction_eq([v + (6 if i == 3 else 0) for i, v in enumerate(ref["genres"]["trap"]["bandes"])], "trap")
    assert eq == [{"hz": 250, "db": -3.0}]                       # +6 dB de bas-médium : −3 dB (la moitié, plafonnée)


# ------------------------------------------------------------------------------------------------ poser sa voix (ACE-Step), la reprise
def _clics(duree, bpm, t0, decale=0.0, f=None):
    x = np.zeros((int(duree * SR), 2))
    k, p = 0, 60 / bpm
    while t0 + k * p + decale < duree - 0.1:
        a = int((t0 + k * p + decale) * SR)
        n = 600
        env = np.hanning(2 * n)[n:]
        sig = env if f is None else env * np.sin(2 * np.pi * f * np.arange(n) / SR)
        x[a: a + n] += 0.6 * sig[:, None]
        k += 1
    return x


def test_poser_sa_voix_calee_sur_l_instru_du_projet(tmp_path, monkeypatch):
    """ACE-Step rejoue l'instru 60 ms en retard et chante dessus (sa voix aussi 60 ms en retard) : sa voix entre dans le projet recalée
    (décalage mesuré +60 ms, retiré), et son calage sur la grille passe de ~60 ms à presque rien. Témoin : le calage d'avant."""
    import chant
    p = SP.nouveau("Sur l'instru de papa", tempo=120, tonalite="A minor")
    d = SP.dossier(p["id"])
    base = _clics(12, 120, 0.25)
    _ecrire(d / "pistes" / "instru.wav", base)
    SP.modifier(p["id"], lambda q: (SP.ajouter_piste(q, "pistes/instru.wav", "instru", "Instru", duree_s=12), q.update(premier_temps_s=0.25, duree_s=12),
                                    SP.regler_zones(q, [{"nom": "refrain Hakim", "debut_s": 4, "fin_s": 8, "qui": "hakim"}])))
    rejouee = _clics(12, 120, 0.25, 0.060)
    voix = _clics(12, 240, 0.25, 0.060, f=880)                       # sa voix : sur chaque croche, 60 ms en retard comme l'instru rejouée
    faux = tmp_path / "faux-sep.py"
    np.save(tmp_path / "v.npy", voix)
    np.save(tmp_path / "i.npy", rejouee)
    faux.write_text(f"""import json, sys, numpy as np
sys.path.insert(0, {str(Path(SP.__file__).parent)!r})
import studio_mesures as M
from pathlib import Path
d = Path(sys.argv[3]); d.mkdir(parents=True, exist_ok=True)
v, i = np.load({str(tmp_path / 'v.npy')!r}), np.load({str(tmp_path / 'i.npy')!r})
M.ecrire_wav(d / "vocals.wav", v, 44100, 32); M.ecrire_wav(d / "instru.wav", i, 44100, 32)
print(json.dumps({{"pistes": {{"vocals": str(d / "vocals.wav")}}, "instru": str(d / "instru.wav")}}))
""")
    lanceur = tmp_path / "py"
    lanceur.write_text(f"#!/bin/sh\nshift; shift; shift; shift; exec {sys.executable} {faux} \"$@\"\n")
    lanceur.chmod(0o755)
    monkeypatch.setattr(chant, "PYTHON_SEPARATION", lanceur)
    monkeypatch.setattr(studio, "mixer", lambda v, b, *a, **k: {"wav": str(v)})
    c = {"projet": p["id"], "base": str(d / "pistes" / "instru.wav"), "titre": "Refrain HK", "nom": "x", "zones_seulement": True, "autotune_niveau": "leger"}
    chant.poser_dans_projet(tmp_path / "chant.wav", c, tmp_path)
    q = SP.lire(p["id"])
    t = q["pistes"][-1]
    assert t["role"] == "voix_hakim" and t["regions"] == [{"debut_s": 4, "source_debut_s": 4, "duree_s": 4.0, "gain_db": 0.0}]   # ses zones seulement
    cal = q["voix_posees"][-1]["calage"]
    assert abs(cal["decalage_instru_ms"] - 60) <= 5, cal
    assert abs(cal["grille_avant"]["mediane_ms"] - 60) <= 6 and cal["grille_apres"]["mediane_abs_ms"] <= 6, cal
    v, _ = M.lire(d / t["fichier"])
    assert M.calage_sur_grille(v, SR, 120, 0.25)["mediane_abs_ms"] <= 6


def test_la_reprise_rejoue_l_instru_sans_voix(tmp_path, monkeypatch):
    import chant
    src = tmp_path / "chanson.mp3"
    subprocess.run([FFMPEG, "-hide_banner", "-loglevel", "error", "-y", "-f", "lavfi", "-i", "sine=f=220:d=3", str(src)], check=True)
    monkeypatch.setattr(chant, "racines_audio", lambda: [tmp_path])
    c = chant.preparer("[instrumental]", "oriental dark trap, rhythmic male rap vocals", 100, "Moujahid (instru rejouée)", bpm=140,
                       tonalite="A minor", reprise=str(src), fidelite=0.8)
    p = chant.parametres(c)
    assert p["task_type"] == "cover" and p["src_audio"] == str(src.resolve()) and p["instrumental"] is True and p["lyrics"] == "[Instrumental]"
    assert p["audio_cover_strength"] == 0.8 and p["keyscale"] == "A minor" and p["bpm"] == 140
    assert "vocal" not in c["description"].replace("no vocals", "")            # aucune étiquette de voix ne reste
    with pytest.raises(chant.Refus, match="instrumental"):
        chant.lancer("[verse] salut", "trap", 30, reprise=str(src), demarrer=lambda *a: 1, dossier=tmp_path / "t", chansons=tmp_path / "c")
    assert "task_type" not in chant.parametres(chant.preparer("[instrumental]", "trap", 30))   # témoin : sans reprise, une instru neuve


def test_les_outils_de_hakim(projet, tmp_path, monkeypatch):
    """Ses outils : réservés à Hakim ; voir le projet, régler une piste en mots, poser ses zones en mesures, lancer le rendu (en file)."""
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = lambda n: mcp_server.mcp._tool_manager.get_tool(n).fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert outil("studio_projet")() == "Seul Hakim travaille dans le studio."
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    assert "« Essai »" in outil("studio_projet")("liste")
    v = outil("studio_projet")("voir", "essai")
    assert "t1 Voix de Hakim" in v and "120" in v
    r = outil("studio_piste")("essai", "voix de hakim", "regler", "volume=-4, medium=-3, medium_hz=300, reverb=0.25, autotune=léger")
    assert r.startswith("Réglée.") and "vol -4.0 dB" in r and "autotune léger" in r and "réverb 0.25" in r
    assert outil("studio_piste")("essai", "t9", "regler", "volume=1").startswith("Refusé : piste inconnue")
    p = SP.lire(projet)
    assert p["pistes"][0]["eq"]["medium_hz"] == 300 and p["pistes"][0]["autotune"] == "leger"
    z = outil("studio_zones")("essai", "couplet de papa : m2-m3 ; refrain Hakim : 0:01-0:02")
    assert "couplet de papa (papa) 2.00-4.00 s" in z and "refrain Hakim (hakim) 1.00-2.00 s" in z    # 120 BPM : une mesure = 2 s
    assert "Voix de Hakim chante" in outil("studio_zones")("essai")
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = outil("studio_rendre")("essai", pistes_separees=True)
    assert r.startswith("Rendu lancé") and len(vus) == 1
    j = json.loads(next((studio.STUDIO / "travaux").glob("J-*.json")).read_text())
    assert j["type"] == "rendre" and j["params"]["projet"] == projet and j["params"]["pistes_separees"] is True


def test_studio_avis_dit_le_rendu_fini_et_ou_le_trouver(projet, tmp_path, monkeypatch):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    studio.lancer("rendre", {"projet": projet, "mix_auto": False, "envoyer": True})
    assert studio.travailleur(studio.STUDIO / "travaux") == 1
    a = mcp_server.mcp._tool_manager.get_tool("studio_avis").fn()
    assert "Rendu prêt" in a and "master -14" in a and "dBTP" in a
    assert "complet : " in a and "Essai v1.mp3" in a and "instru : " in a and "Essai v1 (instru).mp3" in a   # où les trouver, pour fichier_joindre


def test_egaliseur_correctif_des_voix():
    """La voix de Hakim dans Moujahid 3.2 (bandes mesurées le 13/11) : rien à creuser ni à ajouter. Une voix boueuse (+6 dB à 250 Hz), une
    voix sourde (présence −18 dB) et une voix sifflante : chacune son geste, et seulement le sien (témoin : la voix de Hakim)."""
    hakim = [-31.6, -28.4, -5.2, 14.5, 19.3, 14.7, 7.0, 5.2, 4.9, -0.4]
    c = SP.eq_correctif_voix(hakim)
    assert (c["medium_db"], c["aigu_db"]) == (0.0, 0.0)
    boueuse = list(hakim); boueuse[3] = 23.0
    assert SP.eq_correctif_voix(boueuse)["medium_db"] < -2 and SP.eq_correctif_voix(boueuse)["aigu_db"] == 0.0
    sourde = list(hakim); sourde[6], sourde[7] = -2.0, -4.0
    assert SP.eq_correctif_voix(sourde)["aigu_db"] > 1.5 and SP.eq_correctif_voix(sourde)["medium_db"] == 0.0
    sifflante = list(hakim); sifflante[8] = 14.0
    assert SP.eq_correctif_voix(sifflante)["deesser"] > 0.5 and c["deesser"] < SP.eq_correctif_voix(sifflante)["deesser"]
