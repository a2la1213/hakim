"""Tests du harness d'éval de rappel (Phase 0.5) — 100% synthétique.

AUCUN test ne touche data/memory.db (garde `_forbid_real_db` de conftest.py) :
épisodes synthétiques à embeddings fixes 2-dim, embed_fn injecté (pas de modèle).
"""

import json
import math

from eval.run_eval import (
    evaluate,
    gate,
    load_queries,
    mrr,
    precision_at_k,
    recall_at_k,
)


# --- Cas 1 : precision_at_k -------------------------------------------------


def test_precision_at_k_parfait():
    assert precision_at_k([1, 2, 3], {1, 2, 3}, k=6) == 1.0


def test_precision_at_k_moitie():
    assert precision_at_k([1, 9, 2, 8], {1, 2, 3, 4}, k=4) == 0.5


def test_precision_at_k_zero():
    assert precision_at_k([7, 8, 9], {1, 2}, k=6) == 0.0


def test_precision_at_k_borne_par_min_k_expected():
    # k=6 > len(expected)=2 : dénominateur = min(6, 2) = 2, pas 6.
    assert precision_at_k([1, 2, 7, 8, 9, 10], {1, 2}, k=6) == 1.0


def test_precision_at_k_ne_regarde_que_le_top_k():
    # le pertinent est en position k+1 : il ne compte pas.
    assert precision_at_k([7, 8, 1], {1}, k=2) == 0.0


def test_precision_at_k_expected_vide():
    assert precision_at_k([1, 2], set(), k=6) == 0.0


# --- Cas 2 : recall_at_k / mrr ----------------------------------------------


def test_recall_at_k_partiel():
    # 1 pertinent trouvé sur 4 attendus.
    assert recall_at_k([1, 7, 8], {1, 2, 3, 4}, k=3) == 0.25


def test_recall_at_k_parfait_et_zero():
    assert recall_at_k([1, 2], {1, 2}, k=6) == 1.0
    assert recall_at_k([7, 8], {1, 2}, k=6) == 0.0


def test_mrr_premier():
    assert mrr([1, 7, 8], {1, 2}, k=6) == 1.0


def test_mrr_troisieme():
    assert math.isclose(mrr([7, 8, 1], {1}, k=6), 1.0 / 3.0)


def test_mrr_absent_du_top_k():
    assert mrr([7, 8, 9], {1}, k=6) == 0.0
    assert mrr([7, 8, 1], {1}, k=2) == 0.0  # pertinent hors top-k


# --- Cas 3 : evaluate sur épisodes synthétiques -------------------------------

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


def _score_cosine(query_text, query_emb, episode):
    ax, ay = query_emb
    bx, by = episode["embedding"]
    na = math.hypot(ax, ay)
    nb = math.hypot(bx, by)
    if na == 0.0 or nb == 0.0:
        return 0.0
    return (ax * bx + ay * by) / (na * nb)


def test_evaluate_synthetique_deterministe():
    queries = [
        # top-2 cosine pour "alpha" : [1, 3] -> precision 1.0, mrr 1.0
        {"query": "alpha", "expected": [1, 3], "note": "parfait"},
        # top-2 cosine pour "beta" : [2, 3] mais expected {1, 2} -> precision 0.5
        {"query": "beta", "expected": [1, 2], "note": "moitié"},
    ]
    res = evaluate(_score_cosine, queries, _EPISODES, k=2,
                   embed_fn=_embed_synthetique)
    per = res["per_query"]
    assert len(per) == 2
    assert per[0]["retrieved_ids"] == [1, 3]
    assert per[0]["precision_at_k"] == 1.0
    assert per[0]["recall_at_k"] == 1.0
    assert per[0]["mrr"] == 1.0
    assert per[1]["retrieved_ids"] == [2, 3]
    assert per[1]["precision_at_k"] == 0.5
    assert per[1]["recall_at_k"] == 0.5
    assert per[1]["mrr"] == 1.0  # id 2 en tête
    assert math.isclose(res["precision_at_k"], 0.75)
    assert math.isclose(res["recall_at_k"], 0.75)
    assert math.isclose(res["mrr"], 1.0)
    assert res["k"] == 2
    # déterminisme : deux appels -> même résultat
    assert evaluate(_score_cosine, queries, _EPISODES, k=2,
                    embed_fn=_embed_synthetique) == res


# --- Cas 4 : gate -------------------------------------------------------------


def test_gate_candidat_meilleur_passe():
    queries = [{"query": "alpha", "expected": [3], "note": ""}]

    def bon(query_text, query_emb, ep):
        return float(ep["id"])  # top-1 = id 3

    def mauvais(query_text, query_emb, ep):
        return -float(ep["id"])  # top-1 = id 1

    res = gate(bon, mauvais, queries, _EPISODES, k=1,
               embed_fn=_embed_synthetique)
    assert res["candidate"] == 1.0
    assert res["baseline"] == 0.0
    assert res["passes"] is True


def test_gate_candidat_pire_echoue():
    queries = [{"query": "alpha", "expected": [3], "note": ""}]

    def bon(query_text, query_emb, ep):
        return float(ep["id"])

    def mauvais(query_text, query_emb, ep):
        return -float(ep["id"])

    res = gate(mauvais, bon, queries, _EPISODES, k=1,
               embed_fn=_embed_synthetique)
    assert res["candidate"] == 0.0
    assert res["baseline"] == 1.0
    assert res["passes"] is False


def test_gate_egalite_passe():
    # >= : un candidat à égalité avec le baseline passe.
    queries = [{"query": "alpha", "expected": [1], "note": ""}]

    def fn(query_text, query_emb, ep):
        return -float(ep["id"])

    res = gate(fn, fn, queries, _EPISODES, k=1, embed_fn=_embed_synthetique)
    assert res["passes"] is True


# --- Cas 5 : load_queries -----------------------------------------------------


def test_load_queries_jsonl(tmp_path):
    p = tmp_path / "queries.jsonl"
    lignes = [
        {"query": "daemon anamnese", "expected": [12, 34], "note": "n1"},
        {"query": "atelier3d", "expected": [56], "note": "n2"},
    ]
    p.write_text(
        "\n".join(json.dumps(l, ensure_ascii=False) for l in lignes) + "\n",
        encoding="utf-8",
    )
    out = load_queries(p)
    assert out == lignes


def test_load_queries_ignore_lignes_vides(tmp_path):
    p = tmp_path / "queries.jsonl"
    p.write_text('{"query": "q", "expected": [1], "note": ""}\n\n',
                 encoding="utf-8")
    assert load_queries(p) == [{"query": "q", "expected": [1], "note": ""}]
