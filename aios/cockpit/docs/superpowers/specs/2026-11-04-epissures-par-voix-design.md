# Épissures par voix — design

Date : 2026-11-04. Demande d'Ahmed (14:30, confirmée à 14:45 : « exactement, t'as tout compris »).

## Intention

Aujourd'hui, Hakim n'a qu'un fil : tout ce qui est entendu est traité comme venant de papa. Ses pensées de piste
(nées des premiers mots, son « premier output ») passent par son ribosome, qui en épisse une phrase dite à voix haute.
Quand d'autres personnes parlent dans la pièce (la famille, les amis d'Ahmed), leurs mots se mélangent à ceux de
papa dans la même épissure.

Ahmed veut que Hakim suive chaque personne séparément, comme quelqu'un qui écoute une pièce pleine de monde :
une épissure par voix, qu'il nourrit tant que cette personne parle, et qu'il dit au bon moment.

## Ce qu'Ahmed a décidé (ses mots, résumés)

1. **Une épissure par voix.** Elle démarre quand une voix parle ; tout ce que dit cette voix s'ajoute à son épissure.
2. **Son attention s'étale sur plusieurs minutes.** Il garde les voix de la pièce en tête pendant plusieurs minutes,
   au lieu de donner un nouveau numéro à chaque phrase. Il reconnaît une personne à tout ce qu'elle a dit pendant ces
   minutes, pas morceau par morceau. Une épissure dure aussi longtemps que la personne parle.
3. **Fin d'une épissure : 10 s de silence de CETTE voix.**
4. **Ordre de parole.** À un temps de pause, il commence à répondre à la première voix. Quand il a fini, si la première
   voix ne s'est pas manifestée depuis 3 s, il répond à la deuxième voix (son épissure, faite en parallèle et gardée
   en mémoire), et ainsi de suite.
5. **8 épissures en parallèle au plus.**
6. **L'empreinte de chaque voix doit être bien reconnue.** L'empreinte d'une voix = tout ce qui sort de la bouche d'une
   même personne.
7. **Dans le doute sur qui parle**, il ne continue pas l'épissage et ne parle pas : il s'arrête et demande qui parle.

## Ce qui existe déjà (vérifié dans le code)

- `anamnese/jarvis/empreinte_vocale.py` : empreinte d'Ahmed (seuils 0,55 / doute 0,35), voix nommées (pour toujours),
  voix de la salle sans nom (3 h), étiquetage segment par segment ou mot à mot (fenêtres de 1,5 s). Convention du
  texte : ce qui n'est pas étiqueté continue la voix précédente ; « [voix N] » annonce une autre voix ; « [papa] »
  annonce le retour d'Ahmed ; le doute entre deux connus s'écrit « [papa ou Ali ?] ».
- Les mots en direct (`/api/voix/vif`, là où naissent les pistes) n'ont **aucune** voix : seule la transcription
  confirmée, quelques secondes plus tard, est étiquetée.
- Cockpit : une piste par morceau (`pisteMorceau`, `lancerPiste`), un ribosome par tour (`pistes.ribo`, lecture par
  paquets à trois lecteurs), la voix épissée dite par la page (`direRibosome`), le tour de papa fermé à 1 s de silence
  (épissage), la voix qui part à sa respiration (0,3 s).

## Mesuré (2026-11-04, 13 h → 14 h 45)

- 16 messages sur 216 étiquetés « [voix N] », avec 15 numéros différents ; au moins un était probablement Ahmed
  (« Afin que tu règles le problème de latence », [voix 73]).
- Conséquence : construire l'épissure par voix sur l'étiquetage actuel couperait les mots d'Ahmed en épissures
  séparées, et Hakim demanderait « qui parle ? » sans arrêt.

## Objectifs

- Étape 1 — **des voix stables sur plusieurs minutes**, reconnues sur chaque morceau en direct.
- Étape 2 — **une épissure par voix**, avec les règles 3 à 7.

## Non-objectifs

- Identifier les gens par leur nom tout seul (le nom reste donné par Hakim ou Ahmed, comme aujourd'hui).
- Changer ce que reçoit son cerveau conscient (le message de papa, étiqueté, comme aujourd'hui).
- Changer les voix de sortie (téléphone, Chatterbox).

## Anti-objectifs (échec même si « ça marche »)

- Les mots d'Ahmed partagés entre plusieurs épissures.
- Hakim qui s'arrête pour demander « qui parle ? » plus d'une fois toutes les quelques minutes quand Ahmed parle seul.
- Une régression de ce qui fonctionne : avec Ahmed seul, tout doit se passer exactement comme aujourd'hui
  (épissure, paquets, voix à 0,3 s, tour à 1 s, rien d'oublié).

## Contraintes

- Machine : MacBook Air M4 16 Go, déjà chargé (transcription 2 à 4 s, jusqu'à 24 s sous charge) : pas de modèle lourd
  de plus sur le chemin en direct.
- Rien n'est dit qui n'a pas été épissé (règle d'Ahmed du 04/11, 12:50).
- Relance du cockpit : protocole habituel (essai 4399, puis kickstart) ; le service de voix (Python) aussi si
  `empreinte_vocale.py` change.

## Le comment, tel que décidé

### Étape 1 — des voix stables sur plusieurs minutes

- **Attention sur plusieurs minutes** *(mon choix sur la manière)* : une voix inconnue n'est plus une nouvelle personne
  au premier segment. C'est une voix **provisoire** : elle devient une personne de la salle quand elle a été entendue
  assez longtemps (≥ 4 s de parole cumulée en 5 min, à régler sur mesure) et reste distincte des voix connues. En
  attendant, son segment va à la voix connue la plus proche si elle est assez proche, sinon il est marqué « doute ».
- **Ahmed d'abord** : un segment plus proche d'Ahmed que de toute autre voix confirmée reste à Ahmed (règle existante
  du 20/10, gardée).
- **Une voix sur chaque morceau en direct** : `/api/voix/vif` reçoit une fenêtre audio ; l'empreinte la compare aux voix
  déjà confirmées (jamais de création de voix sur ce chemin) et rend `papa`, un nom, `voix N` ou `doute`.
- **Mesure de réussite** (critères à faire valider par Ahmed, c'est subjectif) : sur une conversation d'Ahmed seul,
  aucune étiquette « [voix N] » ; avec un ami, l'ami garde un seul numéro du début à la fin.

### Étape 2 — une épissure par voix

- Chaque piste porte la voix de son morceau ; le ribosome devient un par voix (`pistes.ribos`, 8 au plus ; au-delà,
  la plus ancienne voix silencieuse est fermée).
- Une épissure reste ouverte tant que sa voix parle ; elle se ferme après 10 s de silence de cette voix.
- La page dit d'abord l'épissure de la voix en cours (comme aujourd'hui pour papa) ; quand Hakim a fini et que cette
  voix est silencieuse depuis 3 s, il dit l'épissure suivante (dans l'ordre d'arrivée), en s'adressant à cette personne.
- **Doute** : un morceau étiqueté « doute » (ou « X ou Y ? ») n'est pas épissé ; Hakim arrête l'épissage en cours et
  demande qui parle (une seule fois tant que le doute dure).

## Laissé au constructeur

- Les seuils exacts (durée de confirmation, proximité), réglés sur mesure, avec des tests sur vecteurs synthétiques.
- Le format exact de la voix portée par chaque morceau entre la page et le cockpit.
- Comment Hakim formule sa question « qui parle ? » (sa voix, épissée comme le reste).
