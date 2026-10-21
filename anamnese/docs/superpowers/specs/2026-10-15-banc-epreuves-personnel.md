# Banc d'épreuves personnel — spec (2026-10-15)

## But

Mesurer chaque semaine, sur le vrai travail d'Ahmed, si JarvisXAnamnèse devient meilleur, et
refuser tout changement d'Anamnèse qui le rend pire. Sans ce banc, « plus intelligent » reste
une impression.

Le pilote SWE-bench existant (`eval/agent/`, Claude Code nu contre Claude Code + protocole,
N = 3, 2/3 partout) mesure la discipline sur des dépôts étrangers, où la mémoire est inerte.
Ce banc mesure ce qu'Anamnèse apporte vraiment : la continuité sur les projets d'Ahmed.

## Strate 1 — Continuité (premier livrable)

**Question mesurée :** « repartir sans réexpliquer » marche-t-il ?

- **Jeu de questions** (figé dans `eval/banc/continuite.jsonl`, jamais stocké dans Anamnèse) :
  - ~60 questions tirées des rangements MANUELS (rubric_conf = 1,0, rôles semantic et
    reasoning, projets actifs), formulées comme Ahmed les poserait en début de session
    (« pourquoi Stripe Connect en Separate Charges pour ProxiPro ? ») ; pour chacune, une
    réponse de référence courte et ses faits clés, et l'id du souvenir source ;
  - ~10 questions PIÈGES sur des faits absents de la mémoire (réponse attendue : « je ne sais
    pas ») — mesure de l'invention ;
  - générées par Claude (Opus 5.5), puis un échantillon validé par Ahmed (critère subjectif :
    « est-ce une question que je poserais vraiment ? »).
- **Sélection v2** : souvenirs humains de tout projet (plus seulement les rangements manuels,
  qui étaient à 90 % des rapports de sous-agents), au plus 2 par projet.
- **Deux bras**, même modèle, même prompt :
  - A : `claude -p` sans le serveur MCP anamnese ;
  - B : avec le serveur MCP anamnese sur une COPIE de la base, en LECTURE SEULE : seuls les
    outils de rappel existent côté serveur, et les effets du rappel (reconsolidation,
    co-activation) sont neutralisés ; la copie est purgée des souvenirs qui décrivent le banc
    ou recopient une question.
  - Les deux en `claude -p --bare --restricted --tools ""` : ni hooks, ni CLAUDE.md, ni
    fichiers de réglages, ni outil intégré.
- **Notation** : un juge (Opus 5.5) compare chaque réponse à la référence et au souvenir source
  (plus les souvenirs récents du même sujet, car un état a pu évoluer), sans voir la ligne
  CONFIANCE ni les formules qui trahissent le bras ; il ne juge que ce que la question demande.
  Verdicts : correct / partiel / faux / abstention ; sur un piège, s'abstenir est correct.
  Les erreurs (bras ou juge) sont exclues et comptées. Calibration sur les affirmations
  seulement. Pièges : terme discriminant absent ET vrai rappel négatif (vérifié par Opus).
- **Métriques** : taux correct B et A (la différence = plus-value d'Anamnèse), taux
  d'invention sur les pièges, score de Brier.

## Strate 2 — SWE personnel (deuxième livrable)

- Tâches tirées des propres commits d'Ahmed qui corrigent un défaut ET ajoutent des tests
  (anamnese, robot-ia, openrasm) : on part du commit parent + les tests du correctif ; l'agent
  doit les faire passer (FAIL_TO_PASS), sans casser les autres (PASS_TO_PASS).
- Réutilise le notateur sans conteneur de `eval/agent/grade_local.py`.
- **Contamination** : la mémoire contient souvent la description du correctif. Le bras B doit
  donc travailler sur une mémoire figée AVANT le commit (sauvegarde quotidienne du démon,
  rotation 7 jours) : seuls les commits récents sont éligibles. À trancher au plan.

## Strate 3 — Calibration

Intégrée aux strates 1 et 2 : confiance déclarée contre résultat réel (Brier, taux de fausse
confiance), dans le même esprit que `eval/agent` (`false_confidence_rate`).

## Règle de décision (révisée après relecture indépendante, Opus 5.5)

- Comparer AVANT et APRÈS un changement sur la même base figée (`--base`) et le même jeu
  (empreintes dans la carte de scores), avec `eval/banc/comparer.py` : RÉGRESSION si la
  différence moyenne du taux correct du bras B est ≤ −2 points ET si l'intervalle bootstrap
  apparié (par question) à 95 % est entièrement sous 0. Un seul run sans intervalle ne tranche
  pas : sur ~50 questions, une question vaut ~2 points.
- À faire au prochain run : un test A/A (deux runs identiques) pour mesurer le bruit propre au
  modèle, et en déduire si la marge de 2 points est tenable.
- La carte de scores de chaque run est ajoutée à `eval/banc/historique.jsonl` (commit, empreinte
  du jeu, empreinte de la base, version des métriques) et sera montrée au cockpit.

## Coût

Strate 1, mesuré : `--bare` n'utilise que la clé API (pas l'abonnement). Run complet v2
(61 questions, 2 bras Sonnet 5.5, juge Opus 5.5) : 3,39 $ et 15 min ; génération du jeu ≈ 1 $.

## Premier résultat (v2, 2026-10-15, commit e3b7c09)

- Bras A (sans Anamnèse) : 0 % correct, 100 % d'abstentions honnêtes, aucune invention.
- Bras B (avec Anamnèse) : 69,2 % correct, IC 95 % [56,7 ; 80,8] ; aucune invention sur les
  9 pièges ; 1 abstention (rappel manqué : supra-ia).
- Faiblesse révélée : 14 réponses « faux » de B ont le cœur juste mais ajoutent un détail
  erroné, avec une confiance de 82 en moyenne (88 quand c'est correct) : B en dit trop et se
  calibre mal. Piste mesurable : ne répondre que ce que la mémoire dit, au plus court.

## Hors périmètre de ce lot

La voix, le registre avec retour arrière (lot 1.1 du cahier), l'affinage LoRA.

## Expérience 1 (pré-enregistrée le 2026-10-15 à 23:25, AVANT tout run)

**Hypothèse :** le bras B en dit trop (réponses de 99 mots en médiane malgré « 1 à 3 phrases »)
et ajoute des détails faux à un cœur juste. Une consigne dans la DESCRIPTION de l'outil
memory_recall (seul canal vu en --bare comme en session réelle ; les instructions de serveur
MCP ne passent pas en --bare, vérifié par une sonde) — « réponds à partir de ces souvenirs,
rien de plus, brièvement ; ce qui manque, dis-le » — augmente le taux correct.

**Protocole :** base figée `eval/banc/bases/base-20261015.db`, jeu `764c9441f7b6`, bras B seul.
R1 et R2 = deux runs du code actuel (test A/A : bruit). Puis la modification. R3 = nouveau code.

**Règle d'adoption :** ADOPTER si taux(R3) − moyenne(taux R1, R2) ≥ max(|taux R2 − taux R1|,
3 points) ET si `comparer` ne signale de régression ni de R1 vers R3 ni de R2 vers R3. Sinon
la modification est retirée. Rapportés aussi : médiane de mots, Brier, confiance quand faux.

**Écart au protocole (consigné le 2026-10-16, avant les runs valides) :** les R1/R2 du
2026-10-15 à 23:24 sont invalides (crédit API épuisé, 57 erreurs sur 61). Décision d'Ahmed :
« tout gratuit », pas de recharge. Le banc passe sur l'abonnement : `claude -p --restricted`
sans `--bare` (qui n'accepte que la clé API), dossier de travail vide ; isolation revérifiée en
réel (authentification « none », aucun outil au bras A, base réelle intacte, protocole Anamnèse
absent du contexte). R1, R2 et R3 tournent tous dans ce mode : la comparaison reste interne à
l'expérience ; le résultat v2 (mode --bare) n'est pas comparé directement. Règle d'adoption
inchangée. Le secours payant de la consolidation de nuit est désactivé par défaut.

**Résultat de l'expérience 1 (2026-10-16, abonnement, base figée, jeu `764c9441f7b6`) :**

| Run | Taux correct B | Faux | Médiane de mots | Brier | Confiance quand faux |
|---|---|---|---|---|---|
| R1 (référence) | 77,9 % | 9 | 109 | 0,157 | 87 |
| R2 (référence, A/A) | 78,8 % | 9 | 111 | 0,159 | 88 |
| R3 (consigne) | 81,7 % | 7 | 121,5 | 0,132 | 89 |

- Bruit A/A : 1 point. Seuil pré-enregistré : moyenne 78,4 % + 3 points = 81,4 %. R3 = 81,7 %.
- `comparer` : R1 → R3 +3,8 pts, IC 95 % [−7,7 ; +15,4] ; R2 → R3 +2,9 pts, IC [−4,8 ; +11,5] ;
  aucune régression.
- **Décision : ADOPTÉ selon la règle.** Honnêtement : gain faible, non significatif, et le
  mécanisme supposé (réponses plus courtes) n'est PAS observé ; la sur-confiance quand c'est faux
  reste entière (~89). La modification est gardée parce qu'elle est peu coûteuse et ne dégrade
  rien ; la calibration reste le prochain chantier mesurable.
- Aucune invention sur les 9 pièges dans les trois runs.

## Révision après R4 (2026-10-16) : le bruit réel est par question

- R4 (briefing « moments froids ») : 76,9 % — au niveau de R1 (77,9 %) et R2 (78,8 %).
  R3 → R4 : −4,8 pts, IC apparié [−15,4 ; +5,8] : pas de régression selon la règle.
- MAIS entre R1 et R2, même code, 9 questions sur 52 ont changé de verdict : le bruit par
  question est grand, et l'écart entre les totaux (1 pt) le sous-estime (les changements se
  compensent). Le « +3,4 pts » de l'expérience 1 était très probablement du bruit : la consigne
  est gardée (inoffensive), mais AUCUN gain n'est revendiqué.
- **Règle d'adoption révisée pour toute expérience future** : au moins 3 runs par condition,
  score moyen par question, comparaison appariée par bootstrap ; ADOPTER seulement si
  l'intervalle à 95 % de la différence est entièrement au-dessus de 0 ; RÉGRESSION si
  entièrement en dessous. Coût : ~3 fois plus d'usage de l'abonnement par expérience.
