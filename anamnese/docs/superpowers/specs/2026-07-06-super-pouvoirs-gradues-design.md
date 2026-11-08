# Super-pouvoirs gradués pour les agents atelier — design

- **Date** : 2026-07-06
- **Statut** : design validé par Ahmed (paliers gradués — PAS god-mode ; application aux 17 agents Atelier3D = augmentation sur place).
- **Cible** : `~/.claude/skills/atelier/` (charte, SKILL.md §3, roles.md, + nouveau `capability-tiers.md`) — hors git anamnèse, traçabilité par rapport. Application : `~/Desktop/botbatiment/.claude/agents/` (17 agents). Spec/plan versionnés dans le repo anamnèse.

## Objectif

Prolonger le cerveau partagé (livré ce jour) : chaque agent généré par `/atelier` reçoit, EN PLUS de la charte + mémoire bornée, les capacités (MCP + CLI/Bash + skills) **scopées à son palier de rôle**. Généraliser la réduction de privilège d'aujourd'hui (7 outils anamnèse bornés) à l'ensemble du toolset — sans jamais tomber dans le god-mode uniforme qui remettrait le trésor à portée de chaque agent.

## État actuel (vérifié)

- Les 17 agents Atelier3D datent d'avant le cerveau partagé : **0 ont la charte**, tous en `model: claude-fable-5` (à basculer Opus 4.8, décision Ahmed).
- Tools actuels hétérogènes : experts = `Read, Grep, Glob, Bash` ; devs = `+Edit, Write` ; designer = `+Skill` ; QA = `+playwright`. Notamment **les experts ont `Bash`** (un terminal = pouvoir de mutation) — le design le resserre.
- Serveurs MCP connectés à la session : anamnese, github, supabase, sentry, **stripe**, playwright, context7, **gmail, calendar, drive**, arbor.

## Décisions

1. **Périmètre MCP.** Les agents ne voient QUE les serveurs pertinents-projet en **lecture/dev**. **Exclus totalement du toolset de tout agent** : `gmail`/`calendar`/`drive` (compte Google perso d'Ahmed), `stripe` (argent → barrière humaine), `arbor` (infra). Un agent Atelier3D n'a aucune raison de toucher les mails/le compte bancaire.
2. **`Bash` = privilège Dev**, pas Lecture (un terminal peut muter/pousser). Les experts purs perdent `Bash`, gagnent le MCP-lecture (analyse sur données réelles) + la mémoire.
3. **Encodage DRY** : un fichier `capability-tiers.md` définit `palier → toolset` UNE fois ; roles.md **nomme** le palier de chaque rôle ; atelier émet le `tools` correspondant.
4. **Application Atelier3D** : augmentation **sur place** (script, backup) — préserve le prompt métier, ajoute charte + branche + palier + Opus 4.8.

## Architecture

### 1. `capability-tiers.md` (nouveau, source unique de la frontière de sécurité)

Définit 3 paliers + le réservé-humain. Toolsets (énumération de référence ; la liste exacte finale est dans le fichier) :

- **Palier LECTURE** — experts métier, sécurité, DPO, architecte, chef-de-projet, designer :
  `Read, Grep, Glob` + MCP **lecture seule** (`github` : get_file_contents/search_code/list_commits ; `supabase` : list_tables/list_migrations/get_advisors/get_logs ; `sentry` : search_issues/search_events/get_sentry_resource ; `context7`) + `Skill` (rôles qui en ont besoin) + les **7 outils anamnèse bornés** de la charte. **PAS de `Bash`, `Edit`, `Write`.**
- **Palier DEV** — backend, frontend, fullstack, ia-ml, 3D-cao, calcul-paie :
  LECTURE + `Bash`, `Edit`, `Write` + `supabase` **dev** (execute_sql, apply_migration, create_branch, generate_typescript_types). **JAMAIS** merge_branch/delete_branch/prod.
- **Palier QA/OPS** — qa-automation, devops-sre :
  LECTURE + `Bash`, `Edit`, `Write` + `playwright` (tous les browser_*) + `sentry` lecture. **0 deploy prod.**
- **RÉSERVÉ HUMAIN (dans aucun `tools` d'agent)** : `stripe` (tout), `supabase` apply_migration **prod**/merge_branch/delete_branch, `github` write/merge, `git push` main, deploy Vercel, gmail/calendar/drive/arbor.

Note `Bash` : non sous-scopable (tout-ou-rien). Donné aux paliers Dev/QA-Ops uniquement ; la charte interdit déjà le destructif (`git push` main, rm hors périmètre, deploy prod). Le vrai garde-fou reste que Lecture ne l'a pas du tout.

### 2. Mapping des 17 rôles Atelier3D → palier

| Palier | Rôles |
|---|---|
| LECTURE | architecte-logiciel, chef-de-projet, dpo-conformite, expert-btp-chantier, expert-paie-france, expert-paie-suisse, expert-sia-archi, ingenieur-securite, product-designer-ux (+Skill ui-ux-pro-max) |
| DEV | dev-frontend-ui (+Skill ui-ux-pro-max), dev-fullstack, ingenieur-3d-cao, ingenieur-backend-supabase, ingenieur-calcul-paie-compta, ingenieur-ia-ml |
| QA/OPS | qa-automation, devops-sre |

Resserrement notable : `ingenieur-securite` passe en LECTURE (auditeur = lecture seule, prouve les failles, ne les corrige pas) — perd `Bash` qu'il avait.

### 3. Skills scopés

Les skills d'**orchestration** (subagent-driven-development, brainstorming, writing-plans) restent au **pilote** — jamais dans une feuille (SDD-dans-SDD = imbrication interdite). Les feuilles reçoivent les skills **métier** : `ui-ux-pro-max` (designer, frontend), `audit` (sécurité, chef-de-projet). Comportement d'un skill invoqué DANS un sous-agent = **à prouver par dry-run** (inconnu à ce stade).

### 4. Intégration atelier (SKILL.md §3)

À la matérialisation, après le prompt-noyau + la charte : atelier **lit le palier du rôle** (dans roles.md) et **émet le `tools`** = toolset du palier (depuis capability-tiers.md) + les MCP/skills spécifiques éventuels du rôle. La charte (inchangée) continue de porter la discipline ; capability-tiers.md porte les capacités.

### 5. Script d'augmentation des 17 agents (`~/.claude/skills/atelier/augment-existing-agents.sh` ou équivalent)

Pour chaque `.claude/agents/<slug>.md` d'un projet donné : backup, puis (a) remplace `model:` par `opus`, (b) remplace la ligne `tools:` par le toolset du palier du rôle, (c) provisionne `projets/<projet>/<domaine>` (rubric_create), (d) appende la charte substituée si absente. **Préserve intégralement le prompt métier.** Idempotent (ne double pas la charte). Réversible (backups).

## Vérification (dry-run, comme le cerveau partagé)

1. **Statique** : un agent de chaque palier a EXACTEMENT le toolset de son palier — ni plus (pas de stripe/gmail/prod), ni moins. Les 17 Atelier3D ont charte + branche + Opus 4.8, prompt métier préservé (diff), backups présents.
2. **Négatif (le test qui compte)** : un agent LECTURE (ex. ingenieur-securite) dispatché ne PEUT PAS écrire/exécuter/déployer — il n'a physiquement ni `Bash`, ni `Edit`, ni `Write`, ni stripe. Prouver que l'allowlist bloque, pas juste la charte.
3. **Skills-en-sous-agent** : dispatcher un agent DEV avec `ui-ux-pro-max` sur une micro-tâche → prouver que le skill s'invoque et se comporte correctement dans le contexte sous-agent (le point inconnu).
4. **Review adversariale** (prose + config) : la frontière de sécurité est-elle étanche (aucun chemin vers stripe/perso/prod depuis un `tools` d'agent) ? capability-tiers.md est-il la source unique ? pas de contradiction charte/paliers.

## Ce qu'on ne fait PAS (YAGNI)
God-mode uniforme · MCP perso/argent dans les agents · skills d'orchestration dans les feuilles · sous-scoper Bash (impossible) · toucher le money-gate Atelier3D (reporté par Ahmed).

## Honnêtetés
- Livrable = prose (capability-tiers.md, charte, roles.md) + skill (SKILL.md) + un script d'augmentation. Confiance = dry-run (dont le test négatif) + review adversariale, pas pytest.
- `Bash` reste un pouvoir large pour Dev/QA (non sous-scopable) : la sûreté vient du fait que Lecture ne l'a pas, et que la charte + l'absence des tools prod/stripe ferment les chemins destructeurs. Assumé.
- Le comportement des skills en sous-agent est un **inconnu** tant que le dry-run n'a pas tranché — signalé, pas caché.
- `~/.claude` et `~/Desktop/botbatiment/.claude` hors traçabilité git-anamnèse → rapport + backups.
