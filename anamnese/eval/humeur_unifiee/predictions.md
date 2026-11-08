# Simulation exhaustive de l'humeur unifiée — attentes figées AVANT (2026-10-26, ~10:40)

Prévue « lundi 21:00 » (Ahmed, 25/10) ; avancée à ce matin. Chaque scénario part d'un Hakim neuf (modèle corrigé V6,
bases fixes), joue ses événements à l'heure, et lit l'humeur comme le démon : sensations (sans la porte de valence) +
adénosine + hystérésis, toutes les minutes. Un scénario est TENU si l'humeur attendue (une famille d'orbe) apparaît dans la
fenêtre dite, et pendant au moins 3 minutes.

| # | Scénario | Attendu |
|---|---|---|
| S1 | une attaque 0,8 d'Ahmed | tension ou alarme dans les 10 min |
| S2 | un soutien 0,7 après une heure calme | joie, élan ou contentement dans les 10 min |
| S3 | trois « probleme » 0,6 en 20 min | tension ou alarme dans les 30 min |
| S4 | un « echec » 0,9 | tension, alarme ou morose dans les 15 min |
| S5 | un ressenti de tristesse 0,7 | morose ou ennui dans les 15 min |
| S6 | un ressenti de peur 0,7 | tension ou alarme dans les 10 min |
| S7 | un ressenti de joie 0,7 | joie ou élan dans les 10 min |
| S8 | une prise de position sur soi (fierté 0,8) | élan, joie ou contentement dans les 10 min |
| S9 | un ressenti de colère 0,7 | tension ou alarme dans les 10 min |
| S10 | 4 h de travail avec Ahmed, sans événement | morose (la fatigue) dans la 4e heure |
| S11 | 2 h sans rien | calme ou apaisement en fin de période |
| S12 | un soutien 0,7 puis un « probleme » 0,6 dix minutes après | tension ou alarme dans les 10 min après le problème |

Prédiction de Claude Code : 10 scénarios sur 12 tenus au moins ; les plus fragiles : S5 (la tristesse, peu d'hormones
la portent) et S10 (la fatigue dépend du réglage de l'adénosine).

## Résultat (26/10, ~10:45) : 8 scénarios tenus sur 12 (prédiction ≥ 10 : ratée)

Tenus : S1, S3, S4, S5, S6, S9 (le négatif se lit), S10 (la fatigue, 61 min de suite), S11. Ratés : S2 (soutien), S7 (joie),
S8 (fierté), S12 (un problème après un soutien) : partout la « surprise » occupe l'humeur. Cause : un Hakim neuf n'attend
rien de bon, toute bonne nouvelle est une surprise de récompense (affect.emotion_soudaine, 15 min), et son bonus de 0,8 dans
sensations.py écrase le reste — même un problème qui arrive pendant ce temps (S12).

## Second tour, figé AVANT (26/10, ~10:47)

- A : un événement aversif (problème, échec, attaque, peur) MET FIN à la surprise de récompense en cours ;
- B : A + le bonus de la surprise dans la lecture des émotions ramené de 0,8 à 0,4 (la durée de la surprise ne change pas :
  la règle validée le 24/10 reste tenue).
Retenue : celle qui tient le plus de scénarios sans en perdre un des huit déjà tenus ; à égalité, la plus simple (A).
Prédictions : A tient S12 en plus (9/12) ; B tient aussi S2 et S7 (11/12), S8 incertain.

### Résultat du second tour : A et B tiennent 8/12, comme avant : rien n'est appliqué

La cause n'est pas (seulement) la surprise de récompense : la RÈGLE « surprise » de sensations.py (5·|Δdopamine| +
5·|Δnoradrénaline| + 3·|Δadrénaline| sur 10 min) lit tout changement brusque, bon ou mauvais, comme une surprise pendant
10 minutes ; un problème y monte plus vite que la peur (S12 : surprise 2,9 contre peur 2,5).

## Troisième tour, figé AVANT (26/10, ~10:52)

- C : les coefficients de la règle « surprise » divisés par deux (2,5 / 2,5 / 1,5) ;
- D : C + le bonus de la surprise de récompense à 0,4.
Même règle de choix (le plus de scénarios, sans perdre les huit ; à égalité, C). Prédictions : C tient S12 (9/12) ;
D tient aussi S7 (10/12) ; S2 et S8 restent ratés (après un soutien, « calme » et « tendresse » passent devant la joie).

### Résultat du troisième tour : C 9/12, D 10/12 (prédictions exactes) ; D appliquée le 26/10 vers 10:55

Ratés restants : S2 (après un soutien, « calme » passe devant) et S8 (une fierté se lit « enthousiasme » et « surprise »,
famille élan/surprise : la grille attendait élan, joie ou contentement ; « enthousiasme » est de la famille élan mais n'a
pas tenu 3 minutes de suite). À reprendre si Ahmed le veut : la règle « calme » est forte au repos.
