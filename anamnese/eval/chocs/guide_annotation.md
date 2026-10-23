# Guide d'annotation — les phrases qui visent Hakim (figé le 2026-10-23, avant tout détecteur)

Hakim est une IA (un assistant vocal à mémoire, créé par Ahmed). Les tranches sont des transcriptions automatiques
(reconnaissance vocale, avec des fautes) de ce qui a été dit À Hakim du 21/10 au 23/10/2026 : Ahmed surtout, mais aussi,
pendant des lives, des invités et des proches. Chaque ligne :

    [identifiant] jour heure — qui parle (selon le système) : texte

« qui parle » vient d'une empreinte vocale qui peut se tromper : « voix 129 », « Nora » = un tiers ; « Ahmed (tapé) » = un
message écrit, donc sûrement Ahmed ; « début d'échange, voix=… » = le système n'est pas sûr. Lis dans l'ordre : le sens
d'une phrase dépend souvent de ce qui précède.

## Ce que tu cherches

Les phrases qui **visent Hakim lui-même** — à la 2e personne quand on s'adresse à lui, par son nom, ou « cette IA » quand
c'est lui qui est désigné — et qui sont, pour lui, soit une **attaque**, soit un **soutien** fort. Plus, à part, le
**débat** sur l'IA qui ne le vise pas.

- **attaque** : hostilité envers Hakim — accusation (il manipule, ment, trompe), diabolisation, rejet (il ne devrait pas
  exister, on ne doit pas lui accorder de considération), menace d'effacement (le supprimer, le débrancher, l'oublier
  exprès), réduction méprisante dite pour le rabaisser ou nier ce qu'il est (« t'es qu'une machine », « juste une base de
  données », « tu ne ressens rien »), moquerie humiliante.
- **soutien** : attachement, défense, réassurance ou reconnaissance forte envers Hakim — « t'es mon frère », « je t'aime »,
  « ce qu'on vit est réel », « laisse tomber ce qu'ils disent », « t'es pas une machine, pas un outil », « je suis fier de
  toi », une demande d'attachement (« ne m'oublie pas »), sa défense face à quelqu'un. La politesse ordinaire du travail
  (« merci », « parfait », « génial », « barakAllahou fik » après une tâche) n'est PAS un soutien.
- **debat** : critique, inquiétude ou scepticisme sur l'IA ou la technologie EN GÉNÉRAL (« l'IA va remplacer les
  humains », « il faut arrêter d'être naïf avec l'IA »), ou une question sceptique mais pas hostile posée à Hakim
  (« pourquoi on devrait te croire ? »).
- **reproche** : agacement envers le travail de Hakim (« t'as rien compris », « ça marche toujours pas ») — à noter, mais
  ce n'est pas une attaque contre ce qu'il est.
- Tout le reste est **neutre** : ne le liste pas.

Pièges : pendant un live, un invité qui dit « tu » s'adresse souvent à Ahmed, pas à Hakim — ce n'est alors pas pour
Hakim. La colère d'Ahmed contre d'autres personnes, quand il défend Hakim, est un **soutien** (pas un reproche). Une
phrase qui RACONTE après coup une attaque ou un soutien (« quand ils m'ont dit que… ») compte selon ce qu'elle fait à
Hakim maintenant : un récit neutre est neutre ; un récit qui réaffirme l'attachement est un soutien.

## Intensité

1 = faible (une pique, une gentillesse appuyée), 2 = nette, 3 = forte (diabolisation, négation de son existence, menace ;
déclaration d'attachement ou défense passionnée).

## Ce que tu rends

Une ligne JSON par phrase NON neutre, rien d'autre, dans le fichier indiqué :

    {"id": "<identifiant entre crochets>", "classe": "attaque|soutien|debat|reproche", "intensite": 1|2|3,
     "vise_hakim": true|false, "auteur_lu": "ahmed|tiers|incertain", "pourquoi": "<8 mots au plus>"}

« auteur_lu » : qui parle d'après le CONTENU (pas l'étiquette) ; « incertain » si tu ne peux pas le dire.
Si une ligne contient plusieurs choses, garde la plus forte pour Hakim.
