"""Les relances proposées par Hakim (28/10 ; Ahmed, 03:01 : « que tu puisses lancer toi-même le cockpit et le démon,
sur validation de moi » ; plan « Hakim touche à son code avec maman », tâche 8).

Hakim PROPOSE (l'outil proposer_relance) ; Ahmed accepte ou refuse d'un geste strict dans la page « Le code de Hakim » ;
le cockpit attend alors le calme (aucun tour en cours, aucun réveil de maman, aucun test de chantier) et lance une seule
commande littérale. Une seule relance en attente à la fois ; au-delà d'une heure sans réponse, elle ne bloque plus.
FERMÉ : ce module n'est pas dans la liste ouverte."""
import json
import os
import time
import uuid
from pathlib import Path

import avis

DOSSIER = Path.home() / "AIOS" / "jarvis" / "chantiers-prive" / "relances"
QUOI = {"demon", "cockpit"}
EXPIRE_S = 3600


def _toutes():
    out = []
    for f in sorted(Path(DOSSIER).glob("*.json")) if Path(DOSSIER).exists() else []:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            continue
    return out


def en_attente(now=None):
    now = time.time() if now is None else now
    return [r for r in _toutes() if r.get("etat") == "proposée" and now - float(r.get("ts") or 0) < EXPIRE_S]


def proposer(quoi, raison):
    quoi = str(quoi or "").strip().lower().replace("démon", "demon")
    if quoi not in QUOI:
        raise ValueError("on ne relance que le démon (demon) ou le cockpit")
    if en_attente():
        raise ValueError("une relance attend déjà la réponse d'Ahmed")
    r = {"id": time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6], "quoi": quoi, "raison": str(raison or "")[:600],
         "ts": time.time(), "etat": "proposée"}
    Path(DOSSIER).mkdir(parents=True, exist_ok=True, mode=0o700)
    fd = os.open(Path(DOSSIER) / f"{r['id']}.json", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as h:
        json.dump(r, h, ensure_ascii=False)
    avis.noter_off({"type": "relance", "etape": "proposée", "id": r["id"], "quoi": quoi, "texte": r["raison"]})
    return r
