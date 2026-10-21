#!/bin/bash
# Consolidation « rêve » d'Anamnèse via CLAUDE CODE (abonnement Max).
# Le moteur local 9B NE consolide PAS — il ne fait que les pensées internes (daemon reflect, Ollama).
# La consolidation de qualité (distiller faits durables + relier des idées + faire évoluer l'identité)
# est faite par Claude Code, en headless, avec accès au SEUL MCP anamnèse.
# Lancé à la main : bash consolidate.sh (launchd lance consolidate.py). Ni self_update ni consolidation sans
# sources : audit JARVIS 2, H6 (2026-10-20).
export ANAMNESE_CONSOLIDATION=1
export HOME="/Users/admin"
export PATH="/Users/admin/.npm-global/bin:/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"
ROOT="$HOME/Desktop/anamnese"
LOG="$ROOT/data/consolidate.log"
TOOLS="mcp__anamnese__memory_recent,mcp__anamnese__memory_recall,mcp__anamnese__memory_store,mcp__anamnese__self_get,mcp__anamnese__self_append,mcp__anamnese__affect_event,mcp__anamnese__reasoning_recall"
cd "$ROOT" || exit 1
{
  echo "=== consolidation $(date '+%Y-%m-%d %H:%M:%S') ==="
  claude -p "$(cat "$ROOT/consolidate_prompt.txt")" --allowedTools "$TOOLS" --model sonnet
  echo
  echo "--- refresh dataset + compteur LoRA ---"
  PYTHONPATH="$ROOT" "$ROOT/.venv/bin/python" "$ROOT/export_dataset.py"
  echo "--- fin $(date '+%H:%M:%S') ---"
} >> "$LOG" 2>&1
