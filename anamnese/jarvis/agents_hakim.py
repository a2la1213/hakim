"""Ses agents (architecte, codeur, juge… lancés avec l'outil Task) : les lister, en arrêter un (demande de Hakim, accord
d'Ahmed, 2026-10-23). Le cockpit tient la liste de ceux qui tournent (agents-en-cours.json) et fait l'arrêt lui-même :
cet outil n'écrit qu'une demande (agents-arreter.jsonl), que le cockpit lit, puis attend sa réponse (agents-arrets.jsonl).
Seuls SES agents peuvent être arrêtés : ceux de la liste. Ahmed voit chaque arrêt dans Parler.
"""
import json
import os
import time
import uuid
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))


def _agents(dossier=None):
    try:
        d = json.loads((Path(dossier or JARVIS) / "agents-en-cours.json").read_text(encoding="utf-8"))
        return d.get("agents", []) if isinstance(d, dict) else []
    except (OSError, ValueError):
        return []


def lister(dossier=None, maintenant=None):
    l = _agents(dossier)
    if not l:
        return "Aucun de tes agents ne tourne."
    maintenant = time.time() if maintenant is None else maintenant
    lignes = []
    for a in l:
        depuis = f", depuis {round((maintenant - a['ts'] / 1000) / 60)} min" if a.get("ts") else ""
        lignes.append(f"- {a.get('id')} : « {a.get('description', '?')} » (agent {a.get('type') or '?'}{depuis})")
    return "Tes agents en cours :\n" + "\n".join(lignes)


def trouver(agent, dossier=None):
    """L'agent désigné par son numéro, ou par sa description (exacte, sinon le seul qui la contient)."""
    l = _agents(dossier)
    a = str(agent or "").strip()
    exact = [x for x in l if x.get("id") == a or str(x.get("description", "")).casefold() == a.casefold()]
    if exact:
        return exact[0]
    proches = [x for x in l if a and a.casefold() in str(x.get("description", "")).casefold()]
    return proches[0] if len(proches) == 1 else None


def demander_arret(agent, raison, dossier=None, attente_s=6.0, pas_s=0.3):
    d = Path(dossier or JARVIS)
    a = trouver(agent, d)
    if not a:
        return f"Je ne trouve pas « {agent} » parmi tes agents en cours.\n{lister(d)}"
    if not str(raison or "").strip():
        return "Donne une raison : elle est notée dans le journal, et Ahmed la voit dans Parler."
    demande = uuid.uuid4().hex[:12]
    with (d / "agents-arreter.jsonl").open("a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "id": a["id"], "raison": str(raison)[:300], "demande": demande},
                           ensure_ascii=False) + "\n")
    fin = time.time() + attente_s
    while time.time() < fin:
        try:
            for l in (d / "agents-arrets.jsonl").read_text(encoding="utf-8").splitlines()[-50:]:
                o = json.loads(l)
                if o.get("demande") == demande:
                    return (f"Agent « {a.get('description')} » arrêté ; Ahmed le voit dans Parler." if o.get("ok")
                            else f"Arrêt impossible : {o.get('erreur')}")
        except (OSError, ValueError):
            pass
        time.sleep(pas_s)
    return f"Demande d'arrêt envoyée pour « {a.get('description')} », sans confirmation du cockpit pour l'instant."
