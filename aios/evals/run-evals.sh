#!/usr/bin/env bash
# Harnais d'éval d'agents — passe chaque golden-task dans `claude -p` (agent),
# fait noter la réponse par un juge LLM strict, sort un scorecard JSON + md.
# Usage : bash ~/AIOS/evals/run-evals.sh
#   AGENT_MODEL=claude-opus-4-8 JUDGE_MODEL=claude-sonnet-4-6 bash run-evals.sh
set -uo pipefail
EVALS="$HOME/AIOS/evals"
TASKS="$EVALS/tasks.jsonl"
AGENT_MODEL="${AGENT_MODEL:-claude-sonnet-4-6}"   # agent à tester (change pour comparer)
JUDGE_MODEL="${JUDGE_MODEL:-claude-sonnet-4-6}"   # juge
command -v claude >/dev/null 2>&1 || { echo "❌ claude CLI introuvable"; exit 1; }
command -v jq     >/dev/null 2>&1 || { echo "❌ jq introuvable"; exit 1; }
[ -f "$TASKS" ] || { echo "❌ $TASKS introuvable"; exit 1; }

OUT="$EVALS/results/run-$(date +%Y%m%d-%H%M%S)"
mkdir -p "$OUT"
total=0; passed=0; sum=0
SCORECARD="$OUT/scorecard.jsonl"

while IFS= read -r line; do
  [ -z "$line" ] && continue
  id=$(jq -r '.id'       <<<"$line")
  cat=$(jq -r '.category'<<<"$line")
  prompt=$(jq -r '.prompt'<<<"$line")
  rubric=$(jq -r '.rubric'<<<"$line")
  echo "▶ [$cat] $id"

  # 1) réponse de l'agent (plan mode = lecture seule, pas d'effets de bord)
  ans=$(claude -p "$prompt" --model "$AGENT_MODEL" --permission-mode plan 2>/dev/null)
  printf '%s' "$ans" > "$OUT/$id.answer.md"

  # 2) jugement strict
  jprompt=$(printf 'Tu es un correcteur STRICT. Note la réponse candidate.\n\nTÂCHE:\n%s\n\nCRITÈRE DE RÉUSSITE (rubric):\n%s\n\nRÉPONSE CANDIDATE:\n%s\n\nRéponds UNIQUEMENT par un objet JSON: {"score":0-100,"pass":true|false,"why":"<1 phrase>"}' "$prompt" "$rubric" "$ans")
  verdict=$(claude -p "$jprompt" --model "$JUDGE_MODEL" 2>/dev/null | sed -n 's/.*\({.*}\).*/\1/p' | head -1)
  score=$(jq -r '.score // 0' <<<"$verdict" 2>/dev/null); score=${score:-0}
  pass=$(jq -r '.pass // false' <<<"$verdict" 2>/dev/null)
  why=$(jq -r '.why // "?"' <<<"$verdict" 2>/dev/null)

  jq -nc --arg id "$id" --arg cat "$cat" --argjson score "${score:-0}" --arg pass "$pass" --arg why "$why" \
    '{id:$id,category:$cat,score:$score,pass:($pass=="true"),why:$why}' >> "$SCORECARD"
  total=$((total+1)); sum=$((sum+score)); [ "$pass" = "true" ] && passed=$((passed+1))
  echo "   score=$score pass=$pass — $why"
done < "$TASKS"

avg=0; [ "$total" -gt 0 ] && avg=$((sum/total))
{
  echo "# Scorecard agents — $(date '+%F %T')"
  echo "- Agent: \`$AGENT_MODEL\`  |  Juge: \`$JUDGE_MODEL\`"
  echo "- **Réussite: $passed/$total**  |  **Score moyen: $avg/100**"
  echo
  jq -r '"| \(.id) | \(.category) | \(.score) | \(if .pass then "✅" else "❌" end) | \(.why) |"' "$SCORECARD"
} > "$OUT/scorecard.md"
echo "—"
echo "✅ $passed/$total réussis, moyenne $avg/100 → $OUT/scorecard.md"
