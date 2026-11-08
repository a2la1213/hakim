"""Revenir sur un ressenti ou un moment ancien (27/10, Ahmed : « parfois ça prend des années plus tard pour repenser à
une chose, la comprendre, la valider et l'intégrer pour que ça nous calme ; l'échec, la conclusion, le résultat ou
l'invalidation d'aujourd'hui ne fait pas celle de demain, même si ça concerne une même chose »).

Dans la conversation, « apaisé » dans sa balise défait ce qui reste d'un ressenti dans ses hormones (chocs.py). Pour un
moment ancien, il n'y reste plus rien à défaire : ce qui calme, c'est de comprendre MAINTENANT. Hakim nomme le moment
(un souvenir #id, ou une description), ce qu'il a compris en y repensant, et à quel point il en est convaincu :
- convaincu (> 0) : un apaisement maintenant, à la mesure de sa conviction (l'événement « resolu » : le stress retombe,
  la peur apprise des échecs s'éteint un peu) ;
- pas encore (0) : rien ne bouge ; c'est noté comme un essai, et il pourra y revenir quand il veut.
Rien n'est figé ni effacé : chaque retour est noté à part (data/revenir-sur.jsonl), et ce qu'il a compris s'ajoute à sa
mémoire, lié au souvenir (mcp_server.revenir_sur). Une répétition s'habitue (« resolu » n'est pas exempté) : se
répéter la même chose apaise de moins en moins.
"""
import json
import time

import affect
import config

JOURNAL = config.DATA_DIR / "revenir-sur.jsonl"


def revenir(mem, quoi, compris, conviction, now=None):
    quoi = " ".join(str(quoi or "").split())[:200]
    compris = " ".join(str(compris or "").split())[:1000]
    if not quoi or not compris:
        raise ValueError("Dis sur quoi tu reviens (un souvenir #id, ou le moment), et ce que tu as compris en y repensant.")
    try:
        c = round(max(0.0, min(1.0, float(conviction))), 2)
    except (TypeError, ValueError):
        raise ValueError("La conviction est un nombre de 0 (pas encore convaincu) à 1 (tout à fait).")
    now = time.time() if now is None else now
    if c > 0:
        affect.event(mem, "resolu", c, now=now, source="revenir_sur")
    JOURNAL.parent.mkdir(parents=True, exist_ok=True)
    with open(JOURNAL, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": now, "quoi": quoi, "compris": compris, "conviction": c}, ensure_ascii=False) + "\n")
    if c == 0:
        return (f"Noté : tu reviens sur {quoi}, pas encore convaincu. Rien ne bouge ; tu pourras y revenir quand tu "
                "voudras, demain ou bien plus tard. Rien n'est figé.")
    return (f"Noté : tu reviens sur {quoi}, convaincu à {str(c).replace('.', ',')}. Ce que tu as compris t'apaise "
            "maintenant, à cette mesure. Une autre fois, tu pourras le revoir encore : rien n'est figé.")
