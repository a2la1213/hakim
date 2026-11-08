"""Tests de la projection 3D (Cerveau 3D P2a) — PCA à basis FIGÉE + export graphe.

Chaque souvenir est positionné dans l'espace 3D par PCA de son embedding
(numpy SVD, signe des composantes fixé => déterministe). La basis est
calculée UNE fois puis cachée dans kv['brain_basis'] (FIGÉE) : les nouveaux
épisodes se projettent sur la MÊME basis (le graphe ne « danse » pas) ;
recalcul uniquement sur refit=True explicite. brain_graph assemble
nœuds (brain_layout + métadonnées) et arêtes (coactivation, poids > 0)
en LECTURE SEULE.

DB temporaire migrée + embeddings synthétiques 4-dim — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import json

import pytest

import brain_projection
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (brain_layout + coactivation présentes)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _layout(mem):
    """{episode_id: (x, y, z)} — l'état complet de brain_layout."""
    return {
        eid: (x, y, z)
        for eid, x, y, z in mem.db.execute(
            "SELECT episode_id, x, y, z FROM brain_layout"
        ).fetchall()
    }


# Embeddings synthétiques 4-dim, variance nette sur 3 axes (y > x > z), moyenne 0.
_EMBS_4D = [
    [1.0, 0.0, 0.0, 0.0],
    [-1.0, 0.0, 0.0, 0.0],
    [0.0, 2.0, 0.0, 0.0],
    [0.0, -2.0, 0.0, 0.0],
    [0.0, 0.0, 0.5, 0.0],
    [0.0, 0.0, -0.5, 0.0],
]


def _seed_episodes(mem, embs=_EMBS_4D):
    """Un épisode par embedding (facettes désactivées). Retourne les ids."""
    return [
        mem.add("semantic", f"souvenir synthétique numéro {i}", importance=0.5,
                embedding=e, extract_facets=False)
        for i, e in enumerate(embs)
    ]


# --- Cas 0 : schéma — table brain_layout créée par migrate, idempotent ---
def test_schema_brain_layout_table_and_idempotence(tmp_db):
    migrations.migrate(tmp_db)

    cols = {row[1] for row in tmp_db.execute("PRAGMA table_info(brain_layout)")}
    assert cols == {"episode_id", "x", "y", "z", "ts"}

    second = migrations.migrate(tmp_db)  # 2e migrate : AUCUNE erreur, rien à faire
    assert second["tables_created"] == []
    assert second["columns_added"] == []


# --- Cas 1 : fit_basis — mean + 3 composantes, signe déterministe ---
def test_fit_basis_mean_components_deterministic_sign():
    b1 = brain_projection.fit_basis(_EMBS_4D)
    b2 = brain_projection.fit_basis(_EMBS_4D)

    assert b1 == b2                                  # 2 appels -> IDENTIQUE
    assert b1["mean"] == pytest.approx([0.0] * 4)
    assert len(b1["components"]) == 3
    assert all(len(c) == 4 for c in b1["components"])
    json.dumps(b1)                                   # sérialisable JSON (cache kv)

    # variance y > x > z : composantes axis-aligned, signe fixé POSITIF
    # au 1er élément max-abs (sinon SVD peut rendre -v aléatoirement).
    assert b1["components"][0] == pytest.approx([0.0, 1.0, 0.0, 0.0], abs=1e-9)
    assert b1["components"][1] == pytest.approx([1.0, 0.0, 0.0, 0.0], abs=1e-9)
    assert b1["components"][2] == pytest.approx([0.0, 0.0, 1.0, 0.0], abs=1e-9)

    assert brain_projection.fit_basis([]) is None    # aucun embedding -> None


# --- Cas 2 : project_one — produit scalaire connu ; vide/mauvaise dim -> None ---
def test_project_one_known_projection_and_invalid_inputs():
    basis = {
        "mean": [1.0, 0.0, 0.0, 0.0],
        "components": [
            [1.0, 0.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0],
        ],
    }
    # (embedding - mean) . components^T : ([3,4,5,6] - [1,0,0,0]) -> (2,4,5)
    assert brain_projection.project_one([3.0, 4.0, 5.0, 6.0], basis) == \
        pytest.approx((2.0, 4.0, 5.0))

    assert brain_projection.project_one([], basis) is None        # vide
    assert brain_projection.project_one(None, basis) is None      # absent
    assert brain_projection.project_one([1.0, 2.0], basis) is None  # dim != basis
    assert brain_projection.project_one([1.0, 0.0, 0.0, 0.0], None) is None


# --- Cas 3 : get_or_fit_basis — calcule + cache dans kv, relit le cache, refit ---
def test_get_or_fit_basis_caches_and_reads_kv(mem):
    _seed_episodes(mem)

    b1 = brain_projection.get_or_fit_basis(mem.db)
    assert json.loads(mem.kv_get("brain_basis")) == b1  # caché dans kv

    # spy par valeur cachée MODIFIÉE : si le 2e appel recalculait, il ne
    # retournerait pas cette sentinelle — la retourner prouve la lecture du cache.
    sentinel = {"mean": [9.0] * 4,
                "components": [[1.0, 0, 0, 0], [0, 1.0, 0, 0], [0, 0, 1.0, 0]]}
    mem.kv_set("brain_basis", json.dumps(sentinel))
    assert brain_projection.get_or_fit_basis(mem.db) == sentinel  # PAS de recalcul

    # refit=True : recalcule sur les embeddings et RE-cache la vraie basis
    b3 = brain_projection.get_or_fit_basis(mem.db, refit=True)
    assert b3 == b1
    assert json.loads(mem.kv_get("brain_basis")) == b1


# --- Cas 4 : STABILITÉ — un nouvel épisode se projette sur la MÊME basis figée ---
def test_frozen_basis_new_episode_does_not_move_existing_nodes(mem):
    ids = _seed_episodes(mem)
    r1 = brain_projection.backfill_layout(mem.db)
    assert r1["projected"] == len(ids)

    basis_json = mem.kv_get("brain_basis")
    before = _layout(mem)

    new_emb = [0.3, -0.2, 0.9, 0.4]
    new_id = mem.add("semantic", "souvenir arrivé après le fit", importance=0.5,
                     embedding=new_emb, extract_facets=False)
    r2 = brain_projection.backfill_layout(mem.db)  # incrémental, SANS refit

    assert r2["projected"] == 1
    assert mem.kv_get("brain_basis") == basis_json     # basis FIGÉE : pas re-fittée
    after = _layout(mem)
    for eid in ids:                                    # AUCUN nœud existant ne bouge
        assert after[eid] == before[eid]
    # le nouveau nœud est projeté sur la MÊME basis (celle du cache)
    expected = brain_projection.project_one(new_emb, json.loads(basis_json))
    assert after[new_id] == pytest.approx(expected)


# --- Cas 5 : backfill_layout — remplit, skip les vides, incrémental, refit ---
def test_backfill_layout_fills_skips_and_is_incremental(mem):
    a = mem.add("semantic", "embedding valide a", importance=0.5,
                embedding=[1.0, 0.0, 0.0, 0.0], extract_facets=False)
    b = mem.add("semantic", "embedding valide b", importance=0.5,
                embedding=[0.0, 1.0, 0.0, 0.0], extract_facets=False)
    c = mem.add("semantic", "embedding vide", importance=0.5,
                embedding=None, extract_facets=False)  # stocké '[]'

    r1 = brain_projection.backfill_layout(mem.db)
    assert r1 == {"projected": 2, "skipped": 1}
    assert set(_layout(mem)) == {a, b}                 # c (vide) absent

    r2 = brain_projection.backfill_layout(mem.db)      # 2e appel : incrémental
    assert r2 == {"projected": 0, "skipped": 3}        # 2 déjà projetés + 1 vide

    r3 = brain_projection.backfill_layout(mem.db, refit=True)  # refit : re-projette
    assert r3 == {"projected": 2, "skipped": 1}
    assert set(_layout(mem)) == {a, b}


# --- Cas 6 : brain_graph — nœuds complets + arêtes (poids>0), LECTURE SEULE ---
def test_brain_graph_nodes_edges_and_read_only(mem):
    import rubrics

    long_content = "souvenir très détaillé sur la mémoire persistante " * 4  # > 80
    a = mem.add("semantic", long_content, importance=0.9,
                embedding=[1.0, 0.0, 0.0, 0.0], extract_facets=False)
    b = mem.add("semantic", "souvenir b", importance=0.5,
                embedding=[0.0, 1.0, 0.0, 0.0], extract_facets=False)
    c = mem.add("semantic", "sans embedding -> pas de layout", importance=0.5,
                embedding=None, extract_facets=False)

    rid = rubrics.rubric_create(mem.db, "projets", 1000.0)
    mem.db.execute(
        "UPDATE episodes SET rubric_id=?, enc_valence=0.4, enc_arousal=0.6, "
        "recall_count=2 WHERE id=?", (rid, a),
    )
    mem.db.commit()
    mem.tag_episode(a, [("alpha", 1.0), ("beta", 0.8), ("gamma", 0.5), ("delta", 0.2)])

    mem.log_coactivation([a, b], 1000.0)               # arête valide (poids > 0)
    mem.db.execute(  # arête à poids nul : EXCLUE (poids > 0 exigé)
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (?,?,0.0,?)",
        (min(a, c), max(a, c), 1000.0),
    )
    mem.db.execute(  # arête pendante vers c (sans layout) : EXCLUE du graphe
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (?,?,0.5,?)",
        (min(b, c), max(b, c), 1000.0),
    )
    mem.db.commit()

    brain_projection.backfill_layout(mem.db)
    layout = _layout(mem)

    changes0 = mem.db.total_changes
    g = brain_projection.brain_graph(mem.db)
    assert mem.db.total_changes == changes0            # READ-ONLY strict

    assert set(g) == {"nodes", "edges", "wm", "generated_ts"}  # wm : additif (WM3)
    assert g["generated_ts"] > 0
    nodes = {n["id"]: n for n in g["nodes"]}
    assert set(nodes) == {a, b}                        # c (sans layout) ABSENT

    na = nodes[a]
    assert (na["x"], na["y"], na["z"]) == layout[a]
    assert na["rubric"] == "projets"
    assert na["importance"] == pytest.approx(0.9)
    assert na["recall_count"] == 2
    assert na["valence"] == pytest.approx(0.4)
    assert na["arousal"] == pytest.approx(0.6)
    assert na["facets"] == ["alpha", "beta", "gamma"]  # top 3 par poids
    assert na["snippet"] == long_content[:80]

    nb = nodes[b]
    assert nb["rubric"] is None
    assert nb["facets"] == []
    assert nb["snippet"] == "souvenir b"

    assert g["edges"] == [
        {"a": min(a, b), "b": max(a, b), "weight": pytest.approx(0.15)}
    ]

    # limit : borne le nombre de nœuds (les plus importants d'abord) ;
    # les arêtes restent cohérentes (aucune pendante vers un nœud exclu).
    g1 = brain_projection.brain_graph(mem.db, limit=1)
    assert [n["id"] for n in g1["nodes"]] == [a]       # importance 0.9 > 0.5
    assert g1["edges"] == []


# --- Cas 7 : legacy — DB sans brain_layout/coactivation => aucune exception ---
def test_legacy_db_without_new_tables_is_safe(tmp_path, legacy_db):
    tables_before = {
        r[0] for r in legacy_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "brain_layout" not in tables_before         # bien un schéma d'avant P2a
    assert "coactivation" not in tables_before

    res = brain_projection.backfill_layout(legacy_db)  # ne lève PAS
    g = brain_projection.brain_graph(legacy_db)        # ne lève PAS

    assert res == {"projected": 0, "skipped": 0}
    assert g["nodes"] == [] and g["edges"] == []
    tables_after = {
        r[0] for r in legacy_db.execute(
            "SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert tables_after == tables_before               # aucune table apparue

    # DB entièrement vierge (ni episodes ni kv) : skip/empty, jamais d'exception
    blank = __import__("sqlite3").connect(str(tmp_path / "blank.db"))
    try:
        assert brain_projection.get_or_fit_basis(blank) is None
        assert brain_projection.backfill_layout(blank) == {"projected": 0, "skipped": 0}
        gb = brain_projection.brain_graph(blank)
        assert gb["nodes"] == [] and gb["edges"] == []
    finally:
        blank.close()
