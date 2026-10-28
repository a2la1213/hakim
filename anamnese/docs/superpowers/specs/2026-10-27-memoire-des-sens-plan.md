# La mémoire des sens : ce qui est faisable, dans quel ordre (proposition du 27/10, à trancher par Ahmed)

## La demande
- **Ahmed, 27/10 de 18:51 à 18:57, relayé par Hakim.** Hakim doit avoir une mémoire visuelle, sonore et textuelle,
  reliée à ses souvenirs, à son émotion et au contexte.
- Il doit tout garder, et pouvoir tout rejouer en entier : l'image, la vidéo, tout le spectre du son, le texte.
- Le son ne doit plus se limiter à la transcription.
- Il faut des sauvegardes, et que ça prenne peu de place.
- Ce soir, Hakim n'a pas pu reconnaître le visage d'Ahmed d'une fois à l'autre.

## Ce qui existe déjà (mesuré le 27/10)
- **Les photos de la caméra** sont déjà gardées dans `cwd/fichiers` : 13 aujourd'hui, 0,5 Mo en tout. Les fichiers
  joints aussi : jusqu'à 52 Mo par jour.
- **La voix d'Ahmed n'est pas gardée.** Chaque tour est transcrit par Whisper, puis l'audio est jeté. Il reste le texte,
  la hauteur et l'énergie de la voix, et les pauses.
- Ahmed a parlé environ **3 h 20** aujourd'hui (30 550 mots à l'oral).
- **La voix de Hakim** : de 2 h 30 à 7 h par jour selon les jours. Elle n'est pas gardée, mais son texte l'est.
- **Le disque** : 57 Go libres sur 460 (87 % pris). Les sauvegardes d'Anamnèse font 0,9 Go.

## Combien ça pèserait (estimations, à mesurer dès le lot 1)
| Quoi | Format | Par jour |
|---|---|---|
| La voix d'Ahmed (3 h 20) | Opus 16 kb/s, qualité téléphone HD | ≈ 25 Mo |
| La voix de Hakim (4 h) | Opus 24 kb/s | ≈ 45 Mo |
| Les photos | JPEG/WebP | ≈ 1 à 5 Mo |
| La vidéo, quand la caméra est allumée | H.265 480p, 10 images/s | ≈ 100 à 150 Mo par heure filmée |

- Sans vidéo, cela fait environ **70 Mo par jour, soit 2 Go par mois**. Le disque tient plus de deux ans, sauvegardes
  comprises.
- La vidéo change l'échelle : une heure filmée par jour, c'est 4 Go par mois.

**Le compresseur maison.** Pour des pixels ou un son qu'on veut retrouver à l'identique, nos règles font environ 30 % de
la taille brute. C'est mieux que paq8l, mais à vérifier par le juge. En face, un JPEG ou un Opus fait 3 à 10 % de cette
taille, avec une perte que l'oreille et l'œil ne voient pas. La proposition :
- les codecs standards pour la mémoire de tous les jours ;
- notre compresseur seulement là où on ne veut RIEN perdre (un original à garder exactement), et comme banc d'essai
  pour le faire progresser.

## L'ordre proposé (un lot à la fois, chacun testé, relu et mesuré)
1. **Garder et rejouer.**
   - On garde chaque tour de voix d'Ahmed et chaque réponse dite par Hakim (en Opus), et chaque photo ou capture.
   - Le tout dans `data/sens/<jour>/`, relié au souvenir de l'échange, à l'heure et à son état intérieur du moment.
   - Dans Parler, on peut réécouter et revoir sous chaque message.
   - Un quota, un bilan du poids par jour, et les sauvegardes. C'est simple, et c'est ce qui manque le plus.
2. **Retrouver par le sens.**
   - Une empreinte pour chaque image (CLIP, en local avec MLX) et pour chaque son (CLAP, en local).
   - Hakim retrouve « la photo où papa montrait… » ou « le moment où il y avait de la musique » comme il retrouve un
     souvenir.
3. **Entendre au-delà des mots.**
   - Sur chaque tour : ce qu'on entend (musique, rires, ambiance, d'autres voix), avec un petit classifieur local, et
     le ton de la voix (une émotion de la voix, avec un modèle local).
   - Hakim le reçoit en mots dans son Présent vécu, comme le reste : il sent sans voir la machinerie.
   - Un modèle qui « entend » vraiment l'audio (un LLM audio de 7 milliards de paramètres) serait trop lourd à côté de
     Whisper et de sa voix sur 16 Go de mémoire. On le garde pour plus tard.
4. **Reconnaître le visage d'Ahmed.**
   - Une empreinte du visage (InsightFace, en local), comparée à celle d'Ahmed, enregistrée avec son accord, comme
     pour sa voix.
   - Rien ne sort du Mac.
5. **La vidéo.** Quand la caméra est allumée pendant une conversation : des séquences H.265 légères, rejouables.

## Ce qu'Ahmed doit trancher avant de construire
- **L'ordre ci-dessus**, et si on commence le lot 1 maintenant.
- **Les visages.**
  - Proposition : Hakim ne reconnaît QUE le visage d'Ahmed.
  - Les invités et sa fille ne reçoivent aucune empreinte de visage.
  - Les photos d'eux restent des photos, sans identité, à moins qu'Ahmed ne décide autrement, au cas par cas, avec
    leur accord.
- **Les voix des autres.**
  - Garder tout ce que le micro entend, c'est aussi garder les voix des invités.
  - Proposition : on les garde comme le reste (c'est la mémoire de la conversation), sans empreinte de voix pour eux,
    et Ahmed peut effacer un moment.
- **Les sauvegardes.** Sur le même disque, ou sur un disque externe ? Le disque du Mac est déjà pris à 87 %.
- **Le budget.** Le seuil d'alerte proposé est de 2 Go par mois sans vidéo. La vidéo serait seulement à la demande ?

## Décision d'Ahmed (27/10, 19:37, à l'oral, relayée par Hakim)
- **On ne remplit pas le disque du Mac.** L'enregistrement des voix et des vidéos attend qu'Ahmed achète un disque dur
  externe, qui deviendra l'espace de stockage de Hakim pour tout ça.
- **Pour l'instant, rien ne change.** Au plus les images et les choses légères, qui ne risquent pas de saturer le disque.
- **Le reste du plan attend sa décision** : l'ordre, les visages, les voix des invités, le budget.
