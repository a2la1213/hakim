"""Notation via le harnais SWE-bench officiel (Docker). Vérifié par exécution.

Prérequis (à installer AVANT le go/no-go, cf. task-3-report) :
  - Docker en marche (`docker --version`)
  - `pip install swebench` dans .venv

grade() shelle `python -m swebench.harness.run_evaluation`, puis retrouve et parse
le rapport JSON `*.{run_id}.json` écrit à la racine. ROBUSTE : si le harnais échoue
ou n'écrit aucun rapport, grade() retourne {} proprement (pas d'exception), et
resolved_ids({}) retourne un set vide.
"""
import json, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATASET = "princeton-nlp/SWE-bench_Lite"


def grade(preds_path, run_id, max_workers=4):
    # check=False : si le harnais échoue, on ne lève pas — on retombe sur la
    # recherche de rapport ci-dessous et on renvoie {} si aucun n'existe.
    # try/except : honore la docstring « pas d'exception » même si le binaire
    # est introuvable / le sous-processus explose.
    try:
        subprocess.run([sys.executable, "-m", "swebench.harness.run_evaluation",
            "--dataset_name", DATASET, "--predictions_path", str(preds_path),
            "--run_id", run_id, "--max_workers", str(max_workers)], check=False)
    except (subprocess.SubprocessError, FileNotFoundError, OSError):
        return {}
    # le harnais écrit <model>.<run_id>.json à la racine ; on prend le PLUS
    # RÉCENT par date de modif (pas le dernier alphabétique).
    reports = list(Path(".").glob(f"*.{run_id}.json"))
    if not reports:
        return {}
    latest = max(reports, key=lambda p: p.stat().st_mtime)
    return json.loads(latest.read_text())


def resolved_ids(report_json):
    return set(report_json.get("resolved_ids", []) or report_json.get("resolved", []))


def sanity_oracle(task, run_id="sanity"):
    """Applique le gold_patch → le harnais DOIT noter resolved (prouve la notation)."""
    p = HERE / "preds_oracle.jsonl"
    p.write_text(json.dumps({"instance_id": task["instance_id"],
        "model_patch": task["patch"], "model_name_or_path": "gold"}))
    rep = grade(p, run_id)
    return task["instance_id"] in resolved_ids(rep)
