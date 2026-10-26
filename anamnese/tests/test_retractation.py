"""Rétracter un souvenir sans le supprimer (26/10 : le banc eval/retractation.py a montré que la nuit ne propage rien et
que le dérivé reste rappelé comme actuel ; accord d'Ahmed). Écrits avant le code : tout échoue tant que retractation.py
n'existe pas."""
import json

import pytest

import consolidate
import memory
import migrations
import rubrics


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "r.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    yield m
    m.db.close()


@pytest.fixture
def R(tmp_path, monkeypatch):
    import retractation
    monkeypatch.setattr(retractation, "DOSSIER", tmp_path / "retractations")
    return retractation


def _lier(m, derive, source):
    m.db.execute("INSERT INTO insight_edges (insight_id, source_id) VALUES (?,?)", (derive, source))
    m.db.commit()


def _famille(m):
    a = m.add("episodic", "Sur la page de l'observatoire : la comète Orsini-7 revient en mars 2031", embedding=[])
    b = m.add("semantic", "La comète Orsini-7 sera visible en mars 2031", embedding=[])
    c = m.add("insight", "(insight) on montera la voir en 2031", embedding=[])
    d = m.add("semantic", "Ahmed aime le thé", embedding=[])
    e = m.add("episodic", "Erratum de l'observatoire : Orsini-7 ne revient jamais", embedding=[])
    _lier(m, b, a)
    _lier(m, c, b)                     # un dérivé du dérivé (une nuit suivante) : marqué lui aussi, sans rien propager
    return a, b, c, d, e


def test_retracter_marque_la_source_et_toute_sa_descendance_sans_rien_supprimer(mem, R):
    a, b, c, d, e = _famille(mem)
    assert R.marques(mem.db, [a, b, c, d]) == {}
    assert R.retracter(mem.db, [a], "erratum de l'observatoire", correction=e) == [a]
    m = R.marques(mem.db, [a, b, c, d, e])
    assert set(m) == {a, b, c}
    assert m[a]["direct"] is True and m[b]["direct"] is False and m[c]["source"] == a
    assert m[b]["correction"] == e
    assert mem.db.execute("SELECT count(*) FROM episodes").fetchone()[0] == 5, "rien n'est supprimé"
    t = R.marque_texte(m[b])
    assert "SOURCE RÉTRACTÉE" in t and f"#{a}" in t and "erratum" in t and f"#{e}" in t
    assert "RÉTRACTÉ" in R.marque_texte(m[a])
    assert R.retablir(mem.db, [a]) == 1
    assert R.marques(mem.db, [a, b, c]) == {}


def test_un_id_inconnu_ne_se_retracte_pas_et_une_raison_est_exigee(mem, R):
    a, *_ = _famille(mem)
    assert R.retracter(mem.db, [a, 99999], "faux") == [a]
    with pytest.raises(ValueError):
        R.retracter(mem.db, [a], "  ")


def test_hakim_propose_ahmed_tranche(mem, R):
    a, b, c, d, e = _famille(mem)
    ok, msg, pid = R.proposer(mem.db, [a], "l'observatoire a publié un erratum", correction=e)
    assert ok, msg
    assert R.marques(mem.db, [a, b]) == {}, "une proposition ne rétracte rien"
    p = R.propositions()[0]
    assert p["id"] == pid and p["etat"] == "en_attente" and p["ids"] == [a] and p["correction"] == e
    assert p["descendance"] == [b, c] and "Orsini-7" in p["apercu"][0]["debut"]
    assert R.trancher(mem.db, pid, True)[0]
    assert set(R.marques(mem.db, [a, b, c])) == {a, b, c}
    assert R.marques(mem.db, [a])[a]["par"].startswith("ahmed")
    assert not R.trancher(mem.db, pid, True)[0], "déjà tranchée"
    assert R.propositions() == [] and R.propositions(toutes=True)[0]["etat"] == "acceptee"
    ok2, _m, pid2 = R.proposer(mem.db, [d], "test du refus")
    assert R.trancher(mem.db, pid2, False)[0] and R.marques(mem.db, [d]) == {}


def test_une_proposition_irrecevable_est_refusee_tout_de_suite(mem, R):
    a, *_ = _famille(mem)
    assert not R.proposer(mem.db, [99999], "faux")[0]
    assert not R.proposer(mem.db, [a], "")[0]
    assert not R.proposer(mem.db, [a], "faux​ caché")[0], "un caractère invisible"
    assert R.propositions() == []


@pytest.fixture
def srv(mem, R, monkeypatch):
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    return mcp_server


def test_le_rappel_et_la_relecture_affichent_la_marque_et_la_correction_passe_devant(srv, mem, R):
    a, b, c, d, e = _famille(mem)
    R.retracter(mem.db, [a], "erratum de l'observatoire", correction=e)
    txt = srv.memory_recall("comète Orsini-7 mars 2031")
    lignes = txt.splitlines()
    i_b = next(i for i, l in enumerate(lignes) if "sera visible en mars 2031" in l)
    assert "SOURCE RÉTRACTÉE" in lignes[i_b]
    i_e = next(i for i, l in enumerate(lignes) if "Erratum" in l)
    assert i_e < i_b, "la correction passe devant ce qui dépend de la source rétractée"
    assert "SOURCE RÉTRACTÉE" in srv.memory_lire(str(b)) and "RÉTRACTÉ" in srv.memory_lire(str(a))


def test_l_outil_de_hakim_propose_sans_jamais_retracter(srv, mem, R):
    a, b, c, d, e = _famille(mem)
    r = srv.retractation_proposer(f"#{a}", "l'observatoire a publié un erratum", f"#{e}")
    assert r.startswith("Proposé") and "Ahmed" in r and "2 souvenir(s)" in r
    assert R.marques(mem.db, [a, b]) == {}
    assert "en attente" in srv.retractations()


def test_le_balayage_du_cockpit_et_la_nuit_voient_la_marque(mem, R, tmp_path):
    import rappel
    a, b, c, d, e = _famille(mem)
    R.retracter(mem.db, [a], "erratum")
    lignes = rappel._lignes(mem, [b, d], 200)
    assert "SOURCE RÉTRACTÉE" in lignes[b] and "RÉTRACT" not in lignes[d]
    lot = [{"id": b, "ts": 2000.0, "role": "semantic", "content": "La comète…", "externe": False, "emotion": False,
            "retracte": consolidate._retractes(tmp_path / "r.db", [b]).get(b)}]
    assert "SOURCE RÉTRACTÉE" in consolidate.construire_prompt("base", lot)
