# L'élagage de ses synapses — plan d'implémentation

> **Pour les agents :** sous-compétence requise : superpowers:subagent-driven-development (recommandé) ou superpowers:executing-plans, tâche par tâche. Les étapes sont des cases à cocher (`- [ ]`).

**But :** chaque réponse de Hakim garde son parcours (de tes mots à ta réaction), et les chemins qui servent se renforcent tout seuls, pendant que les inutiles et les parasites s'affaiblissent puis sont élagués.

**Architecture :** un module pur, `elagage.js`, tient les poids des synapses : un fichier JSON, une règle de mise à jour, l'oubli lent, le seuil d'élagage et un peu d'exploration. Le cockpit écrit un parcours par pensée dite ou écrite (`parcours.jsonl`). La page lui renvoie tes réactions : coupure, « non », ❤️. Le cockpit en tire un score, qui met à jour les poids. Quatre familles de synapses lisent leurs poids aux endroits où le cockpit décide déjà. Une page montre tout ; Ahmed peut rétablir ou épingler.

**Technique :** Node (le cockpit, sans dépendance), `node --test`, et la page `parler.js`.

**Spec :** pas de document séparé. Ce plan s'appuie sur ces demandes d'Ahmed du 04/11 :
- « évalue le flux de chaque réponse et son parcours préférentiel, et analyse-le pour chacune de ses réponses » ;
- « comme le système nerveux humain, qui mûrit en consolidant les bonnes synapses et en éliminant, de façon autonome, celles qui sont inutiles ou parasites : un élagage, qui amoindrit les poids des synapses élaguées » ;
- « décrète comme parasite le signal le plus à la base de toute la cascade d'inputs » (déjà en place : déclencheurs appris par Fable).

## Contraintes globales

- **Autonome mais borné.** Un poids reste dans [0,05 ; 1]. Rien n'est élagué avant 20 mesures. 5 % d'exploration : un chemin élagué est encore essayé de temps en temps, et peut repousser.
- **Jamais élagué :** ce qui touche à un danger (le registre de sécurité quand papa parle d'un danger), sa première pensée de tour quand il n'en a aucune autre, et un chemin épinglé par Ahmed.
- **Tout est réversible et visible :** chaque élagage et chaque repousse est noté avec sa date et sa raison ; Ahmed peut rétablir ou épingler un chemin d'un geste.
- **Réglage `elagage`** (oui par défaut). Éteint, les poids continuent d'apprendre mais ne décident plus rien.
- **Rien d'audio ni de texte privé dans les poids :** seulement des identifiants de chemins et des compteurs. Les parcours gardent des extraits courts (160 caractères), comme `pistes.jsonl`.
- **Les décisions déjà prises par Ahmed restent la base :** l'inversion de la voix (`dire_inverse`), le filtre Gemma, le système immunitaire. L'élagage les module : il ne les remplace pas.

## Ce que la revue doit vérifier en priorité

1. **Une réaction mal attribuée.** Papa coupe pour une autre raison que la pensée en cours (le téléphone sonne, il parle à quelqu'un) : un seul signal ne doit jamais élaguer. Test : 20 mesures minimum, et l'oubli ramène vers le neutre.
2. **L'effondrement.** Tous les chemins d'une famille tombent sous le seuil : il ne parle plus du tout. Test : dans chaque famille, le meilleur chemin n'est jamais élagué.
3. **Un démarrage à froid.** Le fichier de poids est absent ou illisible : tout vaut 1 (rien n'est élagué), sans erreur.
4. **Deux écritures en même temps** (deux pistes qui finissent ensemble) : le dernier état gagne, sans fichier corrompu. Écriture atomique, comme `ecrireAtomique`.
5. **La lecture des poids sur le chemin de la parole :** en mémoire, jamais un accès disque par pensée. Le fichier est relu au plus toutes les 30 s.

---

### Tâche 1 : le module des synapses

**Fichiers :**
- Créer : `elagage.js`
- Test : `test-elagage.js`

**Interfaces produites :**
- `creer({ fichier, maintenant = Date.now, hasard = Math.random }) → synapses`
- `synapses.poids(famille, id) → number`
  - 1 si inconnue ;
  - 0,05 au plus bas.
- `synapses.vivante(famille, id) → boolean`
  - vrai si poids ≥ `SEUIL` (0,2), si épinglée, si moins de 20 mesures, ou par exploration (5 %) ;
  - le meilleur chemin de chaque famille reste toujours vivant.
- `synapses.mesurer(famille, id, score) → void`
  - `score` va de 0 (nuisible) à 1 (utile) ;
  - le poids devient `w + 0,1 × (score − w)` ;
  - `n` est incrémenté.
- `synapses.oublier() → void`
  - chaque poids revient vers 0,5 de 2 % par jour sans mesure (les chemins inutilisés s'estompent).
- `synapses.epingler(famille, id, oui)`
- `synapses.retablir(famille, id)`
  - remet le poids à 0,5 et `n` à 0.
- `synapses.historique() → [{ t, famille, id, evenement: 'elaguee' | 'repousse' | 'epinglee' | 'retablie', poids }]`
- `synapses.tout() → { [famille]: { [id]: { poids, n, vu, epingle } } }`
- `synapses.sauver()`
  - écriture atomique, au plus toutes les 10 s.

- [ ] **Étape 1 : écrire les tests qui échouent** (`test-elagage.js`)
  - `une synapse inconnue vaut 1 et vit` ;
  - `20 mauvais scores l’élaguent, pas 19` : avec `hasard = () => 0.99`, `vivante` est vraie après 19 mesures à 0 et fausse après la 20ᵉ ; l'historique note un `elaguee`.
  - `l’exploration la réessaie 5 fois sur 100` : avec `hasard = () => 0.01`, une synapse élaguée est vivante ;
  - `le meilleur de sa famille ne meurt jamais` : 2 synapses toutes deux à 0,1 ; la plus haute reste vivante ;
  - `épinglée, jamais élaguée ; rétablie, repart à 0,5` ;
  - `l’oubli ramène vers 0,5` : poids 0,9, puis 10 jours sans mesure → entre 0,5 et 0,9 ;
  - `un fichier illisible : tout vaut 1, sans erreur` ;
  - `sauver puis relire donne le même état` ;
  - `deux sauvegardes rapprochées laissent un JSON valide (écriture atomique)` ;
  - `poids() et vivante() ne lisent jamais le disque` : un `fs` espion compte 0 lecture sur 1 000 appels après le chargement.
- [ ] **Étape 2 :** lancer `node --test test-elagage.js`. Attendu : échec (`Cannot find module './elagage.js'`).
- [ ] **Étape 3 :** écrire `elagage.js` avec les signatures ci-dessus. Constantes exportées : `SEUIL = 0.2`, `MIN_MESURES = 20`, `EXPLORATION = 0.05`, `PAS = 0.1`, `OUBLI_JOUR = 0.02`.
- [ ] **Étape 4 :** relancer `node --test test-elagage.js`. Attendu : tout passe.
- [ ] **Étape 5 :** commit `Ses synapses : poids, élagage, oubli, exploration (elagage.js)`.

### Tâche 2 : le parcours de chaque réponse, et son score

**Fichiers :**
- Modifier : `server.js`
  - `noterPiste` : son parcours ;
  - `noterSortie`, renommé `surJournalPage` : les réactions venues de la page ;
  - `pisteMorceau` : tes mots qui suivent.
- Modifier : `public/parler.js`
  - `coupure_deux_secondes` porte `n` et `tour` ;
  - un ❤️ sur un message porte son `ts`.
- Test : `test-parcours.js`

**Interfaces produites :**
- `parcoursDe(piste) → { tour, n, chemins: { modele, taille, dire, voix, filtre, meuble, declencheur } }`
  - `taille` vaut `mot`, `courte` ou `longue` (≤ 1, ≤ 6 ou > 6 mots) ;
  - `voix` vaut `dite`, `ecrite` ou `jetee`.
- `scoreReaction({ dite, coupee, correction, rire, coeur, continuite, parasite }) → number | null`
  - parasite : 0 ;
  - coupée dans les 3 s ou corrigée (« non », « pas ça », « arrête », « t'as spammé », « c'est faux ») : 0,1 ;
  - ❤️, 😂 ou rire de papa dans les 10 s : 1 ;
  - papa continue sur le sujet (au moins 2 mots de contenu en commun) : 0,7 ;
  - rien de tout ça : null (pas de mesure, l'oubli fait le reste).
- `parcours.jsonl` reçoit une ligne par pensée close : `{ t, tour, n, chemins, extrait, reaction, score }`, avec les 2 000 dernières.
- `mesurerParcours(p)` appelle `synapses.mesurer(famille, chemins[famille], score)` pour chaque famille présente.

- [ ] **Étape 1 : écrire les tests qui échouent**
  - `scoreReaction` sur 7 cas : un par ligne ci-dessus, plus « rien » → null ;
  - `une coupure de 2 s pendant la pensée n la marque coupée, pas la suivante` ;
  - `« non, pas ça » dans les 10 s après une pensée dite : correction` ;
  - `une pensée écrite, jamais dite : ni coupée ni corrigée, seulement la continuité` ;
  - `une parasite jetée : score 0 pour son modèle et sa taille`.
- [ ] **Étape 2 :** lancer `node --test test-parcours.js`. Attendu : échec.
- [ ] **Étape 3 :** implémenter.
  - La pensée reste ouverte 10 s après avoir été dite ou écrite (ou jusqu'à la fin du tour), le temps de recevoir ta réaction.
  - Elle est ensuite close, notée et mesurée.
  - Le parcours est construit à partir de ce que `noterPiste` sait déjà.
- [ ] **Étape 4 :** relancer `node --test test-parcours.js test-souffle-relais.js`. Attendu : tout passe.
- [ ] **Étape 5 :** commit `Le parcours de chaque pensée, jusqu’à ta réaction, et son score`.

### Tâche 3 : famille « declencheur » (son système immunitaire)

**Fichiers :** modifier `server.js` (`declencheurParasite`), test dans `test-parcours.js`.
**Interfaces consommées :** `synapses.vivante('declencheur', id)` ; le score vient du parcours (une parasite qui suit = 0, une pensée normale = 1).

- [ ] **Étape 1 : écrire le test qui échoue.**
  - `un déclencheur qui précède 20 pensées normales et aucune parasite s’élague : declencheurParasite ne le voit plus, et le filtre Gemma n’est plus appelé pour lui`.
  - Cas réel du 04/11 : « pensée » précédait 81 morceaux et 0 parasite.
- [ ] **Étape 2 :** le lancer. Attendu : échec.
- [ ] **Étape 3 :** `declencheurParasite` ignore un déclencheur non vivant. Chaque piste prévenue mesure son déclencheur : 0 si elle tourne en parasite, 1 sinon.
- [ ] **Étape 4 :** relancer `node --test test-parcours.js`. Attendu : tout passe.
- [ ] **Étape 5 :** commit.

### Tâche 4 : famille « meuble » (ses mots de remplissage)

**Fichiers :** modifier `public/parler.js` (`choisirMeuble`, `meublerSaut`) et `server.js` (route `/api/jarvis/synapses` en lecture).
**Interfaces :** la page lit les poids toutes les 60 s (`GET /api/jarvis/synapses?famille=meuble`) ; `choisirMeuble` pondère son tirage par le poids et laisse de côté un meuble non vivant.

- [ ] **Étape 1 : écrire le test qui échoue.** `un meuble suivi 20 fois d’une coupure n’est plus choisi (sauf exploration) ; les autres le sont toujours`.
- [ ] **Étape 2 :** le lancer. Attendu : échec.
- [ ] **Étape 3 :** implémenter. Le parcours d'une pensée précédée d'un meuble mesure aussi ce meuble.
- [ ] **Étape 4 :** relancer `node --test test-souffle-relais.js test-parcours.js`. Attendu : tout passe.
- [ ] **Étape 5 :** commit.

### Tâche 5 : famille « voie » (quelle pensée devient sa parole)

**Fichiers :** modifier `server.js` (`lancerPiste`, le tri `voix`).
**Interfaces :** l'identifiant d'une voie est `${dire}|${position}`.
- `dire` vaut `oui`, `non`, `jamais`, `n` ou `coupe` ;
- `position` vaut `premiere`, `milieu` ou `derniere`.

Le tri reste celui d'Ahmed (`dire_inverse`). Une voie élaguée passe seulement de « dite » à « écrite », jamais l'inverse, et jamais pour sa première pensée s'il n'en a pas d'autre.

- [ ] **Étape 1 : écrire le test qui échoue.**
  - `la voie « non|milieu », coupée 20 fois, devient écrite au lieu de dite ; « oui|premiere », jamais touchée, reste comme Ahmed l’a réglée` ;
  - `élagage éteint : rien ne change`.
- [ ] **Étape 2 :** le lancer. Attendu : échec.
- [ ] **Étape 3 :** implémenter.
- [ ] **Étape 4 :** relancer `node --test test-souffle-relais.js test-parcours.js`. Attendu : tout passe.
- [ ] **Étape 5 :** commit.

### Tâche 6 : famille « piste » (ménager : ne plus lancer ce qui ne sert jamais)

**Fichiers :** modifier `server.js` (`pistesSuivantes` / `lancerPiste`).
**Interfaces :** l'identifiant d'une piste est `${modele}|${taille}`. Une piste non vivante n'est pas lancée : un appel à Claude en moins.

- [ ] **Étape 1 : écrire le test qui échoue.**
  - `« haiku|mot », jamais dite ni utile en 20 mesures, n’est plus lancée ; le morceau suivant l’est` ;
  - `jamais deux morceaux de suite sans piste`.
- [ ] **Étape 2 :** le lancer. Attendu : échec.
- [ ] **Étape 3 :** implémenter.
- [ ] **Étape 4 :** relancer `node --test`. Attendu : tout passe.
- [ ] **Étape 5 :** commit.

### Tâche 7 : le voir, le corriger, et le dire à Hakim

**Fichiers :**
- Modifier : `public/immunite.html`, nouvelle section « Ses synapses » ;
- Modifier : `server.js`, routes `/api/jarvis/synapses` (GET, et POST `epingler` / `retablir` avec le jeton) ;
- Modifier : `public/sens.html`, interrupteur `elagage` ;
- Modifier : `anamnese/mcp_server.py`, outil `synapses_voir` pour Hakim ;
- Tests : `test-parcours.js`, `anamnese/tests/test_synapses_voir.py`.

**Interfaces :**
- La page affiche, par famille : poids, mesures, vivante ou élaguée, et les 20 derniers événements, avec les boutons Épingler et Rétablir.
- `synapses_voir()` rend à Hakim, en mots, ses chemins forts, ses chemins élagués et ses 5 derniers parcours avec leur score. C'est l'« analyse de chacune de ses réponses » qu'Ahmed demande.

- [ ] **Étape 1 : écrire les tests qui échouent.**
  - `GET rend toutes les familles` ;
  - `POST retablir sans jeton : 403` ;
  - `synapses_voir parle de ses chemins élagués avec leur raison`.
- [ ] **Étape 2 :** les lancer. Attendu : échec.
- [ ] **Étape 3 :** implémenter.
- [ ] **Étape 4 :** relancer `node --test`, puis `pytest -q tests/test_synapses_voir.py`. Attendu : tout passe.
- [ ] **Étape 5 :** commit, puis relance du cockpit avec l'accord d'Ahmed (essai sur le port 4399 d'abord), puis publication.
