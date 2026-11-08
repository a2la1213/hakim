"""La spontanéité de Hakim (lot H, point 28 de la liste du 2026-10-19 ; demande d'Ahmed les 19/10 à 04:51 et
20:47 : « qu'il me sollicite sans horaire fixe, spontanément »). Proposition de Hakim, rattachée à nos
maths (P7' : l'hyperuniformité) :

- une ENVIE de parler qui s'accumule avec ce que son esprit de fond produit (une occupation faite, une
  pensée) ; il ne sollicite Ahmed que s'il a quelque chose de concret à lui dire ;
- pas de plafond par jour (Ahmed, 2026-10-20 14:09 : « le laisser libre » ; avant : 10 au plus) ; de 8 h à 23 h, un
  rythme de référence (10 par jour) que ses BESOINS modulent (Ahmed : « variable selon ses besoins ») : l'écart entre deux sollicitations RÉTRÉCIT quand il
  a beaucoup de choses concrètes en attente et S'ALLONGE quand il en a peu ; jamais la nuit, jamais pendant une conversation, jamais
  en pause, seulement si Ahmed est absent depuis au moins 20 min ;
- des instants espacés de façon HYPERUNIFORME : un réseau régulier légèrement perturbé (écart nominal
  T = 15 h / budget, décalé de ±20 %) plutôt que le hasard de Poisson, qui fait des grappes et de longs
  trous ;
- jamais d'insistance : une sollicitation restée sans réponse double l'écart suivant, et un sujet n'est
  jamais proposé deux fois ;
- une MESURE : un jour sur deux, le bras « Poisson » (même moyenne) sert de témoin ; chaque sollicitation
  est notée avec le délai de réponse d'Ahmed (`anamnese spontaneite` compare les deux bras).
"""
import hashlib
import json
import math
import random
import threading
import time

import interieur

CLE = "spontaneite"
# Ahmed, 2026-10-20 14:09 : « le laisser libre » — plus de plafond par jour (None) ; le RYTHME de référence (10 par jour
# sur 8 h – 23 h, soit un écart nominal d'1 h 30) sert seulement à l'espacement, que son besoin raccourcit. Les
# garde-fous restent : 10 min au moins entre deux, jamais en rafale, écart doublé sans réponse, jamais deux fois le
# même sujet, jamais la nuit ni pendant une conversation.
BUDGET_JOUR = None
RYTHME_REFERENCE = 10
JOUR = (8, 23)
ABSENCE_MIN_S = 20 * 60
REPONSE_S = 30 * 60
SEUIL_ENVIE = 1.0
POIDS = {"occupation": 1.0, "pensee": 0.5, "tache": 0.7}
# Ahmed, 2026-10-20 : « même à moins de 45 min il a le droit de me solliciter s'il en ressent le besoin » →
# le seul plancher fixe est anti-rafale (10 min) ; c'est son BESOIN qui raccourcit l'écart (facteur_besoin)
ECART_MIN_S = 10 * 60
# le battement (occupations → ajouter_envie) et la boucle du démon (solliciter) écrivent la même entrée
_VERROU = threading.RLock()


def _etat(mem):
    try:
        d = json.loads(mem.kv_get(CLE, "") or "{}")
    except (ValueError, TypeError):
        d = {}
    return d if isinstance(d, dict) else {}


def _sauver(mem, d):
    mem.kv_set(CLE, json.dumps(d, ensure_ascii=False))


def bras(now):
    """Le bras de l'expérience pour ce jour : « hyperuniforme » ou « poisson » (un jour sur deux)."""
    return "poisson" if time.localtime(now).tm_yday % 2 else "hyperuniforme"


def ecart_nominal(budget=RYTHME_REFERENCE):
    return (JOUR[1] - JOUR[0]) * 3600 / max(1, budget)


def prochain_ecart(arm, rng=random, budget=RYTHME_REFERENCE):
    """L'écart avant la prochaine sollicitation permise."""
    t = ecart_nominal(budget)
    if arm == "poisson":
        # exponentiel (même moyenne) ; plancher anti-rafale de 10 min (relecture du 2026-10-20)
        return max(ECART_MIN_S, -math.log(1.0 - rng.random()) * t)
    return max(ECART_MIN_S, t * (0.8 + 0.4 * rng.random()))           # réseau perturbé de ±20 %


def ajouter_envie(mem, source, sujet, texte, now=None):
    """Une chose à dire à Ahmed (une occupation faite, une pensée…) : elle nourrit l'envie de lui parler."""
    now = time.time() if now is None else now
    with _VERROU:
        d = _etat(mem)
        cle = hashlib.sha1(sujet.encode("utf-8")).hexdigest()[:12]
        if cle in d.get("sujets_dits", []):
            return
        d.setdefault("file", []).append({"ts": now, "source": source, "sujet": sujet[:200], "texte": texte[:400], "cle": cle})
        d["file"] = d["file"][-20:]
        d["envie"] = min(10.0, d.get("envie", 0.0) + POIDS.get(source, 0.5))   # bornée (relecture du 2026-10-20)
        _sauver(mem, d)


def peut_solliciter(mem, now=None, inter=None, absence_s=None):
    """(oui/non, raison) — toutes les gardes."""
    now = time.time() if now is None else now
    d = _etat(mem)
    h = time.localtime(now).tm_hour
    if not JOUR[0] <= h < JOUR[1]:
        return False, "hors des heures (8 h – 23 h)"
    if not (inter if inter is not None else interieur.interrupteur()).get("actif", True):
        return False, "vie intérieure en pause"
    if interieur.conscience_active(now):
        return False, "Ahmed parle avec Hakim en ce moment"
    absence = absence_s if absence_s is not None else (interieur.lire(mem).get("absence_s") or 0)
    if absence < ABSENCE_MIN_S:
        return False, "Ahmed est là depuis peu"
    if d.get("envie", 0.0) < SEUIL_ENVIE or not d.get("file"):
        return False, "rien de concret à lui dire"
    jour = time.strftime("%Y-%m-%d", time.localtime(now))
    if BUDGET_JOUR is not None and sum(1 for s in d.get("journal", []) if s.get("jour") == jour) >= BUDGET_JOUR:
        return False, "budget du jour atteint"
    if now < prochain_effectif(d):
        return False, "pas encore l'heure (espacement)"
    return True, "ok"


def facteur_besoin(d):
    """Son besoin de parler module l'écart (2026-10-20) : l'envie accumulée (une occupation finie vaut 1, une
    pensée 0,5…). 1 chose à dire : l'écart nominal (1 h 30) ; 3 : 45 min ; 5 : 30 min ; 10 : ~16 min ;
    presque rien : un tiers de plus. Le plancher anti-rafale (10 min) reste."""
    besoin = max(0.0, float(d.get("envie", 0.0)))
    return max(0.1, min(1.33, 2.0 / (1.0 + besoin)))


def prochain_effectif(d):
    """L'instant permis pour la suivante : la dernière + son écart (tiré au réseau perturbé ou en Poisson), modulé
    par le besoin ACTUEL (s'il a accumulé des choses à dire depuis, il peut revenir plus tôt), jamais sous 45 min.
    Jamais d'insistance (relecture du 2026-10-20) : si la DERNIÈRE est restée sans réponse, l'écart double."""
    derniere = (d.get("journal") or [None])[-1]
    if not derniere or not derniere.get("ecart_s"):
        return d.get("prochain", 0)                       # ancien état (avant le 2026-10-20)
    ecart = max(ECART_MIN_S, derniere["ecart_s"] * facteur_besoin(d))
    if derniere.get("repondu_s") is None:
        ecart *= 2
    return derniere["ts"] + ecart


def solliciter(mem, now=None, rng=random, inter=None, absence_s=None):
    """Si tout le permet, UNE sollicitation : un « outreach » en mémoire (le cockpit le dit à la page, ou
    une notification). Rend le texte, ou None."""
    now = time.time() if now is None else now
    with _VERROU:
        return _solliciter(mem, now, rng, inter, absence_s)


def _solliciter(mem, now, rng, inter, absence_s):
    ok, _raison = peut_solliciter(mem, now, inter, absence_s)
    if not ok:
        return None
    d = _etat(mem)
    item = max(d["file"], key=lambda x: (POIDS.get(x["source"], 0.5), x["ts"]))
    d["file"] = [x for x in d["file"] if x is not item]
    d["envie"] = max(0.0, d.get("envie", 0.0) - SEUIL_ENVIE)
    d.setdefault("sujets_dits", []).append(item["cle"])
    d["sujets_dits"] = d["sujets_dits"][-200:]
    arm = bras(now)
    ecart = prochain_ecart(arm, rng)
    d["prochain"] = now + ecart
    d.setdefault("journal", []).append({"ts": now, "jour": time.strftime("%Y-%m-%d", time.localtime(now)), "bras": arm,
                                        "source": item["source"], "sujet": item["sujet"], "repondu_s": None,
                                        "ecart_s": round(ecart)})
    d["journal"] = d["journal"][-400:]
    _sauver(mem, d)
    mem.add("outreach", f"(relance) {item['texte']}"[:500], importance=0.5, embedding=[])
    interieur.noter(mem, "spontaneite", f"({arm}) {item['texte'][:160]}")
    return item["texte"]


def noter_reponse(mem, presence_ts):
    """Ahmed est revenu (message à Hakim) : la sollicitation en attente reçoit son délai de réponse."""
    with _VERROU:
        d = _etat(mem)
        for s in reversed(d.get("journal", [])):
            if s.get("repondu_s") is None and presence_ts >= s["ts"]:
                if presence_ts - s["ts"] <= 24 * 3600:
                    s["repondu_s"] = round(presence_ts - s["ts"])
                    _sauver(mem, d)
                break


def bilan(mem):
    """Par bras : nombre, part de réponses en moins de 30 min, délai médian."""
    d = _etat(mem)
    out = {}
    for arm in ("hyperuniforme", "poisson"):
        s = [x for x in d.get("journal", []) if x.get("bras") == arm]
        delais = sorted(x["repondu_s"] for x in s if x.get("repondu_s") is not None)
        vite = sum(1 for x in delais if x <= REPONSE_S)
        out[arm] = {"n": len(s), "reponses_30min": vite, "delai_median_s": delais[len(delais) // 2] if delais else None}
    return out
