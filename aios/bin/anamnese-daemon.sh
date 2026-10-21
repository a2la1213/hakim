#!/bin/bash
# Lanceur du daemon Anamnèse. Logs dans /tmp (hors TCC) : launchd ne peut pas écrire dans ~/Desktop.
exec >> /tmp/anamnese-daemon.log 2>&1
echo "=== [$(date '+%F %T')] démarrage lanceur (uid=$(id -u)) ==="
cd /Users/admin/Desktop/anamnese || { echo "ÉCHEC cd Desktop/anamnese"; exit 1; }
echo "cd OK · python: $(ls -la .venv/bin/python 2>&1 | head -1)"
exec /usr/bin/caffeinate -s /Users/admin/Desktop/anamnese/.venv/bin/python daemon.py
