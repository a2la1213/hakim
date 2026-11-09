#!/bin/bash
# (09/11, agent vitesse) Hakim en natif sur le M4 : le cockpit (node), son claude CLI et le Python d'Anamnèse tournaient en x86_64
# traduit par Rosetta (« footprint » : « 64-bit (translated) »). Mesuré le 09/11 : un claude -p d'essai, 24,2 s de CPU en x86_64
# contre 14,2 s en arm64 (-41 %), même version 2.1.300 ; l'Anamnèse arm64 : 200 embeddings 0,22 → 0,15 s, mêmes paquets.
# Ce script ne tue rien et ne relance rien. Chaque étape garde l'ancien à côté (suffixe -x86-nov09) ; « retour » remet tout.
#
#   ./natif-arm64.sh verifier        ce qui est prêt (rien ne change)
#   ./natif-arm64.sh claude          le claude CLI en arm64 (sûr à chaud : les claude déjà lancés gardent l'ancien fichier)
#   ./natif-arm64.sh cockpit         le plist du cockpit pointe vers node arm64 (pris en compte au prochain bootout/bootstrap)
#   ./natif-arm64.sh python          le venv d'Anamnèse en arm64 (À FROID : refuse si un Python d'Anamnèse tourne encore)
#   ./natif-arm64.sh retour [claude|cockpit|python]   l'ancien remis (tout, ou une partie)
set -u
RT=/Users/admin/AIOS/.runtime
NODE_ARM="${NODE_ARM:-$RT/node-v26.4.0-darwin-arm64/bin/node}"
CLAUDE_ARM="${CLAUDE_ARM:-$RT/claude-arm64/package/claude}"
CLAUDE_EXE="${CLAUDE_EXE:-/Users/admin/.npm-global/lib/node_modules/@anthropic-ai/claude-code/bin/claude.exe}"
PLIST="${PLIST:-$HOME/Library/LaunchAgents/com.aios.cockpit.plist}"
ANA="${ANA:-/Users/admin/Desktop/anamnese}"
arch_de() { file -b "$1" 2>/dev/null | grep -oE 'arm64|x86_64' | head -1; }

verifier() {
  echo "node arm64     : $(arch_de "$NODE_ARM") $("$NODE_ARM" --version 2>/dev/null)"
  echo "claude arm64   : $(arch_de "$CLAUDE_ARM") $("$CLAUDE_ARM" --version 2>/dev/null)"
  echo "claude en place: $(arch_de "$CLAUDE_EXE") $("$CLAUDE_EXE" --version 2>/dev/null)"
  echo "cockpit plist  : $(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:0' "$PLIST")"
  echo "venv Anamnèse  : $(arch_de "$(readlink -f "$ANA/.venv/bin/python")") ; prêt à côté : $(arch_de "$(readlink -f "$ANA/.venv-arm64/bin/python" 2>/dev/null)")"
}

claude_arm() {
  [ "$(arch_de "$CLAUDE_EXE")" = arm64 ] && { echo "claude : déjà arm64"; return 0; }
  [ "$(arch_de "$CLAUDE_ARM")" = arm64 ] || { echo "claude arm64 absent"; return 1; }
  [ "$("$CLAUDE_ARM" --version)" = "$("$CLAUDE_EXE" --version)" ] || { echo "versions différentes : refus"; return 1; }
  ln -f "$CLAUDE_EXE" "$CLAUDE_EXE.x86-nov09"                       # l'ancien gardé (même fichier, un lien de plus)
  cp "$CLAUDE_ARM" "$CLAUDE_EXE.arm64.tmp" && chmod 755 "$CLAUDE_EXE.arm64.tmp" && mv -f "$CLAUDE_EXE.arm64.tmp" "$CLAUDE_EXE"
  echo "claude : $(arch_de "$CLAUDE_EXE") $("$CLAUDE_EXE" --version)"
}

cockpit_arm() {
  [ -x "$NODE_ARM" ] || { echo "node arm64 absent"; return 1; }
  [ -f "$PLIST.bak-nov09" ] || cp -p "$PLIST" "$PLIST.bak-nov09"
  /usr/libexec/PlistBuddy -c "Set :ProgramArguments:0 $NODE_ARM" "$PLIST"
  plutil -lint "$PLIST" >/dev/null && echo "cockpit : $(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:0' "$PLIST")"
  echo "  pris en compte au prochain : launchctl bootout gui/$(id -u)/com.aios.cockpit ; launchctl bootstrap gui/$(id -u) $PLIST"
}

python_arm() {
  [ "$(arch_de "$(readlink -f "$ANA/.venv-arm64/bin/python")")" = arm64 ] || { echo "venv arm64 absent"; return 1; }
  # à froid : aucun processus ne doit tenir l'ancien venv (ses modules compilés seraient remplacés sous ses pieds)
  local vivants; vivants=$(ps -axo pid=,command= | grep -E "Desktop/anamnese/(\.venv/bin/python|[a-z_]+\.py)|anamnese rappel-serveur|python@3\.14.*(daemon|corps|mcp_server|cli|maman)\.py" | grep -v grep | grep -v ".venv-separation\|jarvis/.venv/")
  if [ -n "$vivants" ]; then echo "refus : ces processus tiennent encore l'ancien venv (à arrêter d'abord, par leur service) :"; echo "$vivants" | cut -c1-160; return 1; fi
  mv "$ANA/.venv" "$ANA/.venv-x86-nov09" && mv "$ANA/.venv-arm64" "$ANA/.venv" && echo "python : $(arch_de "$(readlink -f "$ANA/.venv/bin/python")")"
}

retour() {
  local q="${1:-tout}"
  if [ "$q" = claude ] || [ "$q" = tout ]; then
    [ -f "$CLAUDE_EXE.x86-nov09" ] && mv -f "$CLAUDE_EXE.x86-nov09" "$CLAUDE_EXE" && echo "claude : $(arch_de "$CLAUDE_EXE")"
  fi
  if [ "$q" = cockpit ] || [ "$q" = tout ]; then
    [ -f "$PLIST.bak-nov09" ] && cp -p "$PLIST.bak-nov09" "$PLIST" && echo "cockpit : $(/usr/libexec/PlistBuddy -c 'Print :ProgramArguments:0' "$PLIST")"
  fi
  if [ "$q" = python ] || [ "$q" = tout ]; then
    [ -d "$ANA/.venv-x86-nov09" ] && mv "$ANA/.venv" "$ANA/.venv-arm64" && mv "$ANA/.venv-x86-nov09" "$ANA/.venv" && echo "python : $(arch_de "$(readlink -f "$ANA/.venv/bin/python")")"
  fi
  return 0
}

case "${1:-verifier}" in
  verifier) verifier ;;
  claude) claude_arm ;;
  cockpit) cockpit_arm ;;
  python) python_arm ;;
  retour) retour "${2:-tout}" ;;
  *) echo "usage : $0 verifier|claude|cockpit|python|retour [claude|cockpit|python]"; exit 2 ;;
esac
