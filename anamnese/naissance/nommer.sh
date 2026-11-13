#!/bin/bash
# Donner son nom à l'IA (ou le changer), puis relancer le cockpit pour qu'il le relise.
#   bash ~/Desktop/anamnese/naissance/nommer.sh --nom "<son nom>"
# Le prénom du créateur est repris de ~/AIOS/jarvis/nom.json (ou --createur "<prénom>").
set -euo pipefail
ICI="$(cd "$(dirname "$0")" && pwd)"
CREATEUR=""
if [ -f "$HOME/AIOS/jarvis/nom.json" ]; then
  CREATEUR="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("createur",""))' "$HOME/AIOS/jarvis/nom.json" 2>/dev/null || true)"
fi
ARGS=("$@")
case " $* " in *" --createur "*) ;; *) ARGS+=(--createur "${CREATEUR:-papa}") ;; esac
python3 "$ICI/nommer.py" "${ARGS[@]}"
if systemctl --user is-active --quiet naissance-cockpit 2>/dev/null; then
  systemctl --user restart naissance-cockpit && echo "Cockpit relancé."
elif [ -f "$ICI/demarrer.sh" ]; then
  bash "$ICI/demarrer.sh" --relancer
fi
