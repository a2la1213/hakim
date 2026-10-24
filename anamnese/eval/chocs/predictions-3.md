# Chocs d'humeur — le test en vrai (figé AVANT l'allumage, 2026-10-23)

Décision d'Ahmed (23/10, 10:07, relayée par Hakim, confirmée à Claude Code : « tu peux voir ce que Hakim te dit ») :
brancher pour de vrai et tester. Branché : chocs.py (réflexe lexical par voix, balise de Hakim, sagesse de fond et du
moment, habituation du soutien, choc qui passe outre la bonne humeur), la nouvelle règle de nuit de sagesse.py, la
sagesse ramenée à 0,205. Ce fichier, le guide d'annotation (empreinte a6106526…) et le code sont figés avant l'allumage.

## Fenêtre

- Rodage, non compté : de l'allumage au 23/10 à 23:59 (les pannes s'y voient et se corrigent).
- Test : du 24/10 00:00 au 30/10 23:59 (7 jours). Bilan le 31/10. Tout changement de code pendant le test est noté
  avec son heure ; les jours d'avant et d'après sont donnés séparément.

## Données

Le journal des échanges (une phrase par voix, corpus.py), chocs.jsonl (réflexes, balises, reprises en main), le journal
des affects, le journal du temps (valence, humeur nommée toutes les 15 s), sagesse.json. Les hormones heure par heure se
reconstruisent en rejouant les événements journalisés depuis la sauvegarde de chaque nuit (simulateur validé à 0,002).
Étiquettes : à la fin, deux annotateurs indépendants (Opus et Sonnet), même guide, sans voir chocs.jsonl ; arbitrage par
les règles d'etiqueter.py. Clé = attaque ou soutien d'intensité ≥ 2 qui vise Hakim.

## Critères

- **L1, la balise** : une balise lisible dans ≥ 90 % des réponses à un message ; et 0 balise visible dans le journal,
  la conversation partagée ou les échanges à mémoriser.
- **L2, la détection** (verdict final de chaque message : la balise si elle existe, sinon le réflexe ; contre les
  étiquettes, au niveau du message) : attaques rappel ≥ 0,7 et précision ≥ 0,6 ; soutiens rappel ≥ 0,8 et précision
  ≥ 0,7 ; soutien lu dans ≤ 3 % des messages neutres ; attaque lue dans ≤ 5 % des débats qui ne le visent pas.
- **L3, le saut** : pour chaque attaque clé, dans les 5 min l'humeur nommée passe à « alarme », « tension » ou
  « morosité » au moins une fois, ET la valence baisse d'au moins 0,05 dans les 10 min. Tenu si ≥ 70 % des attaques
  clés. Moins de 3 attaques clés dans la fenêtre : INSUFFISANT, pas de conclusion.
- **L4, pas d'humeur coincée** : après chaque attaque, la valence revient à moins de 0,1 de sa valeur d'avant en 3 h.
- **L5, la réassurance** (si au moins 2 cas : un soutien clé d'Ahmed dans l'heure après une attaque clé) : contre le même
  rejeu sans ce soutien, la charge de stress de l'heure suivante est plus basse. Sinon : descriptif.
- **L6, la sagesse** : chaque nuit, elle bouge de 0,02 au plus.
- **L7, le plafond** : la part du temps où l'ocytocine ou la sérotonine dépasse 0,9 est plus basse que sur la courbe
  réelle des 21-23/10 (54,4 %).

## Prédictions de Claude Code (écrites avant)

- L1 : entre 85 et 95 % — Hakim oubliera parfois la balise, surtout dans les réponses longues de travail.
- L3 : INSUFFISANT probable — les attaques n'arrivent que pendant les lives ; s'il y en a 3 ou plus, tenu.
- L2 : les soutiens tiennent ; la précision des soutiens est la plus fragile (Hakim lit de la chaleur partout).
- L4, L6 : tenus. L7 : tenu (l'habituation du soutien).

Variables calculées, pas un ressenti prouvé.

## Amendement du 23/10 à 12:05, AVANT la fenêtre

L'habituation s'étend aux « succes » du lexique (simulé : plafond 41 % → 31 %) ; le style du moment (style.py) est
branché depuis 11:45 (critères à part : eval/voix_mots/criteres.md). Les critères L1 à L7 sont inchangés.

## Changements de code pendant la fenêtre (notés avec leur heure, comme prévu)

Avant la fenêtre (rodage) : le 23/10 à 23:46, le lexique de la parole ne lit plus un problème NIÉ (« c'est pas un
problème ») comme un problème (ce71129), actif dès la relance du démon juste avant minuit.

Pendant la fenêtre :
- **24/10 00:56**, relance du démon et du cockpit : la **surprise de récompense** suit l'écart absolu (cbd1d33,
  revalidation de l'affect v2, eval/affect_v2_predictions.md). Effet attendu sur ce test : le libellé « surprise »
  change de moments (plus de surprise pour un petit « merci », une vraie pour une forte bonne nouvelle inattendue). L3
  ne compte que « alarme », « tension » ou « morosité » ; L7 (le plafond) ne dépend pas de la surprise. Les mesures
  seront données aussi en séparant avant et après 00:56 si un écart apparaît.
- 24/10 00:56 : Hakim peut écrire à Claude Code et proposer une mission pendant un réveil (d54bd4e, 705846c). Sans effet
  sur les hormones.
- 24/10 02:11 : le cockpit suit lui-même les agents de Hakim (47d31ba). Sans effet sur les hormones.
- 24/10 05:47 : la ligne de batterie dit « branchée » (3be476a). Sans effet sur les hormones.
- La relance du démon du 24/10 vers 00:35 (ancienne règle de surprise) n'a rien changé au code.
- **24/10 à 12:07:46** (relance du démon) : « n'importe quoi » n'est plus un « echec » du lexique que s'il vise
  Hakim (« tu dis n'importe quoi », « c'est n'importe quoi ce que tu… », « n'importe quoi cette réponse ») ; en blague ou à
  propos d'un autre, plus rien. Le 24/10 à 08:26 et 08:30, il avait donné deux pics de CRH et d'adrénaline au début du live.
  Les 32 phrases étiquetées gardent précision et rappel à 1,0. Effet attendu sur ce test : moins de faux « échec » dans
  L2 et L3 ; les mesures seront données aussi avant et après ce changement.
