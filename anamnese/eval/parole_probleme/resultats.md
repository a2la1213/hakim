# Les faux « probleme » de la parole : résultats (28/10, 03:05)

**Les critères ont été figés avant le code** (`criteres.md`, commit e57c8da). L'étiquetage a été fait à l'aveugle, par un agent indépendant qui n'a vu ni les règles ni les corrections :

| Étiquette | Nombre |
|---|---|
| vrai | 20 |
| materiel | 1 |
| faux | 41 |

Ces 62 messages déclenchaient tous « probleme » avec les règles d'avant. Le détail est dans `~/AIOS/jarvis/bancs/parole-probleme/bilan.json` (textes privés).

## A + B + C, le paquet complet : C1 échoue, donc il n'est pas appliqué

| Critère | Mesure | Issue |
|---|---|---|
| C1, garder les vrais | 18 sur 20 (90 %) | **échoue** (seuil 95 %) |
| C2, les témoins | 5 sur 5 à 0,5 | passe |
| C3, cette nuit | 02:12:48 → 0 ; 01:29:05 → 0,1 | passe |

**B a coûté deux vrais problèmes.** Deux demandes de réparation du système de Hakim contenaient un mot de matériel (« smartphone », « connexion ») sans aucun mot de ma liste « système », et B les a ramenées à une attention. La règle était trop large. Je ne la retouche pas sur ces mêmes 62 messages : ce serait l'ajuster sur les données qui la jugent.

## A + C, appliqués

A et C sont indépendants de B, et chacun passe ses propres critères :

| Critère | Mesure | Issue |
|---|---|---|
| C1, garder les vrais | 20 sur 20 | passe |
| C2, les témoins | 5 sur 5 à 0,5 | passe |
| C3, 02:12:48 (la cible de A) | 0 | passe |
| C3, 01:29:05 (la cible de B) | 0,5 | **échoue** : B n'est pas appliqué |
| C4, la voie rapide | tests de `test_affect_v2.py` | passe |

C4 vérifie trois cas :
- source parole et sujet « mots:… » neuf : rien ;
- peur apprise sur le type : elle joue ;
- source « hakim » : comme avant.

**Écart à la règle figée, dit tel quel.** La règle disait « si C1, C2 ou C3 échoue, on n'applique pas ». Elle a été écrite pour le paquet entier. J'applique la partie qui passe et je retire la partie qui échoue, plutôt que de tout garder ou de tout jeter. Le cas de 01:29 reste donc possible.

## Ce que la mesure apprend en plus

- **Le lexique « probleme » se trompe deux fois sur trois.**
  - 41 messages sur 62 n'étaient pas un problème présent pour Hakim.
  - A n'en retire que 3, et 38 déclenchent encore.
  - Prédiction figée : A et B retirent ou allègent au plus un tiers des « faux » et « materiel ». Elle est **vérifiée** : 4 sur 42 avec A + B (3 faux retirés, le cas matériel allégé).
- **C ne couvre qu'une partie des événements.**
  - Sur les 88 événements « probleme » de la parole du journal affectif, 16 ont un sujet « mots:… » et 72 une rubrique.
  - Une rubrique familière (projets/anamnese/hakim) n'a presque pas de nouveauté, donc pas de voie rapide.
  - Mais une rubrique rare la déclenche encore. C'était le cas à 01:29 : « projets/axai-distillation/pilotage », un rangement de hasard.

## À proposer à Ahmed (non appliqué)

- **C élargi.** Pour tout « probleme » venu de la parole, la nouveauté du sujet ne compte plus comme menace, quel que soit le sujet. Le sujet est attribué automatiquement dans les deux cas.
- **B, version 2.** La règle se limite à la phrase qui porte le mot de problème. Elle sera jugée sur des messages NEUFS, jamais sur ces 62.
