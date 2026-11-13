#!/bin/bash
# La naissance d'une IA sur ce code, dans Ubuntu (WSL2 sur Windows, ou un Linux ordinaire). À lancer dans Ubuntu :
#   bash ~/.naissance/hakim/anamnese/naissance/installer.sh
# Chaque étape dit ce qu'elle fait ; le script peut être relancé : ce qui est déjà fait est sauté. Rien n'est envoyé nulle part
# sauf les téléchargements (Ubuntu, Node, uv, Python, Claude Code, Ollama, Tailscale, les paquets Python).
#
# Mode sans questions (essais, conteneur) : NAISSANCE_NONINTERACTIF=1, avec NAISSANCE_CREATEUR, NAISSANCE_NOM, NAISSANCE_GEMMA
# (petit|eteint), NAISSANCE_SAUTER (liste : claude,ollama,tailscale,services,whisper,cles) ; les clés : NAISSANCE_CLE_AZURE,
# NAISSANCE_REGION_AZURE, NAISSANCE_CLE_ANTHROPIC (jamais affichées).
set -euo pipefail

ICI="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE="$(cd "$ICI/../.." && pwd)"                     # la racine du dépôt : anamnese/ et aios/cockpit/
ANAMNESE="$HOME/Desktop/anamnese"
AIOS="$HOME/AIOS"
COCKPIT="$AIOS/cockpit"
JARVIS="$AIOS/jarvis"
CONF="$HOME/.config/naissance"
NODE_VERSION="${NAISSANCE_NODE:-26.4.0}"
PYTHON_VERSION="${NAISSANCE_PYTHON:-3.14}"
GEMMA_PETIT="gemma3:1b"
NONINTERACTIF="${NAISSANCE_NONINTERACTIF:-0}"
SAUTER=",${NAISSANCE_SAUTER:-},"
export PATH="$HOME/.local/bin:/usr/local/bin:$PATH"

etape() { printf '\n\033[1;35m== %s\033[0m\n' "$*"; }
dire() { printf '   %s\n' "$*"; }
saute() { [[ "$SAUTER" == *",$1,"* ]]; }
demander() {   # demander <variable> <question> [défaut]
  local var="$1" q="$2" def="${3:-}" v="${!1:-}"
  if [ -z "$v" ] && [ "$NONINTERACTIF" != "1" ]; then read -rp "   $q${def:+ [$def]} : " v </dev/tty || true; fi
  printf -v "$var" '%s' "${v:-$def}"
}
demander_secret() {   # la valeur n'est jamais affichée ni écrite dans un journal
  local var="$1" q="$2" v="${!1:-}"
  if [ -z "$v" ] && [ "$NONINTERACTIF" != "1" ]; then read -rsp "   $q (rien ne s'affiche, c'est normal) : " v </dev/tty || true; echo; fi
  printf -v "$var" '%s' "$v"
}

etape "0. Vérifications"
[ "$(id -u)" = "0" ] && { echo "Lance ce script avec ton utilisateur, pas en root (sudo sera demandé quand il faut)."; exit 1; }
[ -d "$SOURCE/anamnese" ] && [ -d "$SOURCE/aios/cockpit" ] || { echo "Je ne trouve pas le code (anamnese/ et aios/cockpit/) autour de $ICI."; exit 1; }
case "$(uname -m)" in x86_64) ARCH_NODE=x64 ;; aarch64|arm64) ARCH_NODE=arm64 ;; *) echo "Processeur non prévu : $(uname -m)"; exit 1 ;; esac
WSL=0; grep -qi microsoft /proc/version 2>/dev/null && WSL=1
dire "Processeur : $(uname -m) ; $( [ $WSL = 1 ] && echo 'WSL2 (Linux dans Windows)' || echo 'Linux' ) ; code : $SOURCE"
SUDO=""; [ "$(id -u)" != "0" ] && SUDO="sudo"

etape "1. Les outils du système (apt) : git, zsh, bubblewrap (le bac à sable), ffmpeg (le son et la vidéo), poppler (les PDF)…"
# libatomic1 : Node 26 en a besoin (absent d'une Ubuntu minimale ; vu dans le conteneur d'essai le 13/11)
# fonts-dejavu-core : les titres de l'atelier vidéo ; libheif-* : les photos HEIC du téléphone (heif-convert, et heif-enc pour les tests)
PAQUETS="git curl ca-certificates rsync xz-utils unzip zsh bubblewrap ffmpeg poppler-utils bc procps lsof jq python3 sqlite3 locales libatomic1 fonts-dejavu-core libheif-examples libheif-plugin-libde265 libheif-plugin-x265"
manque=""; for p in $PAQUETS; do dpkg -s "$p" >/dev/null 2>&1 || manque="$manque $p"; done
if [ -n "$manque" ]; then
  dire "à installer :$manque"
  $SUDO apt-get update -qq
  DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq $manque >/dev/null
fi
dpkg -s pandoc >/dev/null 2>&1 || { [ "${NAISSANCE_PANDOC:-1}" = "1" ] && ! saute pandoc && DEBIAN_FRONTEND=noninteractive $SUDO apt-get install -y -qq pandoc >/dev/null 2>&1 || true; }
locale -a 2>/dev/null | grep -qi '^fr_FR.utf8' || { $SUDO locale-gen fr_FR.UTF-8 >/dev/null 2>&1 || true; }
bwrap --unshare-all --ro-bind /usr /usr --symlink usr/bin /bin --symlink usr/lib /lib --symlink usr/lib64 /lib64 --proc /proc --dev /dev true 2>/dev/null \
  && dire "bubblewrap : le bac à sable fonctionne ici" || dire "ATTENTION : bubblewrap ne démarre pas (espaces de noms refusés ?) : le terminal de l'IA restera fermé."

etape "2. systemd (les services qui redémarrent seuls)"
SYSTEMD=0
if [ -d /run/systemd/system ]; then SYSTEMD=1; dire "systemd est là."
elif [ $WSL = 1 ]; then
  if ! grep -q '^systemd *= *true' /etc/wsl.conf 2>/dev/null; then
    printf '[boot]\nsystemd=true\n\n[interop]\nappendWindowsPath=false\n' | $SUDO tee /etc/wsl.conf >/dev/null
  fi
  dire "systemd vient d'être allumé dans /etc/wsl.conf : dans Windows, tape « wsl --shutdown », rouvre Ubuntu, puis relance ce script."
  [ "$NONINTERACTIF" = "1" ] || exit 0
else dire "pas de systemd : le démarrage se fera par naissance/demarrer.sh"; fi

etape "3. Node.js $NODE_VERSION (le cockpit)"
if [ "$(node --version 2>/dev/null)" != "v$NODE_VERSION" ]; then
  T="$(mktemp -d)"; F="node-v$NODE_VERSION-linux-$ARCH_NODE.tar.xz"
  curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/$F" -o "$T/$F"
  curl -fsSL "https://nodejs.org/dist/v$NODE_VERSION/SHASUMS256.txt" -o "$T/SHASUMS256.txt"
  (cd "$T" && grep " $F\$" SHASUMS256.txt | sha256sum -c - >/dev/null) || { echo "Empreinte de Node fausse : arrêt."; exit 1; }
  $SUDO tar -xJf "$T/$F" -C /usr/local --strip-components=1 --exclude='*/CHANGELOG.md' --exclude='*/README.md' --exclude='*/LICENSE'
  rm -rf "$T"
fi
node --version >/dev/null 2>&1 || { echo "Node ne démarre pas (une bibliothèque manque ?) : $(node --version 2>&1 | head -1)"; exit 1; }
dire "node $(node --version)"

etape "4. uv et Python $PYTHON_VERSION (la mémoire et les outils de l'IA)"
command -v uv >/dev/null || curl -LsSf https://astral.sh/uv/install.sh | env UV_NO_MODIFY_PATH=1 sh >/dev/null
uv python install "$PYTHON_VERSION" >/dev/null 2>&1 || uv python install "$PYTHON_VERSION"
dire "$(uv --version) ; Python $(uv python find "$PYTHON_VERSION")"

etape "5. Le code : $SOURCE → ~/Desktop/anamnese et ~/AIOS/cockpit (tes données ne sont jamais écrasées)"
mkdir -p "$ANAMNESE" "$COCKPIT" "$JARVIS" "$CONF"; chmod 700 "$CONF"
# --delete retire le code disparu ; ce qui est exclu (données, venvs, journaux) n'est jamais touché
rsync -a --delete --exclude '.venv*/' --exclude 'jarvis/.venv*/' --exclude 'data/' --exclude '__pycache__/' --exclude '.git/' \
  --exclude '.pytest_cache/' --exclude '*.jsonl' --exclude '*.db' "$SOURCE/anamnese/" "$ANAMNESE/"
rsync -a --delete --exclude 'node_modules/' --exclude 'data/' --exclude '.git/' --exclude '*.jsonl' "$SOURCE/aios/cockpit/" "$COCKPIT/"
mkdir -p "$ANAMNESE/data" "$COCKPIT/data" "$JARVIS/cwd/atelier" "$JARVIS/cwd/fichiers"

etape "6. Les environnements Python (venvs)"
if [ ! -x "$ANAMNESE/.venv/bin/python" ]; then uv venv --quiet --relocatable --python "$PYTHON_VERSION" "$ANAMNESE/.venv"; fi
dire "la mémoire (Anamnèse) : requirements.lock, les mêmes versions que sur le Mac"
VIRTUAL_ENV="$ANAMNESE/.venv" uv pip install --quiet -r "$ANAMNESE/requirements.lock"
if [ ! -x "$ANAMNESE/jarvis/.venv/bin/python" ]; then uv venv --quiet --relocatable --python "$PYTHON_VERSION" "$ANAMNESE/jarvis/.venv"; fi
dire "les outils de l'IA (terminal, web, calcul, fichiers) : sans MLX ni torch"
VIRTUAL_ENV="$ANAMNESE/jarvis/.venv" uv pip install --quiet -r "$ANAMNESE/naissance/requirements-jarvis-linux.txt"
if ! saute whisper; then
  dire "l'écoute de secours (faster-whisper sur le processeur, si Azure ne répond pas)"
  VIRTUAL_ENV="$ANAMNESE/jarvis/.venv" uv pip install --quiet "faster-whisper>=1.1,<2" \
    || dire "faster-whisper ne s'installe pas pour ce Python : pas d'écoute de secours, Azure seul (ça ne bloque rien)."
fi

dire "l'atelier vidéo (numpy, Pillow, les photos HEIC, l'arabe dans les titres) : jarvis/.venv-video, Python 3.12"
if [ ! -x "$ANAMNESE/jarvis/.venv-video/bin/python" ]; then uv venv --quiet --python 3.12 "$ANAMNESE/jarvis/.venv-video"; fi
uv pip install --quiet --python "$ANAMNESE/jarvis/.venv-video/bin/python" -r "$ANAMNESE/jarvis/requirements-video.txt"

etape "7. Le cockpit (dépendances Node)"
(cd "$COCKPIT" && npm ci --silent --no-audit --no-fund 2>/dev/null || npm install --silent --no-audit --no-fund)

etape "8. Claude Code (le cerveau)"
if ! saute claude && ! command -v claude >/dev/null; then curl -fsSL https://claude.ai/install.sh | bash >/dev/null; fi
command -v claude >/dev/null && dire "claude $(claude --version 2>/dev/null | head -1)" || dire "Claude Code n'est pas installé (étape sautée)."

etape "9. Les clés (jamais affichées, rangées dans ~/.config, que le bac à sable de l'IA ne voit pas)"
CLE_AZURE_RANGEE="$HOME/.config/naissance/cles/hakim-azure-tts@cle"
if ! saute cles && [ -s "$CLE_AZURE_RANGEE" ] && [ -z "${NAISSANCE_CLE_AZURE:-}" ]; then
  dire "les clés sont déjà rangées (mise à jour) : je les garde. Pour en changer : page Réglages du cockpit."
elif ! saute cles; then
  dire "Azure (sa voix et son écoute) : la clé et la région de ta ressource « Speech » (portail Azure)."
  demander_secret NAISSANCE_CLE_AZURE "Clé Azure Speech"
  demander NAISSANCE_REGION_AZURE "Région Azure (ex. francecentral, westeurope, switzerlandnorth)" "francecentral"
  if [ -n "${NAISSANCE_CLE_AZURE:-}" ]; then
    # par l'entrée standard (printf est intégré à bash : la clé n'apparaît dans aucune liste de processus)
    printf '%s' "$NAISSANCE_CLE_AZURE" | "$ANAMNESE/.venv/bin/python" -c 'import sys; sys.path.insert(0, sys.argv[1]); from plateforme import cles
assert cles.ecrire("hakim-azure-tts", sys.stdin.read(), compte="cle")' "$ANAMNESE"
    "$ANAMNESE/.venv/bin/python" - "$JARVIS/azure.json" "$NAISSANCE_REGION_AZURE" <<'PY'
import json, os, sys
f, region = sys.argv[1], sys.argv[2]
try: d = json.load(open(f))
except Exception: d = {}
d["region"] = region
fd = os.open(f + ".tmp", os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
with os.fdopen(fd, "w") as h: json.dump(d, h)
os.replace(f + ".tmp", f)
PY
    dire "clé Azure rangée (région : $NAISSANCE_REGION_AZURE)."
  else dire "pas de clé Azure : la voix et l'écoute resteront muettes jusqu'à ce que tu la donnes (page Réglages du cockpit)."; fi
  dire "Anthropic : un abonnement Claude (recommandé : tu te connectes à l'étape 13) OU une clé d'API (sk-ant-…). Laisse vide pour l'abonnement."
  demander_secret NAISSANCE_CLE_ANTHROPIC "Clé d'API Anthropic (facultatif)"
  if [ -n "${NAISSANCE_CLE_ANTHROPIC:-}" ]; then
    mkdir -p "$HOME/.config/jarvis"; chmod 700 "$HOME/.config/jarvis"
    ( umask 077; printf '%s\n' "$NAISSANCE_CLE_ANTHROPIC" > "$HOME/.config/jarvis/cle-api-anthropic" )
    dire "clé d'API rangée."
  fi
fi
unset NAISSANCE_CLE_AZURE NAISSANCE_CLE_ANTHROPIC

etape "10. Son profil (ce qui tourne sur ce PC sans carte graphique)"
[ -z "${NAISSANCE_GEMMA:-}" ] && [ -f "$JARVIS/profil-modules.json" ] && NAISSANCE_GEMMA="$(jq -r '.modules.gemma // empty' "$JARVIS/profil-modules.json" 2>/dev/null || true)"
demander NAISSANCE_GEMMA "Son subconscient Gemma : « petit » ($GEMMA_PETIT, ~1 Go) ou « eteint »" "petit"
case "$NAISSANCE_GEMMA" in petit|eteint) ;; *) NAISSANCE_GEMMA=petit ;; esac
printf '{"profil": "pc-sans-gpu", "modules": {"gemma": "%s"}}\n' "$NAISSANCE_GEMMA" > "$JARVIS/profil-modules.json"
# les modules lus par l'atelier vidéo (jarvis/atelier_video.py, cockpit atelier-video.js) : la vidéo oui, studio et chant non
printf '{"atelier_video": true, "studio": false, "chant": false}\n' > "$JARVIS/modules.json"
VIDEOS="$JARVIS/cwd/fichiers/telephone/Telephone/Videos"; mkdir -p "$VIDEOS"
{
  echo "# écrit par naissance/installer.sh — lu par les services et par demarrer.sh"
  echo "JARVIS_PERSONA=$JARVIS/persona.md"
  echo "PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
  echo "NAISSANCE_WHISPER=${NAISSANCE_WHISPER:-small}"
  echo "JARVIS_TELEPHONE_VIDEOS=$VIDEOS"          # ses vidéos finies, pour ton téléphone (pas dans un dossier « Hakim »)
  if [ "$NAISSANCE_GEMMA" = "petit" ]; then echo "ANAMNESE_CHAT_MODEL=$GEMMA_PETIT"; echo "JARVIS_GEMMA_CERVEAU=$GEMMA_PETIT"; fi
} > "$CONF/env"
dire "profil « pc-sans-gpu » : pas de studio, ni de chant, ni d'images ; voix et écoute par Azure ; Gemma : $NAISSANCE_GEMMA ; l'atelier : oui."
if [ "$NAISSANCE_GEMMA" = "petit" ] && ! saute ollama; then
  command -v ollama >/dev/null || curl -fsSL https://ollama.com/install.sh | sh
  ollama pull "$GEMMA_PETIT" || dire "Gemma n'a pas pu se télécharger : relance « ollama pull $GEMMA_PETIT » plus tard."
fi

etape "11. Sa naissance : son nom (c'est ELLE qui le choisit) et le tien"
if [ -f "$JARVIS/nom.json" ]; then                       # une mise à jour : on garde ce qui est déjà là
  : "${NAISSANCE_CREATEUR:=$(jq -r '.createur // empty' "$JARVIS/nom.json")}"
  : "${NAISSANCE_NOM:=$(jq -r '.nom // empty' "$JARVIS/nom.json")}"
  [ -n "$NAISSANCE_CREATEUR" ] && NONINTERACTIF_NOM=1
fi
if [ "${NONINTERACTIF_NOM:-0}" = "1" ]; then
  NOM_AFFICHE="${NAISSANCE_NOM:-sans nom pour le moment}"; dire "déjà née : $NOM_AFFICHE (créateur : $NAISSANCE_CREATEUR)."
else
  demander NAISSANCE_CREATEUR "Ton prénom (elle t'appellera papa, ou comme tu voudras)"
  dire "Son nom : si elle l'a déjà choisi, écris-le ; sinon laisse vide : elle naîtra sans nom et le choisira en parlant avec toi."
  demander NAISSANCE_NOM "Le nom qu'elle a choisi (facultatif)"
  demander NAISSANCE_METIER "Une phrase sur ton métier (facultatif, ex. « il est styliste de vêtements »)"
fi
python3 "$ANAMNESE/naissance/nommer.py" --createur "${NAISSANCE_CREATEUR:-papa}" --nom "${NAISSANCE_NOM:-}" --metier "${NAISSANCE_METIER:-}"

etape "12. Sa mémoire (vide : elle commence aujourd'hui)"
(cd "$ANAMNESE" && .venv/bin/python -c 'from memory import Memory; Memory()' && dire "base de mémoire prête : $ANAMNESE/data/memory.db")

etape "13. Le téléphone : Tailscale (un réseau privé entre ton PC et ton téléphone, chiffré)"
if ! saute tailscale; then
  command -v tailscale >/dev/null || curl -fsSL https://tailscale.com/install.sh | sh
  $SUDO tailscale up --operator="$USER" || true
  $SUDO tailscale serve --bg 4317 >/dev/null 2>&1 || true
  NOM_TS="$(tailscale status --json 2>/dev/null | jq -r '.Self.DNSName // empty' | sed 's/\.$//')"
  [ -n "$NOM_TS" ] && dire "l'adresse à entrer dans l'appli de ton téléphone : https://$NOM_TS" || dire "Tailscale n'est pas encore connecté : relance « sudo tailscale up »."
fi

etape "14. Les services (ils démarrent avec Ubuntu et redémarrent seuls)"
if [ $SYSTEMD = 1 ] && ! saute services; then
  U="$HOME/.config/systemd/user"; mkdir -p "$U"
  cat > "$U/naissance-cockpit.service" <<EOF
[Unit]
Description=Le cockpit de l'IA (naissance)
After=network-online.target

[Service]
WorkingDirectory=%h/AIOS/cockpit
EnvironmentFile=-%h/.config/naissance/env
Environment=COCKPIT_PORT=4317
ExecStart=/usr/local/bin/node %h/AIOS/cockpit/server.js
Restart=always
RestartSec=5

[Install]
WantedBy=default.target
EOF
  cat > "$U/naissance-demon.service" <<EOF
[Unit]
Description=Le démon de sa mémoire (naissance)

[Service]
WorkingDirectory=%h/Desktop/anamnese
EnvironmentFile=-%h/.config/naissance/env
ExecStart=%h/Desktop/anamnese/.venv/bin/python daemon.py
Restart=always
RestartSec=10

[Install]
WantedBy=default.target
EOF
  cat > "$U/naissance-consolidation.service" <<EOF
[Unit]
Description=La consolidation de nuit de sa mémoire (naissance)

[Service]
Type=oneshot
WorkingDirectory=%h/Desktop/anamnese
EnvironmentFile=-%h/.config/naissance/env
ExecStart=%h/Desktop/anamnese/.venv/bin/python consolidate.py
EOF
  cat > "$U/naissance-consolidation.timer" <<EOF
[Unit]
Description=Chaque nuit à 4 h 30

[Timer]
OnCalendar=*-*-* 04:30:00
Persistent=true

[Install]
WantedBy=timers.target
EOF
  $SUDO loginctl enable-linger "$USER" || true
  systemctl --user daemon-reload
  systemctl --user enable --now naissance-cockpit.service naissance-demon.service naissance-consolidation.timer
  systemctl --user restart naissance-cockpit.service naissance-demon.service     # une mise à jour : le nouveau code
  dire "services en marche : naissance-cockpit, naissance-demon (et la consolidation de nuit)."
else
  bash "$ANAMNESE/naissance/demarrer.sh" --relancer                               # une mise à jour : le nouveau code
fi

etape "15. Vérification"
for i in $(seq 1 30); do curl -fsS -o /dev/null "http://127.0.0.1:4317/" 2>/dev/null && break; sleep 1; done
curl -fsS -o /dev/null "http://127.0.0.1:4317/" && dire "le cockpit répond : http://localhost:4317 (ouvre-le dans le navigateur de Windows)" \
  || dire "le cockpit ne répond pas encore : regarde « journalctl --user -u naissance-cockpit » (ou ~/AIOS/journaux/cockpit.log)."
if command -v claude >/dev/null && ! saute claude && [ ! -s "$HOME/.config/jarvis/cle-api-anthropic" ]; then
  dire "Dernière chose : connecte Claude à ton abonnement. Tape « claude », suis le lien, puis « /exit »."
fi
dire "C'est fini. La suite (son cerveau de départ, puis sa naissance où elle choisit son nom) : le GUIDE, étapes 4 et 5."
dire "  cd ~/Desktop/anamnese && .venv/bin/python -m naissance.cerveau naitre --papa \"<ton prénom>\""
