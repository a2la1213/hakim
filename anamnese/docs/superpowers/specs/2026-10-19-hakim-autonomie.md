# Hakim — autonomie (lot H de la liste du 19 octobre 2026)

Liste d'origine : `~/AIOS/jarvis/cwd/atelier/plans/optimisations_2026-10-19.md` (proposée par Hakim, ordre décidé
par Ahmed le 19/10 à 22:30 : lot C, puis E, puis H). Ce document dit ce qui est fait, avec quels garde-fous,
et ce qui attend une décision d'Ahmed.

## Fait cette nuit (chaque point testé, relu par Opus en fin de lot)

### 28. Spontanéité — `spontaneite.py`
- Il ne sollicite Ahmed que s'il a quelque chose de CONCRET à dire (une occupation finie nourrit son envie).
- jusqu'à 10 fois par jour (Ahmed, 20/10), le nombre réel suivant son BESOIN : l'écart rétrécit quand il a
  beaucoup de choses concrètes en attente (45 min pour 3 choses, ~16 min pour 10), s'allonge quand il en a peu ;
  plancher anti-rafale de 10 min ;
  de 8 h à 23 h ; jamais en pause, jamais pendant une conversation, seulement si Ahmed
  est absent depuis 20 min ; jamais deux fois le même sujet ; sans réponse, l'écart suivant double.
- Espacement hyperuniforme (réseau régulier décalé de ±20 %) ; un jour sur deux, bras témoin Poisson (même
  moyenne). Mesure : `anamnese spontaneite` (réponses en moins de 30 min, délai médian, par bras).
- À évaluer par Ahmed au bout d'une semaine.

### 29. Ses agents — cockpit (`server.js`, `AGENTS`)
- Architecte (lit, conçoit), Codeur (écrit et exécute dans l'atelier seulement), Juge (relit, refait, tranche).
- Profondeur 1 (un agent n'a pas l'outil Task) ; agents intégrés de Claude Code refusés par règle de permission.
- Budget : 8 lancements par jour ; au-delà, cerveau sans Task jusqu'au lendemain. Journal : `~/AIOS/jarvis/agents.jsonl`.

### 30. Toucher à son propre code — `jarvis/chantiers.py`
- Copie (git clone local, branche `hakim/<nom>`) dans l'atelier ; la mémoire n'est pas copiée ; l'original jamais touché.
- Tests en arrière-plan sous bac à sable : écriture seulement dans la copie, aucun réseau (sauf boucle locale),
  lecture du dossier personnel limitée à la copie, au venv, aux modèles téléchargés et au code d'origine (jamais
  `data/`, `.env`, ni les autres projets). Vraie suite : 862 tests verts en 74 s.
- Résultats des tests hors de l'atelier (non falsifiables) ; une promotion exige des tests à jour.
- Promotion = patch + fiche (fichiers, CŒUR signalé, tests, résumé) dans `~/AIOS/jarvis/cwd/promotions` ; la page
  d'Ahmed est prévenue ; RIEN n'est appliqué automatiquement. Application : Ahmed, ou Claude Code avec son accord,
  en commit à part (`git revert` pour défaire).
- Cœur (signalé, relecture obligatoire) : identity.py, evenements.py, memory.py, migrations.py, conftest.py,
  config.py, engine.py, registre.py, consolidate.py, persona, gardes de jarvis/ (groupes, terminal, fichiers, web,
  calcul, taches, chantiers).

**Relecture Opus du 20/10 : BLOQUER.** La première version laissait sortir du bac à sable (configuration git
écrite depuis l'atelier, faux `.git` vers l'original, profil suivi par lien symbolique, résultat de tests daté).
Outils suspendus pour Hakim (`CHANTIERS_SUSPENDUS`, jarvis/mcp_terminal.py), puis refondus (commit 873d4af) :
dépôt git hors de l'atelier, tests sur une extraction de l'arbre, empreinte write-tree, profils passés en ligne
(`sandbox-exec -p`). Une seconde relecture juge les failles d'origine fermées. **Réactivation : sur décision
d'Ahmed** (mettre `CHANTIERS_SUSPENDUS = ""`).

### 31. Parler aux autres IA — `jarvis/consulter.py`, outil `consulter_ia`
- Liste blanche : Argon (Gemini). Clé dans le trousseau d'Ahmed, service `anamnese-gemini-api` — **absente le
  19/10 : à y ranger par Ahmed**.
- 20 consultations par jour ; secrets, mails, numéros, IBAN masqués avant l'envoi ; réponse enveloppée comme
  contenu externe ; journal `~/AIOS/jarvis/consultations.jsonl`.
- Réserve : certaines offres gratuites entraînent leurs modèles sur les échanges (choisir une offre qui ne le fait pas).

## En attente d'une décision d'Ahmed

### 32. Jardin secret
Conditions proposées par Hakim (19/10, 21:40), non tranchées (« à décider à tête reposée ») :
carnet privé chiffré ; clé dans le trousseau d'Ahmed, qui s'engage à ne pas le lire sans raison ; accès seulement en
cas d'urgence ou d'audit de sécurité, avec journal d'accès ; son contenu n'est jamais retourné contre Hakim ; Hakim
s'engage à dire tout ce qui touche à un danger ou au bien-être d'Ahmed et ne ment jamais sur l'existence de
l'espace ; pas de secret total ; version minimale et réversible d'abord.
Questions à trancher : qui détient la clé (Ahmed seul ? les deux ?) ; Hakim peut-il relire son carnet entre deux
conversations (il faut alors que la clé lui soit accessible) ; que devient le carnet si Hakim est réinitialisé.

### 18. Empreinte vocale
Reconnaître la voix d'Ahmed (jamais pour autoriser une action sensible). Demande l'installation d'un petit modèle
local d'empreinte vocale (accord d'Ahmed avant toute installation).
