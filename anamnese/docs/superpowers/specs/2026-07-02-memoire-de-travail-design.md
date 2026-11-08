# Mémoire de travail ultra-boostée — design

- **Date** : 2026-07-02
- **Statut** : design validé par Ahmed.
- **Cible** : `~/Desktop/anamnese/` (+ branchement viz `~/AIOS/cockpit`).

## Objectif
Donner à Anamnèse une **mémoire de travail** (episodic buffer, Baddeley) **vivante + amorcée** : l'ensemble de souvenirs qu'elle « tient en tête maintenant ». Ultra-boostée vs l'humain (4±1, volatile en secondes) : **focus ~24 + halo ~150, persistant toute la session, structuré, zéro interférence intra-session**. Plafond honnête : seul le focus est injecté au contexte (fenêtre LLM + pertinence) — le halo n'est jamais dumpé.

## Décisions d'Ahmed
1. **Vivante + amorcée** (pas briefing-seul, pas intra-session-seul).
2. **Deux étages** : FOCUS net (injecté) + HALO périphérique (promouvable, non injecté).

## Architecture
- La MDT = **couche d'attention au-dessus de la LTM** (`episodes`) — pas un nouveau store : des pointeurs + scores, régénérables.
- État dans `kv['working_memory']` (JSON) : `{"focus": [{"id": int, "score": float}], "halo": [...], "updated_ts": float}`.
- `config.py` : `WM_FOCUS_CAP=24`, `WM_HALO_CAP=150`, `WM_DECAY=0.85` (multiplicateur par update des non-touchés), `WM_FLOOR=0.15` (éviction), `WM_PROMOTE_SCORE=…` (défauts raisonnables, calibrables).

## Politique d'attention (automatique)
- **Promotion** : les top résultats d'un `memory_recall` montent en focus (score = wm_score) ; un `memory_store`/`store_in` fait entrer le nouvel épisode en focus.
- **wm_score** = combinaison bornée de : `importance` + `enc_arousal` (tag amygdalien, si présent) + récence-de-toucher-dans-la-session + co-activation-avec-le-focus (table `coactivation`).
- **Décroissance** : à chaque update, les items non re-touchés `score *= WM_DECAY`.
- **Rétrogradation/éviction** : focus > cap → le plus faible descend en halo ; halo > cap ou score < floor → évincé.
- **Halo** = rétrogradés + voisins de co-activation du focus (les « prêts à revenir »).
- Écriture de l'état WM **bornée** aux chemins déjà écrivains (memory_recall reconsolidate=True, store) — pas sur le rappel lecture-seule.

## Amorçage & surface
- `wm_boot()` (outil MCP) : sème le focus depuis (a) le dernier état WM persistant (continuité), (b) les souvenirs récents saillants, (c) la rubrique dominante récente. **Absorbe le « résumé de session »** (le focus EST le « où on en était »).
- `working_memory()` (outil MCP) : le focus formaté (briefing lisible) — injectable par le hook SessionStart / le protocole CLAUDE.md.
- **Cerveau 3D** : `brain_graph` gagne un champ `wm` par nœud (`"focus"|"halo"|null`) ; la viz allume le focus (vif/halo lumineux) et le halo (lueur ténue). Le cerveau « pense » visiblement.

## Phases
- **WM1** — cœur : état kv + politique d'attention (`Memory.wm_touch/wm_update/wm_get`) + câblage memory_recall/store + tests.
- **WM2** — amorçage + surface : `wm_boot`, `working_memory()` (MCP), protocole d'injection au démarrage.
- **WM3** — viz : champ `wm` dans brain_graph + allumage dans la viz cockpit.

## Honnêtetés
- Le gain réel = persistance + structure + périphérie promouvable, PAS « plus de tokens dans le contexte ».
- La valeur (continuité « repartir en sachant ») est qualitative — pas de gate precision@6 applicable ; on mesure ce qui est mesurable (le focus contient-il les items attendus après une session simulée) et on assume le reste.
- Rétro-compatible (kv + champ optionnel), offline, réversible, aucun impact sur le scoring de rappel (la MDT consomme le rappel, elle ne le modifie pas).
