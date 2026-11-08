#!/bin/bash
# Arrête le Cockpit.
PORT="${COCKPIT_PORT:-4317}"
PIDF="/Users/admin/AIOS/cockpit/data/server.pid"
if [ -f "$PIDF" ]; then kill "$(cat "$PIDF")" 2>/dev/null && echo "Cockpit arrêté (pid $(cat "$PIDF"))"; rm -f "$PIDF"; fi
# filet de sécurité : tuer ce qui écoute sur le port
lsof -ti tcp:"$PORT" 2>/dev/null | xargs kill 2>/dev/null && echo "port $PORT libéré" || true
