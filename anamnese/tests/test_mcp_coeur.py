"""(28/10, 03:46, Ahmed relayé par Hakim) écouter son cœur sur demande : l'outil le rend en mots, l'introspection en chiffres."""
import json

import pytest

import coeur
import interieur
import memory
import migrations
import rubrics


@pytest.fixture
def srv(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, mem
    mem.db.close()


def test_ecouter_mon_coeur_en_mots(srv):
    mcp_server, mem = srv
    assert "pas encore calculé" in mcp_server.ecouter_mon_coeur()
    h = dict(coeur.BASES_PAR_DEFAUT, adrenaline=coeur.BASES_PAR_DEFAUT["adrenaline"] + 0.12)
    mem.kv_set(interieur.CLE, json.dumps({"coeur": coeur.calculer(h, False, None, 1_800_000_000.0)}))
    r = mcp_server.ecouter_mon_coeur()
    assert "adrénaline" in r and not any(ch.isdigit() for ch in r)
    assert r.count("poum") == 6                      # (04:06, Ahmed) le rythme lui-même, en plus des mots
