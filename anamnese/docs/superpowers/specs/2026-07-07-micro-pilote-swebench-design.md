# Micro-pilote SWE-bench-Lite dans le forfait — design

- **Date** : 2026-07-07
- **Statut** : design validé par Ahmed (instrument = SWE-bench-Lite réel ; déroulé = micro-pilote pour tenir dans le forfait Claude Code Max ~125 $ ; bras B = cœur discipline/vérification, PAS atelier/tournoi).
- **Cible** : nouveau dossier `~/Desktop/anamnese/eval/agent/` (à côté de l'éval mémoire existante). Spec/plan versionnés dans le repo anamnese.
- **But** : transformer l'axe faible « validation empirique » (30/100) en un **premier signal directionnel mesuré** — est-ce que notre échafaudage rend Claude Code meilleur en résolution de bugs réels ?

## Contrainte dure : le budget

Tout doit tenir dans le **forfait Claude Code Max (~125 $ / fenêtre d'usage)**. Les agents tournent **via l'abonnement** (usage-métré, PAS facture API séparée). Conséquence assumée : on n'achète **pas** le chiffre paper-grade sur 300 instances comparable au leaderboard SOTA — on achète un **micro-A/B directionnel** sur ~8–12 tâches réelles. C'est honnête et c'est ce qui débloque la mesure.

## Ce que ce pilote mesure VRAIMENT (honnêteté de périmètre)

Sur des repos SWE-bench **étrangers** (flask, sqlfluff…), notre **mémoire Anamnèse est inerte** : elle contient les projets d'Ahmed (Atelier3D/anamnese/Coran), rien sur ces repos → aucun recall pertinent. Donc le micro-pilote isole et teste la **discipline de vérification** de notre setup (protocole CLAUDE.md + systematic-debugging + TDD + auto-réfutation adversariale + prouvé/plausible), **pas** la mémoire ni l'orchestration lourde.
- **Mémoire** : sa valeur se prouve sur du travail RÉPÉTÉ dans le MÊME codebase (déjà mesurée en partie par `eval/longmemeval.py`) — hors périmètre ici.
- **Atelier/tournoi** : artillerie pour features multi-modules — inutile et hors-budget sur un patch mono-issue — un autre bench, plus tard.

## Architecture

### 1. Sélection des tâches — `eval/agent/select_tasks.py`
Choisit N (défaut 8, ≤12) instances de `princeton-nlp/SWE-bench_Lite`, stratifiées, filtrées sur des repos Python **légers** (Docker/deps modestes, pour tenir sur un M4 16 Go). Sort `eval/agent/tasks.jsonl` (instance_id, repo, base_commit, problem_statement, FAIL_TO_PASS, PASS_TO_PASS). Variante container-free (type SWE-MiniSandbox) documentée en fallback si le Docker 16 Go coince.

### 2. Deux bras — même modèle (Opus 4.8), mêmes tâches
- **A = baseline** : Claude Code headless (`claude -p`) SANS notre échafaudage — pas de CLAUDE.md perso, pas de MCP anamnese, pas de skills de discipline. Prompt minimal « résous cette issue ».
- **B = notre cœur** : Claude Code headless AVEC le protocole CLAUDE.md (vérification objectif/subjectif, auto-réfutation, prouvé/plausible) + les skills `systematic-debugging`/`test-driven-development`. (Anamnese branché mais noté inerte pour ces repos.)
- Chaque run : repo cloné au `base_commit`, l'agent bosse, on capture `git diff` → `model_patch`. Sortie `eval/agent/preds_{A,B}.jsonl` (instance_id, model_patch, model_name_or_path).

### 3. Notation — harnais SWE-bench officiel
`python -m swebench.harness.run_evaluation --dataset_name princeton-nlp/SWE-bench_Lite --predictions_path preds_X.jsonl --run_id …` en Docker, `max_workers` petit (≤ 4 sur M4). Produit le compte `resolved` par bras (FAIL_TO_PASS + PASS_TO_PASS verts).

### 4. Scorecard A/B — `eval/agent/report.py`
Agrège : taux de résolution A vs B, usage/temps par bras (proxy coût), et par instance un verdict (A✓B✓ / A✗B✓ = notre gain / A✓B✗ = notre régression / A✗B✗). Sort `eval/agent/scorecard_agent.json` + un résumé lisible. Rejouable après chaque optimisation future.

## Garde-fous budget (tenir dans ~125 $)
- N petit (démarrer à **8**), **séquentiel**, cap d'itérations par tâche (`--max-turns`).
- **Règle STOP** : suivre l'usage ; si une tâche part en boucle, la couper. Journaliser l'usage consommé pour extrapoler AVANT tout scale-up.
- Le harnais de notation (Docker, local) ne consomme PAS le forfait (compute local) — seul le bras agent le fait.

## Vérification (méta : on éprouve l'instrument lui-même)
1. **Pipeline end-to-end sur 1 tâche** d'abord : sélection → run A → run B → grading → scorecard, sur UNE instance triviale, pour prouver que la chaîne tient avant de dépenser sur 8.
2. **Oracle sanity** : appliquer le `gold_patch` de référence → le harnais doit le noter `resolved` (prouve que la notation est correcte).
3. **Isolation des bras** : vérifier que A n'a réellement PAS le CLAUDE.md/skills et B les a (sinon on ne mesure rien).
4. Résultat rapporté avec sa **bande d'incertitude** (N=8 → signal directionnel, pas significativité statistique).

## Honnêtetés
- N=8–12 = **directionnel**, pas comparable-SOTA ni statistiquement significatif. Assumé, c'est le prix du budget.
- **Confond coût/qualité** : le bras B (discipline) consomme plus d'usage/temps ; le scorecard DOIT rapporter les deux (B peut résoudre plus mais coûter plus — c'est une info, pas un échec).
- Sélection biaisée (repos légers, petit N) → non représentatif du full SWE-bench. Rapporté.
- Faisabilité infra réelle à valider (Docker sur M4 16 Go) : le Step 1 (pipeline sur 1 tâche) est le go/no-go avant de dépenser.
- Ce pilote mesure la **discipline**, pas la mémoire ni l'orchestration — ne pas surinterpréter le résultat comme « tout notre setup ».
