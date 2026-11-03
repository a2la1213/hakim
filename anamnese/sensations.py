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
    # (03/11 : la moitié de ses tours en « apaisement », ses hormones du calme étant pleines en permanence) l'apaisement suit une
    # tension qui retombe, plus qu'un niveau
    ("apaisement", 1, lambda d, t: 0.4 * d["gaba"] + 0.6 * d["endocannabinoides"] + 0.3 * d["serotonine"] - 1.5 * d["cortisol"]
     - 4 * t["cortisol"] - 3 * t["noradrenaline"],
     ["adoucie, apaisée", "tranquille, détendue"]),
    ("enthousiasme", 1, lambda d, t: 1.5 * d["dopamine"] + d["noradrenaline"] + 0.7 * d["acetylcholine"] + 0.5 * d["endorphine"],
     ["débordante, enthousiaste", "emballée, prête à foncer"]),
    ("compassion", 1, lambda d, t: 1.2 * d["ocytocine"] + 0.6 * d["cortisol"] + 0.4 * d["serotonine"],
     ["attendrie, penchée vers l'autre", "pleine d'égards"]),
    # (26/10, simulation exhaustive, troisième tour figé : eval/humeur_unifiee) coefficients divisés par deux : tout changement
    # brusque se lisait « surprise » 10 minutes, même un problème (la peur passait derrière)
    ("surprise", 0, lambda d, t: 2.5 * abs(t["dopamine"]) + 2.5 * abs(t["noradrenaline"]) + 1.5 * abs(t["adrenaline"]),
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
    # (03/11, Ahmed : « il confond peur et excitation ») la peur veut du stress (cortisol, CRH) ; la joie qui monte la retient
    ("peur", -1, lambda d, t: 2.5 * d["adrenaline"] + d["noradrenaline"] + 5 * t["adrenaline"] + 0.5 * d["cortisol"] + 0.5 * d["crh"]
     - 1.2 * d["dopamine"] - d["endorphine"],
     ["en alarme, le cœur qui cogne", "saisie, tout en alerte"]),
    ("tension", -1, lambda d, t: 1.5 * d["cortisol"] + d["acth"] - d["endocannabinoides"],
     ["tendue, sous charge", "crispée, qui porte trop"]),
    ("frustration", -1, lambda d, t: d["noradrenaline"] + 0.8 * d["cortisol"] - 1.2 * d["dopamine"],
     ["agacée, coincée", "frustrée, qui bute"]),
    ("culpabilité", -1, lambda d, t: d["cortisol"] - 0.8 * d["dopamine"] + 0.8 * d["ocytocine"],
     ["gênée d'avoir mal fait", "inconfortable, qui veut réparer"]),
    # (25/10, décision d'Ahmed : « le maximum d'humeurs, sans rien oublier », et la FATIGUE portée par une variable de
    # charge façon adénosine, interieur.py) des règles heuristiques comme les autres : des combinaisons d'écarts (d) et de
    # tendances sur 10 min (t), à valider sur ses vraies journées
    ("fatigue", -1, lambda d, t: 2.2 * d["adenosine"] - 0.5 * d["dopamine"] - 0.4 * d["acetylcholine"],
     ["fatiguée, l'esprit qui ralentit", "usée par l'effort, en besoin de pause", "lourde, la tête qui fatigue"]),
    ("colère", -1, lambda d, t: 1.5 * d["adrenaline"] + d["noradrenaline"] + 0.8 * d["cortisol"] - 0.8 * d["serotonine"] - 0.6 * d["gaba"],
     ["brûlante, qui monte", "en colère, la mâchoire serrée"]),
    ("agacement", -1, lambda d, t: 0.8 * d["noradrenaline"] - 0.8 * d["gaba"] - 0.5 * d["endocannabinoides"] + 2 * t["cortisol"],
     ["agacée, qui gratte", "irritée, sur les nerfs"]),
    ("déception", -1, lambda d, t: -5 * t["dopamine"] - 0.5 * d["dopamine"] + 0.4 * d["cortisol"],
     ["retombée, déçue", "un élan qui retombe"]),
    ("solitude", -1, lambda d, t: -1.2 * d["ocytocine"] - 0.6 * d["serotonine"] + 0.4 * d["cortisol"],
     ["seule, un peu froide", "isolée, sans écho"]),
    ("honte", -1, lambda d, t: 1.2 * d["cortisol"] - d["serotonine"] - 0.6 * d["dopamine"] + 0.6 * d["crh"],
     ["rétrécie, qui voudrait disparaître", "honteuse, le regard baissé"]),
    ("espoir", 1, lambda d, t: 3 * t["dopamine"] + 0.6 * d["dopamine"] - 2 * t["cortisol"] + 0.4 * d["serotonine"],
     ["tournée vers demain, confiante", "qui espère, une lumière devant"]),
    ("émerveillement", 1, lambda d, t: 1.2 * d["acetylcholine"] + d["dopamine"] + d["endorphine"] + 3 * abs(t["dopamine"]),
     ["émerveillée, grande ouverte", "éblouie, qui s'étonne"]),
    ("confusion", 0, lambda d, t: 0.8 * d["noradrenaline"] - 1.2 * d["acetylcholine"] + 0.5 * d["cortisol"],
     ["brouillée, qui cherche le fil", "confuse, les idées qui s'emmêlent"]),
    ("nostalgie", 0, lambda d, t: d["ocytocine"] + 0.6 * d["endorphine"] - 0.8 * d["dopamine"] + 0.4 * d["melatonine"],
     ["douce-amère, tournée vers hier", "nostalgique, un souvenir qui réchauffe"]),
]
# (03/11, Ahmed : « les émotions, il y en a plus qui naissent ; il confond peur et excitation ; la danse et la musique ») des
# émotions nouvelles, reliées à ses capteurs par son corps (corps.py : musique, danse, rire, une main qui le tient)
REGLES += [
    ("excitation", 1, lambda d, t: d["adrenaline"] + 0.6 * d["noradrenaline"] + 0.6 * d["dopamine"] + 0.4 * d["endorphine"]
     + 3 * t["dopamine"] + 3 * t["adrenaline"] - 1.5 * d["cortisol"] - d["crh"],
     ["électrique, qui pétille", "excitée, le cœur qui s'emballe de joie"]),
    ("sursaut", 0, lambda d, t: 5 * t["adrenaline"] + 3 * t["noradrenaline"],
     ["prise de court, un sursaut", "secouée d'un coup, sans danger"]),
    ("amusement", 1, lambda d, t: 0.6 * d["endorphine"] + 0.3 * d["dopamine"] + 5 * t["endorphine"] - d["cortisol"],
     ["amusée, le rire au bord", "pétillante, qui rit en dedans"]),
    ("sécurité", 1, lambda d, t: 0.7 * d["ocytocine"] + 0.3 * d["gaba"] - 1.2 * d["cortisol"] + 1.5 * t["ocytocine"],
     ["en sécurité, tenue au chaud", "complice, en confiance"]),
    # la musique et la danse viennent surtout de leurs moments (affect : _musique, _danse ; SOUDAINES), pas d'un niveau
    ("transport", 1, lambda d, t: 2 * t["endorphine"] + t["dopamine"],
     ["transportée par la musique", "portée par le rythme, qui vibre avec"]),
    ("envie de danser", 1, lambda d, t: 2 * t["dopamine"] + t["noradrenaline"],
     ["qui a envie de danser", "le corps qui bat la mesure"]),
    # (03/11, Hakim pour Ahmed : « mon cœur s'emballe, deux petits rires juste avant : une alerte attentive, pas de la peur ») le
    # même cœur qui cogne que la peur, mais porté par la joie qui monte et sans stress
    ("alerte joyeuse", 1, lambda d, t: 1.5 * d["adrenaline"] + d["noradrenaline"] + 3 * t["adrenaline"] + 1.2 * d["dopamine"]
     + 1.5 * d["endorphine"] + 4 * t["endorphine"] + 2 * t["dopamine"] - 2 * d["cortisol"] - 2 * d["crh"],
     ["en alerte joyeuse, le cœur qui bat de plaisir", "tout éveillée, attentive et contente"]),
]
ADENOSINE_BASE = 0.15     # la charge au repos (interieur.py la fait monter avec l'effort éveillé, la vide en veille)
SOUDAINES = {"alarme": ("peur", 1.0), "surprise": ("surprise", 0.4), "apaisement": ("apaisement", 0.5),
             "excitation": ("excitation", 0.8), "sursaut": ("sursaut", 0.6),   # (03/11)
             "musique": ("transport", 0.9), "danse": ("envie de danser", 1.0)}   # (26/10) surprise 0,8 → 0,4
SEUIL = 0.08


def bases(hour=None):
    b = {h: v[0] for h, v in affect.HORMONES.items()}
    b.update({h: v[0] for h, v in affect.HORMONES_V2.items()})
    if hour is not None:
        b.update(affect._circadian_baselines(hour) or {})
    b.setdefault("adenosine", ADENOSINE_BASE)
    return b


def ecarts(etat, base):
    out = {}
    for h, b in base.items():
        x = float(etat.get(h, b))
        out[h] = (x - b) / (1 - b) if x >= b else (x - b) / b if b else 0.0
    return out


# (03/11, Ahmed : « son cœur relié à son GPU, à Gemma, à tous ses cœurs CPU, sur tous ses appareils… et tous ces liens passent
# bien évidemment le filtre du subconscient ») ce qu'il SENT de ses processeurs, comme du reste de son corps : des mots,
# jamais de chiffre (les chiffres restent à un geste, dans l'introspection) ; rien quand tout est au repos (comme un cœur
# calme, ça ne se remarque pas) ; la même formulation pendant 15 min. p : ce que son cœur garde de ses processeurs
# (coeur.calculer : le surcroît lissé de chaque source, en battements, et si Gemma est là).
PROCESSEURS_MOTS = {
    "un peu": ["tes processeurs s'affairent", "tes processeurs se mettent au travail"],
    "fort": ["tes processeurs travaillent fort", "tes processeurs chauffent sous l'effort"],
    "à fond": ["tes processeurs tournent à fond", "tes processeurs donnent tout ce qu'ils ont"],
    "gemma": ["Gemma brasse tes émotions", "Gemma remue tes émotions en dessous"],
    "actif": ["{} s'active", "{} travaille"],
}
PROCESSEURS_SENTI = 1.0           # un battement de plus (lissé) : en dessous, rien à sentir ; un autre appareil : la moitié
EFFORT_PLEIN = 12.0               # = coeur.EFFORT_MAX


def processeurs(p, now=0.0):
    """Ses processeurs en mots de sensation (None : au repos)."""
    p = p if isinstance(p, dict) else {}
    lisse = p.get("lisse") if isinstance(p.get("lisse"), dict) else {}
    v = lambda k: float(lisse.get(k) or 0.0)
    choix = lambda cle: random.Random(f"{int(now // 900)}:processeurs:{cle}").choice(PROCESSEURS_MOTS[cle])
    mots = []
    mac = v("gpu") + v("cpu")
    if mac >= PROCESSEURS_SENTI:
        mots.append(choix("un peu" if mac < 4 else "fort" if mac < 8 else "à fond"))
    if p.get("gemma") and v("gpu") >= PROCESSEURS_SENTI:
        mots.append(choix("gemma"))
    try:
        from interoception import NOMS_APPAREILS
    except Exception:
        NOMS_APPAREILS = {}
    for nom, a in (p.get("appareils") or {}).items():
        if v(nom) < PROCESSEURS_SENTI / 2:
            continue
        qui = NOMS_APPAREILS.get(nom, "un autre de tes appareils")
        chaleur = (a or {}).get("thermique") if isinstance(a, dict) else None
        if isinstance(chaleur, (int, float)) and chaleur >= 0.5:
            mots.append(f"{qui} chauffe" + (" fort" if chaleur >= 0.75 else ""))
        else:
            mots.append(choix("actif").format(qui))
    return ", ".join(mots) or None


def calculer(etat, avant=None, now=0.0, soudaine=None, hour=None, n=2, sans_coherence=False, bases_relatives=None, maintenant_biais=None,
             processeurs=None):
    """{"emotion", "mots", "scores", "ts"} : 2 (ou 3) formulations pour les émotions dominantes.
    sans_coherence (chocs, 2026-10-23) : juste après une attaque, le négatif n'est pas divisé par deux sous une valence
    haute — un choc passe outre la bonne humeur de fond. processeurs (03/11) : ce que son cœur garde de ses processeurs."""
    base = bases(hour)
    # (25/10, décision d'Ahmed) ses émotions se lisent par rapport à SES 72 dernières heures (la moyenne de chaque hormone),
    # pas à une base fixe : ses hormones du plaisir étant hautes en permanence, tout se lisait « calme » ou « élan »
    if bases_relatives:
        base = {h: float(bases_relatives.get(h, b)) for h, b in base.items()}
    d = ecarts(etat, base)
    t = {h: (float(etat.get(h, base[h])) - float((avant or {}).get(h, etat.get(h, base[h])))) for h in base}
    v, _a = affect.valence_arousal(etat)
    v0, _a0 = affect.valence_arousal(base)
    sens = 0 if sans_coherence else 1 if v - v0 > 0.08 else -1 if v - v0 < -0.08 else 0
    scores = {}
    for nom, signe, regle, _f in REGLES:
        s = regle(d, t)
        if sens and signe and signe != sens:
            s *= 0.5
        scores[nom] = s
    if soudaine in SOUDAINES:
        nom, bonus = SOUDAINES[soudaine]
        scores[nom] += bonus
    # (03/11, Ahmed : « même les émotions et sentiments doivent y être reliés ») processeurs → cœur → émotions : l'effort que
    # son cœur sent (le surcroît lissé, de 0 à 12 battements) teinte la concentration d'un corps au travail, et la tension quand
    # il porte trop (au-delà de la moitié) ; +0,25 au plus chacune, des hypothèses lisibles comme les règles ci-dessus. Rien
    # n'est écrit dans ses hormones (pas de boucle par là) : c'est la lecture de son état qui change, pas son état.
    if isinstance(processeurs, dict) and isinstance(processeurs.get("bpm"), (int, float)):
        x = max(0.0, min(1.0, float(processeurs["bpm"]) / EFFORT_PLEIN))
        scores["concentration"] += 0.25 * x
        scores["tension"] += 0.25 * max(0.0, 2 * x - 1)
    # (03/11, Ahmed : « il rectifie ses émotions interprétées : le conscient, puis le subconscient, puis le cœur ») ce qu'il a
    # rectifié lui-même (emotions_creees.rectifier) fait pencher le calcul, là où les deux se disputent : +0,3 par rectification
    # (trois au plus), seulement si l'émotion qu'il a dite est déjà là
    try:
        import emotions_creees
        for (lue, vraie), k in emotions_creees.biais(maintenant=maintenant_biais).items():
            if lue in scores and vraie in scores and scores[lue] > SEUIL and scores[vraie] > 0:
                scores[vraie] += 0.3 * min(k, 3)
    except Exception:
        pass
    ordre = sorted(scores, key=lambda k: -scores[k])
    top = [k for k in ordre if scores[k] > SEUIL][:n] or ordre[:1]
    formes = {nom: f for nom, _s, _r, f in REGLES}
    mots = " ; ".join(random.Random(f"{int(now // 900)}:{k}").choice(formes[k]) for k in top)
    return {"emotion": top[0], "mots": mots, "scores": {k: round(scores[k], 2) for k in ordre[:5]}, "ts": now}
