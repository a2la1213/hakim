"""Dump l'API de parsing de logs de swebench → comment obtenir le pass/fail par test node-id
(gère les IDs paramétrés) sans Docker. ZÉRO budget (pas de clone, pas de claude)."""
import json, inspect
from pathlib import Path
HERE = Path(__file__).resolve().parent
task = json.loads(open(HERE / "tasks.jsonl").readline())
repo, version = task["repo"], task.get("version")
print(f"repo={repo} version={version}\n")

# 1) la table repo -> parser de logs
found = None
for modpath, attr in [
    ("swebench.harness.log_parsers", "MAP_REPO_TO_PARSER"),
    ("swebench.harness.log_parsers.python", "MAP_REPO_TO_PARSER"),
    ("swebench.harness.log_parsers", "MAP_REPO_VERSION_TO_PARSER"),
    ("swebench.harness.constants", "MAP_REPO_TO_PARSER"),
]:
    try:
        mod = __import__(modpath, fromlist=[attr])
        m = getattr(mod, attr)
        print(f"✓ trouvé {modpath}.{attr} — flask présent ? {repo in m}")
        parser = m.get(repo)
        print(f"  parser({repo}) = {parser}")
        if callable(parser):
            print(f"  signature = {inspect.signature(parser)}")
            print(f"  docstring = {(parser.__doc__ or '')[:300]}")
        found = (modpath, attr, parser)
        break
    except Exception as e:
        print(f"  (pas dans {modpath}.{attr} : {type(e).__name__})")

# 2) exports du module log_parsers (voir les fonctions parse_log_*, le statut PASSED/FAILED)
try:
    import swebench.harness.log_parsers as lp
    print("\nlog_parsers exports:", [x for x in dir(lp) if not x.startswith("_")][:40])
    if hasattr(lp, "TestStatus"):
        print("  TestStatus:", [s for s in dir(lp.TestStatus) if not s.startswith("_")])
except Exception as e:
    print("\nlog_parsers:", type(e).__name__, e)

# 3) fonctions de grading haut niveau
try:
    import swebench.harness.grading as gr
    print("\ngrading exports:", [x for x in dir(gr) if not x.startswith("_")][:40])
except Exception as e:
    print("\ngrading:", type(e).__name__, e)

# 4) le test_cmd de la spec (comment lancer les tests pour ce repo)
try:
    from swebench.harness.constants import MAP_REPO_VERSION_TO_SPECS
    spec = MAP_REPO_VERSION_TO_SPECS.get(repo, {}).get(version) or MAP_REPO_VERSION_TO_SPECS.get(repo, {}).get(str(version))
    print("\ntest_cmd de la spec:", spec.get("test_cmd") if spec else "?")
except Exception as e:
    print("\nspec test_cmd:", e)
