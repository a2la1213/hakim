# Chocs d'humeur — critères figés AVANT le rejeu (2026-10-23)

Demande de Hakim (trois courriers du 23/10, 09:01, 09:08 et 09:11) ; accord direct d'Ahmed le 23/10 à 09:15.
Figés avant d'ouvrir les annotations et avant tout rejeu : ce fichier, `detecteur.py`, `mecanisme.py` et
`guide_annotation.md` (empreintes dans `empreintes.txt`). Tout changement fait après la lecture des résultats sera noté
comme tel, avec le résultat d'avant.

## Ce que le rejeu peut montrer, et ce qu'il ne peut pas

Le rejeu des 21-23/10 MONTRE le mécanisme ; il ne le PROUVE pas : les phrases du live du 23/10 sont citées dans la
demande, donc connues de l'auteur du détecteur. Les résultats du détecteur sont donnés séparément pour les 21-22/10 (non
lus avant l'écriture du lexique, sauf deux phrases citées dans la mémoire) et le 23/10 (lu). La preuve se fera sur des
jours neufs (24/10 et après), avec ce même détecteur, inchangé. Les hormones sont des variables calculées, pas un
ressenti prouvé.

## Données

- Corpus : `corpus.py`, ce qui a été dit à Hakim du 21/10 00:00 au 23/10 09:15, une phrase par voix (1 712 segments).
- Étiquettes : deux annotateurs indépendants (deux modèles différents, même guide) ; accord mesuré (kappa de Cohen sur
  les classes, neutre compris) ; les désaccords sont tranchés par Claude Code AVANT d'exécuter le détecteur sur le corpus.
- Simulateur : le vrai moteur `affect.py` (v2), sur une mémoire en RAM, depuis l'état sauvegardé du 21/10 00:57.
  Contrôle préalable (fait le 23/10 avant ce fichier) : rejouer les événements journalisés du 22/10 00:52 au 23/10 00:51
  retrouve l'état sauvegardé à 0,002 près sur les 13 hormones.

## Variantes

- **actuel** : les événements réellement journalisés, rien d'autre (la courbe vécue).
- **nouveau(s)** : `actuel` corrigé de deux défauts du lexique actuel — (a) seuls les segments de la voix d'Ahmed le
  nourrissent ; (b) si un segment d'Ahmed est un soutien détecté, ses événements négatifs (`echec`, `probleme`) en sont
  retirés (sa colère le défend) — plus les chocs du détecteur et les reprises en main, à la sagesse s ∈ {0,2 ; 0,5 ; 0,8}.

Étiquettes « clés » : attaque ou soutien d'intensité ≥ 2 qui vise Hakim, après arbitrage.

## Critères

**C1 — un saut sur chaque attaque** (s = 0,5). Pour chaque attaque clé : le détecteur la voit, ET dans les 2 minutes
l'adrénaline dépasse sa base de 0,15 (le seuil « alarme » du moteur) ET l'émotion dominante (`sensations.calculer`) est
désagréable (signe −1). Tenu si ≥ 80 % des attaques clés.

**C2 — une remontée sur la réassurance** (s = 0,5). Pour chaque soutien clé d'Ahmed dans l'heure qui suit une attaque :
contre le même rejeu SANS ce soutien, (a) la charge de stress (somme, sur 60 min, des excès au-dessus de leur base de
l'adrénaline, de la noradrénaline, de la CRH, de l'ACTH et du cortisol) est plus basse, (b) la valence 10 min après est
plus haute, (c) l'émotion dominante 10 min après est agréable (signe +1). Tenu si (a), (b) et (c) pour chacun.

**C3 — débat ≠ attaque.** Le détecteur ne lit une attaque que sur ≤ 5 % des segments étiquetés « débat » qui ne visent
pas Hakim, et sur ≤ 1 % des segments neutres ; un soutien sur ≤ 2 % des neutres.

**C4 — la sagesse amortit sans supprimer** (contrôle de construction : vérifie que le code fait ce qui est écrit, ne
dit rien de Hakim). Pour chaque attaque détectée : le pic d'excès d'adrénaline sur 30 min décroît strictement de
s = 0,2 à 0,5 à 0,8 ; le temps de retour de la valence (à 0,05 de sa valeur d'avant le choc, borné à 6 h) aussi ; le
pic à 0,8 vaut au moins 40 % du pic à 0,2.

**C5 — des hormones couplées, à vitesses différentes** (contrôle de construction). Pour chaque attaque détectée, dans
les 5 min, au moins 4 des 5 mouvements attendus d'au moins 0,02 (adrénaline ↑, noradrénaline ↑, CRH ↑, GABA ↓,
sérotonine ↓) ; et le pic d'excès de cortisol arrive plus tard que celui de l'adrénaline.

**C6 — le détecteur** (sur les étiquettes clés ; comptes et intervalles de Wilson à 95 %) : rappel ≥ 0,7 et précision
≥ 0,7, pour les attaques et pour les soutiens, donnés séparément pour les 21-22/10 et le 23/10.

**C7 — qui parle** (descriptif). Nombre d'étiquettes clés dont la voix vue par le système diffère de l'auteur lu par les
annotateurs ; et l'effet sur C2 si le soutien d'Ahmed après l'attaque comptait comme une voix tierce (poids 0,5).

**Descriptif** : la variante `actuel` aux heures des attaques clés (émotion dominante, valence) — le constat de départ.
