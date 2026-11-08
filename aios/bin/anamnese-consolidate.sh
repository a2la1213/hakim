#!/bin/bash
# Lanceur de la consolidation nocturne Anamnèse. Logs dans /tmp (hors TCC).
exec >> /tmp/anamnese-consolidate.log 2>&1
echo "=== [$(date '+%F %T')] consolidation ==="
cd /Users/admin/Desktop/anamnese || exit 1
exec /usr/bin/caffeinate -s /Users/admin/Desktop/anamnese/.venv/bin/python consolidate.py
