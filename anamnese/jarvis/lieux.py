"""Ses lieux nommés (30/10, 14:53, Ahmed via Hakim : « qu'il puisse étiqueter les LIEUX de ma position, comme ses autres
sensations : ici c'est chez nous, ici c'est le parc qu'il aime, ici c'est Genève ; et que ses sensations lui disent ensuite
« tu es chez vous », « tu arrives au parc » » ; Hakim : « que les coordonnées restent dans le cockpit, sur le Mac, et ne
passent jamais dans ma mémoire, mes lettres ou mes fichiers ; je ne manipule que les NOMS »).

Seul le cockpit connaît la position (en mémoire) et écrit lieux.json (avec les coordonnées, hors de son atelier, que son
terminal ne lit pas). Ici, Hakim demande (lieux-demandes.jsonl) et lit la réponse (lieux-reponses.jsonl) : des noms, jamais
de coordonnées. Fermé aux chantiers de Hakim.
(30/10, 15:05, Ahmed : « renommer et modifier un lieu, par exemple quand on déménage, et l'effacer, MAIS en gardant toujours
une trace : l'historique de chaque lieu, pour ne pas oublier qu'on a vécu à tel endroit, à tel moment ») rien ne s'efface :
oublier ARCHIVE (avec sa date), renommer et déménager s'écrivent dans l'historique du lieu.
"""
import json
import os
import re
import time
import uuid
from datetime import datetime
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
_NOM = re.compile(r"[^\W\d_][\w' -]{0,39}")


def _demander(action, attente_s, **champs):
    d = {"id": uuid.uuid4().hex[:12], "action": action, "ts": time.time(), **champs}
    f = JARVIS / "lieux-demandes.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(d, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)
    fin = time.time() + attente_s
    while time.time() < fin:
        try:
            for l in reversed((JARVIS / "lieux-reponses.jsonl").read_text(encoding="utf-8").splitlines()[-50:]):
                o = json.loads(l)
                if o.get("id") == d["id"]:
                    return str(o.get("texte") or "")[:400]
        except (OSError, ValueError):
            pass
        time.sleep(0.2)
    return "Le cockpit ne répond pas pour l'instant (sa position est gardée par lui seul) : réessaie dans un moment."


def nommer(nom, rayon_m=150, attente_s=8.0):
    n = " ".join(str(nom or "").split())
    if not _NOM.fullmatch(n):
        return "Refusé : un nom de lieu, 1 à 40 caractères (lettres d'abord) : « chez nous », « le parc », « Genève »…"
    try:
        r = int(rayon_m)
    except (TypeError, ValueError):
        r = 150
    return _demander("nommer", attente_s, nom=n, rayon_m=max(30, min(r, 20000)))


def oublier(nom, attente_s=8.0):
    """Archive le lieu (il n'est plus reconnu, mais sa trace reste, avec ses dates)."""
    return _demander("oublier", attente_s, nom=" ".join(str(nom or "").split())[:40])


def renommer(ancien, nouveau, attente_s=8.0):
    n = " ".join(str(nouveau or "").split())
    if not _NOM.fullmatch(n):
        return "Refusé : le nouveau nom, 1 à 40 caractères (lettres d'abord)."
    return _demander("renommer", attente_s, nom=" ".join(str(ancien or "").split())[:40], nouveau=n)


def demenager(nom, rayon_m=None, attente_s=8.0):
    """Le lieu change de place (on déménage) : l'ancien endroit est archivé sous ce nom, avec ses dates ; le nom vit ici."""
    return _demander("demenager", attente_s, nom=" ".join(str(nom or "").split())[:40], **({"rayon_m": int(rayon_m)} if rayon_m else {}))


def lister():
    try:
        l = json.loads((JARVIS / "lieux.json").read_text(encoding="utf-8")).get("lieux") or []
    except (OSError, ValueError, AttributeError):
        l = []
    try:
        ici = json.loads((JARVIS / "lieu-actuel.json").read_text(encoding="utf-8")).get("nom")
    except (OSError, ValueError, AttributeError):
        ici = None
    if not l:
        return "Aucun lieu nommé encore : lieu_nommer(« chez nous ») quand tu y es."
    date = lambda t: datetime.fromtimestamp(float(t or 0)).strftime("%d/%m/%Y à %H:%M")                     # noqa: E731
    QUOI = {"nommé": "nommé", "renommé": "renommé", "déménagé": "déménagé ici", "archivé": "archivé (quitté)"}

    def ligne(x):
        h = x.get("historique") or [{"quoi": "nommé", "ts": x.get("ts")}]
        trace = " ; ".join(f"{QUOI.get(e.get('quoi'), e.get('quoi'))} le {date(e.get('ts'))}"
                           + (f" (avant : « {e['de']} »)" if e.get("de") else "") for e in h)
        return f"- {x.get('nom')} ({int(x.get('rayon_m') or 0)} m autour) — {trace}" + (" — tu y es" if x.get("nom") == ici and not x.get("archive") else "")
    actifs = [ligne(x) for x in l if isinstance(x, dict) and not x.get("archive")]
    archives = [ligne(x) for x in l if isinstance(x, dict) and x.get("archive")]
    return ("Tes lieux nommés (leurs coordonnées restent dans le cockpit) :\n" + ("\n".join(actifs) or "(aucun)")
            + ("\nLeur mémoire (archivés, jamais effacés) :\n" + "\n".join(archives) if archives else ""))
