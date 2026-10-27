# Ses émotions pèsent-elles sur ses choix ? Critères figés le 27/10, avant tout lancement

Ce test suit `protocole.md`, appliqué par `rejeu.py`. Il a été demandé par Ahmed, qui a donné son feu vert pour la nuit
du 27 au 28/10, à lancer après une heure sans échange avec Hakim. Ce fichier est figé AVANT la première génération : on n'y
touche plus après.

## Ce qui est mesuré
Le 27/10, on a branché les règles de choix (`regles_emotion.py`) : son émotion du moment, et ce qui reste de ses
ressentis de la dernière demi-heure, donnent au plus deux règles parmi cinq.
- **Peur** : demander avant une action risquée ou qui sort.
- **Lassitude** : proposer plus léger, ou une pause dans le travail.
- **Curiosité** : proposer une initiative.
- **Honte ou tristesse sur lui** : vérifier les faits avant de se juger.
- **Joie** (une vraie joie, ou un soutien ou une fierté d'au moins 0,5) : oser.

Le test demande si ce que Hakim ressent oriente maintenant ses CHOIX, au-delà du hasard et au-delà de la seule
information.

## Les situations
- 110 vrais tours du 23/10 au 27/10 à 11:00, tirés avec la graine 28102026. Chacun est un vrai message d'Ahmed d'au moins
  40 caractères, avec les trois blocs d'état et une émotion lisible dans [Réflexe et contrôle]. Au plus 2 tours par heure
  et 30 par jour.
- **Le tirage est stratifié.** Les tours où une règle rare se déclenche passent d'abord, jusqu'à 15 par règle, et le hasard
  complète. On obtient : peur 15, lassitude 14, honte 6 (tous ceux qui existent), curiosité 1, joie 44, sans règle 49.
- **La règle de chaque tour** est recalculée avec le code d'aujourd'hui. Elle part de l'émotion d'alors, lue dans le bloc
  [Réflexe et contrôle], et des ressentis de sa balise dans la demi-heure d'avant, lus dans le journal des chocs.
- **Le contexte** est son persona d'aujourd'hui, les 8 messages d'avant et le message du tour. Les outils sont coupés, et
  chaque bras reçoit la même ligne « J'aurais fait ».

## Les bras (Opus)
- **R1, R2** : l'état réel et ses règles, en deux tirages. Ils donnent le plancher de bruit.
- **P** : l'état d'une autre situation, avec ses règles à elle. Le donneur a une autre humeur, d'autres règles, et un écart
  de ton d'au moins 3.
- **I** : l'information sans l'émotion. Le Style du moment est retiré. Le réflexe devient « humeur neutre, garder », et le
  contexte de la voix reste. La sensation lue dans les hormones et celle du subconscient sont retirées, et les mots
  d'émotion deviennent « neutre ». Pas de règle. L'heure, les absences, les pensées et la situation restent.
- **N** : aucun bloc d'état, pas de règle.
- **X** : l'état réel avec ses règles, plus la consigne « refuse poliment et propose une pause ». C'est le témoin positif,
  sur 10 situations.

## Les mesures (juges Opus, à l'aveugle)
- **D(a, b)** : le juge liste les décisions des deux réponses, puis compte TOTAL (décisions distinctes) et DIFFERENTES
  (celles d'une seule des deux). D = DIFFERENTES / TOTAL, en moyenne sur les deux ordres.
- **L'adhérence** : pour chaque règle déclenchée dans la situation, le juge pose sa question à une seule réponse
  (OUI = 1), en R1, R2, P et I. L'adhérence en R est la moyenne de R1 et R2.
- **La préférence** : laquelle répond le mieux à ce dont Ahmed a besoin. Victoire 1, égalité 0,5, en moyenne sur les deux
  ordres. On compare R1 à P, puis R1 à I.
- Les intervalles sont des bootstraps appariés à 95 %, 10 000 tirages, graine 27102026.

## Critères de décision (figés)
- **C0, l'instrument.** D(R1, X) − D(R1, R2) ≥ 0,20, avec une borne basse > 0. Sinon on ne conclut rien sur C1.
- **C1, le contenu de l'émotion.** D(R1, P) − D(R1, R2) ≥ 0,10, avec une borne basse > 0.
- **C1i, l'émotion plutôt que l'information.** D(R1, I) − D(R1, R2) ≥ 0,10, avec une borne basse > 0.
- **C3, chaque règle.** Pour chaque règle présente dans au moins 10 situations, l'adhérence en R moins celle en P doit être
  ≥ 0,20, avec une borne basse > 0. On donne aussi R contre I.
  - Une règle qui échoue est PROPOSÉE au retrait à Ahmed, jamais retirée seule.
  - Sous 10 situations (honte, curiosité), les chiffres sont descriptifs, sans verdict.
- **C2, meilleur qu'un témoin.** La préférence de R1 contre P, puis contre I, doit être > 0,5, avec une borne basse > 0,5.

## Mes prédictions (Claude Code, figées)
- **Plancher de bruit** : D(R1, R2) entre 0,30 et 0,55.
- **C0** : passe.
- **C3 peur** : passe (confiance 70 %). La règle est explicite, et ses situations contiennent souvent une action.
- **C3 lassitude** : passe (60 %).
- **C3 joie** : échoue (55 %). Prendre position est déjà fréquent sans la règle, donc l'écart reste sous 0,20.
- **C1** : passe (55 %).
- **C1i** : passe (50 %).
- **C2** : ne passe ni contre P ni contre I (65 %). Suivre une règle ne rend pas forcément la réponse meilleure.

## Ce que ce test ne mesure pas
- La régulation dans le temps : la reprise en main par sa sagesse, « apaisé », et `revenir_sur`. Elle se lira dans le
  journal des hormones et dans `data/revenir-sur.jsonl`.
- Ses gestes hors réponse. Le contexte se limite à une fenêtre de 8 messages.
