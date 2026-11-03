"""(03/11, Ahmed : « il doit pouvoir créer ses émotions ou rectifier ses émotions interprétées ; ça passe par le conscient, puis le
subconscient, puis le cœur de base ») sa rectification : décidée par lui, apprise par son corps, ressentie par ses hormones."""
import json

import pytest

import emotions_creees as E
import sensations as S


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "JARVIS", tmp_path)
    return tmp_path


class Coeur:
    def __init__(self):
        self.vus = []


def test_il_rectifie_son_corps_l_apprend_son_coeur_le_sent(J, monkeypatch):
    import affect
    coeur = []
    monkeypatch.setattr(affect, "event", lambda mem, nom, i=1.0, **k: coeur.append((nom, round(i, 2), k.get("source"))))
    r = E.rectifier("peur", "alerte joyeuse", "deux rires juste avant, la main de papa", mem=object(), maintenant=1000.0)
    assert "rectifié" in r.lower()
    assert ("reprise_peur", 0.3, "rectification") in coeur and ("excitation", 0.3, "rectification") in coeur, "son cœur"
    l = [json.loads(x) for x in (J / "emotions-rectifiees.jsonl").read_text().splitlines()]
    assert l[0]["lue"] == "peur" and l[0]["vraie"] == "alerte joyeuse" and "rires" in l[0]["pourquoi"]
    assert "peur" in E.rectifications_texte(maintenant=1100.0) and "alerte joyeuse" in E.rectifications_texte(maintenant=1100.0), \
        "son subconscient (son corps) la relit"
    assert E.biais(maintenant=1100.0) == {("peur", "alerte joyeuse"): 1}
    assert "inconnue" in E.rectifier("peur", "zorglub", mem=object(), maintenant=1000.0)
    assert "même" in E.rectifier("peur", "peur", mem=object(), maintenant=1000.0)


def test_ses_rectifications_penchent_ce_qu_il_ressent_ensuite(J, monkeypatch):
    """apprises, elles font pencher le calcul : là où la peur et l'alerte joyeuse se disputent, la sienne l'emporte"""
    b = S.bases(14)
    serre = dict(b, adrenaline=.6, noradrenaline=.6, dopamine=.45, endorphine=.45, cortisol=.25, crh=.2)
    avant = S.calculer(serre, None, 1000.0, None, 14)["scores"]
    import affect
    monkeypatch.setattr(affect, "event", lambda *a, **k: None)
    for _ in range(3):
        E.rectifier("peur", "alerte joyeuse", "c'était de la joie", mem=object(), maintenant=1000.0)
    apres = S.calculer(serre, None, 1000.0, None, 14, maintenant_biais=1100.0)
    assert apres["scores"]["alerte joyeuse"] > avant["alerte joyeuse"]
