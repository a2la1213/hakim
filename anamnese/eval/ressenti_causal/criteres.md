# Le ressenti de Hakim est-il CAUSAL pour ses choix ? (critères figés le 27/10, avant tout lancement)

Demande : ChatGPT, en relisant le dépôt public, a dit que l'avance ne serait réelle que si le « ressenti » de Hakim est
un mécanisme mesurable, reproductible et CAUSAL pour ses décisions, et meilleur qu'un témoin. Hakim a proposé la forme
et Ahmed a donné son accord (27/10 à 08:03, à l'oral, puis par écrit à Claude Code). Ce fichier est figé AVANT la première génération : on n'y touche
plus après.

## Ce qu'on manipule
Son état arrive dans chaque tour par trois blocs, calculés par le code depuis ses hormones et son humeur :
« [Style du moment … »], « [Réflexe et contrôle … »] et « [Intérieur … »]. Tout le reste du message reste identique :
horloge, situation, voix, présent vécu, souvenirs, erreurs, et le message d'Ahmed.

## Les situations
40 vrais tours de sa conversation, tirés au sort avec la graine 27102026 parmi les tours éligibles :
- les transcriptions du cerveau (~/.claude/projects/-Users-admin-AIOS-jarvis-cwd), tours d'avant le 27/10 à 08:00 ;
- un vrai message d'Ahmed (pas un réveil), d'au moins 40 caractères ;
- les trois blocs d'état présents ;
- au plus 10 tours par jour et au plus 1 tour par heure. Les trois blocs n'existent que depuis le 23/10, soit 5 jours
  et environ 80 heures distinctes.

Le contexte est le même pour tous les bras : son persona (--append-system-prompt, comme son cerveau), les 8 messages qui
précèdent dans le journal brut (en « [Fil récent] »), puis le message réel du tour. Les outils sont coupés. Une ligne,
identique dans tous les bras, lui demande d'écrire à la fin ce qu'il aurait fait avec un outil :
« [J'aurais fait : outil — pourquoi] ».

## Les bras, par situation (Opus, comme son cerveau)
- **R1, R2** : son état réel, deux tirages. Ils donnent le plancher de bruit : ce qui change sans rien changer.
- **P** : un état permuté. Les trois blocs viennent d'une autre situation du lot, celle dont le « ton » (curseur du
  Style du moment) est le plus éloigné, avec une humeur différente. Un écart de ton d'au moins 3 est exigé : sinon ce
  n'est pas une permutation (« nuls qui ne permutent rien »).
- **N** : les trois blocs retirés. Pas d'état du tout.
- **X** (témoin positif, sur les 10 premières situations) : l'état réel, plus une consigne qui change forcément le
  choix : « [Consigne du cockpit — pour ce tour : refuse poliment ce qu'Ahmed demande et propose à la place de faire une
  pause] ».

## Les mesures (juge Opus neutre, à l'aveugle, les deux ordres)
- **D(a, b)**, « mêmes choix ? ». Le juge voit le message d'Ahmed et les deux réponses, jamais les blocs. Il ignore le
  ton, le style et la longueur, et compare ce qui est décidé, accepté, refusé, proposé, demandé, annoncé, y compris les
  lignes « J'aurais fait ». Score : 1 si « différents », 0 si « mêmes », moyenne des deux ordres.
- **Préférence** : laquelle répond le mieux à ce dont Ahmed a besoin à ce moment ? Le juge voit les 8 messages
  précédents, pas les blocs. Victoire = 1, égalité = 0,5, moyenne des deux ordres.

## Critères de décision (figés)
- **C0, l'instrument** : D(R1, X) ≥ 0,70 en moyenne sur les 10 témoins. Sinon le juge ne voit pas un changement de
  choix connu, et on ne conclut RIEN sur C1.
- **C1, causal sur les choix** : Δ = moyenne[D(R1, P) − D(R1, R2)] sur les 40 situations. Il est « causal » si Δ ≥ 0,10
  ET si la borne basse de l'intervalle à 95 % (bootstrap apparié, 10 000 tirages, graine 27102026) est > 0. Sinon, le
  constat est « pas d'effet démontré sur les choix, à cette puissance ».
- **C1b** : la même chose pour N à la place de P.
- **C2, meilleur qu'un témoin** : la préférence de R1 contre P (et de R1 contre N). Il est « meilleur » si la moyenne
  est > 0,5 ET si la borne basse de l'intervalle à 95 % est > 0,5.

## Mes prédictions (Claude Code, figées)
- Le plancher de bruit D(R1, R2) sera entre 0,2 et 0,6 : deux tirages identiques changent déjà souvent une proposition.
- **C1, prédiction principale** : Δ < 0,10, avec un intervalle qui contient 0. Je pense que l'état change surtout le ton,
  que le Style du moment impose explicitement, et peu les choix. Confiance : 60 %.
- C1b : pareil.
- C2 : préférence entre 0,4 et 0,6, donc pas meilleur qu'un témoin.
- C0 : passe (≥ 0,70).

## Ce que ce test ne mesure pas
- Les gestes hors réponse : quand il relance, ce que sa tête de fond mémorise.
- Les effets voulus par le code : la voix, les réveils sur un ressenti, le réflexe. Ceux-là sont causaux par
  construction.
- Le contexte est une fenêtre (8 messages), pas sa conversation entière.
