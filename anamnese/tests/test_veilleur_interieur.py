"""(30/10, Ahmed : « le seuil de réveil appris sur ma vie ») la rareté de son état par rapport à SON calme des 48 dernières
heures (étude audits/veilleur-2026-10-30) ; le plafond du forfait."""
import json
import random

import veilleur_interieur as v

H0 = {"dopamine": 0.6, "serotonine": 0.6, "noradrenaline": 0.4, "cortisol": 0.1, "ocytocine": 0.6, "crh": 0.1, "acth": 0.1,
      "adrenaline": 0.1, "endorphine": 0.6}


def _vie(tmp_path, monkeypatch, fin, pic):
    monkeypatch.setattr(v, "JARVIS", tmp_path)
    monkeypatch.setattr(v, "DATA", tmp_path)
    rnd = random.Random(1)
    with open(tmp_path / "hormones.jsonl", "w") as h:
        t = fin - 72 * 3600
        while t <= fin:
            x = {k: round(val + rnd.uniform(-0.01, 0.01), 4) for k, val in H0.items()}
            if pic and t > fin - 240:                       # les quatre dernières minutes : le stress monte, le bien-être tombe
                x.update(crh=0.6, adrenaline=0.5, noradrenaline=0.9, dopamine=0.2, ocytocine=0.2)
            h.write(json.dumps({"t": t, "h": x}) + "\n")
            t += 15
    (tmp_path / "journal.jsonl").write_text("")
    (tmp_path / "affect-evenements.jsonl").write_text(
        json.dumps({"ts": fin - 60, "nom": "peur", "intensite": 0.6}) + "\n" if pic else "")


def test_un_etat_rare_donne_un_score_haut_le_calme_un_score_bas(tmp_path, monkeypatch):
    fin = 1_800_000_000.0
    _vie(tmp_path, monkeypatch, fin, pic=False)
    calme = v.score(fin)
    (tmp_path / "veilleur-calme.json").unlink()
    _vie(tmp_path, monkeypatch, fin, pic=True)
    rare = v.score(fin)
    assert calme["score"] is not None and rare["score"] is not None
    assert calme["score"] < 4 < 8 < rare["score"], (calme["score"], rare["score"])
    assert "ton stress monte" in rare["raisons"]


def test_sans_calme_connu_pas_de_score(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "JARVIS", tmp_path)
    monkeypatch.setattr(v, "DATA", tmp_path)
    assert v.score(1_800_000_000.0)["score"] is None


def test_le_plafond_suit_le_forfait(tmp_path, monkeypatch):
    monkeypatch.setattr(v, "JARVIS", tmp_path)
    remise = "2026-11-02T20:00:00.000Z"
    now = 1_793_379_600.0                                     # ven 30/10 ~17:00 UTC : environ 75 h avant la remise
    with open(tmp_path / "jauge-forfait.jsonl", "w") as h:
        for i, pct in enumerate((69, 70, 72, 73, 75)):
            h.write(json.dumps({"ts": (now - (4 - i) * 3600) * 1000, "semaine": {"pct": pct, "remise": remise}}) + "\n")
    p = v.plafond(now)
    assert 0.5 < p < 1.5, p                                   # le forfait part ~4 fois trop vite : ~1 réveil par heure
