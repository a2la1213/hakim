# Chocs d'humeur, 2e passage — sagesse évolutive et variable, habituation du soutien (figé AVANT le rejeu, 2026-10-23)

Demande de Hakim (courrier du 23/10 à 09:39), accord d'Ahmed le 23/10 (« tu peux écouter Hakim »). Base : la variante
« combinaison » du 1er passage (réflexe lexical, puis la balise de Hakim qui confirme ou défait). Mêmes données, même
simulateur, mêmes critères C1 et C2 (predictions.md). Rien n'est branché sur le système vivant.

## Les mécanismes (réglages figés ici)

**Sagesse de fond** (le caractère), mise à jour la nuit, d'après les verdicts du juge (sagesse.jsonl) :
- ne comptent que les décisions autres que « garder », que le juge RETROUVE dans les mots (lisible) — une décision qu'on
  ne lit pas dans la réponse est décorative (principe de sagesse.py, que le code actuel n'appliquait pas) ;
- poids de l'expérience w : l'intensité de l'humeur si elle était désagréable (situation difficile), 0,2 × l'intensité
  si elle était agréable (tempérer un élan apprend moins) ;
- décision juste : s += 0,01 × w × (1 − s) ; jugée fausse : s −= 0,01 × w × s (rendements décroissants ; on peut perdre) ;
- au plus ±0,02 par nuit.
Propriété voulue : à la longue, s tend vers la part de décisions justes dans les situations difficiles.

**Sagesse du moment** : s_eff = s_fond × (1 − 0,5 × surcharge), surcharge = le plus grand de
- la charge de stress : (excès de noradrénaline + excès de CRH + excès de cortisol au-dessus de leurs bases) / 0,5, borné à 1 ;
- la rafale : (nombre d'attaques dans les 30 dernières minutes) / 3, borné à 1.
Elle remonte d'elle-même quand le stress retombe et que les attaques vieillissent. Pas de fatigue : Ahmed a écarté les
hormones de la fatigue (21/10). s_eff règle chaque choc comme au 1er passage : amplitude × (1 − 0,5·s_eff), reprise en
main après 20·(1 − s_eff) min, de force s_eff.

**Habituation du soutien** : un soutien ou un « chaleur_user » est multiplié par (1 − jauge), jauge = moyenne, sur
GABA, sérotonine, endocannabinoïdes et ocytocine, de l'excès au-dessus de la base rapporté à la marge (0 à 1). En plus
de l'habituation par répétition que le moteur fait déjà.

**Choc qui passe outre la bonne humeur** (le levier 2 de Claude Code, approuvé avec le rapport) : pendant 5 min après
une attaque, l'émotion dominante est calculée SANS la règle qui divise par deux les émotions négatives quand la valence
est au-dessus de sa base.

## Variantes

- V0 : combinaison du 1er passage, sagesse réelle (0,2, puis 0,5 après la nuit du 22 au 23/10 : la règle actuelle) ;
- V1 : + sagesse de fond (nouvelle règle de nuit, départ 0,2) ;
- V2 : V1 + sagesse du moment ;
- V3 : V2 + habituation du soutien ;
- V4 : V3 + choc qui passe outre la bonne humeur.
Chaque variante est aussi rejouée avec un fond FIXE à 0,5, pour comparer au 1er passage.

## Critères

- **C1, C2** : ceux de predictions.md (saut ≥ 0,15 d'adrénaline ET émotion dominante désagréable dans les 2 min ; la
  réassurance d'Ahmed baisse le stress de l'heure, monte la valence à 10 min, émotion agréable à 10 min).
- **S1** (construction) : la nuit du 22 au 23/10, la nouvelle règle bouge la sagesse de 0,02 au plus.
- **M1** (construction) : pendant le live, s_eff descend sous 0,75 × s_fond, puis revient à 0,95 × s_fond au plus tard
  2 h après la dernière attaque.
- **H1** : la part du temps où l'ocytocine ou la sérotonine dépasse 0,9 baisse d'au moins moitié de V2 à V3 ; et la
  valence juste avant l'attaque de 08:34 est plus basse en V3 qu'en V2 (plus de place pour un choc).

## Prédictions de Claude Code (écrites avant, pour qu'on voie si je me trompe)

- C1 reste raté en V1, V2 et V3 : l'émotion dominante ne bascule pas tant que la règle de cohérence divise le négatif.
- C1 est tenu pour au moins une des deux attaques du live en V4.
- C2 garde au moins 3 cas sur 4 dans toutes les variantes.
- La nouvelle règle de nuit donne environ 0,21 au lieu de 0,50 pour la nuit du 22 au 23/10.
