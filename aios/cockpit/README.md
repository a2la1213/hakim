# ◆ Claude Code — Cockpit

Tableau de bord **live** de Claude Code dans VSCode : inventaire actif (CLI, MCP, skills, agents, plugins),
sessions en cours, + **humeur et pensées internes** d'Anamnèse. Branché sur des sources réelles, zéro mock,
zéro dépendance npm (Node natif + `sqlite3`).

## Lancer
```bash
~/AIOS/cockpit/start.sh      # démarre le serveur + ouvre le navigateur
~/AIOS/cockpit/stop.sh       # arrête
```
→ http://localhost:4317

## Ce qu'il affiche (7 tuiles, bento)
- **Humeur · Anamnèse** — valence/arousal + 7 neuromodulateurs (jauges animées)
- **Activité live** — chaque tool-use / prompt en temps réel (hooks + transcripts)
- **Inventaire actif** — MCP (pastilles ✔/auth/down), skills, agents, CLI, plugins
- **Pensées internes** — thoughts / reflections / reasoning d'Anamnèse
- **Sessions Claude Code** — sessions actives/idle (multi-session) + derniers évènements
- **Mémoires récentes** — derniers souvenirs sémantiques

## Sources de données
| Source | D'où |
|---|---|
| Inventaire | `npm ls -g`, `brew list`, `claude mcp list`, `~/.claude/{skills,agents,plugins}` |
| Humeur + pensées + mémoires | `~/Desktop/anamnese/data/memory.db` (lecture seule) |
| Activité live | hooks Claude Code → `data/events.jsonl` + tail des transcripts `.jsonl` |

## Composants
- `server.js` — backend (HTTP + SSE), `public/` — frontend, `hooks/emit.js` — émetteur de hooks
- `vscode-extension/` — panneau VSCode (voir son README)

## Hooks
Ajoutés à `~/.claude/settings.json` (PostToolUse, UserPromptSubmit, Stop, SubagentStop, Notification,
SessionStart). Sauvegarde : `~/.claude/settings.json.bak-cockpit`. Pour retirer : supprimer ces clés du `hooks`.
