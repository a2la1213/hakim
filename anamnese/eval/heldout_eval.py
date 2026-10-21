"""Éval de rappel HORS-ÉCHANTILLON — l'antidote au biais in-sample.

Le chiffre maison affiché (precision@6 live = 0.661) a été obtenu APRÈS
recalibration des poids `W_*` via `eval/tune_weights.py` sur les MÊMES
16 requêtes de `eval/queries.jsonl` qui le mesurent → c'est un chiffre
IN-SAMPLE (les poids ont été choisis pour lui plaire).

Ce script mesure la même precision@6 (live vs plat) sur un jeu TENU À
L'ÉCART : `eval/queries_heldout.jsonl` — requêtes curées à la main en
LISANT le contenu de la vraie base (jamais dérivées d'un ranker), sur
des sujets/formulations DISTINCTS des 16 in-sample (aucun id attendu
partagé, garde `check_disjoint`). Aucun poids n'a jamais été réglé sur
ce jeu : le chiffre held-out est le seul chiffre maison honnête.

Réutilise le scoring de `eval/run_eval.py` À L'IDENTIQUE (import, zéro
duplication de formule) ; `run_eval.py` n'est pas modifié. Lecture
seule de la vraie base (URI mode=ro via `run_eval.load_episodes`).
Rien ne s'exécute à l'import (pas de DB, pas de modèle d'embeddings).
"""

import pathlib
import sys
import time

# Permet `python eval/heldout_eval.py` depuis n'importe où.
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from eval.run_eval import (  # noqa: E402 — après le sys.path
    DEFAULT_K,
    QUERIES_PATH as QUERIES_INSAMPLE_PATH,
    evaluate,
    load_episodes,
    load_queries,
    make_score_live,
    score_flat,
)

QUERIES_HELDOUT_PATH = pathlib.Path(__file__).resolve().parent / "queries_heldout.jsonl"


# --- Chargement + garde d'étanchéité -------------------------------------------


def load_heldout(path=QUERIES_HELDOUT_PATH):
    """Charge le jeu held-out (même format JSONL que `queries.jsonl`)."""
    return load_queries(path)


def _norm_text(text):
    return " ".join(str(text).lower().split())


def check_disjoint(heldout_queries, insample_queries):
    """Garde d'honnêteté : le held-out ne doit RIEN partager avec l'in-sample.

    Retourne la liste des problèmes (vide = étanche) :
      - même texte de requête (normalisé espaces/casse) ;
      - id d'épisode attendu présent dans un `expected` in-sample.
    """
    problems = []
    insample_texts = {_norm_text(q["query"]) for q in insample_queries}
    insample_ids = set()
    for q in insample_queries:
        insample_ids.update(q["expected"])
    for q in heldout_queries:
        if _norm_text(q["query"]) in insample_texts:
            problems.append(f"requête identique à l'in-sample : {q['query']!r}")
        shared = insample_ids & set(q["expected"])
        if shared:
            problems.append(
                f"ids attendus partagés avec l'in-sample : {sorted(shared)} "
                f"(requête {q['query'][:50]!r})"
            )
    return problems


# --- Moteur ----------------------------------------------------------------------


def run_heldout(queries, episodes, k=DEFAULT_K, now=None, embed_fn=None):
    """Évalue plat ET live (miroir exact de `Memory.retrieve` via run_eval)
    sur un jeu de requêtes. `now` figé pour la reproductibilité intra-run.
    """
    now = time.time() if now is None else now
    return {
        "k": k,
        "flat": evaluate(score_flat, queries, episodes, k=k, embed_fn=embed_fn),
        "live": evaluate(make_score_live(now), queries, episodes, k=k,
                         embed_fn=embed_fn),
    }


# --- CLI -------------------------------------------------------------------------


def _print_table(res, titre):
    flat, live = res["flat"], res["live"]
    entete = f"{'p@6 plat':>9} {'p@6 live':>9}  requête ({titre})"
    print(entete)
    print("-" * len(entete))
    for pf, pl in zip(flat["per_query"], live["per_query"]):
        q = pf["query"]
        q = q if len(q) <= 58 else q[:55] + "..."
        print(f"{pf['precision_at_k']:>9.3f} {pl['precision_at_k']:>9.3f}  {q}")
    print("-" * len(entete))
    print(f"{flat['precision_at_k']:>9.3f} {live['precision_at_k']:>9.3f}  "
          f"AGRÉGÉ (precision@{res['k']} moyenne)")
    print(f"{flat['recall_at_k']:>9.3f} {live['recall_at_k']:>9.3f}  "
          f"recall@{res['k']} moyen")
    print(f"{flat['mrr']:>9.3f} {live['mrr']:>9.3f}  MRR moyen")


def main():
    heldout = load_heldout()
    insample = load_queries(QUERIES_INSAMPLE_PATH)
    problems = check_disjoint(heldout, insample)
    if problems:
        for p in problems:
            print(f"FUITE held-out/in-sample : {p}", file=sys.stderr)
        raise SystemExit(1)

    episodes = load_episodes()
    now = time.time()
    print(f"Éval HORS-ÉCHANTILLON — {len(heldout)} requêtes held-out "
          f"(vs {len(insample)} in-sample), {len(episodes)} épisodes, "
          f"k={DEFAULT_K}\n")

    res_h = run_heldout(heldout, episodes, k=DEFAULT_K, now=now)
    res_i = run_heldout(insample, episodes, k=DEFAULT_K, now=now)

    _print_table(res_h, "HELD-OUT")

    ph_flat = res_h["flat"]["precision_at_k"]
    ph_live = res_h["live"]["precision_at_k"]
    pi_flat = res_i["flat"]["precision_at_k"]
    pi_live = res_i["live"]["precision_at_k"]

    print("\n--- HONNÊTETÉ : held-out vs in-sample (precision@6) ---")
    print(f"{'':>12} {'plat':>7} {'live':>7} {'marge live-plat':>16}")
    print(f"{'HELD-OUT':>12} {ph_flat:>7.3f} {ph_live:>7.3f} "
          f"{ph_live - ph_flat:>+16.3f}   <- jamais servi à régler les poids")
    print(f"{'in-sample':>12} {pi_flat:>7.3f} {pi_live:>7.3f} "
          f"{pi_live - pi_flat:>+16.3f}   <- poids tunés dessus (tune_weights)")
    passes = ph_live >= ph_flat
    print(f"\ngate held-out (live vs plat) : baseline={ph_flat:.3f} "
          f"candidate={ph_live:.3f} passes={passes}")


if __name__ == "__main__":
    main()
