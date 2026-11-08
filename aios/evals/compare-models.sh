#!/usr/bin/env bash
# A/B des modèles sur le harnais d'éval — décision par la donnée, pas par le hype.
# Juge FIXE (Opus) pour une notation comparable.
# Usage : bash ~/AIOS/evals/compare-models.sh   [modele1 modele2 ...]
set -uo pipefail
cd "$HOME/AIOS/evals" || exit 1
JUDGE="${JUDGE_MODEL:-claude-opus-4-8}"
if [ "$#" -gt 0 ]; then MODELS=("$@"); else MODELS=(claude-fable-5 claude-opus-4-8 claude-sonnet-5); fi

echo "Juge (fixe) : $JUDGE"
printf '%-24s %s\n' "MODÈLE AGENT" "RÉSULTAT"
printf '%-24s %s\n' "------------" "--------"
for M in "${MODELS[@]}"; do
  line=$(AGENT_MODEL="$M" JUDGE_MODEL="$JUDGE" bash run-evals.sh 2>/dev/null | tail -1)
  [ -z "$line" ] && line="(échec — modèle indisponible ? redémarre Claude Code / vérifie /model)"
  printf '%-24s %s\n' "$M" "$line"
done
echo
echo "Scorecards détaillés : ~/AIOS/evals/results/ (un dossier horodaté par run)"
