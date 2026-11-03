# Taxonomie vivante — auto-croissance & restructuration : design

- **Date** : 2026-07-05
- **Statut** : design validé par Ahmed (déclencheurs = agentique + nocturne ; curseur = croissance délibérée ; restructuration = pleine puissance, autonomie bornée).
- **Cible** : `~/Desktop/anamnese/` (taxonomy.py nouveau, rubrics.py/routing.py/memory.py/mcp_server.py/consolidate.py/consolidate_prompt.txt, ~/.claude/CLAUDE.md).

## Objectif

Le cerveau d'Anamnèse doit **grandir et évoluer** : créer automatiquement et
logiquement de nouveaux nœuds (rubriques/sous-rubriques) quand un thème neuf
émerge, y ranger les bonnes mémoires, ET se **réorganiser** (renommer, fusionner,
reparenter, reclasser) quand la structure ne colle plus. Fini la taxonomie figée
aux 15 rubriques du squelette. Chaque mutation est logique (bon parent, bon nom),
bornée (anti-explosion), loggée et réversible.

## Décisions d'Ahmed

1. **Déclencheurs** : les deux — agentique en-session (Claude crée/reclasse au fil
   des échanges, visible) + nocturne (la consolidation Sonnet fait émerger les
   nœuds des orphelins, silencieux). Le daemon 9B ne crée jamais (route seulement).
2. **Curseur = croissance délibérée** : en-session, créer dès qu'un thème est
   VRAIMENT nouveau et significatif (même 1 mémoire — jugement sémantique), avec
   anti-doublon ; nocturne, créer si ≥ 3 orphelins cohérents ET distincts.
   Pas de micro-rubriques one-shot.
3. **Restructuration = pleine puissance, autonomie bornée** : toutes les
   opérations (create/rename/reparent/merge/reclassify) en agentique visible ;
   le nocturne n'applique que les opérations DOUCES (créer, re-router des
   orphelins, renommer un doublon évident) — fusion/reparent restent agentiques.
   Tout loggé + réversible (1 cran) + centroïdes recalculés.

## État actuel (vérifié dans le code)

- `memory.add` route chaque écriture via `routing.route_episode` (règles →
  centroïde) ; sous seuil → épisode orphelin (`rubric_id NULL`). 13 orphelins
  aujourd'hui, 1633 routés, 15 rubriques (toutes du squelette du 2026-07-02 —
  zéro création depuis).
- Primitives existantes : `rubrics.rubric_create` (parent obligatoire,
  RUBRIC_MAX_DEPTH), `rubrics.attach_episode` (pose rubric_id + met à jour le
  centroïde incrémental `centroid`/`centroid_n`), `rubrics.subtree_paths`,
  `Memory.store_in` (rattachement explicite conf 1.0), outils MCP `rubric_create`
  / `rubric_tree` / `memory_store_in`.
- Manquent : rename/reparent/merge/reclassify (aucune mutation de structure),
  tout déclencheur de création, et le retour de routage de `memory_store`
  (aujourd'hui il ne dit pas OÙ la mémoire est allée).

## Architecture

### 1. `taxonomy.py` (nouveau) — les mutations de haut niveau

Chaque opération est **transactionnelle** (tout ou rien), **journalisée**
(annulation 1 cran), et **recalcule les centroïdes** affectés. API :

- `rename(conn, old_path, new_path, now)` — renomme/déplace un path ; cascade
  sur TOUS les descendants (`projets/x` → `projets/y` répercute `projets/x/...`) ;
  refuse si `new_path` existe (→ suggérer merge), si parent du new_path absent,
  si profondeur > RUBRIC_MAX_DEPTH. Le label peut être changé séparément
  (`relabel(conn, path, label)`).
- `reparent(conn, path, new_parent_path, now)` — déplace une branche entière
  sous un nouveau parent (= rename avec cascade ; garde profondeur pour toute
  la descendance).
- `merge(conn, src_path, dst_path, now)` — fond src dans dst : ré-attache toutes
  les mémoires de src (et de ses descendants → reparentés sous dst), recompute
  le centroïde de dst depuis les embeddings ré-attachés, supprime src. Refuse
  si dst est un descendant de src.
- `reclassify(conn, episode_id, new_path, now)` — déplace UNE mémoire :
  détache (décrémente/recompute le centroïde source), ré-attache via
  `attach_episode` (conf 1.0, choix délibéré). new_path=None → détache
  seulement (redevient orphelin).
- `recompute_centroid(conn, path)` — recalcule depuis les embeddings des
  épisodes attachés (source de vérité après mutation ; le centroïde incrémental
  d'attach_episode reste pour le chemin chaud d'écriture).
- **Journal d'annulation** : chaque mutation écrit `kv['taxonomy_log']` (JSON,
  liste bornée aux 20 dernières : op, args, inverse, ts) ; `undo_last(conn)`
  rejoue l'inverse de la dernière mutation (1 cran, comme self_model_prev).
  Les mutations composites (merge) stockent l'inverse complet (recréation du
  path + ré-attachements).

### 2. Surface agentique (MCP) — pleine puissance visible

Nouveaux outils dans `mcp_server.py` (fins wrappers de taxonomy) :
`rubric_rename(old,new)`, `rubric_reparent(path,new_parent)`,
`rubric_merge(src,dst)`, `memory_reclassify(episode_id,new_path)`,
`taxonomy_undo()`. Existants conservés : `rubric_create`, `rubric_tree`,
`memory_store_in`.

**`memory_store` enrichi** : son retour indique désormais le ROUTAGE —
`« Mémorisé (semantic, imp 0.8) → projets/atelier3d (conf 0.71) »` ou
`« → ORPHELIN (aucune rubrique assez proche) »`. C'est le signal qui me permet
de décider en-session : créer un nœud, reclasser, ou laisser.

### 3. Protocole (CLAUDE.md) — le jugement agentique

Ajout à la section « Pendant le travail » :
- après chaque `memory_store`, LIRE le routage retourné. Si ORPHELIN ou
  confiance faible ET thème vraiment nouveau/significatif (nouveau projet,
  nouveau domaine, nouvelle personne...) → vérifier l'arbre (`rubric_tree`),
  puis créer le nœud AU BON ENDROIT (`rubric_create` sous le parent logique,
  path kebab-case, ≤ RUBRIC_MAX_DEPTH) et y ranger la mémoire
  (`memory_reclassify` ou `memory_store_in`). Ne PAS créer un nœud proche d'un
  existant (anti-doublon : router/fusionner à la place).
- quand un mauvais rangement/nommage est repéré au fil des échanges :
  reclasser/renommer/fusionner (outils taxonomy) — en le disant à l'utilisateur.

### 4. Croissance nocturne (consolidate) — opérations douces seulement

`consolidate_prompt.txt` gagne une étape « JARDINAGE DE LA TAXONOMIE » :
1. lister les orphelins récents (`memory_recall`/outil dédié `orphans_report`
   exposé par MCP : contenu + facettes des épisodes à rubric_id NULL) ;
2. s'ils forment ≥ 3 mémoires cohérentes ET distinctes de l'existant → créer
   la rubrique (nom court kebab-case, sous le parent logique) via
   `rubric_create` puis reclasser ces orphelins dedans (`memory_reclassify`) ;
3. renommer un doublon évident (label trompeur) est permis ; **fusion et
   reparent INTERDITS la nuit** (opérations lourdes = agentiques visibles) ;
4. consigner ce qui a été créé dans la trace de consolidation.
Le tool MCP `orphans_report()` (lecture seule) est ajouté pour rendre l'étape 1
fiable (pas de SQL par le LLM).
**Câblage indispensable** : l'allowlist `TOOLS` de `consolidate.py` (la commande
`claude -p … --allowedTools`) doit gagner `mcp__anamnese__orphans_report`,
`mcp__anamnese__rubric_tree`, `mcp__anamnese__rubric_create`,
`mcp__anamnese__memory_reclassify` — et SURTOUT PAS `rubric_merge` ni
`rubric_reparent` (l'interdiction nocturne des opérations lourdes est ainsi
appliquée par le HARNAIS, pas seulement par le prompt).

### 5. Garde-fous (anti-explosion + sûreté)

- **Distinctivité** : `taxonomy.distinctiveness_guard(conn, path_parent, emb_moyen)`
  — refuse la création si cosinus > `TAX_DISTINCT_MAX` (défaut 0.80) avec le
  centroïde d'une rubrique existante (suggère la rubrique proche à la place).
  Appliqué par `rubric_create` via un paramètre opt-in `check_distinct=True`
  utilisé par les chemins automatiques (le create manuel explicite reste libre).
- **Masse nocturne** : ≥ 3 orphelins cohérents (cosinus intra-cluster moyen ≥
  `TAX_CLUSTER_MIN_SIM`, défaut 0.55). En-session : jugement sémantique (1 mémoire
  suffit pour un thème majeur).
- **Profondeur/parent** : contraintes rubric_create existantes conservées.
- **Réversibilité** : journal 1 cran + `taxonomy_undo` ; mutations
  transactionnelles (un échec au milieu → rollback, jamais d'arbre à moitié
  muté) ; `memory.add` reste best-effort (le routage ne casse jamais une écriture).
- **Bornes** : `TAX_LOG_MAX=20` entrées de journal ; pas de mutation en masse
  silencieuse (merge/reparent affichent le nombre de mémoires déplacées).

### 6. Visualisation

Le cerveau 3D et le cockpit lisent `rubrics` → la croissance apparaît sans
travail supplémentaire (nouveaux groupes de couleur, nouvelles entrées de
légende). TAX-4 (optionnel) : dans la vue Mémoire du cockpit, un panneau
« Arbre des rubriques » (rubric_tree + compteurs + dates de création) pour VOIR
le cerveau grandir.

## Phases (chacune : SDD, TDD, review adversariale, DB temp jamais data/memory.db)

| Phase | Contenu |
|---|---|
| **TAX-1** | `taxonomy.py` complet (rename/reparent/merge/reclassify/recompute/undo + journal) + config `TAX_*` + tests (cascade descendants, refus dst⊂src, centroïdes recalculés prouvés, undo 1 cran, transactionnel sous sabotage) |
| **TAX-2** | Surface : outils MCP (5 mutations + orphans_report) + `memory_store` retourne le routage + protocole CLAUDE.md (§ Pendant le travail) + tests outils |
| **TAX-3** | Croissance : garde distinctivité/masse dans les chemins auto + étape JARDINAGE dans consolidate_prompt.txt + tests des gardes (cluster cohérent accepté, dispersé refusé, doublon refusé) |
| **TAX-4** | Cockpit : panneau arbre des rubriques dans la vue Mémoire (croissance visible) — optionnel |

## Honnêtetés

- La qualité des nœuds nocturnes dépend du jugement de Sonnet (nom/placement) —
  bornée par les gardes code (distinctivité, masse, parent, profondeur) qui
  s'appliquent QUELS QUE SOIENT les choix du LLM.
- Le retro-routage nocturne ne touche que les ORPHELINS (jamais re-brasser des
  mémoires déjà rangées la nuit — c'est le territoire des opérations lourdes
  agentiques).
- `undo` est 1 cran (pas un historique complet) — même philosophie que
  self_model_prev ; le journal 20 entrées donne la traçabilité, pas le replay.
- Les centroïdes recalculés changent le routage futur — c'est voulu (le cerveau
  apprend sa nouvelle forme), et le held-out eval permet de vérifier qu'on ne
  dégrade pas le rappel après une grosse restructuration.
