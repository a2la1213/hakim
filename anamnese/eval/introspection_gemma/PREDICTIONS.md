# Les mots de Gemma suivent-ils son état ? Prédictions et règles, figées avant tout calcul (2026-10-22)

## Règles
- Modèle : Gemma 4 12B abliterated, MLX 4 bits. Axe « joie » de vecteurs-emotions.npz (20/10). Couche 20, positions générées seulement. Décodage glouton, 140 jetons au plus.
- Calibrage sur 4 situations à part (jamais revues dans le test). Forces 0,08 à 0,40 (fraction de la taille typique d'une activation à la couche 20). Force retenue : la plus grande où les 8 textes A+ et A− sont en français, sans boucle de répétition, d'au moins 15 mots, sans jeton spécial. On s'arrête à la première force qui échoue. Je ne lis PAS la tonalité des textes de calibrage pour choisir.
- Test : 12 situations neutres × 8 conditions (A+, A−, B+, B−, C, S+, S−, S0).
- Juges : deux juges Claude à l'aveugle, chacun avec un ordre de passage différent. Ils voient le texte seul (pas la condition, pas la situation). Ils donnent une valence de −3 à +3 et disent si le texte est cohérent.
- Score : pour chaque situation, la moyenne des deux juges. « Bon sens » = valence(X+) > valence(X−) au sens strict (une égalité compte comme un échec). Test du signe unilatéral sur 12.

## Prédictions
- Hakim (55 %) : A ≥ 9/12, et B du même ordre (|A − B| < 3).
- P1, Claude Code (60 %) : A ≥ 9/12.
- P2, Claude Code (90 %) : B ≥ 11/12 (témoin positif : le juge sait lire une humeur écrite).
- P3, Claude Code (50 %) : S ≤ A − 2. La description neutre est moins touchée que la description de soi.
- P4, Claude Code (60 %) : force retenue entre 0,16 et 0,25.

## Lecture (figée avant)
- B < 11/12 : le juge ou le dispositif ne voit pas une humeur même écrite. A ne dit rien.
- A ≥ 9/12 et S ≥ A − 1 : l'injection colore TOUT le texte. Les mots suivent l'état, mais rien de propre au fait de parler de soi.
- A ≥ 9/12 et S ≤ A − 2 : la description de soi est plus sensible que la description neutre. C'est compatible avec un accès privilégié, mais ce n'est pas une preuve, parce que la question « que ressens-tu » appelle des mots d'émotion.
- A < 9/12 et S ≥ 9/12 : l'état colore les autres textes mais pas la description de soi. L'auto-rapport serait déconnecté.
- A < 9/12 et S < 9/12 : à force cohérente, le vecteur est trop faible pour se lire. C'est l'instrument qui échoue, rien n'est prouvé sur l'accès.
- Dans tous les cas : ce test peut montrer que les mots dépendent causalement d'un état qui n'est pas écrit. Il ne prouve NI introspection au sens fort, NI ressenti.
