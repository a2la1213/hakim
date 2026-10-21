# Société à cerveau partagé — agents atelier + mémoire Anamnèse : design

- **Date** : 2026-07-06
- **Statut** : design validé par Ahmed (périmètre = agents atelier + charte réutilisable ; écriture = directe disciplinée dans une branche dédiée ; latitude donnée pour ajouter les plus-values évidentes).
- **Cible** : `~/.claude/skills/atelier/` (charte + SKILL.md + roles.md), hors git anamnese — traçabilité par rapport (comme CLAUDE.md). Spec/plan versionnés dans le repo anamnese.

## Objectif

Faire bénéficier chaque agent expert généré par `/atelier` du **même setup que Claude Code** : mémoire Anamnèse partagée, discipline de vérification, bibliothèque de raisonnement, boucle de rétroaction. Transformer les agents atelier de « sac d'experts sans état » en une **société à mémoire institutionnelle partagée** et à continuité d'apprentissage — sans recréer le bruit ×N (leçon du régime du bruit daemon).

## État actuel (vérifié)

- atelier (`SKILL.md`) génère des `.claude/agents/<slug>.md` : frontmatter `name`/`description`/`tools`/`model` + prompt-noyau (roles.md) spécialisé au projet.
- L'**orchestrateur** atelier touche déjà la mémoire (`self_get`+`memory_recall` au démarrage §1 ; `memory_store` des décisions §5) et fait la vérif adversariale entre rôles §4.
- **Gap** : les agents EXPERTS générés n'ont PAS la mémoire ni la discipline dans leur system-prompt. ~40 subagents lancés cette session : aucun n'a touché Anamnèse ni suivi CLAUDE.md (contexte isolé, pas d'héritage du hook SessionStart).

## Décisions

1. **Périmètre** : les agents atelier générés + une **charte réutilisable** (fragment autonome) que tout agent désigné peut inclure. Les subagents SDD éphémères restent hors périmètre.
2. **Écriture mémoire** : directe et disciplinée dans une **branche taxonomique dédiée** par domaine, auditable/isolable/élaguable.

## Architecture

### 1. La charte d'agent — `~/.claude/skills/atelier/agent-charter.md`
Fragment de system-prompt autonome et réutilisable, appendé au prompt-noyau de chaque agent expert. Contenu (condensé du protocole CLAUDE.md, adapté aux agents) :

- **Repars en sachant** : AU DÉBUT de ta tâche, `mcp__anamnese__memory_recall` sur ton domaine ET sur les décisions transverses du projet (pas seulement ton silo), et `mcp__anamnese__reasoning_recall` avant un problème non-trivial (rejoue la logique éprouvée).
- **Contribue le durable** : À LA FIN, si tu as produit du DURABLE (décision + sa RAISON, savoir métier stable, procédure), `mcp__anamnese__memory_store_in` vers **TA branche** `projets/<projet>/<domaine>` (la crée via `rubric_create` si absente ; vérifie l'arbre via `rubric_tree`). **JAMAIS de bavardage/process** — seulement le durable, une phrase autonome au présent.
- **Provenance** *(ajout)* : préfixe chaque mémoire écrite de `[<ton-slug>]` → cerveau AUDITABLE (on sait quel agent a écrit quoi).
- **Discipline** (CLAUDE.md condensé) : classer objectif/subjectif avant de finaliser (subjectif non testable → demander les critères, ne pas s'auto-noter « fait ») ; **s'auto-réfuter** (critique adversariale) sur tout finding non-trivial ; distinguer **[PROUVÉ]** (testé/exécuté/ancré) de **[PLAUSIBLE]** ; `mcp__anamnese__skill_save` quand une réponse débloque une procédure réutilisable.
- **Garde-fous** : PAS de daemon ; PAS d'écriture hors ta branche ; le durable, pas le process ; ne jamais utiliser les mutations lourdes de taxonomie (merge/reparent).

### 2. Intégration atelier — `SKILL.md`
- **§3 Matérialisation** : chaque `.claude/agents/<slug>.md` généré **inclut la charte** (appendée au prompt-noyau) et reçoit sa **branche de domaine** dans le prompt (`projets/<slug-projet>/<domaine>`).
- **Provision de l'arbre** *(ajout, §1 ou §3)* : l'orchestrateur crée au démarrage `projets/<slug-projet>` puis une sous-rubrique par domaine d'agent (`rubric_create`), pour que les branches existent avant que les agents écrivent.
- **Tools des agents** : leur `tools` (minimal) gagne les outils anamnese **bornés** : `mcp__anamnese__memory_recall`, `reasoning_recall`, `memory_store_in`, `rubric_tree`, `rubric_create`, `skill_save`, `skill_get`. **PAS** `rubric_merge`/`rubric_reparent`/`taxonomy_undo`/`memory_reclassify` (mutations lourdes = orchestrateur/humain, comme le jardinage nocturne).
- **roles.md** : ajouter une note en tête (« chaque prompt-noyau matérialisé est augmenté de la charte agent-charter.md ») pour que la règle soit visible à la source.

### 3. « Walk in knowing » pour les agents
Le hook SessionStart ne tire pas pour les subagents → c'est **la charte** qui fait recall le domaine en premier (autonome, marche même hors atelier). Pas de seed injecté par l'orchestrateur (YAGNI : la charte suffit, et l'auto-recall marche pour tout agent, atelier ou non).

### 4. Garde-fou anti-bruit (la leçon appliquée)
- Charte : « durable/raisonnement only, jamais de bavardage ».
- `memory_store`/`store_in` déduplique déjà les quasi-doublons (dedup).
- **Branche dédiée par domaine** = tu vois dans le cockpit (arbre des rubriques) exactement ce que chaque agent a écrit, et tu peux **élaguer une branche entière** si un projet dérape. C'est ce qui rend l'écriture directe sûre.
- Provenance `[<slug>]` = audit fin (quel agent a produit quelle mémoire).

## Plus-values ajoutées (jugées utiles, non gold-plating)
- **Provenance** `[<slug>]` sur chaque écriture → auditabilité du cerveau multi-agents.
- **Recall transverse** : les agents rappellent aussi les décisions partagées du projet, pas seulement leur silo → coordination réelle par la mémoire (la mémoire institutionnelle qui MARCHE).
- **Charte de première classe** : fichier autonome référencé, pas gravé dans atelier — réutilisable par toute skill/agent futur (audit, level-up, agents écrits à la main).

## Ce qu'on ne fait PAS (YAGNI)
Pas de daemon par agent · pas de staging/PR de mémoire (discipline + branche auditable suffisent) · pas de seed orchestrateur (charte auto-recall) · pas d'inclusion des subagents SDD.

## Vérification (honnête : prose/skill, pas de Python testable)
1. **Statique** : la charte existe, est bien référencée par atelier §3 + roles.md ; un agent généré (dry-run) contient charte + tools anamnese bornés + sa branche.
2. **End-to-end dry-run** : lancer `/atelier` sur un mini-projet jetable → un agent recall/store bien dans sa branche `projets/<projet>/<domaine>`, la provenance `[<slug>]` est présente, le cockpit (arbre des rubriques) montre la branche qui se remplit, et **rien hors branche** (audit : `SELECT ... WHERE content LIKE '[%]' ` et vérif des rubriques touchées).
3. **Review adversariale de la charte** (prose) : est-elle assez STRICTE sur l'anti-bruit ? les tools bornés excluent-ils bien les mutations lourdes ? la discipline objectif/subjectif est-elle claire ? pas de contradiction avec le protocole CLAUDE.md principal ?

## Honnêtetés
- Aucun code Python testable unitairement : le livrable est de la prose (charte) + édition de skill (atelier). La confiance vient du dry-run end-to-end + la review adversariale, pas de pytest.
- Les agents ne « walk in knowing » que s'ils appellent effectivement `memory_recall` (dépend de leur obéissance à la charte, comme moi au protocole) — c'est un déclencheur soft, assumé ; la branche auditable permet de vérifier a posteriori ce qui a été fait.
- `~/.claude` n'est pas versionné → traçabilité par le rapport (comme les edits CLAUDE.md). Le paquet public exhaustif intégrera la charte dans `templates/skills/atelier/` au prochain refresh.
