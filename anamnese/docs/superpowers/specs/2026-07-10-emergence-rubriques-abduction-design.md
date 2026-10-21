# Émergence de rubriques depuis l'abduction

> **Statut :** design validé (brainstorming 2026-07-10). Extension du moteur de liens
> génératifs (synthesis). N'altère pas le routage LIVE, la coactivation, l'ablation, les portes 2026-07-03.

**Goal :** Faire que le cerveau **invente de nouvelles catégories** à partir de ses propres
synthèses : quand un **cluster d'insights** abductifs forme un thème neuf qu'**aucune rubrique
existante ne couvre**, créer une nouvelle rubrique (Claude, gardée) et y ranger ces insights.
La croissance est **délibérée** (principe d'Ahmed : « grandir, mais ne pas créer un nœud proche
d'un existant »).

**Architecture :** module `rubric_emergence.py` (fonctions PURES + orchestration `emerge(mem, chat_fn)`),
branché dans `synthesis_claude.run_claude` **après** la génération des insights → piloté par
l'abduction, jugement **Claude uniquement**. Garde-code anti-redondance (distance aux centroïdes
des rubriques existantes). Visibilité cockpit : endpoint `/api/emerged` + panneau `🌱`.

**Tech Stack :** Python 3.14 (.venv), SQLite, numpy (clusters/centroïdes), `claude -p` (backend, mocké au build), `embeddings`, cockpit Node.

## Global Constraints

- **Claude UNIQUEMENT crée des rubriques** : `emerge` est appelée depuis `synthesis_claude` (jamais depuis la passe locale 9B). Le 9B génère des insights mais ne crée pas de catégories (jugement délicat).
- **Garde anti-redondance non-négociable** : un cluster dont le centroïde est trop proche d'une rubrique existante (cosinus ≥ plancher) → PAS de création (on route vers l'existante). Principe « pas de nœud proche d'un existant ».
- **Réversible** : `rubric_create` taggue `kind_hint="emerged"` ; `taxonomy_undo` existe.
- **Ne PAS casser** : le routage LIVE (`mem.add` → `route_episode`), la coactivation, l'ablation (portes A/B/C), le moteur de synthèse (`synthesis.run`), les portes 2026-07-03.
- **Kill-switch** : `config.RUBRIC_EMERGE_ENABLED` (env `ANAMNESE_RUBRIC_EMERGE`, défaut on).
- **Seuils gravés** : `RUBRIC_EMERGE_MIN_INSIGHTS=3` (taille min du cluster), `RUBRIC_EMERGE_SIM=0.50` (tightness du cluster, cosinus), `RUBRIC_EMERGE_REDUNDANCY_FLOOR=0.60` (couvert par existante si cosinus centroïde ≥ ça).
- **Zéro `claude -p` au build** : `emerge` testée `chat_fn` mockée.
- **Parent obligatoire** : `rubric_create` refuse un path dont le parent n'existe pas → `emerge` ne propose que des paths sous un parent existant (ou un root connu).

## Composants

### 1. `rubric_emergence.py` — PUR (TDD)
- `_cos(a, b)`, `_centroid(embs) -> list[float]` (moyenne).
- `_cluster(items, min_size, sim) -> list[list[int]]` : `items=[(insight_id, emb)]`, clustering glouton par cosinus ≥ `sim`, garde les clusters de taille ≥ `min_size`. Déterministe (ordre par id).
- `covered(cluster_centroid, rubric_centroids, floor) -> bool` : True si le centroïde du cluster est à cosinus ≥ `floor` d'AU MOINS un centroïde de rubrique existante (→ déjà couvert, pas de création). **Garde sémantique.**
- `valid_path(path, existing_paths) -> bool` : **Garde structurelle.** (a) path **NEUF** (PAS déjà dans `existing_paths` — on ne crée que du neuf) ; (b) contient au moins un `/` et son PARENT (préfixe avant le dernier `/`) est dans `existing_paths` — **l'émergence niche TOUJOURS sous une rubrique existante, jamais un nouveau root** (croissance délibérée, pas de nouvelle taxonomie de tête) ; (c) tous les segments kebab-case `^[a-z0-9-]+$`, pas de `/` en tête/fin ; (d) profondeur ≤ `config.RUBRIC_MAX_DEPTH`.
- `parse_path(out) -> str|None` : extrait le path proposé (1re ligne kebab-case `a/b-c`), `None` si `NONE`/vide/invalide.

### 2. Orchestration `emerge(mem, chat_fn) -> list[str]`
1. Charger les insights récents (`role='insight'`) avec embedding, PAS déjà dans une rubrique `kind_hint='emerged'` (évite de re-traiter). 
2. `_cluster` → clusters ≥ `MIN_INSIGHTS`.
3. Charger les centroïdes des rubriques existantes (colonne `centroid`).
4. Pour chaque cluster : `_centroid` ; **garde sémantique** — si `covered(centroïde, rubric_centroids, REDUNDANCY_FLOOR)` → skip (le thème est déjà couvert, les insights restent routés vers l'existant) ; sinon `propose_path(chat_fn, textes_insights, paths_existants)` → **garde structurelle** — si `parse_path` non-None ET `valid_path(path, existing_paths)` (neuf + parent existant + kebab-case + profondeur) → `rubrics.rubric_create(conn, path, now, kind_hint='emerged')` + `rubrics.attach_episode` de chaque insight du cluster. 
5. Best-effort (try/except par cluster). Retourne les paths créés.

`propose_path(chat_fn, insight_texts, existing_paths)` : prompt Claude *« Voici N insights liés :\n… Ces insights forment-ils un thème NEUF non couvert par ces rubriques existantes : … ? Si oui, propose UN path kebab-case court sous le bon parent existant (ex. projets/xxx, savoir/yyy). Sinon réponds NONE. »* → `parse_path`.

### 3. Hook Claude — `synthesis_claude.run_claude`
Après `synthesis.run(...)` (génération des insights), appeler `rubric_emergence.emerge(mem, chat)` (best-effort). Le daemon (`_synthesis_claude_pass`) et le lancement manuel déclenchent donc l'émergence, toujours **Claude**. La passe locale 9B (`_synthesis_pass`) ne l'appelle PAS.

### 4. Config (`config.py`)
`RUBRIC_EMERGE_ENABLED` (env `ANAMNESE_RUBRIC_EMERGE`, défaut on), `RUBRIC_EMERGE_MIN_INSIGHTS=3`, `RUBRIC_EMERGE_SIM=0.50`, `RUBRIC_EMERGE_REDUNDANCY_FLOOR=0.60`.

### 5. Cockpit — visibilité `🌱` (`~/AIOS/cockpit`)
- Endpoint `GET /api/emerged` (sqlite -readonly) : rubriques `kind_hint='emerged'` + nb d'insights rattachés + un extrait → `{emerged:[{path, label, n_insights, sample}]}`.
- Panneau `🌱 RUBRIQUES ÉMERGÉES` dans le labo des rêves : le path + combien d'insights l'ont enfantée. Avec le panneau `💡` existant, Ahmed voit la **chaîne complète** : souvenirs → insight → nouvelle rubrique.

## Flux de données
Rêve/synthèse Claude → insights créés → `emerge` : clusters d'insights → cluster non-couvert → Claude nomme → garde anti-redondance → `rubric_create(kind_hint='emerged')` + rattache les insights. → Cockpit `/api/emerged` : les rubriques nées de l'abduction.

## Ce qui n'est PAS modifié
- Le routage LIVE (`mem.add`), la coactivation, l'ablation (A/B/C), `synthesis.run`, les portes 2026-07-03. La passe locale 9B (pas de création de rubrique).

## Stratégie de test (TDD sur le PUR ; zéro `claude -p` au build)
- PUR : `_cos`, `_centroid`, `_cluster` (min_size + tightness), `covered` (couvert vs neuf), `valid_path` (kebab-case + parent existe + profondeur), `parse_path` (path vs NONE).
- Orchestration `emerge` : `tmp_db` seedée (insights + embeddings + rubriques avec centroïdes) + `chat_fn` mockée → un cluster neuf crée une rubrique `kind_hint='emerged'` + rattache les insights ; un cluster couvert par une rubrique existante NE crée RIEN ; un cluster < min → rien.
- `run_claude` : appelle `emerge` après `synthesis.run` (mocké, zéro claude réel).
- Cockpit : `node --check` + curl `/api/emerged`.

## Honnêteté / limites
- Le nommage dépend de Claude (jugement variable) ; la garde-code (redondance + parent existant + kebab-case) borne les dégâts, mais un nom imparfait reste possible → `taxonomy_undo` + supervision Ahmed.
- Clusters par proxy embedding + seuils heuristiques → ajustables (gravés). N petit d'insights au début → peu d'émergences (normal ; ça grandit avec le corpus d'insights).
