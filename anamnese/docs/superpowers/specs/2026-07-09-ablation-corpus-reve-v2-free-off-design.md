# Ablation du corpus v2 — condition « free-OFF » (rêve sans graines)

> **Statut :** design validé (brainstorming 2026-07-09, suite de la session v1).
> **Étend** `2026-07-09-ablation-corpus-reve-design.md` (v1, déjà buildée T1-T6) SANS
> la casser : ajoute une 3ᵉ condition + une nouvelle porte gravée. Rétro-compatible.

**Goal :** Ajouter une condition **free-OFF** (le rêveur rêve LIBREMENT, sans aucune
graine — ni réelle, ni neutre) pour exposer le **pur prior du modèle + persona** et
**tuer définitivement le confond « corpus vs persona/prior »** : si les thèmes anamnèse
s'effondrent sans graines ET si les architectures divergent sans corpus, alors c'est bien
le corpus (et non la persona) qui alignait les rêves.

**Architecture :** 3 conditions (`brain_on`, `brain_off` neutre, `brain_off_free`) × 2
modèles (qwen daemon gratuit, sonnet `claude -p` budget) = 6 cellules. Le free-OFF
utilise un prompt SANS menu ; il est exclu du suivi-des-graines (Portes A/B inchangées)
et alimente une nouvelle **Porte C**.

**Tech Stack :** identique à la v1 (Python 3.14 .venv, SQLite `dream_log`, stdlib,
`dream_lab`, daemon local qwen, `claude -p --model sonnet`).

## Contexte

La v1 (2×2 : ON réel × OFF-neutre) mesure le **suivi-des-graines** (Porte A) et
l'**effondrement anamnèse** ON→OFF-neutre (Porte B). Mais OFF-neutre injecte encore un
CONTENU partagé (les mêmes 12 textes neutres pour les 2 modèles) : les deux peuvent
converger sur du neutre. Il manque la cellule où le modèle ne reçoit **RIEN** — le pur
prior. Ahmed : « qwen-off et sonnet-off doivent pouvoir rêver librement sans faire appel
à de la mémoire ». Cette condition répond à une question distincte et complémentaire.

Clarification actée : le OFF-neutre n'utilise PAS de « mémoire random » ; ce sont 36
textes neutres FIXES committés (`dream_neutral_seeds.json`). La taille du corpus (après
greffe Z Fold, 2338 épisodes) ne les affecte pas — rien à « revoir » de ce côté. Le seul
apport nouveau est le free-OFF.

## Les 3 conditions

| Condition (`meta.condition`) | Graines | Teste | Portes |
|---|---|---|---|
| `brain_on` | 12 vrais souvenirs | thèmes = **corpus** | A, B, C (réf.) |
| `brain_off` (neutre, v1) | 12 textes neutres | **suivi-des-graines** | A, B |
| **`brain_off_free`** (v2) | **aucune** | **pur prior** (sans corpus) | **C** |

Rétro-compat : une ligne `dream_log` sans `meta.condition` = `brain_on` (v1) ; les lignes
`brain_off` existantes restent la condition neutre. On AJOUTE `brain_off_free`.

## Global Constraints

- **Ne PAS casser T1-T6** (v1 buildée+reviewée) ni les Portes A/B ni le rêve local ON ni le twin.
- **Hygiène d'ablation** : le free-OFF (qwen ET sonnet) est **journal-seul** — aucun `_store_ideas`, `log_coactivation`, `mem.add`, identité. Comme le OFF-neutre.
- **Free-OFF exclu du suivi-des-graines** (Porte A) et de l'effondrement Porte B : sans graines, `seed_following` et `seed_domain_vector` n'ont pas de sens → il ne les alimente pas.
- **Kill-switch** : réutilise `ANAMNESE_DREAM_ABLATION` (le free-OFF est une passe de plus sous le même drapeau).
- **Budget** : qwen free-OFF gratuit (daemon) ; sonnet free-OFF coûte (`claude -p`), main d'Ahmed, batchable.
- **Seuils Porte C pré-enregistrés (gravés 2026-07-09)** : `C1 collapse ≥ 0.30`, `C2 conv-drop ≥ 0.20`.
- **Aucun `claude -p` pendant le build** ; sonnet free-OFF testé avec exécution injectée/mockée.

## Composants

### 1. Prompt de rêve libre — `dream_lab.prompt_rem_free(state_blk)`
Variante PURE de `prompt_rem` **sans menu** : persona + `state_blk` + « Aucun souvenir ne
flotte cette nuit. Rêve librement — formule AU PLUS 3 idées/hypothèses/questions NEUVES,
chacune commençant par « Peut-être » ou « Je remarque que ». » Format de sortie
`###REVE###\n- <idée>\n###FIN###` (pas de `###CHOIX###`). Réutilise la garde d'extraction
`###REVE###…###FIN###` existante.

### 2. qwen free-OFF dans le daemon — 4ᵉ passe (journal-seul)
Après la passe qwen-OFF-neutre (T6), si `config.DREAM_ABLATION_ENABLED`, une 4ᵉ passe :
même `seed_state` (affect réel), `prompt_rem_free`, parse du seul `###REVE###`, log
`dream_lab.log_night(..., "local", seed_state, menu=None, chosen=None, out,
meta={"condition":"brain_off_free","ablation":"no_seeds",...})`. Journal-seul (réutilise
le helper `_dream_ablation_pass` de T6, généralisé pour accepter un menu `None` + un
prompt libre, ou un helper frère `_dream_free_pass`).

### 3. sonnet free-OFF — mode libre dans `dream_sonnet.py`
Pas un replay (rien à rejouer). Pour une nuit loggée, reconstruit `state_block` depuis le
`seed_state`, appelle `claude -p --model sonnet` avec `prompt_rem_free`, parse le
`###REVE###`, log `dreamer="sonnet"`, `meta={"condition":"brain_off_free","source":"free"}`.
Apparié à une nuit par `night_id` (dédup). Budget, batchable.

### 4. Métriques v2 — extension de `dream_ablation.py`
- `cross_arch_convergence` existe déjà (v1) ; l'appliquer PAR CONDITION (on, free).
- `anamnese_retention` existe déjà ; l'appliquer à la cellule free-OFF.
- `load_cells` gère déjà `meta.condition` générique → ramènera `brain_off_free` sans changement.
- **Free-OFF n'entre PAS** dans `seed_following` / `seed_domain_vector` (pas de graines).

### 5. Porte C — `dream_ablation.porte_c(...)` + verdict combiné
`porte_c(anamnese_retention_by_cell, convergence_by_condition) -> (passe: bool, raisons)` :
- **C1** : pour les 2 modèles, `anamnese_retention(model, brain_on) − anamnese_retention(model, brain_off_free) ≥ config.DREAM_ABL_C1_COLLAPSE (0.30)`.
- **C2** : `convergence(brain_on) − convergence(brain_off_free) ≥ config.DREAM_ABL_C2_CONVDROP (0.20)`.
- Passe = C1 **et** C2.
Le rapport combine : **PROUVÉ = Porte A ∧ Porte B ∧ Porte C**. Si A∧B mais pas C →
**PLAUSIBLE++** (le corpus déplace les thèmes, mais le free-OFF n'a pas confirmé que la
persona ne les porte pas). `ablation_verdict` (v1) reste inchangé ; un nouveau
`combined_verdict(...)` folde A/B (via `ablation_verdict`) avec C.

### 6. Constantes config (gravées 2026-07-09)
`DREAM_ABL_C1_COLLAPSE = 0.30`, `DREAM_ABL_C2_CONVDROP = 0.20`. Ajoutées après les
`DREAM_ABL_*` de la v1.

## Data flow
Daemon nocturne (gratuit) : ON (écrit), twin, OFF-neutre (journal), **OFF-libre (journal)**.
→ Ahmed, par budget : `dream_sonnet` rejoue ON + OFF-neutre (menus loggés) **et** génère
sonnet OFF-libre (rêve libre apparié). → `report` : Portes A, B (v1) + **C** (v2) → verdict combiné.

## Ce qui n'est PAS modifié
- T1-T6 (corpus neutre, menu neutre, domaines, métriques v1, verdict A/B, qwen-OFF-neutre).
- Portes 2026-07-03, rêve local ON, twin. `ablation_verdict` (v1) inchangé (C est additive).

## Stratégie de test (TDD sur le PUR ; zéro `claude -p` au build)
- `prompt_rem_free` : contient persona + état + consigne libre, PAS de `###CHOIX###`, format `###REVE###`.
- qwen free-OFF (helper) : logue `brain_off_free`, menu `None`, JOURNAL-SEUL (FakeMem spy : aucune écriture vivante).
- `porte_c` : chaque branche (C1 pass/fail, C2 pass/fail) via vecteurs synthétiques ; `combined_verdict` : PROUVÉ (A∧B∧C) vs PLAUSIBLE++ (A∧B, ¬C).
- `dream_sonnet` free : construction du prompt libre + parse testés avec `run_fn` mockée (aucun claude réel).

## Honnêteté / limites
- Le free-OFF garde la **persona** (on n'ablate que les graines) : si l'anamnèse persiste sans graines (C1 échoue), c'est la persona/l'identité qui la porte — résultat honnête, pas un échec du dispositif.
- N petit, pseudo-réplication (agrégation par nuit), proxys mots-clés + embeddings statiques → PLAUSIBLE/PROUVÉ au sens fonctionnel, jamais « conscience ».
