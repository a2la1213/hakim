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
