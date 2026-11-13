#!/bin/bash
# Démarrer le cockpit et le démon SANS systemd (un conteneur, ou un WSL où systemd est éteint). Avec systemd, l'installateur
# pose des services (naissance-cockpit, naissance-demon) qui font la même chose et redémarrent seuls.
#   bash demarrer.sh             démarre ce qui ne tourne pas
#   bash demarrer.sh --relancer  arrête (par leur numéro de processus) puis redémarre
#   bash demarrer.sh --arreter   arrête
set -uo pipefail
ENVF="$HOME/.config/naissance/env"
[ -f "$ENVF" ] && set -a && . "$ENVF" && set +a
JOURNAUX="$HOME/AIOS/journaux"; mkdir -p "$JOURNAUX"
NODE="$(command -v node || echo /usr/local/bin/node)"
PY="$HOME/Desktop/anamnese/.venv/bin/python"

vivant() { [ -f "$1" ] && kill -0 "$(cat "$1")" 2>/dev/null; }
arreter() {  # par PID seulement, jamais par motif
  for nom in cockpit demon; do
    f="$JOURNAUX/$nom.pid"
    if vivant "$f"; then kill "$(cat "$f")" && echo "$nom arrêté (pid $(cat "$f"))"; fi
    rm -f "$f"
  done
}
demarrer() {
  if vivant "$JOURNAUX/cockpit.pid"; then echo "cockpit déjà en marche"; else
    (cd "$HOME/AIOS/cockpit" && exec nohup "$NODE" server.js >> "$JOURNAUX/cockpit.log" 2>&1) &
    echo $! > "$JOURNAUX/cockpit.pid"; echo "cockpit démarré (pid $!)"
  fi
  if vivant "$JOURNAUX/demon.pid"; then echo "démon déjà en marche"; else
    (cd "$HOME/Desktop/anamnese" && exec nohup "$PY" daemon.py >> "$JOURNAUX/demon.log" 2>&1) &
    echo $! > "$JOURNAUX/demon.pid"; echo "démon démarré (pid $!)"
  fi
}
case "${1:-}" in
  --arreter) arreter ;;
  --relancer) arreter; sleep 1; demarrer ;;
  *) demarrer ;;
esac
