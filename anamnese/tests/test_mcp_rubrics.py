"""Tests des outils MCP rubriques (Phase 1D) — via tool.fn, `_mem` monkeypatché.

mcp_server est importé DANS la fixture (jamais au niveau module) : le 1er
import s'exécute sous la garde conftest AVEC memory.Memory patché, donc son
`_mem = Memory()` d'import pointe la DB temporaire — JAMAIS data/memory.db.
`_embed` est patché à None (repli lexical) : déterministe, aucun modèle chargé.
"""

import pytest

import memory
import migrations
import rubrics


@pytest.fixture
def srv(tmp_path, monkeypatch):
    """(module mcp_server, Memory temp migrée + squelette) prêt à tester."""
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)

    # 1er import de mcp_server : `_mem = Memory()` doit tomber sur la DB temp.
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, mem
    mem.db.close()


def _fn(mod, name):
    """La fonction d'un outil réellement ENREGISTRÉ auprès de FastMCP."""
    return mod.mcp._tool_manager.get_tool(name).fn


# --- garde-fou (cas 5) : le _mem testé est bien la Memory sur DB temporaire ---
def test_mcp_mem_is_temp_db(srv):
    mod, mem = srv
    assert mod._mem is mem


# --- Cas 4a : rubric_create crée (label/kind_hint vides → défauts rubrics.py) ---
def test_rubric_create_tool_creates(srv):
    mod, mem = srv
    out = _fn(mod, "rubric_create")(
        "projets/anamnese/rubriques", label="Rubriques", kind_hint="projet"
    )
    assert "projets/anamnese/rubriques" in out
    row = mem.db.execute(
        "SELECT label, kind_hint, depth FROM rubrics WHERE path=?",
        ("projets/anamnese/rubriques",),
    ).fetchone()
    assert row == ("Rubriques", "projet", 2)

    # défauts vides → None → label = dernier segment, kind_hint absent
    _fn(mod, "rubric_create")("projets/unification/tests")
    row = mem.db.execute(
        "SELECT label, kind_hint FROM rubrics WHERE path=?",
        ("projets/unification/tests",),
    ).fetchone()
    assert row == ("tests", None)

    # parent inexistant → l'erreur claire de rubrics.py remonte
    with pytest.raises(ValueError):
        _fn(mod, "rubric_create")("inconnu/enfant")


# --- Cas 4b : rubric_tree liste avec compteurs, filtres root_path/max_depth ---
def test_rubric_tree_tool_lists_with_counts(srv):
    mod, mem = srv
    mem.store_in("un souvenir anamnese", "projets/anamnese")

    out = _fn(mod, "rubric_tree")()  # défauts = tout l'arbre
    assert "projets/anamnese — 1" in out
    assert "savoir-applecture — 0" in out

    scoped = _fn(mod, "rubric_tree")("projets", 1)
    assert "projets/atelier3d" in scoped
    assert "projets/atelier3d/qa" not in scoped  # depth 2 exclu
    assert "savoir-applecture" not in scoped  # hors sous-arbre


# --- Cas 4c : memory_store_in stocke ET rattache (conf 1.0, compteur) ---
def test_memory_store_in_tool_stores_and_attaches(srv):
    mod, mem = srv
    out = _fn(mod, "memory_store_in")(
        "preference : tests deterministes", "technique-transverse", "semantic", 0.7
    )
    assert "technique-transverse" in out

    row = mem.db.execute(
        "SELECT role, importance, rubric_id, rubric_conf FROM episodes WHERE content=?",
        ("preference : tests deterministes",),
    ).fetchone()
    rid = rubrics.get_rubric_id(mem.db, "technique-transverse")
    assert row == ("semantic", 0.7, rid, 1.0)
    assert (
        mem.db.execute(
            "SELECT memory_count FROM rubrics WHERE id=?", (rid,)
        ).fetchone()[0]
        == 1
    )


# --- Cas 4d : memory_recall(rubric=) filtre à la tranche ; défaut inchangé ---
def test_memory_recall_rubric_filters_slice(srv):
    mod, mem = srv
    mem.store_in("decision anamnese rappel", "projets/anamnese")
    mem.store_in("tafsir rappel applecture", "savoir-applecture")
    recall = _fn(mod, "memory_recall")

    everything = recall("rappel")  # sans rubric = comportement actuel
    assert "decision anamnese rappel" in everything
    assert "tafsir rappel applecture" in everything

    sliced = recall("rappel", rubric="projets")
    assert "decision anamnese rappel" in sliced
    assert "applecture" not in sliced
