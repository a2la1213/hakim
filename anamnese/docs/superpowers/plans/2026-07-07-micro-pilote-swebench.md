# Micro-pilote SWE-bench-Lite Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Un A/B directionnel mesurant si notre discipline de vérification (bras B) résout plus de bugs réels SWE-bench-Lite que Claude Code nu (bras A), en tenant dans le forfait Claude Code Max.

**Architecture:** `eval/agent/` : `select_tasks.py` (choisit ~8 instances légères → tasks.jsonl), `run_arm.py` (clone au base_commit, lance `claude -p` avec la config du bras, capture `git diff` → preds), `grade.py` (harnais SWE-bench Docker + sanity oracle), `report.py` (scorecard A/B), `run_pilot.py` (orchestrateur + GO/NO-GO sur 1 tâche AVANT les 8 + règle STOP). Code pur (select/report) en TDD ; runner/harnais vérifiés par exécution.

**Tech Stack:** Python 3 (.venv), `datasets` (HuggingFace, SWE-bench_Lite), `swebench` (harnais Docker), `claude` CLI headless (`claude -p`), pytest.

## Global Constraints

- **Budget dur** : tenir dans le forfait Claude Code Max (~125 $ / fenêtre d'usage). Agents via l'abonnement (`claude -p`), **séquentiel**, cap `--max-turns 40` par tâche. **Règle STOP** : journaliser l'usage/temps ; couper une tâche qui dépasse le cap ; go/no-go sur 1 tâche AVANT de lancer les 8.
- **N = 8** par défaut (≤ 12). Directionnel, PAS comparable-SOTA ni statistiquement significatif — l'écrire dans chaque sortie.
- **Isolation des bras** (sinon on ne mesure RIEN) : bras A = `CLAUDE_CONFIG_DIR` vers un dossier VIDE (0 CLAUDE.md, 0 skill, 0 MCP) ; bras B = config avec notre CLAUDE.md + skills systematic-debugging/TDD (+ anamnese MCP, noté inerte sur ces repos). Même modèle Opus 4.8, mêmes tâches.
- **Dataset** : `princeton-nlp/SWE-bench_Lite`, split `test`. Champs utilisés : `instance_id`, `repo`, `base_commit`, `problem_statement`, `patch` (gold), `test_patch`, `FAIL_TO_PASS`, `PASS_TO_PASS`, `environment_setup_commit`.
- **Prédictions** : JSONL, une ligne/instance = `{"instance_id", "model_patch", "model_name_or_path"}` (format harnais SWE-bench).
- Cible `~/Desktop/anamnese/eval/agent/` (repo git anamnese → commits normaux). Tests dans `tests/`.
- Honnêteté : ce pilote mesure la **discipline**, pas la mémoire (inerte sur repos étrangers) ni l'orchestration.

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `eval/agent/__init__.py` | package | 1 |
| `eval/agent/select_tasks.py` | filtre repos légers + choisit N → tasks.jsonl | 1 |
| `eval/agent/run_arm.py` | clone + `claude -p` par bras + capture patch → preds_{arm}.jsonl | 2 |
| `eval/agent/grade.py` | harnais SWE-bench Docker + sanity oracle gold_patch | 3 |
| `eval/agent/report.py` | scorecard A/B + verdict par instance | 4 |
| `eval/agent/run_pilot.py` | orchestrateur + GO/NO-GO 1 tâche + STOP | 5 |
| `tests/test_agent_select.py` / `tests/test_agent_report.py` | TDD des parties pures | 1, 4 |

---

### Task 1: `select_tasks.py` — choisir N instances légères

**Files:**
- Create: `eval/agent/__init__.py`, `eval/agent/select_tasks.py`, `tests/test_agent_select.py`

**Interfaces:**
- Produces: `pick_instances(rows, n=8, light_repos=LIGHT_REPOS) -> list[dict]` (sous-ensemble filtré+tronqué) ; `LIGHT_REPOS` (set de repos Python à Docker léger) ; `main()` écrit `eval/agent/tasks.jsonl`.

- [ ] **Step 1: Test** `tests/test_agent_select.py` :

```python
from eval.agent.select_tasks import pick_instances, LIGHT_REPOS

def _row(repo, iid): return {"repo": repo, "instance_id": iid, "base_commit": "abc"}

def test_filtre_repos_legers_et_tronque():
    rows = ([_row("pallets/flask", f"flask-{i}") for i in range(5)] +
            [_row("django/django", f"dj-{i}") for i in range(5)])  # django = lourd, exclu
    out = pick_instances(rows, n=3)
    assert len(out) == 3
    assert all(r["repo"] in LIGHT_REPOS for r in out)
    assert all("django" not in r["repo"] for r in out)

def test_stratifie_sur_plusieurs_repos_si_possible():
    rows = ([_row("pallets/flask", f"f-{i}") for i in range(4)] +
            [_row("psf/requests", f"r-{i}") for i in range(4)])
    out = pick_instances(rows, n=4)
    assert len({r["repo"] for r in out}) >= 2  # ne pas tout prendre dans un seul repo

def test_n_plus_grand_que_dispo_ne_casse_pas():
    rows = [_row("pallets/flask", "f-0")]
    assert len(pick_instances(rows, n=8)) == 1
```

- [ ] **Step 2: Run test → FAIL** : `cd ~/Desktop/anamnese && .venv/bin/python -m pytest tests/test_agent_select.py -q` → `ModuleNotFoundError`.
- [ ] **Step 3: Implémenter** `eval/agent/select_tasks.py` :

```python
"""Choisit N instances SWE-bench-Lite dans des repos Python à Docker léger."""
import json, itertools
from pathlib import Path

# Repos RÉELLEMENT dans le split test de SWE-bench-Lite ET les plus légers (vérifié).
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
    ordered = [r for r in itertools.chain(*itertools.zip_longest(*by_repo.values())) if r]
    return ordered[:n]

def main(n=8):
    from datasets import load_dataset
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    rows = [dict(x) for x in ds]
    picked = pick_instances(rows, n=n)
    with open(OUT, "w") as f:
        for r in picked:
            f.write(json.dumps({k: r[k] for k in (
                "instance_id", "repo", "base_commit", "problem_statement",
                "patch", "test_patch", "FAIL_TO_PASS", "PASS_TO_PASS",
                "environment_setup_commit") if k in r}) + "\n")
    print(f"{len(picked)} tâches écrites → {OUT}")
    return picked

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run test → PASS** : `.venv/bin/python -m pytest tests/test_agent_select.py -q`.
- [ ] **Step 5: Commit** : `git add eval/agent/__init__.py eval/agent/select_tasks.py tests/test_agent_select.py && git commit -m "eval/agent: sélection de tâches SWE-bench-Lite (repos légers, stratifié)"`.

---

### Task 2: `run_arm.py` — runner d'un bras (clone + claude -p + capture patch)

**Files:**
- Create: `eval/agent/run_arm.py`
- Test: `tests/test_agent_select.py` (ajout d'un test pur pour `build_prompt`/`extract_prediction`)

**Interfaces:**
- Consumes: `tasks.jsonl` (T1).
- Produces: `run_task(task, arm, workdir, config_dir, max_turns=40) -> dict` (une prédiction) ; `build_prompt(task) -> str` ; `extract_prediction(instance_id, diff, model) -> dict` ; `main(arm)` écrit `eval/agent/preds_{arm}.jsonl` + `usage_{arm}.jsonl`.

- [ ] **Step 1: Test des fonctions PURES** (ajouter dans `tests/test_agent_select.py`) :

```python
from eval.agent.run_arm import build_prompt, extract_prediction

def test_build_prompt_contient_l_issue():
    p = build_prompt({"problem_statement": "Fix the parser crash on empty input"})
    assert "empty input" in p and "diff" in p.lower()

def test_extract_prediction_format_harnais():
    pred = extract_prediction("flask-123", "diff --git a/x b/x\n...", "opus-4.8-armB")
    assert pred == {"instance_id": "flask-123",
                    "model_patch": "diff --git a/x b/x\n...",
                    "model_name_or_path": "opus-4.8-armB"}
```

- [ ] **Step 2: Run → FAIL**, puis **Step 3: implémenter** `eval/agent/run_arm.py` :

```python
"""Runner d'un bras : clone le repo au base_commit, lance claude -p headless avec
la config du bras, capture git diff comme prédiction. Vérifié par EXÉCUTION."""
import json, subprocess, tempfile, time, os
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_URL = "https://github.com/{repo}.git"

def build_prompt(task):
    return ("Résous cette issue GitHub dans ce dépôt. Modifie le code source pour "
            "que les tests passent. Ne touche PAS aux fichiers de test.\n\n"
            f"ISSUE:\n{task['problem_statement']}\n\n"
            "Quand tu as fini, laisse simplement tes modifications dans l'arbre "
            "git (un `git diff` doit montrer ton patch).")

def extract_prediction(instance_id, diff, model):
    return {"instance_id": instance_id, "model_patch": diff, "model_name_or_path": model}

def run_task(task, arm, config_dir, max_turns=40, timeout_s=1800):
    with tempfile.TemporaryDirectory() as wd:
        repo_dir = Path(wd) / "repo"
        subprocess.run(["git", "clone", "--quiet", REPO_URL.format(repo=task["repo"]), str(repo_dir)], check=True)
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "--quiet", task["base_commit"]], check=True)
        env = {**os.environ, "CLAUDE_CONFIG_DIR": str(config_dir)}  # isolation du bras
        t0 = time.time()
        proc = subprocess.run(
            ["claude", "-p", build_prompt(task), "--max-turns", str(max_turns),
             "--output-format", "json", "--permission-mode", "acceptEdits"],
            cwd=str(repo_dir), env=env, capture_output=True, text=True, timeout=timeout_s)
        dt = time.time() - t0
        # patch = diff des SOURCES (exclut d'éventuels fichiers de test touchés)
        diff = subprocess.run(["git", "-C", str(repo_dir), "diff"], capture_output=True, text=True).stdout
        model = f"opus-4.8-arm{arm}"
        usage = {"instance_id": task["instance_id"], "arm": arm, "seconds": round(dt, 1),
                 "returncode": proc.returncode, "stdout_tail": (proc.stdout or "")[-400:]}
        return extract_prediction(task["instance_id"], diff, model), usage

def main(arm, config_dir, tasks_path=HERE / "tasks.jsonl"):
    tasks = [json.loads(l) for l in open(tasks_path)]
    preds, usages = [], []
    for t in tasks:  # SÉQUENTIEL (budget)
        try:
            pred, usage = run_task(t, arm, config_dir)
        except subprocess.TimeoutExpired:
            pred = extract_prediction(t["instance_id"], "", f"opus-4.8-arm{arm}")
            usage = {"instance_id": t["instance_id"], "arm": arm, "timeout": True}
        preds.append(pred); usages.append(usage)
        print(f"[{arm}] {t['instance_id']} : {usage.get('seconds','TIMEOUT')}s")
    (HERE / f"preds_{arm}.jsonl").write_text("\n".join(json.dumps(p) for p in preds))
    (HERE / f"usage_{arm}.jsonl").write_text("\n".join(json.dumps(u) for u in usages))
    return preds

if __name__ == "__main__":
    import sys
    main(sys.argv[1], Path(sys.argv[2]))  # ex: python -m eval.agent.run_arm A /tmp/cfg_A
```

- [ ] **Step 4: Run test pur → PASS**.
- [ ] **Step 5: Préparer les 2 config-dirs (isolation)** — `cfg_A` VIDE ; `cfg_B` = copie de `~/.claude/CLAUDE.md` + les skills systematic-debugging/TDD (+ .mcp anamnese). Documenter dans le rapport la commande exacte de préparation.
- [ ] **Step 6: Commit** (le run réel se fait en T5).

---

### Task 3: `grade.py` — harnais SWE-bench + sanity oracle

**Files:**
- Create: `eval/agent/grade.py`

**Interfaces:**
- Consumes: `preds_{arm}.jsonl`, `tasks.jsonl`.
- Produces: `grade(preds_path, run_id) -> dict` (résultats harnais) ; `sanity_oracle(task) -> bool` ; `resolved_ids(report_json) -> set`.

- [ ] **Step 1: Vérif prérequis** — `docker --version` et `.venv/bin/python -c "import swebench"` (sinon `pip install swebench` ; si Docker absent/16 Go trop juste → basculer variante container-free et le noter). Écrire ce check au rapport.
- [ ] **Step 2: Implémenter** `eval/agent/grade.py` :

```python
"""Notation via le harnais SWE-bench officiel (Docker). Vérifié par exécution."""
import json, subprocess
from pathlib import Path
HERE = Path(__file__).resolve().parent
DATASET = "princeton-nlp/SWE-bench_Lite"

def grade(preds_path, run_id, max_workers=4):
    subprocess.run(["python", "-m", "swebench.harness.run_evaluation",
        "--dataset_name", DATASET, "--predictions_path", str(preds_path),
        "--run_id", run_id, "--max_workers", str(max_workers)], check=True)
    # le harnais écrit <model>.<run_id>.json à la racine ; on le retrouve
    reports = sorted(Path(".").glob(f"*.{run_id}.json"))
    return json.loads(reports[-1].read_text()) if reports else {}

def resolved_ids(report_json):
    return set(report_json.get("resolved_ids", []) or report_json.get("resolved", []))

def sanity_oracle(task, run_id="sanity"):
    """Applique le gold_patch → le harnais DOIT noter resolved (prouve la notation)."""
    p = HERE / "preds_oracle.jsonl"
    p.write_text(json.dumps({"instance_id": task["instance_id"],
        "model_patch": task["patch"], "model_name_or_path": "gold"}))
    rep = grade(p, run_id)
    return task["instance_id"] in resolved_ids(rep)
```

- [ ] **Step 3: Exécuter le sanity oracle sur 1 tâche** — `sanity_oracle(task)` doit retourner `True` (le gold_patch est résolu). **C'est la preuve que la notation marche.** Si `False` → la chaîne Docker/harnais est cassée, corriger avant tout.
- [ ] **Step 4: Commit**.

---

### Task 4: `report.py` — scorecard A/B (TDD)

**Files:**
- Create: `eval/agent/report.py`, `tests/test_agent_report.py`

**Interfaces:**
- Consumes: `resolved_ids` de chaque bras + `tasks.jsonl` + `usage_{arm}.jsonl`.
- Produces: `build_scorecard(all_ids, resolved_A, resolved_B, usage_A, usage_B) -> dict`.

- [ ] **Step 1: Test** `tests/test_agent_report.py` :

```python
from eval.agent.report import build_scorecard

def test_scorecard_compte_verdicts_et_taux():
    ids = ["t1", "t2", "t3", "t4"]
    rA = {"t1"}            # A résout t1
    rB = {"t1", "t2", "t3"}  # B résout t1,t2,t3
    sc = build_scorecard(ids, rA, rB, usage_A=[{"seconds": 10}], usage_B=[{"seconds": 30}])
    assert sc["resolved_A"] == 1 and sc["resolved_B"] == 3
    assert sc["taux_A"] == 0.25 and sc["taux_B"] == 0.75
    assert sc["gains_B"] == ["t2", "t3"]      # A✗ B✓
    assert sc["regressions_B"] == []          # A✓ B✗
    assert sc["verdicts"]["t1"] == "A✓B✓" and sc["verdicts"]["t4"] == "A✗B✗"
    assert sc["cout_A_s"] == 10 and sc["cout_B_s"] == 30
    assert sc["directionnel"] is True  # rappel honnêteté toujours présent
```

- [ ] **Step 2: Run → FAIL**, **Step 3: implémenter** `eval/agent/report.py` :

```python
"""Scorecard A/B : taux de résolution, verdict par instance, coût (proxy temps)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent

def build_scorecard(all_ids, resolved_A, resolved_B, usage_A, usage_B):
    verdicts = {}
    for i in all_ids:
        a, b = i in resolved_A, i in resolved_B
        verdicts[i] = ("A✓B✓" if a and b else "A✗B✓" if b and not a
                       else "A✓B✗" if a and not b else "A✗B✗")
    n = len(all_ids) or 1
    return {
        "n": len(all_ids),
        "resolved_A": len(resolved_A), "resolved_B": len(resolved_B),
        "taux_A": round(len(resolved_A) / n, 3), "taux_B": round(len(resolved_B) / n, 3),
        "gains_B": sorted([i for i in all_ids if i in resolved_B and i not in resolved_A]),
        "regressions_B": sorted([i for i in all_ids if i in resolved_A and i not in resolved_B]),
        "verdicts": verdicts,
        "cout_A_s": sum(u.get("seconds", 0) for u in usage_A),
        "cout_B_s": sum(u.get("seconds", 0) for u in usage_B),
        "directionnel": True,
        "note": f"N={len(all_ids)} — signal DIRECTIONNEL, pas comparable-SOTA ni statistiquement significatif. Mesure la discipline, pas la mémoire.",
    }

def main(resolved_A, resolved_B):
    tasks = [json.loads(l) for l in open(HERE / "tasks.jsonl")]
    ids = [t["instance_id"] for t in tasks]
    uA = [json.loads(l) for l in open(HERE / "usage_A.jsonl")]
    uB = [json.loads(l) for l in open(HERE / "usage_B.jsonl")]
    sc = build_scorecard(ids, resolved_A, resolved_B, uA, uB)
    (HERE / "scorecard_agent.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False))
    print(json.dumps(sc, indent=2, ensure_ascii=False))
    return sc
```

- [ ] **Step 4: Run test → PASS**. **Step 5: Commit**.

---

### Task 5: `run_pilot.py` — orchestrateur + GO/NO-GO + STOP

**Files:**
- Create: `eval/agent/run_pilot.py`

**Interfaces:** Consumes T1-T4.

- [ ] **Step 1: Implémenter** l'orchestrateur avec le **gate go/no-go** :

```python
"""Orchestre le micro-pilote. GO/NO-GO sur 1 tâche AVANT de dépenser sur N."""
import json, sys
from pathlib import Path
from eval.agent import select_tasks, run_arm, grade, report
HERE = Path(__file__).resolve().parent

def pilot(cfg_A, cfg_B, n=8, smoke=True):
    tasks = select_tasks.main(n=n)
    # 1) SANITY oracle sur la 1re tâche → la notation marche ?
    assert grade.sanity_oracle(tasks[0]), "STOP: le harnais ne note pas le gold_patch — chaîne cassée."
    if smoke:
        # 2) GO/NO-GO : pipeline complet sur la SEULE 1re tâche, les 2 bras
        one = [tasks[0]]
        (HERE / "tasks.jsonl").write_text(json.dumps(one[0]))
        run_arm.main("A", Path(cfg_A)); run_arm.main("B", Path(cfg_B))
        rA = grade.resolved_ids(grade.grade(HERE / "preds_A.jsonl", "smokeA"))
        rB = grade.resolved_ids(grade.grade(HERE / "preds_B.jsonl", "smokeB"))
        print("SMOKE OK — relance avec smoke=False pour les", n, "tâches.")
        return report.main(rA, rB)
    # 3) run complet (après GO explicite)
    select_tasks.main(n=n)
    run_arm.main("A", Path(cfg_A)); run_arm.main("B", Path(cfg_B))
    rA = grade.resolved_ids(grade.grade(HERE / "preds_A.jsonl", "fullA"))
    rB = grade.resolved_ids(grade.grade(HERE / "preds_B.jsonl", "fullB"))
    return report.main(rA, rB)

if __name__ == "__main__":
    # défaut = smoke (1 tâche) ; passer 'full' pour les N après validation
    smoke = "full" not in sys.argv
    pilot(sys.argv[1], sys.argv[2], smoke=smoke)
```

- [ ] **Step 2: GO/NO-GO réel** — lancer `pilot(cfg_A, cfg_B, smoke=True)` (1 tâche). Attendu : sanity oracle OK, les 2 bras produisent un patch, la notation tourne, un scorecard sort. **Journaliser l'usage/temps consommé** pour extrapoler le coût des 8. Si l'usage d'1 tâche × 16 runs (8×2) risque de dépasser le forfait → réduire N.
- [ ] **Step 3: Décision** — présenter à Ahmed : coût observé sur 1 tâche + extrapolation × N, et **demander le GO explicite** avant le run `full`. (Barrière humaine sur la dépense.)
- [ ] **Step 4: Commit** l'orchestrateur (le run `full` est déclenché à la main d'Ahmed).

---

### Task 6: Rapport de résultats + honnêteté

- [ ] Quand le run `full` est fait : écrire `eval/agent/RESULTS.md` — taux A vs B, gains/régressions de B, coût des 2 bras, et les **honnêtetés** (N faible = directionnel ; mesure la discipline pas la mémoire ; confond coût/qualité). Committer.
- [ ] Mettre à jour l'auto-évaluation : l'axe « validation empirique » passe de 30 (rien mesuré) à un score reflétant qu'on a un **premier A/B réel** (pas encore SOTA, mais plus [PLAUSIBLE] tout nu).
