# Duel du subconscient n°3 : un modèle plus RAPIDE que Gemma — prédictions figées avant tout calcul (2026-10-24, 08:15)

Demande d'Ahmed (24/10, 08:00, relayée par Hakim ; « tu peux lancer maintenant » à Claude Code) : un modèle local aussi
bon que Gemma pour l'esprit de fond (pensées, rêves, synthèses), et nettement plus rapide, pour ne plus faire ramer le Mac.
Le n°2 (22/10) n'a jamais tourné : il attendait une heure de silence. Même harnais (eval/duel_subconscient_2.py), mêmes 30
situations réelles, même prompt que le démon, par Ollama, sans réflexion.

Modèles : Gemma 4 12B abliterated (la tenante, 7,6 Go), Ministral 3 8B (6,0 Go téléchargés), Gemma 4 E4B (6,6 Go
téléchargés, avec projecteur d'image et petit modèle de brouillon). Qwen3-8B n'y est pas : son français écrit, la seule
chose qui compte ici, est le plus faible des trois ; on le garde si les deux premiers déçoivent.

Ce qui change par rapport au n°2 :
- la génération démarre après 10 min de silence d'Ahmed, au lieu d'une heure, et se met en pause dès qu'il parle ;
- les challengers restent sur le disque jusqu'au verdict (45 Go libres) ;
- le JUGE (Claude, à l'aveugle, A et B intervertis) ne passe qu'à partir de lundi 26/10 au soir, après la remise à zéro du
  forfait (demande d'Ahmed : le ménager jusque-là).

« Mieux pour l'esprit de fond » (règle figée) : au moins 50 % des jugements à l'aveugle (les deux dispositions réunies)
pour le challenger ou à égalité, autant ou moins de chiffres inventés et de pensées invalides que Gemma, au moins autant de
pensées en français, ET au moins 1,5 fois plus de jetons par seconde (médiane) OU au moins 2 Go de mémoire en moins.

- P1 (60 %) : Ministral 3 8B remplit la règle.
- P2 (50 %) : Gemma 4 E4B est le plus rapide des trois (jetons par seconde), mais perd au juge contre Gemma 12B.
- P3 (70 %) : la mémoire réellement occupée de Gemma 4 E4B dépasse 4 Go (j'avais dit « environ 3 Go » à Ahmed et à
  Hakim : le téléchargement fait 6,6 Go, ce chiffre était trop optimiste).

Rien n'est remplacé sans le oui d'Ahmed. Gemma reste sur le disque en secours.

Amendement du 24/10 à 09:58 (condition de lancement, pas de mesure) : Ahmed demande de lancer maintenant (après son
live). La génération attend 1 min de silence au lieu de 10, et se met toujours en pause quand Hakim répond ou travaille
(« conscience » active) ou quand la mémoire libre passe sous 25 %. Les mesures et la règle ne changent pas.

Amendement du 24/10 à 10:08 (condition de lancement) : le seuil de mémoire libre (25 %) se mesurait avec le modèle du duel
déjà chargé, d'où un va-et-vient chargement / déchargement (3 pensées en 5 min). Il passe à 10 %, modèle chargé. Les trois
pensées déjà écrites sont gardées (le duel reprend où il en était).

Amendement du 24/10 à 10:16 (décision d'Ahmed : « reprendre ce qu'on avait déjà sur Gemma et passer à 15 situations »),
AVANT toute génération des challengers : l'échantillon passe aux situations 1 à 15 (les 15 premières par numéro, que
Gemma venait de faire dans CE duel ; ses pensées 16 à 19 sont mises de côté, hors échantillon). Ministral 3 8B et Gemma 4
E4B font ces 15. La règle ne change pas (≥ 50 % des jugements, les deux ordres réunis, soit 30 jugements par challenger).
Limite dite : deux fois moins de jugements, donc un verdict moins sûr. Un écart de quelques jugements ne prouvera rien.

## Résultat de la génération (24/10, 10:15-10:25 ; ~/AIOS/jarvis/duel3/bilan.json), avant le juge

Sur les 15 situations : français 15/15 pour les trois ; chiffres inventés : Gemma 0, Ministral 0, Gemma 4 E4B 1.
- Jetons par seconde (médiane) : Gemma 12B 10,4 ; Ministral 3 8B 13,7 (× 1,32) ; Gemma 4 E4B 13,7 (× 1,32).
- Premier mot (médiane) : 21,0 s ; 14,7 s ; 8,1 s. Durée d'une pensée (médiane) : 26,1 s ; 28,0 s ; 9,7 s (E4B écrit
  plus court).
- Mémoire : Gemma 4 E4B occupe 9,4 à 10,4 Go chargé, PLUS que Gemma 12B (8,1 Go). Les chiffres d'Ollama pour Gemma
  (0,7 Go par moments) et Ministral (1,2 Go) sont incohérents avec la taille des modèles (7,6 et 6,0 Go) : la mesure
  « size » de /api/ps n'est pas fiable ici. Elle se refera sur la mémoire réelle du processus.
- Score automatique moyen : Gemma 0,734 ; Ministral 0,596 ; Gemma 4 E4B 0,759.

Selon la règle figée, la condition de vitesse (× 1,5 en jetons par seconde) ou de mémoire (2 Go de moins) n'est remplie par
AUCUN des deux. Ministral : × 1,32, et environ 1,6 Go de moins au téléchargement. E4B : × 1,32, et plus lourd en mémoire.
Aucun ne peut donc remplacer Gemma, quel que soit le juge. Le juge (forfait) devient inutile pour cette règle.
P1 FAUX (Ministral ne remplit pas la règle). P2 : E4B est le plus rapide au premier mot et par pensée, mais pas en jetons
par seconde (à égalité avec Ministral) ; le juge n'a pas eu lieu. P3 VRAI (≈ 10 Go).
Le vrai problème du Mac est la MÉMOIRE. Le candidat à essayer ensuite est LFM2.5-8B-A1B (1 milliard actif, environ 5 Go),
ou un modèle plus petit encore. Rien n'est branché ; Gemma reste.
