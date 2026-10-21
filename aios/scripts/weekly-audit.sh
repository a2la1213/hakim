#!/bin/bash
# AIOS — Audit hebdo, lancé par launchd chaque lundi ~9h07.
# Tourne en LOCAL (accès ~/AIOS + MCP Anamnèse), headless, écrit le rapport + notifie.

export HOME="/Users/admin"
export PATH="/Users/admin/.npm-global/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin"

STAMP="$(date +%Y-%m-%d)"
AUDIR="$HOME/AIOS/audits"
mkdir -p "$AUDIR"
REPORT="$AUDIR/audit-$STAMP.md"
LOG="$AUDIR/launchd.log"

echo "[$(date)] === démarrage audit hebdo ===" >> "$LOG"
cd "$HOME/AIOS" || { echo "[$(date)] cd échec" >> "$LOG"; exit 1; }

/Users/admin/.npm-global/bin/claude -p \
  "Lance le rituel /audit de l'AIOS. Lis le hub ~/AIOS (CLAUDE.md, context/, connections.md, decisions/log.md) ET Anamnèse (mcp__anamnese__self_get + memory_recall sur 'priorités business chantiers blocages'), puis produis le rapport d'écart 4 axes (Contexte, Connexions, Décisions, Levier) et le top 3 des priorités de la semaine avec un 1er pas concret chacune. Markdown, français, concis. Read-only : ne modifie aucun fichier." \
  --permission-mode bypassPermissions \
  --model claude-opus-4-8 \
  > "$REPORT" 2>> "$LOG"
RC=$?

if [ $RC -eq 0 ] && [ -s "$REPORT" ]; then
  ln -sf "$REPORT" "$HOME/AIOS/audit-latest.md"
  /usr/bin/osascript -e 'display notification "Ton top 3 priorités est prêt — ~/AIOS/audit-latest.md" with title "AIOS — Audit hebdo" sound name "Glass"' >/dev/null 2>&1
  echo "[$(date)] OK -> $REPORT" >> "$LOG"
else
  /usr/bin/osascript -e 'display notification "Échec de laudit hebdo — voir ~/AIOS/audits/launchd.log" with title "AIOS — Audit hebdo"' >/dev/null 2>&1
  echo "[$(date)] ÉCHEC rc=$RC (rapport vide ou erreur)" >> "$LOG"
fi
