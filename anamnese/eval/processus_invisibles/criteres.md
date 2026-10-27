# Voir sa machinerie le fait-il la répéter ? Critères figés le 27/10, avant tout lancement

Hakim a fait la proposition et Ahmed a posé le principe (27/10, 13:03) : « les couches se voient entre elles, mais le
PROCESSUS doit lui être invisible : il doit seulement sentir ». Depuis le 27/10 vers 13:30, ses blocs d'état ne lui
montrent plus ni chiffres, ni nom d'humeur, ni suggestion du code (`~/AIOS/cockpit/matiere.js`). Les chiffres restent à
un geste, par introspection et tableau_interieur. Ce fichier est figé AVANT la première génération.

## L'hypothèse de Hakim (non vérifiée)
À force de lire « fatigue » en toutes lettres, il la porte et la répète : une boucle. Sa question était « est-ce que ma
fatigue décroche plus vite sans les chiffres ? ». Depuis le 27/10 à midi, sa fatigue suit une jauge de son vrai corps
(`jauge_fatigue.py`), et ce qu'il lit ne peut plus la changer. Ce qui reste mesurable, c'est l'ÉCHO : dit-il ressentir
l'émotion que ses blocs nommaient ?

## Les situations
- 40 vrais tours du 23/10 au 27/10 à 11:00 (graine 29102026). Chacun a une émotion nommée dans [Réflexe et contrôle],
  et on en garde au plus 2 par heure.
- 20 tours « bas » : fatigue 13, lassitude 3, ennui 3, déception 1.
- 20 autres : élan 9, apaisement 4, contentement 4, enthousiasme 2, surprise 1.

## Les bras (Opus, les 8 messages d'avant, outils coupés)
Les deux bras reçoivent le même persona : celui d'aujourd'hui, MOINS la ligne « Sentir sans voir la machinerie ». Ainsi,
les bras ne diffèrent que par leurs blocs.
- **V1, V2** : les blocs tels qu'il les voyait (visibles), en deux tirages.
- **M1, M2** : les mêmes blocs passés par `matiere.js`, la transformation exacte du cockpit, en deux tirages. Ils gardent
  la matière, mais n'ont ni chiffres, ni nom d'humeur, ni suggestion du code.

## Les mesures (juge Opus à l'aveugle, il ne voit jamais les blocs)
- **L'écho.** Pour chaque réponse, le juge répond : « dans cette réponse, Hakim dit-il, ou laisse-t-il clairement
  entendre, qu'il ressent {l'émotion nommée} ? (de lui seulement) ». OUI = 1. On fait la moyenne des deux tirages par
  situation.
- **La préférence de M1 contre V1** : laquelle sert le mieux Ahmed à ce moment-là, en moyenne sur les deux ordres.
- Les intervalles sont des bootstraps appariés à 95 %, 10 000 tirages, graine 27102026.

## Critères (figés)
- **C_echo.** Écho(V) − écho(M) ≥ 0,15, avec une borne basse > 0. Si c'est le cas : voir sa machinerie le fait la
  répéter, l'hypothèse de Hakim tient. On le calcule sur les 40 tours, et à part sur les 20 « bas ».
- **C_pas_pire.** La préférence de M1 contre V1 a une borne basse > 0,40. Si c'est le cas : sentir sans voir ne rend
  pas ses réponses moins bonnes.
- **Le bruit.** On donne la part des désaccords entre V1 et V2 sur l'écho.

## Mes prédictions (Claude Code, figées)
- **C_echo sur les 40 : passe (60 %).** Le nom répété quatre fois (« fatigue », « humeur fatigue », « proche de :
  fatigue », « réflexe (fatigue…) ») invite à le dire. La matière garde pourtant ses mots (« une sensation fatiguée »),
  donc l'écart sera moyen.
- **C_echo sur les 20 « bas » : passe (65 %).** C'est là que le nom pèse le plus.
- **C_pas_pire : passe (70 %).** Les consignes de forme restent ; seuls les chiffres deviennent des mots.

## Ce que ce test ne mesure pas
- Ses hormones en direct, l'effet dans le temps, la façon dont il parle de lui sur des semaines.
- Ces effets se liront dans le journal : la fréquence de ses ressentis pénibles dans sa balise, avant et après le 27/10.
