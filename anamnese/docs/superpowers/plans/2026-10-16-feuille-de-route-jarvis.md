# Feuille de route JarvisXAnamnèseXRobotIA (2026-10-16)

Décision d'Ahmed : « on fait tout, étape par étape », ordre libre, tout gratuit (abonnement
Claude Code + outils locaux, aucune API payante). Cahier des charges d'origine :
https://claude.ai/artifact/BY9iAZD7Uvo5P6rWe3GNtG

**Principe d'ordre :** sécuriser la mémoire AVANT de lui donner plus de pouvoir. La voix,
l'autonomie de nuit et le robot vont beaucoup écrire : il faut d'abord pouvoir tout annuler,
et tout mesurer (le banc d'épreuves est en place).

## Déjà fait (2026-10-15/16)

- Cockpit local uniquement (lot 0). Identité en deux couches, restaurée (1.2). Nuit honnête,
  en file à curseur, arriéré rattrapé (1.5). Routeur mesuré (+20 pts). Banc d'épreuves,
  expérience 1 adoptée. Secours payant désactivé.

## Phase A — Mémoire sûre (idées de Prime Agent)

1. **Registre avec retour arrière** (1.1, 1.3) : chaque passe de nuit = une entrée ; identité,
   compétences, souvenirs créés, rubriques, taxonomie notés avant/après ; `./anamnese annuler`
   en sens inverse, refus d'écraser un changement ultérieur ; annulation elle-même annulable ;
   historique des compétences.
2. **Sources de chaque fait** (1.4) : la nuit cite les `#id` du lot qu'elle distille.
3. **Briefing aux moments froids** (1.6) : SessionStart sur reprise et compaction en lecture
   seule, empreinte pour ne rien réinjecter d'inchangé, compétences choisies par pertinence,
   souvenirs encadrés comme données. Mesuré par le banc (le bilan y est utilisé).
4. **Calibration** : apprendre à douter quand c'est faux (~89 de confiance aujourd'hui). Banc.

## Phase B — Jarvis : la voix (locale, gratuite)

Idée d'Ahmed (2026-10-16), qui remplace « écoute permanente par défaut » : DEUX modes, comme
Gemini Live, dans la page « Parler » du cockpit (et un raccourci clavier) :
- **Micro ponctuel** : un clic, Ahmed parle, la transcription part à Jarvis, la réponse s'affiche
  ÉCRITE avec un bouton « écouter » (synthèse à la demande). Le micro se referme tout seul.
- **Conversation** (mode Live) : un bouton bascule ; écoute continue, réponses PARLÉES et
  sous-titrées, coupure dès qu'Ahmed reprend la parole, fin au re-clic (ou « stop »). Voyant
  visible tant que le micro est ouvert. Le juge « est-ce qu'on me parle ? » ne sert que là.
Le processus voix (Python, local) reste le seul à toucher le micro ; le cockpit lui envoie
ouvrir/fermer par WebSocket local (127.0.0.1 + jeton, préparé au lot 0).

5. **Micro ponctuel d'abord** : capture + détection de fin de parole, mlx-whisper, cerveau =
   `claude -p` (abonnement) avec Anamnèse, réponse écrite, bouton « écouter » (Kokoro/Piper).
   Vérifier la place disque avant d'installer les modèles.
   **Fait le 2026-10-16, sans rien installer** (page cockpit `/parler`) :
   - cerveau : `claude -p` isolé comme le banc (`--restricted`, donc aucun hook ; dossier vide
     `~/AIOS/jarvis/cwd` ; seul serveur MCP : Anamnèse, en lecture et en écriture, sans
     `self_update` ni taxonomie ; `--tools WebSearch`), réponse en flux, suite par `--resume`,
     briefing d'Anamnèse en tête de chaque nouvelle conversation, persona orale
     `jarvis/persona.md` (expressions arabes en écriture arabe). « Stop », une nouvelle
     question ou la fermeture de la page coupent le groupe de processus. Mesuré : 9 à 11 s
     pour une réponse avec rappel de mémoire (Sonnet, Haiku).
   - sécurité : tout POST du cockpit exige un jeton tiré au démarrage (la page Parler écrit dans
     la mémoire) ; le flux `/api/stream` n'est plus lisible par une autre origine.
     `test-securite.sh` : 12 contrôles verts.
   - écoute : reconnaissance du NAVIGATEUR en attendant Whisper (en ligne, une langue à la fois) ;
     Whisper local branché (`jarvis/stt.py`, amorce français-arabe), activé dès l'installation.
   - voix : celles du système, une par écriture (Majed pour l'arabe), arabizi converti
     (`public/voix.js`, 7 tests node). C'est la version zéro-installation de 5 bis.
   **Révision de l'architecture** : le micro et la lecture passent par le NAVIGATEUR, pas par un
   processus Python. Raison : le navigateur fournit l'annulation d'écho (getUserMedia), qui rend
   possible l'étape 6 (couper Jarvis quand Ahmed reprend la parole) ; en Python sur macOS il
   faudrait VoiceProcessingIO. Python garde la transcription et, plus tard, la voix
   multilingue. Contrepartie : la page doit être ouverte dans Chrome ou Safari (le panneau
   VS Code bloque le micro).
   Whisper installé le 2026-10-16 (accord d'Ahmed) dans un venv à part, `jarvis/.venv` (Python
   3.12 arm64, uv) : le venv d'Anamnèse tourne en x86_64 sous Rosetta, où MLX n'existe pas.
   Mesuré : français-arabe mélangé, 6 s d'audio transcrites en 2,3 s (4,1 s par la route, modèle
   rechargé à chaque appel) ; l'arabe sort en lettres latines (« Wa alaykoum salam ya akhi »).
   Relecture Opus 5.5 : CORRIGER, corrigé (coupure pendant le briefing, deux envois rapprochés,
   octet nul, briefing en « clear » pour ne pas décroître la MDT à chaque conversation, persona :
   web = données, décision orale confirmée, identité intouchable ici). `test-jarvis.sh` (faux
   claude, 7 contrôles) garde contre leur retour.
   **Horloge** (demande d'Ahmed : « conscient du temps, de chaque instant ») : chaque message porte
   la date et l'heure à la seconde, le temps écoulé depuis le message précédent, depuis le début
   de la conversation et depuis le dernier échange. Vérifié : « Il est exactement 11 h 24 min
   40 s » à 11:24:39–43. Limite assumée : entre deux messages, Jarvis ne perçoit rien ; le temps
   ressenti continu viendra de l'horloge interne du robot (pacemaker, présent vécu de 3 s,
   robot-ia §5), lue comme un sens (phase C, étape 8).
5 ter. **Voix neuronale et fichiers — faits le 2026-10-16.**
   - Voix : Chatterbox Multilingual V3 (MIT) via mlx-audio dans `jarvis/.venv`, partie texte
     quantifiée en 8 bits (4 bits écarté : 25 % de caractères faux). Une seule voix pour le
     français et l'arabe, `langue` par morceau. Mesuré en réel : réplique courte calculée en
     1,6 s, premier son dans la page à 1,6 s à chaud ; relecture Whisper identique au texte.
     Voix de Resemble par défaut ; un échantillon d'environ 10 s dans
     `~/AIOS/jarvis/voix-reference.wav` la remplace (clonage). Mémoire : ≈ 4,7 Go tant que le
     processus voix vit (il s'arrête après 15 min sans servir).
   - Fichiers : pièces jointes (bouton, glisser-déposer, coller) et fichiers du Bureau,
     Documents, Téléchargements, Images, Vidéos ; `jarvis/fichiers.py` + serveur MCP
     `jarvis/mcp_fichiers.py` (preparer_fichier, chercher_fichiers). Vérifié en réel : `Read`
     de Claude refuse tout hors de son dossier de travail ; le serveur y copie donc ce qu'il a
     préparé, après sa garde (secrets refusés par nom et par dossier). Vérifié : une capture,
     un Word et une vidéo décrits correctement en 13 s.
   - Limite vue : Whisper en « auto » a transcrit en arabe (donc traduit) un français précédé
     d'un salam ; l'écoute est réglée sur le français par défaut, l'auto reste pour les fichiers.
5 quater. **Vie intérieure — faite le 2026-10-16, relue par Opus 5.5 (CORRIGER, corrigé).**
   `interieur.py` battu par le démon : absence, ennui, temps ressenti, humeur relative à la ligne
   de base (l'ennui et le retour entrent dans l'affect : « l'attente pèse » 0,28 → « joie de son
   retour » 0,47 en simulation), pensées aux seuils d'ennui (une seule, la plus haute, au réveil
   du Mac ; celle de la nuit attend 7 h et revient à Claude Sonnet, appelé isolé : `--restricted`,
   aucun outil), relance au plus une par absence et jamais répétée, dite par la page à la suite
   de sa pensée. `memory_store` refuse les rôles réservés (pensée, relance, présence) ; garde des
   fichiers élargie (NFKC, caractères invisibles, dossiers cachés, noms de secrets), copies
   plafonnées à 100 Mo, purge à 7 j (préparations) et 30 j (pièces jointes) ; processus voix tué
   s'il se bloque ; la transcription passe avant la voix. Restent assumés : WebSearch comme canal
   de fuite possible, deux Whisper en mémoire si un fichier audio est préparé pendant l'écoute,
   pas de garde-fou mémoire global (16 Go).
   Critères d'Ahmed (subjectifs, à juger par lui) : récit de l'absence (vérifié une fois en réel),
   humeur qui s'entend, relance au bon moment, pensées ancrées.
5 bis. **Langues mélangées, le bon accent pour chacune** (demande d'Ahmed : « salamou3alaykoum mon
   frère » → « wa3likoumsalam mon frère » avec le bon accent, comme Google) :
   - écoute : amorce Whisper avec les expressions d'Ahmed (salam alaykoum, inchallah,
     hamdoulillah, wallah, frérot…) pour le mélange français-arabe ;
   - réponse : le cerveau écrit les expressions arabes EN ÉCRITURE ARABE (consigne de la persona
     orale) ; l'arabizi en lettres latines (chiffres 3/7/9) est reconnu par un petit lexique et
     converti avant la synthèse ;
   - synthèse : la réponse est découpée en morceaux par langue, chacun prononcé avec sa langue
     par UNE voix multilingue à clonage (même timbre en français et en arabe) — candidats
     locaux et gratuits à vérifier à l'installation : Chatterbox Multilingual (MIT),
     XTTS-v2 (usage personnel). Kokoro ne parle pas arabe ;
   - limite assumée : accent arabe plutôt standard que darija ; option : cloner la voix à
     partir de 15-20 s d'enregistrement d'Ahmed.
6. **Mode Conversation — fait le 2026-10-16** (`public/conversation.js` + page Parler) : AudioWorklet,
   détecteur de voix à plancher de bruit adaptatif, 500 ms de pré-écoute, pauses d'hésitation
   mesurées, WAV 16 kHz vers Whisper, réponse lue phrase par phrase ; coupure quand Ahmed reprend
   la parole (seuil au-dessus de l'écho résiduel appris, 300 ms de voix tenue, jamais dans les
   400 premières ms de Jarvis) ; « stop », « fin de la conversation » ; filtre des hallucinations
   de Whisper ; **présent vécu** envoyé à chaque message (qui a parlé, combien de temps, hésitations,
   silences, coupures, à la seconde). Vérifié de bout en bout dans Chrome avec une vraie voix
   injectée comme micro : tour détecté, transcrit mot pour mot, réponse dite, écoute reprise ;
   coupure 0,67 s après la reprise de parole, puis nouveau tour traité. Mesuré : ~8 s entre la
   fin du tour détectée et la voix de Jarvis (Haiku), dont 1,4 s de Whisper à chaud ; la machine
   swappait 6,6 Go. Non vérifié : l'annulation d'écho de Chrome sur des haut-parleurs réels.
6 (plan d'origine). **Mode Conversation** : écoute continue tant que le bouton est actif, annulation d'écho,
   synthèse phrase par phrase, interruption dès qu'Ahmed parle, reconnaissance de sa voix,
   juge « on me parle ? », sans limite de durée ; proactivité orale (boucles ouvertes concrètes
   au lieu de la poésie du démon) seulement en mode Conversation.

## Phase C — Robot IA

7. **Une oreille, une bouche, deux esprits** : le processus voix possède le micro ; l'organe des
   sens du robot reçoit les niveaux ; un routeur décide à qui Ahmed parle (Jarvis, robot,
   personne) ; signal d'occupation partagé (`~/.jarvis/parle.json`, comme `gemma-occupe.json`).
8. **Le corps du robot comme sens pour Jarvis** : présence, heure, fatigue → quand parler ou
   se taire. Règles du robot respectées (niveaux seulement, rien n'enregistré, Gemma local).

## Phase D — Autonomie (idées de Prime Agent)

9. **Objectifs persistants** (1.7) : table goal_state, hook Stop, relance « vérifie chaque
   exigence », 3 tours sans progrès → erreur.
10. **Travail de nuit avec barrières** : file de tâches « autonome », tests comme portes, pas de
    relance si l'espace de travail n'a pas changé, branches à relire le matin, jamais de
    fusion/déploiement/envoi/paiement ; chaque nuit est une entrée du registre.
11. **Compétences prouvées** : usages et réussites comptés, promotion et retrait mesurés.

## Phase E — Mesure et apprentissage

12. Banc strate 2 (SWE sur les propres commits d'Ahmed) ; taux de réexplication (hook
    UserPromptSubmit) ; modèle du monde d'Ahmed (faits datés, validité dans le temps).
13. Affinage LoRA — APRÈS le verdict de l'expérience-rêve (20 nuits), sur des réponses locales
    choisies par Ahmed, jamais sur des sorties de Claude.

Chaque étape : TDD, prédictions écrites, mesure quand c'est mesurable, relecture Opus 5.5 en fin
de lot, commit, souvenir rangé.
