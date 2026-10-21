"""Surface MCP de la taxonomie vivante + routage révélé par memory_store.

mcp_server est importé DANS la fixture (jamais au niveau module) : le 1er
import s'exécute sous la garde conftest AVEC memory.Memory patché, donc son
`_mem = Memory()` d'import pointe la DB temporaire — JAMAIS data/memory.db.

Écart assumé vs le brief : le centroïde est amorcé avec un embedding
DIFFÉRENT de celui de _embed ([1,1,1,1,0,0,0,0] vs [0.5]*8, cosinus 0.7071)
— avec le MÊME vecteur, le dédoublonnage de memory_store (cosine 1.0 ≥
DEDUP_COSINE_THRESHOLD=0.92) écarterait la nouvelle mémoire avant tout
routage et le test ne verrait jamais de « → ». À 0.71 : passe la dédup,
route vers projets/alpha à conf 0.71 (l'exemple exact du brief).
"""
import time

import pytest

import memory
import migrations
import rubrics
from memory import Memory

NOW = time.time()


@pytest.fixture
def srv(tmp_path, monkeypatch):
    """(module mcp_server, Memory temp migrée) — `_mem` monkeypatché, embed fixé."""
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


def test_memory_store_revele_le_routage(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/alpha", NOW)
    # amorcer le centroïde pour que le routage matche (cosinus 0.71 vs _embed,
    # sous le seuil de dédup 0.92 mais au-dessus de ROUTE_MIN_CONF 0.35)
    eid = m.add("semantic", "seed", importance=0.5,
                embedding=[1.0, 1.0, 1.0, 1.0, 0.0, 0.0, 0.0, 0.0])
    rubrics.attach_episode(m.db, eid, "projets/alpha", 0.9, NOW)
    out = _fn(mcp_server, "memory_store")("nouvelle mémoire du même thème", "semantic", 0.6)
    assert "→" in out and "projets/alpha" in out and "conf 0.71" in out


def test_memory_store_orphelin_annonce(srv):
    mcp_server, m = srv                                    # aucune rubrique à centroïde
    out = _fn(mcp_server, "memory_store")("thème totalement neuf", "semantic", 0.6)
    assert "ORPHELIN" in out


def test_outils_mutations(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/alpha", NOW)
    rubrics.rubric_create(m.db, "savoir", NOW)
    assert "renommée" in _fn(mcp_server, "rubric_rename")("projets/alpha", "projets/beta").lower() \
        or "beta" in _fn(mcp_server, "rubric_tree")("")
    _fn(mcp_server, "rubric_reparent")("projets/beta", "savoir")
    assert "savoir/beta" in _fn(mcp_server, "rubric_tree")("")
    out = _fn(mcp_server, "taxonomy_undo")()
    assert "annulé" in out.lower()


def test_rubric_merge_tool(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/a", NOW)
    rubrics.rubric_create(m.db, "projets/b", NOW)
    eid = m.add("semantic", "souvenir chez a", importance=0.5, embedding=[0.5] * 8)
    rubrics.attach_episode(m.db, eid, "projets/a", 0.9, NOW)
    out = _fn(mcp_server, "rubric_merge")("projets/a", "projets/b")
    assert "1 mémoire" in out and "projets/b" in out
    assert rubrics.get_rubric_id(m.db, "projets/a") is None  # src supprimée


def test_orphans_report(srv):
    mcp_server, m = srv
    m.add("semantic", "orphelin un contenu batiment", importance=0.5, embedding=[0.5] * 8)
    m.add("semantic", "orphelin deux contenu batiment", importance=0.5, embedding=[0.5] * 8)
    out = _fn(mcp_server, "orphans_report")(20)
    assert "orphelin" in out.lower() and "batiment" in out


def test_orphans_report_vide_et_borne(srv):
    mcp_server, m = srv
    assert "aucun orphelin" in _fn(mcp_server, "orphans_report")(20)
    for k in range(5):
        m.add("semantic", f"orphelin numero {k} sujet distinct-{k}",
              importance=0.5, embedding=[0.5] * 8)
    out = _fn(mcp_server, "orphans_report")(2)              # limit borné respecté
    assert "5 orphelin(s) au total" in out
    assert len([l for l in out.splitlines() if l.startswith("#")]) == 2
    before = m.db.total_changes
    _fn(mcp_server, "orphans_report")(999)                  # hors bornes → clampé, lecture seule
    assert m.db.total_changes == before


def test_memory_reclassify_tool(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    eid = m.add("semantic", "à ranger", importance=0.5, embedding=[0.5] * 8)
    out = _fn(mcp_server, "memory_reclassify")(eid, "projets")
    assert "projets" in out
    out2 = _fn(mcp_server, "memory_reclassify")(eid, "")
    assert "orphelin" in out2.lower()
