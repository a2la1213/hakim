"""Après `.venv/bin/pip install swebench` : dump la SPEC d'environnement swebench de la
1re tâche (deps ÉPINGLÉES) → me montre comment installer le repo correctement (fix ImportError).
ZÉRO budget. Robuste à plusieurs versions de l'API swebench."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent

task = json.loads(open(HERE / "tasks.jsonl").readline())
repo = task["repo"]
version = task.get("version")
if version is None:  # tasks.jsonl généré avant l'ajout du champ version → relire le dataset
    from datasets import load_dataset
    ds = load_dataset("princeton-nlp/SWE-bench_Lite", split="test")
    version = next(r["version"] for r in ds if r["instance_id"] == task["instance_id"])
print(f"repo={repo} | version={version} | instance={task['instance_id']}")

import swebench
print("swebench:", getattr(swebench, "__version__", "?"))

# la table des specs peut vivre à différents chemins selon la version
specs_map = None
for modpath, attr in [("swebench.harness.constants", "MAP_REPO_VERSION_TO_SPECS"),
                      ("swebench.harness.constants.constants", "MAP_REPO_VERSION_TO_SPECS"),
                      ("swebench.harness.constants.python", "MAP_REPO_VERSION_TO_SPECS")]:
    try:
        mod = __import__(modpath, fromlist=[attr])
        specs_map = getattr(mod, attr)
        print(f"specs trouvées dans {modpath}.{attr}")
        break
    except Exception as e:
        print(f"  (pas dans {modpath}: {type(e).__name__})")

if specs_map is not None:
    spec = specs_map.get(repo, {}).get(version) or specs_map.get(repo, {}).get(str(version))
    print("── SPEC (repo, version) ──")
    print(json.dumps(spec, indent=2, default=str))

# essai complémentaire : make_test_spec (donne les scripts d'install/eval complets)
try:
    from swebench.harness.test_spec import make_test_spec
    row = {**task, "version": version}
    ts = make_test_spec(row)
    print("── make_test_spec : attributs ──")
    for a in ("setup_env_script", "install_repo_script", "eval_script", "test_cmd"):
        v = getattr(ts, a, None)
        if v:
            print(f"\n=== {a} ===\n{v[:1500] if isinstance(v, str) else v}")
except Exception as e:
    print(f"(make_test_spec indisponible : {type(e).__name__}: {e})")
