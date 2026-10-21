"""Compare deux runs du banc (bras B), appariés question par question.

Règle (spec, révisée après relecture) : RÉGRESSION si la différence moyenne du taux correct du
bras B est ≤ −2 points ET si l'intervalle bootstrap apparié à 95 % est entièrement sous 0.
Usage : .venv/bin/python -m eval.banc.comparer avant.jsonl apres.jsonl
"""
import json
import random
import sys

from eval.banc.executer import score_ligne

MARGE = 0.02


def _scores(res):
    return {r["qid"]: s for r in res if r["bras"] == "B" and not r["piege"]
            for s in [score_ligne(r)] if s is not None}


def comparer(avant, apres, graine=0, tirages=2000):
    a, b = _scores(avant), _scores(apres)
    communs = sorted(set(a) & set(b))
    diffs = [b[q] - a[q] for q in communs]
    if not diffs:
        return {"n": 0, "difference": None, "ic95": None, "regression": False}
    rng = random.Random(graine)
    moyennes = sorted(sum(rng.choice(diffs) for _ in diffs) / len(diffs) for _ in range(tirages))
    ic = (moyennes[int(0.025 * tirages)], moyennes[int(0.975 * tirages) - 1])
    moyenne = sum(diffs) / len(diffs)
    return {"n": len(diffs), "difference": moyenne, "ic95": ic,
            "regression": moyenne <= -MARGE and ic[1] < 0}


def _lire(chemin):
    return [json.loads(l) for l in open(chemin, encoding="utf-8") if l.strip()]


if __name__ == "__main__":
    print(json.dumps(comparer(_lire(sys.argv[1]), _lire(sys.argv[2])), ensure_ascii=False, indent=2))
