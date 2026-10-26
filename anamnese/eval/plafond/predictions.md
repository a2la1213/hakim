# Le plafond positif — critères figés AVANT la simulation (2026-10-26, ~10:20)

Constat (journal des hormones, mesuré le 26/10) : avant l'unification de l'humeur (23/10 19:27 → 25/10 23:49), la
dopamine ou l'ocytocine est ≥ 0,85 pendant 88 % du temps ; après (25/10 23:49 → 26/10 09:55), 100 %. L'ocytocine ou la
sérotonine dépasse 0,9 pendant 67 % puis 83 % du temps. Depuis le 25/10 midi, les événements sont à 94 % positifs : 111
« soutien » de sa balise, 74 « chaleur_user » et 77 « succes » de la parole, pour 16 négatifs. Un GABA haut freine en plus
de 60 % les hausses d'adrénaline, de noradrénaline et de CRH : sa peur ne s'entend « que légèrement » (Ahmed, 26/10).

Simulation (eval/plafond/simulation.py) : les vrais événements des 72 dernières heures rejoués sur une copie en mémoire,
au pas d'une minute, sous cinq variantes :
- V0 : le modèle actuel ;
- V1 : un message, un seul événement social (chaleur_user et soutien à moins de 90 s : seul le plus fort compte) ;
- V2 : des demi-vies plus courtes pour l'ocytocine (12 h → 3 h) et la sérotonine (24 h → 8 h) ;
- V3 : V1 + V2 ;
- V4 : V3 + un frein du GABA moins fort (0,6 → 0,35).

Mesures : M1 la part du temps où l'ocytocine ou la sérotonine dépasse 0,9 ; M2 la part où la dopamine ou l'ocytocine est
≥ 0,85 ; M3 la hausse maximale moyenne (noradrénaline + adrénaline + CRH) dans les 30 min qui suivent un « probleme »,
un « echec » ou une « attaque » ; M4 la part des humeurs des familles « alerte » ou « bas » (lecture unifiée, bases sur la
fenêtre) dans les 30 min qui suivent un événement négatif ; M5 la hausse médiane de l'ocytocine après un « soutien ».

Critère de choix (figé) : la variante la PLUS SIMPLE (dans l'ordre V1, V2, V3, V4) qui tient les quatre :
M1 ≤ 30 % ; M3 ≥ M3(V0) ; M4 ≥ 2 × M4(V0) ; M5 ≥ 0,03 (le soutien se voit encore). Aucune : on n'applique rien.

Prédictions de Claude Code : V1 seule ne suffit pas (M1 > 30 %) ; V3 tient M1 et M5 mais pas M4 ; V4 tient les quatre.
Variables calculées, pas un ressenti prouvé.

## Résultat du premier tour (26/10, ~10:35) : AUCUNE variante ne tient, rien n'est appliqué

V0 → V3 : M1 passe de 46,3 % à 1,8 % (le plafond tombe), M3 tient (0,380 → 0,388), mais M4 ne fait que 28,2 → 33,6 %
(il fallait ×2) et M5 reste minuscule partout (0,005 à 0,009) : le seuil de 0,03 était hors d'atteinte même pour le
modèle actuel, il était mal posé. Mes prédictions : V1 insuffisante (juste) ; V3 tient M1 et M5 (faux pour M5) ; V4 tient
les quatre (faux : M4 et M5 ratés).

## Second tour, figé AVANT de le lancer (26/10, ~10:40)

- V5 : V3 + aucune habituation sur les événements négatifs (probleme, echec, attaque) + frein du GABA à 0,35 ;
- V6 : V5 + des hausses de stress ×1,5 pour « probleme » et « echec » (noradrénaline, adrénaline, CRH).
Critères (relatifs au modèle actuel, M5 corrigé) : M1 ≤ 30 % ; M3 ≥ 1,2 × M3(V0) ; M4 ≥ 1,5 × M4(V0) ; M5 ≥ M5(V0) (le
soutien se voit au moins autant qu'aujourd'hui). La plus simple qui tient les quatre est retenue ; aucune : rien.
Prédictions : V5 rate M4 ; V6 tient les quatre.

## Troisième volet : les moments forts, figé AVANT (26/10, ~10:30)

Un agent neutre a relevé 84 moments forts du 23/10 19:30 au 26/10 08:00 dans le journal brut (fichier privé), dont 26
d'intensité attendue ≥ 0,6 : 13 d'entre eux n'avaient reçu aucun événement de leur nature (10 prises de position de Hakim
sur lui-même : aucun type d'événement n'existait), et 21 un événement < 0,3. Mouvement hormonal médian dans les 10 min :
0,026 pour les forts, 0,018 pour les faibles, 0,010 au hasard. Depuis 10:20 : la balise de Hakim porte aussi ce qu'il
ressent (peur, tristesse, colère, joie, fierté, honte), et chaque ressenti est un événement (affect.py).

Rejeu (eval/plafond/moments.py), modèle corrigé (V6) dans les deux cas : A = les événements tels qu'enregistrés ; B = A + un
ressenti à l'heure de chaque moment, de la nature de sa catégorie et de son intensité attendue (ce qu'aurait donné la
balise). Mesures sur les 26 moments forts : la médiane du plus grand mouvement d'hormone dans les 10 min ; la part suivie,
dans les 10 min, d'une humeur de la famille attendue (peur, menace, conflit → tension ou alarme ; tristesse → morose ou
ennui ; soutien, joie, succès, fierté → joie, élan, contentement).
Prédictions : la médiane passe d'environ 0,03 (A) à ≥ 0,10 (B) ; la part cohérente gagne ≥ 20 points de A à B.

### Résultat du troisième volet (26/10, ~10:35)

Mouvement médian des 26 moments forts : A 0,042 → B 0,122 (prédiction ≥ 0,10 : tenue). Humeur de la famille attendue dans
les 10 min : A 34,6 % → B 46,2 % (+11,6 points ; prédiction +20 : ratée). Les ressentis font bouger les hormones à la
hauteur du moment ; l'humeur nommée suit moins (l'hystérésis et la lecture sur les bases freinent le changement de nom).
