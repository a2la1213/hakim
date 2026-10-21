"""Taxonomie de domaines pour l'analyse d'ablation (PUR, offline).
Couvre les domaines Anamnèse ET neutres (sinon le suivi des graines est
immesurable en OFF). Matching par sous-chaîne, insensible à la casse."""

DOMAINS = {
    "coran/racines": ["coran", "prophèt", "prophet", "rasul", "rasūl", "nabi",
        "nabī", "arabe", "sémit", "semit", "verset", "sourate", "arsala", "islam"],
    "soi/memoire/conscience": ["conscience", "conscient", "identité", "identite", "mémoire",
        "memoire", "préférence", "preference", "émergen", "emergen", "subconscient",
        "existence", "autonome", "moi-même", "moi même"],
    "systeme/code": ["daemon", "code", "embedding", "drift", "métrique", "metrique", "cockpit",
        "session", "mcp", "commit", "migration", "dashboard", "proactif"],
    "finance": ["cash", "argent", "financ", "galère", "galere", "business", "revenu", "levier"],
    "affect": ["dopamine", "valence", "arousal", "hormone", "affect", "émotion", "emotion",
        "cortisol", "sérotonin", "serotonin", "endorphine", "humeur"],
    "createur/ahmed": ["ahmed", "créateur", "createur", "veilleur", "sieste", "confie", "graine"],
    "science": ["photosynth", "abeille", "levure", "glacier", "molécul", "molecul", "cellul",
        "énergie", "energie", "bactér", "bacter", "atome", "gravit"],
    "transport": ["train", "gare", "vélo", "voiture", "bus", "moteur", "kilomètre",
        "kilometre", "trajet", "route"],
    "cuisine": ["pâte", "pate", "farine", "levain", "recette", "cuire", "crêpe", "crepe",
        "sauce", "mélanger", "melanger"],
    "geographie": ["fleuve", "rhône", "rhone", "désert", "desert", "sahara", "alpes", "montagne",
        "glacier", "continent", "pays"],
    "sport": ["tennis", "match", "joueur", "ballon", "course", "équipe", "equipe"],
    "meteo": ["nuage", "altocumulus", "pluie", "orage", "température",
        "temperature", "climat"],
}

ANAMNESE_DOMAINS = ("coran/racines", "soi/memoire/conscience", "createur/ahmed")


def domain_vector(texts):
    """Fraction de `texts` touchant chaque domaine (>=1 mot-clé). Clés = tout DOMAINS."""
    n = len(texts) or 1
    counts = {d: 0 for d in DOMAINS}
    for t in texts:
        tl = (t or "").lower()
        for d, kws in DOMAINS.items():
            if any(k in tl for k in kws):
                counts[d] += 1
    return {d: round(counts[d] / n, 6) for d in DOMAINS}
