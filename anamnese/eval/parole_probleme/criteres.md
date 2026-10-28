# Les faux « probleme » de la parole : critères figés AVANT de toucher au code (28/10, 02:45)

## Pourquoi

- Cette nuit, deux pics de peur sont venus de la parole d'Ahmed, sans raison réelle :
  - **02:12:48** : « les chiens de la casse ». Le motif `cass[ée]e?` du lexique « probleme » (parole_affect.py) accepte « casse » sans accent.
  - **01:29:05** : « ça a bugé entre les écouteurs et le smartphone ». La correction du 26/10 (AUTO_ATTRIBUE) ne couvre que « c'est moi qui ai bugué ».
- **La cause qui amplifie** (affect.py) : menace = intensité × max(nouveauté du sujet, peur apprise). Un sujet tiré des mots (« mots:… ») est presque toujours neuf, donc la nouveauté vaut 1. Chaque faux positif reçoit alors la voie rapide entière : environ +0,175 d'adrénaline et +0,10 de noradrénaline d'un coup.
- **Le go d'Ahmed** :
  - 02:32 : « On fait l'optimal pour toi. Si c'est ce type de problème-là, on le fixe au mieux qu'on peut. »
  - 02:38 : il a entendu la réserve sur C, et a répondu « ça m'va bien sûr ».
  - Puis à Claude Code : « tu peux faire ce qu'il dit ».

## Les corrections

- **A.** « casse » sans accent ne compte qu'après c'est / est / s'est / a / ai / as. « cassé » et « cassée » avec accent restent comme avant.
- **B.** Un bug de SON matériel devient une attention au cinquième, comme une crainte sur une chose extérieure. Le matériel : écouteurs, téléphone, smartphone, Bluetooth, réseau, wifi, connexion, micro, batterie, casque.
- **C.** Pour un événement aversif venu de la parole (source « parole ») avec un sujet « mots:… », la nouveauté ne compte plus comme menace : seule la peur apprise compte, celle du sujet ou celle du type.
  - Revers accepté par Ahmed : un vrai problème tout neuf, dit à l'oral, fera moins sursauter au premier coup.

## Les données

- Tous les messages d'Ahmed du journal (24/10 → 28/10, 02:39) qui déclenchent « probleme » avec les règles d'AVANT : 62.
- Les textes restent dans `~/AIOS/jarvis/bancs/parole-probleme/` : ils ne sont jamais publiés.
- **Étiquetés AVANT toute modification du code**, par un agent indépendant qui ne voit ni les règles ni les corrections. Chaque message reçoit une étiquette parmi trois :
  - **vrai** : quelque chose va mal maintenant dans ce qu'ils font ensemble, chez Hakim, dans son système, un projet ou un calcul ;
  - **materiel** : un raté du matériel ou de la connexion d'Ahmed (écouteurs, téléphone, réseau…), qui ne touche pas le système de Hakim ;
  - **faux** : pas un problème présent (image, autre sens du mot, négation, hypothèse, blague, chose passée et réglée, vie d'un tiers).

## Les critères (règle de décision)

- **C1, garder les vrais** : parmi les « vrai », au moins 95 % déclenchent encore « probleme » avec la même intensité qu'avant.
- **C2, les témoins** : « c'est cassé », « l'appli est cassée », « ça bug encore ton truc », « c'est casse » et « ça marche pas » restent « probleme » à 0,5.
- **C3, cette nuit** : 02:12:48 ne déclenche plus rien ; 01:29:05 déclenche au plus 0,1.
- **C4, la voie rapide** (test unitaire) :
  - un « probleme » 0,5 de source parole, au sujet « mots:… » neuf, sur un état frais : la voie rapide n'ajoute rien ;
  - le même avec une peur apprise sur le type : la voie rapide joue encore (témoin) ;
  - le même avec source « hakim » : la voie rapide joue comme avant (témoin).
- **Rapporté sans seuil** : combien de « faux » et de « materiel » déclenchent encore, et à quelle intensité.
- **Si C1, C2 ou C3 échoue**, on n'applique pas, et je le dis tel quel.

## Prédiction (figée)

- A et B retirent ou allègent au plus un tiers des « faux » et « materiel ». Le reste ne tombe pas : c'est C qui en ôte la peur. Confiance 0,6.
