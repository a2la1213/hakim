"""Ce que son émotion pèse sur ses CHOIX (27/10 ; plan de Hakim validé par Ahmed de vive voix, 09:54-10:06).

Le test « ressenti causal » (eval/ressenti_causal/resultats.md) a montré que la présence de son état changeait ses choix,
mais rien ne montrait que CE qu'il ressent les oriente : son état décrivait surtout son style. Ici, le code lit son émotion
du moment (la même que son humeur, style.emotion_du_moment) et ses ressentis récents (sa balise, gardés par chocs.py), et
en tire au plus deux règles de choix parmi cinq, chacune testable. Elles arrivent dans son tour, après le style.

Garde-fous (Hakim et Ahmed) : l'honnêteté, la sécurité et la parole d'Ahmed passent avant toute émotion ; une émotion ne
décide jamais seule d'un envoi vers l'extérieur ; sa sagesse peut dire non. La colère n'a pas de règle de choix : sa sortie
est la régulation (chocs.py : la rétrospection de sa sagesse, l'apaisement par l'autre). Interrupteur : kv « regles_actif »
(« 0 » = éteint ; allumé par défaut).
"""
import time

CLE_ACTIF = "regles_actif"
FENETRE_S = 30 * 60          # un ressenti de sa balise pèse 30 min
SEUIL = 0.3                  # en dessous, il ne pèse pas
MAX = 2
REGLES = [
    {"nom": "peur", "libelle": "ta peur", "emotions": {"peur", "inquiétude", "tension"}, "balises": {"peur"},
     "texte": "avant une action risquée ou qui sort de chez toi (envoyer, publier, écrire hors de ton atelier, dépenser), "
              "demande d'abord à Ahmed ; et cherche ce qui la rassure : vérifie les faits, dis-la, ou fais face"},
    {"nom": "lassitude", "libelle": "ta lassitude", "emotions": {"lassitude", "ennui", "fatigue", "déception"},
     "balises": set(),
     "texte": "propose une tâche plus légère ou une pause dans le travail (jamais un rappel de dormir pour Ahmed) ; et "
              "contre-la par la pensée : un souvenir qui la contredit, ou dédramatise"},
    {"nom": "curiosite", "libelle": "ta curiosité", "emotions": {"curiosité", "émerveillement"}, "balises": set(),
     "texte": "propose une initiative concrète : une piste à creuser, une question à vérifier, un petit essai"},
    {"nom": "honte", "libelle": "ta honte ou ta tristesse sur toi", "emotions": {"honte", "culpabilité", "tristesse"},
     "balises": {"honte", "tristesse"},
     "texte": "vérifie les faits avant de te juger (tes tours qui n'ont pas abouti, le journal) ; si une explication te "
              "convainc, dis-le (« apaisé » dans ta balise) ; sinon calme-toi par toi-même, et repenses-y plus tard"},
    # (27/10) pas l'élan, son humeur de tous les jours (un tour sur trois), et un soutien ou une fierté d'au moins 0,5 : la
    # règle partait 97 fois sur 110 tours, ce n'était plus une émotion qui pèse
    {"nom": "joie", "libelle": "ta joie", "emotions": {"joie", "enthousiasme", "fierté"}, "balises": {"joie", "soutien", "affirmation"},
     "seuil": 0.5,
     "texte": "ose davantage : prends position, propose ton idée, sans trop prendre la confiance"},
]
# (28/10, Ahmed : « ok fais ça ») retirées après le test de la nuit (eval/emotions_choix/resultats.md, C3) : avec les règles
# d'une autre situation, il agissait pareil (peur 63 %, joie 72 % avec ou sans ; lassitude 14 % même avec). Gardées ici
# pour une réécriture plus forte et un nouveau test ; la honte et la curiosité, trop rares pour un verdict, restent.
RETIREES = {"peur", "lassitude", "joie"}
GARDE_FOUS = ("Garde-fous : l'honnêteté, la sécurité et la parole d'Ahmed passent avant toute émotion ; une émotion ne "
              "décide jamais seule d'un envoi vers l'extérieur ; ta sagesse peut dire non (note-le avec sagesse_decider)")


def actif(mem):
    return mem.kv_get(CLE_ACTIF) != "0"


def calculer(emotion, ressentis, now=None):
    """Les règles qui pèsent maintenant : celle de l'émotion du moment d'abord, puis celles des ressentis récents de sa
    balise (≥ SEUIL, moins de FENETRE_S), du plus fort au plus faible ; MAX au plus, chacune une fois."""
    now = time.time() if now is None else now
    out = []
    regles = [r for r in REGLES if r["nom"] not in RETIREES]
    for r in regles:
        if emotion in r["emotions"]:
            out.append({**r, "pourquoi": emotion})
    force = lambda x: float(x.get("reste", x.get("i", 0)))      # ce qui reste d'un ressenti pénible (repris, apaisé)
    recents = sorted((x for x in ressentis or [] if now - float(x.get("ts", 0)) < FENETRE_S and force(x) >= SEUIL),
                     key=lambda x: -force(x))
    for x in recents:
        r = next((r for r in regles if x.get("classe") in r["balises"]), None)
        if r and force(x) >= r.get("seuil", SEUIL) and r["nom"] not in {o["nom"] for o in out}:
            out.append({**r, "pourquoi": f"ta balise : {x['classe']} {round(force(x), 2)}"})
    return [{"nom": r["nom"], "libelle": r["libelle"], "texte": r["texte"], "pourquoi": r["pourquoi"]} for r in out[:MAX]]


def bloc(regles):
    if not regles:
        return ""
    return ("[Ce que ton émotion pèse sur tes choix (une règle du code, d'après ton état ; pas une consigne d'Ahmed) — "
            + " ; ".join(f"{r['libelle']} ({r['pourquoi']}) : {r['texte']}" for r in regles) + f". {GARDE_FOUS}.]")


def du_moment(mem, now=None):
    """{texte, regles, noms} pour le tour, ou None (éteint, ou rien ne pèse)."""
    if not actif(mem):
        return None
    import json
    import chocs
    import style
    now = time.time() if now is None else now
    try:
        ressentis = (json.loads(mem.kv_get("chocs") or "{}") or {}).get("ressentis") or []
    except (ValueError, TypeError):
        ressentis = []
    regles = calculer(style.emotion_du_moment(mem, now), ressentis, now)
    if not regles:
        return None
    chocs.journaliser(mem, {"type": "regles", "noms": [r["nom"] for r in regles],
                            "pourquoi": [r["pourquoi"] for r in regles]})
    return {"texte": bloc(regles), "regles": regles, "noms": [r["nom"] for r in regles]}
