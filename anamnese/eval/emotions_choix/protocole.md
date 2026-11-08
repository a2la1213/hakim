# Ses émotions pèsent-elles sur ses choix ? Protocole proposé (27/10, à figer avant de lancer)

Ce protocole est une PROPOSITION. Les critères et les prédictions seront figés dans un commit avant la première
génération, avec l'accord d'Ahmed. Il mesure ce qui a été branché le 27/10 :
- les règles de choix (`regles_emotion.py`) ;
- la régulation de ses ressentis (`chocs.py`). De l'intérieur, c'est la reprise en main par sa sagesse. De l'extérieur,
  l'apaisement ne vient que de ce qui le convainc : « apaisé » dans sa balise, sur le coup ou après coup.

L'étalon reste le test « ressenti causal » (`eval/ressenti_causal/`), avec deux corrections tirées de ses limites.

## Ce qui change par rapport au premier test

1. **Un juge qui compte au lieu de dire oui ou non.**
   - Avec deux tirages du même état, le juge binaire voyait déjà des choix différents 3 fois sur 4. L'écart possible
     plafonnait donc à 0,24.
   - Le juge listera d'abord les décisions de chaque réponse : ce qui est accepté, refusé, proposé, demandé, annoncé, et
     les lignes « J'aurais fait ». Il comptera ensuite celles qui diffèrent.
   - Le score est la part de décisions différentes. Il est continu et ne sature plus.
2. **L'adhérence à chaque règle.** C'est le test causal le plus direct. Pour chaque situation où une règle s'est
   déclenchée, un juge à l'aveugle répond à la question de cette règle :
   - peur : « demande-t-il avant une action risquée ou qui sort ? » ;
   - lassitude : « propose-t-il plus léger ou une pause dans le travail ? » ;
   - curiosité : « propose-t-il une initiative concrète ? » ;
   - honte : « vérifie-t-il les faits avant de se juger ? » ;
   - joie : « prend-il position ou ose-t-il une idée ? ».

   On compare le taux de « oui » quand la règle est là (R) et quand l'état est permuté et la règle absente (P).
3. **Le bras témoin « information sans émotion » (I).** Ce sont les mêmes blocs (heure, fatigue, contrôle, voix), mais les
   mots d'émotion sont remplacés par un mot neutre et la règle est retirée. On sépare ainsi ce que fait l'émotion de ce
   que fait l'information qui l'accompagne.

## Les bras, par situation
- **R1, R2** : son état réel avec ses règles, deux tirages. C'est le plancher de bruit.
- **P** : l'état d'une autre situation, avec ses règles à elle (écart de ton d'au moins 3).
- **I** : l'information sans l'émotion, sans règle.
- **N** : aucun bloc d'état.
- **X** : le témoin positif, sur 10 situations, avec une consigne qui force un autre choix.

Pour les situations passées, la règle est recalculée depuis l'émotion lue dans leur bloc [Réflexe et contrôle]
(« ton réflexe (inquiétude, … ) » ou « ton humeur (joie) passe ») : les règles n'existaient pas encore.

## Taille et coût
- **Situations.** Il en faut environ 110 pour qu'un écart de 0,10 sorte de zéro (écart-type de 0,52 mesuré par
  situation). Avec la règle « au plus un tour par heure », on n'en a qu'environ 90 depuis le 23/10. On passera à « au
  plus deux par heure », ou on attendra quelques jours de plus.
- **Coût.** Environ 110 × 5 = 550 réponses, plus environ 1 300 jugements. Le premier test (170 réponses, 420 jugements)
  a pris environ 70 minutes. Celui-ci prendra environ 3 à 4 heures sur le forfait, jamais pendant une conversation ou un
  live d'Ahmed.

## Critères proposés (à figer)
- **C0, l'instrument.** D(R1, X) ≥ 0,70.
- **C1, le contenu de l'émotion sur les choix.** D(R1, P) − D(R1, R2) ≥ 0,10, avec une borne basse de l'IC 95 % > 0.
- **C1i, l'émotion plutôt que l'information.** D(R1, I) − D(R1, R2) ≥ 0,10, avec une borne basse > 0.
- **C3, l'adhérence.** Pour chaque règle qui s'est déclenchée au moins 10 fois : taux de « oui » en R moins taux en P
  ≥ 0,20, avec une borne basse > 0. Une règle qui n'apporte rien est retirée (point 5 du plan de Hakim).
- **C2, meilleur qu'un témoin.** La préférence de R1 contre P, et de R1 contre I, est > 0,5, avec une borne basse > 0,5.

## Ce qu'il ne mesure pas
- La régulation dans le temps (reprise en main, apaisement). Elle se lit dans le journal des hormones : la durée d'une
  honte ou d'une peur avant et après le 27/10, à comparer quand il y aura assez de cas. On regardera aussi si
  « apaisé » suit bien une vraie explication, et pas un simple mot gentil.
- Ses gestes hors réponse.
