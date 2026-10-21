"""Notateur CONTAINER-FREE (zéro Docker) pour repos pytest légers.

Pour chaque prédiction : clone le repo au base_commit dans un dossier jetable, crée un venv,
installe le repo (editable) + pytest, applique le model_patch (fix de l'agent) PUIS le
test_patch (gold — définit FAIL_TO_PASS/PASS_TO_PASS) en dernier, et lance pytest sur les
tests cibles. resolved = CHAQUE test cible a réellement PASSÉ (statut par test via junit XML :
aucun skipped/failure/error) — pas seulement returncode==0, qui compterait un test
SKIPPED/DESELECTED/XFAIL comme résolu (faux positif).

FILET DE SÛRETÉ : `sanity_oracle` note le GOLD patch → doit être resolved. Si ce notateur
maison a un défaut (mauvaise version de dep, patch qui n'applique pas), le gold ne passera pas
et le go/no-go STOP avant qu'on croie le moindre chiffre. Interface identique à grade.py
(grade / resolved_ids / sanity_oracle) → run_pilot swap juste l'import.

Honnêteté : plus léger mais moins blindé que le harnais Docker officiel (pas d'env conda à
deps épinglées) ; le sanity oracle par tâche est ce qui rend le chiffre digne de confiance."""
import json, subprocess, sys, tempfile, shutil, os
import xml.etree.ElementTree as ET
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_URL = "https://github.com/{repo}.git"

def _spec(task):
    """Spec d'environnement swebench (deps ÉPINGLÉES d'époque) pour la tâche, ou None.
    Import LAZY : ne casse pas l'import de ce module quand swebench n'est pas installé
    (tests des fonctions pures). Nécessite `pip install swebench` pour la notation réelle."""
    try:
        from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    except Exception:
        return None
    m = MAP_REPO_VERSION_TO_SPECS.get(task.get("repo"), {})
    v = task.get("version")
    return m.get(v) or m.get(str(v))

def _python_for(pyver):
    """Interpréteur pour la version demandée par la spec (ex '3.9'), sinon BASE_PYTHON."""
    if pyver:
        p = shutil.which(f"python{pyver}")
        if p:
            return p
        if str(pyver).startswith("3.9") and Path("/usr/bin/python3").exists():
            return "/usr/bin/python3"
    return BASE_PYTHON

def _base_python():
    """Python ADAPTÉ aux repos SWE-bench (3.9–3.11) pour le venv de chaque tâche.
    PAS le 3.14 du venv anamnèse : pytest 7.x + les vieux repos crashent sur 3.14 (pytest exit 4).
    Ordre de préférence : 3.11 → 3.10 → 3.9 → /usr/bin/python3 (souvent 3.9 sur macOS)."""
    for cand in ("python3.11", "python3.10", "python3.9"):
        p = shutil.which(cand)
        if p:
            return p
    if Path("/usr/bin/python3").exists():
        return "/usr/bin/python3"
    return sys.executable

BASE_PYTHON = _base_python()

def _run(cmd, cwd=None, timeout=1200):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

def _as_list(v):
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        try:
            parsed = json.loads(v)
        except Exception:
            return [v] if v.strip() else []
        # garde de type : un scalaire JSON (str/int/…) n'est pas une liste de cibles → []
        return parsed if isinstance(parsed, list) else []
    return []

def _all_passed(xml_path):
    """PURE : True SSI le junit XML contient ≥1 <testcase> et aucun n'a d'enfant
    <failure>/<error>/<skipped> (un test réellement PASSÉ n'a aucun de ces enfants).
    Robuste : fichier absent/vide/illisible → False."""
    p = Path(xml_path)
    if not p.exists() or p.stat().st_size == 0:
        return False
    try:
        root = ET.parse(str(p)).getroot()
    except Exception:
        return False
    n = 0
    for c in root.iter("testcase"):
        n += 1
        for child in c:
            if child.tag in ("failure", "error", "skipped"):
                return False
    return n > 0

def _apply_patch(repo, wd, name, patch):
    """Applique un patch dans le repo (git apply, fallback three-way). Retourne True si vide/appliqué."""
    if not patch or not patch.strip():
        return True
    pf = Path(wd) / name
    pf.write_text(patch if patch.endswith("\n") else patch + "\n")
    r = _run(["git", "-C", str(repo), "apply", "--verbose", str(pf)], timeout=120)
    if r.returncode == 0:
        return True
    r2 = _run(["git", "-C", str(repo), "apply", "--3way", str(pf)], timeout=120)
    return r2.returncode == 0

def _make_test_spec(task):
    """Construit un TestSpec swebench (2e arg du parser). None si indisponible."""
    for modpath in ("swebench.harness.test_spec.test_spec", "swebench.harness.test_spec"):
        try:
            mod = __import__(modpath, fromlist=["make_test_spec"])
            return mod.make_test_spec(task)
        except Exception:
            continue
    return None

def _test_status_map(task, log):
    """Parse le log pytest via le parser OFFICIEL de swebench → {node_id: status}.
    Robuste : parser absent → {} ; signature à 1 ou 2 args tolérée."""
    try:
        from swebench.harness.log_parsers import MAP_REPO_TO_PARSER
    except Exception:
        return {}
    parser = MAP_REPO_TO_PARSER.get(task.get("repo"))
    if parser is None:
        return {}
    try:
        return parser(log, _make_test_spec(task))
    except TypeError:
        try:
            return parser(log)  # anciennes signatures à 1 argument
        except Exception:
            return {}
    except Exception:
        return {}

def resolve_task(task, model_patch, timeout=1800):
    """True si model_patch résout la tâche : FAIL_TO_PASS + PASS_TO_PASS tous verts."""
    # exiger ≥1 FAIL_TO_PASS : sinon un patch qui ne fait que garder des PASS_TO_PASS verts
    # (sans jamais corriger un test cassé) serait noté « résolu » à tort.
    if not _as_list(task.get("FAIL_TO_PASS")):
        return False
    targets = _as_list(task.get("FAIL_TO_PASS")) + _as_list(task.get("PASS_TO_PASS"))
    if not targets:
        return False
    with tempfile.TemporaryDirectory() as wd:
        repo = Path(wd) / "repo"
        if _run(["git", "clone", "--quiet", REPO_URL.format(repo=task["repo"]), str(repo)], timeout=300).returncode != 0:
            return False
        if _run(["git", "-C", str(repo), "checkout", "--quiet", task["base_commit"]], timeout=120).returncode != 0:
            return False
        spec = _spec(task)
        if spec is None:
            return False  # sans spec swebench, on ne sait pas installer les deps d'époque de façon fiable
        venv = Path(wd) / "venv"
        _run([_python_for(spec.get("python", "")), "-m", "venv", str(venv)], timeout=120)
        py = str(venv / "bin" / "python")
        env_path = {**os.environ, "PATH": f"{venv / 'bin'}{os.pathsep}{os.environ.get('PATH', '')}"}
        # 0) pip récent : le pip du venv 3.9 (21.x) ne sait pas installer un projet pyproject.toml-seul
        #    en éditable (PEP 660). On upgrade AVANT (la spec re-pinnera setuptools ensuite si besoin).
        _run([py, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools", "wheel"], timeout=300)
        # 1) deps ÉPINGLÉES d'époque (fournies par swebench) — c'est ce qui règle les ImportError de version
        pip_pkgs = spec.get("pip_packages") or []
        if pip_pkgs and _run([py, "-m", "pip", "install", "-q", *pip_pkgs], timeout=1500).returncode != 0:
            return False
        # 2) commande d'install de la spec (ex "python -m pip install -e ."), venv sur le PATH
        install_cmd = spec.get("install")
        if install_cmd and subprocess.run(["bash", "-c", install_cmd], cwd=str(repo), env=env_path,
                                          capture_output=True, text=True, timeout=1500).returncode != 0:
            return False
        # 3) pytest pour lancer les tests cibles
        if _run([py, "-m", "pip", "install", "-q", "pytest"], timeout=600).returncode != 0:
            return False
        # 3b) extras de test best-effort (dotenv, async…) : sinon des PASS_TO_PASS SKIP faute de dep
        #     optionnelle. pip (only-if-needed) ne casse pas les pins ; les extras absents échouent en silence.
        for ex in ("test", "tests", "dev", "dotenv", "async"):
            _run([py, "-m", "pip", "install", "-q", "-e", f".[{ex}]"], cwd=str(repo), timeout=600)
        # ORDRE OFFICIEL : fix agent (model_patch) D'ABORD, gold tests (test_patch) EN DERNIER
        # → le modèle ne peut pas altérer les tests notés.
        if not _apply_patch(repo, wd, "model.patch", model_patch or ""):
            return False  # le patch de l'agent ne s'applique pas → non résolu
        if not _apply_patch(repo, wd, "test.patch", task.get("test_patch", "")):
            return False
        # note via le PARSER OFFICIEL de swebench (gère les node-ids paramétrés à caractères
        # spéciaux que pytest ne matche pas en argument). On lance -rA sur les FICHIERS de test,
        # puis on parse le log, puis on exige que tous les targets soient PASSED.
        test_files = sorted({t.split("::")[0] for t in targets})
        r = _run([py, "-m", "pytest", "-rA", "-o", "addopts=", "--runxfail", "-p", "no:cacheprovider",
                  *test_files], cwd=str(repo), timeout=timeout)
        status = _test_status_map(task, (r.stdout or "") + "\n" + (r.stderr or ""))
        try:
            from swebench.harness.constants import TestStatus
            passed = TestStatus.PASSED.value
        except Exception:
            passed = "PASSED"
        return bool(status) and all(status.get(t) == passed for t in targets)

def grade(preds_path, run_id=None, tasks_path=HERE / "tasks.jsonl"):
    """Note toutes les prédictions d'un bras → {"resolved_ids": [...]}. Interface = grade.py."""
    with open(tasks_path) as f:
        tasks = {json.loads(l)["instance_id"]: json.loads(l) for l in f if l.strip()}
    resolved = []
    with open(preds_path) as f:
        for line in f:
            if not line.strip():
                continue
            pred = json.loads(line)
            t = tasks.get(pred["instance_id"])
            if t and (pred.get("model_patch") or "").strip() and resolve_task(t, pred["model_patch"]):
                resolved.append(pred["instance_id"])
    return {"resolved_ids": resolved}

def resolved_ids(report):
    return set(report.get("resolved_ids", []) or report.get("resolved", []))

def sanity_oracle(task):
    """Applique le GOLD patch (task['patch']) → DOIT être resolved. Valide ce notateur."""
    return resolve_task(task, task.get("patch", ""))
