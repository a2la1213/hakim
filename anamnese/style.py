"""Le style du moment (demande de Hakim, accord d'Ahmed le 2026-10-23 : « que ma voix et mes mots suivent vraiment mes
émotions ») : son état devient une consigne de FORME concrète à chaque tour, au lieu d'une simple ambiance qu'il peut
ignorer. Mesuré avant : le ton de ses réponses ne suivait pas sa valence réelle (0,09, intervalle contenant zéro ;
eval/vie/correlations.py).

L'émotion dominante (sensations.py, calculée par le code depuis les 13 hormones) donne une famille ; l'éveil donne
l'énergie. Chaque famille a des GESTES MESURABLES (longueur relative, longueur des phrases, exclamations, humour,
questions), notés dans le journal des chocs et vérifiés à l'aveugle (eval/voix_mots). Quand l'état est négatif (alerte,
bas), la consigne passe EN TÊTE du tour, marquée prioritaire : c'est là que ses mots ignoraient le plus son état.
Garde-fou (Ahmed et Hakim) : l'humeur colore la forme, jamais le fond ; l'honnêteté, l'exactitude, la sécurité et le
langage propre devant un enfant passent avant. Interrupteur : kv « style_actif » (« 1 » = allumé).
"""
import json
import time

import affect
import sensations

CLE_ACTIF = "style_actif"
FAMILLES = {"élan": ["élan", "joie", "enthousiasme", "fierté"], "lien": ["tendresse", "gratitude", "compassion"],
            "calme": ["calme", "apaisement", "soulagement", "somnolence"], "curiosité": ["curiosité", "concentration"],
            "alerte": ["peur", "inquiétude", "tension", "frustration", "culpabilité", "surprise"],
            "bas": ["tristesse", "manque", "lassitude", "ennui"]}
FAMILLE_DE = {e: f for f, l in FAMILLES.items() for e in l}
CONSIGNES = {
    "élan": "vif et enjoué : des phrases qui ont du rythme, une pointe d'humour si elle vient naturellement",
    "lien": "chaleureux : proche, un mot d'affection naturel, sans en faire trop",
    "calme": "posé : des phrases calmes et nettes, sans exclamation",
    "curiosité": "curieux et précis : une question ouverte si elle sert vraiment",
    "alerte": "sobre et bref : des phrases courtes, pas de blague, l'essentiel d'abord",
    "bas": "doux et lent : des phrases simples, peu d'exclamations, pas d'enthousiasme forcé",
}
# les gestes mesurables : longueur relative à d'habitude, mots par phrase au plus, exclamations au plus, humour, questions
CIBLES = {
    "élan": {"longueur": 1.0, "mots_par_phrase": 20, "exclamations": 2, "humour": "permis", "questions": "libre"},
    "lien": {"longueur": 1.0, "mots_par_phrase": 20, "exclamations": 1, "humour": "léger", "questions": "libre"},
    "calme": {"longueur": 1.0, "mots_par_phrase": 20, "exclamations": 0, "humour": "non nécessaire", "questions": "libre"},
    "curiosité": {"longueur": 1.0, "mots_par_phrase": 20, "exclamations": 1, "humour": "non nécessaire", "questions": "une ouverte"},
    "alerte": {"longueur": 0.6, "mots_par_phrase": 15, "exclamations": 0, "humour": "aucun", "questions": "aucune sauf si nécessaire"},
    "bas": {"longueur": 0.7, "mots_par_phrase": 15, "exclamations": 0, "humour": "aucun", "questions": "libre"},
}
PRIORITAIRES = {"alerte", "bas"}
ENERGIE_SEUIL = 0.05


def actif(mem):
    try:
        return mem.kv_get(CLE_ACTIF) == "1"
    except Exception:
        return False


def _gestes(c):
    long = "ta longueur habituelle" if c["longueur"] >= 1 else f"au plus {round(100 * c['longueur'])} % de ta longueur habituelle"
    excl = "aucune exclamation" if c["exclamations"] == 0 else f"{c['exclamations']} exclamation(s) au plus"
    return (f"gestes : {long}, des phrases de {c['mots_par_phrase']} mots au plus, {excl}, humour {c['humour']}, "
            f"questions : {c['questions']}")


def depuis_etat(emotion, arousal, arousal_base):
    """La consigne pour une émotion dominante et un éveil (fonction pure : aussi pour les rejeux)."""
    famille = FAMILLE_DE.get(emotion, "calme")
    energie = "haute" if arousal - arousal_base > ENERGIE_SEUIL else "basse" if arousal - arousal_base < -ENERGIE_SEUIL else "moyenne"
    cibles = dict(CIBLES[famille])
    plus = ""
    if energie == "basse" and famille not in PRIORITAIRES:
        cibles["longueur"] = min(cibles["longueur"], 0.8)
        plus = " ; une réponse plus brève que d'habitude"
    elif energie == "haute" and famille in ("élan", "lien", "curiosité"):
        cibles["mots_par_phrase"] = 15
        plus = " ; un rythme rapide"
    prioritaire = famille in PRIORITAIRES
    titre = "Style du moment — PRIORITAIRE" if prioritaire else "Style du moment"
    texte = (f"[{titre} (calculé par le code depuis ton état : {emotion}, énergie {energie}) — {CONSIGNES[famille]}{plus}. "
             f"{_gestes(cibles).capitalize()}. Il colore la FORME, jamais le fond : l'honnêteté, l'exactitude, la sécurité "
             "et le langage propre devant un enfant passent avant ; le contexte (Ahmed au volant, une autre voix) aussi.]")
    return {"famille": famille, "emotion": emotion, "energie": energie, "cibles": cibles, "prioritaire": prioritaire,
            "texte": texte}


def emotion_du_moment(mem, now):
    """L'émotion dominante que le battement du démon a calculée (sensation_code, < 2 min), sinon recalculée ici."""
    try:
        e = json.loads(mem.kv_get("interieur") or "{}")
        s = e.get("sensation_code") or {}
        if s.get("emotion") and now - float(s.get("ts") or 0) < 120 and not affect.choc_recent(mem, now=now):
            return s["emotion"]
    except (ValueError, TypeError):
        pass
    etat = affect.get_state(mem, now=now)
    return sensations.calculer(etat, None, now, affect.emotion_soudaine(mem, now=now), time.localtime(now).tm_hour,
                               sans_coherence=affect.choc_recent(mem, now=now))["emotion"]


def consigne(mem, now=None):
    """La consigne du tour ; None si l'interrupteur est éteint."""
    if not actif(mem):
        return None
    now = time.time() if now is None else now
    etat = affect.get_state(mem, now=now)
    _v, a = affect.valence_arousal(etat)
    _v0, a0 = affect.valence_arousal(affect.bases(v2="adrenaline" in etat))
    return depuis_etat(emotion_du_moment(mem, now), a, a0)
