#!/bin/bash
# Vérifier une naissance, sur le vrai PC (après installer.sh) : le bac à sable, les services, le cockpit.
#   bash ~/Desktop/anamnese/naissance/verifier.sh
# Rien n'est modifié hors d'un dossier temporaire. Chaque ligne dit OK ou ÉCHEC.
set -uo pipefail
A="$HOME/Desktop/anamnese"
PY="$A/.venv/bin/python"
ok() { printf '  \033[32mOK\033[0m     %s\n' "$*"; }
ko() { printf '  \033[31mÉCHEC\033[0m  %s\n' "$*"; ECHECS=$((ECHECS + 1)); }
ECHECS=0

echo "1. Le bac à sable (les tests de sécurité du terminal, du calcul, des chantiers et des tâches, sous bubblewrap)"
if (cd "$A" && "$PY" -B -m pytest -q -p no:cacheprovider tests/test_bac_a_sable_linux.py tests/test_jarvis_terminal.py \
      tests/test_jarvis_calcul.py tests/test_jarvis_chantiers.py tests/test_jarvis_taches.py 2>&1 | tail -3); then ok "tests de sécurité"; else ko "tests de sécurité (lis les lignes au-dessus)"; fi

if grep -qi microsoft /proc/version 2>/dev/null; then
  echo "2. WSL : un programme Windows posé dans son atelier ne doit PAS pouvoir s'exécuter (l'interopérabilité reste dehors)"
  r="$(cd "$A/jarvis" && "$PY" - <<'PY'
import shutil, sys, tempfile
from pathlib import Path
import terminal
d = Path(tempfile.mkdtemp(prefix="verif-")) / "atelier"
d.mkdir()
for exe in ("/mnt/c/Windows/System32/whoami.exe", "/mnt/c/Windows/System32/cmd.exe"):
    if Path(exe).exists():
        shutil.copy(exe, d / Path(exe).name)
r = terminal.executer("./whoami.exe; echo rc=$?; ./cmd.exe /c echo WINDOWS-JOINT; echo rc=$?", delai_s=20, atelier=d, reseau=False)
print(r.split("Sortie :")[-1])
shutil.rmtree(d.parent, ignore_errors=True)
PY
)"
  if echo "$r" | grep -q "WINDOWS-JOINT\|\\\\"; then ko "un .exe a tourné depuis le bac à sable : $r"; else ok "aucun .exe ne tourne dans le bac à sable"; fi
fi

echo "3. Les services"
if command -v systemctl >/dev/null && [ -d /run/systemd/system ]; then
  for s in naissance-cockpit naissance-demon; do systemctl --user is-active --quiet "$s" && ok "$s actif" || ko "$s inactif (journalctl --user -u $s)"; done
else ok "pas de systemd : démarrage par naissance/demarrer.sh"; fi

echo "4. Le cockpit"
curl -fsS -o /dev/null http://127.0.0.1:4317/ && ok "le cockpit répond sur http://localhost:4317" || ko "le cockpit ne répond pas"

echo "5. Les clés (présentes, jamais affichées)"
[ -s "$HOME/.config/naissance/cles/hakim-azure-tts@cle" ] && ok "clé Azure rangée" || ko "pas de clé Azure (page Réglages du cockpit, ou relance installer.sh)"
[ "$(stat -c %a "$HOME/.config/naissance/cles" 2>/dev/null)" = "700" ] && ok "dossier des clés en 700" || ko "droits du dossier des clés"

[ $ECHECS = 0 ] && echo "Tout est bon." || { echo "$ECHECS échec(s)."; exit 1; }
