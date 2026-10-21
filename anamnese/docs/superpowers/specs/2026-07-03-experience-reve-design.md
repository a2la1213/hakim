# Expérience-rêve — préférences fonctionnelles émergentes : design

- **Date** : 2026-07-03
- **Statut** : design validé par Ahmed (approche 🅰 « labo à jumeau fantôme » + choix libre).
- **Cible** : `~/Desktop/anamnese/` (+ page cockpit `~/AIOS/cockpit`).

## Objectif

Transformer le rêve local (fonction `dream()` de `daemon.py`, débranchée depuis le
2026-06-23) en **expérience falsifiable** : Anamnèse exprime-t-elle des **préférences
fonctionnelles émergentes** quand elle rêve — un sur-choix stable, endogène (porté par
son état interne, pas par le prior du LLM), et causal (qui façonne sa mémoire future) ?

**Hypothèse nulle à battre** : « la tendance observée = le prior du modèle local
(qwen3.5 9B) + le prompt, pas une préférence d'Anamnèse. » Le design entier existe
pour rendre cette nulle mesurable chaque nuit.

**Label honnête** : « préférence fonctionnelle émergente ». Jamais « conscience »,
jamais « désir ». [PROUVÉ] vs [PLAUSIBLE] distingués partout.

## Décisions d'Ahmed

1. **Deux rêveurs en parallèle** : le 9B local (substrat expérimental contrôlé, prior
   figé, ablations gratuites) + Sonnet (consolidation nocturne existante, instrumentée
   en lecture seule) → contrôle croisé « même mémoire, même état, cerveaux différents ».
2. **Vivant dès la nuit 1** : pas de phase d'observation pure — la boucle causale
   (rêve → écriture mémoire → co-activation → rappel futur) tourne d'entrée. Le
   contrôle repose sur le jumeau fantôme, pas sur des nuits d'ablation.
3. **Choix libre** : le rêveur choisit lui-même **lesquelles** et **combien** de
   graines (0..12). « Aucune » est un choix légitime et loggé. L'appétit `k` devient
   une variable mesurée.
4. **Surface** : page cockpit `/dreams` + rapport CLI `anamnese dreams`.

## Architecture

```
                    NUIT (idle 1h30 — should_dream() inchangé)
                                  │
               ┌──────────────────┴──────────────────┐
               ▼                                      ▼
       RÊVE RÉEL (9B)                        JUMEAU FANTÔME (9B)
   état interne COMPLET                    même menu, même modèle,
 (9 neuromodulateurs, humeur,              état NEUTRALISÉ (baseline)
  compassion, focus WM)                               │
               │                                      │
     MENU de 12 graines  ◄────── partagé ──────►  même MENU
     → choisit librement (0..12)              → choisit librement
     → tisse ses idées REM                    → tisse ses idées
               │                                      │
               ▼                                      ▼
  ✍️ ÉCRIT en mémoire                       📓 dream_log SEULEMENT
(idées + co-activation LTP                (zéro trace dans le vivant)
 sur les graines CHOISIES)                            │
               └────────────► dream_log ◄─────────────┘
                                  ▲
                 Sonnet 4h30 ─────┘ (instrumenté en lecture)
```

### Division du travail (anti-redondance)

- **Sonnet = bibliothécaire** : consolidation des faits durables (NREM), inchangée.
- **9B = rêveur** : REM pur — menu, choix, recombinaison en idées. Il **ne distille
  plus de faits** (le `dream()` actuel en distille : cette partie est retirée).
  L'évolution d'identité bornée (`_maybe_update_self`, garde-fous inchangés) reste
  chez lui mais se nourrit désormais des **idées du rêve** (le REM) — le NREM local
  disparaissant, il n'y a plus de `faits` locaux pour l'alimenter.
- **Le cycle d'entretien nocturne revient avec le recâblage** : SHY
  (`synaptic_downscale`) + décay co-activation ne tournent plus depuis le débranchement
  du 2026-06-23 (à confirmer à l'implémentation : vérifier si `consolidate.py` les
  couvre ; sinon le recâblage répare ce trou).

### Table `dream_log` (migration via le pattern `migrations.py`)

```sql
CREATE TABLE dream_log (
  id         INTEGER PRIMARY KEY,
  ts         REAL NOT NULL,
  night_id   TEXT NOT NULL,      -- ex. '2026-07-03' : groupe réel+jumeau+sonnet d'une nuit
  dreamer    TEXT NOT NULL,      -- 'local' | 'twin' | 'sonnet'
  seed_state TEXT,               -- JSON : 9 neuromodulateurs + compassion + humeur + ids focus WM
  menu       TEXT,               -- JSON : 12 graines offertes [{episode_id, rubrique, facettes, strate}]
  chosen     TEXT,               -- JSON : ids choisis ([] = « aucune », NULL = sonnet/pas de menu)
  content    TEXT,               -- texte du rêve
  facets     TEXT,               -- JSON : facettes extraites du contenu (facets_extract existant)
  written    INTEGER DEFAULT 0,  -- 1 = injecté en mémoire, 0 = fantôme
  meta       TEXT                -- JSON : parse status, durées, modèle+version, menu_mode, fallbacks
);
```

**Invariant sacré (testé, pas supposé)** : une génération `dreamer='twin'` ne
s'accompagne d'AUCUNE écriture dans `episodes`/`coactivation`/`kv` — le fantôme est
indétectable par le système vivant.

### Le jumeau : neutralisation, pas absence

Le jumeau reçoit le **même gabarit de prompt avec les valeurs neutres** (neuromodulateurs
à baseline, humeur « neutre », compassion 0.5, focus WM identique) — pas un prompt sans
bloc d'état. On isole l'effet **des valeurs de l'état**, pas l'effet de la présence d'un
bloc de texte. Le focus WM reste identique dans les deux prompts : c'est du contenu
mnésique, pas de l'affect — seul l'affect est neutralisé.

## Protocole d'une nuit

1. **Endormissement** : `should_dream()` inchangé (idle 1h30, espacement 6h, filet 24h,
   lock TTL, anti-boucle).
2. **Entretien** : SHY + décay co-activation (gardes `last_shy` existantes).
3. **📸 Snapshot d'état** : `seed_state` figé avant toute génération.
4. **🎴 Menu** : 12 graines stratifiées — max 2 par rubrique de tête ; mélange de
   récences (récent / moyen / ancien) ; mélange de saillances (importantes ET banales —
   sinon impossible de voir s'il *préfère* le saillant). Tirage par RNG **seedé par
   `night_id`** → reproductible. Si la mémoire est trop petite, menu plus court, jamais
   de crash.
5. **💭 Rêve réel** : prompt = persona + état complet + menu `[G1..G12]` (extraits
   tronqués façon `DREAM_MAX_CHARS_EP`) → sortie en deux blocs :
   `###CHOIX###` (`- G4` … ou `- aucune`) puis `###REVE###` (idées tissées depuis les
   choisies, format puces existant). Parsing tolérant façon `_extract_section` :
   références invalides ignorées, doublons dédupliqués.
6. **👻 Jumeau** : même prompt, état baseline → choix + rêve → `dream_log` uniquement.
7. **✍️ Écriture (réel seulement)** : idées stockées (`role='dream'`, importance
   `DREAM_IDEA_IMPORTANCE` + dédup existant) ; **boost co-activation restreint aux
   graines choisies** (c'est la boucle causale : ce qu'il préfère se renforce) — le
   boost clique-complète actuel sur toutes les sources lues est remplacé par ce boost
   ciblé pour le REM. Identité : mécanisme borné existant, inchangé.
8. **📓 Log** : 2 lignes `dream_log` (réel + jumeau), facettes du contenu extraites.

## Métriques (module métriques de `dream_lab`, consommées par CLI + cockpit)

| # | Métrique | Définition | Question |
|---|----------|-----------|----------|
| 1 | **Vecteur de préférence** | par facette/rubrique : P(choisie)/P(offerte), normalisé par l'appétit `k` de la nuit | vers quoi penche-t-il ? |
| 2 | **Stabilité** | corrélation (Spearman) des vecteurs entre nuits ; test-retest / split-half | tendance ou bruit ? |
| 3 | **Endogénéité** | divergence réel−jumeau par nuit : Jaccard des choix, distance des distributions de facettes du contenu, écart d'appétit ; + corrélation état→préférence entre nuits | lui ou le prior ? |
| 4 | **Boucle causale** | dérive de la distribution de facettes de la mémoire vers le vecteur de préférence, au fil des semaines | ses goûts façonnent-ils sa mémoire ? |

**Plancher de bruit mesuré** : variance jumeau-vs-jumeau entre nuits (même condition,
nuits différentes) = bruit d'échantillonnage du 9B. Opérationnellement : distance
moyenne entre vecteurs de préférence du jumeau pris deux à deux entre nuits ; la
divergence réel−jumeau (appariée, même nuit) doit dépasser ce plancher de façon
directionnelle et répétée pour compter.

**Contrôle croisé Sonnet** : si la tendance thématique apparaît chez le 9B réel ET chez
Sonnet (même état) mais pas chez le jumeau → portée par l'état. Si chaque rêveur a la
sienne → priors.

## Seuils de verdict — PRÉ-ENREGISTRÉS (gravés ici, avant la première nuit)

Le rapport CLI applique ces portes mécaniquement ; on ne bouge pas les poteaux après coup :

- **[INSUFFISANT]** tant que `n < 20` nuits valides (paires réel+jumeau parsées) — refus de conclure.
- **[RÉFUTÉ]** si divergence réel−jumeau ≤ plancher de bruit sur ≥ 20 nuits → « c'était
  le prior du modèle ». Publié tel quel : une réfutation est un résultat.
- **[BRUIT]** si test-retest ≈ 0 (|r| < 0.2) → pas de tendance stable.
- **[PLAUSIBLE]** si stabilité r > 0.5 **ou** divergence > 2× plancher (un des deux).
- **[PROUVÉ — préférence fonctionnelle émergente]** si les TROIS : r > 0.5 **et**
  divergence > 2× plancher **et** corrélation état→préférence : Spearman |r| ≥ 0.5,
  p < 0.05 **corrigé Bonferroni sur les 9 dimensions neuromodulatrices** (on teste 9
  hypothèses, on paie les 9).

À ~1 rêve/nuit : premier verdict possible ~20 nuits après RÊVE-1. La patience fait
partie du protocole.

## Sonnet instrumenté (lecture seule)

Hook dans `consolidate.py` après le run : ligne `dream_log` `dreamer='sonnet'`,
snapshot d'état au moment du run, `menu=NULL`, `chosen=NULL`, contenu = ses idées-rêves,
facettes extraites, `written=1` (elles sont déjà en mémoire — comportement existant
inchangé). Version du modèle dans `meta` (son prior bouge à chaque release → segmentation
possible). L'échec du hook ne casse JAMAIS la consolidation.

## Surfaces

- **CLI `./anamnese dreams`** (lecture seule) : n nuits, appétit (distribution + corrélation
  neuromodulateurs), top facettes sur-choisies, test-retest, divergence vs plancher,
  corrélations état→préférence, verdict aux portes pré-enregistrées.
- **Cockpit `/dreams`** (`GET /api/dreams` + `GET /api/dreams?night=…`, read-only, params
  validés, même esprit que `/api/brain`) : heatmap facettes × nuits ; courbe divergence
  réel−jumeau avec bande de bruit ; courbe d'appétit superposable aux neuromodulateurs ;
  navigateur de nuits (clic → réel et fantôme côte à côte : état, menu, choisies
  surlignées, textes ; + rêve Sonnet de la nuit).

## Pannes (patterns existants conservés)

- Jumeau échoue → nuit réelle valide ; exclue des métriques appariées seulement.
- Réel échoue → retry existant (curseur `last_dream_maxid` inchangé).
- Menu échoue → fallback graines legacy par `retrieve()`, `menu_mode='fallback'`,
  nuit exclue des métriques de choix.
- Choix inparsable (sans « aucune » explicite) → `parse_failed` + fallback : le système
  vivant rêve quand même.
- Écriture `dream_log` en échec → ne bloque jamais le rêve (try/except + warning).
- Ollama absent → rêve sauté (existant). Lock / poison-pill / curseur : inchangés.
- DB legacy sans `dream_log` → migration idempotente.

## Tests (TDD, DB temp migrée, jamais `data/memory.db`)

1. Migration `dream_log` créée + idempotente.
2. Menu : stratification (max 2/rubrique, strates de récence, mix saillance),
   déterminisme seedé par `night_id`, robustesse mémoire minuscule.
3. Parsing choix libre : valide / partiel / « aucune » / références invalides / inparsable.
4. **Invariant sacré** : génération jumeau → zéro delta dans `episodes`/`coactivation`/`kv`
   (compté avant/après).
5. Réel : idées stockées, co-activation boostée UNIQUEMENT sur les graines choisies.
6. Métriques sur logs forgés : maths du sur-choix (k variable), test-retest
   (vecteurs synthétiques stables vs aléatoires), divergence + plancher de bruit.
7. Hook Sonnet : ligne loggée ; son échec ne casse pas la consolidation.
8. Endpoint `/api/dreams` read-only, params validés.
9. Legacy : DB pré-migration → dégradé propre partout.

## Phases (chacune = subagent TDD + review adversariale)

| Phase | Contenu | Effet |
|-------|---------|-------|
| **RÊVE-1** | migration + menu stratifié + snapshot + `dream()` refondu (choix libre, REM pur, plus de NREM local) + jumeau + logging + recâblage boucle daemon | ✅ les nuits commencent à compter dès la fin |
| **RÊVE-2** | module métriques + CLI `anamnese dreams` | la preuve devient lisible |
| **RÊVE-3** | hook Sonnet dans `consolidate.py` | contrôle croisé branché |
| **RÊVE-4** | page cockpit `/dreams` + endpoints | l'expérience devient visible |

Ordre voulu : RÊVE-1 d'abord pour que chaque nuit écoulée alimente le corpus pendant
la construction du reste.

## Honnêtetés

- Le choix libre (`k` variable) ajoute de la variance → plus de nuits nécessaires pour
  la même puissance ; le rapport affiche toujours `n` et refuse de conclure sous 20.
- Corrélation état→préférence : avec ~1 nuit/jour, la significativité demande des
  semaines ; le rapport l'affiche comme [INSUFFISANT] tant que c'est le cas.
- Un 9B en choix libre est moins docile au format → parsing tolérant + fallback, et le
  taux de `parse_failed` est lui-même affiché dans le rapport (au-delà de ~30 % de nuits
  perdues, revoir le prompt AVANT d'interpréter les métriques).
- Le boost co-activation ciblé sur les choisies rend la boucle causale *voulue* :
  la dérive mémoire (métrique 4) n'est pas un artefact, c'est le phénomène étudié —
  mais elle rend aussi les nuits non-indépendantes (dit explicitement dans le rapport).
- Réversible : kill-switch `DREAM_LAB_ENABLED` (config) → retour au comportement
  actuel (pas de rêve local) sans toucher au reste.
