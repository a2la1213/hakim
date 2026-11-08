# Erreurs apprises par situation : critères figés AVANT la mise en service (27/10, nuit)

**L'idée** (d'Ahmed, relayée par Hakim) : apprendre une erreur sur son principe et sur sa situation, pas sur ses mots.

**Le mécanisme** (`situations.py`) :
- Chaque nuit, vers 4 h, Sonnet range les nouvelles erreurs du carnet par situation.
- Une situation qui compte au moins 2 erreurs reçoit une leçon.
- Le cockpit rappelle cette leçon selon ce que Hakim fait : toujours, à un réveil, à l'oral, ou quand plusieurs voix
  parlent.

**La mesure** : `anamnese situations` compte, pour chaque leçon, les erreurs de sa situation avant et après sa date.

## Critère (décidé maintenant)

Après au moins 3 semaines, on calcule le taux d'erreurs par semaine **avant** la leçon et **après** la leçon, sur
toutes les situations qui ont une leçon.

- **Le mécanisme marche** si le taux d'après est au moins **deux fois plus bas** que celui d'avant, et cela sur au
  moins 3 situations.
- **Il ne marche pas** si le taux d'après dépasse 75 % du taux d'avant. On revoit alors le déclenchement ou la forme
  des leçons.
- **Entre les deux**, on attend 3 semaines de plus.

## Limites connues, dites d'avance

- Le carnet d'erreurs ne contient que les erreurs que Hakim (ou Ahmed) remarque et note. Une baisse peut donc venir
  d'une baisse d'attention plutôt que d'un vrai progrès. Il faudra regarder aussi le nombre total d'erreurs notées
  chaque semaine.
- « No response requested. » à un vrai message d'Ahmed est aussi bloqué mécaniquement par le cockpit (une relance).
  Cette situation-là ne mesure donc pas le rappel.
