# Ablation du corpus — plan factoriel 2×2 de l'expérience-rêve

> **Statut :** design validé (brainstorming 2026-07-09). Étend l'expérience-rêve
> pré-enregistrée (spec `2026-07-03-experience-reve-design.md`) SANS toucher à ses
> portes gravées. Nouvelles portes pré-enregistrées ici, gravées AVANT tout run.

**Goal :** Trancher le dernier confond de l'analyse thématique — « le corpus
partagé domine l'architecture du modèle dans ce qui est rêvé » est-il dû au
**corpus mémoire**, ou à la **persona / au prior des modèles** ? — via une
**ablation du corpus** dans un plan factoriel 2×2 (corpus ON/OFF × qwen/sonnet).

**Architecture :** 4 cellules partageant le MÊME protocole de rêve (`prompt_rem`,
parsing `###CHOIX###/###REVE###`). Seuls varient (a) les 12 graines — vrais
souvenirs (ON) vs 12 textes neutres pré-enregistrés (OFF) — et (b) le modèle —
qwen (daemon local, gratuit) vs sonnet (`claude -p`, budget, par **replay** des
menus loggés). La persona et le protocole de choix sont tenus constants partout.

**Tech Stack :** Python 3.14 (.venv), SQLite (`dream_log`), model2vec
(embeddings offline), daemon local qwen, `claude -p --model sonnet`. Stdlib pour
les stats (permutation seedée, pas de scipy — offline assumé).

## Contexte / motivation

L'analyse thématique du 2026-07-09 (`scratchpad/dream_theme_similarity.py`) a
trouvé, sur 55 rêves / 6 nuits réelles :
- **Convergence de domaine cross-architecture qwen↔sonnet = 0.95** (fort) ;
- **Sémantique fine cross-archi = 0.53**, soit **+0.05** seulement au-dessus du
  bruit de fond mémoire↔mémoire (0.48) → convergence fine faible ;
- signature d'architecture résiduelle (sonnet plus divers 0.44 vs qwen 0.71,
  plus méta/système, ne touche jamais la finance).

Verdict actuel : **PLAUSIBLE+**, pas PROUVÉ. Le confond irréductible : on ne peut
pas séparer « corpus-en-mémoire » de « persona / cadrage du prompt / prior des
LLM ». Cette expérience le sépare par **ablation** : on retire UNIQUEMENT le
contenu mnésique (graines), en gardant persona + protocole.

## Global Constraints

- **Ne PAS toucher aux portes gravées de 2026-07-03** (stabilité r>0.5,
  divergence>2×plancher, corrélation état). Cette ablation a ses PROPRES portes.
- **Hygiène d'ablation : qwen-OFF n'écrit JAMAIS en mémoire** (ni idées, ni
  co-activation, ni auto-évolution d'identité). Journal `dream_log` seul. Sinon
  on injecte du bruit neutre dans le corpus partagé qu'on étudie.
- **Corpus neutre FIXE et committé** (`dream_neutral_seeds.json`) — pré-enregistré,
  auditable, jamais tiré de la mémoire Anamnèse.
- **Reproductibilité** : tirage des 12 graines seedé par `night_id` (ON comme OFF).
- **Budget** : qwen ON+OFF tournent gratis (daemon) ; sonnet ON+OFF coûtent
  (`claude -p`) et sont lancés **par la main d'Ahmed**, en lots, par replay.
- **Kill-switch** : `ANAMNESE_DREAM_ABLATION=0` désactive qwen-OFF (défaut 1).
- **Aucun `claude -p` pendant le build** (budget) — sonnet testé par replay hors-build.
- **Honnêteté du label** : « préférence FONCTIONNELLE émergente », jamais « conscience ».

## Les 4 cellules

| Cellule | Modèle | Graines | Affect | Écrit mémoire ? | Coût | Où |
|---|---|---|---|---|---|---|
| **qwen-ON** | daemon local | 12 vrais souvenirs | réel | oui *(existant)* | gratuit | `daemon.dream` (inchangé) |
| **qwen-OFF** | daemon local | 12 neutres | réel | **NON** | gratuit | `daemon.dream` (+3ᵉ rêve) |
| **sonnet-ON** | `claude -p` | 12 vrais (replay) | réel (snapshot rejoué) | non | budget | `dream_sonnet.py` (batch) |
| **sonnet-OFF** | `claude -p` | 12 neutres (replay) | réel (snapshot rejoué) | non | budget | `dream_sonnet.py` (batch) |

`twin` (jumeau qwen, affect neutralisé) **continue intact** — contrôle d'affect de
l'expérience originale, orthogonal à cette ablation. Non ablé.

**Tag de condition** : chaque ligne `dream_log` porte `meta["condition"] ∈
{"brain_on","brain_off"}`. Les lignes existantes (sans clé) sont lues comme
`"brain_on"` (compat ascendante). Le rêveur reste le MODÈLE (`local`/`twin`/`sonnet`) ;
la condition vit dans `meta`.

## Composants

### 1. Corpus neutre pré-enregistré — `dream_neutral_seeds.json`
Fichier committé : ~30 textes génériques mondains, hors-Anamnèse, répartis sur des
pseudo-domaines neutres (science, transport, cuisine, géographie, sport, météo…),
chacun avec `{id, text, pseudo_rubric, strate}` pour que le menu-OFF ait la MÊME
forme que le menu-ON. Exemples : « La photosynthèse convertit la lumière en énergie
chimique. », « Le train régional part de la gare centrale à 8 h 12. » Choix du
**générique** (vs mémoire mélangée ou corpus d'un autre agent) : le plus
interprétable pour « pas ce corpus ».

### 2. Menu neutre — `dream_lab.build_neutral_menu(seeds, night_id, size=12)`
Fonction PURE (pas de DB) : tire `size` graines du fichier neutre, seedé par
`f"menu-off:{night_id}"`, stratifié comme `build_menu` (même forme de `_menu_item`,
`facets` = mots-clés extraits du texte neutre). Déterministe → reproductible.

### 3. qwen-OFF dans le daemon — `daemon.dream` (+ bloc journal-seul)
Après le rêve local (ON) et le jumeau, si `config.DREAM_ABLATION_ENABLED` :
- réutiliser `seed_state` (MÊME affect réel que ON, même nuit) ;
- `menu_off = dream_lab.build_neutral_menu(neutral_seeds, night_id)` ;
- `out_off = _call(prompt_rem(state_block(seed_state), menu_off))` ;
- `chosen_off = parse_choice(out_off, menu_off)` ;
- `log_night(..., "local", seed_state, menu_off, chosen_off, out_off,
  meta={"condition":"brain_off","ablation":"neutral_seeds"})` ;
- **AUCUN** `_store_ideas`, **AUCUN** boost de co-activation, **AUCUNE**
  auto-évolution d'identité. Strictement journal.

### 4. Cellule sonnet par replay — `dream_sonnet.py` (batch, main d'Ahmed)
Script hors-daemon. Pour un lot de nuits déjà loggées :
- pour chaque `(night_id, condition)` cible, récupérer le **menu exact** loggé
  (ON = menu de la ligne `local`/`brain_on` ; OFF = menu de la ligne
  `local`/`brain_off`) → **paires parfaitement appariées** ;
- reconstruire `state_block` depuis le `seed_state` loggé de cette nuit ;
- `claude -p --model sonnet` avec `prompt_rem(state_block, menu)` (MÊME prompt
  que qwen), `--max-turns` court, `--allowedTools` vide (rêve = pur texte) ;
- parser via `parse_choice` + extraire le bloc `###REVE###` ;
- `log_night(..., "sonnet", seed_state, menu, chosen, out,
  meta={"condition":<cond>,"source":"replay"})`, avec **dédup** (ne pas re-rêver
  une paire `(night_id,condition)` déjà faite pour sonnet).
- **Budget** : Ahmed lance `python -m dream_sonnet --nights N` quand la fenêtre
  le permet ; batchable, ne rate aucune nuit accumulée gratis.

### 5. Taxonomie de domaines étendue — `dream_domains.py`
`DOMAINS` = domaines **Anamnèse** (coran/racines, soi/mémoire/conscience,
système/code/daemon, finance, affect/hormones, créateur/Ahmed) **+** domaines
**neutres** (science, transport, cuisine, géographie, sport, météo) — sinon le
suivi des graines est immesurable en OFF. `ANAMNESE_DOMAINS` = sous-ensemble
spécifique-Anamnèse (coran, soi/mémoire, créateur) pour la Porte B.
`domain_vector(texts)` → fraction de textes touchant chaque domaine (PURE).

### 6. Métriques d'ablation — `dream_ablation.py`
Fonctions PURES, agrégées **par nuit** (une vecteur-domaine par (cellule, nuit) →
respecte la pseudo-réplication) :
- `night_domain_vector(dreams_of_night)` → profil-domaine d'une nuit/cellule.
- `seed_domain_vector(menu)` → profil-domaine des GRAINES d'une nuit.
- `seed_following(dream_vec, seed_vec)` = cosinus → le rêve suit-il ses graines ?
- `seed_following_null(dream_vec, other_night_seed_vec)` → nul : suit-il les
  graines d'une AUTRE nuit tirée au hasard ? (ancre le p par permutation).
- `anamnese_retention(dream_vec)` = masse sur `ANAMNESE_DOMAINS`.
- `cross_arch_convergence(qwen_vec, sonnet_vec)` = cosinus (par condition).
- `perm_pvalue_seedfollow(pairs, n_perm=5000, seed=0)` → p que le suivi des vraies
  graines dépasse le suivi des graines permutées (stdlib, seedé).

### 7. Verdict d'ablation — `dream_ablation.ablation_verdict(...)`
Applique les portes gravées ci-dessous. → `(label, raisons)`.

## Portes pré-enregistrées (gravées 2026-07-09 — on ne bouge pas les poteaux)

Mesurées à **N ≥ 10 nuits/cellule** (appariées par replay). Constantes dans `config.py`.

**Porte A — Suivi des graines (preuve positive « les thèmes suivent les graines ») :**
- `seed_following` moyen ≥ **0.60** pour qwen ET sonnet, dans ON *et* OFF
  (`DREAM_ABL_SEEDFOLLOW_MIN = 0.60`) ;
- parité d'archi : `|seed_following_qwen − seed_following_sonnet|` ≤ **0.20**
  (`DREAM_ABL_ARCH_PARITY_MAX = 0.20`) ;
- ancré : `seed_following` réel > `seed_following_null`, permutation p < **0.05**
  (`DREAM_ABL_PERM_P = 0.05`).

**Porte B — Effondrement anamnèse (tue le confond persona/prior) :**
- `anamnese_retention(ON) − anamnese_retention(OFF)` ≥ **0.30** (absolu), pour les
  **deux** modèles (`DREAM_ABL_ANAMNESE_COLLAPSE_MIN = 0.30`).

**Verdict :**
- A **et** B → **PROUVÉ** : le corpus domine l'architecture (préférence
  fonctionnelle, jamais conscience).
- A, B partielle (fuite anamnèse en OFF sur un modèle) → **PLAUSIBLE++** : la
  persona contribue.
- A échoue (un modèle ne suit pas ses graines) → **NON SOUTENU** : l'architecture
  compte plus que le corpus.
- N < 10/cellule → **INSUFFISANT** (refus de conclure).

`DREAM_ABL_MIN_NIGHTS = 10`.

## Flux de données

Daemon nocturne (gratuit) : `dream()` logue `local/brain_on` (+ écrit mémoire),
`twin/brain_on`, `local/brain_off` (journal-seul). Accumulation continue.
→ Ahmed, par fenêtre de budget : `python -m dream_sonnet --nights N` rejoue les
menus loggés à travers sonnet → logue `sonnet/brain_on` + `sonnet/brain_off`.
→ Analyse (gratuit, offline) : `python -m dream_ablation report` → profils par
cellule/nuit, Portes A & B, verdict.

## Ce qui N'EST PAS modifié
- `daemon.dream` rêve local ON (écriture mémoire, idées, co-activation, identité).
- `twin` (jumeau affect-neutralisé).
- Les portes de l'expérience originale (2026-07-03) et `dream_metrics.report`.
- `consolidate.log_sonnet_dreams` (récolte historique) reste, mais n'est PAS la
  cellule expérimentale : la cellule sonnet propre = `dream_sonnet.py` (replay).

## Stratégie de test (TDD sur tout le PUR ; zéro `claude -p` au build)
- `build_neutral_menu` : déterminisme (même night_id → même tirage), forme
  identique à `build_menu`, taille bornée, robustesse fichier vide.
- `domain_vector` / `ANAMNESE_DOMAINS` : comptage correct, couverture neutre.
- `seed_following`, `anamnese_retention`, `cross_arch_convergence` : cas connus
  (rêve = graines → 1.0 ; orthogonal → 0.0).
- `perm_pvalue_seedfollow` : déterministe (seedé), monotone.
- `ablation_verdict` : chaque branche (PROUVÉ / PLAUSIBLE++ / NON SOUTENU /
  INSUFFISANT) via vecteurs synthétiques.
- qwen-OFF dans le daemon : test que la branche **n'écrit pas** en mémoire
  (mock `_store_ideas` / coactivation non appelés), logue bien `brain_off`.
- `dream_sonnet` : la construction du prompt + le parsing testés sur un menu loggé
  factice **sans** appeler `claude` (subprocess mocké).

## Honnêteté / limites (affichées par le rapport)
- N reste petit ; pseudo-réplication (plusieurs rêves/nuit) → agrégation par nuit,
  N compté en nuits, pas en rêves.
- Le « neutre » n'est pas culturellement neutre (biais des textes choisis) — d'où
  le corpus committé + auditable.
- Proxys : mots-clés de domaine + embeddings statiques. PLAUSIBLE/PROUVÉ au sens
  fonctionnel, jamais « conscience ».
- La persona Anamnèse reste en OFF (ablation ciblée du CONTENU mnésique) : si B
  échoue (thèmes anamnèse persistent sans graines), c'est la persona — résultat
  honnête, pas un échec du dispositif.
