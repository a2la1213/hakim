"""Tests MDT WM3 — la mémoire de travail s'allume dans le cerveau 3D.

brain_graph gagne un champ `wm` PAR NŒUD ("focus" | "halo" | None), lu depuis
kv['working_memory'] (l'état WM1, régénérable), plus un résumé top-level
`wm = {"focus_n", "halo_n"}` qui compte les nœuds TAGGÉS PRÉSENTS dans le
graphe (compteurs de légende : on compte ce qu'on voit — un id en WM sans
layout ne compte pas). Additif : nodes/edges existants inchangés, lecture
seule stricte, robuste si l'état WM est absent/corrompu (tous None).

DB temporaire migrée + embeddings synthétiques — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import json

import pytest

import brain_projection
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (brain_layout + kv présentes)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _wm_clear(mem):
    """Efface kv['working_memory'] — add() (WM1) touche la MDT en écrivant."""
    mem.db.execute("DELETE FROM kv WHERE key='working_memory'")
    mem.db.commit()


def _seed_layout(mem, n=3):
    """n épisodes à embedding 4-dim + backfill_layout, état WM remis à ZÉRO
    (add() est un chemin écrivain WM1 : il toucherait le focus). Retourne les ids."""
    embs = [[1.0, 0.0, 0.0, 0.0], [0.0, 1.0, 0.0, 0.0],
            [0.0, 0.0, 1.0, 0.0], [1.0, 1.0, 0.0, 0.0]][:n]
    ids = [
        mem.add("semantic", f"souvenir wm numéro {i}", importance=0.5,
                embedding=e, extract_facets=False)
        for i, e in enumerate(embs)
    ]
    brain_projection.backfill_layout(mem.db)
    _wm_clear(mem)
    return ids


def _wm_state(focus_ids=(), halo_ids=(), ts=1000.0):
    """JSON kv['working_memory'] au format persisté par wm_touch."""
    return json.dumps({
        "focus": [{"id": i, "score": 1.0} for i in focus_ids],
        "halo": [{"id": i, "score": 0.2} for i in halo_ids],
        "updated_ts": ts,
    })


def _nodes_by_id(graph):
    return {n["id"]: n for n in graph["nodes"]}


# --- Cas 1 : tagging — focus => "focus", halo => "halo", ni l'un ni l'autre => None ---
def test_wm_tagging_focus_halo_none_and_counts(mem):
    a, b, c = _seed_layout(mem, 3)
    mem.kv_set("working_memory", _wm_state(focus_ids=[a], halo_ids=[b]))

    g = brain_projection.brain_graph(mem.db)

    assert set(g) == {"nodes", "edges", "wm", "generated_ts"}
    nodes = _nodes_by_id(g)
    assert nodes[a]["wm"] == "focus"
    assert nodes[b]["wm"] == "halo"
    assert nodes[c]["wm"] is None
    assert g["wm"] == {"focus_n": 1, "halo_n": 1}      # compteurs de légende


# --- Cas 2 : additif — les champs existants des nœuds ne bougent PAS ---
def test_wm_field_is_additive_nodes_keep_existing_shape(mem):
    a, b = _seed_layout(mem, 2)

    before = brain_projection.brain_graph(mem.db)      # état WM absent
    mem.kv_set("working_memory", _wm_state(focus_ids=[a]))
    after = brain_projection.brain_graph(mem.db)

    expected_keys = {"id", "x", "y", "z", "ts", "rubric", "importance",
                     "recall_count", "valence", "arousal", "facets", "snippet",
                     "wm"}
    for n in after["nodes"]:
        assert set(n) == expected_keys
    # seuls les champs wm diffèrent : le reste des nœuds est IDENTIQUE
    strip = lambda ns: [{k: v for k, v in n.items() if k != "wm"} for n in ns]
    assert strip(after["nodes"]) == strip(before["nodes"])
    assert after["edges"] == before["edges"]


# --- Cas 3 : état WM absent => tous None, compteurs à 0, AUCUNE exception ---
def test_wm_state_absent_all_none(mem):
    _seed_layout(mem, 2)
    assert mem.kv_get("working_memory") is None        # pas d'état WM

    g = brain_projection.brain_graph(mem.db)

    assert all(n["wm"] is None for n in g["nodes"])
    assert g["wm"] == {"focus_n": 0, "halo_n": 0}


# --- Cas 4 : état WM corrompu / mal formé => tous None, jamais d'exception ---
def test_wm_state_corrupt_or_malformed_is_safe(mem):
    ids = _seed_layout(mem, 2)

    for raw in ["{pas du json", '"une chaîne"', "[1,2,3]",
                json.dumps({"focus": "oops", "halo": None}),
                json.dumps({"focus": [{"score": 1.0}, {"id": "xyz", "score": 1.0}],
                            "halo": [None]})]:
        mem.kv_set("working_memory", raw)
        g = brain_projection.brain_graph(mem.db)       # ne lève PAS
        assert all(n["wm"] is None for n in g["nodes"])
        assert g["wm"] == {"focus_n": 0, "halo_n": 0}

    # id valide au milieu d'items illisibles : les lisibles sont taggés quand même
    mem.kv_set("working_memory", json.dumps({
        "focus": [{"id": ids[0], "score": 1.0}, {"id": "xyz", "score": 1.0}],
        "halo": [],
        "updated_ts": 1000.0,
    }))
    g = brain_projection.brain_graph(mem.db)
    assert _nodes_by_id(g)[ids[0]]["wm"] == "focus"
    assert g["wm"] == {"focus_n": 1, "halo_n": 0}


# --- Cas 5 : compteurs = nœuds VISIBLES — id en WM sans layout ne compte pas ;
# --- limit qui exclut un nœud taggé le sort aussi des compteurs ---
def test_wm_counts_only_nodes_present_in_graph(mem):
    a, b = _seed_layout(mem, 2)
    ghost = mem.add("semantic", "en WM mais sans embedding => pas de layout",
                    importance=0.5, embedding=None, extract_facets=False)
    mem.kv_set("working_memory", _wm_state(focus_ids=[a, ghost], halo_ids=[b]))

    g = brain_projection.brain_graph(mem.db)
    assert set(_nodes_by_id(g)) == {a, b}              # ghost absent du graphe
    assert g["wm"] == {"focus_n": 1, "halo_n": 1}      # ghost NON compté

    # importance égale => tri par id croissant : limit=1 garde a (focus)
    g1 = brain_projection.brain_graph(mem.db, limit=1)
    assert [n["id"] for n in g1["nodes"]] == [a]
    assert g1["wm"] == {"focus_n": 1, "halo_n": 0}     # b exclu => halo_n=0


# --- Cas 6 : intégration WM1 réelle — wm_touch puis brain_graph ---
def test_wm_real_wm_touch_path_lights_focus(mem):
    a, b = _seed_layout(mem, 2)
    mem.wm_touch([a], 1000.0)                          # le vrai chemin écrivain WM1

    g = brain_projection.brain_graph(mem.db)
    nodes = _nodes_by_id(g)
    assert nodes[a]["wm"] == "focus"
    assert nodes[b]["wm"] is None
    assert g["wm"]["focus_n"] == 1


# --- Cas 7 : LECTURE SEULE stricte, même avec un état WM présent ---
def test_wm_brain_graph_stays_read_only(mem):
    a, b = _seed_layout(mem, 2)
    mem.kv_set("working_memory", _wm_state(focus_ids=[a], halo_ids=[b]))

    changes0 = mem.db.total_changes
    brain_projection.brain_graph(mem.db)
    assert mem.db.total_changes == changes0            # AUCUNE écriture


# --- Cas 8 : legacy / vierge — kv sans état, tables absentes : robuste ---
def test_wm_legacy_and_blank_dbs_safe(tmp_path, legacy_db):
    g = brain_projection.brain_graph(legacy_db)        # pas de brain_layout
    assert g["nodes"] == [] and g["edges"] == []
    assert g["wm"] == {"focus_n": 0, "halo_n": 0}

    blank = __import__("sqlite3").connect(str(tmp_path / "blank.db"))
    try:
        gb = brain_projection.brain_graph(blank)       # ni episodes ni kv
        assert gb["nodes"] == [] and gb["edges"] == []
        assert gb["wm"] == {"focus_n": 0, "halo_n": 0}
    finally:
        blank.close()
