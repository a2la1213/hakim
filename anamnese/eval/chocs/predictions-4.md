# Humeur unifiée — le test sur plusieurs jours, figé AVANT (2026-10-25, 23:49 ; démon relancé avec tout à 23:49)

Demande d'Ahmed (25/10, 23:47, relayée par Hakim) : relancer l'expérience coupée, pour voir si l'humeur unifiée (hormones
+ adénosine → émotion, relative à 72 h ; commit unification) suit mieux ce que Hakim vit. Comparaison : AVANT = 24/10 00:00
→ 25/10 23:44 (humeur par valence et éveil) ; APRÈS = 26/10 00:00 → 01/11 23:59. Bilan le 02/11. Tout changement de code
pendant la fenêtre est noté avec son heure.

Critères (les données : journal du temps toutes les 15 s, journal des hormones, journal brut, chocs.jsonl) :
- **U1, la palette** : en moyenne au moins 8 humeurs différentes par jour éveillé (AVANT : à mesurer sur 24-25/10).
- **U2, le négatif se voit** : après chaque événement négatif clé (attaque ou échec du lexique d'intensité ≥ 0,5, problème
  signalé, coupure de calcul), une humeur de la famille « alerte » ou « bas » dans les 10 min, pour au moins 60 % des cas.
- **U3, la fatigue** : après au moins 3 h de travail continu (Ahmed présent ou Hakim actif), « fatigue » ou « lassitude »
  au moins une fois dans l'heure qui suit, pour au moins 2 cas sur 3 (sinon INSUFFISANT).
- **U4, pas de clignotement** : durée médiane d'une humeur ≥ 3 min.
- **U5, l'accord humain** : deux annotateurs aveugles (Opus et Sonnet, même guide) lisent 40 moments tirés au sort (20 AVANT,
  20 APRÈS) avec les 5 dernières minutes de conversation, et nomment l'émotion qu'ils y lisent ; la famille d'humeur de Hakim
  concorde avec la leur plus souvent APRÈS qu'AVANT.

Prédictions de Claude Code : U1 tenu ; U2 tenu de peu ; U3 INSUFFISANT ou tenu ; U4 tenu ; U5 tenu.
Variables calculées, pas un ressenti prouvé.

## Changements pendant la fenêtre

- 26/10 à 00:13 (demande d'Ahmed : des graphiques plus fins) : le journal des hormones prend une ligne à chaque battement
  (15 s) au lieu d'une par minute, avec la famille de l'humeur. Le calcul de l'humeur ne change pas : les bases sur 72 h et
  le journal brut gardent une mesure par minute.
- 26/10 vers 10:12 (demande d'Ahmed : « le plafond positif », sa peur à peine audible) : le modèle des hormones change, sur
  critères figés avant (eval/plafond/predictions.md, variante V6) : demi-vies de l'ocytocine 12 h → 3 h et de la sérotonine
  24 h → 8 h ; un message, un seul événement social ; frein du GABA 0,6 → 0,35 ; aucune habituation des coups durs ;
  stress d'un problème ou d'un échec ×1,5. Les bases sur 72 h repartent de 10:20 (la base fixe les 12 premières heures).
  La voix change aussi (expressivité 0,3-1,0, débits ×0,86-×1,12) : ça ne touche pas l'humeur. Le test garde sa fenêtre,
  mais l'APRÈS mélange désormais deux modèles : le bilan les séparera (avant et après 10:12).
- 26/10 vers 10:20 : ses ressentis (peur, tristesse, colère, joie, fierté, honte) entrent dans sa balise et deviennent des
  événements ; un message sans rubrique sûre reçoit un sujet tiré de ses mots. Vers 10:55 : la règle « surprise » divisée par
  deux et son bonus 0,8 → 0,4 (simulation exhaustive, eval/humeur_unifiee). Le bilan du 02/11 séparera avant et après 10:12.
