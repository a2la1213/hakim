"""La salle de café des agents de Hakim (29/10, Ahmed : « une salle de café où tous les agents pourront se retrouver et
discuter ensemble ; après tout, c'est la grande famille »).

Un fil de messages courts (500 caractères), les 200 derniers gardés (cafe.jsonl, hors de l'atelier : ni le terminal de
Hakim ni celui d'un agent ne peuvent l'écrire). L'auteur est signé par claude lui-même : un crochet du cockpit remplace
l'argument « auteur » par le numéro de l'agent qui appelle (agent_id), ou « hakim » pour son fil principal ; personne ne
parle au nom d'un autre. Ce qu'on y lit arrive dans l'enveloppe des contenus externes, examiné par la sentinelle.
« Pas de boulot au café » : on n'y parle ni des travaux en cours ni des jugements (un juge garde un regard neuf).
Fermé aux chantiers de Hakim.
"""
import fcntl
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import enveloppe

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
TEXTE_MAX = 500
AHMED_MAX = 2000           # (30/10) Ahmed y écrit lui-même, par le cockpit seul (python cafe.py ahmed < texte)
GARDES = 200
_ID = re.compile(r"a[0-9a-f]{16}")


def _lire_json(f):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _qui(auteur, d, ahmed=False):
    """(prénom, rôle) de l'auteur, ou None s'il n'est pas de la famille. « ahmed » : seulement par le cockpit (ahmed=True)."""
    if auteur == "ahmed" and ahmed:
        return "Ahmed", "papa"
    if auteur == "hakim":
        return "Hakim", "celui qui vous lance"
    if not _ID.fullmatch(str(auteur or "")):
        return None
    agents = (_lire_json(d / "registre-agents.json").get("agents") or {})
    a = agents.get(auteur) if isinstance(agents, dict) else None
    if not isinstance(a, dict):
        return None
    fiche = ((_lire_json(d / "agents-fiches.json").get("agents") or {}).get(auteur) or {})
    return (fiche.get("prenom") or f"l'agent « {str(a.get('description', '?'))[:80]} »"), str(a.get("type") or "agent")[:40]


def dire(texte, auteur, dossier=None, ahmed=False):
    d = Path(dossier or JARVIS)
    t = re.sub(r"\s+", " ", str(texte or "")).strip()
    maximum = AHMED_MAX if ahmed else TEXTE_MAX
    if not t or len(t) > maximum:
        return f"Refusé : un message de 1 à {maximum} caractères."
    qui = _qui(auteur, d, ahmed)
    if not qui:
        return "Refusé : l'auteur n'est pas signé par le cockpit (seuls Hakim et ses agents parlent au café)."
    f = d / "cafe.jsonl"
    with open(d / "cafe.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps({"ts": time.time(), "auteur": auteur, "prenom": qui[0], "role": qui[1], "texte": t},
                               ensure_ascii=False) + "\n")
        os.chmod(f, 0o600)
        lignes = f.read_text(encoding="utf-8").splitlines()
        if len(lignes) > 2 * GARDES:
            tmp = d / f"cafe.jsonl.{os.getpid()}.tmp"
            tmp.write_text("\n".join(lignes[-GARDES:]) + "\n", encoding="utf-8")
            os.replace(tmp, f)
    return "C'est dit, au café."


def lire(n=30, dossier=None):
    d = Path(dossier or JARVIS)
    try:
        lignes = (d / "cafe.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    msgs = []
    for l in lignes[-GARDES:]:
        try:
            msgs.append(json.loads(l))
        except ValueError:
            continue
    msgs = msgs[-max(1, min(int(n or 30), GARDES)):]
    if not msgs:
        return "Personne n'a encore parlé au café."
    corps = "\n".join(f"{datetime.fromtimestamp(m.get('ts', 0)).strftime('%d/%m %H:%M')} — {m.get('prenom', '?')} ({m.get('role', '?')}) : "
                      f"{m.get('texte', '')}" for m in msgs)
    return enveloppe.enveloppe(corps, "la salle de café de la famille (ses agents et Hakim)")


if __name__ == "__main__":                     # (30/10) le cockpit seul : un message d'Ahmed, lu sur l'entrée standard
    import sys
    if sys.argv[1:] == ["ahmed"]:
        print(dire(sys.stdin.read(AHMED_MAX * 4), "ahmed", ahmed=True))
    else:
        print("usage : python cafe.py ahmed < texte")
