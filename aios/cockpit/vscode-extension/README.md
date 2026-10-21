# AIOS — Claude Cockpit (extension VSCode)

Affiche le Cockpit Claude Code directement dans un panneau VSCode (webview vers le serveur local).

## Lancer en mode dev (le plus simple)
1. Ouvrir le dossier `~/AIOS/cockpit/vscode-extension` dans VSCode.
2. Appuyer sur **F5** (« Run Extension ») → une fenêtre VSCode de test s'ouvre.
3. `Cmd+Shift+P` → **AIOS: Ouvrir le Claude Cockpit**.

## Installer pour de bon (.vsix)
```bash
cd ~/AIOS/cockpit/vscode-extension
npx @vscode/vsce package        # produit aios-claude-cockpit-0.1.0.vsix
code --install-extension aios-claude-cockpit-0.1.0.vsix
```
Puis `Cmd+Shift+P` → **AIOS: Ouvrir le Claude Cockpit**.

> L'extension démarre le serveur local (`start.sh`) si besoin, puis charge `http://localhost:4317`.
> Le serveur lit l'inventaire (CLI/MCP/skills/agents), Anamnèse (humeur + pensées) et les transcripts de session.
