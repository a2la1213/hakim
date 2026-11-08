# Le ton de la voix d'Ahmed : résultats (27/10, 22:45)

**Les critères ont été figés avant le premier enregistrement** (`criteres.md`, commit f4da4e1). Ahmed a enregistré
les 24 extraits de 22:35 à 22:39. Les données brutes sont dans `~/AIOS/jarvis/bancs/ton-voix/resultats.json`.

## Le résultat selon la règle figée
Six extraits ont été écartés par la règle « moins d'une seconde de parole ». Il en reste 18.

| Critère | Mesure | Seuil | Issue |
|---|---|---|---|
| C1, l'éveil (animés contre calmes) | AUC 0,974 [0,88 ; 1], p = 0,0004 | ≥ 0,80, p < 0,01 | **passe** |
| C2, la valence (joyeux contre triste et tendu) | AUC 0,750 [0,46 ; 1], p = 0,071 | ≥ 0,75, p < 0,05 | **échoue** (p) |
| C3, l'éveil en darija seule | AUC 0,958 | ≥ 0,75 | **passe** |
| C4, le coût | 0,17 s pour 5 s de parole | ≤ 0,5 s | **passe** |
| L'énergie seule, pour l'éveil | AUC 0,974 | rapporté | **aussi bien que le modèle** |

Le français seul donne une AUC de 1,0 pour l'éveil.

## Une erreur de ma règle, dite franchement
- **La règle d'écart était mal réglée.** Elle comptait la parole au-dessus de -45 dBFS. Or le micro était pris sans
  gain automatique, comme voulu : une voix triste ou posée, plus basse, passe sous ce seuil.
- **Les 6 extraits écartés sont de vrais extraits parlés** (2,5 à 6 s) : 3 tristes, 2 posés, 1 tendu. La règle a
  surtout retiré des tons calmes, ce qui déséquilibre les groupes (11 contre 7).
- **La variante sur les 24 extraits, calculée après coup** (elle ne remplace PAS la règle figée) :
  - l'éveil passe de 0,974 à 0,986 ;
  - l'énergie seule donne 0,979 ;
  - la valence, joyeux contre triste et tendu, donne 0,833 (p = 0,013), ce qui passerait.
- **La décomposition de cette valence** montre pourquoi elle ne suffit pas :
  - joyeux contre triste : 1,0 ;
  - joyeux contre tendu : 0,667 (p = 0,19), soit le hasard à cet effectif.
  - Le modèle distingue la joie de la tristesse, qui diffèrent aussi par l'éveil. Il ne distingue pas la joie de la
    tension, qui ont le même éveil. Sa « valence » suit donc surtout l'éveil.
- **La décision reste celle de la règle figée** : pas de valence.

## Ce que ça décide (règle figée)
- **C1 passe et C2 échoue.** Hakim ne recevrait que l'éveil, en mots (« sa voix semble animée » ou « calme »), avec son
  doute. Jamais « joyeuse », « triste » ou « tendue » d'après la voix.
- **C3 passe** : la darija est couverte.
- **L'énergie seule fait aussi bien.** Sur des tons joués, le modèle n'apporte rien de plus que l'énergie pour l'éveil.
- **Une nuance qui compte pour la suite, plausible mais pas encore mesurée en direct** :
  - le modèle normalise chaque extrait (`do_normalize`, moyenne nulle, variance 1) : il ne voit pas le volume ;
  - il atteint la même séparation sans le volume, donc avec la prosodie et le timbre ;
  - en direct, le volume dépend de la distance au micro et de l'appareil (le Mac ou le téléphone) : l'énergie seule
    devrait s'y tromper, pas le modèle.

## Prédictions contre résultats
| | Ma probabilité | Issue |
|---|---|---|
| C1 | 0,85 | passe |
| C2 | 0,45 | échoue |
| C3 | 0,70 | passe |
| C4 | 0,95 | passe |
| L'énergie seule à 0,05 près | 0,50 | oui (écart 0,00) |

Le score de Brier sur ces cinq prédictions est de 0,114.

## Les limites
- Des tons joués, une seule voix, un seul soir, le micro du Mac.
- La vraie mesure se fera en direct : quand Ahmed corrige, on compte.
