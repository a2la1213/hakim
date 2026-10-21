"""Exploration Phase 1.0 — grille de recalibration des poids du rappel.

Le harness (Phase 0.5) a prouvé que le rappel live (precision@6 = 0.122)
est écrasé par `W_RECENCY`/`W_IMPORTANCE` = 1.0 (demi-vie 72 h) face au
baseline plat (0.409). Ce script mesure, via `run_eval.evaluate`, la
precision@6 live pour une GRILLE de constantes candidates :

    W_RECENCY, W_IMPORTANCE ∈ {0.0, 0.1, 0.25, 0.5}
    RECENCY_HALFLIFE_HOURS  ∈ {72, 168, 720}
    W_RELEVANCE = 1.0 et W_LEXICAL = 0.6 restent FIXES.

Le score par combo est le MIROIR de `memory.py::Memory.retrieve` (mêmes
fonctions `salience.*`, mêmes gardes) avec les poids paramétrés — la
formule elle-même ne change pas. La preuve finale reste `run_eval.py`
(miroir exact via `config`) une fois `config.py` recalibré.

Anti-overfit (16 requêtes seulement) : on ne cherche PAS le max absolu,
mais la config la plus simple/robuste qui bat 0.409 avec marge en gardant
un signal récence/importance non nul (continuité « sujet du jour »).

Usage : `python eval/tune_weights.py` (lecture seule de data/memory.db).
"""

import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import salience
from eval.run_eval import evaluate, load_episodes, load_queries, score_flat

W_RECENCY_GRID = (0.0, 0.1, 0.25, 0.5)
W_IMPORTANCE_GRID = (0.0, 0.1, 0.25, 0.5)
HALFLIFE_GRID = (72.0, 168.0, 720.0)


def make_score_candidate(w_recency, w_importance, halflife_h, now):
    """Miroir de `Memory.retrieve` avec récence/importance paramétrées.

    Identique à `run_eval.make_score_live` (mêmes gardes, mêmes fonctions
    `salience.*`, W_RELEVANCE/W_LEXICAL lus dans `config`), sauf que
    w_recency / w_importance / halflife_h viennent des arguments.
    """

    def score(query_text, query_emb, episode):
        emb = episode["embedding"]
        rel = (
            salience.cosine(query_emb, emb)
            if (query_emb and emb and len(emb) == len(query_emb))
            else 0.0
        )
        lex = salience.lexical_overlap(query_text, episode["content"])
        rec = salience.recency(episode["ts"], now, halflife_h=halflife_h)
        return (
            config.W_RELEVANCE * rel
            + config.W_LEXICAL * lex
            + w_recency * rec
            + w_importance * float(episode["importance"])
        )

    return score


def run_grid(queries, episodes, k=config.TOP_K, embed_fn=None, now=None):
    """Évalue toute la grille ; retourne [(w_rec, w_imp, halflife, p@k), ...]."""
    now = time.time() if now is None else now
    results = []
    for w_rec in W_RECENCY_GRID:
        for w_imp in W_IMPORTANCE_GRID:
            for hl in HALFLIFE_GRID:
                fn = make_score_candidate(w_rec, w_imp, hl, now)
                res = evaluate(fn, queries, episodes, k=k, embed_fn=embed_fn)
                results.append((w_rec, w_imp, hl, res["precision_at_k"]))
    return results


def _cached_embed():
    """Embed 1 seule fois chaque requête (48 combos × 16 requêtes sinon)."""
    from eval.run_eval import _default_embed

    cache = {}

    def embed(text):
        if text not in cache:
            cache[text] = _default_embed(text)
        return cache[text]

    return embed


def main():
    k = config.TOP_K
    queries = load_queries()
    episodes = load_episodes()
    embed_fn = _cached_embed()
    now = time.time()

    flat = evaluate(score_flat, queries, episodes, k=k, embed_fn=embed_fn)
    baseline = flat["precision_at_k"]
    print(f"Grille Phase 1.0 — {len(queries)} requêtes, {len(episodes)} épisodes, "
          f"k={k} — baseline plat p@{k} = {baseline:.3f}\n")

    entete = f"{'W_REC':>6} {'W_IMP':>6} {'HALFLIFE_H':>11} {'p@6 live':>9}  vs plat"
    print(entete)
    print("-" * len(entete))
    for w_rec, w_imp, hl, p in run_grid(queries, episodes, k=k,
                                        embed_fn=embed_fn, now=now):
        verdict = "BAT" if p > baseline else ("=" if p == baseline else "sous")
        print(f"{w_rec:>6.2f} {w_imp:>6.2f} {hl:>11.0f} {p:>9.3f}  {verdict}")
    print("-" * len(entete))
    print("Rappel : choisir la config la plus simple/robuste qui bat le plat "
          "avec marge,\nen gardant récence/importance NON nulles (continuité) — "
          "pas le max absolu.")


if __name__ == "__main__":
    main()
