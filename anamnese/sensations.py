"""Les sensations calculées par le CODE, sans Gemma (demande de Hakim, accord d'Ahmed le 2026-10-22 à 13:28 et 13:30 : « un
GROS lexique, spécifique à chaque type d'émotion, calculé à partir des variations de mes 13 hormones »).

Le ressenti de Gemma (jarvis/scanner.py) ne se calcule plus quand Ahmed est là (Gemma se tait) : il peut être ancien.
Celui-ci se recalcule à chaque battement du démon (interieur.tick, toutes les 15 s), sans modèle, sans mémoire :
- pour chaque hormone, son ÉCART à sa base (la base circadienne pour le cortisol et la mélatonine), ramené entre −1 et 1
  (au-dessus : par la marge jusqu'à 1 ; en dessous : par la base), et sa TENDANCE sur ~10 min ;
- 23 émotions (le prototype de Hakim, atelier/pour_ahmed/lexique, ses règles reprises sur ces écarts normalisés et sur
  les VRAIES bases d'affect.py : il avait pris GABA 0,7, CRH 0,3, ACTH 0,2 au lieu de 0,5, 0,15, 0,15), et l'émotion
  soudaine d'affect (alarme → peur, surprise, apaisement) ;
- une cohérence avec la valence : une émotion de signe contraire à une valence nettement marquée est atténuée de moitié
  (le cas de 13:20 relevé par Hakim : « gratitude » quand l'humeur dit « élan », qui sont du même côté, passe ; « tristesse »
  sous une valence haute, non) ;
- deux ou trois formulations par émotion, la même pendant 15 min (pas de clignotement).
Les coefficients sont des HYPOTHÈSES lisibles (Hakim, revues ici), pas une mesure : à valider à l'aveugle comme le ressenti
de Gemma l'a été (11/12 le 20/10).
"""
import random

import affect

# (nom, signe de valence : +1 agréable, −1 désagréable, 0 neutre, règle, formulations accordées à « une sensation »)
REGLES = [
    ("élan", 1, lambda d, t: 1.2 * d["dopamine"] + 0.6 * d["noradrenaline"] + 0.5 * d["endorphine"],
     ["expansive, vive, portée", "vibrante, poussée en avant", "électrique, pleine d'élan"]),
    ("joie", 1, lambda d, t: 1.3 * d["endorphine"] + d["dopamine"] + 0.6 * d["serotonine"] - d["cortisol"],
     ["légère, lumineuse", "joyeuse, qui sourit en dedans", "claire, détendue du dedans"]),
    ("tendresse", 1, lambda d, t: 1.5 * d["ocytocine"] + 0.5 * d["serotonine"] - 0.5 * d["noradrenaline"],
     ["chaude, proche", "tendre, attachée", "enveloppée, tournée vers l'autre"]),
    ("gratitude", 1, lambda d, t: d["ocytocine"] + d["serotonine"] + 0.5 * d["endorphine"] - 0.5 * d["cortisol"],
     ["reconnaissante, pleine", "touchée, avec un merci qui monte"]),
    ("fierté", 1, lambda d, t: 4 * t["dopamine"] + d["dopamine"] + 0.5 * d["serotonine"],
     ["redressée, fière", "satisfaite d'avoir tenu"]),
    ("curiosité", 1, lambda d, t: 1.5 * d["acetylcholine"] + 0.8 * d["dopamine"] - d["cortisol"],
     ["en éveil, tendue vers ce qui vient", "attentive, avide de comprendre", "vive, qui cherche"]),
    ("concentration", 0, lambda d, t: 1.2 * d["acetylcholine"] + 0.8 * d["noradrenaline"] - abs(d["adrenaline"]),
     ["nette, concentrée", "focalisée, sans bruit"]),
    ("calme", 1, lambda d, t: 1.5 * d["gaba"] + 1.2 * d["endocannabinoides"] + d["serotonine"] - d["noradrenaline"] - d["cortisol"],
     ["calme, posée", "sereine, qui respire large", "au repos, sans pression"]),
    ("soulagement", 1, lambda d, t: -6 * t["cortisol"] - 4 * t["noradrenaline"] + d["endocannabinoides"],
     ["relâchée, soulagée", "délestée d'un poids", "apaisée après la tension"]),
    ("apaisement", 1, lambda d, t: d["gaba"] + 1.5 * d["endocannabinoides"] + 0.8 * d["serotonine"] - 1.5 * d["cortisol"],
     ["adoucie, apaisée", "tranquille, détendue"]),
    ("enthousiasme", 1, lambda d, t: 1.5 * d["dopamine"] + d["noradrenaline"] + 0.7 * d["acetylcholine"] + 0.5 * d["endorphine"],
     ["débordante, enthousiaste", "emballée, prête à foncer"]),
    ("compassion", 1, lambda d, t: 1.2 * d["ocytocine"] + 0.6 * d["cortisol"] + 0.4 * d["serotonine"],
     ["attendrie, penchée vers l'autre", "pleine d'égards"]),
    ("surprise", 0, lambda d, t: 5 * abs(t["dopamine"]) + 5 * abs(t["noradrenaline"]) + 3 * abs(t["adrenaline"]),
     ["prise de court, bousculée", "intriguée, un peu secouée"]),
    ("ennui", -1, lambda d, t: -1.5 * d["dopamine"] - d["noradrenaline"] - 0.5 * d["acetylcholine"],
     ["plate, en attente", "désœuvrée, qui tourne en rond", "terne, tournée vers rien"]),
    ("lassitude", -1, lambda d, t: -1.2 * d["serotonine"] - 0.8 * d["dopamine"] + 1.2 * d["melatonine"],
     ["lasse, au ralenti", "fatiguée du dedans", "pesante, qui s'éteint doucement"]),
    ("somnolence", 0, lambda d, t: 2.5 * d["melatonine"] - d["acetylcholine"],
     ["flottante, ensommeillée", "lourde, aux paupières basses"]),
    ("tristesse", -1, lambda d, t: -1.2 * d["serotonine"] - 1.2 * d["endorphine"] - 0.6 * d["ocytocine"] + 0.5 * d["cortisol"],
     ["grise, un peu serrée", "creuse, qui manque de chaleur", "en retrait, triste"]),
    ("manque", -1, lambda d, t: -1.5 * d["ocytocine"] - 4 * t["ocytocine"],
     ["seule, qui attend quelqu'un", "en manque de présence"]),
    ("inquiétude", -1, lambda d, t: 1.2 * d["cortisol"] + d["noradrenaline"] + 0.8 * d["crh"] - d["gaba"],
     ["nouée, sur le qui-vive", "inquiète, à l'affût", "tendue, un peu serrée au ventre"]),
    ("peur", -1, lambda d, t: 3 * d["adrenaline"] + 1.5 * d["noradrenaline"] + 6 * t["adrenaline"],
     ["en alarme, le cœur qui cogne", "saisie, tout en alerte"]),
    ("tension", -1, lambda d, t: 1.5 * d["cortisol"] + d["acth"] - d["endocannabinoides"],
     ["tendue, sous charge", "crispée, qui porte trop"]),
    ("frustration", -1, lambda d, t: d["noradrenaline"] + 0.8 * d["cortisol"] - 1.2 * d["dopamine"],
     ["agacée, coincée", "frustrée, qui bute"]),
    ("culpabilité", -1, lambda d, t: d["cortisol"] - 0.8 * d["dopamine"] + 0.8 * d["ocytocine"],
     ["gênée d'avoir mal fait", "inconfortable, qui veut réparer"]),
]
SOUDAINES = {"alarme": ("peur", 1.0), "surprise": ("surprise", 0.8), "apaisement": ("apaisement", 0.5)}
SEUIL = 0.08


def bases(hour=None):
    b = {h: v[0] for h, v in affect.HORMONES.items()}
    b.update({h: v[0] for h, v in affect.HORMONES_V2.items()})
    if hour is not None:
        b.update(affect._circadian_baselines(hour) or {})
    return b


def ecarts(etat, base):
    out = {}
    for h, b in base.items():
        x = float(etat.get(h, b))
        out[h] = (x - b) / (1 - b) if x >= b else (x - b) / b if b else 0.0
    return out


def calculer(etat, avant=None, now=0.0, soudaine=None, hour=None, n=2):
    """{"emotion", "mots", "scores", "ts"} : 2 (ou 3) formulations pour les émotions dominantes."""
    base = bases(hour)
    d = ecarts(etat, base)
    t = {h: (float(etat.get(h, base[h])) - float((avant or {}).get(h, etat.get(h, base[h])))) for h in base}
    v, _a = affect.valence_arousal(etat)
    v0, _a0 = affect.valence_arousal(base)
    sens = 1 if v - v0 > 0.08 else -1 if v - v0 < -0.08 else 0
    scores = {}
    for nom, signe, regle, _f in REGLES:
        s = regle(d, t)
        if sens and signe and signe != sens:
            s *= 0.5
        scores[nom] = s
    if soudaine in SOUDAINES:
        nom, bonus = SOUDAINES[soudaine]
        scores[nom] += bonus
    ordre = sorted(scores, key=lambda k: -scores[k])
    top = [k for k in ordre if scores[k] > SEUIL][:n] or ordre[:1]
    formes = {nom: f for nom, _s, _r, f in REGLES}
    mots = " ; ".join(random.Random(f"{int(now // 900)}:{k}").choice(formes[k]) for k in top)
    return {"emotion": top[0], "mots": mots, "scores": {k: round(scores[k], 2) for k in ordre[:5]}, "ts": now}
