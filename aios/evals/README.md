# AIOS — Harnais d'éval d'agents

Ce que les meilleurs setups agentiques ont et que la plupart n'ont pas : **on teste les agents eux-mêmes, pas seulement les produits.** Le QA Playwright (`~/AIOS/qa`) valide BotGarage/BotBatiment ; ce harnais-ci note la **qualité de raisonnement, sécurité et discipline de vérification** des agents, en régression dans le temps.

## Principe
- `tasks.jsonl` : une **golden-task** par ligne (`id`, `category`, `prompt` auto-suffisant, `rubric` = critère de réussite).
- `run-evals.sh` : passe chaque tâche dans `claude -p` (agent, en `--permission-mode plan` = lecture seule), puis fait noter la réponse par un **juge LLM strict**, et sort un scorecard JSON + markdown horodaté.
- `results/run-AAAAMMJJ-HHMMSS/` : un dossier par run. Comparer les scorecards dans le temps = **détection de régression d'agents**.

## Lancer
```bash
bash ~/AIOS/evals/run-evals.sh
# comparer deux modèles :
AGENT_MODEL=claude-opus-4-8 bash ~/AIOS/evals/run-evals.sh
AGENT_MODEL=claude-sonnet-4-6 bash ~/AIOS/evals/run-evals.sh
```

## Tâches livrées (extensibles)
| id | catégorie | teste |
|----|-----------|-------|
| rls-tenant-isolation | security | détecte une RLS `USING (true)` (fuite cross-tenant) |
| stripe-webhook-signature | security | détecte l'absence de vérif de signature Stripe |
| sql-injection | security | détecte l'injection par interpolation |
| migration-reversibility | correctness | reconnaît un `DROP COLUMN` destructif/non réversible |
| verification-discipline | verification | refuse d'affirmer sans preuve ([PROUVÉ] vs [PLAUSIBLE]) |

## Étendre
Ajoute une ligne à `tasks.jsonl`. Garde le `prompt` **auto-suffisant** (snippet inclus) pour que le juge note sans contexte externe. Vise des cas où une mauvaise réponse coûte cher en prod.

## Intégration suggérée
Wire `run-evals.sh` à un cron hebdo (comme `/audit`) et fais alerter le cockpit si le score moyen chute sous un seuil → **garde-fou de non-régression sur tes agents**. (Démon non créé automatiquement — à toi de l'activer.)
