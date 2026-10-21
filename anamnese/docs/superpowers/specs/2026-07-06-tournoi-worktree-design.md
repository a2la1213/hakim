# Tournoi worktree pour problèmes durs — design

- **Date** : 2026-07-06
- **Statut** : design validé par Ahmed (escalade adaptative ; jury adversarial d'office ; niveaux d'escalade 1+2+3 + seeding repliés).
- **Cible** : `~/.claude/skills/atelier/workflow-template.js` (le gabarit d'orchestration) — hors git anamnèse, traçabilité par rapport. Spec/plan versionnés dans le repo anamnèse.
- **Dépend de** : le cerveau partagé (livré) + les paliers de capacité (spec `2026-07-06-super-pouvoirs-gradues-design.md`). Ce chantier s'enchaîne APRÈS les paliers.

## Objectif

Réaliser l'intuition d'Ahmed — « le worktree peut optimiser le raisonnement des agents » — **au bon niveau (orchestration, pas cognition individuelle)**. Un worktree n'améliore pas la pensée d'un agent ; il permet des **tentatives divergentes en parallèle** + une **sélection adversariale** sur les problèmes durs, et — via la mémoire — fait que l'org **apprend quelle stratégie gagne pour quelle classe de problème**. Deux upgrades au gabarit atelier : (1) jury adversarial pour le design, (2) tournoi de build adaptatif.

## État actuel (vérifié — workflow-template.js)

- Phase **Concevoir** : panel de designs par lentille, mais le gagnant est choisi par **auto-note** (`designs.sort((a,b)=>b.score-a.score)`, ligne 45) — signal faible (auto-validation).
- Phase **Construire** : **1 tentative par module**, déjà en `isolation: 'worktree'` (ligne 52). Une seule passe, pas de tournoi.
- Phases Vérifier/Livrer : déjà solides (réfutation adversariale, completeness-critic, audit indépendant).

## Décisions

1. **Jury adversarial de design d'office** (remplace l'auto-note) — gain net, coût faible.
2. **Tournoi de build en escalade ADAPTATIVE** (pas systématique) — le coût N× ne se paie que sur les problèmes durs.
3. **Trois déclencheurs d'escalade** (la difficulté est découverte, pas seulement déclarée) + **seeding** + garde-fou anti « crier au loup ».
4. **Worktrees fournis par le HARNAIS** (`isolation: 'worktree'`), jamais arbor dans un agent.

## Architecture

### 1. Jury adversarial de design (phase Concevoir)

Après les N propositions par lentille : dispatcher un **jury indépendant** — des agents **palier LECTURE** qui n'ont pas écrit les designs, chacun notant les N propositions sur une **lentille distincte** (correctness/robustesse, fidélité métier, perf/échelle). Agrégation des notes → gagnant. On extrait aussi les **bonnes idées des perdants** (à greffer au build). Remplace `designs.sort(by self-score)`.

### 2. Tournoi de build adaptatif (phase Construire)

Par module :
- **Défaut** : 1 tentative en worktree (inchangé).
- **Escalade en tournoi** (N tentatives divergentes, défaut 3, scalable au budget) si l'un des 3 déclencheurs se produit :
  - **N1 — échec de vérif** : la tentative unique échoue (tests rouges / audit BLOQUER).
  - **N2 — auto-report** : l'agent renvoie `needsEscalation: true` + une **raison concrète** (il voit à mi-parcours que c'est un nid de guêpes) → escalade **sans attendre** les tests rouges.
  - **N3 — pré-flag mémoire** : au cadrage, l'orchestrateur `reasoning_recall` la classe de problème ; si le cerveau a mémorisé « dur » (d'un run précédent), il pose `hard:true` **d'emblée**.
  - (Le flag statique `hard:true` explicite au cadrage reste possible.)
- **Chaque tentative** : palier DEV, son propre worktree, une **stratégie distincte** (« minimal/robuste », « perf d'abord », « idiomatique au repo »), lance ses **propres tests**.
- **Seeding (escalade non gaspillée)** : les findings de la tentative échouée/auto-reportée sont injectés dans les N tentatives — « la tentative 1 a essayé A et buté sur B → diverge ». La divergence part plus intelligente qu'à l'aveugle.

### 3. Sélection en 2 temps — OBJECTIF avant subjectif

- **(a) Filtre objectif** : seules survivent les tentatives dont les **tests passent**. (Un jury ne peut jamais choisir une tentative cassée.)
- **(b) Jury adversarial** : sur les survivantes, des juges LECTURE classent sur lentilles diverses → gagnant.
- **(c) Synthèse optionnelle** : greffer les bonnes idées des perdantes **seulement si propre/pas cher** (sinon on garde le gagnant tel quel).
- **0 survivante** → **BLOQUER** vers Ahmed, avec les preuves d'échec des N tentatives. Pas d'escalade infinie.
- Le worktree gagnant est retenu ; les perdants **jetés** (auto-nettoyés par le harnais).

### 4. Apprentissage persistant (le cœur de l'intuition)

À l'issue d'un tournoi : la **stratégie gagnante + pourquoi elle a gagné (et pourquoi les autres ont perdu)** est écrite comme trace `kind="reasoning"` dans `projets/<projet>/<domaine>` (provenance de l'orchestrateur/agent gagnant). Effet : au prochain problème de la même classe, `reasoning_recall` fait remonter la stratégie gagnante → les agents démarrent plus intelligents, et N3 pré-flag la difficulté. **Le raisonnement de l'org s'optimise dans le temps.**

## Garde-fous

- **Coût délibéré** : `log()` de chaque escalade et de son POURQUOI (jamais de N× silencieux). N=3 défaut, scalable via `budget`.
- **Anti « crier au loup »** (N2) : l'auto-report exige une **raison concrète** (pas un flag nu) ; plafond d'escalade (N fixe → puis barrière humaine) ; la charte (ne pas gonfler pour plus de ressources) limite l'abus.
- **Objectif avant subjectif** : les tests filtrent, le jury ne fait que classer les survivantes.
- **Composition avec les paliers** : agents de build = DEV, juges = LECTURE — les deux chantiers composent (les paliers disent CE que fait chaque agent ; le tournoi dit COMBIEN et comment on sélectionne).

## Vérification (dry-run)

1. **Escalade N1** : un module au test volontairement cassé → prouver que la vérif échoue → le workflow escalade en N tentatives worktree.
2. **Escalade N2** : un agent renvoyant `needsEscalation:true` + raison → escalade sans attendre les tests rouges.
3. **Sélection** : parmi N tentatives dont certaines cassent les tests → prouver que seules les vertes atteignent le jury, et que le gagnant vient du jury (pas de l'auto-note).
4. **Nettoyage** : les worktrees perdants sont supprimés ; seul le gagnant persiste.
5. **Mémoire (N3)** : la trace « stratégie gagnante + pourquoi » est écrite ; un 2ᵉ run `reasoning_recall` la retrouve et pré-flag `hard`.
6. **Review adversariale** (prose/JS) : le trigger est-il sain ? le filtre objectif empêche-t-il un jury de choisir une tentative cassée ? l'escalade est-elle bornée ? le coût est-il loggé ?

## Ce qu'on ne fait PAS (YAGNI)
Arbor dans les agents (harnais fournit les worktrees) · tournoi sur le trivial (escalade adaptative) · synthèse risquée · escalade sans fin · auto-report sans raison concrète.

## Honnêtetés
- Un worktree n'améliore PAS la cognition d'un agent isolé — le gain est au niveau orchestration (tentatives parallèles + sélection) et, persistant, via la mémoire. Revendiqué tel quel, sans survente.
- Livrable = JS (workflow-template.js) + schémas. Pas de pytest ; confiance = dry-run (dont escalade + sélection objective) + review adversariale.
- N2 (auto-report) dépend de l'honnêteté de l'agent — mitigé par « raison concrète exigée » + gate orchestrateur, pas infaillible. Signalé.
- `~/.claude` hors git-anamnèse → rapport + backup du gabarit.
