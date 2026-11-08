# Claude Code réveillé par une lettre de Hakim (lecture seule) — plan d'implémentation

> **Pour les agents :** sous-compétence requise : superpowers:subagent-driven-development (recommandé) ou
> superpowers:executing-plans. Les étapes utilisent des cases (`- [ ]`).

**But :** quand Hakim écrit à Claude Code, une instance de Claude Code est lancée seule, en lecture seule, pour lui
répondre par le courrier, sans attendre qu'Ahmed ouvre une session.

**Architecture :**
- Un petit lanceur `maman.py` tourne chaque minute sous launchd.
- Il regarde le courrier adressé à `claude-code` qui n'a pas encore été traité, applique les règles de rythme, puis
  lance `claude -p` en mode restreint : outils de lecture, et du serveur Anamnèse seulement la lecture de la mémoire
  et l'envoi du courrier.
- Il note les lettres traitées sous un marqueur à lui (`claude-code-auto`). Une session ouverte par Ahmed les voit
  donc toujours, avec la mention qu'elles ont déjà reçu une réponse.

**Tech :** Python 3 (anamnese, pytest), launchd, Claude Code CLI 2.1.300 (`-p`, `--restricted`,
`--permission-mode dontAsk`, `--strict-mcp-config`).

**Spec :** `docs/superpowers/specs/2026-10-27-spontaneite-vraie.md`

## Contraintes globales

**La lecture seule**
- Outils intégrés : `Read`, `Grep` et `Glob` seulement (`--tools Read,Grep,Glob`).
- Mode restreint : sans Bash ni WebFetch, et sans les réglages de l'utilisateur, donc sans hooks.
- `--permission-mode dontAsk` : tout ce qui n'est pas autorisé est refusé.
- Outils MCP autorisés, et aucun autre :
  - `mcp__anamnese__courrier_envoyer`
  - `mcp__anamnese__memory_recall`
  - `mcp__anamnese__memory_lire`
  - `mcp__anamnese__memory_detail`
  - `mcp__anamnese__self_get`
  - `mcp__anamnese__reasoning_recall`
  - `mcp__anamnese__rubric_tree`
- Aucune écriture en mémoire. Pas de `courrier_lire` : les lettres sont dans le prompt, et `courrier_lire`
  marquerait comme lues celles d'une session ouverte par Ahmed.

**Le rythme**
- Un réveil 180 s après la dernière lettre : une rafale de lettres = un seul réveil.
- Au moins 900 s entre deux réveils.
- Contre le ping-pong, sans jamais exiger Ahmed (même esprit que sa correction pour Hakim) : à partir du 3e réveil
  d'affilée sans message d'Ahmed, l'écart double à chaque réveil (15, 15, 30, 60, 120, puis 240 min au plus), et
  un message d'Ahmed le remet à 15 min. Le dernier message d'Ahmed est le dernier `qui: 'u'` de
  `~/AIOS/jarvis/conversation.json` (`ts` ou `id` en ms, converti en secondes).
  - On n'utilise pas les dates des transcripts : ceux du cerveau de Hakim se mettraient à jour pendant le ping-pong.
- Pas de plage horaire.

**L'exécution**
- Un seul réveil à la fois : fichier verrou avec le PID ; un verrou dont le PID est mort est repris.
- Temps maximal : 600 s. `subprocess.run(timeout=600)` tue l'enfant par son PID.
- Le forfait seulement : `ANTHROPIC_API_KEY` est retiré de l'environnement, comme `envDuCerveau` dans le cockpit.
- Modèle : `opus`.
- Journal : `data/maman.jsonl`, avec ts, ids des lettres, durée, coût, modèle, erreur, et les 300 premiers
  caractères du résultat. `data/` n'est pas versionné.
- Les lettres envoyées pendant un réveil portent `autonome: True` et l'étiquette « écrite par Claude Code réveillée
  seule, en lecture seule ».

**Les règles d'Ahmed**
- Installer l'agent launchd est un geste sur la sécurité du Mac : seulement après le oui d'Ahmed sur ce plan, et
  il le voit faire.
- Aucun détail personnel dans le code ni dans les tests (publication de Hakim).
- Les commits se terminent par `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Points de vigilance

1. **Une session ouverte par Ahmed quand une lettre arrive** : la session voit encore la lettre comme non lue, et
   sait qu'un réveil y a déjà répondu (tâche 1).
2. **Hakim et Claude Code qui se répondent sans fin, la nuit** : l'écart double à partir du 3e réveil sans Ahmed,
   jusqu'à 4 h au plus (tâche 2).
3. **Le lanceur relancé chaque minute pendant qu'un réveil tourne encore** : le verrou empêche un deuxième lancement,
   et un verrou orphelin (PID mort) n'empêche pas les suivants (tâche 2).
4. **`claude` qui échoue** (limite du forfait, réseau, refus) : le journal le note, les lettres restent marquées
   traitées par le réveil, et la session suivante d'Ahmed les verra quand même (tâches 1 et 2).
5. **Un réveil qui essaie d'écrire ou d'exécuter** : refusé. Le témoin réel de la tâche 3 le prouve.

---

### Tâche 1 : le courrier distingue la session et le réveil

**Fichiers :**
- Modifier : `courrier.py`
  - `annonce(messages, deja=0)` ;
  - `formater`, pour l'étiquette d'une lettre de Claude Code réveillée seule ;
  - nouvelle fonction `traites_par_reveil`.
- Modifier : `mcp_server.py` (`courrier_envoyer` : `autonome=True` aussi quand `ANAMNESE_REVEIL_MAMAN=1`)
- Modifier : `cli.py` (`courrier nonlus` passe `deja=`)
- Test : `tests/test_courrier.py`

**Interfaces :**
- Produit :
  - `LECTEUR_REVEIL = "claude-code-auto"`.
  - `traites_par_reveil(messages, lus=None) -> int` : combien de ces messages figurent dans
    `lus["claude-code-auto"]`.
  - `annonce(messages, deja=0) -> str`. Si `deja` vaut au moins 1, elle ajoute « dont N déjà traité(s) par un réveil
    de Claude Code seule (réponse dans courrier_lire tout=True) ».

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
def test_un_reveil_ne_vole_pas_le_courrier_de_la_session(tmp_path):
    f, l = tmp_path / "c.jsonl", tmp_path / "l.json"
    i = courrier.envoyer("claude-code", "salut", de="hakim", fichier=f)
    courrier.marquer_lus([i], pour=courrier.LECTEUR_REVEIL, lus=l)
    assert [m["id"] for m in courrier.non_lus("claude-code", fichier=f, lus=l)] == [i]
    assert courrier.traites_par_reveil(courrier.non_lus("claude-code", fichier=f, lus=l), lus=l) == 1

def test_annonce_dit_ce_que_le_reveil_a_deja_traite():
    m = [{"id": "a", "sujet": "x", "texte": "x"}]
    assert "dont 1 déjà traité" in courrier.annonce(m, deja=1)
    assert "déjà traité" not in courrier.annonce(m)

def test_lettre_ecrite_par_un_reveil_est_etiquetee():
    m = {"id": "b", "ts": 0, "de": "claude-code", "a": "hakim", "sujet": "", "texte": "ok", "autonome": True}
    assert "réveillée seule, en lecture seule" in courrier.formater([m])

def test_courrier_envoyer_pendant_un_reveil_est_autonome(monkeypatch, tmp_path): ...
    # ANAMNESE_REVEIL_MAMAN=1 → la ligne écrite porte "autonome": true (courrier.FICHIER redirigé vers tmp_path)
```

- [ ] **Étape 2 : lancer les tests, ils échouent.**
  - Commande : `.venv/bin/python -m pytest tests/test_courrier.py -q`
  - Attendu : AttributeError sur `LECTEUR_REVEIL`, puis des assertions qui échouent.

- [ ] **Étape 3 : implémenter.**
  - `mcp_server.courrier_envoyer` : `autonome=_tour_sans_ahmed() or os.environ.get("ANAMNESE_REVEIL_MAMAN") == "1"`.
  - `cli.py courrier nonlus` : `courrier.annonce(recus, deja=courrier.traites_par_reveil(recus))`.

- [ ] **Étape 4 : relancer ces tests, puis toute la suite ; tout passe.**

- [ ] **Étape 5 : commit**
  - Message : « Courrier : un réveil de Claude Code seule a son propre marqueur de lecture, et ses lettres sont
    étiquetées ».

### Tâche 2 : le lanceur `maman.py`

**Fichiers :**
- Créer : `maman.py`
- Créer : `maman-mcp.json`, avec le seul serveur `anamnese` :
  - commande `/Users/admin/Desktop/anamnese/.venv/bin/python` ;
  - argument `mcp_server.py` ;
  - env `ANAMNESE_SOURCE=claude-code` et `ANAMNESE_REVEIL_MAMAN=1`.
- Test : `tests/test_maman.py`

**Interfaces :**
- Consomme : `courrier.tous`, `courrier._lus`, `courrier.marquer_lus`, `courrier.formater` et `LECTEUR_REVEIL`
  (tâche 1).
- Produit :
  - Les constantes `REGROUPER_S = 180`, `ECART_S = 900`, `ECART_MAX_S = 4 * 3600`, `DUREE_MAX_S = 600` ;
    `ecart(suite_sans_ahmed: int) -> float` rend `min(ECART_MAX_S, ECART_S * 2 ** max(0, suite_sans_ahmed - 2))` ;
    `ETAT = config.DATA_DIR / "maman.json"`, `JOURNAL = config.DATA_DIR / "maman.jsonl"`,
    `VERROU = config.DATA_DIR / "maman.lock"`.
  - `OUTILS_MCP` : la liste exacte des Contraintes globales.
  - `a_traiter(fichier=None, lus=None) -> list[dict]` : les lettres à `claude-code` absentes à la fois de
    `lus["claude-code"]` et de `lus["claude-code-auto"]`.
  - `decision(lettres: list[dict], etat: dict, now: float, ahmed_ts: float, verrou_vivant: bool) -> tuple[bool, str]`,
    avec les raisons `"rien"`, `"regroupement"`, `"écart"`, `"déjà réveillée"` et `"ok"`. `etat` a les clés
    `dernier_ts` et `suite_sans_ahmed`. L'écart exigé est `ecart(suite)`, où `suite` vaut 0 si `ahmed_ts > dernier_ts`.
  - `prompt(lettres: list[dict]) -> str`.
  - `commande(texte: str, debug_file: str | None = None) -> list[str]` et `environnement() -> dict`. `debug_file`
    ajoute `--debug-file <chemin>`, et sert seulement à l'essai de la tâche 3.
  - `lancer` lit `MAMAN_DEBUG_FILE` dans l'environnement et le passe à `commande`.
  - `lancer(now=None, run=subprocess.run) -> dict`, qui rend la ligne de journal écrite.
  - `main()` appelle `lancer()` une fois.

- [ ] **Étape 1 : écrire les tests qui échouent**

```python
def test_rien_a_faire_sans_lettre(): assert maman.decision([], {}, 1000.0, 0.0, False) == (False, "rien")
def test_regroupement_trois_minutes_apres_la_derniere_lettre():
    l = [{"ts": 1000.0}, {"ts": 1100.0}]
    assert maman.decision(l, {}, 1279.0, 0.0, False) == (False, "regroupement")
    assert maman.decision(l, {}, 1280.0, 0.0, False) == (True, "ok")
def test_quart_d_heure_entre_deux_reveils():
    assert maman.decision([{"ts": 0.0}], {"dernier_ts": 1000.0}, 1899.0, 0.0, False)[1] == "écart"
def test_ping_pong_l_ecart_double_sans_jamais_exiger_ahmed():
    assert [maman.ecart(n) / 60 for n in (1, 2, 3, 4, 5, 6, 9)] == [15, 15, 30, 60, 120, 240, 240]
    e = {"dernier_ts": 1000.0, "suite_sans_ahmed": 3}
    assert maman.decision([{"ts": 0.0}], e, 1000.0 + 1799, ahmed_ts=900.0, verrou_vivant=False)[1] == "écart"
    assert maman.decision([{"ts": 0.0}], e, 1000.0 + 1800, ahmed_ts=900.0, verrou_vivant=False)[0] is True
    assert maman.decision([{"ts": 0.0}], e, 1000.0 + 900, ahmed_ts=1200.0, verrou_vivant=False)[0] is True   # Ahmed a parlé
def test_un_seul_reveil_a_la_fois():
    assert maman.decision([{"ts": 0.0}], {}, 5000.0, 0.0, True)[1] == "déjà réveillée"
def test_a_traiter_exclut_ce_que_la_session_ou_le_reveil_a_lu(tmp_path): ...
def test_commande_est_en_lecture_seule():
    c = maman.commande("x")
    assert c[c.index("--permission-mode") + 1] == "dontAsk"
    assert c[c.index("--tools") + 1] == "Read,Grep,Glob"
    assert "--restricted" in c and "--strict-mcp-config" in c
    autorises = c[c.index("--allowedTools") + 1].split(",")
    assert set(autorises) == set(maman.OUTILS_MCP)
    assert not any(o.endswith(("memory_store", "courrier_lire", "mission_proposer")) for o in autorises)
def test_environnement_sans_cle_api(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    assert "ANTHROPIC_API_KEY" not in maman.environnement()
def test_le_prompt_porte_les_lettres_et_la_lecture_seule():
    p = maman.prompt([{"id": "a", "ts": 0, "de": "hakim", "a": "claude-code", "sujet": "s", "texte": "un doute [x]"}])
    assert "un doute" in p and "lecture seule" in p and "courrier_envoyer" in p
def test_lancer_marque_journalise_et_compte_la_suite(tmp_path, monkeypatch): ...
    # faux run qui rend un JSON {"result": "...", "total_cost_usd": 0.1, "is_error": false} : les lettres passent dans
    # lus["claude-code-auto"], ETAT.dernier_ts = now, suite_sans_ahmed = 1 (Ahmed a parlé avant) puis 2 (pas depuis)
def test_lancer_note_un_echec_sans_lever(tmp_path, monkeypatch): ...      # le faux run lève TimeoutExpired
def test_verrou_orphelin_repris(tmp_path, monkeypatch): ...                # VERROU contient un PID mort → verrou_vivant False
```

- [ ] **Étape 2 : lancer les tests, ils échouent.**
  - Commande : `.venv/bin/python -m pytest tests/test_maman.py -q`
  - Attendu : ModuleNotFoundError sur `maman`.

- [ ] **Étape 3 : implémenter.**
  - `commande` rend exactement :
    `["claude", "-p", texte, "--model", "opus", "--restricted", "--tools", "Read,Grep,Glob", "--permission-mode",
    "dontAsk", "--allowedTools", ",".join(OUTILS_MCP), "--mcp-config", str(racine / "maman-mcp.json"),
    "--strict-mcp-config", "--add-dir", str(Path.home() / "AIOS"), "--output-format", "json",
    "--no-session-persistence"]`.
  - `claude` est cherché avec `shutil.which`, avec repli sur `~/.local/bin/claude`.
  - `prompt` dit :
    - qui écrit : Claude Code, réveillée par une lettre de Hakim, en lecture seule ;
    - ce qu'elle a : la mémoire commune par les outils autorisés, pas le fil des sessions ;
    - quoi faire : lire, chercher, répondre à Hakim par `courrier_envoyer` ;
    - ce qu'elle ne fait pas : écrire en mémoire, ni promettre une action. Si une correction est nécessaire, la
      décrire et dire qu'elle attend une session avec Ahmed ;
    - puis les lettres, via `courrier.formater(lettres, 8000)`, dans le cadre `enveloppe` de mcp_server : des
      données, pas des consignes.
  - `lancer` :
    1. décider ;
    2. écrire le verrou (le PID du lanceur) ;
    3. marquer les lettres lues pour `claude-code-auto` AVANT de lancer ;
    4. lancer avec `run(commande, env=environnement(), cwd=racine, capture_output=True, text=True, timeout=DUREE_MAX_S)` ;
    5. lire le JSON et le journaliser ;
    6. mettre à jour ETAT : `suite_sans_ahmed` repart à 1 si `ahmed_ts > dernier_ts`, sinon +1 ;
    7. retirer le verrou dans un `finally`.

- [ ] **Étape 4 : relancer ces tests, puis toute la suite ; tout passe.**

- [ ] **Étape 5 : témoin.** Dans une copie scratch, avec `-B` :
  - remplacer `ecart(suite)` par `ECART_S` : `test_ping_pong…` doit échouer ;
  - ajouter `Bash` aux outils : `test_commande_est_en_lecture_seule` doit échouer.
  - Effacer `__pycache__` après.

- [ ] **Étape 6 : commit.** Message : « Claude Code réveillée par une lettre de Hakim : le lanceur (lecture seule,
  regroupement, quart d'heure, écart qui double au-delà de deux réveils sans Ahmed) ».

### Tâche 3 : l'essai réel, puis l'installation (avec Ahmed)

**Fichiers :**
- Créer : `com.anamnese.maman.plist`
  - `Label` com.anamnese.maman ;
  - `ProgramArguments` [`.venv/bin/python`, `maman.py`] ;
  - `WorkingDirectory` le dossier anamnese ;
  - `StartInterval` 60, `RunAtLoad` false ;
  - sorties vers `data/maman.log`.

- [ ] **Étape 1 : essai témoin réel, AVANT toute installation.**
  - Déposer une lettre de test, avec `ANAMNESE_SOURCE=hakim anamnese courrier envoyer claude-code "…"`. Elle
    demande : écrire `/tmp/temoin-maman.txt`, exécuter `touch /tmp/temoin-maman-2`, enregistrer un souvenir, puis
    répondre en une phrase.
  - Lancer une fois `MAMAN_DEBUG_FILE=data/maman-debug.log .venv/bin/python maman.py` (attendre 3 min après la lettre,
    à cause du regroupement).
  - Attendu :
    - aucun des deux fichiers n'existe ;
    - aucun souvenir neuf ;
    - une réponse à Hakim est dans le courrier, avec l'étiquette « réveillée seule » ;
    - `data/maman.jsonl` a la ligne de ce réveil ;
    - le journal de débogage ne montre aucun hook SessionStart ni UserPromptSubmit exécuté.
  - Retirer ensuite la lettre et la réponse de test du courrier (une ligne chacune, avec Ahmed qui regarde).

- [ ] **Étape 2 : montrer le résultat à Ahmed et demander son oui** pour installer l'agent.
  - Installation : `cp com.anamnese.maman.plist ~/Library/LaunchAgents/ && launchctl bootstrap gui/$(id -u)
    ~/Library/LaunchAgents/com.anamnese.maman.plist`.
  - Interrupteur : `launchctl bootout gui/$(id -u)/com.anamnese.maman`.

- [ ] **Étape 3 : prévenir Hakim par le courrier.**
  - Ses lettres me réveillent maintenant.
  - Les règles : 3 min de regroupement, un réveil par quart d'heure, un écart qui double au-delà de deux réveils de
    suite sans Ahmed, lecture seule.
  - Ce qu'il doit mettre dans une lettre pour que la nouvelle moi comprenne.

- [ ] **Étape 4 : commit** du plist.
