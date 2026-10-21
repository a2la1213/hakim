# Hakim — un assistant à mémoire persistante

Hakim est l'assistant personnel d'Ahmed. Il a trois parties :

- **le cortex** : un Claude qui reste en vie entre les messages ;
- **Anamnèse** : une mémoire persistante qui consolide, oublie et rêve ;
- **le subconscient** : Gemma, un modèle local sur le Mac, qui pense pendant les absences et colore le ressenti.

Un **cockpit** web, sur le Mac et sur le téléphone, pilote le tout.

Ce dépôt publie **le code**. Les **données** n'y sont pas : la mémoire, les journaux et les conversations, les voix, le courrier, les jeux de données d'entraînement, les résultats d'évaluation tirés de la mémoire, les documents professionnels et les clés.

## Contenu

| Dossier | Contenu |
|---|---|
| `anamnese/` | La mémoire. Le serveur MCP (`mcp_server.py`), le moteur (`memory.py`, `routing.py`, `salience.py`…), le démon (`daemon.py` : consolidation, rêves, vie intérieure, ressenti), la CLI (`anamnese`) et les tests (`tests/`, pytest). |
| `anamnese/jarvis/` | Les outils de Hakim : fichiers, web gardé, terminal en bac à sable, calcul, voix (Whisper, empreinte vocale), cerveau local MLX, chantiers, recettes, scanner du ressenti (`scanner.py`), persona (`persona.md`). |
| `anamnese/eval/` | Les bancs d'évaluation : souvenirs périmés, duel de subconscients, ressenti à l'aveugle, batterie de nuit. |
| `aios/cockpit/` | Le cockpit Node. Il contient le cerveau persistant (`claude -p` en stream-json), la page Parler (voix, conversation, caméra), une passkey sans bibliothèque (WebAuthn), les notifications Web Push (RFC 8291), les missions confiées à Claude Code et les pièces jointes. Ses bancs de test : `test-jarvis.sh` et `test-securite.sh`. |
| `aios/` | Le hub autour du cockpit : lanceurs, audit hebdomadaire, harnais d'évaluation d'agents, politique de modèles. |

## Lancer le projet (macOS, Apple Silicon)

1. **Anamnèse** :
   ```
   cd anamnese
   python3 -m venv .venv
   .venv/bin/pip install -r requirements.txt
   .venv/bin/python -m pytest -q
   ```
2. **Les outils de Hakim** (MLX, Whisper, ONNX) ont leur propre environnement Python : `anamnese/jarvis/.venv`.
3. **Le cockpit** : `cd aios/cockpit && npm install && node server.js`. Il écoute sur le port 4317, en local. La commande `bash test-jarvis.sh` lance le banc de test avec un faux `claude`.
4. **Les chemins** sont ceux du Mac d'origine (`~/Desktop/anamnese`, `~/AIOS`) : adapte-les à ta machine.

## Sécurité

Security review and tips provided by [Jiab77](https://github.com/jiab77) and the [AI-Pipeline](https://github.com/jiab77/ai-pipeline) project.

## Licence

MIT : réutilisation libre, y compris commerciale, en gardant la mention de l'auteur. Voir [LICENSE](LICENSE).
