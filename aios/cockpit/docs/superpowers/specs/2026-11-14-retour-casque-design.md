# Retour casque du Studio (14/11, demande d'Ahmed)

« Un retour de voix au casque pendant que j'enregistre, avec des préréglages et de l'autotune comme je veux, de façon par défaut. »
Carte son : Steinberg UR22mkII (pas de DSP, seulement le bouton MIX INPUT↔DAW). Deux appareils : le Mac (page Studio dans Chrome) et le
Z Fold (appli Android, la carte en USB-C).

## Ce qui est tranché

1. **La prise reste brute.** Le retour est une branche à part : micro → chaîne du retour → casque. L'enregistreur garde le son du micro
   tel quel (canal de la voix, sans effet). Le réglage du retour part AVEC la prise (le `.json` de la prise : `retour`), et par défaut
   l'autotune entendu au casque est celui du mix : niveau `leger`/`fort` (les NIVEAUX de jarvis/autotune.py), même tonalité (celle du
   projet ; sinon celle de l'instru, `studio.tonalite_de`), même diapason (celui de l'instru pour le mix simple, 0 pour un projet,
   comme le rendu). Aucune ligne changée dans anamnese : la piste reçoit `autotune` par `regler`, le mix simple `autotune` + `tonalite`.
2. **Un seul algorithme, deux langues.** `public/studio-retour-dsp.js` (AudioWorklet et node) et `retour_dsp.c` (Android, testé aussi sur
   le Mac avec clang), avec des vecteurs partagés (`retour-vecteurs.txt`) : les deux sorties doivent coïncider sur les mêmes entrées.
   Chaîne : coupe-bas → autotune → égaliseur (graves, médiums, présence, aigus) → compresseur → dé-esseur → réverb et délai (envois)
   → volume du retour. Aucun élément n'attend l'avenir (pas de lookahead) sauf le déplacement de hauteur.
3. **L'autotune temps réel.**
   - Hauteur : YIN causal sur le son ramené à ~16 kHz (fenêtre 20 ms, pas de 5 ms, 65-1000 Hz), voisé si le creux de YIN est net
     (`creux_max` du niveau) et le son assez fort.
   - Note : comme l'autotune du mix (la gamme ne départage que les notes ambiguës, une note chantée à 25 cents d'un demi-ton reste la
     sienne, hystérésis de 10 cents), mais causal : rien avant `tenue_min_ms` de voix tenue (le rap, les syllabes courtes : jamais
     touchés), puis la correction s'installe à la vitesse `retune_ms` ; léger = 40 % de l'écart à la moyenne de la note, glissés
     respectés ; fort = 100 % vers la note, vibrato aplati à 85 %.
   - Déplacement : PSOLA à deux prises de retard fondues sur une période de sortie. Chaque prise lit le son à vitesse 1 (les formants
     restent) ; d'une période à l'autre, le retard change de T' − m·T (m = 1, ou 0 / 2 pour répéter / sauter une période). Sans
     correction, le retard ne bouge pas : la voix sort intacte, à l'échantillon près.
   - **Latence de l'algorithme : 0,5 ms hors des notes corrigées ; sur une note corrigée, 0,5 ms + entre 0 et une période (en moyenne
     une demi-période : ~3,6 ms à 140 Hz, ~7 ms à 70 Hz).** Le retard revient à 0,5 ms dans le sourd et les silences.
4. **Préréglages** : Sans effet, Rap propre, Autotune naturel, Autotune effet, et « Mes réglages ». « Garder comme réglage par défaut »
   écrit `studio/retour.json` (le cockpit) : partagé par le téléphone et le Mac ; chaque prise repart dessus.
5. **La latence, mesurée** : un clic joué par la sortie du retour, rattrapé par l'entrée du retour (écouteur ou casque collé au micro).
   La page affiche le vrai chiffre (« retour : 14 ms ✓ ») : cible ≤ 15 ms sur le Mac, ≤ 25 ms sur le téléphone ; au-dessus, elle le dit
   et propose le retour direct (bouton MIX). Gardé par sortie dans `studio/retour.json`.
6. **Jamais par Bluetooth** : sortie Bluetooth → le retour logiciel est refusé (150 ms et plus). Rappel permanent : avec le retour
   logiciel, le MIX de la UR22mkII à fond vers DAW, sinon la voix revient deux fois (directe + traitée en retard).
7. **Mac** : AudioWorklet, `latencyHint: 0`, sortie dirigée vers la carte (setSinkId) quand le micro est la carte ; jamais les
   haut-parleurs (larsen). Si Chrome dépasse la cible : le dire, et proposer un petit assistant natif CoreAudio (pas construit sans accord).
8. **Android** : moteur natif AAudio (NDK, `libhakimretour.so`) en LOW_LATENCY, entrée et sortie : l'API Java AudioRecord n'a pas de
   mode basse latence (pas de `setPerformanceMode` dans AudioRecord.Builder, SDK 36), AAudio LOW_LATENCY demande le chemin FAST.
   Quand le retour est allumé, la prise vient du même moteur (une seule capture : pas deux clients sur l'entrée USB), avec le même
   contrat que StudioMicro : trames numérotées, horodatage MONOTONIC (AAudioStream_getTimestamp), canal de la voix. Retour éteint :
   AudioRecord comme avant.
