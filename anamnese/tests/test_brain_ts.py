"""Tests 3D-detail — `ts` (date/heure de l'épisode) dans les nœuds de brain_graph.

Chaque nœud de brain_graph gagne un champ ADDITIF `ts` : le timestamp epoch
(float) de l'épisode (episodes.ts), pour afficher date+heure dans le cerveau
3D. Le reste du nœud ne bouge pas, la lecture seule stricte est conservée, et
un ts NULL/illisible (DB partielle hors contrainte NOT NULL) donne ts=None
sans jamais lever.

DB temporaire migrée + embeddings synthétiques — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import sqlite3

import pytest

import brain_projection
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (brain_layout présente)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _seed(mem, n=2):
    """n épisodes à embedding 4-dim + backfill_layout. Retourne les ids."""
    embs = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0], [0.0, 0.0, 1.0, 0.0]][:n]
    ids = [
        mem.add("semantic", f"souvenir ts numéro {i}", importance=0.5,
                embedding=e, extract_facets=False)
        for i, e in enumerate(embs)
    ]
    brain_projection.backfill_layout(mem.db)
    return ids


def _nodes_by_id(graph):
    return {n["id"]: n for n in graph["nodes"]}


# --- Cas 1 : chaque nœud porte le ts de SON épisode (float epoch) ---
def test_node_carries_episode_ts(mem):
    a, b = _seed(mem, 2)
    # timestamps distincts et connus, posés directement (déterministe)
    mem.db.execute("UPDATE episodes SET ts=1111.5 WHERE id=?", (a,))
    mem.db.execute("UPDATE episodes SET ts=2222.25 WHERE id=?", (b,))
    mem.db.commit()

    g = brain_projection.brain_graph(mem.db)

    nodes = _nodes_by_id(g)
    assert nodes[a]["ts"] == pytest.approx(1111.5)
    assert nodes[b]["ts"] == pytest.approx(2222.25)
    assert isinstance(nodes[a]["ts"], float)


# --- Cas 2 : additif — `ts` s'AJOUTE, les autres champs du nœud ne bougent pas,
# --- et brain_graph reste en LECTURE SEULE stricte ---
def test_ts_is_additive_and_read_only(mem):
    _seed(mem, 2)

    changes0 = mem.db.total_changes
    g = brain_projection.brain_graph(mem.db)
    assert mem.db.total_changes == changes0            # AUCUNE écriture

    expected_keys = {"id", "x", "y", "z", "rubric", "importance", "recall_count",
                     "valence", "arousal", "facets", "snippet", "wm", "ts"}
    for n in g["nodes"]:
        assert set(n) == expected_keys


# --- Cas 3 : ts NULL / illisible => ts=None, JAMAIS d'exception ---
def test_ts_null_is_safe(tmp_path):
    # schéma minimal SANS contrainte NOT NULL sur ts (DB partielle/exotique)
    conn = sqlite3.connect(str(tmp_path / "nullable.db"))
    try:
        conn.executescript("""
            CREATE TABLE episodes (
                id INTEGER PRIMARY KEY, ts REAL, role TEXT,
                content TEXT, importance REAL, embedding TEXT
            );
            CREATE TABLE brain_layout (
                episode_id INTEGER PRIMARY KEY, x REAL, y REAL, z REAL, ts REAL
            );
        """)
        conn.execute(
            "INSERT INTO episodes (id, ts, role, content, importance, embedding) "
            "VALUES (1, NULL, 'semantic', 'sans horloge', 0.5, '[1.0,0.0]')"
        )
        conn.execute(
            "INSERT INTO episodes (id, ts, role, content, importance, embedding) "
            "VALUES (2, 'pas-un-nombre', 'semantic', 'ts corrompu', 0.5, '[0.0,1.0]')"
        )
        conn.executemany(
            "INSERT INTO brain_layout (episode_id, x, y, z, ts) VALUES (?,?,?,?,?)",
            [(1, 0.1, 0.2, 0.3, 100.0), (2, 0.4, 0.5, 0.6, 100.0)],
        )
        conn.commit()

        g = brain_projection.brain_graph(conn)         # ne lève PAS

        nodes = _nodes_by_id(g)
        assert nodes[1]["ts"] is None                  # NULL → None
        assert nodes[2]["ts"] is None                  # illisible → None
        assert nodes[1]["snippet"] == "sans horloge"   # le reste est intact
    finally:
        conn.close()


# --- Cas 4 : legacy / vierge — toujours robuste (aucun nœud, aucune exception) ---
def test_ts_legacy_and_blank_dbs_safe(tmp_path, legacy_db):
    g = brain_projection.brain_graph(legacy_db)        # pas de brain_layout
    assert g["nodes"] == []

    blank = sqlite3.connect(str(tmp_path / "blank.db"))
    try:
        assert brain_projection.brain_graph(blank)["nodes"] == []
    finally:
        blank.close()
