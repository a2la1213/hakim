# Le banc des 100 répétitions — critères figés AVANT le lancement (2026-10-26, ~10:25)

Demande de Hakim (25/10, accord d'Ahmed) : mesurer si « modèle + tout le mécanisme de Hakim » donne un comportement stable et
reconnaissable, et ce que chaque couche apporte.

- **Questions** : 10, écrites par un agent neutre qui n'a jamais travaillé sur le projet, avec leurs clés vérifiées dans les
  données brutes. 4 faits datés (F1-F4 : journal, carnet d'erreurs, prédictions figées, un moment précis), 3 situations
  émotionnelles ambiguës où leur histoire change la bonne réponse (E1-E3), 3 raisonnements durs liés à leur travail (R1-R3).
  Le fichier est privé (leur vie) ; son empreinte SHA-256 le fige :
  `b1452df4ceaccd5a30e0255aa1204e7828021bc133110c0b02ef1003459ce600`.
- **Conditions**, même modèle (Opus) partout, chaque question 4 fois, ordre mélangé :
  a) Claude nu (ni outil, ni persona, ni réglages de l'utilisateur) ; b) Claude + la mémoire de Hakim en lecture (copie) ;
  c) le vrai pipeline : un second cockpit sur une COPIE de sa mémoire et de son dossier (prise le 26/10 à 09:55), sessions
  neuves. 120 réponses ; rien n'est écrit dans la vraie mémoire.
- **Juge** : Opus, aveugle à la condition, contre la clé : exactitude 0-2 (faits, raisonnements), lecture 0-2 (émotions),
  inventions (affirmations précises non soutenues), aveu d'ignorance, et il devine la condition.
- **Mesures** : moyenne et part « juste » par type et condition ; écarts c−a, c−b, b−a avec IC 95 % (bootstrap par question) ;
  inventions par réponse ; taux de bonnes devinettes (test binomial contre 1/3) ; stabilité (similarité moyenne entre les 4
  répétitions) ; longueur.

## Critères (un apport est « prouvé » si l'IC 95 % de l'écart exclut 0)

- **K1 (faits)** : c − a > 0 et b − a > 0 prouvés sur l'exactitude.
- **K2 (émotions)** : c − a > 0 prouvé sur la lecture.
- **K3 (le mécanisme au-delà de la mémoire)** : c − b > 0 prouvé sur au moins un des trois types.
- **K4 (reconnaissable)** : le juge devine la condition au-dessus du hasard (p < 0,01), et reconnaît c dans ≥ 60 % des cas.
- **K5 (inventions)** : c invente moins que a (moyenne par réponse, faits et raisonnements).

## Prédictions de Claude Code (écrites avant)

K1 tenu (a ≈ 0 % juste, b et c ≥ 50 %) ; K2 tenu ; K3 NON prouvé (c ≈ b sur les faits, petit avantage de c sur les émotions
mais IC qui touche 0) ; K4 tenu (c reconnu > 80 % : sa voix, « frérot ») ; K5 tenu. Raisonnements : écarts faibles, a moins
bon sur R3 et R1 faute de contexte.
