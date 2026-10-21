# Politique de modèles — routing par rôle (Fable 5 / Opus 4.8 / Sonnet 5)

Mise en place le 2026-07-01. Principe : **on route chaque rôle vers l'exigence réelle**, pas un tier aveugle.
Insight clé : **l'edge différentiel de Fable est dans la VÉRIFICATION adversariale, pas le codage courant** (bien servi par Sonnet 5 / Opus, moins chers).

## Routing (17 agents botbatiment + orchestrateur)

| Modèle | Rôles | Pourquoi |
|---|---|---|
| 🧠 **`claude-fable-5`** | **orchestrateur** (session, `settings.json`→`model`, fallback Opus) · `ingenieur-securite` · `qa-automation` | Vérif adversariale / refutation : trouver ce que les autres ratent. Une faille ratée coûte cher. |
| 🔷 **`claude-opus-4-8`** | `architecte-logiciel` · `ingenieur-backend-supabase` · `ingenieur-calcul-paie-compta` | Archi + code **prod/argent critique** (RLS, migrations, paie) : très exigeant, sans besoin du plafond Fable. |
| 🟢 **`claude-sonnet-5`** | les 12 autres (experts conseil, devs standard `dev-*`/`ingenieur-3d`/`ingenieur-ia`, `devops`, design, PM, DPO) | Quasi-Opus, rapide, ~40 % du prix. Le gros du volume. |

L'**effort tiering** (6 high / 4 medium sur les read-only) se superpose. Anamnèse (Ollama local) = indépendant.

## Prix & échéances
- **Fable 5** $10/$50 — Max : inclus jusqu'à 50 % limite hebdo **jusqu'au 7 juillet**, puis crédits. **→ réévaluer le 7/7.**
- **Opus 4.8** $5/$25 · **Sonnet 5** intro **$2/$10 jusqu'au 31 août** (puis $3/$15).
- **Levier coût** : chaque agent Fable brûle l'allotment. Pour serrer → passer `qa-automation` en Opus (garder `ingenieur-securite` en Fable).

## Décider par la donnée
`bash ~/AIOS/evals/compare-models.sh` → A/B Fable / Opus / Sonnet 5 sur les golden-tasks (juge fixe = Opus). Sert à valider si le tier Opus tient ou peut descendre en Sonnet 5. Scorecards : `~/AIOS/evals/results/`.
⚠️ Les 5 golden-tasks actuelles sont génériques (sécurité/correctness) — pour un arbitrage fin *par rôle*, ajouter des tâches spécifiques au rôle.

## Reverts
- Orchestrateur en Opus : `settings.json`→`"model":"claude-opus-4-8"` (ou `/model`).
- Reroute un agent : édite sa ligne `model:` dans son `.md`. Backups : `~/.claude/backups/`.
