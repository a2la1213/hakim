# Régime du bruit daemon — design

- **Date** : 2026-07-06
- **Statut** : design validé par Ahmed (exclusion = reflection + outreach ; rétention = aucune ; option one-shot de blanchiment des embeddings existants à sa main).
- **Cible** : `~/Desktop/anamnese/` (memory.py, daemon.py, config.py, tests).

## Problème (grounded)

Le daemon écrit une pensée toutes les 30 min : **52 % de la base** = 503 `reflection` + 400 `outreach` (1742 épisodes, 12,7 Mo). Deux défauts vérifiés :
1. **Correction** : `memory_recall` appelle `retrieve` SANS `kinds` ; l'exclusion des rôles daemon ne se déclenche que `if kinds` → le bavardage du daemon (importance 0.4, parfois barré) **concurrence le savoir durable pour le top-6**.
2. **Efficience** : ces épisodes sont embeddés (4,8 Mo, ~36 Mo/an) alors qu'ils ne sont **jamais rappelés** ni utilisés par le labo des rêves (qui les lit par leur TEXTE, pas leur embedding — `DREAM_CONSOLIDATABLE` les lit ; `DREAM_MENU_ROLES` les EXCLUT).
La consolidation nocturne distille déjà le durable des reflections en `semantic` → le raw est redondant.

## Décisions

1. **Rappel** : exclure `reflection` + `outreach` par défaut. GARDER recallables : `thought`, `dream`, `reasoning`, `semantic`, `episodic`, `reference`.
2. **Écriture** : le daemon n'embedde plus reflection/outreach (embedding vide). Effet de bord assumé : ils deviennent orphelins (hors taxonomie) = journal chronologique.
3. **Rétention** : AUCUNE suppression — flux de métacognition gardé pour toujours.
4. **One-shot** (déclenché par Ahmed, pas automatique) : blanchir les embeddings des reflection/outreach déjà en base pour récupérer les 4,8 Mo.

## Architecture

### 1. `memory.py::retrieve` — exclusion par défaut
Nouveau paramètre `exclude_roles=config.RECALL_EXCLUDE_ROLES` (défaut `("reflection", "outreach")`).
Dans la boucle de candidats (là où `if kinds and role not in kinds: continue`), ajouter :
`if exclude_roles and role in exclude_roles: continue` — sauf si l'appelant a passé un `kinds` positif qui, lui, prime (un `kinds=["reflection"]` explicite doit ramener des reflections : l'exclusion ne s'applique QUE quand le rôle n'est pas explicitement demandé). Règle : `exclude_roles` filtre uniquement les rôles NON listés dans `kinds`. Simplement : si `kinds` est fourni, il gouverne (exclude ignoré, car kinds est déjà un filtre positif restrictif) ; si `kinds` est None, `exclude_roles` retire les rôles daemon.
- Config : `RECALL_EXCLUDE_ROLES = ("reflection", "outreach")`.
- Rétro-compatible : les appels avec `kinds` (le rêve `kinds=["semantic"]`, `reasoning_recall kinds=["reasoning"]`) sont inchangés. Les appels sans kinds (memory_recall, cli recall) gagnent l'exclusion.

### 2. `daemon.py` — ne plus embedder reflection/outreach
- `reflect()` : `mem.add("reflection", out[:600], importance=0.4, embedding=[])` (au lieu de `embeddings.embed(...)`).
- L'outreach : `mem.add("outreach", ..., importance=0.5, embedding=[])`.
- Vérifs de non-régression (déjà sur TEXTE, donc intactes) : la de-echo (`salience.lexical_overlap` sur `content`), l'anti-spam outreach (idem). Le rêve lit `content`. Le dashboard lit `content`.
- `memory.add` avec `embedding=[]` : déjà géré (extract_facets try/except, routing route_episode sur embedding vide → route_by_centroid retourne None → orphelin ; update_centroid no-op sur vide). Aucun crash.

### 3. Garantie de sûreté (orphelins = OK)
- `orphans_report` et `taxonomy.orphan_clusters` filtrent `role IN ('semantic','episodic','reference','reasoning')` → reflection/outreach orphelins sont **invisibles** au jardinage nocturne. Prouvé par test.
- Effet cosmétique : le `COUNT WHERE rubric_id IS NULL` grimpe (journal hors taxonomie) — sans conséquence (aucune UI proéminente ne l'affiche ; orphans_report est role-filtré).

### 4. One-shot (script, déclenché manuellement)
`scripts/blanch_daemon_embeddings.py` : `UPDATE episodes SET embedding='[]' WHERE role IN ('reflection','outreach') AND embedding != '[]'` sur `data/memory.db`, avec backup préalable (checkpoint WAL) + compte des lignes touchées. NE tourne PAS tout seul (Ahmed le lance). Récupère les 4,8 Mo actuels. (Ne touche pas rubric_id — les 903 existants gardent leur rangement ; seuls les nouveaux naissent orphelins. Cohérence assumée : mix transitoire, sans impact fonctionnel puisque tous sont exclus du rappel.)

## Tests (TDD, DB temp migrée, jamais data/memory.db)
1. `retrieve` sans kinds : une reflection très pertinente + un semantic → le semantic sort, la reflection est ABSENTE. Un outreach idem.
2. `retrieve(kinds=["reflection"])` explicite → ramène bien la reflection (l'exclusion ne prime pas sur un kinds positif).
3. `retrieve(kinds=["semantic"])` (chemin du rêve) → inchangé.
4. daemon reflect : monkeypatch, l'épisode reflection créé a `embedding == '[]'` (ou vide), pas d'embed appelé ; de-echo (2e pensée quasi-identique) toujours sautée.
5. reflection non-embeddée → orpheline (rubric_id NULL), ABSENTE de orphans_report (rôle filtré), ABSENTE du recall par défaut.
6. Non-régression full suite (≥ 403).

## Honnêtetés
- Les 903 existants gardent leur rubric_id (rangés) tant que le one-shot ne blanchit que l'embedding ; les nouveaux naissent orphelins. Mix transitoire, sans effet fonctionnel (tous exclus du rappel).
- Pas de rétention = la base grandit d'un journal de texte (~600 o × 48/j ≈ 10 Mo/an de texte sans embedding) — assumé, c'est le journal de pensée voulu.
- L'exclusion de rappel s'applique AUSSI aux 903 déjà là (c'est un filtre au rappel, pas une propriété d'écriture) → le gain de correction est immédiat, dès le déploiement.
