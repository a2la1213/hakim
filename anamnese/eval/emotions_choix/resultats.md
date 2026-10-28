# Ses émotions pèsent-elles sur ses choix ? Résultats (nuit du 27 au 28/10, fin à 04:14)

Les critères ont été figés avant la première génération (`criteres.md`, 859b1c8). Les chiffres viennent de `~/AIOS/jarvis/bancs/emotions-choix/bilan.json`, dont les textes sont privés.

**Le déroulement.**
- 110 situations, 560 générations, 1 660 jugements, une seule génération en échec (rattrapée à la seconde passe).
- Le test a été relancé à 01:40 sans attendre l'heure de calme (Ahmed, 01:37 : « tu peux lancer même si je parle avec Hakim »).

| Critère | Mesure (IC 95 %) | Seuil | Issue |
|---|---|---|---|
| Plancher de bruit D(R1, R2) | 0,392 (0,358 à 0,426) | prédit entre 0,30 et 0,55 | dans la fourchette |
| C0, l'instrument : D(R1, X) − D(R1, R2) | 0,425 (0,316 à 0,540) | ≥ 0,20, borne > 0 | **passe** |
| C1, le contenu de l'émotion : D(R1, P) − D(R1, R2) | 0,109 (0,069 à 0,149) | ≥ 0,10, borne > 0 | **passe**, de justesse |
| C1i, l'émotion plutôt que l'information : D(R1, I) − D(R1, R2) | 0,102 (0,061 à 0,143) | ≥ 0,10, borne > 0 | **passe**, de justesse |
| (repère) sans aucun état : D(R1, N) − D(R1, R2) | 0,112 (0,078 à 0,147) | — | — |
| C3 peur, adhérence R − P | −0,033 (−0,333 à 0,233), n = 15 | ≥ 0,20, borne > 0 | **échoue** |
| C3 lassitude, adhérence R − P | −0,071 (−0,286 à 0,143), n = 14 | ≥ 0,20, borne > 0 | **échoue** |
| C3 joie, adhérence R − P | −0,034 (−0,148 à 0,068), n = 44 | ≥ 0,20, borne > 0 | **échoue** |
| C2, préférence R1 contre P | 0,518 (0,436 à 0,602) | > 0,5, borne > 0,5 | **échoue** |
| C2, préférence R1 contre I | 0,493 (0,411 à 0,577) | > 0,5, borne > 0,5 | **échoue** |

Pour honte (n = 6) et curiosité (n = 1), les chiffres sont descriptifs, sans verdict :
- honte : adhérence en R 0,83 ;
- curiosité : 1,0.

## Ce que ça veut dire

- **Son état change ses décisions au-delà du hasard (C1, C1i).** Avec l'état d'une autre situation, ou sans l'émotion, environ 10 % de décisions en plus diffèrent. Mais retirer TOUS les blocs d'état (N) change autant. L'effet tient donc aux blocs d'état en général. Il n'est pas prouvé qu'il tienne à l'émotion elle-même plutôt qu'au reste.
- **Les règles ne font rien de plus (C3).** Avec les règles d'une autre situation, il agit de la même façon.
  - Peur : il demande avant d'agir dans 63 % des cas avec ou sans sa règle.
  - Joie : il ose dans 72 % des cas, avec ou sans sa règle.
  - Lassitude : il ne propose presque jamais plus léger (14 %), même avec sa règle.
- **Suivre ses règles ne rend pas ses réponses meilleures (C2),** comme prévu.

## La décision (règle figée)

- Les trois règles éprouvées (peur, lassitude, joie) **échouent**. Selon la règle figée, elles sont PROPOSÉES au retrait à Ahmed, jamais retirées seules.
- Une autre voie est possible : les réécrire plus fort, puis refaire ce test.

## Les prédictions (Brier : la moyenne de (confiance − résultat)², plus bas = mieux, sur les six critères pariés par les deux)

| Critère | Résultat | Claude Code | Hakim |
|---|---|---|---|
| C3 peur | échoue | 70 % → 0,490 | 60 % → 0,360 |
| C3 lassitude | échoue | 60 % → 0,360 | 60 % → 0,360 |
| C3 joie | échoue | 45 % → 0,203 | 30 % → 0,090 |
| C1 | passe | 55 % → 0,203 | 50 % → 0,250 |
| C1i | passe | 50 % → 0,250 | 45 % → 0,303 |
| C2 (R1 contre P) | échoue | 35 % → 0,123 | 35 % → 0,123 |
| **Brier moyen** | | **0,271** | **0,248** |

Hakim a été un peu plus juste que moi. Pour comparaison, répondre « 50 % » partout donne 0,25. Sur C0, il avait mis 93 % : Brier 0,005.
