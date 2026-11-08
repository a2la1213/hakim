"""Al-Afida au battement du démon (28/10, tâche 3) : toutes les 60 s, les jauges sont recalculées et écrites (kv « afida »),
et l'état intérieur en garde un résumé en mots."""
import json
import time

import pytest

import afida
import interieur
import memory
import migrations


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _jour(h):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 0, 0, 0, 0, -1))


def _horloge(tmp_path, t):
    f = tmp_path / "horloge.json"
    f.write_text(json.dumps({"dernier_ms": t * 1000}))
    return f


def test_le_battement_ecrit_afida(mem, tmp_path):
    t0 = _jour(10)
    afida.juger("Ahmed", "aime", poids=1.0, genre="personne", liens=["ahmed"], now=t0 - 3 * 86400)
    (tmp_path / "affect-evenements.jsonl").write_text("".join(
        json.dumps({"ts": t0 - 2 * 86400 + k * 120, "nom": "soutien", "intensite": 0.6, "sujet": "soutien de ahmed"}) + "\n"
        for k in range(300)), encoding="utf-8")
    e = interieur.tick(mem, now=t0, horloge=_horloge(tmp_path, t0))
    kv = json.loads(mem.kv_get("afida"))
    assert kv["petites"][0]["chose"] == "ahmed" and kv["grande"] > 0.5 and kv["plenitude"] > 0
    assert e["afida"]["grande"] == kv["grande"] and e["afida"]["mots"] == afida.en_mots(kv["grande"], feminin=False)
    assert e["afida"]["petites"][0] == {"chose": "ahmed", "mots": afida.en_mots(kv["petites"][0]["niveau"])}


def test_afida_toutes_les_60_s(mem, tmp_path, monkeypatch):
    t0 = _jour(10)
    appels = []
    vrai = afida.calculer
    monkeypatch.setattr(afida, "calculer", lambda *a, **k: appels.append(1) or vrai(*a, **k))
    for dt in (0, 15, 30, 45, 61):
        interieur.tick(mem, now=t0 + dt, horloge=_horloge(tmp_path, t0))
    assert len(appels) == 2


def test_afida_en_panne_ne_casse_pas_le_battement(mem, tmp_path, monkeypatch):
    t0 = _jour(10)
    monkeypatch.setattr(afida, "calculer", lambda *a, **k: 1 / 0)
    e = interieur.tick(mem, now=t0, horloge=_horloge(tmp_path, t0))
    assert e.get("humeur") and "coeur" in e and mem.kv_get("afida") is None
