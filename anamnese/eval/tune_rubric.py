"""Exploration Phase 1C — GATE du bonus rubrique-aware dans le score de rappel.

Question mesurée : « ajouter un bonus-rubrique CATÉGORIEL au score live
améliore-t-il precision@6 sur la vraie base migrée+routée ? ». Le candidat
`make_score_rubric` route la REQUÊTE (`routing.route_by_centroid` sur son
embedding, sans kind_hint : une requête n'a pas de rôle) vers une rubrique
cible, puis ajoute au score live :

    W_RUBRIC_MATCH * (1.0 si episode.rubric_id ∈ subtree(rubrique cible) sinon 0.0)

Le bonus est 0/1 — PAS un 2e signal de similarité (le cosinus requête↔centroïde
ne pondère pas le bonus) : la revue 1A avait pointé le double-comptage
embedding comme LE risque de ce terme, et c'est précisément ce que le gate
doit départager. Requête non routable (embedding vide, plancher 1B-harden) →
bonus 0 partout = score live exact (dégradation propre).

Discipline « gate dur » : le terme n'entre dans `Memory.retrieve` QUE si un
W de la grille bat le baseline live (mesuré au début du run, il dérive quand
la base grandit) avec marge >= GATE_MARGIN. Sinon, le score ne change pas —
les rubriques gardent leur ROI par l'organisation + le rappel par tranche (1D).

Usage : `python eval/tune_rubric.py` (lecture SEULE de data/memory.db,
connexion URI mode=ro : zéro écriture possible).
"""

import json
import pathlib
import sqlite3
import sys
import time

_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config
import routing
import rubrics
from eval.run_eval import evaluate, load_queries, make_score_live

# Grille du brief 1C — bornes basses ET hautes : si même 0.4 (comparable à
# W_LEXICAL=0.6) ne bat pas le live, le signal catégoriel n'apporte rien.
W_RUBRIC_GRID = (0.05, 0.1, 0.2, 0.3, 0.4)

# Marge de décision : battre le baseline d'au moins +0.02 en p@6 (16 requêtes :
# en dessous, c'est du bruit d'ex-æquo, pas un gain).
GATE_MARGIN = 0.02


def connect_ro(db_path=config.DB_PATH):
    """Connexion LECTURE SEULE (URI mode=ro) sur la base — zéro écriture."""
    uri = f"file:{pathlib.Path(db_path).resolve()}?mode=ro"
    return sqlite3.connect(uri, uri=True)


def load_episodes_rubric(conn):
    """Tous les épisodes AVEC leur rubric_id (même format que
    run_eval.load_episodes + la clé 'rubric_id', None si jamais routé)."""
    rows = conn.execute(
        "SELECT id, ts, role, content, importance, embedding, rubric_id "
        "FROM episodes ORDER BY id"
    ).fetchall()
    return [
        {
            "id": id_,
            "ts": ts,
            "role": role,
            "content": content,
            "importance": importance,
            "embedding": json.loads(emb_json) if emb_json else [],
            "rubric_id": rubric_id,
        }
        for id_, ts, role, content, importance, emb_json, rubric_id in rows
    ]


def subtree_rubric_ids(conn, root_path):
    """Ids de la rubrique `root_path` + tous ses descendants (frozenset ;
    vide si la rubrique n'existe pas). Délégué à rubrics.subtree_paths —
    jamais réimplémenté ici."""
    paths = rubrics.subtree_paths(conn, root_path)
    if not paths:
        return frozenset()
    marks = ",".join("?" * len(paths))
    rows = conn.execute(f"SELECT id FROM rubrics WHERE path IN ({marks})", paths)
    return frozenset(r[0] for r in rows)


def make_score_rubric(conn, w_rubric, now=None):
    """score_fn candidat : score live + bonus rubrique CATÉGORIEL.

    - la requête est routée UNE fois (cache par embedding) via
      `routing.route_by_centroid(conn, query_emb)` → rubrique cible ;
    - bonus = w_rubric * 1.0 ssi episode.rubric_id ∈ subtree(cible) — 0/1,
      la conf de routage ne pondère RIEN (pas de double-comptage embedding) ;
    - requête non routable → cible vide → bonus 0 partout = live exact ;
    - w_rubric=0 → strictement identique au live (x + 0.0 == x).
    """
    score_live = make_score_live(now)
    cache = {}

    def _target_ids(query_emb):
        key = tuple(query_emb or ())
        if key not in cache:
            path, _conf = routing.route_by_centroid(conn, list(key))
            cache[key] = subtree_rubric_ids(conn, path) if path else frozenset()
        return cache[key]

    def score(query_text, query_emb, episode):
        bonus = 1.0 if episode.get("rubric_id") in _target_ids(query_emb) else 0.0
        return score_live(query_text, query_emb, episode) + w_rubric * bonus

    return score


def _cached_embed():
    """Embed 1 seule fois chaque requête (6 évals × 16 requêtes sinon)."""
    from eval.run_eval import _default_embed

    cache = {}

    def embed(text):
        if text not in cache:
            cache[text] = _default_embed(text)
        return cache[text]

    return embed


def run_grid(conn, queries, episodes, k=config.TOP_K, embed_fn=None, now=None):
    """Évalue la grille ; retourne [(w_rubric, p@k), ...]."""
    now = time.time() if now is None else now
    return [
        (
            w,
            evaluate(
                make_score_rubric(conn, w, now), queries, episodes, k=k,
                embed_fn=embed_fn,
            )["precision_at_k"],
        )
        for w in W_RUBRIC_GRID
    ]


def main():
    k = config.TOP_K
    queries = load_queries()
    conn = connect_ro()
    episodes = load_episodes_rubric(conn)
    embed_fn = _cached_embed()
    now = time.time()

    live = evaluate(make_score_live(now), queries, episodes, k=k, embed_fn=embed_fn)
    baseline = live["precision_at_k"]
    print(f"Gate Phase 1C — {len(queries)} requêtes, {len(episodes)} épisodes, "
          f"k={k} — baseline LIVE p@{k} = {baseline:.3f} (mesuré ce run)\n")

    print("Routage des requêtes (rubrique cible du bonus) :")
    for q in queries:
        emb = embed_fn(q["query"])
        path, conf = routing.route_by_centroid(conn, emb)
        libelle = q["query"] if len(q["query"]) <= 56 else q["query"][:53] + "..."
        print(f"  {path or 'NON ROUTABLE':32s} conf={conf:.3f}  {libelle}")

    entete = f"\n{'W_RUBRIC':>9} {'p@6':>7}  vs live (marge >= +{GATE_MARGIN})"
    print(entete)
    print("-" * len(entete))
    results = run_grid(conn, queries, episodes, k=k, embed_fn=embed_fn, now=now)
    for w, p in results:
        delta = p - baseline
        verdict = "BAT AVEC MARGE" if delta >= GATE_MARGIN else (
            "bat (sans marge)" if delta > 0 else ("=" if delta == 0 else "sous"))
        print(f"{w:>9.2f} {p:>7.3f}  {delta:+.3f}  {verdict}")
    print("-" * len(entete))

    best_w, best_p = max(results, key=lambda x: x[1])
    if best_p - baseline >= GATE_MARGIN:
        print(f"DÉCISION : CÂBLER W_RUBRIC_MATCH={best_w} "
              f"({baseline:.3f} -> {best_p:.3f}).")
    else:
        print(f"DÉCISION : NE PAS CÂBLER (meilleur candidat {best_p:.3f} à "
              f"W={best_w} vs live {baseline:.3f} : marge < +{GATE_MARGIN}). "
              "Le score de retrieve reste inchangé ; les rubriques servent "
              "l'organisation + le rappel par tranche.")
    conn.close()


if __name__ == "__main__":
    main()
