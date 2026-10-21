# Micro-pilote SWE-bench — mode d'emploi (container-free, à la main d'Ahmed)

Pipeline construit + testé (10 tests verts, 0 dépense). Isolation des bras **prouvée** au go/no-go
(marker test) : bras A = `~/.claude/CLAUDE.md` caché (Claude Code nu), bras B = CLAUDE.md présent
(notre protocole). **Zéro Docker** : le notateur `grade_local.py` clone + venv + pytest.

## 0. Prérequis (léger — pas de Docker)
```bash
cd ~/Desktop/anamnese
.venv/bin/pip install datasets    # charge le dataset SWE-bench-Lite depuis HuggingFace
# (git + pytest déjà là ; chaque tâche crée son propre venv jetable)
```

## 1. GO/NO-GO — smoke sur 1 tâche (défaut, dépense minime)
```bash
cd ~/Desktop/anamnese
.venv/bin/python -m eval.agent.run_pilot
```
Déroulé automatique :
1. choisit ~8 tâches (repos légers flask/requests/pytest/pylint/sphinx) ;
2. **sanity oracle** sur la 1re : applique le gold_patch → doit être `resolved` (VALIDE le notateur ; sinon STOP dur, rien dépensé) ;
3. lance les 2 bras sur cette 1 tâche (isolation auto : A cache CLAUDE.md, B non — restauré même si crash) ;
4. note + sort un scorecard.

**Note le temps affiché** (`[A] … : Ns`, `[B] … : Ns`) → extrapole ×16 (8 tâches × 2 bras) pour estimer le coût du full.

## 2. Décision (barrière budget = toi)
Coût observé × 16 tient dans ton forfait ? → GO. Sinon → réduis N.

## 3. Full — les N tâches (SEULEMENT après ton GO)
```bash
.venv/bin/python -m eval.agent.run_pilot full
```
Sort `eval/agent/scorecard_agent.json` : taux A vs B, `gains_B` (notre plus-value), `regressions_B`, coût des 2 bras.

## Ce qui peut coincer (et ce que ça veut dire)
- **Sanity oracle échoue** (gold_patch pas `resolved`) → le notateur maison ne colle pas à ce repo (mauvaise version de dep, patch qui n'applique pas). C'est le filet : on ne croit AUCUN chiffre tant que le gold ne passe pas. Colle-moi la sortie, j'ajuste `grade_local.py`.
- **Bras A dit qu'il a un protocole Anamnèse** → le hide/restore n'a pas marché (CLAUDE.md pas au chemin attendu). On vérifie `~/.claude/CLAUDE.md`.
- **`claude -p` très lent / timeout** → cap `--max-turns` déjà à 40 ; on baisse si besoin.

## Honnêtetés (déjà dans le scorecard)
- N=8 → **directionnel**, pas comparable-SOTA ni statistiquement significatif.
- Mesure la **discipline de vérification** (protocole CLAUDE.md), PAS la mémoire (inerte sur repos étrangers) ni l'orchestration.
- Notateur container-free = plus léger mais moins blindé que le Docker officiel ; le **sanity oracle par tâche** est ce qui rend le chiffre digne de confiance.
- Pendant le run du bras A, ton `~/.claude/CLAUDE.md` est momentanément déplacé (restauré aussitôt) → ne lance pas d'autre Claude Code en parallèle pendant l'éval.
