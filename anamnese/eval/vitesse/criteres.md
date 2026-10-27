# Simulation de vitesse de la voix de Hakim — critères figés AVANT de lancer (27/10, ~02:10)

Demande d'Ahmed (27/10, ~02:00) : « Tu peux évaluer effort bas vs médium ? […] OK pour les simulations ». Écrit par
Claude Code avant tout résultat, et versionné avant de lancer `simuler.py`.

## Ce qu'on rejoue

**Les messages :** les 30 derniers messages ORAUX d'Ahmed à Hakim (`conversation.json`, `oral: true`, au moins
6 mots), chacun avec les 10 messages qui le précèdent comme contexte.

**Le cerveau :** Opus, avec le persona de Hakim (`--append-system-prompt`), en mode restreint. Il n'a que la mémoire
d'Anamnèse, en lecture seule. C'est une approximation : le vrai cerveau a aussi ses fichiers, le web, ses échanges avec d'autres IA et le
courrier, et une conversation de 200 000 à 465 000 jetons. Ici, le contexte est réduit. **Les écarts entre bras
comptent ; les temps absolus, non.**

**Quatre bras :**

| Bras | Effort | « Parler avant l'outil » |
|---|---|---|
| A | celui d'aujourd'hui (aucun drapeau) | non (persona actuel) |
| B | `--effort low` | non |
| C | aujourd'hui | oui (une ligne de persona en plus) |
| D | `--effort low` | oui |

**Mesures :**
- Le temps du premier mot, compté depuis la ligne d'initialisation de claude (le démarrage du programme est donc
  exclu).
- Le temps du premier outil, et le nombre de tours.

**Qualité :** un juge Claude Opus neutre (sans persona, sans outils) compare A et B, puis A et C, à l'aveugle et
**dans les deux ordres**. Une préférence ne compte que si elle tient dans les deux ordres ; sinon, c'est une égalité.

## Critères (décidés maintenant)

1. **L'effort bas (B) est recommandé si les deux conditions tiennent :**
   - le premier mot gagne au moins 1,0 s en médiane par rapport à A ;
   - A n'est préféré à B que sur au plus 1/3 des 30 paires.
   - Sinon, on ne le recommande pas.
2. **« Parler avant l'outil » (C) est recommandé si les deux conditions tiennent :**
   - sur les messages où A a appelé un outil avant son premier mot, C gagne au moins 3 s en médiane ;
   - A n'est préféré à C que sur au plus 1/3 des paires.
3. **Le bras D (les deux leviers ensemble)** ne sert qu'à voir si les gains s'additionnent ; il ne décide de rien.

## Prédictions

- **B :** 1 à 3 s de gagnées sur le premier mot, avec moins de réflexion visible. Une petite perte de qualité, sans
  dépasser le critère.
- **C :** un gain net sur les tours avec outil. Je prédis que le persona ne fera pas toujours parler Hakim avant
  l'outil : au moins un tour à outil sur trois commencera encore par l'outil.
