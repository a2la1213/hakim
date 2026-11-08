"""Debug : POURQUOI le sanity oracle échoue sur task[0]. Montre chaque étape en clair.
ZÉRO budget (aucun claude -p) — juste clone/install/pytest en local."""
import json, subprocess, sys, tempfile, glob, os
from pathlib import Path
from eval.agent import grade_local as G

HERE = Path(__file__).resolve().parent

def run(cmd, cwd=None, timeout=1500):
    return subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout)

print("== Pythons disponibles sur la machine ==")
for pat in ("/usr/local/bin/python3.*", "/opt/homebrew/bin/python3.*", "/usr/bin/python3*"):
    for p in sorted(glob.glob(pat)):
        if "config" not in p:
            v = run([p, "--version"]).stdout.strip() or run([p, "--version"]).stderr.strip()
            print(f"  {p} → {v}")
print(f"  sys.executable (venv anamnèse) → {sys.executable} = Python {sys.version.split()[0]}")
print(f"  → BASE_PYTHON choisi pour les venvs de tâche : {G.BASE_PYTHON}  ({run([G.BASE_PYTHON, '--version']).stdout.strip() or run([G.BASE_PYTHON,'--version']).stderr.strip()})")
print()

task = json.loads(open(HERE / "tasks.jsonl").readline())
print(f"== TASK[0] : {task['instance_id']} | repo {task['repo']} | base {task['base_commit'][:8]} ==")
f2p = G._as_list(task.get("FAIL_TO_PASS"))
print(f"FAIL_TO_PASS ({len(f2p)}): {f2p[:2]}")
print()

with tempfile.TemporaryDirectory() as wd:
    repo = Path(wd) / "repo"
    r = run(["git", "clone", "--quiet", G.REPO_URL.format(repo=task["repo"]), str(repo)], timeout=300)
    print(f"1. clone           rc={r.returncode} {r.stderr[-160:] if r.returncode else 'OK'}")
    r = run(["git", "-C", str(repo), "checkout", "--quiet", task["base_commit"]])
    print(f"2. checkout base   rc={r.returncode} {r.stderr[-160:] if r.returncode else 'OK'}")
    spec = G._spec({**task, "version": task.get("version", "2.0")})
    print(f"3. spec swebench trouvée : {spec is not None}  → python={spec.get('python') if spec else '?'}, {len(spec.get('pip_packages',[])) if spec else 0} deps épinglées")
    venv = Path(wd) / "venv"
    base = G._python_for(spec.get("python", "") if spec else "")
    r = run([base, "-m", "venv", str(venv)])
    print(f"4. venv ({base})   rc={r.returncode}")
    py = str(venv / "bin" / "python")
    env_path = {**os.environ, "PATH": f"{venv / 'bin'}{os.pathsep}{os.environ.get('PATH','')}"}
    r = run([py, "-m", "pip", "install", "-q", "--upgrade", "pip", "setuptools", "wheel"], timeout=300)
    print(f"4-pip. upgrade pip/setuptools/wheel   rc={r.returncode}")
    r = run([py, "-m", "pip", "install", "-q", *(spec.get("pip_packages", []) if spec else [])], timeout=1500)
    print(f"4a. pip install deps épinglées   rc={r.returncode}")
    if r.returncode != 0:
        print("   STDERR:\n   " + "\n   ".join(r.stderr.strip().splitlines()[-10:]))
    import subprocess as _sp
    r = _sp.run(["bash", "-c", spec.get("install", "pip install -e .")] if spec else ["true"],
                cwd=str(repo), env=env_path, capture_output=True, text=True, timeout=1500)
    print(f"4b. install repo   rc={r.returncode}")
    if r.returncode != 0:
        print("   STDERR:\n   " + "\n   ".join(r.stderr.strip().splitlines()[-10:]))
    run([py, "-m", "pip", "install", "-q", "pytest"], timeout=600)
    for ex in ("test", "tests", "dev", "dotenv", "async"):  # extras best-effort (dotenv…)
        run([py, "-m", "pip", "install", "-q", "-e", f".[{ex}]"], cwd=str(repo), timeout=600)
    print("4c. extras de test installés (best-effort)")
    ok1 = G._apply_patch(repo, wd, "gold.patch", task.get("patch", ""))
    print(f"5. apply GOLD patch   applied={ok1}")
    ok2 = G._apply_patch(repo, wd, "test.patch", task.get("test_patch", ""))
    print(f"6. apply test_patch   applied={ok2}")
    targets = f2p + G._as_list(task.get("PASS_TO_PASS"))
    test_files = sorted({t.split("::")[0] for t in targets})
    r = run([py, "-m", "pytest", "-rA", "-o", "addopts=", "--runxfail", "-p", "no:cacheprovider",
             *test_files], cwd=str(repo), timeout=1800)
    print(f"7. pytest -rA sur {len(test_files)} fichier(s) / {len(targets)} cibles   rc={r.returncode}")
    print("   STDOUT tail:\n   " + "\n   ".join((r.stdout or "").strip().splitlines()[-8:]))
    status = G._test_status_map(task, (r.stdout or "") + "\n" + (r.stderr or ""))
    print(f"8. parser swebench : {len(status)} tests parsés")
    try:
        from swebench.harness.constants import TestStatus
        passed = TestStatus.PASSED.value
    except Exception:
        passed = "PASSED"
    manquants = [t for t in targets if t not in status]
    non_passed = [t for t in targets if status.get(t) not in (passed, None)]
    print(f"   cibles NON trouvées dans le parse : {len(manquants)}  (ex: {manquants[:2]})")
    print(f"   cibles trouvées mais PAS PASSED : {len(non_passed)}  (ex: {[(t, status.get(t)) for t in non_passed[:2]]})")
    verdict = bool(status) and all(status.get(t) == passed for t in targets)
    print(f"9. VERDICT notateur (tous targets PASSED) = {verdict}")
