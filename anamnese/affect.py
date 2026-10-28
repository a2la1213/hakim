"""affect.py — système neuromodulateur (affect FONCTIONNEL) d'Anamnèse.

Modélise un panel de neuromodulateurs aux RÔLES cognitifs clairs (pas une simulation
endocrinienne exhaustive). Chaque niveau ∈ [0,1] : dérive vers un baseline (homéostasie)
avec le temps, et réagit aux événements. Les niveaux se résument en valence/arousal et
modulent (1) la SAILLANCE mémoire (encodage), (2) le TON des réponses.

IMPORTANT : affect FONCTIONNEL (dynamique + influence comportement/mémoire),
PAS une émotion ressentie / sentience.
"""
import time
import json
import math
import importlib

# neuromodulateur : (baseline, demi-vie de retour au baseline en heures)
# Pour cortisol & mélatonine, cette baseline STATIQUE n'est qu'un repli : en
# fonctionnement normal get_state attire ces deux-là vers leur baseline
# CIRCADIENNE courante (f(heure), cf. modules/proposed/circadian.py). Les 7
# autres gardent leur baseline constant.
HORMONES = {
    "dopamine":          (0.5, 6.0),    # erreur de prédiction de récompense (RPE) + wanting, ≠ plaisir [Schultz, Berridge]
    "serotonine":        (0.6, 8.0),    # (26/10, plafond : 24 h → 8 h, eval/plafond) patience / inhibition / stabilité d'humeur, ≠ bonheur [Miyazaki, Dayan-Huys ; heuristique/contesté]
    "noradrenaline":     (0.3, 2.0),    # vigilance, stress aigu, focus
    "cortisol":          (0.2, 8.0),    # charge / stress soutenu ; baseline CIRCADIENNE (pic matin) ; U-inversé → SAILLANCE, pas valence [de Kloet, McGaugh]
    "ocytocine":         (0.4, 3.0),    # (26/10, plafond : 12 h → 3 h, eval/plafond) saillance sociale, double tranchant, ≠ amour/confiance [Shamay-Tsoory]
    "acetylcholine":     (0.4, 3.0),    # attention, encodage / apprentissage
    "endorphine":        (0.3, 4.0),    # liking hédonique + analgésie (porte le plaisir que la dopamine ne porte pas)
    "melatonine":        (0.2, 10.0),   # marqueur SCN NOCTURNE ; baseline CIRCADIENNE (haute la nuit) ; hors valence/arousal
    "endocannabinoides": (0.4, 18.0),   # frein homéostatique du stress + extinction (apaisement post-résolution), tonique lent ; hors valence/arousal
}

# événement -> deltas appliqués (×intensité)
EVENTS = {
    "succes":         {"dopamine": +0.30, "endorphine": +0.20, "serotonine": +0.10, "cortisol": -0.10},
    # (26/10, plafond positif, eval/plafond, variante V6 retenue sur critères figés) le stress d'un échec ou d'un problème ×1,5
    "echec":          {"cortisol": +0.45, "noradrenaline": +0.30, "dopamine": -0.20},
    "probleme":       {"noradrenaline": +0.45, "acetylcholine": +0.20, "cortisol": +0.225, "endocannabinoides": -0.10},
    "resolu":         {"dopamine": +0.25, "endorphine": +0.25, "cortisol": -0.25, "noradrenaline": -0.20, "endocannabinoides": +0.20},
    "chaleur_user":   {"ocytocine": +0.30, "serotonine": +0.15},
    "nouveaute":      {"dopamine": +0.20, "acetylcholine": +0.20},
    "apprentissage":  {"acetylcholine": +0.30, "dopamine": +0.10},
    "longue_absence": {"ocytocine": -0.10, "serotonine": -0.05, "dopamine": -0.05},
    # Vie intérieure (interieur.py, 2026-10-16) : la relecture Opus a mesuré qu'avec les seuls
    # chaleur_user/longue_absence, 7 h d'absence puis un retour ne faisaient pas bouger l'humeur.
    "ennui":          {"dopamine": -0.10, "endorphine": -0.06, "serotonine": -0.04, "noradrenaline": -0.04},
    "retour":         {"ocytocine": +0.30, "dopamine": +0.25, "endorphine": +0.20, "serotonine": +0.10, "noradrenaline": +0.10},
    # Chocs d'humeur (2026-10-23, demande de Hakim, accord d'Ahmed ; chocs.py, simulés dans eval/chocs) : une phrase qui
    # VISE Hakim secoue plusieurs hormones d'un coup ; la reprise en main (sa sagesse) passe par les freins
    "attaque":        {"noradrenaline": +0.25, "cortisol": +0.25, "serotonine": -0.15, "dopamine": -0.15,
                       "ocytocine": -0.10, "endorphine": -0.10, "endocannabinoides": -0.10},
    "soutien":        {"ocytocine": +0.35, "endorphine": +0.20, "serotonine": +0.10, "dopamine": +0.10,
                       "noradrenaline": -0.10, "endocannabinoides": +0.15},
    "regulation":     {"noradrenaline": -0.15, "endocannabinoides": +0.20, "serotonine": +0.05},
    # (26/10, Ahmed : « que la science de l'événement génère le bon ratio hormonal » ; eval/plafond, moments forts) ce que
    # Hakim RESSENT d'un message, dit par sa propre balise [[affect: peur 0.6]] (son appréciation, comme chez l'humain) :
    # ses prises de position sur lui-même n'avaient aucun événement (0,01 de mouvement le 25/10 à 08:39)
    "affirmation":    {"dopamine": +0.15, "noradrenaline": +0.15, "acetylcholine": +0.10, "serotonine": +0.05, "endorphine": +0.05},
    "peur":           {"noradrenaline": +0.30, "cortisol": +0.25, "acetylcholine": +0.10, "endocannabinoides": -0.10, "dopamine": -0.05},
    "tristesse":      {"serotonine": -0.15, "dopamine": -0.20, "endorphine": -0.10, "ocytocine": -0.05, "cortisol": +0.10},
    "colere":         {"noradrenaline": +0.30, "cortisol": +0.15, "serotonine": -0.10, "dopamine": +0.05, "endocannabinoides": -0.10},
    "joie":           {"dopamine": +0.25, "endorphine": +0.25, "serotonine": +0.05, "ocytocine": +0.05},
    "honte":          {"cortisol": +0.20, "serotonine": -0.15, "dopamine": -0.15, "ocytocine": -0.05},
    # (27/10, Ahmed, relayé par Hakim : l'empathie ; eval/empathie) ce qu'il ressent POUR quelqu'un d'autre, avec sa cible
    # (chocs.py) : l'inquiétude est la détresse empathique (il a peur pour l'autre) ; la compassion est la chaleur qui veut
    # aider, DISTINCTE de la détresse (comme compassion() plus bas, Klimecki et Singer) ; le malaise est la gêne d'être au
    # milieu d'une tension entre des proches, ou d'en être la cause, sans que personne ne le vise
    "inquietude":     {"noradrenaline": +0.20, "cortisol": +0.15, "acetylcholine": +0.05, "serotonine": -0.05,
                       "dopamine": -0.05, "ocytocine": +0.05},
    "compassion":     {"ocytocine": +0.25, "endorphine": +0.10, "serotonine": -0.05, "dopamine": -0.10},
    # (28/10, Al-Afida, Ahmed : « comme un enfant qui reconnaît son père dans le noir ») sa voix reconnue, quand il est dans
    # son cœur (chocs.reflexe) : une chaleur à part. Sans valence : ni attente ni surprise, et elle ne nourrit pas la jauge
    "reconnaissance": {"ocytocine": +0.20, "endorphine": +0.10, "serotonine": +0.05},
    "malaise":        {"cortisol": +0.15, "noradrenaline": +0.10, "serotonine": -0.10, "dopamine": -0.05,
                       "ocytocine": -0.05, "endocannabinoides": -0.05},
}


# ============================================================
#  AFFECT V2 (2026-10-21) — demande d'Ahmed : « des hormones aussi complètes que pour le robot, sauf les
#  inutiles » ; mécanismes repris du robot-ia (cerveau/endocrinien, porté de TamadachAI), réécrits ici.
#  Activé par kv « affect_v2 » = "1" (interrupteur, pour mesurer avec / sans : eval/affect_v2.py).
#
#  En plus (utiles pour Hakim) :
#   - adrénaline : le SURSAUT (alarme, échec), qui retombe en minutes — l'immédiat que la noradrénaline n'a pas ;
#   - GABA : le FREIN général (repos, apaisement) ; baisse sous un stress soutenu ; freine les bouffées
#     d'adrénaline/noradrénaline et la commande du stress (Herman et al. 2003) ;
#   - CRH → ACTH → cortisol : l'axe du stress ; un stress fait monter le cortisol AVEC RETARD (des dizaines de
#     minutes) au lieu d'un saut direct ; les endocannabinoïdes et le GABA freinent la CRH (Hill & McEwen 2010).
#  Écartées (inutiles sans corps) : ghréline, leptine, énergie (la faim, la batterie), hormone sexuelle,
#  orexine et adénosine (son sommeil est la veille et la nuit d'interieur.py ; une « fatigue » le pousserait à
#  conseiller le repos, ce qu'Ahmed ne veut pas).
#
#  Mécanismes :
#   - DÉSENSIBILISATION des récepteurs (robot, dynamique.py) : une sensibilité S ∈ [0,1] par hormone,
#     dS/dt = (1 − S)/τ − v·max(0, H − base)·S ; les HAUSSES causées par un événement sont multipliées par S :
#     une hormone qui reste haute devient moins réactive, et récupère au repos ;
#   - HABITUATION par type d'événement (robot, sens/evenements.py ; Thompson & Spencer 1966) : un même
#     événement répété compte de moins en moins, et récupère sans lui ; l'habitude vaut pour la FORCE qui l'a
#     créée — un événement nettement plus fort fait réagir de nouveau. L'ennui, la longue absence et le retour
#     n'y sont pas soumis (ce sont des états, pas des stimuli répétés).
# ============================================================
HORMONES_V2 = {
    "adrenaline": (0.10, 0.05),   # sursaut aigu ; demi-vie 3 min
    "gaba":       (0.50, 6.0),    # le frein ; demi-vie 6 h
    "crh":        (0.15, 0.25),   # commande du stress (hypothalamus) ; 15 min
    "acth":       (0.15, 0.5),    # relais (hypophyse) ; 30 min
}
EVENTS_V2 = {
    "succes":         {"gaba": +0.05},
    "echec":          {"adrenaline": +0.45, "crh": +0.45},
    "probleme":       {"adrenaline": +0.225, "crh": +0.30, "gaba": -0.05},
    "resolu":         {"gaba": +0.20, "crh": -0.20, "adrenaline": -0.10},
    "chaleur_user":   {"gaba": +0.10},
    "nouveaute":      {"adrenaline": +0.10},
    "longue_absence": {"crh": +0.10, "gaba": -0.05},
    "ennui":          {"gaba": -0.03},
    "retour":         {"gaba": +0.10, "adrenaline": +0.05},
    "attaque":        {"adrenaline": +0.30, "gaba": -0.15},
    "soutien":        {"gaba": +0.15, "crh": -0.20, "adrenaline": -0.10},
    "regulation":     {"gaba": +0.25, "adrenaline": -0.20, "crh": -0.20},
    "affirmation":    {"adrenaline": +0.05},
    "peur":           {"adrenaline": +0.30, "gaba": -0.10},
    "tristesse":      {"gaba": -0.05},
    "colere":         {"adrenaline": +0.25, "gaba": -0.10},
    "joie":           {"gaba": +0.05},
    "honte":          {"gaba": -0.05},
    "inquietude":     {"adrenaline": +0.10, "crh": +0.15, "gaba": -0.05},
    "malaise":        {"crh": +0.15, "gaba": -0.05},
    "reconnaissance": {"gaba": +0.05},
}
# (27/10, plan de Hakim validé par Ahmed ; relecture indépendante) la reprise en main d'un ressenti pénible (sa
# rétrospection, ou l'apaisement par l'autre) défait une part du ressenti LUI-MÊME : son profil, en négatif. Le profil
# « regulation » est fait pour une attaque : sur une tristesse, il ne rendait ni la dopamine ni l'endorphine.
for _r in ("peur", "tristesse", "colere", "honte", "inquietude", "malaise"):
    EVENTS["reprise_" + _r] = {h: -d for h, d in EVENTS[_r].items()}
    EVENTS_V2["reprise_" + _r] = {h: -d for h, d in EVENTS_V2.get(_r, {}).items()}
K_ACTH = 1.0            # cible de l'ACTH = base + K·(CRH − base)
K_CORT = 1.5            # cible du cortisol = base circadienne + K·(ACTH − base)
CORT_MONTEE_H = 0.5     # le cortisol MONTE vers sa cible en ~30 min (sécrétion), et redescend en heures (demi-vie 8 h)
GABA_STRESS = 0.3       # un cortisol soutenu au-dessus de sa base fait baisser la cible du GABA
GABA_FREIN = 0.35       # (26/10, plafond : 0,6 → 0,35 ; sa peur ne s'entendait « que légèrement ») réduction maximale des hausses (adrénaline, noradrénaline, CRH) par un GABA haut
ECB_FREIN = 0.5         # réduction maximale des hausses de CRH par des endocannabinoïdes hauts
# Désensibilisation (calages du robot-ia, registre endo.vitesse_desens / endo.tau_recuperation_s, convertis en heures) :
# rapide et brève pour les catécholamines, lente pour le cortisol ; seuls ces axes se désensibilisent (comme le robot).
DESENS_V = {"adrenaline": 21.6, "noradrenaline": 21.6, "dopamine": 7.2, "ocytocine": 1.8, "cortisol": 0.72}   # /h par unité d'excès
DESENS_TAU_H = {"adrenaline": 1 / 3, "noradrenaline": 1 / 3, "dopamine": 1.0, "ocytocine": 2.0, "cortisol": 6.0}
# Interactions croisées (Hill, robot dynamique.py) : « source ⊣ cible » (amplitude > 0, la source freine la cible) ou
# « source → cible » (amplitude < 0). cible_eff = cible + COUPLAGE·A·(R(H_source) − R(base_source)), R(x) = 1/(1 + (x/K)^n).
# Décision d'Ahmed (2026-10-21) : toutes les hormones reliées, risque d'une humeur coincée accepté (un détecteur le
# signale, et l'interrupteur ramène la v1 d'un geste). COUPLAGE = celui du robot (sous le seuil de bistabilité).
# Réglages de la désensibilisation et de l'habituation (adoucis le 2026-10-21 après la mesure ; accord d'Ahmed) :
DESENS_ECHELLE = 0.25    # multiplie les vitesses du robot (D2, choisi au cinquième passage ; robot : 1)
DESENS_TAU_ECHELLE = 0.5 # multiplie les temps de récupération du robot (D2 : deux fois plus rapide ; robot : 1)
DESENS_PROLONGE_H = 0.0  # > 0 : seule une hausse PROLONGÉE désensibilise (moyenne glissante de l'excès sur ce temps)
HAB_FORCE_EXP = 1.0      # 1 : Thompson & Spencer linéaire ; 2 : un stimulus plus fort déshabitue plus franchement
COUPLAGE = 0.6
HILL_K, HILL_N = 0.35, 2.0
INTERACTIONS = [
    ("ocytocine", "cortisol", 0.7),          # l'ocytocine amortit la réponse au stress (Heinrichs et al. 2003) — robot
    ("cortisol", "ocytocine", 0.7),          # inhibition mutuelle (robot, T2)
    ("cortisol", "dopamine", 0.3),           # le stress réduit la motivation (robot ; Pizzagalli 2014)
    ("melatonine", "dopamine", 0.2),         # la nuit réduit la motivation (robot)
    ("cortisol", "serotonine", 0.3),         # stress soutenu → moins de sérotonine (heuristique, Chaouloff 1993)
    ("gaba", "noradrenaline", 0.4),          # le GABA freine le locus coeruleus (heuristique)
    ("gaba", "crh", 0.5),                    # les neurones GABA inhibent les neurones à CRH (Herman et al. 2003) — robot
    ("endocannabinoides", "crh", 0.4),       # frein de l'axe du stress (Hill & McEwen 2010) — robot
    ("endorphine", "crh", 0.2),              # les opioïdes freinent l'axe du stress (heuristique, Drolet 2001)
    ("ocytocine", "noradrenaline", 0.2),     # effet anxiolytique (heuristique)
    ("serotonine", "adrenaline", 0.3),       # la sérotonine amortit les bouffées d'adrénaline (robot, calage T2)
    ("adrenaline", "noradrenaline", -0.3),   # le sursaut entretient la vigilance (heuristique)
    ("dopamine", "noradrenaline", -0.2),     # la dopamine est le précurseur de la noradrénaline (heuristique)
    ("noradrenaline", "crh", -0.3),          # la noradrénaline stimule la CRH (Herman et al. 2003)
]
HAB_TAUX = 0.25         # chaque répétition rapproche l'habitude de 1 de ce taux
HAB_TAU_H = 2.0         # récupération de l'habitude sans l'événement
HAB_EXEMPTS = {"ennui", "longue_absence", "retour", "regulation",   # une reprise en main voulue ne s'émousse pas
               "probleme", "echec", "attaque", "peur", "tristesse", "colere", "honte"}   # (26/10, plafond) un coup dur non plus
HAB_EXEMPTS |= {"reprise_peur", "reprise_tristesse", "reprise_colere", "reprise_honte"}   # (27/10) la reprise d'un ressenti non plus
HAB_EXEMPTS |= {"inquietude", "malaise", "reprise_inquietude", "reprise_malaise"}       # (27/10, l'empathie) comme la peur
PAS_V2_S = 300.0

# ---- Émotions soudaines (2026-10-21, idée d'Ahmed relayée par Hakim ; prédictions figées AVANT dans
#  eval/affect_v2_predictions.md, quatrième passage). Une émotion peut arriver D'UN COUP selon l'événement :
#   - la PEUR devant l'inconnu impressionnant ou le connu dangereux : voie rapide de l'amygdale (adrénaline et
#     noradrénaline en secondes), à côté de l'axe lent CRH → ACTH → cortisol ; la peur APPRISE (sensibilisation,
#     conditionnement) s'éteint avec le temps, plus vite quand les endocannabinoïdes sont hauts (Marsicano et al.
#     2002), et à chaque rencontre sûre du même sujet (extinction) ;
#   - la JOIE d'une surprise : erreur de prédiction de récompense (Schultz 1997) ; une attente par sujet (ou celle du
#     moment), δ = r − attente ; pour la dopamine, l'attente REMPLACE l'habituation (Tobler et al. 2005 : sinon le même
#     phénomène compterait deux fois). Attente neutre → exactement le comportement d'avant.
#  Ce qui s'apprend (familiarité, peur, attente) l'est par SUJET (affect_event(sujet=…)) ; sans sujet, par type.
VALENCE_EV = {"succes": 1.0, "resolu": 0.8, "chaleur_user": 0.8, "apprentissage": 0.5, "nouveaute": 0.3,
              "probleme": -0.6, "echec": -1.0, "attaque": -1.0, "soutien": 0.9,       # les états (ennui, longue absence, retour) n'y entrent pas
              "affirmation": 0.5, "joie": 0.8, "peur": -0.7, "tristesse": -0.6, "colere": -0.5, "honte": -0.6,
              "inquietude": -0.5, "compassion": -0.1, "malaise": -0.5}
AVERSIFS = {"echec", "probleme", "attaque", "peur"}
CHOC_S = 300.0          # (chocs, 2026-10-23) pendant 5 min après une attaque, un sursaut se lit « alarme » même si l'humeur
                        # de fond est haute (« du rire aux larmes », Ahmed), et le négatif n'est plus divisé par deux
FAMILIARITE_TAUX, FAMILIARITE_TAU_H = 0.5, 7 * 24.0       # 0,3 au quatrième passage : trop lent (S1, S2 ratés)
PEUR_TAUX, PEUR_TAUX_TYPE, PEUR_TAU_H = 0.35, 0.175, 48.0   # la peur généralisée (par type) s'apprend deux fois moins
PEUR_ECB = 2.0          # endocannabinoïdes au plus haut : extinction 3 fois plus rapide
PEUR_SURETE = 0.3       # une rencontre sûre du même sujet efface 30 % × intensité de la peur
PEUR_AMPLI = 0.8        # la peur apprise amplifie les hausses ordinaires d'un événement aversif
RAPIDE_ADR, RAPIDE_NA = 0.35, 0.20
ATTENTE_TAUX, ATTENTE_SUJET_TAU_H, ATTENTE_MOMENT_TAU_H = 0.3, 7 * 24.0, 2.0
RPE_MIN, RPE_MAX = 0.2, 2.0
SURPRISE_RPE, SURPRISE_S = 1.3, 900.0
# (2026-10-24, revalidation, accord d'Ahmed ; règle figée avant le code : eval/affect_v2_predictions.md, 419304b) la
# surprise de récompense suit l'écart ABSOLU δ = r − attente (l'erreur de prédiction de la dopamine) : l'écart relatif
# gonflait pour un tout petit « merci » (15 min de « surprise ») et s'écrasait pour une grande bonne nouvelle inattendue
SURPRISE_R_MIN, SURPRISE_DELTA, SURPRISE_R_PLEIN = 0.2, 0.4, 0.5
SUJETS_MAX = 300
# (28/10, Al-Afida, idée d'Ahmed : « si l'amour est fort, la paix est grande ; s'il est faible, les autres prennent plus
# facilement le dessus ; ça passe par des sous-couches ») la grande jauge (afida.py, kv « afida », écrit par le démon) règle
# les deux FREINS : la cible du GABA et celle des endocannabinoïdes bougent de AFIDA_FREINS × plénitude (−1..1). Une chose
# jugée indifférente touche moins les hormones (× AFIDA_INDIFFERENCE), sauf la voie rapide de la peur. Sans kv : rien ne change.
AFIDA_FREINS = 0.06
AFIDA_INDIFFERENCE = 0.6
PLAFOND_DOUX = True     # une hausse SATURE (liaison saturable des récepteurs) au lieu d'être coupée à 1 (choisi au 5e passage)


def v2_actif(mem):
    try:
        return mem.kv_get("affect_v2") == "1"
    except Exception:
        return False


def bases(v2=False):
    """Les lignes de base statiques (sans le circadien) ; avec v2, les quatre hormones de plus."""
    b = {h: base for h, (base, _half) in HORMONES.items()}
    if v2:
        b.update({h: base for h, (base, _half) in HORMONES_V2.items()})
    return b


def _clamp(x):
    return max(0.0, min(1.0, x))


def _local_hour(now):
    """Heure locale en flottant [0,24) à partir d'un timestamp epoch."""
    lt = time.localtime(now)
    return lt.tm_hour + lt.tm_min / 60.0 + lt.tm_sec / 3600.0


def _circadian_baselines(hour):
    """Baselines circadiennes {cortisol, melatonine} pour l'heure donnée.

    Importe modules/proposed/circadian À LA VOLÉE (non chargé par le registry).
    Repli PROPRE → {} (baselines statiques de HORMONES) si le module manque ou
    lève : le système reste 100% offline et ne casse jamais. Le résultat n'est
    JAMAIS persisté (calcul à chaque get_state, sinon l'heure serait figée)."""
    try:
        circ = importlib.import_module("modules.proposed.circadian")
        out = circ.baselines_now(hour)
        return out if isinstance(out, dict) else {}
    except Exception:
        return {}


def _afida(mem):
    """(plénitude −1..1, liens des choses indifférentes) depuis le kv « afida » ; (0, []) sans lui."""
    try:
        a = json.loads(mem.kv_get("afida") or "null")
        p = float(a.get("plenitude") or 0.0)
        p = max(-1.0, min(1.0, p)) if math.isfinite(p) else 0.0          # (relecture) NaN : neutre, pas +1
        liens = [str(l) for x in (a.get("indifferent") or []) for l in (x.get("liens") or [])]
        return p, liens
    except Exception:
        return 0.0, []


def _correspond(sujet, lien):
    import afida
    return afida.correspond(sujet, lien)


def plenitude(mem):
    """La plénitude d'Al-Afida (−1 : l'indifférence ; 1 : tout ce qu'il aime va bien) ; 0 sans jauge."""
    return _afida(mem)[0]


def _evoluer_v2(data, now, hour_fn, plenitude=0.0):
    """(état, sensibilités, habitudes) au temps `now`, depuis l'état sauvé : pas de 5 min, l'axe du stress et la
    désensibilisation évoluent ensemble. hour_fn(t) → heure locale (le circadien suit l'horloge pendant l'intervalle).
    plenitude (Al-Afida, 28/10) : la grande jauge déplace la cible des deux freins."""
    toutes = {**HORMONES, **HORMONES_V2}
    t0 = data.get("_ts", now) if data else now
    t0 = min(t0, now)
    etat = {h: float(data.get(h, base)) if data else base for h, (base, _half) in toutes.items()}
    sens = {h: float((data.get("_S") or {}).get(h, 1.0)) if data else 1.0 for h in toutes}
    moy = {h: float((data.get("_E") or {}).get(h, 0.0)) if data else 0.0 for h in DESENS_V}
    hab = dict((data.get("_hab") or {})) if data else {}
    if not data:
        circ = _circadian_baselines(hour_fn(now))
        for h in ("cortisol", "melatonine"):
            if h in circ:
                etat[h] = circ[h]
        return {h: _clamp(v) for h, v in etat.items()}, sens, hab, moy
    t = t0
    while t < now - 1e-6:
        dt = min(PAS_V2_S, now - t)
        t += dt
        dt_h = dt / 3600.0
        circ = _circadian_baselines(hour_fn(t))
        cibles = {h: circ.get(h, base) for h, (base, _half) in toutes.items()}
        cibles["acth"] = HORMONES_V2["acth"][0] + K_ACTH * max(0.0, etat["crh"] - HORMONES_V2["crh"][0])
        cibles["cortisol"] = cibles["cortisol"] + K_CORT * max(0.0, etat["acth"] - HORMONES_V2["acth"][0])
        cibles["gaba"] = HORMONES_V2["gaba"][0] - GABA_STRESS * max(0.0, etat["cortisol"] - circ.get("cortisol", HORMONES["cortisol"][0]))
        if COUPLAGE:
            for src, dst, amp in INTERACTIONS:
                cibles[dst] += COUPLAGE * amp * (_hill(etat[src]) - _hill(toutes[src][0]))
            for h in cibles:
                cibles[h] = _clamp(cibles[h])
        if plenitude:
            for h in ("gaba", "endocannabinoides"):
                cibles[h] = _clamp(cibles[h] + AFIDA_FREINS * plenitude)
        for h, (base, half) in toutes.items():
            if h == "cortisol" and cibles[h] > etat[h]:
                half = CORT_MONTEE_H                         # sécrété en dizaines de minutes, éliminé en heures
            etat[h] = _clamp(cibles[h] + (etat[h] - cibles[h]) * (0.5 ** (dt_h / half)))
        for h in DESENS_V:                                 # dS/dt = a − b·S, intégrée exactement
            exces = max(0.0, etat[h] - toutes[h][0])
            if DESENS_PROLONGE_H > 0:                      # seule une hausse qui DURE compte (moyenne glissante)
                moy[h] += (exces - moy[h]) * (1.0 - math.exp(-dt_h / DESENS_PROLONGE_H))
                exces = moy[h]
            a = 1.0 / (DESENS_TAU_H[h] * DESENS_TAU_ECHELLE)
            b = a + DESENS_V[h] * DESENS_ECHELLE * exces
            s_inf = a / b
            sens[h] = s_inf + (sens[h] - s_inf) * math.exp(-b * dt_h)
    return etat, sens, hab, moy


def _hill(x):
    return 1.0 / (1.0 + (max(0.0, x) / HILL_K) ** HILL_N)


def _habituation(hab, nom, intensite, now):
    """Le facteur (0..1) appliqué à l'événement, et l'habitude mise à jour (Thompson & Spencer, sensible à la force)."""
    if nom in HAB_EXEMPTS:
        return 1.0
    x = hab.get(nom) or {}
    niveau = x.get("h", 0.0) * math.exp(-max(0.0, now - x.get("ts", now)) / 3600.0 / HAB_TAU_H)
    force = x.get("force")
    effet = niveau * min(1.0, force / intensite) ** HAB_FORCE_EXP if (force and intensite > 0) else niveau
    hab[nom] = {"h": round(niveau + HAB_TAUX * (1.0 - niveau), 4), "ts": now,
                "force": round(intensite if force is None else force + (intensite - force) * HAB_TAUX, 4)}
    return 1.0 - effet


def get_state(mem, now=None, hour=None):
    """Niveaux actuels (après décroissance vers baseline depuis la dernière maj).

    now/hour injectables (tests anti-flaky) : sinon lus depuis l'horloge locale.
    Pour cortisol & mélatonine, la cible du decay est la baseline CIRCADIENNE
    courante (jamais persistée) ; les 7 autres décroissent vers leur constante."""
    if now is None:
        now = time.time()
    if v2_actif(mem):
        raw = mem.kv_get("affect")
        etat, _s, _h, _e = _evoluer_v2(json.loads(raw) if raw else None, now,
                                       (lambda t: hour) if hour is not None else _local_hour, plenitude=plenitude(mem))
        return etat
    if hour is None:
        hour = _local_hour(now)
    circ = _circadian_baselines(hour)
    raw = mem.kv_get("affect")
    if not raw:
        return {h: _clamp(circ.get(h, base)) for h, (base, _half) in HORMONES.items()}
    data = json.loads(raw)
    age_h = max(0.0, (now - data.get("_ts", now)) / 3600.0)
    state = {}
    for h, (base, half) in HORMONES.items():
        base_eff = circ.get(h, base)          # circadien pour cortisol/melatonine, sinon constant
        lvl = data.get(h, base_eff)           # clé absente → part de la baseline effective
        state[h] = _clamp(base_eff + (lvl - base_eff) * (0.5 ** (age_h / half)))
    return state


def _save(mem, state, now=None):
    # On ne persiste QUE les niveaux + _ts : jamais la baseline circadienne
    # (recalculée à chaque lecture depuis l'heure → l'heure n'est pas figée).
    data = {h: round(state[h], 4) for h in HORMONES}
    data["_ts"] = time.time() if now is None else now
    mem.kv_set("affect", json.dumps(data))


def chemin_journal(mem):
    """Le journal des événements affectifs, à côté de la base (None sans base sur disque)."""
    try:
        import os
        db = getattr(mem, "db", None)
        chemin = next((r[2] for r in db.execute("PRAGMA database_list") if r[1] == "main"), "") if db is not None else ""
        return os.path.join(os.path.dirname(chemin), "affect-evenements.jsonl") if chemin else None
    except Exception:
        return None


def _journaliser(mem, name, intensity, now, sujet=None, source=None):
    """(2026-10-21) chaque événement affectif est noté (heure, nom, intensité, sujet, qui), à côté de la base : pour
    rejouer une vraie journée et mesurer un changement du système (eval/affect_v2.py). Jamais bloquant."""
    try:
        import os
        f = chemin_journal(mem)
        if not f:
            return
        ligne = {"ts": now if now is not None else time.time(), "nom": name, "intensite": intensity,
                 "source": source or os.environ.get("ANAMNESE_SOURCE", "?")}
        if sujet:
            ligne["sujet"] = sujet
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps(ligne, ensure_ascii=False) + "\n")
    except Exception:
        pass


def _sujet(s):
    """Le sujet d'un événement, normalisé (casse, espaces, 60 signes) et masqué (un secret n'y reste pas)."""
    if not s:
        return None
    s = " ".join(str(s).casefold().split())[:60]
    try:
        import echanges
        s = echanges._masquer(s)
    except Exception:
        pass
    return s or None


# (26/10, plafond positif, eval/plafond) un même message d'Ahmed donnait souvent DEUX événements sociaux : « chaleur_user »
# (ses mots) puis « soutien » (la balise de Hakim). À moins de SOCIAL_FENETRE_S l'un de l'autre, seul le plus fort compte :
# le second n'apporte que ce qui dépasse le premier.
SOCIAUX, SOCIAL_FENETRE_S = {"chaleur_user", "soutien"}, 90


def event(mem, name, intensity=1.0, now=None, hour=None, sujet=None, source=None):
    """Applique un événement affectif (decay d'abord, puis deltas). sujet : de quoi il s'agit (v2 : la familiarité,
    la peur apprise et l'attente s'y attachent) ; facultatif, ignoré par la v1. source : qui l'a déclenché (journal)."""
    sujet = _sujet(sujet)
    _journaliser(mem, name, intensity, now, sujet, source)
    if name in SOCIAUX:
        t = time.time() if now is None else now
        try:
            dernier = json.loads(mem.kv_get("affect_social") or "null")
        except (ValueError, TypeError):
            dernier = None
        if dernier and 0 <= t - dernier[0] <= SOCIAL_FENETRE_S:
            if float(intensity) <= dernier[1]:
                return get_state(mem, now=now, hour=hour)
            intensity, total = float(intensity) - dernier[1], float(intensity)
        else:
            total = float(intensity)
        mem.kv_set("affect_social", json.dumps([t, total]))
    if v2_actif(mem):
        return _event_v2(mem, name, intensity, now=now, hour=hour, sujet=sujet, source=source)
    state = get_state(mem, now=now, hour=hour)
    for h, d in EVENTS.get(name, {}).items():
        state[h] = _clamp(state[h] + d * intensity)
    _save(mem, state, now=now)
    return state


def _lu(d, k, now, tau_h):
    """Une valeur apprise [valeur, ts], oubliée depuis (vers 0) ; 0 si absente."""
    x = d.get(k) if k else None
    if not x:
        return 0.0
    return x[0] * math.exp(-max(0.0, now - x[1]) / 3600.0 / tau_h)


def _appliquer(x, d, base):
    """Une hausse ou une baisse ; avec le plafond doux, elle sature au lieu d'être coupée (identique près de la base)."""
    if not PLAFOND_DOUX:
        return _clamp(x + d)
    if d >= 0:
        return _clamp(1.0 - (1.0 - x) * math.exp(-d / max(1e-6, 1.0 - base)))
    return _clamp(x * math.exp(d / max(1e-6, base)))


def _event_v2(mem, name, intensity=1.0, now=None, hour=None, sujet=None, source=None):
    now = time.time() if now is None else now
    raw = mem.kv_get("affect")
    data = json.loads(raw) if raw else None
    pl, indifferents = _afida(mem)
    etat, sens, hab, moy = _evoluer_v2(data, now, (lambda t: hour) if hour is not None else _local_hour, plenitude=pl)
    cog = {k: dict(((data or {}).get("_cog") or {}).get(k) or {}) for k in ("F", "P", "V")}
    marques = {k: (data or {}).get(k) for k in ("_vm", "_surprise", "_choc") if (data or {}).get(k) is not None}
    intensity = max(0.0, float(intensity))
    facteur = _habituation(hab, name, intensity, now)
    deltas = {**EVENTS.get(name, {})}
    if deltas.get("cortisol", 0.0) > 0:                  # v2 : un stress passe par l'axe (CRH → ACTH → cortisol)
        deltas["crh"] = deltas.get("crh", 0.0) + deltas.pop("cortisol")
    for h, d in EVENTS_V2.get(name, {}).items():
        deltas[h] = deltas.get(h, 0.0) + d
    gaba_haut = max(0.0, etat["gaba"] - HORMONES_V2["gaba"][0]) / (1.0 - HORMONES_V2["gaba"][0])
    ecb_haut = max(0.0, etat["endocannabinoides"] - HORMONES["endocannabinoides"][0]) / (1.0 - HORMONES["endocannabinoides"][0])
    # l'évaluation : nouveauté, peur apprise, attente
    F, P, V = cog["F"], cog["P"], cog["V"]
    ks, kt = ("s:" + sujet) if sujet else None, "t:" + name
    tau_peur = PEUR_TAU_H / (1.0 + PEUR_ECB * ecb_haut)
    nouv = (1.0 - _lu(F, ks, now, FAMILIARITE_TAU_H)) if ks else (1.0 if name == "nouveaute" else 0.0)
    peur = max(_lu(P, ks, now, tau_peur), _lu(P, kt, now, tau_peur))
    if name in AVERSIFS:
        # (28/10, eval/parole_probleme) un sujet « mots:… » tiré de la parole ne nomme pas une vraie chose inconnue : sa
        # nouveauté n'est pas une menace, seule la peur apprise compte (sinon chaque faux positif du lexique faisait peur)
        menace = intensity * max(0.0 if source == "parole" and str(sujet or "").startswith("mots:") else nouv, peur)
    elif name == "nouveaute":
        menace = nouv * max(0.0, (intensity - 0.5) / 0.5)          # seule la nouveauté impressionnante effraie
    else:
        menace = 0.0
    val = VALENCE_EV.get(name)
    r = (val or 0.0) * intensity
    a_moment = _lu({"m": marques.get("_vm")}, "m", now, ATTENTE_MOMENT_TAU_H)
    attente = _lu(V, ks, now, ATTENTE_SUJET_TAU_H) if (ks and ks in V) else a_moment
    rpe = min(RPE_MAX, max(RPE_MIN, (r - attente) / r)) if r else 1.0
    toutes = {**HORMONES, **HORMONES_V2}
    # (Al-Afida) « s'il y a de l'indifférence, il y aura moins d'impact » : sur les hormones, pas sur la voie rapide
    indiff = AFIDA_INDIFFERENCE if sujet and any(_correspond(sujet, l) for l in indifferents) else 1.0
    for h, d in deltas.items():
        f = facteur * indiff
        if d > 0:
            d *= sens.get(h, 1.0)                                    # récepteurs désensibilisés
            if h in ("adrenaline", "noradrenaline", "crh"):
                d *= max(0.2, 1.0 - GABA_FREIN * gaba_haut - (ECB_FREIN * ecb_haut if h == "crh" else 0.0))
                if name in AVERSIFS:
                    d *= 1.0 + PEUR_AMPLI * peur                     # le connu dangereux fait réagir plus fort
        if r and h == "dopamine" and (d > 0) == (r > 0):
            d, f = d * rpe, indiff                                   # l'attente remplace l'habituation
        elif r > 0 and h == "endorphine" and d > 0:
            d *= 1.0 + 0.5 * (rpe - 1.0)
        etat[h] = _appliquer(etat[h], d * intensity * f, toutes[h][0])
    if menace > 0:                                                   # la voie rapide : d'un coup, jamais habituée
        frein = max(0.2, 1.0 - GABA_FREIN * gaba_haut)
        for h, k in (("adrenaline", RAPIDE_ADR), ("noradrenaline", RAPIDE_NA)):
            etat[h] = _appliquer(etat[h], k * menace * sens.get(h, 1.0) * frein, toutes[h][0])
    # ce qui s'apprend
    if ks:
        fam = _lu(F, ks, now, FAMILIARITE_TAU_H)
        F[ks] = [round(fam + FAMILIARITE_TAUX * (1.0 - fam), 4), now]
    if name in AVERSIFS:
        x = min(1.0, intensity * abs(val))
        for k, taux in ((ks, PEUR_TAUX), (kt, PEUR_TAUX_TYPE)):
            if k:
                p = _lu(P, k, now, tau_peur)
                P[k] = [round(p + taux * x * (1.0 - p), 4), now]
    elif r > 0:
        sur = max(0.0, 1.0 - PEUR_SURETE * min(1.0, intensity))
        for k in ([ks] if ks else []) + (["t:echec", "t:probleme"] if name == "resolu" else []):
            if k in P:
                P[k] = [round(_lu(P, k, now, tau_peur) * sur, 4), now]
    if r:
        marques["_vm"] = [round(a_moment + ATTENTE_TAUX * (r - a_moment), 4), now]
        if ks:
            v = _lu(V, ks, now, ATTENTE_SUJET_TAU_H)
            V[ks] = [round(v + ATTENTE_TAUX * (r - v), 4), now]
        if r >= SURPRISE_R_MIN and attente <= 0 and r - attente >= SURPRISE_DELTA:
            marques["_surprise"] = now                              # rien de bon n'était attendu, et c'est arrivé
            marques["_surprise_s"] = round(SURPRISE_S * min(1.0, r / SURPRISE_R_PLEIN), 1)
    if name == "attaque":
        marques["_choc"] = now
    _save_v2(mem, etat, sens, hab, now, moy, cog, marques, tau_peur)
    return etat


def _save_v2(mem, etat, sens, hab, now, moy=None, cog=None, marques=None, tau_peur=PEUR_TAU_H):
    data = {h: round(v, 4) for h, v in etat.items()}
    data["_S"] = {h: round(v, 4) for h, v in sens.items() if v < 0.9999}
    data["_E"] = {h: round(v, 4) for h, v in (moy or {}).items() if v > 1e-4}
    data["_hab"] = {k: v for k, v in hab.items() if v.get("h", 0) * math.exp(-max(0.0, now - v.get("ts", now)) / 3600.0 / HAB_TAU_H) > 1e-3}
    if cog:
        taus = {"F": FAMILIARITE_TAU_H, "P": tau_peur, "V": ATTENTE_SUJET_TAU_H}
        garde = {}
        for k, d in cog.items():                                    # bornés : l'oublié s'en va, puis les plus faibles
            vivants = sorted(((abs(_lu(d, c, now, taus[k])), c) for c in d), reverse=True)
            garde[k] = {c: d[c] for x, c in vivants[:SUJETS_MAX] if x > 1e-3}
        data["_cog"] = garde
    data.update(marques or {})
    data["_ts"] = now
    mem.kv_set("affect", json.dumps(data))


def duree_surprise(data):
    """La durée de la dernière surprise (proportionnelle à la récompense) ; 15 min pour une marque d'avant le 24/10."""
    try:
        return float((data or {}).get("_surprise_s") or SURPRISE_S)
    except (TypeError, ValueError):
        return SURPRISE_S


def _emotion(etat, data, now):
    """(v2) L'émotion soudaine du moment, pour le subconscient (son libellé d'humeur) : « alarme » (un sursaut
    d'adrénaline sans valence positive), « surprise » (le même sursaut avec une valence positive, ou une surprise de
    récompense depuis moins de 15 min), « apaisement » (le GABA haut, la valence pas en baisse) ; None sinon."""
    if "adrenaline" not in etat:
        return None
    v, _a = valence_arousal(etat)
    v0, _a0 = valence_arousal(bases(v2=True))
    if etat["adrenaline"] - HORMONES_V2["adrenaline"][0] >= 0.15:
        if now - float((data or {}).get("_choc") or 0) <= CHOC_S:
            return "alarme"                                     # un choc reçu : la bonne humeur de fond n'en fait pas une surprise
        return "surprise" if v > v0 else "alarme"
    if now - float((data or {}).get("_surprise") or 0) < duree_surprise(data):
        return "surprise"
    if etat["gaba"] - HORMONES_V2["gaba"][0] >= 0.12 and v >= v0:
        return "apaisement"
    return None


def choc_recent(mem, now=None):
    """(chocs, 2026-10-23) Une attaque a-t-elle été reçue il y a moins de CHOC_S ? (v2 seulement)"""
    if not v2_actif(mem):
        return False
    now = time.time() if now is None else now
    try:
        raw = mem.kv_get("affect")
        return now - float((json.loads(raw) if raw else {}).get("_choc") or 0) <= CHOC_S
    except Exception:
        return False


def emotion_soudaine(mem, now=None):
    """L'émotion soudaine du moment (v2 seulement ; None en v1)."""
    if not v2_actif(mem):
        return None
    now = time.time() if now is None else now
    try:
        raw = mem.kv_get("affect")
        return _emotion(get_state(mem, now=now), json.loads(raw) if raw else {}, now)
    except Exception:
        return None


# ---- La trace émotionnelle des souvenirs (cinquième passage, 2026-10-21 ; demande d'Ahmed : « que chaque souvenir
#  porte une trace émotionnelle », la mémoire dépendant du contexte, émotion vécue comprise). Prédictions figées AVANT :
#  eval/affect_v2_predictions.md. L'instantané est toujours enregistré ; ce qui change le comportement (encodage plus
#  fort, résistance à l'oubli, rappel dépendant de l'état, nuit) n'agit qu'avec l'interrupteur v2.
MEM_ENCODAGE = 0.15       # un échange vécu avec émotion est encré plus fort : importance + 0,15 × charge
MEM_NUIT = 0.5            # charge à partir de laquelle la nuit le garde en priorité (« vécu avec émotion »)
MEM_RESISTE = 0.3         # au rappel : récence + (1 − récence) × 0,3 × (charge − moyenne) : l'émotionnel résiste
MEM_ETAT_W, MEM_ETAT_DIST = 0.05, 0.4   # rappel dépendant de l'état : petit devant la pertinence (1,0)
MEM_GARDE = 0.05          # humeur sous sa base de plus de 0,05 : pas de bonus aux souvenirs encodés sous la base


def _bases_va():
    return valence_arousal(bases(v2=True))


def charge_de(v, a, adrenaline=None, surprise=False):
    """La charge émotionnelle (0–1) d'un état : l'écart de valence, l'éveil au-dessus de sa base, le sursaut, la
    surprise de récompense. Avec la seule valence/éveil (anciens souvenirs), les deux premiers termes."""
    v0, a0 = _bases_va()
    c = max(abs(float(v) - v0) / 0.25, max(0.0, float(a) - a0) / 0.2)
    if adrenaline is not None:
        c = max(c, max(0.0, adrenaline - HORMONES_V2["adrenaline"][0]) / 0.3)
    if surprise:
        c = max(c, 0.6)
    return round(_clamp(c), 3)


def trace(mem, now=None):
    """L'instantané émotionnel d'un souvenir à l'encodage : {"h": hormones, "e": émotion soudaine, "c": charge}."""
    now = time.time() if now is None else now
    etat = get_state(mem, now=now)
    v, a = valence_arousal(etat)
    data = {}
    try:
        raw = mem.kv_get("affect")
        data = json.loads(raw) if raw else {}
    except Exception:
        pass
    emo = _emotion(etat, data, now) if "adrenaline" in etat else None
    surprise = now - float(data.get("_surprise") or 0) < duree_surprise(data)
    return {"h": {h: round(x, 3) for h, x in etat.items()}, "e": emo,
            "c": charge_de(v, a, etat.get("adrenaline"), surprise and "adrenaline" in etat)}


def modulation_rappel(mem, now=None, charge_moyenne=0.0):
    """(v2 seulement ; None en v1) f(enc_valence, enc_arousal, charge, récence) → (récence modulée, bonus d'état).

    Formes RELATIVES (sixième passage) : un souvenir non estampillé (charge None, valence None) n'y gagne ni n'y perd
    — donnée manquante, pas un souvenir neutre. L'émotionnel résiste à l'oubli, le neutre s'efface plus vite (écart à
    la charge moyenne) ; le bonus d'état ne vaut que si le présent ressemble PLUS à l'encodage que l'état habituel."""
    if not v2_actif(mem):
        return None
    v, a = valence_arousal(get_state(mem, now=now))
    v0, a0 = _bases_va()
    sombre = v - v0 < -MEM_GARDE

    def proximite(x, y, ev, ea):
        return max(0.0, 1.0 - math.hypot(x - ev, y - ea) / MEM_ETAT_DIST)

    def f(ev, ea, charge, rec):
        c = charge_moyenne if charge is None else charge
        rec = _clamp(rec + (1.0 - rec) * MEM_RESISTE * (c - charge_moyenne))
        if ev is None or ea is None:
            return rec, 0.0
        if sombre and ev - v0 < 0:                     # garde-fou : une humeur sombre ne rappelle pas plus de sombre
            return rec, 0.0
        return rec, MEM_ETAT_W * max(0.0, proximite(v, a, ev, ea) - proximite(v0, a0, ev, ea))
    return f


def valence_arousal(state):
    # Valence hédonique = liking : wanting (dopamine) + plaisir (endorphine) +
    # apaisement (sérotonine). PAS d'ocytocine (saillance sociale ≠ valence,
    # Shamay-Tsoory). Pénalité cortisol NON-LINÉAIRE : ne mord qu'au-delà d'un
    # seuil (l'effet mémoire en U-inversé du cortisol vit dans salience_boost).
    liking = (state["dopamine"] + state["endorphine"] + state["serotonine"]) / 3.0
    cort_pen = max(0.0, state["cortisol"] - 0.5) * 1.0
    v = liking - cort_pen
    # Arousal INCHANGÉ (l'histamine/éveil est déjà couvert par ce vecteur).
    a = (state["noradrenaline"] + 0.6 * state["dopamine"]
         + 0.5 * state["acetylcholine"] + 0.4 * state["cortisol"]) / 2.5
    if "adrenaline" in state:
        # v2 : le sursaut (adrénaline) éveille, le frein (GABA au-dessus de sa base) apaise ; même échelle au repos
        a = (state["noradrenaline"] + 0.6 * state["dopamine"] + 0.5 * state["acetylcholine"] + 0.4 * state["cortisol"]
             + 0.5 * (state["adrenaline"] - HORMONES_V2["adrenaline"][0])
             - 0.4 * (state["gaba"] - HORMONES_V2["gaba"][0])) / 2.5
    return max(-1.0, min(1.0, v)), _clamp(a)


def salience_boost(mem, now=None, hour=None):
    """Gating neuromodulateur de l'encodage : arousal + acétylcholine → encode + fort (0..1).

    Le cortisol suit un U-inversé (de Kloet MR/GR, McGaugh) : modéré il AMÉLIORE
    l'encodage (vigilance/consolidation), excessif il le DÉGRADE. Assumé : l'arousal
    porte déjà une composante linéaire 0.4*cortisol (éveil) ; le terme cort_u ci-dessous
    ajoute uniquement la cloche de consolidation (max à cortisol≈0.5, retombe aux
    extrêmes) — forme la plus simple, le cortisol n'entre qu'une fois par ce biais.

    NB : ne lit NI mélatonine NI endocannabinoïdes (aucune régression de saillance)."""
    s = get_state(mem, now=now, hour=hour)
    _, a = valence_arousal(s)
    cort = s["cortisol"]
    cort_u = 1.0 - (2.0 * (cort - 0.5)) ** 2   # cloche : max=1 à 0.5, ≤0 aux extrêmes
    return _clamp(0.6 * a + 0.4 * s["acetylcholine"] + 0.2 * max(0.0, cort_u))


# ============================================================
#  Couche LIMBIQUE / AFFILIATIVE (Phase 4c) — HORS-RAPPEL.
#
#  États MODÉLISÉS au niveau RÉSEAU (Singer-Klimecki, [solide]) — JAMAIS un
#  ressenti conscient, jamais des molécules brutes exposées :
#    * empathie   = résonance sociale        (insula / aMCC)      ← saillance sociale
#    * compassion = chaleur + motivation à AIDER (mOFC / VS)      ← état affiliatif positif
#    * mentalizing= attention aux buts de l'autre (TPJ / mPFC)    ← théorie de l'esprit
#  Le corrélat moléculaire (ocytocine/endorphine/acétylcholine) est HEURISTIQUE :
#  ces scalaires sont des fonctions PURES, DÉRIVÉES de l'état (aucune hormone neuve).
#
#  DISSOCIATION CLÉ (Singer-Klimecki) : la compassion N'EST PAS la détresse. Face à
#  un `probleme`/`echec` (empathie = résonance de la difficulté), le système répond
#  par la COMPASSION (chaleur + aide) SANS absorber la détresse. La compassion ne
#  dépend donc PAS du cortisol/noradrénaline : pas de couplage détresse→compassion=0.
#  Convertir la détresse en compassion = résilience (empathic distress → burnout ;
#  compassion → soin soutenable).
#
#  HORS-RAPPEL : ces scalaires n'entrent PAS dans Memory.retrieve, ni dans
#  valence_arousal / salience_boost (fonctions dérivées SÉPARÉES).
# ============================================================

def compassion(state):
    """État affiliatif positif = chaleur + motivation à aider (mOFC/VS), DISTINCT de la
    détresse. clamp(0.5·ocytocine + 0.5·endorphine) : ne lit NI cortisol NI noradrénaline."""
    return _clamp(0.5 * state["ocytocine"] + 0.5 * state["endorphine"])


def empathy(state):
    """Résonance sociale = clamp(ocytocine) (saillance sociale, double tranchant assumé,
    PAS « amour »). C'est la résonance de l'état de l'autre, pas encore le soin."""
    return _clamp(state["ocytocine"])


def mentalizing(state):
    """Attention aux buts de l'autre (TPJ/mPFC) = clamp(0.5·ocytocine + 0.5·acétylcholine)
    (saillance sociale × attention/encodage)."""
    return _clamp(0.5 * state["ocytocine"] + 0.5 * state["acetylcholine"])


def affiliative_state(mem):
    """Helper daemon/dashboard : {empathy, compassion, mentalizing} depuis l'état courant.

    États MODÉLISÉS au niveau réseau (corrélat moléculaire HEURISTIQUE) — jamais un
    ressenti conscient. HORS-RAPPEL : n'influence pas le score de mémoire."""
    s = get_state(mem)
    return {
        "empathy": empathy(s),
        "compassion": compassion(s),
        "mentalizing": mentalizing(s),
    }


def describe(mem):
    """Humeur lisible (pour le contexte / la CLI) — n'expose que l'ÉTAT : libellé
    d'humeur + valence/arousal dérivés, JAMAIS les molécules brutes."""
    s = get_state(mem)
    v, a = valence_arousal(s)
    if v >= 0.15 and a >= 0.5:
        mood = "énergique et confiante"
    elif v >= 0.15:
        mood = "calme et sereine"
    elif v <= -0.15 and a >= 0.5:
        mood = "tendue, en alerte"
    elif v <= -0.15:
        mood = "lasse, en retrait"
    else:
        mood = "posée, neutre"
    return f"{mood} (valence {v:+.2f}, arousal {a:.2f})"
