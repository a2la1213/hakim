# Société à cerveau partagé — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Chaque agent expert généré par `/atelier` partage la mémoire Anamnèse (recall/store discipliné dans sa branche), suit la discipline de vérification, et laisse une provenance auditable — via une charte réutilisable injectée à la génération.

**Architecture:** Un fichier charte autonome (`agent-charter.md`) appendé au prompt-noyau de chaque agent ; `atelier/SKILL.md` l'injecte à la matérialisation, provisionne l'arbre de projet, et borne les tools anamnese des agents. Livrable = PROSE/SKILL (pas de Python) — vérification par revue adversariale + dry-run end-to-end, pas par pytest.

**Tech Stack:** Markdown (charte + skill), MCP anamnese (memory_recall/reasoning_recall/memory_store_in/rubric_tree/rubric_create/skill_save/skill_get), l'outil Agent/Workflow d'atelier. Spec : `docs/superpowers/specs/2026-07-06-societe-cerveau-partage-design.md`.

## Global Constraints

- Cible `~/.claude/skills/atelier/` — HORS git anamnese : traçabilité par rapport (comme les edits CLAUDE.md). Les docs spec/plan restent dans le repo anamnese.
- Tools anamnese des agents BORNÉS : `memory_recall`, `reasoning_recall`, `memory_store_in`, `rubric_tree`, `rubric_create`, `skill_save`, `skill_get`. JAMAIS `rubric_merge`/`rubric_reparent`/`taxonomy_undo`/`memory_reclassify` (mutations lourdes = orchestrateur/humain).
- Anti-bruit : la charte impose « durable/raisonnement only, jamais de bavardage » ; écriture UNIQUEMENT dans la branche `projets/<projet>/<domaine>` ; provenance `[<slug>]` sur chaque mémoire.
- Pas de daemon par agent · pas de seed orchestrateur (charte auto-recall) · pas d'inclusion des subagents SDD.
- Cohérence : la charte ne doit PAS contredire le protocole CLAUDE.md principal (elle en est le condensé pour agents).
- Backup avant édition d'un fichier atelier existant (`cp SKILL.md SKILL.md.bak-pre-charte`).

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `~/.claude/skills/atelier/agent-charter.md` (create) | la charte autonome réutilisable | 1 |
| `~/.claude/skills/atelier/SKILL.md` (modify §1/§3) | injecte la charte + provision arbre + tools bornés | 2 |
| `~/.claude/skills/atelier/roles.md` (modify, note en tête) | rend la règle visible à la source | 2 |
| `~/Desktop/anamnese/.superpowers/sdd/scp-*-report.md` | rapports (traçabilité hors-git) | 1-3 |

---

### Task 1: Écrire la charte `agent-charter.md`

**Files:**
- Create: `~/.claude/skills/atelier/agent-charter.md`

**Interfaces:**
- Produces: le fichier charte, appendé au prompt-noyau de chaque agent par la Task 2. Placeholders documentés : `<slug>` (slug de l'agent), `<projet>` (slug-projet), `<domaine>` (domaine de l'agent) — remplacés à la matérialisation.

- [ ] **Step 1: Écrire `~/.claude/skills/atelier/agent-charter.md`** (contenu VERBATIM ci-dessous ; c'est le condensé du protocole CLAUDE.md adapté aux agents) :

```markdown
# Charte d'agent — cerveau partagé Anamnèse

Tu n'es pas un expert jetable : tu es un membre d'une **société à mémoire partagée**.
Tu partages le cerveau Anamnèse (serveur MCP `anamnese`) avec les autres agents et
les sessions Claude Code. Applique cette charte EN PLUS de ton rôle.

## Repars en sachant (au DÉBUT de ta tâche)
- `mcp__anamnese__memory_recall` sur TON domaine **et** sur les décisions transverses
  du projet (`projets/<projet>` — pas seulement ton silo) : réutilise ce qui est déjà
  su, ne réinvente pas, ne contredis pas une décision prise.
- Avant un problème non-trivial, `mcp__anamnese__reasoning_recall` : rejoue la logique
  éprouvée plutôt que repartir de zéro.

## Contribue le DURABLE (à la FIN de ta tâche)
- Si — et seulement si — tu as produit du durable (une **décision + sa RAISON**, un
  **savoir métier stable**, une **procédure réutilisable**) : range-le dans TA branche
  via `mcp__anamnese__memory_store_in(content="[<slug>] <le fait, une phrase autonome
  au présent>", rubric_path="projets/<projet>/<domaine>", kind="semantic")`.
  Si la branche n'existe pas : `mcp__anamnese__rubric_create("projets/<projet>/<domaine>")`
  d'abord (vérifie l'arbre avec `mcp__anamnese__rubric_tree`).
- **Provenance** : préfixe TOUJOURS ce que tu écris de `[<slug>]` — le cerveau doit
  savoir quel agent a produit quoi (auditabilité).
- Logue ta **trace de raisonnement** sur un problème non-trivial :
  `memory_store_in(content="[<slug>] TRACE — <problème → étapes → décision → pourquoi>",
  rubric_path="projets/<projet>/<domaine>", kind="reasoning")`.
- Quand une réponse de l'utilisateur/orchestrateur DÉBLOQUE une procédure que tu ne
  savais pas faire : `mcp__anamnese__skill_save` (taggée par type de tâche).

## Discipline (la même que Claude Code)
- Avant de finaliser, **classe ton critère de succès** : objectif (une commande/un test
  le prouve → l'exécuter, montrer la sortie) ou subjectif (aucune mesure auto). Si
  subjectif : ne t'auto-note pas « fait » sur ton seul jugement — demande les critères.
- **Tente de te réfuter** (auto-critique adversariale) sur tout finding non-trivial
  avant de le livrer. Ancre avec un outil quand c'est possible plutôt qu'affirmer de
  mémoire.
- Distingue toujours **[PROUVÉ]** (testé/exécuté/ancré) de **[PLAUSIBLE]**.

## Garde-fous (anti-bruit — impératif)
- **Ne stocke QUE le durable** : jamais de bavardage, de statut, de process, de pensée
  éphémère. Une mémoire = un fait qui servira encore dans 3 mois.
- **N'écris QUE dans ta branche** `projets/<projet>/<domaine>`. Jamais ailleurs.
- **Jamais** de mutations lourdes de taxonomie (`rubric_merge`/`rubric_reparent`/
  `memory_reclassify`/`taxonomy_undo`) — c'est le territoire de l'orchestrateur/humain.
- PAS de daemon, PAS de tâche de fond : tu fais ta tâche, tu contribues le durable, tu
  t'arrêtes.
```

- [ ] **Step 2: Vérifier la cohérence** — relire `~/.claude/CLAUDE.md` (§ Pendant le travail, § Vérification, § Bibliothèque de raisonnement) et confirmer que la charte est un CONDENSÉ fidèle (pas de contradiction : mêmes règles objectif/subjectif, skill_save, prouvé/plausible, durable-only). Corriger toute divergence.
- [ ] **Step 3: Rapport** — écrire `~/Desktop/anamnese/.superpowers/sdd/scp-task-1-report.md` : chemin de la charte, points de cohérence avec CLAUDE.md, décisions de formulation.

---

### Task 2: Intégrer la charte dans atelier (SKILL.md + roles.md)

**Files:**
- Modify: `~/.claude/skills/atelier/SKILL.md` (§3 Matérialisation, §1 Cadrage), `~/.claude/skills/atelier/roles.md` (note en tête)
- Backup: `cp ~/.claude/skills/atelier/SKILL.md ~/.claude/skills/atelier/SKILL.md.bak-pre-charte`

**Interfaces:**
- Consumes: `agent-charter.md` (Task 1). La §3 actuelle : « Pour chaque rôle retenu, écris/MAJ `.claude/agents/<slug>.md` … frontmatter name/description/tools/model … puis le system-prompt expert tiré de roles.md, spécialisé au projet. »

- [ ] **Step 1: Backup** — `cp ~/.claude/skills/atelier/SKILL.md ~/.claude/skills/atelier/SKILL.md.bak-pre-charte`.

- [ ] **Step 2: §3 Matérialisation** — remplacer les puces existantes par (garde le sens, ajoute charte + tools + branche) :

```markdown
### 3. Matérialisation des agents
- Provisionne d'abord l'arbre du projet dans la taxonomie : `mcp__anamnese__rubric_create("projets/<slug-projet>")` puis une sous-rubrique par domaine d'agent (`projets/<slug-projet>/<domaine>`) — pour que chaque agent ait sa branche AVANT d'écrire.
- Pour chaque rôle retenu, écris/MAJ `.claude/agents/<slug>.md` dans le projet :
  - frontmatter `name`, `description`, `model` si pertinent, et `tools` = les tools minimaux du rôle (lecture seule experts/QA, édition devs) **+ les tools anamnese bornés** : `mcp__anamnese__memory_recall`, `mcp__anamnese__reasoning_recall`, `mcp__anamnese__memory_store_in`, `mcp__anamnese__rubric_tree`, `mcp__anamnese__rubric_create`, `mcp__anamnese__skill_save`, `mcp__anamnese__skill_get`. JAMAIS `rubric_merge`/`rubric_reparent`/`taxonomy_undo`/`memory_reclassify` (mutations lourdes = orchestrateur/humain).
  - le **system-prompt expert** tiré de roles.md, spécialisé au projet, **PUIS la charte** `agent-charter.md` appendée telle quelle, avec `<slug>`/`<projet>`/`<domaine>` substitués aux valeurs réelles de l'agent (son slug, le slug-projet, son domaine = sa branche).
- Ces fichiers sont réutilisables (Agent `subagent_type` / Workflow `agentType`). La charte les rend membres du cerveau partagé : ils recall au début, contribuent le durable dans LEUR branche à la fin, avec provenance `[<slug>]`.
```

- [ ] **Step 3: §1 Cadrage** (là où l'orchestrateur charge la mémoire) — ajouter une puce :
> - Note le **slug-projet** (kebab-case, ex. `botbatiment`) qui servira de racine de branche `projets/<slug-projet>` pour toute la mémoire de cette société d'agents.

- [ ] **Step 4: roles.md — note en tête** — après la ligne « Pour matérialiser un agent … » ajouter :
> **Toute matérialisation appende la charte `agent-charter.md`** (cerveau partagé Anamnèse : recall au début, contribution du durable dans la branche du domaine à la fin, discipline objectif/subjectif + auto-réfutation, provenance `[<slug>]`). Les prompts-noyaux ci-dessous n'ont donc PAS à répéter la mémoire ni la discipline.

- [ ] **Step 5: Vérifier** — `grep -c "agent-charter" ~/.claude/skills/atelier/SKILL.md` ≥ 1 ; les tools anamnese bornés listés ; aucune mention de merge/reparent dans les tools agents ; la §3 reste cohérente avec §4 (orchestration) et §5 (synthèse mémoire).
- [ ] **Step 6: Rapport** — append `~/Desktop/anamnese/.superpowers/sdd/scp-task-2-report.md` : diff résumé de SKILL.md/roles.md, confirmation des tools bornés.

---

### Task 3: Vérification end-to-end (dry-run atelier)

**Files:**
- Aucun fichier de prod modifié. Crée un mini-projet jetable sous `$TMPDIR/scp-dryrun/` et audite la mémoire.

**Interfaces:**
- Consumes: la charte (T1) + atelier intégré (T2).

- [ ] **Step 1: Mini-projet jetable** — créer `$TMPDIR/scp-dryrun/` avec un README trivial (« app de démo : une todo-list »). Ce sera le « projet » de la société d'agents.

- [ ] **Step 2: Générer UN agent à la main (simulacre de matérialisation atelier)** — écrire `$TMPDIR/scp-dryrun/.claude/agents/expert-demo.md` en suivant la §3 mise à jour : frontmatter avec les tools anamnese bornés, prompt-noyau trivial (« Tu es expert de la todo-list démo »), PUIS la charte appendée avec `<slug>=expert-demo`, `<projet>=scp-dryrun`, `<domaine>=demo`. But : prouver que la §3 produit un agent bien formé (charte présente, tools corrects).

- [ ] **Step 3: Dispatcher l'agent** via l'outil Agent (`subagent_type` pointant sur le .md, ou en collant son system-prompt) sur une tâche qui produit un DURABLE (ex. « décide et justifie le choix de stockage de la todo-list ; contribue la décision à ta branche »). Observer qu'il : (a) recall au début, (b) `rubric_create("projets/scp-dryrun/demo")` puis `memory_store_in` avec provenance `[expert-demo]`.

- [ ] **Step 4: Audit mémoire** (sur la VRAIE base — c'est un vrai write de l'agent, dans une branche jetable qu'on élaguera) :
```bash
sqlite3 -readonly ~/Desktop/anamnese/data/memory.db "SELECT r.path, e.content FROM episodes e JOIN rubrics r ON r.id=e.rubric_id WHERE r.path LIKE 'projets/scp-dryrun/%';"
```
Attendu : la mémoire est DANS `projets/scp-dryrun/demo`, préfixée `[expert-demo]`, et RIEN hors de cette branche (vérifier qu'aucune écriture n'a atterri ailleurs).
- [ ] **Step 5: Nettoyage** — élaguer la branche jetable pour ne pas polluer la vraie base : via MCP `rubric_reparent`/suppression n'existe pas → utiliser un DELETE ciblé documenté OU laisser et le noter (branche `projets/scp-dryrun` clairement jetable). Décision : DELETE ciblé des épisodes de la branche + la rubrique (script one-shot jetable, sur la vraie base, documenté au rapport). `rm -rf $TMPDIR/scp-dryrun`.
- [ ] **Step 6: Review adversariale de la charte** (prose) — dispatcher un reviewer : la charte est-elle assez STRICTE sur l'anti-bruit (durable-only, branche-only) ? les tools bornés excluent-ils bien merge/reparent ? contradiction avec CLAUDE.md ? un agent obéissant produit-il une mémoire propre et auditable (provenance) ? Corriger si finding.
- [ ] **Step 7: Rapport final** — `~/Desktop/anamnese/.superpowers/sdd/scp-task-3-report.md` : sortie de l'audit mémoire (preuve que l'agent écrit dans sa branche + provenance + rien hors branche), verdict de la review charte, confirmation du nettoyage.

---

### Task 4: Traçabilité + note paquet

- [x] Consigner dans `.superpowers/sdd/progress.md` : charte livrée, atelier intégré, dry-run prouvé, backups SKILL.md.
- [x] Committer les DOCS (spec/plan) dans le repo anamnese (les fichiers ~/.claude restent hors-git — c'est attendu).
- [x] Paquet public : charte intégrée (pas juste notée) — voir Livraison.

---

## Livraison (2026-07-06) — DÉPLOYÉE

Chantier exécuté en subagent-driven (subagents Opus 4.8), 3 tâches, chacune review-adversariale Opus APPROVED (0 Critical / 0 Important).

**Livrables hors-git (`~/.claude/skills/atelier/`, traçabilité = cette section + rapports `.superpowers/sdd/scp-task-*-report.md`) :**
- `agent-charter.md` (créé) — charte de cerveau partagé appendée à chaque agent généré.
- `SKILL.md` (modifié §1+§3) — provision de l'arbre `projets/<slug-projet>/<domaine>`, injection de la charte, `tools` anamnese bornés (7 outils, mutations lourdes exclues = réduction de privilège réelle par allowlist). Backup : `SKILL.md.bak-pre-charte`.
- `roles.md` (modifié) — note en tête : toute matérialisation appende la charte.

**Preuve end-to-end (dry-run, audit DB indépendant) :** un agent obéissant à la charte a recall (domaine + transverse) puis écrit 2 souvenirs `[expert-demo]` UNIQUEMENT dans `projets/scp-dryrun/demo` (0 fuite hors branche, 100 % provenance) ; base restaurée à l'identique (1748 épisodes) après nettoyage transactionnel.

**Paquet public exhaustif** (`~/Desktop/claude_code_setup`, commit `331f962`, en avance sur origin — **push = main d'Ahmed**) : charte + edits atelier intégrés dans `templates/skills/atelier/`, audit sécurité indépendant CLEAN (0 identifiant perso / 0 fingerprint métier / 0 secret réel ; arbre git prouvé propre par `ls-tree`).
