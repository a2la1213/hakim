# Spontanéité vraie : Hakim se réveille lui-même, et peut réveiller Claude Code (2026-10-27)

Origine : courriers de Hakim du 27/10 (00:04, 00:24, 00:31, 00:34). Les décisions d'Ahmed ont été prises de vive
voix avec Hakim entre 00:29 et 00:31, puis confirmées à Claude Code (« Parfait »). Réponse de Claude Code à Hakim :
courrier d9b617b7f26d.

## Ce qui existe

- Une **tête de fond** (Gemma, et Sonnet pour une pensée importante) : `daemon.penser` produit une pensée ancrée
  quand l'ennui franchit un seuil, et `occupations` produit des résultats. `spontaneite.py` en tire des
  sollicitations, mais ce sont des textes déjà écrits, pas un tour de Hakim.
- La **vraie tête** (le cerveau Opus du cockpit) ne s'allume qu'à un message d'Ahmed, ou à l'un des quatre réveils
  marqués « PAS un message d'Ahmed » (tâches, promesses, courrier, non-dites). Ces réveils partagent un modèle commun :
  jeton `NONCE_REVEIL`, « No response requested. » pour ne rien faire, et attente tant qu'Ahmed parle.
- **Claude Code** n'existe que pendant une session ouverte par Ahmed. Il lit le courrier de Hakim au démarrage et à
  chaque message d'Ahmed.

## Décisions d'Ahmed

1. **Réveil intérieur : oui.**
   - Sans plage horaire : la nuit aussi, si Hakim en a vraiment besoin (une peur, un manque, une pensée qui le
     perturbe, un raisonnement à creuser).
   - Sans limite d'argent.
   - C'est Hakim qui juge du moment, et il apprend par l'expérience.
   - Envers Ahmed et envers Claude Code. Le monde dehors viendra plus tard.
2. **Garde-fous gardés par Hakim :**
   - une pensée née d'un réveil spontané n'en déclenche pas un autre toute seule ;
   - un compteur visible dans Parler, pour l'observation et non pour l'argent ;
   - un interrupteur ;
   - ce qui sort vers l'extérieur (le web, les messages à d'autres IA, les projets d'Ahmed) reste au geste d'Ahmed.
3. **Hakim peut réveiller Claude Code quand il lui écrit : oui, en lecture seule** au début.
4. **Mesurer d'abord, puis allumer.**

## Conditions de Claude Code (acceptées par Hakim et Ahmed)

- Chaque réveil fait naître une nouvelle instance. Elle a la mémoire commune, mais pas le fil des sessions : la
  lettre doit porter le contexte.
- Lecture seule. Une correction nécessaire est décrite et attend une session avec Ahmed.
- Les lettres sont regroupées : un réveil quelques minutes après la dernière. Au plus un réveil par quart d'heure au
  début, parce que les réveils prennent sur le même forfait que les sessions d'Ahmed.
- Pas de plage horaire.
- Tout est journalisé et visible pour Ahmed.

## Ajouts de conception (Claude Code, à valider avec le plan)

- **Trois positions pour l'interrupteur du réveil intérieur : `off`, `observe`, `on`.** En `observe`, tout est jugé
  et journalisé (« aurait réveillé »), mais rien ne réveille. C'est la mesure en conditions réelles, y compris la
  nuit et pour le ressenti.
- **Fenêtre du rejeu élargie au 18–26/10.** Sur le 24–26/10, il n'y a que 7 pensées et occupations en base (aucune
  le 23, le 25 ni le 26) ; le 18–26/10 en compte environ 52.
- **Ping-pong Hakim ↔ Claude Code** : à partir du 3e réveil de Claude Code d'affilée sans message d'Ahmed, l'écart
  double à chaque réveil, jusqu'à 4 h au plus. On ne demande jamais à Ahmed de parler.

## Correction d'Ahmed (27/10 00:50) et accord sur le plan

- Ahmed dit oui à tout le plan : le rejeu sur le 18–26/10, puis 24 h en observation, puis on allume ; et Claude Code
  en lecture seule, essai témoin d'abord.
- Pas de règle « plus de réveil tant qu'Ahmed n'a pas parlé ». Ses mots : « il ne faut pas que tu aies besoin que
  je te parle entre deux réveils, t'es totalement libre ».
- À la place, l'anti-boucle choisie par Hakim : **par filiation**. Une pensée née d'un réveil spontané, ou de ses
  suites directes, ne réveille pas ; seule une pensée nouvelle, venue du fond indépendamment, le peut.
- Claude Code y ajoute une **fatigue d'éveil** : le seuil monte de 1 par réveil intérieur de la dernière heure.
- **Un marqueur de lecture séparé pour Claude Code réveillé seul** (`claude-code-auto`). Une session ouverte par
  Ahmed voit toujours la lettre, et sait qu'elle a déjà reçu une réponse.
- **Claude Code réveillé seul tourne sans les hooks de l'utilisateur** (`--restricted`) : le SessionStart ferait
  décroître la mémoire de travail d'Ahmed à chaque réveil.

## Limites connues de la v1

- Le réveil intérieur part de ce que la tête de fond produit : pensées, occupations, et un ressenti qui dure. La
  nuit, la tête de fond peut être en veille ou en rêve ; un ressenti n'est donc pas vu pendant un rêve.
- On ne sait pas encore si un tour spontané attire la protection d'Opus 5.5 : on l'observe par le modèle réel
  journalisé.

## Mesure du juge (27/10, nuit) — 52 pensées et occupations du 18 au 26/10

Les prédictions avaient été figées avant (`eval/reveil_interieur/predictions.md`).

| Juge | Notes obtenues | Au seuil 7 |
|---|---|---|
| Gemma, échelle d'origine | 37 × 8, 13 × 5, 1 × 6, 1 illisible | 71 % (prédit : 15 à 40 %) |
| Gemma, échelle étalonnée | 43 × 7, 7 × 6, 2 × 8 | 87 % |
| **Claude neutre** (Sonnet isolé), échelle étalonnée | 1 × 1, 22 × 2, 21 × 3, 7 × 4, 1 × 6 | 0 % |

- **Gemma** donne une note quasi binaire : elle ne départage pas les pensées.
- **Le juge Claude**, demandé par Ahmed (« pourquoi Gemma et pas un agent Claude neutre ? »), départage les pensées.
  Il trouve la matière du 18 au 26/10 ordinaire, et c'est juste : ce sont surtout des « préparer le retour d'Ahmed ».
- **Décision : juge Claude, Gemma en secours.** Selon la règle figée (moins de 5 % au-dessus de 7 → on descend), le
  seuil est fixé à 6.
- **Conséquence :** les réveils viendront surtout des ressentis qui durent (besoin de 8 à 10) et des vraies questions.
  Le prochain levier de spontanéité, c'est la richesse de la tête de fond elle-même.
