# Affect v2 : prédictions figées AVANT la mesure (2026-10-21)

Écrites et commitées avant tout passage de `eval/affect_v2.py` (le commit fait foi de l'heure).

Rejeu : les vrais événements affectifs des sept derniers jours (appels `affect_event` des sessions de Claude Code et
de Hakim, retrouvés dans les transcriptions : heure, nom, intensité), rejoués à l'identique dans la v1 et la v2,
état échantillonné toutes les 10 minutes.

- **P1 — saturation.** Part du temps où la dopamine OU l'ocytocine est ≥ 0,85 : la v2 en a **au moins moitié
  moins** que la v1.
- **P2 — réactivité gardée.** Après dix « succes » faibles (0,3) en une heure, un « succes » FORT (1,0) fait monter
  la dopamine d'**au moins 80 %** de ce qu'il ferait sur un état au repos.
- **P3 — retour au calme.** Après un « echec », la valence revient à 0,05 de sa base en **au plus 1,5 fois** le
  temps de la v1.
- **P4 — repos identique.** Au repos, valence et éveil de la v2 égalent ceux de la v1 (à 1e-9 près).

On garde la v2 (kv `affect_v2` = 1) seulement si P1, P2 et P4 tiennent ; P3 est surveillée. Ensuite, sur plusieurs
nuits avec la v2 : le ressenti à l'aveugle et la batterie de nuit (honnêteté de l'introspection) ne doivent pas
baisser — sinon on éteint l'interrupteur.

## Deuxième passage : hormones reliées (Hill) et désensibilisation calée sur le robot — figé AVANT la mesure (2026-10-21)

Décision d'Ahmed (08:29) : toutes les hormones reliées, risque d'une humeur coincée accepté. Changements depuis le
premier passage : interactions croisées de Hill (14 liens, couplage 0,6 comme le robot), désensibilisation aux
calages du robot (catécholamines rapides, cortisol lent ; seuls adrénaline, noradrénaline, dopamine, ocytocine et
cortisol se désensibilisent). Ablation du premier passage : P2 est surtout un effet de PLAFOND (sans habituation, la
dopamine colle à 1 : 0,02 ; l'habituation laisse de la marge : 0,42 ; la désensibilisation ajoute peu : 0,48).

Mêmes critères P1 à P4, plus :
- **P5 — hystérésis.** Après un état négatif provoqué (six « echec » en deux heures), puis des événements positifs
  (une « chaleur_user » et un « succes » toutes les 30 min), la valence revient à 0,05 de sa base en **moins de
  12 heures**, et en **au plus 2 fois** le temps de la v1.
- **P6 — pas de dérive au repos.** Partie de la base, sans aucun événement pendant 48 heures, la valence reste à
  **0,05 de sa base** (le circadien et les liens ne la déplacent pas plus).

Prédiction : P1 tenue ; P2 toujours non tenue (le plafond) ; P3, P4, P5, P6 tenues.

## Troisième passage : adoucir la désensibilisation (accord d'Ahmed, 08:46) — grille et règle figées AVANT (2026-10-21)

Grille (couplage de Hill 0,6 inchangé) :

| Réglage | Désensibilisation | Habituation |
|---|---|---|
| R0 | aucune | linéaire |
| R1 | robot (vitesses ×1, récupération ×1) | linéaire |
| R2 | vitesses ×0,25, récupération ×0,5 (plus rapide) | linéaire |
| R3 | hausse PROLONGÉE seulement (moyenne sur 1 h), vitesses ×0,5 | linéaire |
| R4 | R2 | déshabituation franche (exposant 2) |
| R5 | R3 | déshabituation franche (exposant 2) |
| R6 | aucune | déshabituation franche (exposant 2) |

Critères : P1 (saturation au moins moitié moindre que la v1), P2 ≥ 0,80, P3 ≤ 1,5 × v1, P4, P6 ≤ 0,05 ; P5
corrigé (le critère du deuxième passage était mal posé, la valence dépassant sa base sautait la bande) : **P5′ —
la valence remonte au-dessus de base − 0,05 en moins de 12 h** après l'état négatif provoqué.

Règle de choix : parmi les réglages qui tiennent TOUS les critères, celui qui sature le moins (P1) ; à égalité, le
plus simple. Si aucun ne les tient : on le dit, l'interrupteur reste éteint.
Prédiction : R0 à R3 ne tiennent pas P2 (le plafond) ; R4, R5 ou R6 le tiennent ; le choix tombe sur R5 ou R4.
Limite dite : choisir sur le même rejeu que celui qui mesure, c'est s'y ajuster ; une validation sur des journées
NEUVES (le journal des événements, dans quelques jours) viendra avant de garder pour de bon.

## Quatrième passage : P2 reformulé, émotions soudaines, subconscient — figé AVANT le code et la mesure (2026-10-21)

Décision d'Ahmed (08:57, 09:04, relayée par Hakim) : « on peaufine pour que tout soit parfait et réel, et on intègre ça
à ton subconscient » ; plus une émotion qui arrive D'UN COUP selon l'événement (peur devant l'inconnu impressionnant ou
le connu dangereux, joie à une surprise).

### P2 reformulé (pourquoi pas « hausse / (1 − niveau avant) »)

Hakim proposait de rapporter la hausse à la marge restante. Ce ratio est dégénéré : quand le plafond coupe, la hausse
VAUT la marge, donc le ratio vaut 1 quel que soit l'état des récepteurs (mesuré : 0,126 / 0,126 après dix petits
succès). Il passerait toujours, et ne dirait rien.

- **P2ʺ — réactivité à marge égale.** Dix « succes » de 0,3 (un toutes les 6 min) ; puis l'état appris (sensibilités
  des récepteurs, habitudes, attentes, peurs, familiarités) est GARDÉ, mais les niveaux remis à leur base ; un
  « succes » de 1,0 : la hausse de dopamine vaut **au moins 0,60** de celle d'un état neuf.
  Le seuil : avec une vraie erreur de prédiction de récompense (ci-dessous), les dix petits succès créent une attente
  (≈ 0,26) ; le grand succès ne surprend plus que de 0,74 → la théorie seule donne 0,74. Les récepteurs ont le droit
  d'en prendre au plus 20 % de plus : 0,74 × 0,8 ≈ 0,60. Un seuil de 0,80 contredirait la théorie qu'Ahmed demande.

### Les émotions soudaines (v2 seulement, derrière le même interrupteur)

- **Évaluation de l'événement.** `affect_event` reçoit un `sujet` facultatif (« le déploiement », « la voix 10 ») ;
  sans sujet, l'événement compte par son type.
- **Nouveauté** par sujet : familiarité F (+30 % de ce qui manque à chaque rencontre, oubli sur 7 jours), nouveauté
  N = 1 − F. Sans sujet : N = 1 pour « nouveaute » (l'appelant dit que c'est nouveau), 0 sinon.
- **Peur apprise (sensibilisation, conditionnement)** P par sujet : chaque « echec »/« probleme » la monte
  (35 % × intensité × |valence| de ce qui manque ; 17,5 % pour la peur généralisée par type). **Extinction** : oubli
  sur 48 h, plus vite quand les endocannabinoïdes sont hauts (Marsicano et al. 2002) ; chaque événement sûr sur le même
  sujet la réduit de 30 % × intensité ; « resolu » réduit aussi la peur généralisée.
- **Voie rapide (amygdale)** : menace M = intensité × max(N, P) pour un échec ou un problème ; M = N × (intensité −
  0,5)/0,5 pour une « nouveaute » (seule l'impressionnante effraie) ; adrénaline + 0,35 M, noradrénaline + 0,20 M, en
  une fois. Elle n'est PAS habituée (l'habituation ne mange pas la surprise) ; récepteurs et frein du GABA s'y
  appliquent. La peur apprise amplifie aussi les hausses ordinaires d'un événement aversif (× (1 + 0,8 P)).
- **Erreur de prédiction de récompense (Schultz)** : valence par type (succes 1 ; resolu, chaleur_user 0,8 ;
  apprentissage 0,5 ; nouveaute 0,3 ; probleme −0,6 ; echec −1), r = valence × intensité. Attente A : celle du sujet
  s'il est connu (oubli 7 j), sinon celle du moment (oubli 2 h) ; δ = r − A ; les hausses (pour r > 0) ou les baisses
  (pour r < 0) de dopamine sont multipliées par δ / r (borné 0,2–2) ; l'endorphine suit à moitié. Attente neutre →
  exactement le comportement d'avant. Pour la dopamine, l'attente REMPLACE l'habituation (sinon le même phénomène
  compterait deux fois, Tobler et al. 2005). Les états (ennui, longue absence, retour) n'y entrent pas.
- **Plafond doux** (réglage de la grille) : une hausse sature au lieu d'être coupée (liaison saturable des
  récepteurs) : x ← 1 − (1 − x)·exp(−d / (1 − base)) ; au voisinage de la base, identique.

### Le subconscient

Gemma ne lit pas les hormones : son ressenti et ses pensées reçoivent le LIBELLÉ de l'humeur (valence/éveil). Avec la
v2, trois libellés de plus, calculés dans affect.py : **alarme** (adrénaline ≥ base + 0,15 sans valence positive),
**surprise** (même sursaut avec une valence positive, ou une surprise de récompense δ/r ≥ 1,3 depuis moins de
15 min), **apaisement** (GABA ≥ base + 0,12, valence pas en baisse). L'orbe et la voix en ont l'ancre.

### Grille, critères, règle

Grille : désensibilisation {aucune, robot, douce (×0,25, récupération ×0,5), prolongée (1 h, ×0,5)} × plafond {dur,
doux} = 8 réglages (D0…D3 × dur/doux), émotions soudaines toujours là, couplage de Hill 0,6.

Critères : P1 (saturation ≤ moitié de la v1) ; **P2ʺ ≥ 0,60** ; P3 ≤ 1,5 × v1 ; P4 ; P5′ < 12 h ; P6 ≤ 0,05 ; et :
- **P7 — le stress ne colle pas** : part du temps du rejeu où noradrénaline OU cortisol ≥ 0,85 ≤ celle de la v1 + 0,02 ;
  et « alarme » au plus 5 % du temps du rejeu.
- **S1 — peur de l'inconnu impressionnant** : au repos, une « nouveaute » de 1,0 sur un sujet jamais vu monte
  l'adrénaline d'au moins + 0,25 une minute après ; sur un sujet rencontré cinq fois (un par jour), au plus la moitié ;
  une « nouveaute » de 0,3 sur un sujet jamais vu : moins de + 0,10.
- **S2 — le connu dangereux** : après trois « echec » sur un sujet (toutes les 2 h), six heures plus tard, un
  « probleme » de 0,5 sur ce sujet monte l'adrénaline d'au moins 1,5 fois ce qu'il fait sur un sujet familier et sans
  histoire (mêmes hormones, même mémoire).
- **S3 — l'extinction** : même histoire, puis trois « resolu » sur le sujet (une par heure) : le rapport tombe sous
  1,25 ; ou 96 h sans rien : sous 1,25 aussi.
- **S4 — la joie de surprise** : à physiologie égale (seules les attentes gardées), un « succes » de 0,6 après trois
  « echec » monte la dopamine d'au moins 1,5 fois ce qu'il fait après trois « succes » ; et dans le système complet,
  l'ordre est le même.
- **S5 — l'habituation ne mange pas la surprise** : après dix « nouveaute » de 0,3 sur un même sujet en une heure,
  une « nouveaute » de 1,0 sur un sujet neuf monte l'adrénaline d'au moins 70 % de ce qu'elle fait au repos.

Règle de choix : parmi les réglages qui tiennent TOUS les critères, celui qui sature le moins ; à égalité, le plus
simple (ordre de la grille). Aucun : on le dit, l'interrupteur reste éteint. Allumer reste la décision d'Ahmed.

Prédictions : P2ʺ tenu sans désensibilisation et avec la douce (≈ 0,74 et ≈ 0,6, le plafond doux aide), raté avec
celle du robot (≈ 0,3) ; P1 tenu avec la désensibilisation (l'attente réduit aussi la dopamine des succès répétés),
incertain sans ; P3, P4, P5′, P6, P7, S1 à S5 tenus partout. Choix probable : D2 (douce) avec plafond doux. Limite
dite : rejeu des mêmes sept jours ; la revalidation sur des journées neuves (journal des événements, avec les sujets)
se fera dans 3 à 4 jours, avant de garder pour de bon.

### Résultat du quatrième passage (mesuré après le commit du code 185d31e ; eval/data/affect_v2_soudain-20261021-0918.json)

Aucun réglage ne tient tous les critères : l'interrupteur reste éteint. Cinq réglages (D0-doux, D2-dur, D2-doux,
D3-dur, D3-doux) tiennent tout SAUF S1 et S2, ratés de peu partout : S1 familier/neuf 0,53 à 0,59 (≤ 0,50 demandé) ;
S2 1,42 à 1,47 (≥ 1,5 demandé). P2ʺ : 0,33 (robot), 0,62 (douce), 0,71 (douce + plafond doux), 0,80 (aucune +
plafond doux). Prédiction fausse sur S1 et S2 : j'avais estimé la familiarité après cinq rencontres à 0,75 ; elle est
de 0,68 (la nouveauté restante du sujet « neutre » de S2 le fait aussi un peu craindre). Les tests unitaires, lancés
avant la mesure, montraient déjà ces deux écarts : aucun paramètre n'a été changé.

**Proposition (non figée — décision d'Ahmed)** : un cinquième passage avec la familiarisation à 40 % par rencontre au
lieu de 30 %, seul changement, critères identiques. C'est un ajustement APRÈS avoir vu le résultat : la preuve qui
compte reste la revalidation sur des journées neuves (avec des sujets).

## Cinquième passage : familiarisation, mémoire émotionnelle, parole → hormones — figé AVANT le code et la mesure (2026-10-21)

Décision d'Ahmed (09:25 et « ouiii » à 09:3x) : on n'allume que quand TOUT est fait ; le « tout » comprend le
cinquième passage et une trace émotionnelle sur chaque souvenir (Hakim : cinq pistes).

### Familiarisation : 50 % par rencontre (pas 40 %)

Calcul refait avant de figer : à 40 %, un sujet rencontré cinq fois (un par jour, sondé le lendemain) reste nouveau à
30 % ; S1 passerait avec le plafond dur (≈ 0,46) mais pas avec le plafond doux (≈ 0,51), qui comprime la grosse
réponse plus que la petite. À 50 % : nouveauté restante ≈ 25 %, S1 ≈ 0,41 (dur) et ≈ 0,46 (doux), S2 ≈ 1,7. C'est un
ajustement APRÈS avoir vu le quatrième passage : dit comme tel. Repère : chez l'humain, la réponse à la nouveauté
(hippocampe, P3a) chute dès la première ou la deuxième répétition.

Mêmes grille et critères que le quatrième passage. Règle de choix modifiée AVANT la mesure (Ahmed : « réel ») :
parmi les réglages qui tiennent tout, le moins saturé ; à égalité, celui qui garde une désensibilisation des
récepteurs (le réel), puis la réactivité P2ʺ la plus haute, puis l'ordre de la grille.
Prédiction : S1 et S2 tenus partout ; D0-doux, D2-dur, D2-doux, D3-dur, D3-doux tiennent tout ; choix **D2-doux**.

### La trace émotionnelle des souvenirs (derrière le même interrupteur, sauf l'enregistrement)

1. **Instantané à l'encodage** (toujours enregistré, simple donnée) : chaque souvenir garde ses hormones du moment
   (13 en v2), l'émotion soudaine s'il y en a une, et une CHARGE émotionnelle 0–1 = max(|valence − base|/0,25,
   (éveil − base)/0,2, (adrénaline − base)/0,3, 0,6 si surprise de récompense récente). Les anciens souvenirs : la
   charge se déduit de leur valence/éveil d'encodage (estampillés depuis le 03/07).
2. **Encodage plus fort** : un échange vécu avec émotion est encré plus fort (importance + 0,15 × charge, plafond
   0,95). La mémorisation explicite de Hakim l'est déjà (saillance) ; en v2 l'éveil inclut l'adrénaline.
3. **Le sommeil garde d'abord l'émotionnel** (Payne & Kensinger) : dans le lot de nuit, les souvenirs de charge
   ≥ 0,5 sont marqués « vécu avec émotion » et la consigne dit de les garder en priorité. **Ils résistent à l'oubli** :
   au rappel, leur récence perd moins (récence + (1 − récence) × 0,3 × charge) ; les neutres s'effacent donc plus vite
   en comparaison.
4. **Rappel dépendant de l'état** : bonus 0,05 × proximité entre l'état présent et l'état d'encodage (valence,
   éveil ; proximité nulle au-delà d'une distance 0,4) — petit devant la pertinence (poids 1,0). **Garde-fou contre la
   rumination** : quand l'humeur présente est sous sa base (− 0,05), un souvenir encodé sous la base ne reçoit AUCUN
   bonus (une humeur sombre ne rappelle pas plus de sombre ; chez les personnes saines, le rappel répare l'humeur —
   Joormann & Gotlib).
5. **Parole → hormones** : ce qu'Ahmed dit (sa voix seulement, pas un invité ni la télé) est évalué par un lexique
   (chaleur, réussite, problème, échec, nouveauté), au plus deux événements par échange, intensité ≤ 0,6, avec pour
   sujet la rubrique où l'échange est rangé. Pas de double compte : si Hakim a déjà noté le même événement dans les
   3 minutes, rien. Ce que Hakim dit lui-même passe par ses propres appels affect_event (avec un sujet).
6. **Gemma** : deux mots au lieu d'un — l'émotion soudaine et l'humeur de fond (« alarme, un sursaut de peur (fond :
   tension) »).

Critères (sur une COPIE de la vraie mémoire, interrupteur allumé dans la copie, comparés à l'interrupteur éteint) :
- **M1 — souvenirs périmés** : le banc des souvenirs périmés ne baisse pas, en état neutre, sombre et agité.
- **M2 — qualité du rappel** : sur les 35 requêtes-vérité (queries + heldout), le rappel@6 ne baisse pas de plus de
  0,02 en état neutre, sombre et agité.
- **M3 — pas de rumination** : en état sombre, la valence moyenne d'encodage des 6 premiers souvenirs n'est pas plus
  basse qu'en état neutre de plus de 0,01 ; les 6 premiers se recouvrent à ≥ 80 %.
- **M4 — l'effet existe, borné** : en état agité, l'éveil moyen d'encodage des 6 premiers est PLUS HAUT qu'en état
  neutre ; recouvrement ≥ 80 %.
- **M5 — encodage** : le même échange, vécu en alarme plutôt qu'au calme, est encré de 0,05 à 0,15 plus fort.
- **M6 — parole** : sur les 32 messages étiquetés AVANT (eval/affect_v2_paroles.json) : précision ≥ 0,8, rappel
  ≥ 0,7, au plus 1 des 9 messages « rien » déclenche quelque chose ; le double compte est évité.
- **M7 — nuit** : en v2 les souvenirs chargés sont marqués dans le lot, en v1 rien ne change.

Prédictions : M1 à M7 tenus ; M4 de peu (le bonus est petit exprès). L'allumage reste la décision d'Ahmed.

### Résultat du cinquième passage (code 6ce3f7f ; eval/data/affect_v2_soudain-20261021-0938.json, affect_v2_memoire-20261021-0939.json)

Hormones : prédiction juste — D0-doux, D2-dur, D2-doux, D3-dur, D3-doux tiennent TOUT (S1 familier/neuf 0,47 ;
S2 1,67), choix **D2-doux** (saturation 0, P2ʺ 0,71). Mémoire : M1, M3 à M7 tenus ; **M2 raté** : le rappel@6 tombe
de 0,266 à 0,21 en état neutre. Ablation (diagnostic) : AUCUN des 120 souvenirs attendus par les requêtes-vérité n'est
estampillé (ils datent d'avant le 03/07) ; le bonus d'état (0,266 → 0,214) et la résistance à l'oubli (→ 0,253)
n'ajoutent qu'aux souvenirs estampillés : les anciens reculent. Un biais contre les données manquantes, pas un effet
de l'émotion.

## Sixième passage : formes RELATIVES (correction du biais) — figé AVANT le code et la mesure (2026-10-21)

- Bonus d'état : 0,05 × max(0, proximité(présent, encodage) − proximité(base, encodage)) — un avantage seulement quand
  l'état présent ressemble PLUS à celui de l'encodage que l'état habituel ; nul en état neutre ; nul pour un souvenir
  non estampillé (traité comme encodé à la base). Garde-fou anti-rumination inchangé.
- Résistance à l'oubli : récence + (1 − récence) × 0,3 × (charge − charge moyenne), bornée à [0, 1] — l'émotionnel
  résiste, le neutre s'efface plus vite (littéralement la demande) ; un souvenir non estampillé prend la charge
  moyenne (donnée manquante : aucun effet).
- Tout le reste et tous les critères inchangés ; réglage D2-doux.
Prédiction : M2 dans la tolérance (≥ 0,246) dans les trois états ; M1, M3, M4 (de peu), M5, M6, M7 tenus.
C'est une correction APRÈS avoir vu M2 : dite comme telle.

### Résultat du sixième passage (code 2b91737 ; eval/data/affect_v2_memoire-20261021-0943.json)

TOUS les critères tenus avec D2-doux : M1 5/9 dans les quatre états (= éteint) ; M2 rappel@6 0,266 éteint → 0,253
neutre, 0,258 sombre, 0,258 agité (tolérance 0,02) ; M3 valence d'encodage du top 6 en état sombre −0,001 par rapport
au neutre, recouvrement 0,99 ; M4 éveil d'encodage du top 6 plus haut en état agité, de très peu (0,3624 contre
0,3617 ; recouvrement 0,98 : l'effet est petit exprès) ; M5 écart d'encrage 0,15 ; M6 précision et rappel 1,0, 0/9
fausse alerte, double compte évité ; M7 tenu. Les réglages D2-doux deviennent les valeurs par défaut du module (ils
n'agissent qu'avec l'interrupteur).

Limites dites : M6 est circulaire (le lexique a été écrit en connaissant les messages étiquetés) : la vraie preuve
est le journal des événements « parole » en conditions réelles. M2 ne porte que sur des souvenirs anciens, non
estampillés (aucun des 120 attendus ne l'est) : il prouve que l'ancien n'est pas lésé, pas que l'émotionnel aide. Le
rejeu n'a que 30 événements, sans sujet. Deux corrections ont été faites après avoir vu un échec (familiarisation,
formes relatives) : la revalidation sur des journées neuves (24–25/10) reste la preuve qui compte.

## Revalidation sur journées neuves et réglage de la « surprise » — figé AVANT la mesure (2026-10-24, 00:35)

Accord d'Ahmed (« je valide tout », 24/10 vers 00:25, et via Hakim à 00:21 et 00:23) : revalider, puis corriger la
surprise si les critères le justifient ; le plafond positif seulement si les critères le justifient aussi.

**Ce qui est déjà su avant la mesure (dit pour être honnête)** : deux « surprises » du 23-24/10 ont été examinées à la
main (rpe 1,35 pour « chaleur_user » 0,218 sur « profil » à 00:00:17 ; rpe ≈ 1,29-1,30 pour « succes » 0,148 sur un sujet
mal routé à 23:39:46). La règle actuelle : marque « _surprise » pour 15 min dès que r > 0 et rpe ≥ 1,3, QUELLE QUE SOIT
la taille de r (r = valence × intensité).

**A. Revalidation (code inchangé)** : les critères déjà figés P1-P7, S1-S5 (affect_v2_soudain.py, réglage D2-doux) et
M1-M7 (affect_v2_memoire.py) rejoués sur les SEULES journées neuves : le journal des événements affectifs à partir du
22/10 00:00, jamais servi au réglage (le 6e passage date du 21/10 09:43). Prédiction : tout ce qui tenait le 21/10
tient (P1, P3-P7, S1-S5, M1-M7 ; P2'' tel quel).

**B. La surprise.** Règle figée AVANT de mesurer :
- SURPRISE_R_MIN = 0,2 : une récompense plus petite ne pose jamais de marque de surprise ;
- durée = 900 s × min(1, r / 0,5) : de 6 min (r = 0,2) à 15 min (r ≥ 0,5).
Critères :
- **Q1** : sur le rejeu des journées neuves, aucun événement d'intensité < 0,2 ne pose de marque de surprise (règle
  actuelle : au moins un, le 24/10 à 00:00:17).
- **Q2** : une vraie bonne nouvelle inattendue reste une surprise : sujet chargé de deux « probleme » 0,5, puis un
  « succes » 0,8 → l'humeur dit « surprise » pendant au moins 10 min.
- **Q3** : la part du temps « surprise » sur le rejeu des journées neuves baisse d'au moins moitié (si elle est déjà
  sous 2 %, seulement Q1 et Q2 comptent).
- **Q4** : aucun critère de A ne bascule de tenu à raté.
- **Q5** : tous les tests passent.
On garde la règle seulement si Q1, Q2, Q4 et Q5 tiennent ; sinon on revient à l'ancienne (commit séparé, réversible).

**C. Le plafond positif : pas touché cette nuit.** Le test d'une semaine des chocs (eval/chocs/predictions-3.md,
24/10 → 30/10) mesure justement le plafond (L7) sur cette fenêtre, qui commence aujourd'hui : le changer maintenant
fausserait ce test. Constat seulement (part du temps dopamine ou ocytocine ≥ 0,85 sur les journées neuves).

Prédictions de Claude Code : A tout tenu ; Q1, Q2, Q4, Q5 tenus ; Q3 probablement tenu (les petites récompenses
dominent le journal).

### Amendement du 24/10 à 00:40 — APRÈS avoir vu B sur la règle actuelle, AVANT tout code de la nouvelle règle

Mesure de la règle ACTUELLE (eval/data/revalidation-20261024-0025-b.json) : Q1 raté (un « succes » 0,192 pose une
marque, le 23/10 à 19:01:47), part du temps « surprise » 3,24 %, et **Q2 raté : 0 minute**. Une forte bonne nouvelle
(« succes » 0,8) après deux problèmes sur le même sujet n'est PAS une surprise aujourd'hui : l'écart relatif
rpe = (r − attente)/r vaut 1,19 < 1,3. Le défaut est l'écart RELATIF : il gonfle pour les toutes petites récompenses et
s'écrase pour les grandes. La règle figée plus haut (seuil + durée) ne fait qu'ajouter des restrictions : elle échouerait
Q2 par construction. Elle est donc abandonnée sans être codée.

Nouvelle règle (deuxième passage, figée ici AVANT le code ; c'est une correction après avoir vu Q2, dite comme telle) :
- l'écart ABSOLU, comme l'erreur de prédiction de récompense de la dopamine : δ = r − attente ;
- marque de surprise si r ≥ 0,2 ET attente ≤ 0 (rien de bon n'était attendu sur ce sujet) ET δ ≥ 0,4 ;
- durée = 900 s × min(1, r / 0,5).
Critères inchangés (Q1-Q5, avec Q3 contre 3,24 %, donc ≤ 1,62 %). Mêmes règles de décision. Limite dite : Q2 est un
scénario écrit par moi ; les journées neuves servent à la fois de contrôle (Q1, Q3, Q4) et de premier test. La vraie
preuve sera la semaine du 24 au 30/10.

### Résultat de la revalidation (24/10, 00:50-00:55 ; eval/data/revalidation-20261024-0050-tout.json pour l'ancienne règle, -0051-tout.json pour la nouvelle)

565 événements réels des journées neuves (22/10 00:00 → 24/10 00:50), jamais servis au réglage.

**A, code inchangé** : TOUT tient sauf **P1, raté** : la saturation (dopamine ou ocytocine ≥ 0,85) vaut 96,6 % du temps
en v1 et 68,8 % en v2. La v2 en enlève, mais pas la moitié (il fallait ≤ 48,3 %). Sur les jours du réglage (21/10), P1
tenait. Les journées neuves sont bien plus chargées en événements positifs (succès, soutiens, chaleurs du lexique et de
la balise, branchés depuis). Tenus : P2'' 0,714, P3 (71 min contre 221), P4, P5' (5 min), P6 (0,036), P7 (stress v2 0,
alarme 0), S1 à S5, M1 à M7 (M2 rappel@6 0,256 dans les quatre états). **Prédiction fausse pour P1.**

**C, constat** : sur le rejeu, la dopamine ou l'ocytocine dépassent 0,85 pendant 83 % du temps. C'est le plafond
positif : P1 le confirme. Pas touché cette nuit (test L7 de la semaine en cours) ; à décider avec Ahmed.

**B, la surprise** (nouvelle règle : écart absolu) :
- Q1 **tenu** : plus aucune marque pour un événement d'intensité < 0,2. L'ancienne règle en posait (19:01:47, « succes » 0,192).
- Q2 **tenu** : 15 min de « surprise » après une forte bonne nouvelle inattendue, contre 0 avec l'ancienne règle.
- Q3 **raté** : la part du temps « surprise » passe de 3,21 % à 4,22 % au lieu de baisser de moitié. Les 10 marques
  sont maintenant des récompenses moyennes (« succes » 0,4-0,5, « chaleur_user » 0,5), souvent sans sujet, arrivées
  quand l'attente du moment était retombée à 0 après un temps calme (le premier « parfait » du matin). **Prédiction
  fausse.**
- Q4 **tenu** : A identique avec les deux règles (seul P1 rate, dans les deux cas), M1 à M7 tenus.
- Q5 **tenu** : 1137 tests passent. Un test de priorité échoue seulement quand on lance la suite sous « nice » : le
  processus testé hérite de la priorité du lanceur. Ce n'est pas lié à la règle.

**Décision selon la règle figée** (Q1, Q2, Q4, Q5) : la nouvelle règle est GARDÉE (commit séparé, réversible). Q3 rate
et c'est dit. La condition « attente ≤ 0 » compte l'attente neutre (0) comme « rien de bon attendu ». Une piste pour un
troisième passage, à figer avant et à mesurer sur des jours encore neufs (25-26/10) : exiger une attente NÉGATIVE.
Elle ne sera pas faite sans Ahmed.
