"""Anamnèse — escalade proactive : quand le watchdog santé détecte un outil
tombé (daemon down, consolidation stale, backup manquant…), ÉMETTRE une
notification + écrire un brief de diagnostic (format SDD) que l'humain lance
en 1 clic. On ÉMET, on ne RÉPARE pas (humain dans la boucle — pas d'agent qui
réécrit ses propres outils : ça contredirait les review-gates).

Contrat : `escalate(report, brief_dir)` consomme la forme RÉELLE de
`health.health_report` = {"warnings": [<str>...], "notes": [...]}. Seuls les
`warnings` escaladent (actionnables) ; les `notes` (ex. rêve daemon stale) sont
douces, jamais. Dédup par fichier marqueur (`brief_dir/.escalated/<hash>`) :
un même problème ne re-notifie/re-brief pas. BEST-EFFORT ABSOLU : un watchdog
qui plante serait pire que rien → aucune exception ne remonte, jamais.
"""
import hashlib
import re
import subprocess
import time
from pathlib import Path

# Dédup à FENÊTRE, pas permanente : un même problème ne re-notifie pas pendant
# DEDUP_TTL_H, mais RÉCIDIVE au-delà (sinon un warning statique comme "daemon
# DOWN" resté muet à jamais — inacceptable pour un watchdog).
DEDUP_TTL_H = 24.0


def notify(title, message):
    """Notification macOS native (osascript). Best-effort : ne lève jamais.
    Répliqué de daemon.notify pour ne pas importer daemon (effets de bord)."""
    def q(s):
        return '"' + str(s).replace("\\", "\\\\").replace('"', '\\"') + '"'
    try:
        subprocess.run(
            ["osascript", "-e", f"display notification {q(message)} with title {q(title)}"],
            check=False, timeout=10,
        )
    except Exception:
        pass


def _brief_body(warning):
    """Brief de diagnostic au format SDD : contexte, symptôme, diagnostic, lancement 1 clic."""
    return (
        "# Escalade santé — outil à vérifier\n\n"
        "- **Statut** : détecté automatiquement par le watchdog (health.py), "
        "NON réparé — action humaine requise (l'escalade émet, ne répare pas).\n\n"
        "## Symptôme\n"
        f"{warning}\n\n"
        "## Diagnostic suggéré\n"
        "- État global : `./anamnese wm-boot` (banner santé) ou `python health.py`.\n"
        "- Daemon down : `launchctl list | grep anamnese` puis "
        "`launchctl kickstart -k gui/$(id -u)/com.anamnese.daemon`.\n"
        "- Consolidation stale : consulter `data/consolidate.log` ; relancer "
        "`python consolidate.py`.\n"
        "- Backup manquant/vieux : `python scripts/backup_memory.py`.\n"
        "- MCP en needs-auth : ré-authentifier via `claude mcp` (ou `/mcp` en session).\n\n"
        "## Lancer la réparation (1 clic)\n"
        f"Ouvre ce brief dans Claude Code et demande : « diagnostique et répare : {warning} ».\n"
    )


def escalate(report, brief_dir):
    """Escalade les warnings actionnables de `report`. Retourne
    {"notified": bool, "brief_path": str|None}. BEST-EFFORT : jamais d'exception.

    Dédup : un warning déjà escaladé (marqueur présent) ne re-notifie/re-brief pas.
    """
    result = {"notified": False, "brief_path": None}
    try:
        if not isinstance(report, dict):
            return result
        warnings = report.get("warnings")
        if not isinstance(warnings, list):
            return result
        actionable = [w for w in warnings if isinstance(w, str) and w.strip()]
        if not actionable:
            return result

        bdir = Path(brief_dir)
        marker_dir = bdir / ".escalated"
        marker_dir.mkdir(parents=True, exist_ok=True)   # brief_dir = fichier → OSError → capté

        first_brief = None
        for w in actionable:
            h = hashlib.sha1(w.encode("utf-8")).hexdigest()[:12]
            marker = marker_dir / h
            if marker.exists():
                try:                                     # dédup À FENÊTRE : muet si récent, récidive au-delà
                    fresh = (time.time() - marker.stat().st_mtime) < DEDUP_TTL_H * 3600
                except Exception:
                    fresh = True                         # marqueur illisible → prudence : ne pas spammer
                if fresh:
                    continue
            slug = re.sub(r"[^a-z0-9]+", "-", w.lower())[:40].strip("-") or "warning"
            brief_path = bdir / f"escalade-{h}-{slug}.md"
            brief_path.write_text(_brief_body(w), encoding="utf-8")
            marker.write_text(str(time.time()), encoding="utf-8")  # marqueur APRÈS le brief
            try:
                notify("Anamnèse — outil à vérifier", w)
            except Exception:
                pass                                     # notif KO ne downgrade pas un brief réussi
            result["notified"] = True
            if first_brief is None:
                first_brief = str(brief_path)
        result["brief_path"] = first_brief
        return result
    except Exception:
        return {"notified": False, "brief_path": None}
