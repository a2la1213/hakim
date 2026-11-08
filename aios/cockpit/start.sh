#!/bin/bash
# Lance le Cockpit Claude Code (serveur Node local) et l'ouvre dans le navigateur.
export PATH="/usr/local/bin:/Users/admin/.npm-global/bin:/usr/bin:/bin"
ROOT="/Users/admin/AIOS/cockpit"
PORT="${COCKPIT_PORT:-4317}"
cd "$ROOT" || exit 1
mkdir -p data

if lsof -ti tcp:"$PORT" >/dev/null 2>&1; then
  echo "Cockpit déjà en ligne sur le port $PORT"
else
  nohup node "$ROOT/server.js" > "$ROOT/data/server.log" 2>&1 &
  echo $! > "$ROOT/data/server.pid"
  # attendre que le port réponde
  for i in $(seq 1 20); do lsof -ti tcp:"$PORT" >/dev/null 2>&1 && break; sleep 0.2; done
  echo "Cockpit démarré (pid $(cat "$ROOT/data/server.pid"))"
fi
echo "→ http://localhost:$PORT"
[ "${COCKPIT_OPEN_BROWSER:-1}" = "1" ] && open "http://localhost:$PORT" 2>/dev/null || true
