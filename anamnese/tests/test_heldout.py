"""Tests de l'éval HORS-ÉCHANTILLON (anti biais in-sample) — 100% synthétique.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py) :
épisodes synthétiques à embeddings 2-dim, embed_fn injecté. Les seuls fichiers
réels lus sont les JSONL de requêtes (pas la base).
"""

import json
import math

from eval.heldout_eval import (
    QUERIES_HELDOUT_PATH,
    check_disjoint,
    load_heldout,
    run_heldout,
)
from eval.run_eval import QUERIES_PATH, load_queries


# --- Cas 1 : loader held-out ---------------------------------------------------


def test_load_heldout_jsonl(tmp_path):
    p = tmp_path / "queries_heldout.jsonl"
    lignes = [
        {"query": "cockpit faux voyant", "expected": [779, 853], "note": "n1"},
        {"query": "backup WAL", "expected": [1220], "note": "n2"},
    ]
    p.write_text(
        "\n".join(json.dumps(l, ensure_ascii=False) for l in lignes) + "\n",
        encoding="utf-8",
    )
    assert load_heldout(p) == lignes


def test_load_heldout_ignore_lignes_vides(tmp_path):
    p = tmp_path / "queries_heldout.jsonl"
    p.write_text('{"query": "q", "expected": [1], "note": ""}\n\n',
                 encoding="utf-8")
    assert load_heldout(p) == [{"query": "q", "expected": [1], "note": ""}]


# --- Cas 2 : le fichier held-out RÉEL est bien formé et étanche ----------------


def test_fichier_heldout_reel_bien_forme():
    queries = load_heldout(QUERIES_HELDOUT_PATH)
    assert len(queries) >= 15  # taille curée annoncée (~15-20)
    for q in queries:
        assert isinstance(q["query"], str) and q["query"].strip()
        assert isinstance(q["expected"], list) and q["expected"]
        assert all(isinstance(i, int) for i in q["expected"])
        assert len(set(q["expected"])) == len(q["expected"])  # pas de doublon


def test_fichier_heldout_reel_disjoint_du_in_sample():
    heldout = load_heldout(QUERIES_HELDOUT_PATH)
    insample = load_queries(QUERIES_PATH)
    assert check_disjoint(heldout, insample) == []


# --- Cas 3 : check_disjoint (synthétique) --------------------------------------


def test_check_disjoint_detecte_id_partage():
    heldout = [{"query": "autre sujet", "expected": [5, 7], "note": ""}]
    insample = [{"query": "sujet in-sample", "expected": [7, 9], "note": ""}]
    problems = check_disjoint(heldout, insample)
    assert len(problems) == 1
    assert "[7]" in problems[0]


def test_check_disjoint_detecte_texte_identique():
    heldout = [{"query": "  Même   Requête ", "expected": [1], "note": ""}]
    insample = [{"query": "même requête", "expected": [2], "note": ""}]
    problems = check_disjoint(heldout, insample)
    assert len(problems) == 1
    assert "identique" in problems[0]


def test_check_disjoint_ok_si_etanche():
    heldout = [{"query": "a", "expected": [1], "note": ""}]
    insample = [{"query": "b", "expected": [2], "note": ""}]
    assert check_disjoint(heldout, insample) == []


# --- Cas 4 : run_heldout sur épisodes synthétiques ------------------------------

_EPISODES = [
    {"id": 1, "ts": 1000.0, "role": "semantic", "content": "alpha un",
     "importance": 0.5, "embedding": [1.0, 0.0]},
    {"id": 2, "ts": 1001.0, "role": "semantic", "content": "beta deux",
     "importance": 0.5, "embedding": [0.0, 1.0]},
    {"id": 3, "ts": 1002.0, "role": "semantic", "content": "alpha trois",
     "importance": 0.5, "embedding": [0.9, 0.1]},
]

_QUERY_EMBS = {"alpha": [1.0, 0.0], "beta": [0.0, 1.0]}


def _embed_synthetique(text):
    return _QUERY_EMBS[text]


def test_run_heldout_precision_flat_exacte():
    queries = [
        # top-2 cosine pour "alpha" : [1, 3] -> precision 1.0
        {"query": "alpha", "expected": [1, 3], "note": "parfait"},
        # top-2 cosine pour "beta" : [2, 3] mais expected {1, 2} -> 0.5
        {"query": "beta", "expected": [1, 2], "note": "moitié"},
    ]
    res = run_heldout(queries, _EPISODES, k=2, now=2000.0,
                      embed_fn=_embed_synthetique)
    assert res["k"] == 2
    flat = res["flat"]
    assert flat["per_query"][0]["retrieved_ids"] == [1, 3]
    assert flat["per_query"][0]["precision_at_k"] == 1.0
    assert flat["per_query"][1]["retrieved_ids"] == [2, 3]
    assert flat["per_query"][1]["precision_at_k"] == 0.5
    assert math.isclose(flat["precision_at_k"], 0.75)


def test_run_heldout_live_borne_et_structure():
    queries = [{"query": "alpha", "expected": [1, 3], "note": ""}]
    res = run_heldout(queries, _EPISODES, k=2, now=2000.0,
                      embed_fn=_embed_synthetique)
    live = res["live"]
    assert len(live["per_query"]) == 1
    assert len(live["per_query"][0]["retrieved_ids"]) == 2
    assert 0.0 <= live["precision_at_k"] <= 1.0
    assert 0.0 <= live["recall_at_k"] <= 1.0
    assert 0.0 <= live["mrr"] <= 1.0


def test_run_heldout_deterministe_a_now_fige():
    queries = [
        {"query": "alpha", "expected": [1, 3], "note": ""},
        {"query": "beta", "expected": [2], "note": ""},
    ]
    r1 = run_heldout(queries, _EPISODES, k=2, now=2000.0,
                     embed_fn=_embed_synthetique)
    r2 = run_heldout(queries, _EPISODES, k=2, now=2000.0,
                     embed_fn=_embed_synthetique)
    assert r1 == r2
