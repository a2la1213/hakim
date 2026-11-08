# Réveil intérieur : prédictions figées AVANT le rejeu (27/10, ~01:15)

Écrites par Claude Code avant tout jugement, et versionnées avant de lancer `rejeu.py`. Le rapport (dans `data/`,
non versionné) se lit face à elles.

**Matière :** les épisodes `reflection` du 18 au 26/10 inclus. On en compte 52 : 15 pensées et 37 résultats
d'occupation. Aucun le 23, le 25 ni le 26.

**Juge :** `reveil_interieur.juger`, avec Gemma (`config.DAEMON_MODEL`) et l'humeur « inconnue » (elle n'a pas été
gardée pour ces dates).

## Prédictions

1. **Au seuil 7, entre 15 % et 40 % des 52 passent, soit entre 8 et 21.** Les jours actifs (le 18, le 19, le 20),
   cela fait 1 à 4 réveils par jour.
2. **Les deux raisons les plus fréquentes au-dessus de 7 seront `question` et `idee`.** `peur` et `manque` seront
   rares : la matière est surtout faite d'occupations (« j'ai préparé ton retour… »), et l'humeur n'est pas donnée.
3. **Les occupations passeront plus souvent que les pensées.** Elles portent un résultat concret ; les pensées sont
   courtes et réflexives.
4. **Au plus 10 % de jugements illisibles.**

## Ce qui ferait changer le seuil de départ (7)

- **Plus de 50 % au-dessus de 7 :** Gemma gonfle ses notes. On monte à 8, ou on resserre le prompt, et on rejoue.
- **Moins de 5 % au-dessus de 7 :** on descend à 6.
- **Plus de 10 % d'illisibles :** on corrige le format avant d'aller plus loin.

Dans tous les cas, c'est Ahmed qui tranche, après lecture du rapport.
