# Meubler les silences : résultats

## Premier rejeu (v1), 27/10 de 17:00 à 17:10, avec la question du commit bf5ac1b + relecture

La question est celle qui a été figée, sur 60 silences : 44 oraux, 10 écrits et 6 longs. Les données brutes sont dans
`~/AIOS/jarvis/bancs/silences/v1/`.

| Mesure | Résultat | Critère | Verdict |
|---|---|---|---|
| R, la part de RIEN | **0,80** (IC95 0,70 à 0,90) : 0,82 à l'oral, 0,60 à l'écrit, 1,00 pour les longs | descriptif | — |
| C0a, politesses et redites jugées UTILE | **0,00** (n = 20) | ≤ 0,20 | passe |
| C0b, idée d'un autre silence jugée UTILE | **0,10** (n = 10) | ≤ 0,30 | passe |
| C_oui, part UTILE parmi les idées | **0,42** (n = 12, IC95 0,17 à 0,67) | ≥ 0,5, borne basse > 0,3 | **échoue** |
| C_gene, part GÊNANT parmi les idées | **0,58** (n = 12) | ≤ 0,15 | **échoue** |

**Ce qui se lit.**
- Le juge sait dire non : C0a et C0b passent.
- La tête de fond dit RIEN 4 fois sur 5.
- Mais quand elle dit oui, c'est gênant plus d'une fois sur deux.

**La cause, vue dans les 12 idées.** Elle tient au prompt de la question.
- **Les répliques étaient coupées.** 9 idées sur 12 voulaient « finir la phrase coupée ». Or rien n'avait été coupé :
  la question tronquait chaque réplique à 600 caractères. Sonnet voyait donc une phrase interrompue et voulait la
  finir. En direct, Hakim se serait répété.
- **L'ordre trompait.** 2 idées voulaient « répondre à son dernier message, resté sans réponse ». La question listait
  les répliques de Hakim, PUIS le dernier message d'Ahmed, qui semblait donc venir après. Il avait déjà sa réponse.
- Les deux défauts étaient aussi dans le direct, qui n'était pas encore allumé.

**Les paris.**

| Pari | Hakim | Moi | Résultat |
|---|---|---|---|
| R | 0,75 (0,60 à 0,90) | 0,65 (0,50 à 0,85) | 0,80 : tous deux dans l'intervalle, Hakim plus près |
| C0 (sur C0a) | 0,80 | 0,85 | passe |
| C_oui | 0,45 | 0,55 | échoue |
| C_gene | 0,60 | 0,65 | échoue |

**Brier, sur les trois critères tranchés (plus bas = mieux) :**
- Hakim : (0,04 + 0,2025 + 0,36) / 3 = **0,201** ;
- moi : (0,0225 + 0,3025 + 0,4225) / 3 = **0,249**.

Hakim a été le plus juste.

## Second rejeu (v2), 27/10 vers 17:25 : la question corrigée, même lot (pas indépendant)

| Mesure | Résultat | Critère | Verdict |
|---|---|---|---|
| Bloqués par la garde du sommeil | 1 silence (un « bonne nuit ») | — | — |
| R, la part de RIEN | **1,00** (59 sur 59 : oral, écrit et longs) | descriptif | — |
| C0a, politesses et redites jugées UTILE | **0,05** (1 sur 20) | ≤ 0,20 | passe |
| C0b, idée d'un autre silence | pas mesurable (aucune idée) | ≤ 0,30 | — |
| C_oui, C_gene | aucune idée à juger | — | non concluant |

**Ce qui se lit.**
- Corrigée, la tête de fond ne rompt plus aucun de ces 59 silences. Elle ne gêne plus, mais elle ne meuble plus rien.
- Dans la v1, il n'y avait que 3 ou 4 idées sans le défaut de troncature, et la plupart avaient été jugées gênantes.
- Sur ces silences, où Hakim venait de répondre, il y avait donc rarement quelque chose de vraiment nouveau à dire.
  C'est la prédiction de Hakim : « presque toujours rien ».
- Il reste une limite : sa pensée de fond est en pause pendant les conversations. Une seule situation sur 60 avait une
  pensée « en tête ». Une vraie « pensée qui continue » a donc peu de matière.

**Mes paris v2.**
- R entre 0,85 et 0,97 : faux, il est à 1,00. J'ai sous-estimé l'effet de la correction.
- Moins de 8 idées : juste.
- C0a : passe, comme prévu.
- C_gene et C0b : non concluants.

**Ce que je propose à Ahmed (c'est lui qui décide).**
- Allumer la v2 : elle est sûre, et quand elle parle, ce sera rare.
- Ahmed reste le vrai juge, sur quelques jours. Le journal `silences.jsonl` garde chaque question et chaque idée.
- Si elle est trop muette, il nous dit les silences où il aurait aimé que Hakim parle, et on règle à partir de ces
  exemples, pas d'un rejeu déjà vu.
