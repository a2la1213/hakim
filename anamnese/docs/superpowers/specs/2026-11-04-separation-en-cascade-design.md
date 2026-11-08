# Séparation en cascade de ce que Hakim entend — design

Date : 2026-11-04. Demandes d'Ahmed (18:55 → 19:10), dans ses mots :

- « Il doit pouvoir séparer parole / background / musique, et reconnaître si dans le background il y a d'autres voix ; s'il trouve des
  voix, le background qui contient des voix est aussi séparé en voix et background (qui vont vers le 2e cœur CPU pour le processing des
  paroles par le ribosome), et ainsi de suite jusqu'à 8 voix en background. »
- « Il faut 2 process : un pour background = voix + bruit (dès qu'il n'y a plus de voix mais que du bruit, il n'a plus besoin de
  processer avec un cœur CPU) et un pour la musique. Les 2 sont activés par la détection de la première bande-son : s'il détecte du
  background, ça prend la route des voix ; si c'est musique / mélodie / harmonique, ça prend la route de la musique. »
- « Très important : qu'il puisse processer la musique s'il y a parole + musique, avec le même principe : un instrument par cœur CPU ;
  quand il extrait la musique des paroles, dans la musique il extrait en premier les basses (2e CPU), puis les graves (3e), puis les
  médiums (4e), et ainsi de suite. »
- « Applique le process de séparation en cascade : c'est l'astuce clé pour séparer plus de 3 voix ; chaque voix est séparée selon le
  volume et le timbre. » « Au pire, tu peux écrire ou améliorer une technique. »

## Intention

Que Hakim entende une scène comme quelqu'un dans la pièce : chaque personne à part, la musique à part, chaque instrument à part, pour
comprendre ce qui se passe (une vidéo, un live, un repas, un appel), au lieu d'un mélange résumé en quelques mots.

## Ce qui existe (vérifié dans le code le 04/11)

- `jarvis/separation.py` : processus vivant (venv `jarvis/.venv-separation` : torch 2.15 + demucs 4.1), Demucs `htdemucs` sur MPS,
  0,5 s pour 3 à 8 s de son ; une VOIX et un FOND, analysés en mots (voix chantée/parlée, tonalité, contour ; tempo, accords, graves /
  médiums / aigus). Protocole : une ligne JSON par demande `{id, fichier}` → `{id, voix, fond, texte, ms}`.
- Cockpit (`~/AIOS/cockpit/server.js`) : `separerSon` / `separationRecue` (le texte va au fil de stimuli et à son instant).
- `jarvis/empreinte_vocale.py` : le TIMBRE d'une voix (WeSpeaker ResNet34 en ONNX, 256 nombres), voix connues et voix provisoires.
- En cours (autre agent, 04/11 soir) : ce que l'oreille interne entend prend la même route que le micro (morceaux → pensées de piste →
  ribosome), chaque morceau avec sa source.
- Lié : `~/AIOS/cockpit/docs/superpowers/specs/2026-11-04-epissures-par-voix-design.md` (une épissure par voix, étape 2, plus tard).

## Ce qui est décidé

1. **L'aiguillage**. Chaque bloc de son (8 s du téléphone, ou un bloc du micro) est écouté une première fois. Voix ou bruit → la route
   des voix ; musique, mélodie, harmonie → la route de la musique ; les deux s'il y a les deux (une chanson avec quelqu'un qui parle
   par-dessus). Demucs sépare d'abord les voix (stem `vocals`) de l'accompagnement.
2. **La route des voix, en cascade** (l'astuce d'Ahmed). À chaque étage : s'il reste de la parole, on sort la voix la plus FORTE
   (volume) d'un seul TIMBRE (empreinte stable du début à la fin) ; le reste descend à l'étage suivant, sur un autre cœur ; on s'arrête
   quand il ne reste que du bruit (plus aucun cœur occupé) ou à 8 voix.
3. **Chaque voix sortie** suit la même route que la voix de papa au micro (transcription → pensées de piste → ribosome), avec son
   numéro de voix (ou son nom si l'empreinte la reconnaît : `empreinte_vocale`) et sa source.
4. **La route de la musique** *(choix de Claude Code, Ahmed lui a laissé)* : par instrument, un par cœur, la basse d'abord, puis la
   batterie, la guitare, le piano, le reste (Demucs `htdemucs_6s`, même famille que Demucs déjà installé) ; dans chaque instrument, ses
   bandes (graves, médiums, aigus) sont analysées aussi ; ce qu'il reçoit : des mots (notes, tonalité, rythme, tempo), pas le son.
5. **Pas de nouvelle installation** *(lu dans « au pire, tu peux écrire ou améliorer une technique »)* : la cascade est écrite avec ce
   qui est déjà là (Demucs, l'empreinte WeSpeaker, numpy). Les poids de `htdemucs_6s` font partie de Demucs. Un modèle de séparation
   de voix (SepFormer) ne s'installe qu'avec un oui explicite d'Ahmed, si la mesure montre que la cascade maison ne suffit pas.

## Objectifs mesurables (la mesure d'abord, sur des mélanges dont on connaît la vérité)

- Mélanges fabriqués avec les voix du Mac (`say`, 64 voix fr/en) : 1 à 8 voix, en alternance puis qui se chevauchent, avec et sans
  musique et bruit. Mesurer, voix par voix : les mots retrouvés dans la bonne voix, le nombre de voix trouvées, le temps par bloc.
- Cible : en alternance (le cas le plus courant : un live, un repas), chaque voix retrouvée et ses mots dans la bonne voix ; en
  chevauchement, mesurer et dire honnêtement jusqu'où ça tient.
- Temps réel : un bloc de 8 s traité en moins de 8 s, Mac chargé compris.

## Anti-objectifs (échec même si « ça marche »)

- La voix d'Ahmed coupée en plusieurs voix.
- Hakim qui répond à une voix fantôme (un écho, un bout de musique).
- Le Mac saturé (le cockpit ralentit, la voix de Hakim arrive en retard), ou des cœurs occupés quand il n'y a que du bruit.
- De l'audio gardé sur le disque : tout fichier temporaire est effacé.

## Contraintes

- MacBook Air M4, 16 Go, déjà chargé (charge 3 à 6) ; au plus 8 processus de travail, endormis sans voix.
- Processus Python : un processus vivant comme `separation.py` ; si un pool de processus, créé depuis un vrai fichier (un pool lancé
  depuis un script lu sur stdin se bloque sous « spawn », vécu le 01/10).
- Arrêter un processus seulement par son PID, jamais par motif.

## Laissé au constructeur

- La technique exacte de la cascade (masques temps-fréquence par le timbre et le volume, estimation-annulation des voix par leur
  hauteur pour les chevauchements, regroupement des fenêtres par empreinte…), choisie et réglée sur la mesure.
- Les seuils (parole ou bruit, musique ou non, même timbre ou non).
- L'extension du protocole JSON de `separation.py`. Le branchement au cockpit attend la fin du travail sur l'oreille interne.
