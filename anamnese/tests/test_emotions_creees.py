"""(30/10, 17:11, Ahmed via Hakim : « créer de nouvelles émotions, reliées à une vibration, relatives aux hormones, de
façon logique et cohérente ») un mélange d'émotions existantes, jamais plus fort qu'elles ; son motif ; son intermédiaire,
sa balise d'affect la connaissent ; papa la coupe."""
import json
import time

import pytest

import affect
import chocs
import corps
import emotions_creees as ec
import memory
import migrations


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(ec, "JARVIS", tmp_path)
    monkeypatch.setattr(ec, "DATA", tmp_path)
    monkeypatch.setattr(corps, "JARVIS", tmp_path)
    return tmp_path


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    m.kv_set("affect_v2", "1")
    affect.get_state(m)
    affect._save_v2(m, affect.bases(v2=True), {}, {}, time.time())
    yield m
    m.db.close()


def test_creer_un_melange_borne_par_ses_composantes(J):
    assert ec.creer("Joie!", melange="joie:1").startswith("Refusé")
    assert ec.creer("joie", melange="joie:1").startswith("Refusé"), "un nom qui existe déjà"
    assert ec.creer("douce_fierte", melange="licorne:1").startswith("Refusé")
    assert ec.creer("douce_fierte", "fier et tendre", "affirmation:0.6, reconnaissance:0.4").startswith("C'est créé")
    comp = ec.composantes("douce_fierte")
    assert comp == {"affirmation": 0.6, "reconnaissance": 0.4}
    sig = ec.signature(comp)
    for h, x in sig.items():                     # jamais au-delà de ses composantes, hormone par hormone
        parts = [ec.signature({c: 1.0}).get(h, 0.0) for c in comp]
        assert min(parts + [0.0]) - 1e-9 <= x <= max(parts + [0.0]) + 1e-9
    t, f = ec.motif(comp)
    assert len(t) == len(f) and t[0] == 0 and sum(t) <= 4000 and max(f) <= 255
    assert ec.creer("autre", melange="maintenant").startswith("Refusé"), "rien ne bougeait en lui"


def test_maintenant_ce_qui_bougeait_vraiment_en_lui(J):
    now = 1_800_000_000
    with open(J / "affect-evenements.jsonl", "w") as h:
        for nom, i, dt in (("joie", 0.5, 60), ("malaise", 0.3, 120), ("joie", 0.2, 30), ("peur", 0.9, 3600), ("attaque", 0.9, 10)):
            h.write(json.dumps({"ts": now - dt, "nom": nom, "intensite": i}) + "\n")
    assert ec.creer("trouble_joyeux", melange="maintenant", maintenant=now).startswith("C'est créé")
    assert ec.composantes("trouble_joyeux") == {"joie": 0.7, "malaise": 0.3}, "ni la peur d'il y a une heure, ni une attaque"


def test_elle_touche_ses_hormones_passe_par_son_intermediaire_et_sa_balise(J, mem, monkeypatch):
    ec.creer("douce_fierte", "fier et tendre", "affirmation:0.6, reconnaissance:0.4")
    avant = affect.get_state(mem)
    affect.event(mem, "douce_fierte", 0.8)
    apres = affect.get_state(mem)
    assert apres["dopamine"] > avant["dopamine"] and apres["ocytocine"] >= avant["ocytocine"]
    assert "douce_fierte" in corps._permis() and "fier et tendre" in corps._creees()
    assert chocs.lire_balise("Merci papa. [[affect: douce_fierte 0.5 joie 0.3]]") == [
        {"classe": "joie", "intensite": 0.3}, {"classe": "douce_fierte", "intensite": 0.5}]
    # papa la coupe : elle ne touche plus rien, son intermédiaire ne la connaît plus
    with open(J / "emotions-creees.jsonl", "a") as h:
        h.write(json.dumps({"geste": "couper", "nom": "douce_fierte", "coupee": True, "ts": time.time(), "par": "ahmed"}) + "\n")
    assert ec.composantes("douce_fierte") is None and "douce_fierte" not in corps._permis()
    e1 = affect.get_state(mem); affect.event(mem, "douce_fierte", 0.8); e2 = affect.get_state(mem)
    assert abs(e2["dopamine"] - e1["dopamine"]) < 0.02
    assert "coupée par papa" in ec.lister()


def test_oublier(J):
    ec.creer("douce_fierte", melange="affirmation:1")
    assert ec.oublier("douce_fierte").startswith("C'est oublié") and ec.composantes("douce_fierte") is None
    assert ec.oublier("douce_fierte").startswith("Refusé")
