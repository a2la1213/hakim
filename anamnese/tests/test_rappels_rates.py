"""La trace des souvenirs ratés (rappels_rates.py, accord d'Ahmed le 2026-10-22) : notés, puis des alias la nuit."""
import json
import time

import memory
import migrations
import rappel
import rappels_rates as R


def _mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    return m


def _balayage(tmp_path, ids, ts=None):
    f = tmp_path / "rappel.jsonl"
    f.write_text(json.dumps({"ts": (ts or time.time()) * 1000, "ids": ids, "scores": [0.02] * len(ids)}) + "\n")
    return f


def test_le_dernier_balayage_vaut_dix_minutes(tmp_path):
    f = _balayage(tmp_path, [1, 2], ts=1000.0)
    assert R.dernier_balayage(1000.0 + 300, f)["ids"] == [1, 2]
    assert R.dernier_balayage(1000.0 + 700, f) is None


def test_une_recherche_manuelle_juste_apres_est_un_indice(tmp_path):
    j = tmp_path / "rates.jsonl"
    assert R.noter_recherche("anniversaire de sa fille", [7, 1, 9], 1000.0, j, {"ids": [1, 2]}) is True
    o = json.loads(j.read_text())
    assert o["type"] == "recherche" and o["hors_balayage"] == [7, 9]
    assert R.noter_recherche("x", [3], 1000.0, tmp_path / "autre.jsonl", balayage=None) is False   # pas de balayage


def test_la_nuit_les_mots_du_message_deviennent_des_alias_et_le_balayage_les_trouve(tmp_path):
    m = _mem(tmp_path)
    eid = m.add("episodic", "Ahmed a eu de très bons retours sur ses deux projets clients.", importance=0.6, embedding=[])
    j = tmp_path / "rates.jsonl"
    R.noter_rate([eid], "il parlait du garage", 1000.0, j, {"ids": []}, message="Mon projet garage a cartonné !")
    fait = R.corriger(m, 2000.0, j)
    assert fait == [(eid, ["cartonné", "garage", "projet"])] or fait[0][0] == eid
    assert "garage" in R.alias(m)[eid]
    idx = rappel.Index().rafraichir(m)
    assert "garage" in idx.lignes[eid][1]
    assert eid in rappel._par_mots(idx, ["garage"], set(), time.time() + 10)
    assert R.corriger(m, 3000.0, j) == []                           # déjà traité : rien deux fois
    R.retirer_alias(m, eid)
    assert R.alias(m) == {}
    assert "garage" not in rappel.Index().rafraichir(m).lignes[eid][1]
    assert "garage" not in m.db.execute("SELECT content FROM episodes WHERE id = ?", (eid,)).fetchone()[0]
