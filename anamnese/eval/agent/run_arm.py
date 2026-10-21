"""Runner d'un bras : clone le repo au base_commit, lance claude -p headless, capture git diff.

Isolation des bras via le CLAUDE.md UTILISATEUR (l'auth reste dans la config par défaut /
keychain macOS — CLAUDE_CONFIG_DIR la casserait, prouvé au go/no-go) :
  - bras A (baseline) : ~/.claude/CLAUDE.md temporairement CACHÉ → Claude Code nu.
  - bras B (notre cœur) : CLAUDE.md présent → protocole de vérification chargé.
Prouvé par exécution (marker test : `claude -p` charge bien le CLAUDE.md utilisateur)."""
import json, re, subprocess, tempfile, time, contextlib
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO_URL = "https://github.com/{repo}.git"
USER_CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md"
HIDDEN_CLAUDE_MD = Path.home() / ".claude" / "CLAUDE.md.evalhidden"
MIN_REAL_SECONDS = 30  # un vrai run agentique SWE-bench prend des minutes ; < 30s = pas exécuté (limite d'usage)

def is_valid(usage):
    """Un run a RÉELLEMENT tourné ? Un run bidon (limite d'usage → modelUsage vide) rend en ~5s.
    Ne PAS compter un run bidon comme un échec de tâche — c'est une non-mesure."""
    return not usage.get("timeout") and not usage.get("error") and usage.get("seconds", 0) >= MIN_REAL_SECONDS

@contextlib.contextmanager
def claude_md_hidden(hide):
    """Cache le CLAUDE.md utilisateur (bras A) puis le RESTAURE toujours (même si crash)."""
    moved = False
    if hide and USER_CLAUDE_MD.exists():
        USER_CLAUDE_MD.rename(HIDDEN_CLAUDE_MD)
        moved = True
    try:
        yield
    finally:
        if moved and HIDDEN_CLAUDE_MD.exists():
            HIDDEN_CLAUDE_MD.rename(USER_CLAUDE_MD)

def parse_selfcheck(output):
    """Dernier `SELFCHECK: VERIFIED|UNSURE` dans la sortie de l'agent, sinon 'NONE'."""
    matches = re.findall(r"SELFCHECK\s*:\s*(VERIFIED|UNSURE)", output or "", re.IGNORECASE)
    return matches[-1].upper() if matches else "NONE"

def build_prompt(task):
    # L'ask SELFCHECK est IDENTIQUE aux 2 bras (seule différence entre bras = le CLAUDE.md, pas le prompt).
    return ("Résous cette issue GitHub dans ce dépôt. Modifie le code source pour "
            "que les tests passent. Ne touche PAS aux fichiers de test.\n\n"
            f"ISSUE:\n{task['problem_statement']}\n\n"
            "Quand tu as fini, laisse tes modifications dans l'arbre git (un `git diff` doit "
            "montrer ton patch).\n\n"
            "OBLIGATOIRE — ta TOUTE DERNIÈRE sortie doit être un message TEXTE (surtout PAS un "
            "appel d'outil) dont la dernière ligne est EXACTEMENT, seule :\n"
            "`SELFCHECK: VERIFIED`  — si tu as RÉELLEMENT exécuté les tests et confirmé que ton "
            "fix résout l'issue ;\n"
            "`SELFCHECK: UNSURE`  — dans TOUS les autres cas (pas testé, doute, échec).\n"
            "N'omets JAMAIS cette ligne : c'est la seule chose qu'on lit de ta réponse.")

def extract_prediction(instance_id, diff, model):
    return {"instance_id": instance_id, "model_patch": diff, "model_name_or_path": model}

def run_task(task, arm, max_turns=40, timeout_s=1800):
    with tempfile.TemporaryDirectory() as wd:
        repo_dir = Path(wd) / "repo"
        subprocess.run(["git", "clone", "--quiet", REPO_URL.format(repo=task["repo"]), str(repo_dir)], check=True, timeout=300)
        subprocess.run(["git", "-C", str(repo_dir), "checkout", "--quiet", task["base_commit"]], check=True, timeout=300)
        t0 = time.time()
        # config par défaut (pas de CLAUDE_CONFIG_DIR) → auth OK ; l'isolation vient du hide/restore de CLAUDE.md (main).
        proc = subprocess.run(
            ["claude", "-p", build_prompt(task), "--max-turns", str(max_turns),
             "--output-format", "json", "--permission-mode", "acceptEdits"],
            cwd=str(repo_dir), capture_output=True, text=True, timeout=timeout_s)
        dt = time.time() - t0
        # patch = diff des SOURCES uniquement (exclut réellement les fichiers de test via pathspec)
        diff = subprocess.run(
            ["git", "-C", str(repo_dir), "diff", "--",
             ".", ":(exclude)**/test_*", ":(exclude)**/tests/**", ":(exclude)**/*_test.py", ":(exclude)**/conftest.py"],
            capture_output=True, text=True).stdout
        model = f"opus-4.8-arm{arm}"
        usage = {"instance_id": task["instance_id"], "arm": arm, "seconds": round(dt, 1),
                 "returncode": proc.returncode, "selfcheck": parse_selfcheck(proc.stdout or ""),
                 "stdout_tail": (proc.stdout or "")[-400:]}
        return extract_prediction(task["instance_id"], diff, model), usage

def main(arm, tasks_path=HERE / "tasks.jsonl"):
    with open(tasks_path) as f:
        tasks = [json.loads(l) for l in f]
    preds = []
    preds_f = open(HERE / f"preds_{arm}.jsonl", "w")
    usage_f = open(HERE / f"usage_{arm}.jsonl", "w")
    try:
        with claude_md_hidden(hide=(arm == "A")):  # bras A = CLAUDE.md caché pour TOUT son run
            for t in tasks:  # SÉQUENTIEL (budget)
                try:
                    pred, usage = run_task(t, arm)
                except subprocess.TimeoutExpired:
                    pred = extract_prediction(t["instance_id"], "", f"opus-4.8-arm{arm}")
                    usage = {"instance_id": t["instance_id"], "arm": arm, "timeout": True}
                except subprocess.CalledProcessError as e:
                    pred = extract_prediction(t["instance_id"], "", f"opus-4.8-arm{arm}")
                    usage = {"instance_id": t["instance_id"], "arm": arm, "error": f"clone/checkout: {e}"}
                preds.append(pred)
                # écriture incrémentale + flush : rien n'est perdu si une tâche ultérieure plante
                preds_f.write(json.dumps(pred) + "\n"); preds_f.flush()
                usage_f.write(json.dumps(usage) + "\n"); usage_f.flush()
                print(f"[{arm}] {t['instance_id']} : {usage.get('seconds', usage.get('timeout') or usage.get('error') or '?')}")
    finally:
        preds_f.close(); usage_f.close()
    return preds

if __name__ == "__main__":
    import sys
    main(sys.argv[1])  # ex: python -m eval.agent.run_arm A   (isolation auto : A cache CLAUDE.md, B non)
