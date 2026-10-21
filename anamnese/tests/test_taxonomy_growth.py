"""Gardes anti-explosion : distinctivité, masse/cohérence des clusters d'orphelins,
allowlist nocturne durcie par le harnais.

Le test MCP suit le pattern de tests/test_taxonomy_mcp.py (T2) : mcp_server est
importé DANS la fixture avec memory.Memory patché (son `_mem = Memory()`
d'import ne doit JAMAIS toucher data/memory.db), et l'outil réellement
enregistré est récupéré via mcp._tool_manager (pas l'attribut .fn direct).
"""
import time

import pytest

import config
import memory
import migrations
import rubrics
import taxonomy
from memory import Memory

NOW = time.time()


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


@pytest.fixture
def srv(tmp_path, monkeypatch):
    """(module mcp_server, Memory temp migrée) — pattern T2 (test_taxonomy_mcp)."""
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    # 1er import de mcp_server : son `_mem = Memory()` doit tomber sur la DB temp.
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", m)
    monkeypatch.setattr(mcp_server, "_embed", lambda t: [0.5] * 8)
    yield mcp_server, m
    m.db.close()


def _fn(mod, name):
    """La fonction d'un outil réellement ENREGISTRÉ auprès de FastMCP."""
    return mod.mcp._tool_manager.get_tool(name).fn


def test_distinctiveness_guard(mem):
    rubrics.rubric_create(mem.db, "projets", NOW)
    eid = mem.add("semantic", "seed", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    rubrics.attach_episode(mem.db, eid, "projets", 0.9, NOW)
    ok, closest, sim = taxonomy.distinctiveness_guard(mem.db, [1.0, 0.01, 0.0, 0.0])
    assert ok is False and closest == "projets" and sim > config.TAX_DISTINCT_MAX
    ok2, _c, _s = taxonomy.distinctiveness_guard(mem.db, [0.0, 1.0, 0.0, 0.0])
    assert ok2 is True                                     # orthogonal = distinct


def test_distinctiveness_guard_sans_centroide(mem):
    """DB sans aucun centroïde (aucune rubrique / rubriques vides) → ok=True."""
    ok, closest, sim = taxonomy.distinctiveness_guard(mem.db, [1.0, 0.0, 0.0, 0.0])
    assert ok is True and closest is None and sim == 0.0
    rubrics.rubric_create(mem.db, "projets", NOW)          # rubrique SANS centroïde
    ok2, closest2, _s = taxonomy.distinctiveness_guard(mem.db, [1.0, 0.0, 0.0, 0.0])
    assert ok2 is True and closest2 is None


def test_orphan_clusters_coherent_vs_disperse(mem):
    for i in range(3):                                     # trio cohérent
        mem.add("semantic", f"theme neuf {i}", importance=0.5,
                embedding=[1.0, 0.05 * i, 0.0, 0.0])
    mem.add("semantic", "bruit isolé", importance=0.5, embedding=[0.0, 0.0, 1.0, 0.0])
    clusters = taxonomy.orphan_clusters(mem.db)
    assert len(clusters) == 1                              # le trio, pas le bruit
    assert len(clusters[0]["episode_ids"]) == 3
    assert clusters[0]["coherence"] >= config.TAX_CLUSTER_MIN_SIM
    # aucun épisode en double dans un cluster émis
    ids = clusters[0]["episode_ids"]
    assert len(ids) == len(set(ids))


def test_orphan_clusters_zero_orphelin(mem):
    assert taxonomy.orphan_clusters(mem.db) == []          # ne crashe pas à vide


def test_rubric_create_mcp_garde(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    eid = m.add("semantic", "seed", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    rubrics.attach_episode(m.db, eid, "projets", 0.9, NOW)
    near = m.add("semantic", "quasi pareil", importance=0.5, embedding=[1.0, 0.01, 0.0, 0.0])
    create = _fn(mcp_server, "rubric_create")
    out = create("savoir", seed_episode_id=near)           # trop proche de 'projets'
    assert "proche" in out.lower() and rubrics.get_rubric_id(m.db, "savoir") is None
    out2 = create("savoir", seed_episode_id=near, force=True)
    assert rubrics.get_rubric_id(m.db, "savoir") is not None
    assert "savoir" in out2


def test_rubric_relabel_tool(srv):
    """Re-labellisation DOUCE (jardinage nocturne) : le label d'affichage change,
    le path ne bouge PAS (aucune cascade), et l'opération est annulable."""
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/ia", NOW)
    out = _fn(mcp_server, "rubric_relabel")("projets/ia", "Intelligence artificielle")
    assert "Intelligence artificielle" in out
    row = m.db.execute(
        "SELECT path, label FROM rubrics WHERE path='projets/ia'").fetchone()
    assert row == ("projets/ia", "Intelligence artificielle")  # path INTACT
    assert "annulé" in _fn(mcp_server, "taxonomy_undo")().lower()
    assert m.db.execute(
        "SELECT label FROM rubrics WHERE path='projets/ia'").fetchone()[0] == "ia"


def test_rubric_create_seed_introuvable(srv):
    """seed_episode_id INEXISTANT ou à embedding vide → refus EXPLICITE (la garde
    de distinctivité ne doit jamais être silencieusement sautée) ; force=True crée."""
    mcp_server, m = srv
    create = _fn(mcp_server, "rubric_create")
    out = create("savoir", seed_episode_id=999999)           # id inexistant
    assert "NON créée" in out and "introuvable" in out
    assert rubrics.get_rubric_id(m.db, "savoir") is None
    m.db.execute("INSERT INTO episodes (id, ts, role, content, embedding) "
                 "VALUES (7777, ?, 'semantic', 'sans embedding', '[]')", (NOW,))
    m.db.commit()
    out2 = create("savoir", seed_episode_id=7777)            # embedding vide
    assert "NON créée" in out2
    assert rubrics.get_rubric_id(m.db, "savoir") is None
    out3 = create("savoir", seed_episode_id=999999, force=True)
    assert rubrics.get_rubric_id(m.db, "savoir") is not None and "savoir" in out3


def test_orphans_report_annote_les_clusters(srv):
    mcp_server, m = srv
    for i in range(3):                                     # trio cohérent orphelin
        m.add("semantic", f"theme neuf {i}", importance=0.5,
              embedding=[1.0, 0.05 * i, 0.0, 0.0])
    out = _fn(mcp_server, "orphans_report")(20)
    assert "CLUSTER" in out and "NOUVEAU" in out


def test_allowlist_nocturne_durcie():
    import consolidate
    tools = consolidate.TOOLS
    for must in ("orphans_report", "rubric_tree", "rubric_create",
                 "memory_reclassify", "rubric_relabel"):
        assert must in tools
    for banned in ("rubric_merge", "rubric_reparent", "taxonomy_undo"):
        assert banned not in tools                          # opérations lourdes IMPOSSIBLES la nuit
