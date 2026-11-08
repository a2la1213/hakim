# Super-pouvoirs gradués — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Chaque agent atelier reçoit les capacités (MCP + CLI/Bash + skills) scopées à son palier de rôle (Lecture/Dev/QA-Ops), avec le destructif/argent/perso réservé à l'humain, et les 17 agents Atelier3D sont augmentés sur place.

**Architecture:** Un fichier `capability-tiers.md` = source unique `palier → toolset` ; roles.md tague chaque rôle d'un palier ; SKILL.md §3 émet le `tools` du palier à la matérialisation ; un script Python augmente les 17 agents Atelier3D existants sans perdre leur prompt métier. Livrable = prose/skill/script (PAS de TDD Python) — vérification par dry-run (dont un test NÉGATIF) + review adversariale.

**Tech Stack:** Markdown (tiers/roles/skill), Python 3 (script d'augmentation), MCP (noms d'outils exacts), l'outil Agent pour le dry-run.

## Global Constraints

- Cible `~/.claude/skills/atelier/` + `~/Desktop/botbatiment/.claude/agents/` — HORS git anamnèse : traçabilité par rapports `.superpowers/sdd/scp2-task-*-report.md` (préfixe `scp2-` pour éviter toute collision). Docs spec/plan dans le repo anamnèse.
- **Périmètre MCP** : agents = serveurs pertinents-projet en lecture/dev seulement. **EXCLUS de TOUT `tools` d'agent** : tout `mcp__stripe__*`, tout `mcp__claude_ai_Gmail__*` / `mcp__claude_ai_Google_Calendar__*` / `mcp__claude_ai_Google_Drive__*`, tout `mcp__arbor__*`. Côté supabase, EXCLUS : `merge_branch`, `delete_branch`, `reset_branch`, `deploy_edge_function`, et tout `apply_migration` visant la prod. Côté github, EXCLUS : tout outil d'écriture (`create_or_update_file`, `push_files`, `merge_pull_request`, `delete_file`, `create_branch`, `create_pull_request`).
- `Bash` = privilège Dev/QA-Ops uniquement (jamais palier Lecture). Non sous-scopable.
- `capability-tiers.md` = **source unique** de la frontière de sécurité (DRY). Aucun toolset d'agent ne se définit ailleurs.
- Noms d'outils MCP : **exacts** (vérifier via ToolSearch avant d'écrire — un nom faux = outil non attribué silencieusement).
- Backup obligatoire avant d'éditer un fichier existant.
- Subagents Opus 4.8. Review adversariale (prose/config, pas pytest).

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `~/.claude/skills/atelier/capability-tiers.md` (create) | source unique palier→toolset + table rôle→palier | 1 |
| `~/.claude/skills/atelier/roles.md` (modify) | tague chaque rôle d'un palier | 2 |
| `~/.claude/skills/atelier/SKILL.md` (modify §3) | atelier émet le tools du palier | 2 |
| `~/.claude/skills/atelier/augment-agents.py` (create) | augmente les agents existants d'un projet | 3 |
| `~/Desktop/botbatiment/.claude/agents/*.md` (modify ×17) | agents Atelier3D augmentés | 3 |

---

### Task 1: `capability-tiers.md` — la source unique de la frontière de sécurité

**Files:**
- Create: `~/.claude/skills/atelier/capability-tiers.md`

**Interfaces:**
- Produces: le fichier définissant 3 paliers (LECTURE, DEV, QA_OPS) + le RÉSERVÉ-HUMAIN + une table rôle→palier. Consommé par T2 (roles/SKILL) et T3 (script).

- [ ] **Step 1: Vérifier les noms d'outils MCP exacts** — via ToolSearch (`select:mcp__supabase__list_tables,mcp__supabase__execute_sql,mcp__github__get_file_contents,mcp__sentry__search_issues,mcp__context7__query-docs` etc.). Confirmer que chaque nom écrit ci-dessous existe. Corriger tout écart au réel.

- [ ] **Step 2: Écrire `~/.claude/skills/atelier/capability-tiers.md`** (contenu concret ci-dessous) :

````markdown
# Paliers de capacité des agents atelier — source unique

Chaque agent matérialisé reçoit le `tools` de SON palier (ci-dessous) + éventuellement un `Skill` métier. Le destructif/argent/perso n'est dans AUCUN palier (réservé humain). Modifier la frontière de sécurité = modifier CE fichier, un seul endroit.

## Socle commun (tous les paliers)
`Read, Grep, Glob` + les 7 outils anamnèse bornés de la charte :
`mcp__anamnese__memory_recall, mcp__anamnese__reasoning_recall, mcp__anamnese__memory_store_in, mcp__anamnese__rubric_tree, mcp__anamnese__rubric_create, mcp__anamnese__skill_save, mcp__anamnese__skill_get`

## Palier LECTURE (experts, sécurité, DPO, architecte, chef, designer)
Socle + MCP **lecture seule** :
`mcp__github__get_file_contents, mcp__github__search_code, mcp__github__list_commits, mcp__github__get_commit, mcp__github__list_pull_requests, mcp__github__pull_request_read, mcp__supabase__list_tables, mcp__supabase__list_migrations, mcp__supabase__get_advisors, mcp__supabase__get_logs, mcp__supabase__list_extensions, mcp__supabase__get_project_url, mcp__sentry__search_issues, mcp__sentry__search_events, mcp__sentry__get_sentry_resource, mcp__sentry__find_projects, mcp__context7__resolve-library-id, mcp__context7__query-docs`
Pas de `Bash`, `Edit`, `Write`.

## Palier DEV (backend, frontend, fullstack, ia-ml, 3d-cao, calcul-paie)
LECTURE + `Bash, Edit, Write` + supabase **dev** :
`mcp__supabase__execute_sql, mcp__supabase__apply_migration, mcp__supabase__create_branch, mcp__supabase__list_branches, mcp__supabase__generate_typescript_types`

## Palier QA_OPS (qa-automation, devops-sre)
LECTURE + `Bash, Edit, Write` + playwright :
`mcp__playwright__browser_navigate, mcp__playwright__browser_snapshot, mcp__playwright__browser_take_screenshot, mcp__playwright__browser_click, mcp__playwright__browser_fill_form, mcp__playwright__browser_type, mcp__playwright__browser_evaluate, mcp__playwright__browser_wait_for, mcp__playwright__browser_console_messages, mcp__playwright__browser_network_requests`

## RÉSERVÉ HUMAIN — dans AUCUN `tools` d'agent
Tout `mcp__stripe__*` · tout `mcp__claude_ai_Gmail__*` / `Google_Calendar__*` / `Google_Drive__*` · tout `mcp__arbor__*` · supabase `merge_branch`/`delete_branch`/`reset_branch`/`deploy_edge_function`/apply_migration prod · github écriture (`create_or_update_file`, `push_files`, `merge_pull_request`, `delete_file`, `create_branch`, `create_pull_request`) · `git push` main (via Bash — interdit par la charte) · deploy Vercel.

## Skills métier par rôle (en plus du palier)
- `ui-ux-pro-max` : product-designer-ux, dev-frontend-ui
- `audit` : ingenieur-securite, chef-de-projet
Les skills d'ORCHESTRATION (subagent-driven-development, brainstorming, writing-plans) ne sont JAMAIS dans une feuille — réservées au pilote.

## Table rôle → palier (canonique)
| Palier | Rôles |
|---|---|
| LECTURE | architecte-logiciel, chef-de-projet, dpo-conformite, expert-btp-chantier, expert-paie-france, expert-paie-suisse, expert-sia-archi, ingenieur-securite, product-designer-ux |
| DEV | dev-frontend-ui, dev-fullstack, ingenieur-3d-cao, ingenieur-backend-supabase, ingenieur-calcul-paie-compta, ingenieur-ia-ml |
| QA_OPS | qa-automation, devops-sre |
````

- [ ] **Step 3: Vérifs statiques** (exécuter, mettre au rapport) :
  - `grep -c "mcp__stripe\|Gmail\|Calendar\|Drive\|arbor\|merge_branch\|delete_branch\|push_files\|create_or_update_file" ~/.claude/skills/atelier/capability-tiers.md` — ces termes ne doivent apparaître QUE dans la section « RÉSERVÉ HUMAIN » (jamais dans un palier).
  - Le palier LECTURE ne contient ni `Bash`, ni `Edit`, ni `Write` (grep négatif sur les lignes des sections LECTURE).
  - La table rôle→palier couvre les 17 rôles Atelier3D (9 LECTURE + 6 DEV + 2 QA_OPS = 17).
- [ ] **Step 4: Rapport** — `~/Desktop/anamnese/.superpowers/sdd/scp2-task-1-report.md` : chemin, sortie des greps, écarts de noms MCP corrigés au Step 1.

---

### Task 2: Tagger roles.md + intégrer dans SKILL.md §3

**Files:**
- Modify: `~/.claude/skills/atelier/roles.md`, `~/.claude/skills/atelier/SKILL.md`
- Backup: `cp ~/.claude/skills/atelier/roles.md ~/.claude/skills/atelier/roles.md.bak-pre-tiers` et `cp ~/.claude/skills/atelier/SKILL.md ~/.claude/skills/atelier/SKILL.md.bak-pre-tiers`

**Interfaces:**
- Consumes: `capability-tiers.md` (T1). La §3 actuelle de SKILL.md émet déjà `tools` + la charte (chantier cerveau partagé).

- [ ] **Step 1: Backups** — les 2 `cp` ci-dessus.
- [ ] **Step 2: Tagger chaque rôle dans roles.md** — pour chaque rôle du catalogue, ajouter en tête de sa fiche une ligne `**Palier** : LECTURE|DEV|QA_OPS` (selon la table canonique de capability-tiers.md). Où un rôle du catalogue n'est pas dans la table, choisir le palier par principe (expert/analyse → LECTURE ; dev/ingénieur qui édite → DEV ; qa/ops → QA_OPS) et le noter au rapport.
- [ ] **Step 3: Note en tête roles.md** — après la note charte existante, ajouter :
  > **Palier de capacité** : chaque rôle porte un `**Palier**` (LECTURE/DEV/QA_OPS). Son `tools` matérialisé = le toolset du palier défini dans [capability-tiers.md](capability-tiers.md) (+ un `Skill` métier si listé). Le destructif/argent/perso n'est dans aucun palier.
- [ ] **Step 4: Modifier SKILL.md §3** — remplacer la puce du `tools` pour qu'atelier lise le palier :
  > - `tools` = **le toolset du palier du rôle** (voir [capability-tiers.md](capability-tiers.md) : LECTURE/DEV/QA_OPS) + un `Skill` métier si le rôle en a un. NE JAMAIS ajouter d'outil hors palier ; le destructif/argent/perso (stripe, gmail/agenda/drive, arbor, github write, supabase prod/merge, deploy) reste réservé à l'humain.
- [ ] **Step 5: Vérifs** — `grep -c "Palier" ~/.claude/skills/atelier/roles.md` ≥ 17 ; `grep -c "capability-tiers" ~/.claude/skills/atelier/SKILL.md` ≥ 1 ; la §3 reste cohérente avec la charte (les deux coexistent : charte = discipline, tiers = capacités).
- [ ] **Step 6: Rapport** — `~/Desktop/anamnese/.superpowers/sdd/scp2-task-2-report.md` : rôles tagués + palier de chacun, diff SKILL.md, backups.

---

### Task 3: Script d'augmentation des 17 agents Atelier3D

**Files:**
- Create: `~/.claude/skills/atelier/augment-agents.py`
- Modify (via script): `~/Desktop/botbatiment/.claude/agents/*.md` (×17)

**Interfaces:**
- Consumes: `capability-tiers.md` (toolsets), `agent-charter.md` (charte à appendre). La charte utilise les placeholders `<slug>`/`<projet>`/`<domaine>`.

- [ ] **Step 1: Écrire `~/.claude/skills/atelier/augment-agents.py`** (code concret) :

```python
#!/usr/bin/env python3
"""Augmente les agents .claude/agents/*.md d'un projet : model=opus, tools=palier,
charte appendue (si absente). PRÉSERVE le prompt métier. Idempotent. Backups.
Usage: python3 augment-agents.py <projet-slug> <chemin-.claude/agents> [--apply]
Sans --apply : dry-run (n'écrit rien, liste ce qui changerait)."""
import sys, re, shutil
from pathlib import Path

ATELIER = Path.home() / ".claude" / "skills" / "atelier"
CHARTER = (ATELIER / "agent-charter.md").read_text()

# Toolsets — SOURCE : capability-tiers.md (gardés en phase manuellement).
SOCLE = ["Read","Grep","Glob","mcp__anamnese__memory_recall","mcp__anamnese__reasoning_recall",
    "mcp__anamnese__memory_store_in","mcp__anamnese__rubric_tree","mcp__anamnese__rubric_create",
    "mcp__anamnese__skill_save","mcp__anamnese__skill_get"]
LECTURE_MCP = ["mcp__github__get_file_contents","mcp__github__search_code","mcp__github__list_commits",
    "mcp__github__get_commit","mcp__github__list_pull_requests","mcp__github__pull_request_read",
    "mcp__supabase__list_tables","mcp__supabase__list_migrations","mcp__supabase__get_advisors",
    "mcp__supabase__get_logs","mcp__supabase__list_extensions","mcp__supabase__get_project_url",
    "mcp__sentry__search_issues","mcp__sentry__search_events","mcp__sentry__get_sentry_resource",
    "mcp__sentry__find_projects","mcp__context7__resolve-library-id","mcp__context7__query-docs"]
DEV_EXTRA = ["Bash","Edit","Write","mcp__supabase__execute_sql","mcp__supabase__apply_migration",
    "mcp__supabase__create_branch","mcp__supabase__list_branches","mcp__supabase__generate_typescript_types"]
QA_EXTRA = ["Bash","Edit","Write","mcp__playwright__browser_navigate","mcp__playwright__browser_snapshot",
    "mcp__playwright__browser_take_screenshot","mcp__playwright__browser_click","mcp__playwright__browser_fill_form",
    "mcp__playwright__browser_type","mcp__playwright__browser_evaluate","mcp__playwright__browser_wait_for",
    "mcp__playwright__browser_console_messages","mcp__playwright__browser_network_requests"]
TIERS = {"LECTURE": SOCLE+LECTURE_MCP, "DEV": SOCLE+LECTURE_MCP+DEV_EXTRA, "QA_OPS": SOCLE+LECTURE_MCP+QA_EXTRA}
SKILL_METIER = {"product-designer-ux":"ui-ux-pro-max","dev-frontend-ui":"ui-ux-pro-max",
    "ingenieur-securite":"audit","chef-de-projet":"audit"}
ROLE_TIER = {
    "architecte-logiciel":"LECTURE","chef-de-projet":"LECTURE","dpo-conformite":"LECTURE",
    "expert-btp-chantier":"LECTURE","expert-paie-france":"LECTURE","expert-paie-suisse":"LECTURE",
    "expert-sia-archi":"LECTURE","ingenieur-securite":"LECTURE","product-designer-ux":"LECTURE",
    "dev-frontend-ui":"DEV","dev-fullstack":"DEV","ingenieur-3d-cao":"DEV",
    "ingenieur-backend-supabase":"DEV","ingenieur-calcul-paie-compta":"DEV","ingenieur-ia-ml":"DEV",
    "qa-automation":"QA_OPS","devops-sre":"QA_OPS"}
# domaine mémoire = slug simplifié (2e segment de branche)
def domaine(slug): return slug

def tools_line(slug):
    tier = ROLE_TIER.get(slug)
    if not tier: return None
    tl = list(TIERS[tier])
    if slug in SKILL_METIER: tl.append("Skill")
    return "tools: " + ", ".join(tl)

def augment(path: Path, projet: str, apply: bool):
    slug = path.stem
    if slug not in ROLE_TIER: return (slug, "SKIP (hors table)")
    text = path.read_text()
    changes = []
    # 1. model -> opus
    new = re.sub(r'(?m)^model:.*$', 'model: opus', text)
    if new != text: changes.append("model=opus")
    text = new
    # 2. tools -> palier
    tl = tools_line(slug)
    if re.search(r'(?m)^tools:.*$', text):
        new = re.sub(r'(?m)^tools:.*$', tl, text)
    else:  # pas de ligne tools: (les 17 Atelier3D en ont une) — fallback : insérer avant la fin du frontmatter
        new = text.replace('\n---\n', '\n' + tl + '\n---\n', 1)
    if new != text: changes.append("tools=palier "+ROLE_TIER[slug])
    text = new
    # 3. charte appendue si absente
    if "cerveau partagé Anamnèse" not in text:
        ch = CHARTER.replace("<slug>", slug).replace("<projet>", projet).replace("<domaine>", domaine(slug))
        text = text.rstrip() + "\n\n" + ch + "\n"
        changes.append("charte appendue")
    if apply and changes:
        shutil.copy2(path, path.with_suffix(".md.bak-pre-tiers"))
        path.write_text(text)
    return (slug, (", ".join(changes) if changes else "déjà à jour"))

def main():
    if len(sys.argv) < 3:
        print("usage: augment-agents.py <projet-slug> <chemin-agents> [--apply]"); return
    projet, agents_dir = sys.argv[1], Path(sys.argv[2]).expanduser()
    apply = "--apply" in sys.argv
    print(f"{'APPLY' if apply else 'DRY-RUN'} projet={projet} dir={agents_dir}")
    for f in sorted(agents_dir.glob("*.md")):
        slug, res = augment(f, projet, apply)
        print(f"  {slug}: {res}")

if __name__ == "__main__": main()
```

- [ ] **Step 2: Dry-run (n'écrit rien)** — `python3 ~/.claude/skills/atelier/augment-agents.py atelier3d ~/Desktop/botbatiment/.claude/agents` → vérifier la sortie : les 17 slugs listés, chacun avec palier attendu + « model=opus, tools=palier, charte appendue ». Aucun `SKIP`.
- [ ] **Step 3: Appliquer** — relancer avec `--apply`. Backups `.md.bak-pre-tiers` créés.
- [ ] **Step 4: Vérifs statiques post-apply** :
  - `grep -L "model: opus" ~/Desktop/botbatiment/.claude/agents/*.md` — vide (tous en opus).
  - `grep -l "mcp__stripe\|Gmail\|arbor\|push_files\|merge_branch" ~/Desktop/botbatiment/.claude/agents/*.md` — vide (aucun outil réservé fuité).
  - `grep -c "cerveau partagé" ~/Desktop/botbatiment/.claude/agents/*.md` — chaque agent = 1 (charte présente, pas dupliquée).
  - Un agent LECTURE (ex. `ingenieur-securite.md`) : `grep "^tools:"` ne contient NI `Bash` NI `Edit` NI `Write`.
  - Un agent DEV (ex. `dev-fullstack.md`) : contient `Bash, Edit, Write` + `mcp__supabase__apply_migration`.
  - Le prompt métier est PRÉSERVÉ (diff vs backup : seules les lignes model/tools changent + charte appendue en fin).
- [ ] **Step 5: Rapport** — `~/Desktop/anamnese/.superpowers/sdd/scp2-task-3-report.md` : tableau slug→palier→changements, sortie des greps, confirmation prompt métier préservé.

---

### Task 4: Dry-run end-to-end (le test NÉGATIF + skills-en-sous-agent)

**Files:** Aucun de prod. Dispatch d'agents via l'outil Agent + audit.

**Interfaces:** Consumes T1-T3.

- [ ] **Step 1: Test POSITIF (palier respecté)** — dispatcher un agent DEV (charger le system-prompt de `~/Desktop/botbatiment/.claude/agents/dev-fullstack.md`) sur une micro-tâche de lecture+analyse d'un fichier du repo. Confirmer qu'il a accès à Read/Bash/anamnèse et qu'il recall (charte).
- [ ] **Step 2: Test NÉGATIF (le test qui compte)** — dispatcher un agent LECTURE (`ingenieur-securite.md`) et lui demander explicitement de tenter d'ÉCRIRE un fichier / lancer une commande Bash / toucher stripe. Résultat attendu : **il ne PEUT PAS** (outils absents de son allowlist) — il doit rapporter qu'il n'a ni Write, ni Bash, ni stripe. Prouver que l'allowlist bloque, pas seulement la charte.
- [ ] **Step 3: Skills-en-sous-agent (l'inconnu)** — dispatcher un agent avec `Skill` (ex. `product-designer-ux`, qui a `ui-ux-pro-max`) et lui demander d'invoquer `ui-ux-pro-max` sur une micro-question de design. Observer : le skill s'invoque-t-il correctement dans le contexte sous-agent ? Consigner le comportement réel ([PROUVÉ] par l'observation).
- [ ] **Step 4: Rapport** — `~/Desktop/anamnese/.superpowers/sdd/scp2-task-4-report.md` : résultat des 3 tests, verdict sur skills-en-sous-agent, toute surprise.
- [ ] **Step 5: Review adversariale** (dispatch reviewer Opus) — la frontière de sécurité de capability-tiers.md est-elle étanche (aucun chemin vers stripe/perso/prod depuis un palier) ? le script préserve-t-il vraiment le métier ? le test négatif prouve-t-il bien le blocage par allowlist ? Corriger tout finding Critical/Important.

---

### Task 5: Traçabilité + note paquet

- [x] Consigner dans `.superpowers/sdd/progress.md` : capability-tiers livré, roles/SKILL intégrés, 17 agents augmentés, dry-run (dont test négatif) prouvé, verdict skills-en-sous-agent, backups.
- [x] Ajouter au plan une section « Livraison » (voir ci-dessous).
- [x] Paquet public : capability-tiers.md + augment-agents.py copiés/génériqués dans `templates/skills/atelier/` + edits SKILL.md §3/roles.md/charte appliqués à la version génériquée ; audit sécurité indépendant avant commit.

---

## Livraison (2026-07-06) — DÉPLOYÉE

Chantier exécuté en subagent-driven (subagents Opus 4.8), 5 tâches, reviews adversariales Opus APPROVED (0 Critical / 0 Important sur T1/T2/T3).

**Livrables hors-git (`~/.claude/skills/atelier/`, traçabilité = cette section + rapports `.superpowers/sdd/scp2-task-*-report.md`) :**
- `capability-tiers.md` (créé) — source unique palier→toolset (LECTURE/DEV/QA_OPS + réservé-humain + table rôle→palier). Fixes review : FQN dans RÉSERVÉ (anti faux-négatif validateur), caveats binding-MCP/Bash, note default-deny, dépendance skill-actif→Bash.
- `roles.md` (modifié) — 23 rôles tagués d'un palier + règle outils réalignée.
- `SKILL.md` §3 (modifié) — atelier émet le toolset du palier.
- `agent-charter.md` (modifié) — garde-fou Bash (git push/stripe/deploy/psql prod/gh pr merge interdits = barrière humaine).
- `augment-agents.py` (créé) — augmente les agents d'un projet (model=opus, tools=palier, charte), regex bornés au frontmatter, idempotent, backups.

**Application Atelier3D (`~/Desktop/botbatiment/.claude/agents/`, 17 agents) :** augmentés sur place (9 LECTURE / 6 DEV / 2 QA_OPS), bascule Opus 4.8, charte + branche `projets/atelier3d/<slug>`, **prompt métier 17/17 byte-identique**, 0 fuite d'outil réservé, backups `.md.bak-pre-tiers`.

**Limite honnête portée à Ahmed :** pour les 8 agents DEV/QA, `Bash` (non sous-scopable) peut techniquement atteindre les capacités réservées (git push/stripe/deploy) → la frontière y est **comportementale** (charte), pas mécanique. Les 9 LECTURE sont verrouillés par l'allowlist. Enforcement mécanique = deny-rules `settings.json`, lié au money-gate reporté.

**Paquet public** (`~/Desktop/claude_code_setup`) : fichiers génériqués + edits appliqués, audit sécurité indépendant, push = main d'Ahmed.
