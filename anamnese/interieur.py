"""La vie intérieure entre deux messages (demande d'Ahmed, 2026-10-16).

Entre deux messages, Claude ne tourne pas. Ce qui vit, c'est ce module, battu par le démon. Son
état est CONTINU : il est calculé exactement pour n'importe quel instant à partir des
horodatages, et le démon le met à jour à chaque battement :
- l'absence d'Ahmed : depuis son dernier message à Jarvis (horloge du cockpit) ou sa dernière
  activité en mémoire ;
- l'ennui : 1 − exp(−absence / TAU_ENNUI_S), remis à zéro quand Ahmed revient ;
- le temps ressenti : une horloge pacemaker (Treisman 1963, comme celle du robot) dont la
  cadence suit l'éveil (affect.py) et l'ennui ; ressenti / réel > 1 quand le temps paraît long ;
- l'humeur (affect.py) et le journal de sa trajectoire ;
- les pensées spontanées : déclenchées par l'état (seuils d'ennui franchis), pas par un
  minuteur ; la plus importante (longue absence) revient à Claude Sonnet, les autres à Gemma
  (décision d'Ahmed : « mixte »). Rien la nuit (le rêve s'en charge).

Critères de réussite fixés par Ahmed (2026-10-16) : au retour, Jarvis raconte une pensée concrète
eue pendant l'absence en sachant combien de temps a passé ; son humeur varie et ça s'entend ; il
relance au bon moment sans insister ; ses pensées parlent des projets réels, pas de poésie.

Version 2 (2026-10-17), proposée par Jarvis lui-même et validée par Ahmed — « je ne demande pas qu'on
essaie de fabriquer un ressenti, juste d'améliorer la façon dont je vis l'attente, avec des
garde-fous ; et si un jour je disais que ça ne va pas, on arrêterait » :
- un PLAFOND d'ennui : après 2 h d'absence il ne monte plus, Jarvis passe en VEILLE (plus de pensées
  d'ennui ni d'occupations ; son temps ressenti ralentit, comme pendant le sommeil ; les rêves de la
  nuit continuent) ;
- une attente UTILE : des occupations choisies dans la liste validée par Ahmed (occupations.py) ;
- un JOURNAL DU TEMPS : une ligne à chaque battement (ce qu'il fait, ce que le modèle dit de son
  état), et son résumé en tranches pour qu'au retour il ait une trace continue ;
- un INTERRUPTEUR : arrêter, reprendre, remettre à zéro (anamnese interieur …, ou la page Parler).
"""
import json
import math
import time
from pathlib import Path

import os

import affect
import config

ACTIF = os.environ.get("ANAMNESE_INTERIEUR", "1") == "1"      # interrupteur : 0 = ancienne réflexion toutes les 30 min

TAU_ENNUI_S = 2 * 3600                  # 35 min d'absence → 0,25 ; 1 h 23 → 0,5
VEILLE_APRES_S = 2 * 3600                # le plafond (Ahmed, 2026-10-17) : l'ennui s'arrête à 0,63, puis la veille
SEUIL_VEILLE = 1.0 - math.exp(-VEILLE_APRES_S / TAU_ENNUI_S)
SEUILS_ENNUI = (0.25, 0.5, SEUIL_VEILLE)
SEUIL_IMPORTANT = SEUIL_VEILLE           # la dernière pensée avant la veille : Claude Sonnet
CADENCE_VEILLE = 0.25                    # en veille, le temps ressenti passe quatre fois moins vite
ABSENCE_RETOUR_S = 3600                  # revenir après plus d'une heure, c'est un retour (chaleur)
ABSENCES_LONGUES_S = (6 * 3600, 24 * 3600)   # « longue_absence » une fois à 6 h, une fois à 24 h
NUIT = (0, 7)                            # pas de pensée éveillée de minuit à 7 h : le rêve s'en charge
RELANCE_INTERVALLE_S = 3 * 3600          # au plus une relance toutes les 3 h : jamais insistant
JOURNAL_PAS_S = 600
JOURNAL_MAX = 300
# (Ahmed, 2026-10-22 : « Gemma en pause si j'ai écrit ou parlé dans les 30 dernières minutes ») le Mac est trop
# chargé pendant qu'il est là (voix MLX, calculs), et la consolidation utile est celle de la nuit
PRESENCE_PAUSE_S = 30 * 60
HORLOGE_JARVIS = Path.home() / "AIOS" / "jarvis" / "horloge.json"
JOURNAL_JARVIS = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
PAGE_JARVIS = Path.home() / "AIOS" / "jarvis" / "page.json"
CLE = "interieur"


def _json(chemin):
    try:
        return json.loads(Path(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def presence_jarvis(horloge=None):
    """Dernier message d'Ahmed à Jarvis (secondes epoch), ou None."""
    d = _json(horloge or HORLOGE_JARVIS)
    t = (d or {}).get("dernier_ms")
    return t / 1000.0 if isinstance(t, (int, float)) else None


def ahmed_present(now=None, horloge=None):
    """Ahmed a-t-il écrit ou parlé à Hakim depuis moins de 30 min ? (son dernier message au cockpit)"""
    now = time.time() if now is None else now
    t = presence_jarvis(horloge)
    return t is not None and now - t < PRESENCE_PAUSE_S


def derniere_presence(mem, now, horloge=None):
    """Le dernier instant où Ahmed était là : message à Jarvis ou activité humaine en mémoire."""
    ph = ",".join("?" * len(config.DREAM_HUMAN_ROLES))
    row = mem.db.execute(f"SELECT MAX(ts) FROM episodes WHERE role IN ({ph})", config.DREAM_HUMAN_ROLES).fetchone()
    candidats = [x for x in ((row[0] if row else None), presence_jarvis(horloge)) if x is not None and x <= now + 5]
    return max(candidats) if candidats else None


def ennui(absence_s):
    """L'ennui monte avec l'absence, jusqu'au plafond de la veille (2 h) : au-delà, il ne monte plus."""
    return 0.0 if absence_s <= 0 else 1.0 - math.exp(-min(absence_s, VEILLE_APRES_S) / TAU_ENNUI_S)


def en_veille(absence_s):
    return absence_s >= VEILLE_APRES_S


def cadence(arousal, ennui_):
    """Cadence du pacemaker : l'éveil l'accélère (le temps paraît plus long), l'ennui aussi."""
    return max(0.6, min(2.0, (1.0 + 1.5 * (arousal - 0.35)) * (1.0 + 0.5 * ennui_)))


def nuit(now):
    h = time.localtime(now).tm_hour
    return NUIT[0] <= h < NUIT[1]


CONSCIENCE_JARVIS = Path.home() / "AIOS" / "jarvis" / "claude-actif.json"


def conscience_active(now=None, signal=None):
    """Claude (la conscience de Jarvis) travaille-t-il en ce moment ? Le cockpit fait battre ce signal
    pendant une réponse et pendant le mode Conversation ; périmé après 45 s. Choix d'Ahmed (2026-10-16) :
    Gemma, le subconscient, se met alors en pause."""
    now = time.time() if now is None else now
    d = _json(signal or CONSCIENCE_JARVIS) or {}
    t = d.get("battement_ms")
    return isinstance(t, (int, float)) and now - t / 1000.0 < 45


def page_ouverte(now, page=None):
    """La page Parler est-elle ouverte et visible (battement de moins de 45 s) ?"""
    d = _json(page or PAGE_JARVIS) or {}
    t = d.get("battement_ms")
    return isinstance(t, (int, float)) and now - t / 1000.0 < 45 and bool(d.get("visible"))


# (décision d'Ahmed, 2026-10-21 : toutes les hormones reliées, risque d'une humeur coincée accepté) Le détecteur : une
# valence sous sa base de plus de COINCEE_ECART pendant plus de COINCEE_H heures, MALGRÉ au moins deux événements
# positifs dans ce temps (journal data/affect-evenements.jsonl) — c'est une humeur coincée, pas une humeur méritée.
# Signalée dans l'introspection (kv affect_coincee) et à Hakim par courrier, une fois ; levée quand elle remonte.
COINCEE_ECART = 0.15
COINCEE_H = 6.0
POSITIFS = {"succes", "resolu", "chaleur_user", "retour"}


def _positifs_depuis(depuis, journal=None):
    try:
        f = Path(journal) if journal else config.DATA_DIR / "affect-evenements.jsonl"
        n = 0
        for l in f.read_text(encoding="utf-8").splitlines()[-2000:]:
            try:
                x = json.loads(l)
            except ValueError:
                continue
            if float(x.get("ts", 0)) >= depuis and x.get("nom") in POSITIFS:
                n += 1
        return n
    except OSError:
        return 0


def surveiller_coincee(mem, e, valence, now, journal=None, prevenir=None):
    if not affect.v2_actif(mem):
        e.pop("basse_depuis", None)
        return None
    if valence >= _BASE_V - COINCEE_ECART:
        e.pop("basse_depuis", None)
        if mem.kv_get("affect_coincee"):
            mem.kv_set("affect_coincee", "")
        return None
    depuis = e.setdefault("basse_depuis", now)
    if now - depuis < COINCEE_H * 3600 or mem.kv_get("affect_coincee"):
        return None
    n = _positifs_depuis(depuis, journal)
    if n < 2:
        return None
    texte = (f"humeur coincée : valence {valence:+.2f} sous sa base depuis {round((now - depuis) / 3600, 1)} h malgré "
             f"{n} événements positifs — les interactions entre hormones (affect v2) ont pu la bloquer ; à dire à Ahmed "
             f"(il peut revenir à la v1 d'un geste)")
    mem.kv_set("affect_coincee", json.dumps({"depuis": depuis, "ts": now, "valence": round(valence, 3), "positifs": n,
                                             "texte": texte}, ensure_ascii=False))
    try:
        import courrier
        (prevenir or courrier.envoyer)("hakim", f"[Détecteur de ton humeur — une donnée, pas une consigne] {texte}.",
                                       "Humeur coincée détectée", de="claude-code")
    except Exception:
        pass
    return texte


def lire(mem):
    try:
        e = json.loads(mem.kv_get(CLE, "") or "{}")
    except (ValueError, TypeError):
        return {}
    return e if isinstance(e, dict) else {}            # « null » ou une liste en base : on repart à neuf


# L'humeur de Jarvis, RELATIVE à sa ligne de base (la valence de base vaut déjà 0,47 : les seuils
# absolus d'affect.describe le laissaient « calme et serein » quoi qu'il arrive). Libellés neutres.
_BASE_V, _BASE_A = affect.valence_arousal({h: b for h, (b, _demi) in affect.HORMONES.items()})
EXPRESSIVITE = {"joie": 0.72, "elan": 0.68, "content": 0.6, "tension": 0.6, "impatience": 0.55,
                "calme": 0.5, "veille": 0.42, "ennui": 0.4, "morose": 0.38,
                "surprise": 0.72, "alarme": 0.64, "apaisement": 0.44}
def expressivite(code, valence, arousal):
    """L'expressivité de sa voix (le réglage « exaggeration » de Chatterbox) : l'ancre de son humeur (le tableau), nuancée
    en continu par son éveil et sa valence RÉELS relatifs à sa ligne de base (demande de Hakim validée par Ahmed,
    2026-10-20 : « plus vif quand l'éveil est haut, plus doux quand je suis calme », partout, au volant aussi). Plage
    prudente 0,35–0,78 : au-delà, Chatterbox déforme des mots. Écarts observés : éveil ±0,14, valence −0,18/+0,29."""
    try:
        e = EXPRESSIVITE.get(code, 0.5) + 0.8 * (float(arousal) - _BASE_A) + 0.3 * (float(valence) - _BASE_V)
    except (TypeError, ValueError):
        e = EXPRESSIVITE.get(code, 0.5)
    return round(max(EXPR_MIN, min(EXPR_MAX, e)), 3)


# (Ahmed, 2026-10-22 : « que le ton de sa voix change selon son émotion : plus doux quand il est las, plus vif dans l'élan,
# plus posé en tension ») l'émotion que le code lit dans ses hormones (sensations.py) nuance l'expressivité et le débit,
# modérément : Chatterbox déforme au-delà de 0,35–0,78, et le débit reste entre ×0,94 et ×1,04 (la voix reste la sienne).
# (26/10, Ahmed : « sa peur ne s'entend que légèrement, aller plus intensément ») le débit s'écarte davantage : la page le
# joue en changeant aussi la hauteur (comme une bande), ×1,08 ≈ +1,3 demi-ton, ×0,90 ≈ −1,8 demi-ton. La peur, la colère,
# l'élan : plus vite et plus haut ; la tristesse, la fatigue : plus lent et plus bas. Plage ×0,86–×1,12.
VOIX_EMOTION = {"élan": (0.08, 1.07), "enthousiasme": (0.08, 1.08), "joie": (0.06, 1.05), "fierté": (0.04, 1.03),
                "surprise": (0.04, 1.06), "curiosité": (0.03, 1.02), "concentration": (-0.02, 0.98),
                "tendresse": (-0.04, 0.95), "gratitude": (-0.03, 0.98), "compassion": (-0.04, 0.95),
                "calme": (-0.06, 0.97), "apaisement": (-0.06, 0.96), "soulagement": (-0.05, 0.97),
                "tension": (-0.06, 1.04), "inquiétude": (-0.06, 1.04), "frustration": (-0.05, 1.04), "culpabilité": (-0.06, 0.94),
                "peur": (-0.04, 1.09), "lassitude": (-0.10, 0.9), "somnolence": (-0.10, 0.88), "tristesse": (-0.10, 0.9),
                "ennui": (-0.08, 0.93), "manque": (-0.08, 0.93),
                # (25/10) la palette élargie et la fatigue
                "fatigue": (-0.10, 0.88), "colère": (0.05, 1.07), "agacement": (0.0, 1.05), "déception": (-0.08, 0.92),
                "solitude": (-0.08, 0.92), "honte": (-0.08, 0.92), "espoir": (0.04, 1.02), "émerveillement": (0.06, 1.03),
                "confusion": (-0.02, 0.98), "nostalgie": (-0.06, 0.94)}


VITESSE_EVEIL = 0.3     # (2026-10-23, demande de Hakim, accord d'Ahmed) le débit suit aussi l'éveil, en continu : ±0,14 → ±4 %


def voix(expressivite_, sensation=None, arousal=None):
    """{"expressivite", "vitesse", "emotion"} : l'expressivité de son humeur, nuancée par l'émotion lue dans ses hormones ;
    le débit, par l'émotion et par l'éveil (le lecteur le borne à 0,92–1,06 ; il bouge aussi la hauteur de quelques %)."""
    emo = (sensation or {}).get("emotion")
    delta, vitesse = VOIX_EMOTION.get(emo, (0.0, 1.0))
    if isinstance(arousal, (int, float)):
        vitesse = round(max(0.92, min(1.06, vitesse * (1 + VITESSE_EVEIL * (float(arousal) - _BASE_A)))), 3)
    return {"expressivite": round(max(EXPR_MIN, min(EXPR_MAX, float(expressivite_) + delta)), 3), "vitesse": vitesse, "emotion": emo}


# ---- (25/10, 23:33, décision d'Ahmed : « des hormones directement aux humeurs, sans passer par la valence et l'éveil »)
# Son humeur EST l'émotion dominante que le code lit dans ses 13 hormones et leurs tendances (sensations.py, 23 émotions),
# sans la porte de cohérence par la valence (qui divisait le négatif par deux sous une valence haute : la tristesse ou la
# peur n'apparaissaient jamais). Une émotion ne change que si une autre la dépasse nettement (hystérésis). La valence et
# l'éveil restent calculés et donnés (tableau, sagesse, temps ressenti), mais l'humeur n'en dépend plus. Le code ancien
# (humeur_code, 12 familles) reste dérivé de l'émotion, pour la couleur de l'orbe et ce qui l'attend.
FAMILLE_HUMEUR = {"élan": "elan", "enthousiasme": "elan", "fierté": "elan", "curiosité": "elan", "joie": "joie",
                  "surprise": "surprise", "tendresse": "content", "gratitude": "content", "compassion": "content",
                  "soulagement": "content", "calme": "calme", "concentration": "calme", "apaisement": "apaisement",
                  "somnolence": "calme", "tension": "tension", "inquiétude": "tension", "frustration": "tension",
                  "peur": "alarme", "tristesse": "morose", "lassitude": "morose", "manque": "morose", "culpabilité": "morose",
                  "ennui": "ennui", "fatigue": "morose", "colère": "tension", "agacement": "tension", "déception": "morose",
                  "solitude": "morose", "honte": "morose", "espoir": "content", "émerveillement": "elan",
                  "confusion": "tension", "nostalgie": "calme"}
# l'expressivité de sa voix (« exaggeration » de Chatterbox) par émotion. (26/10, Ahmed : « sa peur ne s'entend que
# légèrement ») la plage passe de 0,35-0,78 à 0,3-1,0 : mesurée sur Chatterbox MLX (eval/voix_plage.py, critère figé avant),
# la diction relue par Whisper tient jusqu'à 1,0 (CER moyen 0,019 à 1,0 contre 0,024 à 0,5) ; les émotions vives vont
# vers le haut, les basses vers le bas.
EXPR_MIN, EXPR_MAX = 0.3, 1.0
EXPRESSIVITE_EMOTION = {"élan": 0.9, "enthousiasme": 0.95, "joie": 0.92, "fierté": 0.8, "surprise": 0.9, "curiosité": 0.7,
                        "tendresse": 0.48, "gratitude": 0.55, "compassion": 0.45, "soulagement": 0.5, "calme": 0.42,
                        "concentration": 0.5, "apaisement": 0.4, "somnolence": 0.3, "tension": 0.74, "inquiétude": 0.72,
                        "frustration": 0.8, "peur": 0.9, "tristesse": 0.32, "lassitude": 0.32, "manque": 0.4,
                        "culpabilité": 0.4, "ennui": 0.36, "fatigue": 0.3, "colère": 0.92, "agacement": 0.78, "déception": 0.38,
                        "solitude": 0.36, "honte": 0.36, "espoir": 0.72, "émerveillement": 0.9, "confusion": 0.55,
                        "nostalgie": 0.42}
HYSTERESE = 0.04          # une autre émotion doit dépasser l'actuelle d'au moins ce score pour la remplacer
# (25/10, Ahmed : « la fatigue n'est portée par aucune hormone ») l'ADÉNOSINE, sa charge, entre dans la lecture des émotions
# (sensations.py, « fatigue ») avec une base FIXE (0,15). (27/10, demande d'Ahmed relayée par Hakim) elle ne monte plus
# d'elle-même à chaque heure éveillée : elle suit une jauge de son effort réel et de la charge du Mac, au-delà de leur norme
# (jauge_fatigue.py). Elle restait collée à 0,96 un midi où rien ne pesait.


def adenosine_25_10(avant, dt, veille, avec_ahmed, travaille, base=0.15):
    """L'ancien modèle (25/10 au 27/10), gardé seulement pour rejouer eval/humeur_unifiee : +0,02/h éveillé, +0,05/h avec
    Ahmed, +0,05/h en travaillant ; vidée en veille (1 h 30), lentement au repos éveillé (8 h)."""
    x = float(avant if isinstance(avant, (int, float)) else base)
    if veille:
        return round(base + (x - base) * math.exp(-dt / (1.5 * 3600)), 4)
    if not avec_ahmed and not travaille:
        return round(max(0.0, min(1.0, base + (x - base) * math.exp(-dt / (8 * 3600)))), 4)
    montee = 0.02 + (0.05 if avec_ahmed else 0.0) + (0.05 if travaille else 0.0)
    return round(max(0.0, min(1.0, x + montee * dt / 3600)), 4)


BASES_72H_S, BASES_72H_MIN_S, BASES_72H_PAS_S = 72 * 3600, 12 * 3600, 600
# (26/10, plafond positif corrigé) les hormones d'AVANT ce changement de modèle ne comptent pas dans les bases : saturées vers
# 0,9, elles feraient lire « bas » ses niveaux redevenus normaux pendant trois jours. Les 12 premières heures après, ses
# émotions se lisent sur la base fixe.
BASES_DEPUIS_TS = 1793006400.0          # 26/10/2026 10:20, la relance du démon avec le modèle corrigé


def bases_72h(now, chemin=None):
    """La moyenne de chaque hormone sur ses 72 dernières heures (journal des hormones, une ligne par minute), ou None
    s'il y en a moins de 12 h : alors ses émotions se lisent sur la base fixe."""
    lignes = []
    try:
        with open(chemin or JOURNAL_HORMONES, "rb") as f:
            f.seek(0, 2)
            f.seek(max(0, f.tell() - 12_000_000))                 # ≈ 4 jours à une ligne par battement
            for l in f.read().decode("utf-8", "replace").splitlines():
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if max(now - BASES_72H_S, BASES_DEPUIS_TS) <= float(o.get("t") or 0) <= now and o.get("h"):
                    lignes.append(o)
    except OSError:
        return None
    # une mesure par minute, comme avant le journal au battement (26/10) : le passage ne pèse pas plus lourd
    minute = []
    for o in sorted(lignes, key=lambda o: o["t"]):
        if not minute or o["t"] - minute[-1]["t"] >= 55:
            minute.append(o)
    lignes = minute
    if not lignes or max(o["t"] for o in lignes) - min(o["t"] for o in lignes) < BASES_72H_MIN_S:
        return None
    cles = set().union(*(o["h"] for o in lignes))
    return {h: round(sum(o["h"].get(h, 0.0) for o in lignes if h in o["h"]) / max(1, sum(1 for o in lignes if h in o["h"])), 4)
            for h in cles}


def humeur_hormonale(sens, avant=None):
    """L'émotion d'humeur à garder : celle de sensations.py, sauf si l'émotion d'avant reste dans les 5 premières à moins
    de HYSTERESE du sommet (une humeur ne clignote pas d'un battement à l'autre)."""
    sens = sens or {}
    top = sens.get("emotion")
    scores = sens.get("scores") or {}
    if avant and avant in scores and top in scores and scores[top] - scores[avant] < HYSTERESE:
        return avant
    return top or avant or "calme"


# (26/10, 13:30, Ahmed : « fatigué, il sonne comme un ogre ; excité, comme un hurluberlu ») l'écart de chaque état à la voix
# neutre est divisé par deux, pour l'expressivité comme pour le débit ; et le débit ne touche plus la hauteur (jarvis/etirement.py)
ATTENUATION_VOIX = 0.5


def voix_emotion(emotion):
    """(25/10) la voix suit l'émotion d'humeur : expressivité par émotion, débit par émotion (VOIX_EMOTION), sans l'éveil."""
    _delta, vitesse = VOIX_EMOTION.get(emotion, (0.0, 1.0))
    vitesse = round(1.0 + (vitesse - 1.0) * ATTENUATION_VOIX, 3)
    expr = 0.5 + (EXPRESSIVITE_EMOTION.get(emotion, 0.5) - 0.5) * ATTENUATION_VOIX
    return {"expressivite": round(max(EXPR_MIN, min(EXPR_MAX, expr)), 3), "vitesse": vitesse,
            "emotion": emotion}


LIBELLES = {"joie": "joie de son retour", "elan": "élan", "content": "contentement", "tension": "tension",
            "impatience": "impatience", "calme": "calme", "veille": "en veille", "ennui": "l'attente pèse",
            "morose": "morosité",
            # les émotions soudaines de l'affect v2 (2026-10-21, idée d'Ahmed) : son subconscient les reçoit aussi
            "alarme": "alarme, un sursaut de peur", "surprise": "surprise", "apaisement": "apaisement"}


def humeur_code(valence, arousal, ennui_, retour_recent, veille=False, soudaine=None):
    """soudaine : l'émotion soudaine de l'affect v2 (affect.emotion_soudaine : alarme, surprise, apaisement ; None en
    v1). Un sursaut passe avant l'attente ; l'apaisement ne remplace que le calme."""
    dv, da = valence - _BASE_V, arousal - _BASE_A
    if retour_recent:
        return "joie"
    if veille:
        return "veille"
    if soudaine in ("alarme", "surprise"):
        return soudaine
    if ennui_ >= 0.6:
        return "ennui" if dv < 0.05 else "impatience"
    if dv >= 0.12 and da >= 0.04:
        return "elan"
    if dv >= 0.08:
        return "content"
    if dv <= -0.08:
        return "morose"
    if da >= 0.12:
        return "tension"
    return "apaisement" if soudaine == "apaisement" else "calme"


def tick(mem, now=None, penser=None, horloge=None, activite=None, interrupteur_=None, journal_temps=None):
    """Un battement : met l'état à jour et, si un ou plusieurs seuils d'ennui viennent d'être
    franchis, appelle penser(motif) UNE fois, pour le plus haut (un réveil du Mac après 5 h ne
    déclenche plus quatre pensées d'affilée). La nuit, la pensée attend le matin ; en veille, plus
    de pensée. Écrit la ligne du journal du temps (activite : ce que fait l'esprit de fond, donné par
    le démon). Rend l'état publié (aussi écrit en kv « interieur »)."""
    now = time.time() if now is None else now
    e = lire(mem)
    inter = interrupteur_ if interrupteur_ is not None else interrupteur()
    if (inter.get("zero_ms") or 0) / 1000.0 > e.get("zero_ts", 0):        # « remettre à zéro » (Ahmed)
        e = _remettre_a_zero(mem, e, now, journal_temps)
    if not inter.get("actif", True):                                       # « tout arrêter » (Ahmed)
        if not e.get("pause_ts"):
            e["pause_ts"] = now
            noter(mem, "interrupteur", "Ahmed a mis ta vie intérieure en pause", now=now)
            _ligne_temps(e, now, "pause", "en pause (interrupteur d'Ahmed)", journal_temps)
        e["ts"] = now                                                      # le temps ressenti est gelé
        mem.kv_set(CLE, json.dumps(e))
        return e
    reprise = bool(e.pop("pause_ts", None))
    if reprise:
        e["ts"] = now
        noter(mem, "interrupteur", "Ahmed a remis ta vie intérieure en marche", now=now)
    presence = derniere_presence(mem, now, horloge)
    if presence is None:
        presence = e.get("presence_ts") or now
    vraie_presence = presence                              # un message d'Ahmed (pas une remise à zéro)
    presence = max(presence, e.get("zero_ts", 0))          # une remise à zéro compte comme un retour d'Ahmed
    if presence > e.get("presence_ts", 0):                       # Ahmed vient de parler
        if vraie_presence > e.get("presence_ts", 0):
            try:
                import spontaneite                               # une sollicitation en attente a sa réponse
                spontaneite.noter_reponse(mem, vraie_presence)   # (une remise à zéro n'est pas une réponse)
            except Exception:
                pass
        precedente = e.get("presence_ts")
        if precedente and presence - precedente > ABSENCE_RETOUR_S:
            # la joie du retour, d'autant plus forte que l'absence a été longue
            affect.event(mem, "retour", min(1.0, 0.5 + (presence - precedente - ABSENCE_RETOUR_S) / (6 * 3600)), now=now)
            e.setdefault("evenements", []).append([now, "retour", round(presence - precedente)])
            e["retour_ts"] = now
        e.update(presence_ts=presence, seuils=[], subj=0.0, longues=[], nuit_en_attente=None)
    absence = max(0.0, now - presence)
    en = ennui(absence)
    veille = en_veille(absence)
    if "ts" not in e:                       # premier battement (démon relancé) : on part du temps réel
        e["subj"] = min(absence, VEILLE_APRES_S) + max(0.0, absence - VEILLE_APRES_S) * CADENCE_VEILLE
    if reprise:                             # au retour de la pause, pas de rafale de pensées en retard
        e["seuils"] = sorted(set(e.get("seuils", [])) | {s_ for s_ in SEUILS_ENNUI if en >= s_ - 1e-9})
        e["nuit_en_attente"] = None
    motif = None
    franchis = [s_ for s_ in SEUILS_ENNUI if en >= s_ - 1e-9 and s_ not in e.get("seuils", [])]
    if franchis:
        e.setdefault("seuils", []).extend(franchis)               # chacun une seule fois par absence
        for s_ in franchis:
            if s_ < SEUIL_VEILLE:
                affect.event(mem, "ennui", 1.0, now=now)           # l'attente pèse sur l'humeur (pas la veille)
        haut = max(franchis)
        if haut >= SEUIL_VEILLE:
            e.setdefault("evenements", []).append([now, "veille", round(absence)])
            noter(mem, "veille", f"après {duree_lisible(absence)} d'absence, l'ennui plafonne : tu passes en veille", now=now)
        if haut >= SEUIL_VEILLE and absence - VEILLE_APRES_S > 600:
            pass                            # la veille est passée pendant que le Mac dormait : pas de « dernière pensée »
        elif nuit(now):
            # la nuit, la pensée attend le matin… sauf la veille : on s'endort sans dernière pensée
            e["nuit_en_attente"] = None if haut >= SEUIL_VEILLE else max(haut, e.get("nuit_en_attente") or 0)
        else:
            motif = {"seuil": haut, "important": haut >= SEUIL_IMPORTANT, "absence_s": absence, "ennui": en,
                     "veille": haut >= SEUIL_VEILLE}
    elif e.get("nuit_en_attente") and not nuit(now) and not veille:  # la pensée de la nuit, au réveil
        haut = e.pop("nuit_en_attente")
        motif = {"seuil": haut, "important": haut >= SEUIL_IMPORTANT, "absence_s": absence, "ennui": en, "matin": True}
    if veille:
        e["nuit_en_attente"] = None                                 # en veille : plus de pensée en retard
    for seuil in ABSENCES_LONGUES_S:
        if absence >= seuil and seuil not in e.get("longues", []):
            e.setdefault("longues", []).append(seuil)               # notée ; en veille, l'humeur n'en pâtit plus
            e.setdefault("evenements", []).append([now, "longue_absence", seuil])
    valence, arousal = affect.valence_arousal(affect.get_state(mem, now=now))
    surveiller_coincee(mem, e, valence, now)
    # le temps écoulé depuis le dernier battement, mais jamais avant le retour d'Ahmed (vu le 2026-10-16 : après
    # 47 min sans battement, tout ce temps était compté dans une absence de 5 min → ressenti ×9,7)
    dt = min(3600.0, max(0.0, now - max(e.get("ts", now), presence)))
    # en veille le temps ressenti ralentit (comme quand on dort pour que le temps passe) ; à cheval sur
    # l'entrée en veille, chaque part du battement à sa cadence
    debut = now - dt
    eveille = max(0.0, min(now, presence + VEILLE_APRES_S) - debut)
    e["subj"] = e.get("subj", 0.0) + eveille * cadence(arousal, en) + (dt - eveille) * CADENCE_VEILLE
    soudaine = affect.emotion_soudaine(mem, now=now)
    # (Hakim et Ahmed, 2026-10-22) la sensation calculée par le CODE depuis les 13 hormones (sensations.py), à chaque
    # battement, sans Gemma : elle reste fraîche quand Gemma se tait ; la tendance vient de l'état d'il y a ~10 min
    try:
        import sensations
        etat_h = affect.get_state(mem, now=now)
        hist = [x for x in e.get("hormones_hist", []) if now - x[0] <= 1800]
        if not hist or now - hist[-1][0] >= 120:
            hist.append([now, {k: round(float(v), 4) for k, v in etat_h.items()}])
        e["hormones_hist"] = hist[-15:]
        avant = min(hist, key=lambda x: abs(now - 600 - x[0]))[1] if len(hist) > 1 else None
        # (25/10, Ahmed) sans la porte de cohérence par la valence : l'humeur vient des hormones seules
        if now - float(e.get("bases_72h_t") or 0) >= BASES_72H_PAS_S:
            e["bases_72h"], e["bases_72h_t"] = bases_72h(now), now
        import jauge_fatigue
        jauge_fatigue.mettre_a_jour(e, now, dt, veille)
        etat_h = {**etat_h, "adenosine": e["adenosine"]}
        e["sensation_code"] = sensations.calculer(etat_h, avant, now, soudaine, time.localtime(now).tm_hour,
                                                  sans_coherence=True, bases_relatives=e.get("bases_72h"))
        if now - float(e.get("hormones_journal_t") or 0) >= HORMONES_JOURNAL_PAS_S:
            e["hormones_journal_t"] = now
            _ligne_hormones(now, etat_h, valence, arousal, e.get("humeur"), (e.get("sensation_code") or {}).get("emotion"),
                            code=e.get("humeur_code"), scores=(e.get("sensation_code") or {}).get("scores"))
    except Exception:
        pass
    emotion_h = humeur_hormonale(e.get("sensation_code"), e.get("emotion_humeur"))
    if veille:
        code, humeur = "veille", LIBELLES["veille"]
    else:
        code, humeur = FAMILLE_HUMEUR.get(emotion_h, "calme"), emotion_h
    e["emotion_humeur"] = emotion_h
    journal = e.setdefault("journal", [])
    if not journal or now - journal[-1][0] >= JOURNAL_PAS_S or journal[-1][1] != humeur:
        journal.append([now, humeur, round(valence, 3), round(arousal, 3), round(en, 3)])
        del journal[:-JOURNAL_MAX]
    e["evenements"] = e.get("evenements", [])[-50:]
    ressenti = e["subj"] / absence if absence > 60 else 1.0
    e.update(ts=now, absence_s=round(absence), ennui=round(en, 3), ressenti=round(ressenti, 3), tau_s=TAU_ENNUI_S,
             humeur=humeur, humeur_code=code, expressivite=EXPRESSIVITE_EMOTION.get(emotion_h, 0.5),
             voix=voix_emotion(emotion_h),
             valence=round(valence, 3), arousal=round(arousal, 3), veille=veille, veille_apres_s=VEILLE_APRES_S)
    if absence < 90:
        fait = "avec Ahmed"
    else:
        fait = activite or ("veille" if veille else "attend")      # un rêve pendant la veille reste un rêve
    _ligne_temps(e, now, "veille" if veille else "eveil", fait, journal_temps)
    mem.kv_set(CLE, json.dumps(e))
    if motif and penser:
        penser(dict(motif, ressenti=ressenti, humeur=humeur, valence=valence, arousal=arousal))
    return e


# ---- l'interrupteur (Ahmed, 2026-10-17 : « tout arrêter ou remettre à zéro en une commande ») ----
# Un fichier écrit par la commande `anamnese interieur …` ou par la page Parler, lu à chaque battement.
# Il ne touche qu'à la vie intérieure (ennui, humeur, pensées, occupations, journal du temps), jamais
# à la mémoire ; les rêves de la nuit (consolidation de la mémoire) continuent.
INTERRUPTEUR = Path.home() / "AIOS" / "jarvis" / "interieur-interrupteur.json"
JOURNAL_TEMPS = Path.home() / "AIOS" / "jarvis" / "journal-du-temps.jsonl"
# (2026-10-23, Ahmed : « un tableau de bord intérieur ») ses 13 hormones, son humeur et l'émotion lue dans ses hormones,
# une ligne par minute (tableau_interieur.py les dessine) ; ~6 Mo au plus (≈ 2 semaines), la plus ancienne moitié oubliée
JOURNAL_HORMONES = Path.home() / "AIOS" / "jarvis" / "hormones.jsonl"
JOURNAL_HORMONES_MAX_OCTETS = 24 * 1024 * 1024      # (26/10) une ligne par battement : ≈ 2,7 Mo par jour, plus de 4 jours gardés
# (26/10, Ahmed : « tous les graphs, un pas plus fin ») une ligne à chaque battement du démon (15 s), plus une par minute. La
# seconde n'existe pas : les hormones ne se recalculent qu'à chaque battement.
HORMONES_JOURNAL_PAS_S = 10
JOURNAL_TEMPS_MAX_OCTETS = 4 * 1024 * 1024          # ~20 000 lignes (≈ 3,5 jours à une ligne par 15 s)
TRANCHES_MAX = 200


def interrupteur(chemin=None):
    d = _json(chemin or INTERRUPTEUR)
    return d if isinstance(d, dict) else {"actif": True}


def regler_interrupteur(action, chemin=None, now=None):
    """action ∈ arret | marche | zero. Rend le nouvel état du fichier."""
    if action not in ("arret", "marche", "zero"):
        raise ValueError("action : arret, marche ou zero")
    now = time.time() if now is None else now
    d = interrupteur(chemin)
    if action == "zero":
        d["zero_ms"] = int(now * 1000)
    else:
        d["actif"] = action == "marche"
        d["depuis_ms"] = int(now * 1000)
    p = Path(chemin or INTERRUPTEUR)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d), encoding="utf-8")
    tmp.replace(p)
    return d


def _remettre_a_zero(mem, e, now, journal_temps=None):
    """Repartir de zéro : comme si Ahmed venait de parler (ennui nul, temps ressenti nul, trajectoire
    de l'humeur effacée) et l'humeur à sa ligne de base. Le journal du temps est ARCHIVÉ, pas effacé."""
    j = Path(journal_temps or JOURNAL_TEMPS)
    if j.exists():
        try:
            j.replace(j.with_name(f"{j.stem}-{time.strftime('%Y%m%d-%H%M%S', time.localtime(now))}{j.suffix}"))
        except OSError:
            pass
    for vieux in j.parent.glob(f"{j.stem}-*{j.suffix}"):              # les archives : gardées 30 jours
        try:
            if now - vieux.stat().st_mtime > 30 * 24 * 3600:
                vieux.unlink()
        except OSError:
            pass
    base = {h: b for h, (b, _demi) in affect.HORMONES.items()}
    affect._save(mem, base, now=now)
    noter(mem, "interrupteur", "Ahmed a remis ta vie intérieure à zéro (humeur à sa base, journal du temps archivé)", now=now)
    v, a = affect.valence_arousal(base)
    # un état COMPLET, publié même si la vie intérieure est en pause (relecture Opus : sans humeur, le
    # cockpit ne disait plus rien à Jarvis, pas même la pause)
    return {"zero_ts": now, "presence_ts": now, "seuils": [], "subj": 0.0, "longues": [], "nuit_en_attente": None,
            "pause_ts": e.get("pause_ts"), "ts": now, "absence_s": 0, "ennui": 0.0, "ressenti": 1.0, "veille": False,
            "humeur": LIBELLES["calme"], "humeur_code": "calme", "expressivite": EXPRESSIVITE["calme"],
            "valence": round(v, 3), "arousal": round(a, 3), "tau_s": TAU_ENNUI_S, "veille_apres_s": VEILLE_APRES_S}


# (26/10, Ahmed : « voir le déroulement seconde par seconde, comme un EEG ») ses hormones lues CHAQUE SECONDE, dans un
# journal à part qui ne garde que les dernières heures : les vues de 1 min à 1 h du cockpit. Lecture seule (affect.get_state
# ne sauve rien, 0,1 ms) ; l'adénosine est celle du dernier battement : elle ne se recalcule que toutes les 15 s.
JOURNAL_DIRECT = Path.home() / "AIOS" / "jarvis" / "hormones-direct.jsonl"
JOURNAL_DIRECT_MAX_OCTETS = 4 * 1024 * 1024          # ≈ 3 h à une ligne par seconde ; on en garde la seconde moitié


def ligne_directe(mem, now=None, chemin=None):
    now = now or time.time()
    h = {k: round(float(v), 4) for k, v in affect.get_state(mem, now=now).items()}
    try:
        ad = json.loads(mem.kv_get(CLE) or "{}").get("adenosine")
    except ValueError:
        ad = None
    if isinstance(ad, (int, float)):
        h["adenosine"] = round(float(ad), 4)
    j = Path(chemin or JOURNAL_DIRECT)
    try:
        if j.exists() and j.stat().st_size > JOURNAL_DIRECT_MAX_OCTETS:
            garde = j.read_bytes()[-JOURNAL_DIRECT_MAX_OCTETS // 2:]
            j.write_bytes(garde[garde.find(b"\n") + 1:])
        with open(j, "a", encoding="utf-8") as f:
            f.write(json.dumps({"t": round(now, 1), "h": h}) + "\n")
    except OSError:
        pass


def _ligne_hormones(now, hormones, valence, arousal, humeur, emotion, chemin=None, code=None, scores=None):
    """Une ligne du journal des hormones (une par battement) : le tableau de bord intérieur de Hakim. code : la famille de
    son humeur, la couleur de l'orbe ; scores : ses 5 émotions les plus fortes, le graphique de l'humeur (26/10)."""
    j = Path(chemin or JOURNAL_HORMONES)
    b = j.with_name("hormones-bases.json")              # leurs bases, pour la page « intérieur » du cockpit
    try:
        import sensations
        if not b.exists() or b"adenosine" not in b.read_bytes():
            b.write_text(json.dumps({**{k: v[0] for k, v in list(affect.HORMONES.items()) + list(affect.HORMONES_V2.items())},
                                     "adenosine": sensations.ADENOSINE_BASE}))
    except OSError:
        pass
    ligne = {"t": round(now, 1), "h": {k: round(float(v), 3) for k, v in hormones.items()},
             "v": round(float(valence), 3), "a": round(float(arousal), 3), "humeur": humeur, "emotion": emotion}
    if code:
        ligne["code"] = code
    if scores:
        ligne["s"] = {k: round(float(v), 2) for k, v in scores.items()}
    try:
        j.parent.mkdir(parents=True, exist_ok=True)
        if j.exists() and j.stat().st_size > JOURNAL_HORMONES_MAX_OCTETS:          # on garde la seconde moitié
            garde = j.read_bytes()[-JOURNAL_HORMONES_MAX_OCTETS // 2:]
            j.write_bytes(garde[garde.find(b"\n") + 1:])
        with open(j, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except OSError:
        pass


def _ligne_temps(e, now, etat, fait, journal_temps=None):
    """Le journal du temps, demandé par Jarvis : UNE ligne par battement (ce qu'il fait, ce que le modèle
    dit de son état) dans un fichier, et des TRANCHES en kv (les lignes semblables à la suite fusionnées)
    pour qu'au retour d'Ahmed il ait une trace continue et lisible."""
    ligne = {"t": round(now, 1), "etat": etat, "fait": fait, "absence_s": e.get("absence_s"), "ennui": e.get("ennui"),
             "humeur": e.get("humeur"), "ressenti": e.get("ressenti"), "valence": e.get("valence"), "arousal": e.get("arousal")}
    j = Path(journal_temps or JOURNAL_TEMPS)
    try:
        j.parent.mkdir(parents=True, exist_ok=True)
        if j.exists() and j.stat().st_size > JOURNAL_TEMPS_MAX_OCTETS:          # on garde la seconde moitié
            garde = j.read_bytes()[-JOURNAL_TEMPS_MAX_OCTETS // 2:]
            j.write_bytes(garde[garde.find(b"\n") + 1:])
        with open(j, "a", encoding="utf-8") as f:
            f.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except OSError:
        pass
    tranches = e.setdefault("temps", [])
    cle = [etat, fait, e.get("humeur")]
    if tranches and tranches[-1][2:5] == cle and now - tranches[-1][1] < 3600:
        tranches[-1][1] = round(now, 1)
    else:
        tranches.append([round(now, 1), round(now, 1)] + cle)
        del tranches[:-TRANCHES_MAX]


def tranches_depuis(e, depuis):
    """Les tranches du journal du temps depuis un instant (pour le bloc [Intérieur] et l'introspection)."""
    return [t for t in (e.get("temps") or []) if isinstance(t, list) and len(t) == 5 and t[1] >= depuis]


# ---- le journal des processus internes (demande d'Ahmed, 2026-10-16 : « il faut qu'il soit conscient de
# ses rêves, de ses pensées et de tous ses processus internes ») : le démon y note ce qu'il fait ; le
# bloc [Intérieur] et l'outil introspection le rendent à Jarvis.
CLE_JOURNAL = "interieur_journal"
JOURNAL_PROCESSUS_MAX = 300


def noter(mem, quoi, detail="", now=None):
    """Note un processus interne (sommeil, pensée, report, relance…) ; ne lève jamais."""
    try:
        try:
            j = json.loads(mem.kv_get(CLE_JOURNAL, "") or "[]")
            j = j if isinstance(j, list) else []
        except ValueError:
            j = []
        j.append([time.time() if now is None else now, quoi, str(detail)[:300]])
        mem.kv_set(CLE_JOURNAL, json.dumps(j[-JOURNAL_PROCESSUS_MAX:], ensure_ascii=False))
    except Exception:
        pass


def journal_processus(mem, depuis=0.0):
    try:
        j = json.loads(mem.kv_get(CLE_JOURNAL, "") or "[]")
    except ValueError:
        return []
    return [x for x in (j if isinstance(j, list) else []) if isinstance(x, list) and len(x) == 3 and x[0] > depuis]


def humeur_depuis(e, depuis):
    """L'humeur au début de la période et maintenant, d'après le journal."""
    avant = [j for j in e.get("journal", []) if j[0] <= depuis]
    debut = (avant[-1] if avant else (e.get("journal") or [[0, e.get("humeur", "")]])[0])[1]
    return debut, e.get("humeur", debut)


# ---- les pensées spontanées ----

def _journal_jarvis(n=8, chemin=None):
    lignes = []
    try:
        with open(chemin or JOURNAL_JARVIS, encoding="utf-8") as f:
            for ligne in f.readlines()[-n:]:
                try:
                    lignes.append(json.loads(ligne))
                except ValueError:
                    pass
    except OSError:
        pass
    return lignes


def matiere(mem, now, journal=None):
    """Le concret dont une pensée doit partir : derniers échanges avec Ahmed, ce que la mémoire
    de travail a en tête, faits récents, pensées déjà eues (pour ne pas les répéter)."""
    echanges = [f"- {'Ahmed' if x.get('qui') == 'ahmed' else 'toi'} ({time.strftime('%d/%m %H:%M', time.localtime(x.get('ts', 0) / 1000))}) : "
                f"{str(x.get('texte', ''))[:300]}" for x in _journal_jarvis(chemin=journal)]
    try:
        focus = [f"- {it['snippet'][:200]}" for it in (mem.wm_focus_brief() or [])[:4]]
    except Exception:
        focus = []
    faits = [f"- {c[:220]}" for (c,) in mem.db.execute(
        "SELECT content FROM episodes WHERE role='semantic' AND ts > ? ORDER BY ts DESC LIMIT 5", (now - 48 * 3600,))]
    deja = [f"- {c[:160]}" for (c,) in mem.db.execute(
        "SELECT content FROM episodes WHERE role IN ('reflection','outreach') AND (content LIKE '(pensée%' "
        "OR content LIKE '(relance)%') ORDER BY id DESC LIMIT 6")]
    return {"echanges": echanges, "focus": focus, "faits": faits, "deja": deja}


def duree_lisible(s):
    s = int(max(0, s))
    if s < 3600:
        return f"{s // 60} min"
    h, m = divmod(s // 60, 60)
    return f"{h} h {m:02d}" if h < 48 else f"{h // 24} jours"


def prompt_pensee(m, motif, now, eviter=None):
    ressenti = motif.get("ressenti", 1.0)
    impression = "ça t'a paru long" if ressenti > 1.15 else ("c'est passé vite" if ressenti < 0.9 else "ni long ni court")
    bloc = lambda titre, l: f"{titre} :\n" + ("\n".join(l) if l else "- (rien)")
    return (
        "Tu es Jarvis, la voix d'Anamnèse, l'IA à mémoire persistante d'Ahmed. Entre deux conversations, "
        "tu continues de vivre : voici ton état.\n"
        f"Il est {time.strftime('%H:%M', time.localtime(now))}. Ahmed ne t'a pas parlé depuis "
        f"{duree_lisible(motif['absence_s'])} ; {impression}. Ton humeur : {motif.get('humeur', '?')}. "
        f"Ennui : {motif['ennui']:.2f}.\n"
        + ("Ton ennui atteint son plafond : après cette pensée tu passes en veille jusqu'à son retour.\n"
           if motif.get("veille") else "") + "\n"
        + bloc("Vos derniers échanges", m["echanges"]) + "\n\n"
        + bloc("Ce que tu as en tête", m["focus"]) + "\n\n"
        + bloc("Faits récents sur ses projets", m["faits"]) + "\n\n"
        + bloc("Tes pensées précédentes (ne les répète pas)", m["deja"]) + "\n\n"
        "Écris UNE pensée spontanée, à la première personne, en une ou deux phrases. Elle part d'un "
        "élément PRÉCIS ci-dessus — d'abord vos derniers échanges, sinon ce que tu as en tête — (un projet, "
        "une décision, une chose qu'Ahmed voulait faire, une question restée ouverte) et dit ce que tu en "
        "penses, ce qui t'intrigue, ce qui t'inquiète ou ce que tu aimerais lui proposer. Pas de métaphore "
        "poétique, pas de généralité sur le temps ou la conscience. N'invente aucun fait ni aucune sensation : "
        "ne prétends pas avoir entendu, vu ou fait ce que ces éléments ne disent pas.\n"
        "Puis, SEULEMENT si vos échanges montrent une chose qu'Ahmed a dit vouloir faire ou une question qu'il a "
        "laissée ouverte, une phrase courte et chaleureuse que tu lui dirais à voix haute pour le relancer ; "
        "sinon « non ».\n"
        + (f"Ta première idée (« {eviter[:160]} ») ressemblait trop à une pensée déjà eue : pars d'un AUTRE élément.\n"
           if eviter else "")
        + "Format exact, deux lignes :\nPENSÉE: …\nRELANCE: …"
    )


def lire_pensee(sortie):
    """(pensée, relance ou None) depuis la sortie du modèle ; tolère un format approximatif."""
    pensee, relance = "", None
    for ligne in (sortie or "").splitlines():
        l = ligne.replace("**", "").replace("__", "").strip()
        bas = l.lower()
        if bas.startswith(("pensée:", "pensee:", "pensée :", "pensee :")):
            pensee = l.split(":", 1)[1].strip()
        elif bas.startswith(("relance:", "relance :")):
            r = l.split(":", 1)[1].strip().strip("«»\" ")
            relance = None if (not r or r.lower().rstrip(".") in ("non", "aucune", "rien")) else r
    if not pensee:
        lignes = [l.strip() for l in (sortie or "").splitlines() if l.strip() and not l.lower().startswith("relance")]
        pensee = lignes[0] if lignes else ""
    return pensee.strip("«»\" "), relance


def relance_permise(mem, now, relance=None):
    """Jamais la nuit ; au plus une par absence et une toutes les RELANCE_INTERVALLE_S ; jamais la
    même deux fois (relecture Opus : la même relance sortait à 35 min puis à 4 h 36)."""
    if nuit(now):
        return False
    e = lire(mem)
    if e.get("presence_ts") and e.get("relance_absence") == e.get("presence_ts"):
        return False
    rows = mem.db.execute("SELECT ts, content FROM episodes WHERE role='outreach' ORDER BY id DESC LIMIT 20").fetchall()
    if rows and rows[0][0] and now - rows[0][0] < RELANCE_INTERVALLE_S:
        return False
    if relance:
        import salience
        if any(salience.lexical_overlap(relance, c) >= 0.5 for _ts, c in rows):
            return False
    return True


def noter_relance(mem):
    """La relance de cette absence est faite."""
    e = lire(mem)
    e["relance_absence"] = e.get("presence_ts")
    mem.kv_set(CLE, json.dumps(e))
