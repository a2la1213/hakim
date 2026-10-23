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
