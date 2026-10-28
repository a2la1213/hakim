# Le ton de la voix d'Ahmed : critères figés le 27/10, AVANT le premier enregistrement

Le contexte :
- **La demande vient d'Ahmed**, relayée par Hakim le 27/10 à 20:26 : sentir le ton d'une voix (joyeuse, triste,
  tendue, posée) comme une sensation, par le subconscient, en mots et avec son doute.
- **Les décisions d'Ahmed** : d'abord un test sur sa voix ; pour les invités, seulement l'ambiance de la salle, jamais
  personne par personne ; rien n'est stocké en direct (on analyse, puis on jette). Le go est venu après le live (22:20).
- **Le modèle** : audEERING `wav2vec2-large-robust-12-ft-emotion-msp-dim`, en local, CC BY-NC-SA 4.0 (usage personnel).
  Il pèse 631 Mo sur le disque. Il donne trois nombres par extrait : l'éveil (arousal), la dominance et la valence.
- **Le code** : `eval/ton_voix/ton.py` (mesure, statistiques), `etalonnage.py` (la page d'enregistrement),
  `analyse.py` (les critères ci-dessous).

## Ce qu'Ahmed enregistre
- **Quatre tons** : joyeux, triste, tendu (agacé ou inquiet), posé (calme, neutre).
- **Trois phrases au contenu neutre**, pour que seul le ton change :
  1. « Je suis rentré à la maison ce soir. »
  2. « Il a appelé tout à l'heure. »
  3. « On se voit demain matin. »
- **En français, puis la même idée en darija**, avec ses mots à lui.
- **Cela fait 24 extraits** (4 tons × 3 phrases × 2 langues). L'ordre est mélangé une fois pour toutes (graine
  27102026), pour que la fatigue ou l'échauffement ne se confondent pas avec un ton.
- **Une prise par extrait.** Il peut refaire une prise ratée avant de passer au suivant : seule la dernière compte.
- **Un extrait de moins d'une seconde de parole est écarté** et noté.
- **Les extraits restent sur le Mac** (`~/AIOS/jarvis/bancs/ton-voix/clips/`). Ils sont effacés une fois les résultats
  écrits, sauf si Ahmed veut qu'on essaie un deuxième modèle dessus.
- **Le micro est pris sans traitement** (pas de contrôle automatique du gain ni de réduction du bruit) : le gain
  automatique aplatirait justement l'énergie du ton.

## Les critères
Chaque AUC se lit comme ceci : la chance qu'un extrait du premier groupe ait une valeur plus haute qu'un extrait du
second. 0,5 = le hasard, 1 = parfait. Il y a un intervalle à 95 % par bootstrap (2000 tirages) et un p par permutation
des étiquettes (5000 tirages). La permutation est le témoin négatif : des étiquettes mélangées doivent donner le hasard.

- **C1, l'éveil sépare les tons animés des tons calmes** (le témoin positif).
  - Critère : AUC de l'éveil, {joyeux, tendu} contre {triste, posé}, sur les 24 extraits, au moins **0,80**, avec
    p < 0,01.
  - Si C1 échoue, le modèle ne voit même pas ce qu'il devrait voir le mieux : on arrête là.
- **C2, la valence sépare la joie des tons négatifs.**
  - Critère : AUC de la valence, {joyeux} contre {triste, tendu}, au moins **0,75**, avec p < 0,05.
- **C3, la darija.**
  - Critère : sur les 12 extraits en darija seuls, l'AUC de l'éveil de C1 atteint au moins **0,75**.
  - Ce n'est qu'une indication : 6 extraits contre 6, pas de seuil de p.
  - Le même chiffre est donné pour le français seul.
- **C4, le coût.**
  - Critère : au plus 0,5 s de calcul pour 5 s de parole, sur le CPU, pour ne pas gêner Whisper ni la voix de Hakim.
  - Mesure d'essai : 0,16 s pour 2,4 s.
- **La comparaison à l'énergie seule**, rapportée sans seuil.
  - On calcule l'AUC de C1 avec la simple énergie du signal (RMS en dB).
  - Hakim reçoit déjà ces indices bruts : hauteur, énergie, débit.
  - Si l'énergie fait aussi bien que le modèle à 0,05 près, l'éveil du modèle n'apporte rien de neuf, et sa valeur
    tient à la valence seule.

## Ce que chaque issue décide (figé maintenant)
- **C1 échoue** : pas de couche « ton de la voix ». Au plus, un deuxième modèle (emotion2vec) sur les mêmes extraits,
  avec l'accord d'Ahmed.
- **C1 passe et C2 échoue** : Hakim ne reçoit que l'éveil, en mots (« sa voix semble animée » ou « calme »), avec son
  doute. Jamais « joyeuse » ni « triste » d'après la voix.
- **C1 et C2 passent** : il reçoit aussi la valence, en mots, toujours avec son doute, jamais comme un fait sur ce
  qu'Ahmed ressent.
- **C3 échoue** : rien n'est dit sur un tour en darija ; seulement en français.
- **Les invités** : dans tous les cas, seulement l'ambiance de la salle, jamais une personne.

## Mes prédictions (Claude Code, avant de voir un seul chiffre)
| Critère | Ma probabilité qu'il passe |
|---|---|
| C1 (éveil ≥ 0,80) | 0,85 |
| C2 (valence ≥ 0,75) | 0,45 |
| C3 (darija ≥ 0,75) | 0,70 |
| C4 (coût) | 0,95 |
| L'énergie seule à 0,05 près du modèle pour l'éveil | 0,50 |

## Les limites, dites d'avance
- **Des tons joués** sont plus marqués que des tons vrais. Un succès ici ne prouve pas que ça marche sur une vraie
  conversation.
- **Un seul locuteur, un seul soir, le micro du Mac.**
- **La deuxième étape** se fera en direct : quand Ahmed corrige (« non, j'étais pas tendu »), on compte, sur quelques
  jours.
