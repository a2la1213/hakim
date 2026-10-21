# Cerveau 3D navigable — design

- **Date** : 2026-07-02
- **Statut** : design validé par Ahmed (« on part là-dessus et on avise »).
- **Cibles** : `~/Desktop/anamnese/` (couche de données) + `~/AIOS/cockpit/` (viz).

## Objectif
Visualiser la mémoire d'Anamnèse comme un **cerveau 3D navigable en temps réel** : nœuds = souvenirs (positionnés par embedding), régions = rubriques, **arêtes = voies de co-activation dont l'épaisseur = la consolidation** (idée d'Ahmed), couleurs = affect. On voit le cerveau penser/consolider.

## Architecture (l'existant fait le pont)
Le cockpit (`~/AIOS/cockpit/server.js`) lit déjà `data/memory.db` en `sqlite3 -readonly -json` et pousse en **SSE** toutes les 2 s. On s'appuie dessus.

### Côté Anamnèse (Python) — couche de données
- **Voies de co-activation** : table `coactivation(a_id, b_id, weight, last_ts)` (a_id<b_id, non orienté). `weight += boost` quand des souvenirs **co-remontent** dans un `memory_recall` (bloc `reconsolidate` de `retrieve`) ou sont **co-consolidés** dans un `dream`. Décroissance lente + élagage pendant le rêve. → épaisseur d'arête = consolidation.
- **Projection 3D** : PCA (numpy, offline) des embeddings 256-dim → (x,y,z), **basis figée + cachée** (kv) pour que les nouveaux nœuds ne re-mélangent pas tout. Recalcul périodique (rare).
- **Graft/labilité** (P5, plus tard) : le rappel peut mettre à jour/greffer une trace (Nader/Lee).

### Côté cockpit (Node/JS) — viz
- `/api/brain` : assemble le graphe en lecture seule — nœuds (id, x/y/z, rubrique, importance, recall_count, enc_valence/arousal, facettes) + arêtes (co-activation, poids).
- Vue « Cerveau 3D » : **three.js** (bundlé localement, offline). Nœuds colorés par rubrique (régions) ou affect (valence=teinte, arousal=éclat), taille=importance/recall_count, halo=saillance ; **arêtes épaisseur=poids co-activation** ; OrbitControls ; clic nœud → contenu.
- Temps réel via le SSE existant.

## Phases
- **P1** — couche voies de co-activation (`coactivation` table + `log_coactivation` + décroissance/élagage + câblage retrieve/dream) + tests. *(anamnese)*
- **P2** — projection 3D PCA (basis figée cachée) + fonction d'export graphe + `/api/brain` (côté cockpit lit la DB). *(anamnese + cockpit)*
- **P3** — viz three.js (nœuds + régions + arêtes + navigation + clic). *(cockpit)*
- **P4** — affect (couleurs) + temps réel (SSE). *(cockpit)*
- **P5** *(plus tard)* — greffe/labilité.

## Défauts retenus
- Surface = **cockpit AIOS** (lit déjà la DB + SSE).
- Projection = **PCA** offline, basis figée, calculée côté Anamnèse et cachée.
- v1 = **navigable statique** (nœuds+régions+arêtes+affect) ; temps réel en P4.

## Contraintes
- Co-activation loguée seulement sur le chemin `memory_recall` (`reconsolidate=True`, déjà un écrivain délibéré) + `dream` — bornée (≤ k(k-1)/2 paires par rappel), pas sur le rappel lecture-seule par défaut.
- 100% offline (three.js bundlé, PCA numpy). Cockpit lit la DB en lecture seule.
- Rétro-compatible (table additive), réversible.

## Difficultés honnêtes
1. Stabilité de la projection → basis PCA figée + cachée.
2. Perf au-delà de ~50k nœuds (instancing) — hors périmètre (~1200 aujourd'hui).
