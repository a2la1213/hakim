"""Harness d'éval de rappel — le GATE dur du ROI (Phase 0.5).

Mesure la qualité du rappel (precision@6, recall@6, MRR) sur des
requêtes-vérité curées (`eval/queries.jsonl`) contre les vrais épisodes.
Sert de gate : dans toute phase suivante, un nouveau terme/poids `W_*`
n'est accepté QUE si `gate(candidate, baseline, ...)["passes"]` est vrai,
c.-à-d. s'il améliore (ou égale) la precision@6 du rappel plat.

Deux `score_fn(query_text, query_emb, episode_row) -> float` fournis :
  - `score_flat` : baseline plat = cosine(query_emb, ep_emb) seul.
  - `make_score_live(now)` : MIROIR EXACT du scoring de
    `memory.py::Memory.retrieve` (mêmes fonctions `salience.*`, mêmes
    poids `config.W_*`, mêmes gardes) — sans réimplémenter de formule.

Rien ne s'exécute à l'import (pas de DB, pas de modèle d'embeddings :
`embeddings.embed` ne charge model2vec qu'au 1er appel).
"""

import json
import os
import pathlib
import sqlite3
import sys
import time

# Permet `python eval/run_eval.py` depuis n'importe où (sys.path[0] = eval/).
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import salience

QUERIES_PATH = pathlib.Path(__file__).resolve().parent / "queries.jsonl"
DEFAULT_K = config.TOP_K  # 6 — même top-k que le rappel live


# --- Métriques (pures, déterministes) -----------------------------------------


def precision_at_k(retrieved_ids, expected_ids, k=DEFAULT_K):
    """|retrieved[:k] ∩ expected| / min(k, len(expected)) — dans [0, 1]."""
    expected = set(expected_ids)
    denom = min(k, len(expected))
    if denom == 0:
        return 0.0
    return len(set(retrieved_ids[:k]) & expected) / denom


def recall_at_k(retrieved_ids, expected_ids, k=DEFAULT_K):
    """|retrieved[:k] ∩ expected| / len(expected) — dans [0, 1]."""
    expected = set(expected_ids)
    if not expected:
        return 0.0
    return len(set(retrieved_ids[:k]) & expected) / len(expected)


def mrr(retrieved_ids, expected_ids, k=DEFAULT_K):
    """1 / rang du premier pertinent dans le top-k, sinon 0.0."""
    expected = set(expected_ids)
    for rank, rid in enumerate(retrieved_ids[:k], start=1):
        if rid in expected:
            return 1.0 / rank
    return 0.0


# --- score_fn : baseline plat + miroir du rappel live -------------------------


def score_flat(query_text, query_emb, episode):
    """Baseline plat : relevance seule = cosine(query_emb, ep_emb)."""
    emb = episode["embedding"]
    if not query_emb or not emb or len(emb) != len(query_emb):
        return 0.0
    return salience.cosine(query_emb, emb)


def make_score_live(now=None):
    """score_fn miroir de `Memory.retrieve` : relevance + lexical + récence
    + importance, avec les MÊMES poids `config.W_*` et gardes.

    `now` est figé à la création pour que l'éval soit reproductible au sein
    d'un run (retrieve le fige aussi, une fois par appel).
    """
    now = time.time() if now is None else now

    def score_live(query_text, query_emb, episode):
        emb = episode["embedding"]
        rel = (
            salience.cosine(query_emb, emb)
            if (query_emb and emb and len(emb) == len(query_emb))
            else 0.0
        )
        lex = salience.lexical_overlap(query_text, episode["content"])
        rec = salience.recency(episode["ts"], now)
        return (
            config.W_RELEVANCE * rel
            + config.W_LEXICAL * lex
            + config.W_RECENCY * rec
            + config.W_IMPORTANCE * float(episode["importance"])
        )

    return score_live


# --- Chargement (queries curées + épisodes réels, lecture seule) --------------


def load_queries(path=QUERIES_PATH):
    """Parse `queries.jsonl` : une requête-vérité par ligne (lignes vides ignorées)."""
    queries = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                queries.append(json.loads(line))
    return queries


def load_episodes(db_path=config.DB_PATH):
    """Lit tous les épisodes en LECTURE SEULE (URI mode=ro : zéro écriture)."""
    uri = f"file:{pathlib.Path(db_path).resolve()}?mode=ro"
    db = sqlite3.connect(uri, uri=True)
    try:
        rows = db.execute(
            "SELECT id, ts, role, content, importance, embedding "
            "FROM episodes ORDER BY id"
        ).fetchall()
    finally:
        db.close()
    return [
        {
            "id": id_,
            "ts": ts,
            "role": role,
            "content": content,
            "importance": importance,
            "embedding": json.loads(emb_json) if emb_json else [],
        }
        for id_, ts, role, content, importance, emb_json in rows
    ]


# --- Moteur d'évaluation -------------------------------------------------------


def _default_embed(text):
    # output pristine : coupe la barre de progression HF du check de cache
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    import embeddings  # import tardif : ne charge model2vec qu'ici

    return embeddings.embed(text)


def evaluate(score_fn, queries, episodes, k=DEFAULT_K, embed_fn=None):
    """Évalue `score_fn` sur les requêtes-vérité : embed la requête, score
    TOUS les épisodes, prend le top-k (tri stable comme `Memory.retrieve` :
    à score égal, l'ordre de la table est conservé), calcule les métriques.
    """
    embed_fn = embed_fn or _default_embed
    per_query = []
    for q in queries:
        query_text = q["query"]
        expected = set(q["expected"])
        query_emb = embed_fn(query_text)
        scored = [(score_fn(query_text, query_emb, ep), ep["id"]) for ep in episodes]
        scored.sort(key=lambda x: x[0], reverse=True)
        retrieved_ids = [id_ for _s, id_ in scored[:k]]
        per_query.append(
            {
                "query": query_text,
                "note": q.get("note", ""),
                "expected": sorted(expected),
                "retrieved_ids": retrieved_ids,
                "precision_at_k": precision_at_k(retrieved_ids, expected, k),
                "recall_at_k": recall_at_k(retrieved_ids, expected, k),
                "mrr": mrr(retrieved_ids, expected, k),
            }
        )
    n = len(per_query) or 1
    return {
        "k": k,
        "per_query": per_query,
        "precision_at_k": sum(p["precision_at_k"] for p in per_query) / n,
        "recall_at_k": sum(p["recall_at_k"] for p in per_query) / n,
        "mrr": sum(p["mrr"] for p in per_query) / n,
    }


def gate(candidate_fn, baseline_fn, queries, episodes, k=DEFAULT_K, embed_fn=None):
    """LE gate dur : un candidat n'est accepté que s'il fait >= le baseline
    en precision@k sur les requêtes-vérité. Outil des phases suivantes.
    """
    baseline = evaluate(baseline_fn, queries, episodes, k=k, embed_fn=embed_fn)
    candidate = evaluate(candidate_fn, queries, episodes, k=k, embed_fn=embed_fn)
    return {
        "baseline": baseline["precision_at_k"],
        "candidate": candidate["precision_at_k"],
        "passes": candidate["precision_at_k"] >= baseline["precision_at_k"],
    }


# --- CLI -----------------------------------------------------------------------


def main():
    k = DEFAULT_K
    queries = load_queries()
    episodes = load_episodes()
    print(f"Éval de rappel — {len(queries)} requêtes-vérité, "
          f"{len(episodes)} épisodes, k={k}\n")

    now = time.time()
    flat = evaluate(score_flat, queries, episodes, k=k)
    live = evaluate(make_score_live(now), queries, episodes, k=k)

    entete = f"{'p@6 plat':>9} {'p@6 live':>9}  requête"
    print(entete)
    print("-" * len(entete))
    for pf, pl in zip(flat["per_query"], live["per_query"]):
        q = pf["query"]
        q = q if len(q) <= 58 else q[:55] + "..."
        print(f"{pf['precision_at_k']:>9.3f} {pl['precision_at_k']:>9.3f}  {q}")
    print("-" * len(entete))
    print(f"{flat['precision_at_k']:>9.3f} {live['precision_at_k']:>9.3f}  "
          f"AGRÉGÉ (precision@{k} moyenne)")
    print(f"{flat['recall_at_k']:>9.3f} {live['recall_at_k']:>9.3f}  "
          f"recall@{k} moyen")
    print(f"{flat['mrr']:>9.3f} {live['mrr']:>9.3f}  MRR moyen")

    verdict = gate(make_score_live(now), score_flat, queries, episodes, k=k)
    print(f"\ngate(live vs plat) : baseline={verdict['baseline']:.3f} "
          f"candidate={verdict['candidate']:.3f} passes={verdict['passes']}")


if __name__ == "__main__":
    main()
