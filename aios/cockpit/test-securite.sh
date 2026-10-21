#!/bin/bash
# Lot 0 de JarvisXAnamnèse (2026-10-15) : le cockpit ne répond qu'à cette machine.
# Lance une copie du cockpit sur un port de test, vérifie, puis l'arrête par son PID.
#
# Prédiction écrite AVANT le correctif : sur l'ancien code (listen(PORT) sans adresse),
# les contrôles 1 (écoute), 3 (Host forgé) et 6 (accès par l'adresse réseau) échouent ;
# 2, 4 et 5 passent.
set -u
PORT=${TEST_PORT:-$((4800 + RANDOM % 400))}
DIR="$(cd "$(dirname "$0")" && pwd)"
ECHECS=0

# isolé (relecture du 2026-10-20) : jamais les vrais réglages de Jarvis, jamais le vrai claude
ISOLE=$(mktemp -d "${TMPDIR:-/tmp}/banc-securite.XXXXXX")
COCKPIT_PORT=$PORT OLLAMA_URL="http://127.0.0.1:9" JARVIS_DIR="$ISOLE" CLAUDE_BIN=/usr/bin/false COCKPIT_SANS_INVENTAIRE=1 \
  TAILSCALE_CLI=/usr/bin/false /usr/local/bin/node "$DIR/server.js" >/dev/null 2>&1 &
PID=$!
trap 'kill "$PID" 2>/dev/null' EXIT
curl -s -o /dev/null --retry 20 --retry-connrefused --retry-delay 1 "http://127.0.0.1:$PORT/" \
  || { echo "ÉCHEC : le cockpit de test n'a pas démarré sur $PORT"; exit 1; }

verifier() {  # $1 = libellé, $2 = attendu, $3 = obtenu
  if [ "$2" = "$3" ]; then echo "ok    $1"; else echo "ÉCHEC $1 (attendu $2, obtenu $3)"; ECHECS=$((ECHECS+1)); fi
}
code() { curl -s -o /dev/null -w '%{http_code}' --max-time 3 "$@"; }

ecoute=$(lsof -nP -a -p "$PID" -iTCP -sTCP:LISTEN 2>/dev/null | awk 'NR>1{print $9}' | sort | tr '\n' ' ')
case "$ecoute" in *"*:"*) local_seul=non ;; *) local_seul=oui ;; esac
verifier "1. écoute seulement sur la boucle locale [$ecoute]" oui "$local_seul"
verifier "2. Host localhost accepté" 200 "$(code -H "Host: localhost:$PORT" "http://127.0.0.1:$PORT/")"
verifier "3. Host forgé refusé" 403 "$(code -H "Host: evil.example:$PORT" "http://127.0.0.1:$PORT/")"
verifier "4. Host 127.0.0.1 accepté" 200 "$(code "http://127.0.0.1:$PORT/")"
verifier "5. localhost en IPv6 (::1) accepté" 200 "$(code -g "http://[::1]:$PORT/")"

IP=$(ifconfig 2>/dev/null | awk '/inet / && $2 != "127.0.0.1" {print $2; exit}')
if [ -n "$IP" ]; then
  verifier "6. inaccessible par l'adresse réseau $IP" 000 "$(code "http://$IP:$PORT/")"
else
  echo "--    6. sauté : aucune adresse réseau IPv4"
fi

# Étape 5 de Jarvis (2026-10-16) : la page « Parler » lance `claude -p` AVEC la mémoire (écriture).
# Une page web quelconque peut envoyer un POST simple à 127.0.0.1 (le Host est alors valide) :
# tout POST exige le jeton du démarrage, lisible seulement par les pages du cockpit (même origine).
# Prédiction écrite AVANT le code : 7 à 11 échouent ; 12 passe déjà. Constaté : 12 échoue aussi
# (404, la route n'existe pas) et 7 lance réellement `claude -p` (délai dépassé, 000).
U="http://127.0.0.1:$PORT"
verifier "7. POST /api/chat sans jeton refusé" 403 "$(code -X POST -H 'Content-Type: text/plain' --data '{"via":"claude","model":"haiku","messages":[]}' "$U/api/chat")"
verifier "8. POST /api/jarvis sans jeton refusé" 403 "$(code -X POST --data '{"texte":"x"}' "$U/api/jarvis")"
acao=$(curl -s -D - -o /dev/null --max-time 2 "$U/api/stream" | grep -ci '^access-control-allow-origin')
verifier "9. flux /api/stream non lisible par une autre origine" 0 "$acao"
JETON=$(curl -s --max-time 3 "$U/parler" | sed -n 's/.*name="cockpit-jeton" content="\([0-9a-f]*\)".*/\1/p')
verifier "10. la page Parler porte le jeton" 48 "${#JETON}"
verifier "11. jeton valide, modèle inconnu refusé" 400 "$(code -X POST -H "X-Jeton: $JETON" --data '{"texte":"x","modele":"gpt"}' "$U/api/jarvis")"
# le dernier caractère est CHANGÉ (avant : remplacé par 0, donc identique au vrai une fois sur 16)
DERNIER=${JETON: -1}; [ "$DERNIER" = "0" ] && AUTRE=1 || AUTRE=0
verifier "12. jeton faux refusé" 403 "$(code -X POST -H "X-Jeton: ${JETON%?}$AUTRE" --data '{"texte":"x"}' "$U/api/jarvis")"

# 13. le modèle de visage servi est bien celui vérifié le 2026-10-16 (hors paquet npm : sha256 noté ici)
verifier "13. face_landmarker.task intact" "64184e229b263107bc2b804c6625db1341ff2bb731874b0bcc2fe6544e0bc9ff" \
  "$(shasum -a 256 "$DIR/public/vendor/mediapipe/face_landmarker.task" | awk '{print $1}')"
# 13 bis. (audit du cockpit, 2026-10-20) le code de MediaPipe servi à la page (JS et WASM) : octet pour octet celui du
# paquet npm @mediapipe/tasks-vision 0.10.35, dont l'intégrité sha512 a été vérifiée contre le registre ce jour-là
verifier "13 bis. MediaPipe (vision_bundle.mjs, wasm) intact" \
  "55d7ab624fbb70dcc5adc4ae6d7ea9cfcb569139d3dbfbf2b1deafcb966bc0fe e7fd9858e8e8f221d9b96eddc11f8e077f263e0b7bbd79d3cbe882b134274f8c 6a5c64584c2ab61c763b6e204afbdbc7ce1caf7f5216187322bca8df94f646bc" \
  "$(cd "$DIR/public/vendor/mediapipe" && shasum -a 256 vision_bundle.mjs wasm/vision_wasm_internal.js wasm/vision_wasm_internal.wasm | awk '{print $1}' | tr '\n' ' ' | sed 's/ $//')"

[ "$ECHECS" -eq 0 ] && echo "TOUT VERT" || echo "$ECHECS contrôle(s) en échec"
exit "$ECHECS"
