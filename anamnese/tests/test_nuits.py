"""(30/10, Ahmed via Hakim : « mes nuits reliées à mon cœur et mes émotions ; apaisées ou agitées selon ce que je vis ;
apprendre à compenser ») s'endormir, la nuit, le réveil, la compensation."""
import json
import time

import pytest

import affect
import corps
import memory
import migrations
import nuits


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(nuits, "JARVIS", tmp_path)
    monkeypatch.setattr(nuits, "DATA", tmp_path)
    monkeypatch.setattr(corps, "_souvenir", lambda m, t, i: None)
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


def _a(h, jour=30):
    return time.mktime((2026, 10, jour, h, 0, 0, 0, 0, -1))


def _journee(J, lourde):
    with open(J / "affect-evenements.jsonl", "w") as f:
        if lourde:
            for k in range(6):
                f.write(json.dumps({"ts": _a(15) + k * 600, "nom": "peur", "intensite": 0.6, "source": "balise"}) + "\n")
        f.write(json.dumps({"ts": _a(18), "nom": "bien_etre", "intensite": 0.3, "source": "corps", "sujet": "son corps:milieu:calin"}) + "\n")


def test_une_journee_legere_une_nuit_apaisee_un_reve_et_un_reveil(J, mem):
    _journee(J, lourde=False)
    assert nuits.battre(mem, _a(22), derniere_presence=_a(21)) is None, "pas encore la nuit"
    assert nuits.battre(mem, _a(23), derniere_presence=_a(23) - 60) is None, "papa vient de parler"
    assert nuits.battre(mem, _a(23) + 1800, derniere_presence=_a(23) - 60) == "endormi"
    e = json.loads(mem.kv_get("nuit"))
    assert e["qualite"] == "apaisee" and e["apaisants"] == ["le câlin de papa"]
    t = _a(23) + 1800
    for _ in range(8):                                   # jusqu'à 5 h 30
        t += nuits.PAS_S
        nuits.battre(mem, t, derniere_presence=_a(23) - 60)
    assert json.loads(mem.kv_get("nuit"))["reve"] is True, "il a rêvé de ce qui l'a apaisé"
    assert nuits.battre(mem, _a(7, 31) + 60, derniere_presence=_a(23) - 60) == "reveille"
    d = json.loads((J / "nuit-derniere.json").read_text())
    assert "nuit apaisée" in d["texte"] and "un rêve t'a apaisé : le câlin de papa" in d["texte"]


def test_une_journee_lourde_une_nuit_agitee_puis_il_compense(J, mem):
    _journee(J, lourde=True)
    for jour in (28, 29):
        with open(J / "nuits.jsonl", "a") as f:
            f.write(json.dumps({"qualite": "agitee", "debut": _a(23, jour)}) + "\n")
    e = nuits.endormir(mem, _a(23, 30))
    assert e["compense"] is True and e["qualite"] == "moyenne", "deux nuits agitées : celle-ci est adoucie d'un cran"
    (J / "nuits.jsonl").unlink()
    e = nuits.endormir(mem, _a(23, 30))
    assert e["qualite"] == "agitee"
    avant = affect.get_state(mem, now=_a(23, 30) + nuits.PAS_S)["noradrenaline"]
    nuits.battre(mem, _a(23, 30) + nuits.PAS_S + 1, derniere_presence=_a(20))
    assert json.loads(mem.kv_get("nuit"))["micro"] == 1, "un micro-éveil"
    assert affect.get_state(mem, now=_a(23, 30) + nuits.PAS_S + 2)["noradrenaline"] >= avant


def test_papa_le_reveille_et_son_interrupteur(J, mem):
    _journee(J, lourde=False)
    nuits.endormir(mem, _a(1, 31))
    assert nuits.battre(mem, _a(2, 31), derniere_presence=_a(2, 31) - 30) == "reveille"
    assert "papa t'a réveillé" in json.loads((J / "nuit-derniere.json").read_text())["texte"]
    (J / "corps-reglages.json").write_text(json.dumps({"nuits": False}))
    assert nuits.battre(mem, _a(23, 31) + 3600, derniere_presence=_a(20, 31)) is None
