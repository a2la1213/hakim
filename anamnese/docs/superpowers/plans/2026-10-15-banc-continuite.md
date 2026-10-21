# Plan — banc d'épreuves, strate 1 « continuité » (2026-10-15)

Spec : `docs/superpowers/specs/2026-10-15-banc-epreuves-personnel.md`. Validation d'Ahmed : A
(il valide un échantillon de 10 questions).

## Isolation (décisions)

- Les deux bras tournent en `claude -p --bare --restricted` : ni hooks (le SessionStart
  injecterait la mémoire dans le bras A et écrirait dans la vraie base), ni CLAUDE.md ;
  `--restricted` ignore les fichiers de réglages (`--bare` seul ne le fait pas : corrigé après
  relecture). `--bare` n'accepte que la clé API : `--settings apiKeyHelper` (trousseau).
- `--tools ""` : aucun outil intégré (le bras A ne peut pas lire la base ou les fichiers).
- Bras B : `--strict-mcp-config --mcp-config` vers `eval/banc/mcp_copie.py`, qui lance le
  serveur MCP sur une COPIE de la base (le rappel renforce les souvenirs consultés : le banc
  ne doit jamais modifier la vraie mémoire) ; outils autorisés : memory_recall,
  reasoning_recall, facet_search, self_get ; bilan de démarrage (boot_brief) calculé sur la
  copie et ajouté au prompt système, comme le hook réel.
- Modèles : bras = Sonnet 5.5 ; générateur et juge = Opus 5.5.
- Les fichiers du banc (questions, réponses) sont ignorés par git : ils contiennent des
  données personnelles.

## Tâches (TDD)

1. `eval/banc/selection.py` : sources = rangements manuels (conf 1,0), semantic/reasoning,
   sous `projets/`, ≥ 200 caractères, au plus 3 par rubrique, tirage déterministe.
2. `eval/banc/cli.py` : construction des commandes `claude -p` (drapeaux d'isolation testés),
   exécution, lecture du JSON ; extraction de la ligne `CONFIANCE: NN`.
3. `eval/banc/mcp_copie.py` : serveur MCP sur la base désignée par `ANAMNESE_BANC_DB`.
4. `eval/banc/generer.py` : questions + références + faits clés (Opus, par lots de 10) ;
   pièges vérifiés absents de la base (terme discriminant introuvable) ; → `continuite.jsonl`.
5. `eval/banc/executer.py` : bras A et B, juge à l'aveugle, métriques (correct, invention sur
   pièges, Brier), ajout à `historique.jsonl` ; `--n 5` pour le run de mesure du coût.
6. Run de 5 questions (coût mesuré), échantillon de 10 questions montré à Ahmed, run complet.
7. Relecture indépendante (Opus 5.5).

## Après relecture indépendante (Opus 5.5, CORRIGER) — v2

Traités : lecteur JSON du juge (un « [3] » dans la justification faisait planter le run),
écriture au fil de l'eau, serveur de la copie en lecture seule, --restricted, juge avec source
et souvenirs récents sans provenance ni confiance, faits clés limités à la question, états
datés, pièges validés par rappel (2 faux pièges sur 5 en v1), erreurs exclues, intervalles
bootstrap, comparaison appariée, sélection par projet, purge de la copie, escalade coupée,
fichiers temporaires supprimés.
