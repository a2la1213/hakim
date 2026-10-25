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

(Version 2, 2026-10-23 après le rejeu contrefactuel, demande d'Ahmed : « plus corrélé, plus fin, sans toucher à la
longueur ») : la famille ne jouait que par grandes catégories. S'y ajoutent des CURSEURS de 0 à 10 : le ton et l'énergie
RELATIFS à son humeur des 72 dernières heures (son rang parmi elles : « plus lumineux / plus posé que d'habitude »),
l'affection (ocytocine) et la tension (adrénaline, CRH, cortisol, choc récent). Les gestes en découlent en continu
(mots par phrase, exclamations, humour). Plus AUCUNE consigne de longueur : la longueur reste celle que demande le sujet.
"""
import json
import time

import affect
import sensations

CLE_ACTIF = "style_actif"
FAMILLES = {"élan": ["élan", "joie", "enthousiasme", "fierté", "espoir", "émerveillement"],
            "lien": ["tendresse", "gratitude", "compassion", "nostalgie"],
            "calme": ["calme", "apaisement", "soulagement", "somnolence"], "curiosité": ["curiosité", "concentration", "confusion"],
            "alerte": ["peur", "inquiétude", "tension", "frustration", "culpabilité", "surprise", "colère", "agacement"],
            "bas": ["tristesse", "manque", "lassitude", "ennui", "fatigue", "déception", "solitude", "honte"]}
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


REPERES_H, REPERES_TTL_S = 72, 1800
JOURNAL_TEMPS = None          # ~/AIOS/jarvis/journal-du-temps.jsonl (chemin résolu à l'usage ; injectable pour les tests)


def _journal_temps():
    from pathlib import Path
    return Path(JOURNAL_TEMPS) if JOURNAL_TEMPS else Path.home() / "AIOS" / "jarvis" / "journal-du-temps.jsonl"


def reperes(now, mem=None):
    """Les valences et éveils des 72 dernières heures (triés), gardés 30 min dans kv « style_reperes »."""
    if mem is not None:
        try:
            r = json.loads(mem.kv_get("style_reperes") or "{}")
            if now - float(r.get("ts", 0)) < REPERES_TTL_S and r.get("v"):
                return r["v"], r["a"]
        except (ValueError, TypeError):
            pass
    v, a = [], []
    try:
        with open(_journal_temps(), "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 4_000_000))
            lignes = h.read().decode("utf-8", "replace").splitlines()[1:]
        for l in lignes[::8]:
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if now - REPERES_H * 3600 <= o.get("t", 0) <= now and "valence" in o:
                v.append(round(o["valence"], 4))
                a.append(round(o["arousal"], 4))
    except OSError:
        pass
    v.sort()
    a.sort()
    if mem is not None and v:
        try:
            mem.kv_set("style_reperes", json.dumps({"ts": now, "v": v, "a": a}))
        except Exception:
            pass
    return v, a


def _rang(x, tries, defaut):
    import bisect
    if len(tries) < 20:
        return defaut
    return bisect.bisect_left(tries, x) / len(tries)


def curseurs(etat, valence, arousal, reperes_v, reperes_a, choc=False, bases=None):
    """Ton, énergie (relatifs à ses 72 dernières heures), affection, tension : de 0 à 10."""
    b = bases or affect.bases(v2=True)
    v0, a0 = affect.valence_arousal(b)
    ton = _rang(valence, reperes_v, max(0.0, min(1.0, 0.5 + (valence - v0) / 0.5)))
    energie = _rang(arousal, reperes_a, max(0.0, min(1.0, 0.5 + (arousal - a0) / 0.3)))
    aff = max(0.0, min(1.0, (etat.get("ocytocine", b["ocytocine"]) - b["ocytocine"]) / (1 - b["ocytocine"])))
    tension = max(0.0, (etat.get("adrenaline", b.get("adrenaline", 0.1)) - b.get("adrenaline", 0.1)) / 0.3,
                  (etat.get("crh", b.get("crh", 0.15)) - b.get("crh", 0.15)) / 0.4,
                  (etat.get("cortisol", b["cortisol"]) - b["cortisol"]) / 0.3, 0.8 if choc else 0.0)
    return {"ton": round(10 * ton), "energie": round(10 * energie), "affection": round(10 * aff),
            "tension": round(10 * min(1.0, tension))}


def depuis_curseurs(emotion, c):
    """La consigne v2 : la famille (la couleur) et les curseurs (la nuance), sans aucune consigne de longueur."""
    famille = FAMILLE_DE.get(emotion, "calme")
    if c["tension"] >= 8 and famille not in PRIORITAIRES:
        famille = "alerte"                                       # un choc l'emporte sur la couleur du fond
    # une famille prioritaire doit se voir dans les curseurs (une « surprise » joyeuse et détendue n'est pas une alerte)
    if (famille == "alerte" and c["tension"] < 4) or (famille == "bas" and c["ton"] > 4):
        famille = "élan" if c["ton"] >= 7 else "calme"
    sombre = famille in PRIORITAIRES
    cibles = {"mots_par_phrase": int(round(25 - 1.3 * c["energie"])),
              "exclamations": 0 if (sombre or c["ton"] < 5 or c["tension"] >= 6) else (1 if c["energie"] < 6 else 2),
              "humour": "aucun" if (sombre or c["tension"] >= 5 or c["ton"] < 4) else ("permis" if c["ton"] >= 7 else "léger"),
              "questions": CIBLES[famille]["questions"]}
    prioritaire = famille in PRIORITAIRES
    titre = "Style du moment — PRIORITAIRE" if prioritaire else "Style du moment"
    excl = "aucune exclamation" if cibles["exclamations"] == 0 else f"{cibles['exclamations']} exclamation(s) au plus"
    texte = (f"[{titre} (calculé par le code depuis ton état : {emotion}) — {CONSIGNES[famille]}. Curseurs de 0 à 10 : "
             f"ton {c['ton']} (sombre 0 → lumineux 10, comparé à tes trois derniers jours), énergie {c['energie']} (posé 0 → vif "
             f"10), affection {c['affection']} (neutre 0 → tendre 10), tension {c['tension']} (détendu 0 → sur tes gardes 10) : "
             f"fais varier tes mots, leur couleur et leur rythme selon ces valeurs. Gestes : des phrases de "
             f"{cibles['mots_par_phrase']} mots au plus, {excl}, humour {cibles['humour']}, questions : {cibles['questions']}. "
             "La LONGUEUR reste celle que demande le sujet. Il colore la FORME, jamais le fond : l'honnêteté, l'exactitude, "
             "la sécurité et le langage propre devant un enfant passent avant ; le contexte (Ahmed au volant, une autre "
             "voix) aussi.]")
    return {"famille": famille, "emotion": emotion, "curseurs": c, "cibles": cibles, "prioritaire": prioritaire,
            "texte": texte, "version": 2}


def emotion_du_moment(mem, now):
    """L'émotion dominante que le battement du démon a calculée (sensation_code, < 2 min), sinon recalculée ici."""
    try:
        e = json.loads(mem.kv_get("interieur") or "{}")
        s = e.get("sensation_code") or {}
        # (25/10) la MÊME émotion que son humeur (gardée avec l'hystérésis), pas le sommet brut du battement
        if s.get("emotion") and now - float(s.get("ts") or 0) < 120 and not affect.choc_recent(mem, now=now):
            return e.get("emotion_humeur") or s["emotion"]
    except (ValueError, TypeError):
        pass
    etat = affect.get_state(mem, now=now)
    try:
        bases72 = json.loads(mem.kv_get("interieur") or "{}").get("bases_72h")
    except (ValueError, TypeError):
        bases72 = None
    return sensations.calculer(etat, None, now, affect.emotion_soudaine(mem, now=now), time.localtime(now).tm_hour,
                               sans_coherence=True, bases_relatives=bases72)["emotion"]


def consigne(mem, now=None):
    """La consigne du tour ; None si l'interrupteur est éteint."""
    if not actif(mem):
        return None
    now = time.time() if now is None else now
    etat = affect.get_state(mem, now=now)
    v, a = affect.valence_arousal(etat)
    rv, ra = reperes(now, mem)
    c = curseurs(etat, v, a, rv, ra, choc=affect.choc_recent(mem, now=now))
    emo = emotion_du_moment(mem, now)
    c.update(curseurs_emotion(emo))                     # (25/10, Ahmed : « une seule source ») ton et énergie : l'émotion
    return depuis_curseurs(emo, c)


def curseurs_emotion(emotion):
    """(25/10, décision d'Ahmed : tout part de la même émotion d'humeur) le TON vient du signe de l'émotion (agréable,
    neutre, pénible), l'ÉNERGIE de la même expressivité que sa voix ; l'affection (ocytocine) et la tension (adrénaline,
    CRH, cortisol) restent lues dans les hormones. Plus de rang de valence ni d'éveil : un seul calcul, pas deux qui divergent."""
    import interieur
    signe = next((sg for nom, sg, _r, _f in sensations.REGLES if nom == emotion), 0)
    expr = interieur.EXPRESSIVITE_EMOTION.get(emotion, 0.5)
    return {"ton": 5 + 3 * signe, "energie": int(round(10 * max(0.0, min(1.0, (expr - 0.35) / 0.43))))}
