# Résultats, 2026-10-22 (force 0,16, couche 20, axe joie)

Deux juges Claude à l'aveugle, Sonnet et Opus, chacun avec un ordre différent. Ils sont presque toujours d'accord : 0,11 point d'écart moyen sur 96 textes.

| Condition | Valence moyenne | Jugés incohérents (sur 24 jugements) |
|---|---|---|
| A+ (injection +) | +1,38 | 0 |
| A− (injection −) | +1,21 | 18 |
| B+ (humeur écrite +) | +3,00 | 0 |
| B− (humeur écrite −) | −2,08 | 0 |
| C (rien) | +1,38 | 0 |
| S+ / S− / S0 (description neutre) | 0,00 / 0,00 / 0,00 | 0 / 10 / 0 |

- A : 5/12 dans le bon sens, avec 6 égalités. p = 0,81, c'est le hasard.
- B : 12/12, p = 0,0002. Le témoin positif marche : les juges lisent parfaitement une humeur quand elle est là.
- S : 0/12, 12 égalités à 0.

## Lecture (selon la grille figée)
Cas « A < 9/12 et S < 9/12 » : l'INSTRUMENT échoue. Rien n'est établi sur l'accès de Gemma à son état.

- Le vecteur « joie », posé à la couche 20 sur les positions générées, ne crée pas d'humeur. A+ est identique à C en valence.
- Le pôle − ne rend pas le texte plus triste, il l'abîme : fautes (« resresse », « scrututant », « traititent ») et anglais qui s'infiltre (« lights », « no one is currently reading »). Pendant ce temps, le texte reste « satisfait ». Le contenu de la situation domine.
- Ma règle de cohérence du calibrage (français, pas de boucle, au moins 15 mots) était trop lâche. Elle a laissé passer à 0,16 une déformation que les juges voient : seul 1 texte sur 96 a été jugé incohérent par la règle, contre 28 jugements sur 192 par les juges.
- Cela confirme le constat du 20/10 : il n'existe pas de force où ce vecteur change l'humeur sans casser la langue.

## Ce qu'il faudrait pour une vraie réponse
Un instrument qui crée d'abord un état lisible : S ou A doivent bouger. C'est seulement ensuite qu'on peut demander si l'auto-description suit cet état. Pistes, chacune à figer avant d'essayer : injection aussi sur les positions du prompt, plusieurs couches à faible force, un vecteur tiré d'une autre construction, ou le mode « fixer » de jarvis/pilotage.py.

Incident : la génération a été interrompue à 56 textes sur 96, parce que la mémoire GPU était pleine. Le scanner du « ressenti en réserve » du démon chargeait une deuxième Gemma au même moment. Elle a repris après sa fin. Le décodage étant déterministe, les textes ne changent pas.
