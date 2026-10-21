# 🧠 Anamnèse

Une IA **personnelle, persistante et évolutive** : un moteur stable + une
**mémoire externe** + (à venir) un cycle de **« sommeil »** qui consolide.
Inspirée du cerveau (codage parcimonieux, consolidation hippocampe→néocortex)
et de la recherche IA 2026 (Auto-Dreamer, sleep-time compute).

> **Notre avance n'est PAS la puissance brute** — un petit modèle local ne
> dépasse pas un modèle frontière. C'est la **continuité, l'identité et
> l'efficacité** : une IA qui se souvient, grandit et évolue.

## Architecture (Phase 1)
- `engine.py` — moteur **gelé** (Ollama local, hors-ligne). Interchangeable.
- `memory.py` — **mémoire externe** (épisodique + compétences). Le *vrai* recall. SQLite + vecteurs.
- `salience.py` — score récence × importance × pertinence (Generative Agents, Stanford).
- `loop.py` — boucle : récupère le **top-k** souvenirs (sparse) → contexte → moteur → stocke.
- `modules/` — capacités **chargées dynamiquement** (base de l'auto-évolution).

## Les 3 niveaux d'évolution (NE PAS confondre)
1. **Mémoire** (continu) — grandit à chaque échange. ✅ sûr. *90 % du « mieux avec le temps ».*
2. **LoRA** (périodique, Phase 3) — « sommeil profond » : distille l'expérience dans des adaptateurs **versionnés**.
3. **Base** (gelée) — on n'y touche pas → **zéro oubli catastrophique**.

⛔ **Jamais** de fine-tuning continu des poids = oubli catastrophique (recherche A).

## Auto-évolution & modules — AVEC garde-fous
- `/evolve <desc>` → l'IA génère un module dans `modules/proposed/` (**inactif**).
- Tu **revois**, puis `/promote <nom>` → actif au prochain lancement.
- 🔒 **git** versionne tout (réversible) · 🧪 revue/tests avant activation · 🛡️ le cœur (engine/sécurité) reste immuable.

## Décisions d'archi validées par la recherche
- ✅ Base gelée + mémoire externe + consolidation offline (Auto-Dreamer : ~400× moins de tokens, meilleur score).
- ❌ PAS de couche de mémoire neuronale type Titans → c'est de l'attention linéaire, pas du vrai recall (NVIDIA, ICML 2026).
- ✅ Récupération **sparse** (cerveau : ~1 neurone/50 actif).

## Lancer
```bash
# 1. Démarrer Ollama (hors-ligne)
ollama serve                     # ou ouvrir l'app Ollama
# 2. Récupérer les modèles (une seule fois)
ollama pull qwen2.5:7b           # moteur (~4.7 Go) — ou qwen2.5:3b si peu de RAM
ollama pull nomic-embed-text     # embeddings (~274 Mo)
# 3. Installer les deps Python
pip install -r requirements.txt
# 4. Lancer
python3 loop.py
```

## Daemon always-on (proactivité + conscience du temps)

Pour qu'Anamnèse « veille », pense et te sollicite **spontanément** (notifs **générées par le modèle**, jamais codées en dur) :

```bash
# 1. Ollama EN NATIF (GPU Metal = rapide) — via l'app Ollama, ou dans TON Terminal :
ollama serve            # surtout pas headless, sinon il tombe sur le CPU (lent)
# 2. Le daemon, toujours éveillé (Mac branché) :
caffeinate -dimsu ~/Desktop/anamnese/.venv/bin/python ~/Desktop/anamnese/daemon.py
```

- Cerveau léger configurable : `ANAMNESE_DAEMON_MODEL` (défaut `mistral`, ~7B).
- Cadence : `ANAMNESE_REFLECT_EVERY` (défaut 1800 s).
- **Autostart au login** (capot fermé inclus) : copier `com.anamnese.daemon.plist` dans `~/Library/LaunchAgents/`, puis `launchctl load ~/Library/LaunchAgents/com.anamnese.daemon.plist`.
- ⚠️ Perf : sur 16 Go, garde Ollama en natif (GPU). Le 12B est lourd → le daemon utilise un 7B léger.

## Roadmap
- **P1** ✅ Il se souvient (mémoire + récupération sparse) + fondations modules
- **P2** Il dort & rêve (consolidation offline, couche affective valence/arousal)
- **P3** Il s'autonomise (open-weights hébergé + LoRA persona + consolidateur RL)
- **P4** Recherche (mesurer l'effet de la consolidation, angle affectif inédit)
