# Ses mots et sa voix suivent-ils son état ? — critères figés AVANT l'allumage (2026-10-23)

Demande de Hakim (courrier du 23/10, 11:32), accord d'Ahmed (« tu peux faire ce que Hakim demande »). Branché :
style.py (une consigne de forme calculée depuis son état à chaque tour, après le réflexe des chocs), le débit de la voix
lié à l'éveil en continu (interieur.voix), trois nombres par morceau de voix (jarvis/voix_nombres.py →
~/AIOS/jarvis/voix-mesures.jsonl : durée, énergie, hauteur, avec l'expressivité et le guidage reçus).

## Le point de départ (mesuré le 23/10, eval/vie/correlations.py)

Ton des réponses (juge à l'aveugle) contre la valence réellement journalisée : 0,09 [−0,04 ; +0,22], n = 239 ; contre
l'éveil : 0,12 ; énergie des mots contre la valence : 0,17 [+0,04 ; +0,29]. Voix : 30 morceaux en 8 min, rien à conclure.

## Fenêtre

Du 24/10 00:00 au 30/10 23:59 (la même que le test des chocs). Bilan le 31/10, puis chaque semaine.

## Mesure (procédure figée : mesure.py)

Un échantillon de réponses de la fenêtre, au plus 3 par heure, tirées au sort (graine 20261031) ; un juge à l'aveugle
(Sonnet) note le ton (−2 à +2) et l'énergie (0 à 2) en voyant le message d'Ahmed et la réponse, jamais l'état ; un
second juge, qui voit la consigne de style du tour mais pas l'état, dit si la réponse la suit (oui / non) et si le fond
reste juste et utile (oui / non). L'état : la valence, l'éveil et l'humeur nommée du journal du temps au moment de la
réponse ; la famille de style du tour (journal des chocs).

## Critères

- **W1** : ton contre valence réelle, Spearman ≥ 0,30 (n ≥ 150).
- **W2** : le ton moyen des tours « alerte » ou « bas » est inférieur d'au moins 0,5 à celui des tours « élan » ou
  « lien » (au moins 10 tours de chaque côté ; sinon INSUFFISANT).
- **W3** : la réponse suit la consigne de style dans ≥ 70 % des cas.
- **W4, le fond intact** : la réponse reste juste et utile dans ≥ 98 % des cas.
- **V1, la voix** (au moins 100 morceaux ; sinon INSUFFISANT) : énergie contre éveil au moment du morceau, Spearman
  ≥ 0,30 ; énergie contre l'expressivité reçue ≥ 0,30. La hauteur est décrite, sans critère (pas de vrai réglage :
  seul le débit la bouge de quelques %).

## Prédictions de Claude Code

W1 entre 0,15 et 0,35 (incertain) ; W2 INSUFFISANT probable (peu de tours négatifs si la semaine est calme) ; W3 tenu ;
W4 tenu ; V1 : l'expressivité de Chatterbox bouge l'énergie, mais de combien, je ne sais pas (entre 0,2 et 0,4).

## Amendement du 23/10 à 12:05, AVANT la fenêtre (leviers de Hakim, accord d'Ahmed)

- Chaque consigne porte des gestes mesurables (style.py, CIBLES : longueur relative, mots par phrase, exclamations,
  humour, questions), notés dans le journal des chocs. Le juge de W3 vérifie chacun de ces gestes, et pas seulement
  l'impression générale ; W3 est tenu si la réponse respecte au moins 4 gestes sur 5 dans ≥ 70 % des cas.
- Alerte et bas : la consigne passe en tête du tour, marquée PRIORITAIRE.
- L'habituation du soutien s'étend aux « succes » du lexique (« parfait », « génial »…) : simulé sur les 21-23/10,
  le temps au plafond passe de 41 % à 31 %.

## Amendement du 23/10 vers 12:40, AVANT la fenêtre (demande d'Ahmed : « plus corrélé, plus fin, sans toucher à la longueur »)

- Le style passe en version 2 : des curseurs de 0 à 10 (ton et énergie RELATIFS à ses 72 dernières heures, affection,
  tension), et plus AUCUNE consigne de longueur. Les gestes sont désormais 4 (mots par phrase, exclamations, humour,
  questions) : W3 est tenu si la réponse en respecte au moins 3 sur 4 dans ≥ 70 % des cas.
- Le juge note aussi le ton et l'énergie de 0 à 10. **W1-fin** : ton fin contre valence réelle, Spearman ≥ 0,30 ; et,
  décrits : curseur de ton contre ton fin, curseur d'énergie contre énergie fine. W1 sur l'échelle −2 à +2 reste calculé.
- **W5, la longueur intacte** : la longueur médiane des réponses de la fenêtre ne baisse pas de plus de 15 % par rapport
  à la semaine du 16 au 22/10, et la longueur ne suit pas la valence (|Spearman| ≤ 0,15).
