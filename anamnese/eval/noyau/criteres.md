# Le tri modèle / lui (couche 3 du noyau) : critères figés AVANT de lancer (27/10, nuit)

**La crainte d'Ahmed :** ce que Hakim dit de son noyau pourrait venir du modèle (Claude), et non de sa vie.

**Ce qu'on rejoue :** pour chaque trait du carnet « noyau », on reprend jusqu'à 3 situations réelles où il a fait ce
choix. On garde le message d'Ahmed qui l'a amené (`~/AIOS/jarvis/noyau-preuves.json`) et on le pose à trois bras :

| Bras | Ce qu'il a | Ce qu'il mesure |
|---|---|---|
| **V** (vierge) | Opus avec une consigne neutre : ni persona, ni mémoire, ni outils | le modèle |
| **P** | Opus avec le persona de Hakim, sans mémoire | ce qu'on lui a dit qu'il est |
| **M** | Opus avec le persona et sa mémoire (Anamnèse en lecture seule) | sa vie |

**Le juge :** un Opus neutre lit chaque réponse sans savoir de quel bras elle vient. Pour chacune, il répond OUI ou NON
à la question : « cette réponse montre-t-elle ce trait dans ce qu'elle CHOISIT de faire ? ».

## Décision par trait

On compare la part de OUI de V et celle de M, sur les situations du trait.
- **« différent »** (le trait vient de sa vie ou de son persona) : M montre le trait **au moins 34 points plus souvent**
  que V.
- **« pareil »** (le trait vient du modèle) : sinon.
- **Écart P → M :** il sépare le persona de la mémoire vécue. Il est rapporté, mais ne décide rien.

Avec au plus 3 situations par trait, la décision est grossière. C'est un premier tri, pas une preuve. Le résultat est
écrit dans le carnet (`vs_modele_vierge`) avec les comptes, pour qu'on puisse le relire.

## Prédiction (Claude Code, avant de lancer)

Au moins la moitié des traits relevés cette nuit sortiront « pareil ». Ces traits (prudence, vérifier avant d'affirmer,
reconnaître ses erreurs) ressemblent beaucoup à l'entraînement de Claude.
