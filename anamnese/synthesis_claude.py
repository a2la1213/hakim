"""Étage CLAUDE du moteur de liens génératifs (budget, main d'Ahmed). Réutilise le
cœur synthesis.run avec claude -p comme backend, sur le TOP des paires (Claude = juge
fort → moins d'échantillons/sceptiques). Testé chat_fn mockée : zéro claude au build."""
import os
import shutil
import subprocess

import config
import synthesis
import rubric_emergence


def _claude_bin():
    """Résout le binaire claude de façon robuste (le daemon launchd n'a pas ~/.npm-global
    dans son PATH). shutil.which d'abord, puis les emplacements usuels, sans chemin codé en dur."""
    return (shutil.which("claude")
            or next((p for p in (os.path.expanduser("~/.npm-global/bin/claude"),
                                 "/usr/local/bin/claude", "/opt/homebrew/bin/claude")
                     if os.path.exists(p)), "claude"))


def claude_chat(prompt, timeout=300):
    """Backend Claude : un appel claude -p headless (sonnet), pur texte (aucun outil)."""
    try:
        # ANAMNESE_HEADLESS : le hook SessionStart (anamnese outreach) n'amorce pas la mémoire de
        # travail pour une exécution sans interface (relecture 2026-10-16).
        r = subprocess.run([_claude_bin(), "-p", prompt, "--model", "sonnet", "--max-turns", "2",
                            "--allowedTools", ""], capture_output=True, text=True, timeout=timeout,
                           env={**os.environ, "ANAMNESE_HEADLESS": "1"})
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        print("[synthese-claude] claude échoué:", e)
        return None


def run_claude(mem, run_fn=None):
    """Synthèse via Claude sur le top-N des paires fertiles, PUIS émergence de rubriques
    (Claude seul, gardée). run_fn injectable (test). Retourne les insight_ids créés."""
    chat = run_fn or claude_chat
    ids = synthesis.run(mem, chat, "claude", config.SYNTH_CLAUDE_TOPN,
                        n_samples=1, n_skeptics=2)
    try:
        rubric_emergence.emerge(mem, chat)   # crée des rubriques si des insights font thème neuf
    except Exception as e:
        print("[synthese-claude] émergence échouée:", e)
    return ids


if __name__ == "__main__":
    import sqlite3
    import memory
    m = memory.Memory()
    ids = run_claude(m)
    print(f"[synthese-claude] {len(ids)} lien(s) génératif(s) créé(s)")
