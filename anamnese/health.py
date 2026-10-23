"""Watchdog santé — vérifications LECTURE SEULE, remontées au démarrage de session.

Sans lui, une panne silencieuse (daemon mort, consolidation arrêtée, aucun
backup) peut durer des semaines : personne ne regarde les logs. Le banner est
préfixé à la sortie de wm_boot (mcp_server) — CHAQUE début de session voit
« ✅ consolidation (Sonnet) 6h · rêve daemon 9j » ou « ⚠️ daemon DOWN ».

Deux voies de consolidation, deux signaux DISTINCTS :
- PRIMAIRE  kv['last_consolidation'] — la VRAIE consolidation (consolidate.py,
  Claude Sonnet nightly) qui distille la mémoire durable. Stale >48h => ⚠️.
- SECONDAIRE kv['last_dream'] — le rêve du daemon (Ollama 9B, pensées internes
  uniquement). Peut être mort des jours SANS impact => simple note ℹ️, jamais
  l'alarme en titre. (Avant : le watchdog criait « no consolidation 9d » sur ce
  signal alors que la consolidation Sonnet tournait — fatigue d'alarme.)

Contrat :
- health_report(conn) ne fait AUCUNE écriture (SELECT + pragmas lecture) et
  ne lève JAMAIS : kv absent / DB legacy / launchctl indisponible => champ
  None (« inconnu »), pas d'exception. Un watchdog qui plante au boot serait
  pire que pas de watchdog.
- health_banner(report) : banner humain compact, ⚠️ pour chaque warning,
  ℹ️ pour chaque note (douce, ne passe pas l'icône au ⚠️).
"""

import json
import os
import re
import subprocess
import time
from pathlib import Path

import config
import escalate

# Seuils des warnings (heures).
CONSOLIDATION_MAX_H = 48.0    # PRIMAIRE : consolidation Sonnet stale >48h => ⚠️
DREAM_NOTE_H        = 3 * 24  # SECONDAIRE : rêve daemon stale >3j => note ℹ️ (pas ⚠️)
BACKUP_MAX_H        = 7 * 24  # « no backup >7d »
_CMD_TIMEOUT = 5              # s — launchctl/pgrep ne doivent jamais bloquer le boot

# memory-*.db : sauvegardes manuelles (scripts/backup_memory.py, BACKUP_DIR) ;
# auto-AAAA-MM-JJ.db : sauvegarde quotidienne du démon (data/backups), reconnue depuis le 2026-10-15.
_BACKUP_RE = re.compile(r"^(memory-\d{8}-\d{6}(-\d+)?|auto-\d{4}-\d{2}-\d{2})\.db$")


def _daemon_alive():
    """True/False si déterminable, None sinon (jamais d'exception).

    1) `launchctl list com.anamnese.daemon` : un `"PID" = n;` => vivant.
    2) repli : `pgrep -f <ROOT>/daemon.py` (rc 0 = trouvé, rc 1 = ABSENT —
       seul signal « down » vraiment sûr ; rc >= 2 = pgrep lui-même a échoué).
    """
    launchd_loaded_stopped = False
    try:
        out = subprocess.run(
            ["launchctl", "list", "com.anamnese.daemon"],
            capture_output=True, text=True, timeout=_CMD_TIMEOUT,
        )
        if out.returncode == 0:
            if re.search(r'"PID"\s*=\s*\d+', out.stdout):
                return True
            launchd_loaded_stopped = True  # chargé mais sans PID => pas en cours
    except Exception:
        pass
    try:
        out = subprocess.run(
            ["pgrep", "-f", str(config.ROOT / "daemon.py")],
            capture_output=True, text=True, timeout=_CMD_TIMEOUT,
        )
        if out.returncode == 0 and out.stdout.strip():
            return True
        if out.returncode == 1:
            return False
    except Exception:
        pass
    return False if launchd_loaded_stopped else None


def _kv_get(conn, key):
    """kv[key] ou None — table kv absente (DB legacy) => None, jamais d'exception."""
    try:
        row = conn.execute("SELECT value FROM kv WHERE key = ?", (key,)).fetchone()
        return row[0] if row else None
    except Exception:
        return None


def _kv_ts(conn, key):
    """kv[key] parsé en timestamp float, ou None (valeur absente/pourrie/0)."""
    raw = _kv_get(conn, key)
    if raw is None:
        return None
    try:
        return float(raw) or None
    except (TypeError, ValueError):
        return None


def _age_h(ts, now):
    if ts is None or ts <= 0:
        return None
    return max(0.0, (now - ts) / 3600.0)


def _last_backup(*backup_dirs):
    """(path, mtime) du backup le plus récent parmi backup_dirs, ou (None, None)."""
    best = None
    for backup_dir in backup_dirs:
        try:
            d = Path(backup_dir)
            if not d.is_dir():
                continue
            for p in d.iterdir():
                if _BACKUP_RE.match(p.name):
                    mt = p.stat().st_mtime
                    if best is None or mt > best[1]:
                        best = (str(p), mt)
        except Exception:
            continue
    return best if best else (None, None)


def health_report(conn, now=None, backup_dir=None):
    """Bilan de santé LECTURE SEULE : dict + liste `warnings` (jamais d'exception).

    conn : connexion sqlite3 sur la mémoire (la taille DB vient de son propre
    fichier via PRAGMA database_list). kv/champ manquant => None (« inconnu »),
    et seuls les problèmes PROUVÉS déclenchent un warning.
    """
    if now is None:
        now = time.time()
    if backup_dir is None:  # manuels (BACKUP_DIR) + quotidiens du démon (data/backups)
        backup_dirs = (config.BACKUP_DIR, Path(config.DB_PATH).parent / "backups")
    else:
        backup_dirs = (backup_dir,)
    warnings = []
    notes = []

    # (1) Daemon vivant ?
    try:
        daemon_alive = _daemon_alive()
    except Exception:
        daemon_alive = None
    if daemon_alive is False:
        warnings.append("daemon DOWN (launchd/processus introuvable)")

    # (2) PRIMAIRE — vraie consolidation (Claude Sonnet, consolidate.py) :
    # kv['last_consolidation']. C'est ELLE qui distille la mémoire durable ;
    # sa staleness est la seule qui mérite un ⚠️ en titre.
    last_consolidation_ts = _kv_ts(conn, "last_consolidation")
    # Une nuit SAUTÉE par la porte de consolidate.py (rien de neuf) est un signe de vie.
    skip_ts = _kv_ts(conn, "last_consolidation_skip")
    vie_ts = max((t for t in (last_consolidation_ts, skip_ts) if t is not None), default=None)
    consolidation_age_h = _age_h(vie_ts, now)
    if consolidation_age_h is not None and consolidation_age_h > CONSOLIDATION_MAX_H:
        warnings.append(
            f"pas de consolidation (Sonnet) depuis {_fmt_age(consolidation_age_h)} (>{int(CONSOLIDATION_MAX_H)}h)"
        )

    # (2bis) SECONDAIRE — rêve daemon (Ollama, daemon.py) : kv['last_dream'].
    # Pensées internes seulement : peut être mort des jours sans impact sur la
    # mémoire durable => note ℹ️ douce, JAMAIS l'alarme en titre.
    last_dream_ts = _kv_ts(conn, "last_dream")
    dream_age_h = _age_h(last_dream_ts, now)
    if dream_age_h is not None and dream_age_h > DREAM_NOTE_H:
        notes.append(
            f"rêve de Gemma (secondaire, Ollama) inactif depuis {_fmt_age(dream_age_h)} — "
            "sans impact tant que la consolidation Sonnet tourne"
        )

    # (3) Dernière mise à jour de la MDT — kv['working_memory'].updated_ts.
    wm_updated_ts = None
    raw = _kv_get(conn, "working_memory")
    if raw is not None:
        try:
            wm_updated_ts = float(json.loads(raw).get("updated_ts") or 0.0) or None
        except (TypeError, ValueError, AttributeError, json.JSONDecodeError):
            wm_updated_ts = None
    wm_age_h = _age_h(wm_updated_ts, now)

    # (4) Dernier backup — fichier le plus récent de BACKUP_DIR.
    backup_path, backup_ts = _last_backup(*backup_dirs)
    backup_age_h = _age_h(backup_ts, now)
    if backup_ts is None:
        warnings.append(f"AUCUN backup dans {' ni '.join(str(d) for d in backup_dirs)}")
    elif backup_age_h is not None and backup_age_h > BACKUP_MAX_H:
        warnings.append(
            f"dernier backup vieux de {_fmt_age(backup_age_h)} (>{int(BACKUP_MAX_H / 24)}j)"
        )

    # (5) Taille de la DB (fichier de la connexion elle-même, lecture seule).
    db_size = None
    try:
        for _seq, name, path in conn.execute("PRAGMA database_list"):
            if name == "main" and path:
                db_size = os.path.getsize(path)
                break
    except Exception:
        db_size = None

    # (6) L'identité en base est-elle celle du dernier témoin du journal d'événements (lot E, 2026-10-19) ?
    identite_ok = None
    try:
        import json as _json

        import evenements
        coeur, evo = evenements.reconstruire_identite()
        if coeur is not None:
            kv = dict(conn.execute("SELECT key, value FROM kv WHERE key IN ('self_core','self_evolution')").fetchall())
            identite_ok = kv.get("self_core") == coeur and _json.loads(kv.get("self_evolution") or "[]") == evo
            if not identite_ok:
                warnings.append("identité modifiée hors du journal d'événements (voir : anamnese evenements)")
        ok, n, casse = evenements.verifier()
        if n and not ok:
            warnings.append(f"journal d'événements CASSÉ à partir du n°{casse}")
    except Exception:
        pass

    return {
        "identite_conforme": identite_ok,
        "daemon_alive": daemon_alive,
        "last_consolidation_ts": last_consolidation_ts,   # PRIMAIRE (Sonnet)
        "consolidation_age_h": consolidation_age_h,       # PRIMAIRE (Sonnet)
        "last_dream_ts": last_dream_ts,                   # secondaire (rêve daemon)
        "dream_age_h": dream_age_h,                       # secondaire (rêve daemon)
        "wm_updated_ts": wm_updated_ts,
        "wm_age_h": wm_age_h,
        "last_backup_path": backup_path,
        "last_backup_ts": backup_ts,
        "backup_age_h": backup_age_h,
        "db_size_bytes": db_size,
        "warnings": warnings,
        "notes": notes,
    }


def _fmt_age(hours):
    """Âge humain compact : None -> '?', <1h, Nh (<48h), Nj au-delà."""
    if hours is None:
        return "?"
    if hours < 1.0:
        return "<1h"
    if hours < 48.0:
        return f"{int(round(hours))}h"
    return f"{hours / 24.0:.0f}j"


def _fmt_size(size):
    if size is None:
        return "?"
    if size < 1024 * 1024:
        return f"{size / 1024.0:.0f} Ko"
    return f"{size / (1024.0 * 1024.0):.1f} Mo"


def health_banner(report):
    """Banner humain compact : 1 ligne d'état + 1 ligne ⚠️ par warning + ℹ️ par note.

    Seuls les warnings passent l'icône au ⚠️ ; les notes (ex. rêve daemon
    stale) restent informatives — c'est le cœur de l'anti-fatigue d'alarme.
    """
    warns = report.get("warnings") or []
    notes = report.get("notes") or []
    icon = "⚠️" if warns else "✅"
    daemon = {True: "daemon up", False: "daemon DOWN", None: "daemon ?"}.get(
        report.get("daemon_alive"), "daemon ?"
    )
    parts = [
        daemon,
        "consolidation (Sonnet) " + _fmt_age(report.get("consolidation_age_h")),
        "rêve de Gemma (secondaire) " + _fmt_age(report.get("dream_age_h")),   # (23/10, Ahmed) pas le vrai sommeil
        "MDT " + _fmt_age(report.get("wm_age_h")),
        "backup " + ("aucun" if report.get("last_backup_ts") is None
                     else _fmt_age(report.get("backup_age_h"))),
        "DB " + _fmt_size(report.get("db_size_bytes")),
    ]
    lines = [f"{icon} santé : " + " · ".join(parts)]
    lines.extend(f"⚠️ {w}" for w in warns)
    lines.extend(f"ℹ️ {n}" for n in notes)
    # Escalade proactive (best-effort) : là où le bilan est réellement produit,
    # un warning déclenche notif + brief SDD (dédup). Garde anti-effet-de-bord :
    # JAMAIS sous pytest (les tests santé forgent des warnings sans arrêt), et un
    # échec d'escalade ne casse JAMAIS le banner (un watchdog qui plante = pire).
    if warns and not os.environ.get("PYTEST_CURRENT_TEST"):
        try:
            escalate.escalate(report, brief_dir=Path(__file__).resolve().parent / "data" / "escalations")
        except Exception:
            pass
    return "\n".join(lines)
