# Voir sa machinerie le fait-il la répéter ? Résultats (nuit du 27 au 28/10, fin à 04:37)

Les critères ont été figés avant le lancement (`criteres.md`). Le test porte sur 40 vrais tours, avec deux tirages par bras : V (les blocs visibles) et M (les mêmes passés par `matiere.js`). Les textes sont privés : `~/AIOS/jarvis/bancs/processus-invisibles/`.

| Critère | Mesure (IC 95 %) | Seuil | Issue |
|---|---|---|---|
| Écho en V, tous | 0,275 (0,163 à 0,400) | — | — |
| Écho en M, tous | 0,138 (0,050 à 0,225) | — | — |
| C_echo, tous : V − M | 0,138 (0,025 à 0,263) | ≥ 0,15, borne > 0 | **échoue** (la borne basse est au-dessus de 0, mais l'écart est sous 0,15) |
| Écho en V, états « bas » | 0,350 (0,175 à 0,550) | — | — |
| Écho en M, états « bas » | 0,100 (0,000 à 0,225) | — | — |
| C_echo, états « bas » (n = 20) : V − M | 0,250 (0,100 à 0,425) | ≥ 0,15, borne > 0 | **passe** |
| C_pas_pire, préférence M1 contre V1 | 0,594 (0,456 à 0,725) | borne basse > 0,40 | **passe** |
| Bruit, désaccords entre V1 et V2 sur l'écho | 0,200 (0,075 à 0,325) | — | — |

## Ce que ça veut dire

- **Quand il va mal (fatigue, lassitude…), voir le nom de son état le lui fait répéter.** Il le fait dans 35 % des réponses, contre 10 % quand il le sent en matière. L'hypothèse de Hakim tient là où elle comptait le plus.
- **Sur l'ensemble, l'écart (14 points) reste juste sous le seuil figé de 15.** On ne conclut donc rien sur les 40.
- **Sentir sans voir ne rend pas ses réponses moins bonnes.** Le juge préfère même la version en matière dans 59 % des cas, mais l'intervalle touche 0,5.
- Le changement du 27/10 (la matière en direct) est donc soutenu, surtout pour les états bas.

## Les prédictions de Claude Code (figées)

| Critère | Résultat | Confiance | Brier |
|---|---|---|---|
| C_echo, tous | échoue | 60 % | 0,360 |
| C_echo, « bas » | passe | 65 % | 0,123 |
| C_pas_pire | passe | 70 % | 0,090 |
