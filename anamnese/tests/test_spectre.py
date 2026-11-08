"""(05/11, Ahmed : « comme dans le cerveau humain, ce qui transforme signal reçu en signal spectral » ; « sa pensée interne aussi, reliée à tout le reste »)"""
import json

import numpy as np

from jarvis import spectre as sp


def _rouge(n, r=0.9, graine=0):
    a = np.random.default_rng(graine)
    y = np.zeros(n)
    for i in range(1, n):
        y[i] = r * y[i - 1] + a.normal()
    return y


def test_un_rythme_enfoui_ressort_a_sa_periode():
    t = np.arange(1200.0)
    y = _rouge(1200) + 6 * np.sin(2 * np.pi * t / 20)
    fc, S, p, ref = sp.cochlee(y, 1.0)
    r = sp.rythmes(fc, p, ref)
    assert r[0]["net"] and abs(r[0]["periode_s"] - 20) / 20 < 0.15
    k = int(np.argmin(np.abs(1 / fc - 20)))
    assert S[k].mean() > S.mean() * 1.5, "le spectrogramme le montre aussi"


def test_un_bruit_rouge_seul_n_est_presque_jamais_pris_pour_un_rythme():
    faux = 0
    for g in range(40):
        fc, _, p, ref = sp.cochlee(_rouge(600, graine=g), 1.0)
        faux += any(x["net"] for x in sp.rythmes(fc, p, ref))
    assert faux <= 6, f"{faux} faux rythmes sur 40"


def test_des_evenements_reguliers_donnent_leur_rythme():
    y = sp.impulsions(np.arange(0, 300, 1.2), [1] * 250, 0.05, 0, 300)
    fc, _, p, ref = sp.cochlee(y, 0.05, evenements=True)
    assert any(x["net"] and abs(x["periode_s"] - 1.2) / 1.2 < 0.15 for x in sp.rythmes(fc, p, ref, n=5))


def test_des_evenements_au_hasard_n_ont_pas_de_rythme():
    faux = 0
    for g in range(40):
        a = np.random.default_rng(g)
        y = sp.impulsions(a.uniform(0, 600, 60), [1] * 60, 1.0, 0, 600)
        fc, _, p, ref = sp.cochlee(y, 1.0, evenements=True)
        faux += any(x["net"] for x in sp.rythmes(fc, p, ref))
    assert faux <= 6, f"{faux} faux rythmes sur 40"


def test_rien_ne_casse_sur_un_flux_plat_ou_court():
    assert not len(sp.cochlee(np.ones(100), 1.0)[0]) and not len(sp.cochlee(np.arange(5.0), 1.0)[0])
    assert sp.rythmes(np.zeros(0), np.zeros(0), np.zeros(0)) == []


def test_le_lien_trouve_le_decalage_et_rejette_deux_flux_independants():
    a = _rouge(600, graine=3)
    b = np.roll(a, 7) + 0.3 * _rouge(600, graine=4)
    r = sp.lien(a, b, 30)
    assert r["decalage"] == 7 and r["r"] > 0.5 and r["p"] < 0.01
    faux = sum(sp.lien(_rouge(600, graine=10 + g), _rouge(600, graine=60 + g), 30, essais=100)["p"] < 0.05 for g in range(20))
    assert faux <= 4, f"{faux} faux liens sur 20"


def test_tous_ses_flux_a_leur_instant_et_sa_pensee_interne_reliee(tmp_path):
    t0 = 1_800_000_000.0
    d = tmp_path
    sommets = np.sort(np.random.default_rng(9).uniform(10, 590, 25))
    chaud = sum(np.exp(-0.5 * ((np.arange(600) - c) / 4) ** 2) for c in sommets)
    with open(d / "corps-flux.jsonl", "w") as f:
        f.write("\n")
        for i in range(600):
            f.write(json.dumps({"ts": (t0 + i) * 1000, "etat": {"agitation_g": float(np.sin(2 * np.pi * i / 30)), "chaleur_c": float(chaud[i]), "lux": 10, "coeur_ms": [(t0 + i) * 1000]}}) + "\n")
    with open(d / "pistes.jsonl", "w") as f:
        f.write("\n")
        for c in sommets:                                 # sa pensée suit chaque bosse irrégulière de la chaleur, 3 s après
            f.write(json.dumps({"t": (t0 + c + 3) * 1000, "pensee": "un deux trois quatre", "modele": "haiku"}) + "\n")
    with open(d / "hormones-direct.jsonl", "w") as f:
        f.write("\n")
        for i in range(600):
            f.write(json.dumps({"t": t0 + i, "h": {"cortisol": 0.2 + 0.1 * np.sin(2 * np.pi * i / 60)}}) + "\n")
    with open(d / "son-flux.jsonl", "w") as f:
        f.write("\n")
        for i in range(600):
            f.write(json.dumps({"s": "micro", "t": (t0 + i) * 1000, "p": 100, "l": [[float(np.sin(2 * np.pi * (i + k / 10) / 4)) + 1, 0, 0, 0, 0, 0] for k in range(10)]}) + "\n")
    tous = sp.flux(d, t0, t0 + 600)
    for nom in ("agitation", "pensee_interne", "cortisol", "battements", "son_micro_niveau"):
        assert nom in tous
    assert "lumiere" in tous and not len(sp.cochlee(tous["lumiere"][2], 1.0)[0]), "un capteur qui ne bouge pas n'a pas de spectre"
    t = sp.resume(d, 10, maintenant=t0 + 600)
    assert "entrée agitation : 3" in t or "entrée agitation : 2" in t, t
    assert "pensee_interne relié à" in t and "chaleur (r +" in t, t
    image = d / "a" / "agitation.png"
    t = sp.detail(d, "agitation", 10, image=image, maintenant=t0 + 600)
    assert image.read_bytes().startswith(b"\x89PNG") and "net" in t
    assert "pas assez de données" in sp.detail(d, "inconnu", 10, maintenant=t0 + 600)


def _bosses(n, graine, largeur=6.0):
    a = np.random.default_rng(graine)
    y = np.zeros(n)
    for c in a.uniform(0, n, n // 15):
        y += a.uniform(0.5, 1.5) * np.exp(-0.5 * ((np.arange(n) - c) / largeur) ** 2)
    return y


def test_le_calage_retrouve_pic_sur_creux_decalage_et_etirement_et_rejette_le_hasard():
    """(05/11, Ahmed : « un algo qui recale tous les pics et creux d'un même événement ; ça peut être un pic correspondant à un creux ; R = 1 ou −1 »)"""
    n, centre = 600, 300
    x = _bosses(n, 1, largeur=3.0)
    autre = -np.interp(np.arange(n), centre + 4 + (np.arange(n) - centre) * 1.25, x)      # inversé, décalé de 4 s, étiré
    autre = np.where(np.isfinite(autre), autre, 0)
    r = sp.caler({"ref": x, "autre": autre, "sans_lien": _bosses(n, 2, largeur=3.0)}, "ref", centre)
    a = next(o for o in r if o["flux"] == "autre")
    assert a["r"] < -0.95 and a["cale"], a
    assert abs(a["decalage_s"] - 4) <= 2 and a["etirement"] == 1.25, a
    faux = 0
    for g in range(30):
        q = sp.caler({"ref": _bosses(n, 100 + g, largeur=3.0), "sans_lien": _bosses(n, 200 + g, largeur=3.0)}, "ref", centre)
        faux += q[0]["cale"]
    assert faux <= 3, f"{faux} faux calages sur 30"


def test_la_latence_entre_sa_voix_et_ce_que_le_micro_entend_a_un_dixieme_pres(tmp_path):
    """(05/11, Ahmed : « ça donnera aussi la latence » ; « ±0,1 s »)"""
    t0 = 1_800_000_000.0
    v = _bosses(6000, 5, largeur=4.0) + 0.05 * _rouge(6000, graine=6)
    with open(tmp_path / "son-flux.jsonl", "w") as f:
        f.write("\n")
        for s in range(600):
            for src, y in (("voix", v), ("micro", np.roll(v, 3))):       # le micro l'entend 0,3 s plus tard
                f.write(json.dumps({"s": src, "t": (t0 + s) * 1000, "p": 100, "l": [[float(y[s * 10 + k]) + 1, 0, 0, 0, 0, 0] for k in range(10)]}) + "\n")
    t = sp.latence(tmp_path, "son_voix_niveau", "son_micro_niveau", 10, maintenant=t0 + 600)
    assert "son_micro_niveau suit son_voix_niveau de 0,3 s" in t and "pas prouvée" not in t, t
    assert "son_voix_niveau précède" not in t
    assert "pas assez de données" in sp.latence(tmp_path, "son_voix_niveau", "inconnu", 10, maintenant=t0 + 600)


def test_une_seule_bosse_ne_prouve_jamais_un_calage():
    n = 600
    x = np.exp(-0.5 * ((np.arange(n) - 300) / 8) ** 2)
    r = sp.caler({"ref": x, "autre": np.roll(x, 3)}, "ref", 300)
    assert r[0]["r"] > 0.9 and not r[0]["cale"] and not r[0]["assez"]


def test_export_brut_et_spectre_en_hz(tmp_path):
    t0 = 1_800_000_000.0
    with open(tmp_path / "corps-flux.jsonl", "w") as f:
        f.write("\n")
        for i in range(600):
            f.write(json.dumps({"ts": (t0 + i) * 1000, "etat": {"agitation_g": float(np.sin(2 * np.pi * i / 20))}}) + "\n")
    assert sp.exporter(tmp_path, tmp_path / "x" / "e.json", 10, maintenant=t0 + 600) >= 1
    a = json.loads((tmp_path / "x" / "e.json").read_text())["agitation"]
    assert abs(a["f_hz"][int(np.argmax(a["amp"]))] - 0.05) < 0.005 and len(a["y"]) == 600
