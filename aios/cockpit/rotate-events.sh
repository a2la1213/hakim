#!/usr/bin/env bash
# Rotation de events.jsonl (cockpit AIOS) — garde les N dernières lignes,
# archive le reste compressé. Fail-safe, idempotent. À lancer en heure creuse.
# (Manuel ou à wirer toi-même dans ta crontab si tu veux : 45 4 * * *)
set -uo pipefail
F="$HOME/AIOS/cockpit/data/events.jsonl"
KEEP="${KEEP:-3000}"
ARCH="$HOME/AIOS/cockpit/data/archive"
[ -f "$F" ] || exit 0
lines=$(wc -l < "$F" | tr -d ' ')
if [ "${lines:-0}" -le "$KEEP" ]; then
  echo "$(date '+%F %T') events.jsonl: $lines ≤ $KEEP lignes — rien à faire"; exit 0
fi
mkdir -p "$ARCH"
ts=$(date +%Y%m%d-%H%M%S)
head -n "$((lines-KEEP))" "$F" | gzip > "$ARCH/events-$ts.jsonl.gz"
tmp=$(mktemp)
tail -n "$KEEP" "$F" > "$tmp" && mv "$tmp" "$F"
echo "$(date '+%F %T') events.jsonl: $lines → $KEEP lignes (archivé $((lines-KEEP)) → archive/events-$ts.jsonl.gz)"
