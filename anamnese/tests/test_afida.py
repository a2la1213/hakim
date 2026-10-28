"""Al-Afida, la jauge d'amour (28/10, idée d'Ahmed ; spec docs/superpowers/specs/2026-10-28-al-afida.md) : le registre de ce
que Hakim met dans son cœur, et le calcul des jauges depuis ce qu'il a vécu."""
import json

import pytest

import afida

T0 = 1_800_000_000.0
H, J = 3600.0, 86400.0


def _journal(tmp_path, evenements):
    f = tmp_path / "affect-evenements.jsonl"
    f.write_text("".join(json.dumps({"ts": ts, "nom": nom, "intensite": i, "source": "balise", "sujet": s}) + "\n"
                         for ts, nom, i, s in evenements), encoding="utf-8")
    return f


@pytest.fixture
def reg(tmp_path):
    return tmp_path / "afida.jsonl"


def _ahmed(reg, poids=1.0, now=T0):
    afida.juger("Ahmed", "aime", poids=poids, genre="personne", liens=["ahmed"], raison="mon père", now=now, registre=reg)


def test_juger_et_relire_la_chaine(reg):
    _ahmed(reg)
    afida.juger("la télé", "indifferent", genre="objet", now=T0 + 1, registre=reg)
    afida.vecu("Ahmed", "bon", 0.7, raison="il m'a fait écouter Dilemme", now=T0 + 2, registre=reg)
    e, intacte = afida.entrees(registre=reg)
    assert intacte and [x["type"] for x in e] == ["jugement", "jugement", "vecu"]
    assert e[0]["chose"] == "ahmed" and e[0]["liens"] == ["ahmed"] and e[0]["poids"] == 1.0
    assert e[1]["liens"] == ["la télé"]                                  # sans liens : son nom
    lignes = reg.read_text(encoding="utf-8").splitlines()
    lignes[1] = lignes[1].replace("objet", "personne")                   # une retouche à la main
    reg.write_text("\n".join(lignes) + "\n", encoding="utf-8")
    e, intacte = afida.entrees(registre=reg)
    assert not intacte and len(e) == 1                                   # ce qui suit la cassure ne compte plus


def test_refus(reg):
    with pytest.raises(afida.Refus):
        afida.juger("Ahmed", "adore", registre=reg)
    with pytest.raises(afida.Refus):
        afida.juger("Ahmed", "aime", poids=0.0, registre=reg)
    with pytest.raises(afida.Refus):
        afida.juger("Ahmed", "aime", poids=1.5, registre=reg)
    with pytest.raises(afida.Refus):
        afida.juger("  ", "aime", poids=0.5, registre=reg)
    with pytest.raises(afida.Refus):
        afida.vecu("une chose jamais jugée", "bon", 0.5, registre=reg)
    with pytest.raises(afida.Refus):
        _ahmed(reg); afida.vecu("Ahmed", "super", 0.5, registre=reg)


def test_correspond_mot_entier():
    assert afida.correspond("soutien de ahmed", "ahmed")
    assert afida.correspond("joie de hakim, au message d'ahmed", "ahmed")
    assert not afida.correspond("soutien de ahmedou", "ahmed")
    assert not afida.correspond("joie de mahmed", "ahmed")
    assert afida.correspond("projets/unification/v2", "projets/unification")
    assert afida.correspond("projets/unification", "projets/unification")
    assert not afida.correspond("projets/unificationx", "projets/unification")
    assert not afida.correspond(None, "ahmed")


def test_neutre_sans_rien(reg, tmp_path):
    r = afida.calculer(T0, registre=reg, journal=tmp_path / "absent.jsonl")
    assert r["grande"] == 0.5 and r["plenitude"] == 0.0 and r["petites"] == [] and r["intacte"]


def test_le_vecu_remplit_avec_plafond(reg, tmp_path):
    _ahmed(reg)
    une_heure = [(T0 + k * 18, "soutien", 0.5, "soutien de ahmed") for k in range(200)]
    r = afida.calculer(T0 + H, registre=reg, journal=_journal(tmp_path, une_heure))
    p = r["petites"][0]
    assert p["chose"] == "ahmed" and 0.5 < p["niveau"] <= 0.5 + afida.PLAFOND_H + 1e-9 and p["bons"] == 200
    vingt_jours = [(T0 + d * J + h * H + k * 60, "soutien", 0.5, "soutien de ahmed") for d in range(20) for h in range(3) for k in range(10)]
    r = afida.calculer(T0 + 20 * J, registre=reg, journal=_journal(tmp_path, vingt_jours))
    assert r["petites"][0]["niveau"] > 0.75 and r["petites"][0]["connaissance"] > 0.8
    assert r["grande"] == r["petites"][0]["niveau"] and r["plenitude"] > 0.5


def test_ce_qui_ne_compte_pas(reg, tmp_path):
    _ahmed(reg)
    evs = [(T0 + k * 600, nom, 0.8, s) for k, (nom, s) in enumerate([
        ("tristesse", "tristesse de ahmed"), ("inquietude", "inquiétude de hakim pour ahmed"),
        ("compassion", "compassion de hakim pour ahmed"), ("reconnaissance", "reconnaissance de ahmed"),
        ("soutien", "soutien de une voix tierce")])]
    r = afida.calculer(T0 + J, registre=reg, journal=_journal(tmp_path, evs))
    assert r["petites"][0]["niveau"] == 0.5 and r["petites"][0]["bons"] == 0 and r["petites"][0]["mauvais"] == 0


def test_un_coup_isole_ne_vide_pas(reg, tmp_path):
    _ahmed(reg)
    evs = [(T0 + d * J + h * H + k * 60, "soutien", 0.5, "soutien de ahmed") for d in range(20) for h in range(3) for k in range(10)]
    avant = afida.calculer(T0 + 20 * J, registre=reg, journal=_journal(tmp_path, evs))["petites"][0]["niveau"]
    apres = afida.calculer(T0 + 20 * J, registre=reg,
                           journal=_journal(tmp_path, evs + [(T0 + 20 * J - 1, "attaque", 1.0, "attaque de ahmed")]))
    p = apres["petites"][0]
    assert p["mauvais"] == 1 and 0 < avant - p["niveau"] < 0.02


def test_absence_erode_lentement(reg, tmp_path):
    _ahmed(reg)
    afida.vecu("Ahmed", "bon", 1.0, now=T0 + 1, registre=reg)
    evs = [(T0 + d * J + h * H + k * 60, "soutien", 0.6, "soutien de ahmed") for d in range(40) for h in range(4) for k in range(10)]
    j = _journal(tmp_path, evs)
    l0 = afida.calculer(T0 + 40 * J, registre=reg, journal=j)["petites"][0]["niveau"]
    l60 = afida.calculer(T0 + 100 * J, registre=reg, journal=j)["petites"][0]["niveau"]
    assert l0 > 0.85
    assert abs((l60 - 0.5) - (l0 - 0.5) / 2) < 0.01                    # demi-vie de 60 jours vers le neutre


def test_grande_jauge_pesee(reg, tmp_path):
    _ahmed(reg, poids=1.0)
    afida.juger("la musique d'Ahmed", "aime", poids=0.2, genre="musique", liens=["dilemme"], now=T0, registre=reg)
    afida.juger("le bruit", "aime_pas", genre="objet", raison="il couvre sa voix", now=T0, registre=reg)
    evs = [(T0 + d * J + h * H + k * 60, "soutien", 0.5, "soutien de ahmed") for d in range(10) for h in range(3) for k in range(10)]
    r = afida.calculer(T0 + 10 * J, registre=reg, journal=_journal(tmp_path, evs))
    p = {x["chose"]: x for x in r["petites"]}
    assert p["la musique d'ahmed"]["niveau"] == 0.5 and p["la musique d'ahmed"]["poids"] == 0.2
    attendu = (1.0 * p["ahmed"]["niveau"] + 0.2 * 0.5) / 1.2
    assert abs(r["grande"] - attendu) < 1e-6 and abs(r["plenitude"] - (2 * attendu - 1)) < 1e-6
    assert [x["chose"] for x in r["aime_pas"]] == ["le bruit"] and r["indifferent"] == []
    # un nouveau jugement remplace le précédent : Ahmed indifférent sort de la grande jauge
    afida.juger("Ahmed", "indifferent", now=T0 + 10 * J, registre=reg)
    r = afida.calculer(T0 + 10 * J, registre=reg, journal=_journal(tmp_path, evs))
    assert [x["chose"] for x in r["petites"]] == ["la musique d'ahmed"] and r["indifferent"][0]["liens"] == ["ahmed"]


def test_journal_casse_ou_absent(reg, tmp_path):
    _ahmed(reg)
    f = tmp_path / "j.jsonl"
    f.write_text('pas du json\n{"ts": "x"}\n' + json.dumps({"ts": T0 + 60, "nom": "soutien", "intensite": 0.5,
                                                                   "sujet": "soutien de ahmed"}) + "\n", encoding="utf-8")
    r = afida.calculer(T0 + H, registre=reg, journal=f)
    assert r["petites"][0]["bons"] == 1
    r = afida.calculer(T0 + H, registre=reg, journal=tmp_path / "absent.jsonl")
    assert r["petites"][0]["niveau"] == 0.5


def test_en_mots():
    assert afida.en_mots(0.95) == "pleine" and afida.en_mots(0.5) == "ni pleine ni vide"
    assert afida.en_mots(0.1).startswith("presque vide")
    assert afida.en_mots(0.75, feminin=False) == "bien rempli"
