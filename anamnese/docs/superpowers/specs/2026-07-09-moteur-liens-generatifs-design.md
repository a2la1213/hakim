# Moteur de liens génératifs (synthèse abductive)

> **Statut :** design validé (brainstorming 2026-07-09). Nouvelle capacité pour Anamnèse
> (~/Desktop/anamnese). N'altère pas l'ablation ni les portes existantes.

**Goal :** Faire évoluer la mémoire d'**associative** (liens hebbiens de co-occurrence, qui ne
portent qu'un poids) vers **abductive** : générer des **hypothèses/solutions NEUVES** nées de la
**combinaison de souvenirs distants** — l'arête porte désormais un SENS. Exemple : mém. A (physique :
0/1 en alternance/rotation) + mém. B (interactions intermoléculaires imparfaites) → insight : *rendre
l'interaction parfaite via ces 0/1 en mouvement*.

**Exigence fondatrice :** tourne en **LOCAL** (Ollama qwen 9B, always-on, 100% gratuit/offline) —
Claude n'est JAMAIS requis. Le cœur est du **code agnostique au modèle** ; l'intelligence vit dans
l'**orchestration** (sélection-code + filtrage adversarial en meute), pas dans le modèle. On compense
un 9B faible par la **quantité + le crible** (gratuit en local).

**Architecture :** un cœur partagé `synthesis.py` avec 3 étages qui swappent le backend de
génération/vérification : **Local** (daemon 9B, batch large, gratuit), **Claude Code** (top des
paires, qualité, budget), et l'**output** (surfaçage + rétroaction) commun à tous. Deux couches de
liens coexistent : `coactivation` (associatif hebbien, inchangé) et `insight_edges` (abductif, nouveau).

**Tech Stack :** Python 3.14 (.venv), SQLite, numpy (sélection/scores), `engine.chat` (Ollama local),
`claude -p` (backend Claude optionnel), `embeddings.embed` (256-dim), cockpit Node (`/api/insights`).

## Global Constraints

- **Offline à 100%** : le cœur (local) ne dépend JAMAIS de Claude/réseau. Claude = escalade optionnelle.
- **Cœur agnostique au modèle** : `synthesis.run(...)` prend un `chat_fn(prompt)->str` injectable (9B local OU `claude -p`) — même pipeline.
- **La porte de vérification est le crux** : sans crible adversarial, un 9B produit du slop. Anti-slop = étape non-négociable.
- **Ne PAS casser** : l'ablation (dream_ablation, portes A/B/C), le rêve ON/twin, la coactivation existante, les portes 2026-07-03.
- **Kill-switch** : `ANAMNESE_SYNTHESIS=0` désactive la passe (défaut 1).
- **Seuils pré-enregistrés** : mid-distance 0.35–0.60, batch local 20, 3 échantillons/paire, 5 sceptiques / majorité 3 réfutent = mort, top-5 Claude, plancher d'ancrage 0.30, nouveauté min 0.15.
- **Deux couches de liens** : `coactivation` (poids, associatif) INCHANGÉE ; `insight_edges` (typée, abductive) NOUVELLE.
- **Zéro `claude -p` pendant le build** (le backend Claude est testé via `chat_fn` mockée).

## Modèle de données

- **Insight** = un épisode `role="insight"`, contenu `"(insight·<backend>) <hypothèse> [test: <comment tester>]"` (le backend `local`/`claude` est un **préfixe du contenu** — zéro colonne meta à ajouter), `importance` = f(score de valeur), avec embedding.
- **Table `insight_edges`** (nouvelle, via migration) : `insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id)`. L'arête pointe de l'hypothèse vers **chaque souvenir source**. C'est le lien génératif (il SIGNIFIE : « cet insight est né de ces mémoires »).
- **Pas de table meta séparée** : le `backend` vit dans le préfixe du contenu ; l'`importance` porte le score de valeur ; la `nouveauté` est **recalculée à la lecture** (distance aux autres souvenirs) pour le classement cockpit. On garde le schéma minimal (juste `insight_edges` en plus).
- **Récursif** : un insight est un souvenir substantiel → il peut redevenir source d'un futur insight (le cerveau apprend à penser sur ses propres pensées).

## Composants

### 1. `synthesis.py` — le cœur agnostique (PUR + orchestration)
Fonctions PURES (TDD) :
- `grounding_ok(insight_emb, emb_a, emb_b, floor) -> bool` : cosinus(insight, A) ≥ floor ET cosinus(insight, B) ≥ floor (ancrage EMBEDDING, pas lexical — une vraie synthèse reformule).
- `novelty(insight_emb, existing_embs) -> float` : `1 − max cosinus(insight, existants)` ∈ [0,1].
- `parse_hypothesis(out) -> str|None` : extrait l'hypothèse, `None` si sortie = `NONE`/vide/charabia.
- `parse_verdict(out) -> "REFUTE"|"VALIDE"|None` : lit un vote sceptique.
- `majority_kill(votes, n_refute_kill) -> bool` : vrai si ≥ n_refute_kill votes `REFUTE`.
- `fertility_score(cos, cross_rubric, coact_weight) -> float` : pic à mi-distance, bonus inter-rubriques, malus si déjà co-activé.

Orchestration (chat_fn injectable, DB) :
- `select_fertile_pairs(mem, n, lo, hi) -> list[(id_a, id_b, fertility)]` : sur les souvenirs substantiels embeddés, garde les paires à cosinus ∈ [lo,hi], rubriques de tête ≠, coactivation faible/absente ; rangées par `fertility_score`.
- `generate(chat_fn, a_text, b_text, n_samples) -> list[str]` : prompt abductif, `n_samples` générations, retourne les hypothèses non-`NONE`.
- `verify(chat_fn, hypothesis, a_text, b_text, n_skeptics) -> (kept: bool, n_refute: int)` : `n_skeptics` passes « réfute ceci », `majority_kill`.
- `store_insight(mem, hypothesis, source_ids, meta) -> insight_id` : ajoute l'épisode `role="insight"` + les `insight_edges` + **booste la coactivation entre les sources** (rétroaction).
- `run(mem, chat_fn, backend, n_pairs, ...) -> list[insight_id]` : pipeline complet (sélection → génération → ancrage-code → vérification → score nouveauté → seuil → store). Best-effort : ne casse jamais l'appelant.

### 2. Migration `insight_edges` (`migrations.py`)
Ajoute la table (idempotente, legacy-safe) + index `idx_insight_src ON insight_edges(source_id)`. Suit le pattern coactivation existant.

### 3. Étage LOCAL — hook daemon (`daemon.py`)
Dans le cycle de sommeil (après le rêve REM, sous `config.SYNTH_ENABLED` + Ollama up) :
`synthesis.run(mem, local_chat, "local", n_pairs=config.SYNTH_LOCAL_BATCH)` où
`local_chat = lambda p: eng.chat([{"role":"user","content":p}], stream=False, think=False)`.
Best-effort (un échec ne bloque pas le rêve). Gratuit, always-on.

### 4. Étage CLAUDE — `synthesis_claude.py` (budget, main d'Ahmed / consolidate)
`claude_chat = lambda p: subprocess claude -p "<p>" --model sonnet` (sortie texte). Puis
`synthesis.run(mem, claude_chat, "claude", n_pairs=config.SYNTH_CLAUDE_TOPN, n_samples=1, n_skeptics=2)`
sur le **top des paires par fertilité** (Claude = juge fort, moins d'échantillons). Lancé à la main
ou depuis consolidate. Testé avec `chat_fn` mockée (zéro claude réel au build).

### 5. Config (`config.py`)
`SYNTHESIS_ENABLED` (env `ANAMNESE_SYNTHESIS`, défaut on), `SYNTH_MID_LO=0.35`, `SYNTH_MID_HI=0.60`,
`SYNTH_LOCAL_BATCH=20`, `SYNTH_CLAUDE_TOPN=5`, `SYNTH_SAMPLES=3`, `SYNTH_SKEPTICS=5`,
`SYNTH_REFUTE_KILL=3`, `SYNTH_GROUNDING_FLOOR=0.30`, `SYNTH_NOVELTY_MIN=0.15`, `SYNTH_COACT_BOOST`.

### 6. Cockpit — panneau 💡 Insights (`~/AIOS/cockpit`)
Endpoint `/api/insights` (server.js, lecture seule sqlite) : jointure `episodes role='insight'` ×
`insight_edges` × sources → liste `{insight, sources[], score, backend, ts}`, récents/top d'abord.
Page/panneau `public/` : l'hypothèse + les sources cliquables (vers le détail mémoire) + score + badge backend.

## Flux de données
Daemon nocturne (gratuit) : rêve → **synthèse locale** (20 paires : génère 9B ×3, ancre, réfute ×5,
score, stocke les survivants + booste coactivation sources). → Ahmed/budget : `synthesis_claude` sur
le top-5. → Cockpit `/api/insights` : les insights avec leurs sources + score.

## Ce qui n'est PAS modifié
- `coactivation` (couche associative), le rêve ON/twin, l'ablation (portes A/B/C), les portes 2026-07-03.

## Stratégie de test (TDD sur le PUR ; zéro `claude -p` au build)
- PUR : `grounding_ok`, `novelty`, `parse_hypothesis`, `parse_verdict`, `majority_kill`, `fertility_score` (cas connus).
- Orchestration : `generate`/`verify`/`run` avec `chat_fn` **mockée** (déterministe) — vérifier : NONE écarté, hypothèse non-ancrée écartée (grounding), majorité-réfute tue, seuil nouveauté filtre, `store_insight` crée l'épisode + les `insight_edges` + booste la coactivation (spy).
- `select_fertile_pairs` : sur `tmp_db` seedée (embeddings synthétiques) → ne garde que mi-distance + inter-rubriques + faible-coactivation.
- Migration `insight_edges` : idempotence + legacy-safe.
- `synthesis_claude` : construction du prompt + parsing testés `chat_fn` mockée, PAS de claude réel.

## Honnêteté / limites
- Un 9B, même criblé, produit des insights plus modestes que Claude : **moteur de sérendipité** — sur ~20 paires/nuit, il en jettera la plupart (le crible marche) et en gardera **quelques-unes** vraiment neuves. C'est le rendement (les pépites qui passent), pas la qualité par-tentative.
- Risque résiduel : ponts forcés qui passent le crible (faux positifs). Mitigé par ancrage-embedding + majorité-5 + nouveauté ; jamais nul → les insights sont **des hypothèses à considérer, pas des vérités** (label honnête, comme « rêve »).
- Sélection par proxy (embedding mi-distance) : heuristique du « possible adjacent », pas prouvée optimale — ajustable via les seuils gravés.
