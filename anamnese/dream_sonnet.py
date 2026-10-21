"""Replay budget de la cellule sonnet (main d'Ahmed). Rejoue les menus loggés par
qwen à travers `claude -p --model sonnet`, MÊME prompt que qwen → paires appariées.
Batchable ; testé avec run_fn injectée (aucun claude au build). Aucune écriture
mémoire : dream_log seulement."""
import argparse
import json
import subprocess
import sys

import dream_lab


def build_sonnet_prompt(seed_state, menu):
    """MÊME gabarit que qwen (seul le modèle change)."""
    return dream_lab.prompt_rem(dream_lab.state_block(seed_state), menu)


def claude_sonnet(prompt, timeout=300):
    """Exécution réelle (budget). Rêve = pur texte : aucun outil autorisé."""
    try:
        r = subprocess.run(
            ["claude", "-p", prompt, "--model", "sonnet", "--max-turns", "2",
             "--allowedTools", ""],
            capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        print("[dream_sonnet] claude échoué:", e)
        return None


def pending_pairs(conn, condition, limit=10):
    """Nuits qwen loggées pour `condition` PAS encore rejouées par sonnet.
    'qwen' = dreamer 'local' ; condition depuis meta (absent = brain_on)."""
    rows = conn.execute(
        "SELECT night_id, seed_state, menu, meta FROM dream_log WHERE dreamer='local' "
        "AND menu IS NOT NULL ORDER BY ts").fetchall()
    done = set()
    for night_id, meta in conn.execute(
            "SELECT night_id, meta FROM dream_log WHERE dreamer='sonnet'").fetchall():
        m = json.loads(meta) if meta else {}
        done.add((night_id, m.get("condition", "brain_on")))
    out = []
    for night_id, seed_state, menu, meta in rows:
        cond = (json.loads(meta) if meta else {}).get("condition", "brain_on")
        if cond != condition or (night_id, condition) in done:
            continue
        if any(p["night_id"] == night_id for p in out):
            continue                                         # une paire par nuit calendaire
        out.append({"night_id": night_id,
                    "seed_state": json.loads(seed_state) if seed_state else {},
                    "menu": json.loads(menu) if menu else []})
        if len(out) >= limit:
            break
    return out


def replay_pair(conn, item, condition, run_fn=None):
    """Rejoue une paire via sonnet, logue dream_log. run_fn injectable (test)."""
    run_fn = run_fn or claude_sonnet
    if not item.get("menu"):
        return False
    out = run_fn(build_sonnet_prompt(item["seed_state"], item["menu"]))
    if out is None:
        return False
    chosen = dream_lab.parse_choice(out, item["menu"])

    class _Wrap:                                             # log_night attend mem.db + mem.db.commit
        def __init__(self, c): self.db = c
    dream_lab.log_night(_Wrap(conn), item["night_id"], "sonnet", item["seed_state"],
                        item["menu"], chosen, out, written=False,
                        meta={"condition": condition, "source": "replay",
                              "parse": "ok" if chosen is not None else "parse_failed"})
    return True


def build_free_prompt(seed_state):
    """Prompt de rêve LIBRE sonnet (aucun menu) — même gabarit que qwen free."""
    return dream_lab.prompt_rem_free(dream_lab.state_block(seed_state))


def pending_free(conn, limit=10):
    """Nuits qwen loggées PAS encore rêvées en libre par sonnet (une par night_id calendaire)."""
    rows = conn.execute("SELECT night_id, seed_state FROM dream_log WHERE dreamer='local' "
                        "ORDER BY ts").fetchall()
    done = set()
    for night_id, meta in conn.execute(
            "SELECT night_id, meta FROM dream_log WHERE dreamer='sonnet'").fetchall():
        m = json.loads(meta) if meta else {}
        if m.get("condition") == "brain_off_free":
            done.add(night_id)
    out, seen = [], set()
    for night_id, seed_state in rows:
        if night_id in done or night_id in seen:
            continue
        seen.add(night_id)
        out.append({"night_id": night_id,
                    "seed_state": json.loads(seed_state) if seed_state else {}})
        if len(out) >= limit:
            break
    return out


def free_pair(conn, item, run_fn=None):
    """Rêve libre sonnet pour une nuit, log dream_log. run_fn injectable (test)."""
    run_fn = run_fn or claude_sonnet
    out = run_fn(build_free_prompt(item["seed_state"]))
    if out is None:
        return False

    class _Wrap:
        def __init__(self, c): self.db = c
    dream_lab.log_night(_Wrap(conn), item["night_id"], "sonnet", item["seed_state"],
                        None, None, out, written=False,
                        meta={"condition": "brain_off_free", "source": "free", "parse": "ok"})
    return True


def main(nights, condition, run_fn=None):
    import sqlite3
    import config
    conn = sqlite3.connect(str(config.DB_PATH))            # config.DB_PATH = DATA_DIR/"memory.db"
    try:
        if condition == "brain_off_free":
            pend = pending_free(conn, limit=nights)
            n = sum(1 for it in pend if free_pair(conn, it, run_fn=run_fn))
            print(f"[dream_sonnet] {n}/{len(pend)} rêve(s) libre(s) sonnet")
            return
        pend = pending_pairs(conn, condition, limit=nights)
        n = sum(1 for it in pend if replay_pair(conn, it, condition, run_fn=run_fn))
        print(f"[dream_sonnet] {n}/{len(pend)} paire(s) {condition} rejouée(s)")
    finally:
        conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--nights", type=int, default=5)
    ap.add_argument("--condition", choices=["brain_on", "brain_off", "brain_off_free"],
                    default="brain_on")
    a = ap.parse_args()
    main(a.nights, a.condition)
