"""Exploration Phase 3.5b — GATE du terme W_FACET dans le score de rappel.

Question mesurée : « ajouter `W_FACET * facet_overlap(facettes de la requête,
facettes de l'épisode)` au score live améliore-t-il precision@6 sur la vraie
base backfillée (3.5a : facets=200, ~49% des épisodes taggés — les AppLecture
arabes n'ont pas de facettes, tokenizer latin) ? ». Le candidat
`make_score_facet` extrait les facettes de la REQUÊTE
(`facets_extract.extract_facets`, lexical déterministe) et ajoute :

    W_FACET * salience.facet_overlap(facettes requête, facettes épisode)

`facet_overlap` est un JACCARD PUR (|∩|/|∪|, 0 si l'un est vide) — un
utilitaire ensembliste, PAS un 2e signal de similarité (pas de poids de
facette, pas d'embedding) : la redondance avec la relevance cosine est
précisément ce que le gate doit départager. Les facettes des épisodes sont
PRÉCHARGÉES en un dict (une requête SQL, pas de N+1). Requête sans facette
extractible OU épisode non taggé → overlap 0 = score live exact (dégradation
propre). W_FACET=0 → strictement identique au live.

Discipline « gate dur » (même que Phase 1C, qui fut un négatif honnête) : le
terme n'entre dans `Memory.retrieve` QUE si un W de la grille bat le baseline
live (mesuré au début du run — il dérive quand la base grandit) avec marge
>= GATE_MARGIN. Sinon, le score ne change pas — les facettes gardent leur ROI
par `facet_search` + l'organisation (3.5a).

Usage : `python eval/tune_facet.py` (lecture SEULE de data/memory.db,
connexion URI mode=ro : zéro écriture possible).
"""

import pathlib
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import facets_extract
import salience
from eval.run_eval import evaluate, load_episodes, load_queries, make_score_live
from eval.tune_rubric import _cached_embed, connect_ro

# Grille du brief 3.5b — bornes basses ET hautes : si même 0.45 (comparable à
# W_LEXICAL=0.6) ne bat pas le live, le signal facette n'apporte rien au score.
W_FACET_GRID = (0.1, 0.2, 0.3, 0.45)

# Marge de décision : battre le baseline d'au moins +0.02 en p@6 (16 requêtes :
# en dessous, c'est du bruit d'ex-æquo, pas un gain).
GATE_MARGIN = 0.02


def load_facets_by_episode(conn):
    """Précharge {episode_id: frozenset(slugs)} en UNE requête (pas de N+1).

    Épisode sans facette : ABSENT du dict (le score_fn dégrade en frozenset()
    → overlap 0 = live). Mêmes tables que facets_extract.facets_of, jamais
    réimplémenté ailleurs qu'ici en version agrégée.
    """
    rows = conn.execute(
        "SELECT ef.episode_id, f.slug FROM episode_facets ef "
        "JOIN facets f ON f.id = ef.facet_id"
    )
    grouped = {}
    for episode_id, slug in rows:
        grouped.setdefault(episode_id, set()).add(slug)
    return {eid: frozenset(slugs) for eid, slugs in grouped.items()}


def make_score_facet(facets_by_episode, w_facet, now=None):
    """score_fn candidat : score live + W_FACET * Jaccard(facettes).

    - facettes de la requête extraites UNE fois par texte (cache) via
      `facets_extract.extract_facets` — poids ignorés : le Jaccard est sur
      les ENSEMBLES de slugs, pas une similarité pondérée ;
    - `facets_by_episode` : dict préchargé {id: frozenset(slugs)} ;
    - requête sans facette OU épisode non taggé → overlap 0 = live exact ;
    - w_facet=0 → strictement identique au live (x + 0.0 == x).
    """
    score_live = make_score_live(now)
    cache = {}

    def _query_facets(query_text):
        if query_text not in cache:
            cache[query_text] = frozenset(
                slug for slug, _w in facets_extract.extract_facets(query_text)
            )
        return cache[query_text]

    def score(query_text, query_emb, episode):
        overlap = salience.facet_overlap(
            _query_facets(query_text),
            facets_by_episode.get(episode["id"], frozenset()),
        )
        return score_live(query_text, query_emb, episode) + w_facet * overlap

    return score


def run_grid(facets_by_episode, queries, episodes, k=config.TOP_K,
             embed_fn=None, now=None):
    """Évalue la grille ; retourne [(w_facet, p@k), ...]."""
    now = time.time() if now is None else now
    return [
        (
            w,
            evaluate(
                make_score_facet(facets_by_episode, w, now), queries, episodes,
                k=k, embed_fn=embed_fn,
            )["precision_at_k"],
        )
        for w in W_FACET_GRID
    ]


def main():
    k = config.TOP_K
    queries = load_queries()
    episodes = load_episodes()  # URI mode=ro — lecture seule stricte
    conn = connect_ro()
    facets_by_episode = load_facets_by_episode(conn)
    conn.close()
    embed_fn = _cached_embed()
    now = time.time()

    tagged = sum(1 for ep in episodes if ep["id"] in facets_by_episode)
    live = evaluate(make_score_live(now), queries, episodes, k=k, embed_fn=embed_fn)
    baseline = live["precision_at_k"]
    print(f"Gate Phase 3.5b — {len(queries)} requêtes, {len(episodes)} épisodes "
          f"({tagged} taggés = {tagged / (len(episodes) or 1):.0%}), k={k} — "
          f"baseline LIVE p@{k} = {baseline:.3f} (mesuré ce run)\n")

    print("Facettes extraites des requêtes (l'ensemble du Jaccard côté requête) :")
    for q in queries:
        slugs = sorted(s for s, _w in facets_extract.extract_facets(q["query"]))
        libelle = q["query"] if len(q["query"]) <= 48 else q["query"][:45] + "..."
        print(f"  {libelle:48s} {', '.join(slugs) or '(aucune)'}")

    entete = f"\n{'W_FACET':>8} {'p@6':>7}  vs live (marge >= +{GATE_MARGIN})"
    print(entete)
    print("-" * len(entete))
    results = run_grid(facets_by_episode, queries, episodes, k=k,
                       embed_fn=embed_fn, now=now)
    for w, p in results:
        delta = p - baseline
        verdict = "BAT AVEC MARGE" if delta >= GATE_MARGIN else (
            "bat (sans marge)" if delta > 0 else ("=" if delta == 0 else "sous"))
        print(f"{w:>8.2f} {p:>7.3f}  {delta:+.3f}  {verdict}")
    print("-" * len(entete))

    best_w, best_p = max(results, key=lambda x: x[1])
    if best_p - baseline >= GATE_MARGIN:
        print(f"DÉCISION : CÂBLER W_FACET={best_w} "
              f"({baseline:.3f} -> {best_p:.3f}).")
    else:
        print(f"DÉCISION : NE PAS CÂBLER (meilleur candidat {best_p:.3f} à "
              f"W={best_w} vs live {baseline:.3f} : marge < +{GATE_MARGIN}). "
              "Le score de retrieve reste inchangé ; les facettes servent "
              "facet_search + l'organisation (3.5a).")


if __name__ == "__main__":
    main()
