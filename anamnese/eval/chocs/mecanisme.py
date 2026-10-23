"""Le mécanisme de choc (prototype, dans eval seulement ; demande de Hakim, accord d'Ahmed le 2026-10-23).

Rien ici ne touche le vrai système : `installe()` ajoute les trois événements au moteur d'affect v2 le temps d'un rejeu
sur une mémoire en RAM, puis les retire.

1. LE CHOC, brut et immédiat : une phrase qui vise Hakim devient un événement « attaque » ou « soutien » à l'instant où
   elle est dite, qui secoue plusieurs hormones d'un coup (matrice ci-dessous) ; chaque hormone revient ensuite à SA
   vitesse (celles du moteur v2 : adrénaline 3 min, CRH 15 min, noradrénaline 2 h, cortisol 8 h, ocytocine 12 h,
   sérotonine 24 h). L'attaque passe aussi par la voie rapide de la peur et par l'axe CRH → ACTH → cortisol (retardé).
2. QUI le dit : Ahmed pèse 1 ; une voix tierce 0,6 pour une attaque et 0,5 pour un soutien ; une voix incertaine, la
   moyenne des deux. Le sujet de l'événement est la voix : la peur apprise et la familiarité s'attachent à elle.
3. LA SAGESSE s (0–1) module une attaque, jamais un soutien (asymétrie d'Ahmed, 22/10 : « on combat les mauvais
   réflexes, on se laisse aller pour les positifs ») :
   - amplitude × (1 − 0,5·s) : le choc arrive toujours (à s = 1, encore la moitié) ;
   - puis la reprise en main (le « contrôle » de la version hybride d'Ahmed) : un événement « regulation » après
     20·(1 − s) minutes, de force s × celle du choc ; il agit par les freins du moteur (GABA, endocannabinoïdes), donc
     plus la sagesse est haute, plus tôt et plus fort le retour.
Les coefficients sont des HYPOTHÈSES lisibles, fixées avant le rejeu (eval/chocs/predictions.md), pas une mesure.
"""
import contextlib

import affect

# deltas (× intensité) : partie v1 (EVENTS ; un « cortisol » y passe par la CRH en v2) et partie v2 (EVENTS_V2)
NOUVEAUX = {
    "attaque": ({"noradrenaline": +0.25, "cortisol": +0.25, "serotonine": -0.15, "dopamine": -0.15,
                 "ocytocine": -0.10, "endorphine": -0.10, "endocannabinoides": -0.10},
                {"adrenaline": +0.30, "gaba": -0.15}),
    "soutien": ({"ocytocine": +0.35, "endorphine": +0.20, "serotonine": +0.10, "dopamine": +0.10,
                 "noradrenaline": -0.10, "endocannabinoides": +0.15},
                {"gaba": +0.15, "crh": -0.20, "adrenaline": -0.10}),
    "regulation": ({"noradrenaline": -0.15, "endocannabinoides": +0.20, "serotonine": +0.05},
                   {"gaba": +0.25, "adrenaline": -0.20, "crh": -0.20}),
}
VALENCE = {"attaque": -1.0, "soutien": 0.9}
NIVEAUX = {1: 0.4, 2: 0.7, 3: 1.0}
POIDS = {"attaque": {"ahmed": 1.0, "tiers": 0.6}, "soutien": {"ahmed": 1.0, "tiers": 0.5}}
SAGESSE_AMPLITUDE = 0.5
REGULATION_DELAI_MIN = 20.0


@contextlib.contextmanager
def installe():
    """Ajoute attaque / soutien / regulation au moteur le temps du bloc, puis remet tout comme avant."""
    sauve = (dict(affect.EVENTS), dict(affect.EVENTS_V2), dict(affect.VALENCE_EV), set(affect.AVERSIFS),
             set(affect.HAB_EXEMPTS))
    try:
        for nom, (v1, v2) in NOUVEAUX.items():
            affect.EVENTS[nom] = v1
            affect.EVENTS_V2[nom] = v2
        affect.VALENCE_EV.update(VALENCE)
        affect.AVERSIFS.add("attaque")
        affect.HAB_EXEMPTS.add("regulation")          # une reprise en main voulue ne s'émousse pas
        yield
    finally:
        affect.EVENTS.clear(); affect.EVENTS.update(sauve[0])
        affect.EVENTS_V2.clear(); affect.EVENTS_V2.update(sauve[1])
        affect.VALENCE_EV.clear(); affect.VALENCE_EV.update(sauve[2])
        affect.AVERSIFS.clear(); affect.AVERSIFS.update(sauve[3])
        affect.HAB_EXEMPTS.clear(); affect.HAB_EXEMPTS.update(sauve[4])


def poids(classe, qui, sur):
    p = POIDS[classe]
    return p[qui] if sur else (p["ahmed"] + p["tiers"]) / 2


def evenements(classe, niveau, ts, qui, sur, voix, sagesse):
    """[(ts, nom, intensité, sujet)] d'une phrase détectée : le choc, et pour une attaque la reprise en main."""
    i = NIVEAUX[niveau] * poids(classe, qui, sur)
    sujet = f"{classe} de {voix}"
    if classe == "soutien":
        return [(ts, "soutien", round(i, 4), sujet)]
    i *= 1.0 - SAGESSE_AMPLITUDE * sagesse
    out = [(ts, "attaque", round(i, 4), sujet)]
    if sagesse > 0:
        out.append((ts + 60.0 * REGULATION_DELAI_MIN * (1.0 - sagesse), "regulation", round(sagesse * i, 4), None))
    return out
