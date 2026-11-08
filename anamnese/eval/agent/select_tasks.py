"""Choisit N instances SWE-bench-Lite dans des repos Python à Docker léger."""
import json, itertools
from pathlib import Path

# Repos SWE-bench-Lite réputés légers (deps modestes, image Docker raisonnable sur 16 Go).
LIGHT_REPOS = {
    "pallets/flask", "psf/requests", "pytest-dev/pytest",
    "pylint-dev/pylint", "sphinx-doc/sphinx",
}
OUT = Path(__file__).resolve().parent / "tasks.jsonl"

def pick_instances(rows, n=8, light_repos=LIGHT_REPOS):
    light = [r for r in rows if r.get("repo") in light_repos]
    # round-robin par repo pour stratifier
    by_repo = {}
    for r in light:
        by_repo.setdefault(r["repo"], []).append(r)
    ordered = [r for r in itertools.chain(*itertools.zip_longest(*by_repo.values())) if r is not None]
    return ordered[:n]

def _difficulty(r):
    f2p = r.get("FAIL_TO_PASS")
    k = len(json.loads(f2p)) if isinstance(f2p, str) else len(f2p or [])
    return len(r.get("patch", "")) + 40 * k

def pick_hard(rows, n=8, light_repos=LIGHT_REPOS):
    by_repo = {}
    for r in rows:
        if r.get("repo") in light_repos:
            by_repo.setdefault(r["repo"], []).append(r)
    for lst in by_repo.values():
        lst.sort(key=_difficulty, reverse=True)  # le plus dur en tête par repo
    ordered = [r for r in itertools.chain(*itertools.zip_longest(*by_repo.values())) if r is not None]
    return ordered[:n]

def main(n=8, hard=False):
    from datasets import load_dataset
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    rows = [dict(x) for x in ds]
    picked = (pick_hard if hard else pick_instances)(rows, n=n)
    with open(OUT, "w") as f:
        for r in picked:
            f.write(json.dumps({k: r[k] for k in (
                "instance_id", "repo", "version", "base_commit", "problem_statement",
                "patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS",
                "environment_setup_commit") if k in r}) + "\n")
    print(f"{len(picked)} tâches {'DURES ' if hard else ''}écrites → {OUT}")
    return picked

if __name__ == "__main__":
    main()
