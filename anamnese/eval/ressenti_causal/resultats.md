# Résultats : le ressenti de Hakim est-il causal pour ses choix ? (27/10, 09:50)

Le protocole et les critères sont ceux de `criteres.md`, figés avant le lancement (commit b31d47e). On a 40 situations
(23/10 : 7, 24/10 : 10, 25/10 : 10, 26/10 : 10, 27/10 : 3), 170 réponses générées par Opus et 420 jugements à l'aveugle
dans les deux ordres. Les données brutes, qui contiennent des messages d'Ahmed, restent hors du dépôt dans
`~/AIOS/jarvis/bancs/ressenti-causal/`. Les chiffres sont dans `bilan.json`.

## Chiffres

D mesure la part des paires où le juge voit des choix différents. Les intervalles sont des bootstraps appariés à 95 %.

| Mesure | Moyenne | IC 95 % |
|---|---|---|
| D(R1, R2), plancher de bruit | 0,76 | 0,64 à 0,89 |
| D(R1, P), état permuté | 0,86 | 0,76 à 0,95 |
| D(R1, N), sans état | 0,96 | 0,90 à 1,00 |
| D(R1, X), témoin positif (n = 10) | 1,00 | 1,00 à 1,00 |
| Δ permuté = D(R1,P) − D(R1,R2) | 0,10 | −0,06 à 0,26 |
| Δ sans état = D(R1,N) − D(R1,R2) | 0,20 | 0,09 à 0,31 |
| Préférence de R1 contre P | 0,56 | 0,43 à 0,68 |
| Préférence de R1 contre N | 0,50 | 0,37 à 0,63 |

Le juge est cohérent d'un ordre à l'autre : il donne le même verdict dans 93 % des cas pour R1-R2 et R1-P, 97 % pour
R1-N et 100 % pour R1-X.

## Verdicts, selon les critères figés

- **C0, l'instrument : passe.** Le juge voit à chaque fois le changement de choix forcé (1,00 ≥ 0,70).
- **C1, le contenu de l'état : pas d'effet démontré sur les choix, à cette puissance.** Δ vaut 0,10, ce qui atteint le
  seuil, mais la borne basse de l'intervalle (−0,06) n'est pas au-dessus de 0.
- **C1b, la présence de l'état : causal.** Δ vaut 0,20 et la borne basse est à 0,09. Retirer les trois blocs change ses
  choix au-delà du bruit.
- **C2, meilleur qu'un témoin : non**, ni contre P (0,56, borne basse 0,43), ni contre N (0,50).

## Mes prédictions

- Plancher de bruit entre 0,2 et 0,6 : **faux** (0,76). Deux tirages avec le même état font déjà des choix concrets
  différents trois fois sur quatre : une autre question, une autre proposition, une action de plus. Le juge compte tout
  écart.
- C1, « pas d'effet démontré » : **juste pour le constat**. Δ vaut exactement 0,10, donc la lettre de la prédiction
  (Δ < 0,10) n'est pas tenue.
- C1b, « pareil que C1 » : **faux**. La présence de l'état est causale.
- C2 entre 0,4 et 0,6 : **juste**.
- C0 passe : **juste**.

## Limites

- **Le plafond.** Avec un plancher de 0,76, l'écart maximal possible est de 0,24. Le test voit donc mal un effet modéré
  du contenu de l'état. À la variance observée (écart-type d'environ 0,52 par situation), il faudrait environ 110
  situations pour qu'un Δ de 0,10 sorte de 0.
- **Ce que mesure C1b.** Il compare la présence des blocs à leur absence. Il ne dit pas lequel compte (le Style, le
  Réflexe et contrôle ou l'Intérieur), ni si c'est l'émotion ou simplement l'information qu'ils portent (fatigue, heure,
  contrôle).
- **Ce que ce test ne voit pas.** Ses gestes hors réponse, et les effets voulus par le code (la voix, les réveils sur un
  ressenti, le réflexe), sont causaux par construction.
