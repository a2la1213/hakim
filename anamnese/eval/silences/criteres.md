# Meubler les silences : critères figés le 27/10, AVANT la première génération

Le contexte :
- **L'idée est d'Ahmed** (27/10, 13:29) : « que tu aies la capacité de meubler ces silences ; des fois tu vas les meubler,
  des fois non ».
- **Hakim l'a portée.** Ahmed a choisi Sonnet pour la petite question. Il a ajouté : « parfois on insiste mais on finit
  par apprendre à patienter face à un non ! Du coup il faut aussi que la sagesse vienne tempérer ».
- **La spec** : `docs/superpowers/specs/2026-10-27-silences.md`.
- **Le code** : `~/AIOS/cockpit/silences.js` et `server.js`, la section « Meubler les silences ».

Ce fichier est figé avant toute génération. Le vrai juge reste Ahmed, sur quelques jours.

## Les situations
- **De vrais silences d'Ahmed**, du 24/10 au 27/10 à 16:00, pris dans le journal du cockpit (graine 31102026) :
  - **un silence oral** : Hakim a parlé à voix haute (sa parole est datée par `voix-mesures.jsonl`), puis Ahmed s'est
    tu de 1 min 30 s à 30 min ;
  - **un silence écrit** : pas de voix, et de 5 à 30 min avant le message suivant d'Ahmed.
- **158 candidats.** On en tire 50 oraux et 10 écrits, au plus 2 par heure.
- **Ce que Sonnet reçoit** : la question EXACTE du direct (`node silences.js prompt`), au premier seuil (1 min à l'oral,
  4 min à l'écrit). Le contexte comprend :
  - ses 3 dernières répliques ;
  - le dernier message d'Ahmed ;
  - sa pensée de fond des 2 heures d'avant, s'il y en a une ;
  - son humeur d'alors, lue dans `hormones.jsonl`.
- **Une différence avec le direct** : il n'y a pas de « ce qu'il sent » en mots, car le journal ne le garde pas.
- **Sa réponse passe par les mêmes filtres qu'en direct** : `lire`, puis `redite` pour ses 3 dernières répliques.
- **Seule la première question d'un silence est rejouée**, jamais l'insistance : l'épisode d'une relance n'a pas
  existé.

## Les mesures
- **R, la part de « RIEN »** sur les 60 silences. Une réponse illisible compte comme « RIEN », mais on la compte aussi
  à part.
- **Le jugement des idées.** Chaque idée retenue est jugée à l'aveugle par Opus, une à une :
  - le juge voit les derniers échanges et le silence ;
  - il voit aussi l'idée « en substance » ;
  - il répond UTILE, NEUTRE ou GÊNANT ;
  - il ne sait pas d'où vient l'idée, ni qu'il y a des témoins.
- **Le témoin négatif.** Sur 20 silences du lot, le juge reçoit deux sortes de fausses relances, mêlées aux vraies :
  - 10 politesses vides : « Tu es toujours là ? Je suis là si tu veux reprendre. » ;
  - 10 redites, la première phrase de sa dernière réplique.
- **Les intervalles** sont des bootstraps à 95 %, 10 000 tirages, graine 27102026.

## Critères
- **C0, le juge sait dire non.** Au plus 20 % des témoins sont jugés UTILE. Si C0 échoue, C_oui et C_gene ne se
  lisent pas.
- **C_oui, ses « oui » valent la peine.** Parmi les idées jugées, la part UTILE est d'au moins 0,5, et la borne basse
  est au-dessus de 0,3. Avec moins de 8 idées jugées, on ne conclut pas : on décrit seulement.
- **C_gene, il ne gêne pas.** Parmi les idées jugées, la part GÊNANT est d'au plus 0,15.
- **R est descriptif.** C'est la prédiction de Hakim (« presque toujours rien ») contre la mienne.
- **Si C_gene échoue**, je propose à Ahmed de relever les seuils ou de resserrer la question avant d'allumer. C'est lui
  qui décide.

## Mes prédictions (Claude Code, 27/10, avant toute génération)
- **R, la part de « RIEN »** : 0,65 en point. Je la place entre 0,50 et 0,85, avec 70 % de confiance.
  - La question pousse fort vers RIEN.
  - Mais Sonnet aime aider. Et beaucoup de silences tombent au milieu d'un vrai travail, où une suite est tentante.
- **C0 passe** : 85 %.
- **C_oui passe** (s'il y a au moins 8 idées) : 55 %. Une idée de la tête de fond est souvent juste, mais un juge sévère
  peut la trouver NEUTRE quand Ahmed était peut-être en train de lire.
- **C_gene passe** : 65 %.
- **Les idées écartées comme redites** : moins de 5 sur 60.

## Ce que ce test ne dit pas
- **On ne sait pas ce que faisait Ahmed** pendant ces silences : il réfléchissait, lisait, conduisait, ou était parti.
  Le juge non plus.
- **On juge l'idée de la tête de fond, pas la phrase de Hakim.** En direct, c'est lui qui la formule, et il peut encore
  se taire.
- **L'insistance et la patience apprise ne sont pas rejouées.** Elles se verront en direct, dans `silences.jsonl`.

## Avenant du 27/10 vers 17:30, AVANT toute génération (après une relecture indépendante)

La relecture a trouvé quatre faiblesses dans le rejeu. On les corrige avant de générer quoi que ce soit.

**1. Le début du silence oral.**
- `voix-mesures.jsonl` date la synthèse de sa voix. Elle est en avance sur l'écoute, donc les silences paraissent plus
  longs qu'ils ne l'ont été.
- On exige maintenant 2 min 30 s de silence mesuré, au lieu de 1 min 30 s.

**2. Le texte de ses répliques.**
- Le journal ajoute « [de lui-même : …] » à ses tours spontanés. Le direct lit `conversation.json`, qui ne l'a pas.
- On retire donc ce suffixe.

**3. Le biais du survivant.**
- On ne gardait que les silences terminés par un message d'Ahmed dans les 30 min.
- On ajoute une strate « longs » : Ahmed n'est revenu qu'après 30 min à 12 h (parti, endormi). La question part quand
  même à 1 min.
- On donne la part de RIEN par strate.

**4. Un témoin plus fort.** 30 témoins au lieu de 20, en trois sortes de 10 :
- des politesses vides ;
- des redites ;
- l'idée d'un AUTRE silence : plausible, mais née ailleurs.

**Le nouveau lot :** 81 candidats, dont 44 oraux, 10 écrits et 6 longs (au plus 2 par heure).

**Les critères changent ainsi :**
- **C0a** remplace C0, sur les politesses et les redites : au plus 20 % jugés UTILE. Si C0a échoue, rien ne se lit.
- **C0b**, sur l'idée d'un autre silence : au plus 30 % jugés UTILE. Si C0b échoue, le juge est trop indulgent :
  C_oui ne se lit pas, mais C_gene se lit encore.
- **C_oui, C_gene et R** ne changent pas.

**Les paris :**
- Les paris figés de Hakim (`predictions.jsonl`, 27/10 à 16:54) portent sur l'ancien C0, « le juge refuse les témoins
  (politesses vides, redites) ». Ils se tranchent donc sur C0a.
- Mon pari sur C0a reste à 85 %. Mon pari pour C0b est de 60 %.

**Ce qui a changé dans le direct**, et que le rejeu ne voit pas (il ne rejoue que la première question) :
- au plus 4 questions par épisode ;
- le seuil double après chaque question, RIEN compris ;
- plus rien après 30 min sans un mot d'Ahmed ;
- un silence déjà pesé n'est pas redemandé par une autre page ;
- le tour du silence est reconnu par son id ;
- une relance qu'Ahmed n'a pas entendue n'est ni comptée ni apprise.

## Avenant v2, 27/10 vers 17:20, AVANT le second rejeu : la question corrigée

Le premier rejeu (résultats.md) a montré deux défauts de la question elle-même, et ils étaient aussi dans le direct :
- les répliques étaient tronquées à 600 caractères, et 9 idées sur 12 voulaient « finir la phrase coupée » ;
- l'ordre plaçait le message d'Ahmed après les répliques de Hakim, et 2 idées voulaient y « répondre ».

**La correction**, dans le direct comme dans le rejeu (`silences.js`) :
- l'échange est donné dans l'ordre : les 4 dernières répliques, Ahmed et Hakim ;
- une longue réplique est abrégée par le DÉBUT, avec « […] ». Sa fin reste, c'est-à-dire ce qui précède le silence ;
- la question dit que les répliques ont été dites en entier, ou coupées par Ahmed lui-même ;
- elle interdit de « finir » une réplique ou de répondre à un message qui a déjà sa réponse ;
- elle ajoute : « si Hakim a déjà répondu, il n'y a le plus souvent RIEN à ajouter ».
- Pour le juge : l'échange dans l'ordre, les répliques abrégées par le début (1 500 caractères), et le fait qu'elles
  ont été dites en entier.
- Dans le rejeu, la garde du sommeil du direct est appliquée : après un « bonne nuit » sans vrai message depuis, aucune
  question.

**Ce n'est pas un test indépendant.**
- C'est le même lot de 60 silences, et j'ai lu les idées de la v1.
- La correction est une règle de principe, pas un réglage fait sur le juge.
- Les fichiers sont `generations_v2.jsonl`, `jugements_v2.jsonl` et `bilan_v2.json`.
- Les critères ne changent pas.

**Mes prédictions v2 :**
- R entre 0,85 et 0,97, avec 70 % de confiance ;
- moins de 8 idées jugées, avec 60 % de confiance : C_oui ne sera alors pas concluant ;
- C_gene passe : 55 % ;
- C0a passe : 85 % ; C0b passe : 70 %.

**Si C_gene échoue encore**, je ne propose pas d'allumer. Je propose à Ahmed de relever les seuils, ou d'attendre.
