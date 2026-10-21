# Grille de rêve 3×3 complète + contrôles scientifiques — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Générer les conditions manquantes du laboratoire de rêve (twin OFF-neutre/OFF-libre + sonnet en BRAS CONTRÔLÉ complet ON/OFF-neutre/OFF-libre) pour que la logique de verdict existante (Portes A/B/C) puisse enfin CONCLURE.

**Architecture:** Généraliser les 2 passes journal-seul (`_dream_ablation_pass`/`_dream_free_pass`) avec un paramètre `dreamer`. Le daemon `dream()` génère : twin OFF/libre (9B, chaque rêve, gratuit) + un bras sonnet contrôlé 3-conditions (claude_chat, cadence NOCTURNE via garde kv). `dream_ablation.load_cells` exclut les idées de consolidation (non-REM) des cellules. Le verdict est INCHANGÉ (déjà prêt à consommer les cellules sonnet).

**Tech Stack:** Python 3.14 (.venv), SQLite, dream_lab (prompts REM), synthesis_claude.claude_chat (sonnet), cockpit Node. Tests pytest (fixture `tmp_db`, FakeMem local).

## Global Constraints

- **Journal-seul préservé** : les passes n'écrivent RIEN dans le vivant (pas de `mem.add`, `log_coactivation`, `kv_set`, identité). Les tests existants `test_dream_ablation_pass.py` / `test_dream_free_pass.py` DOIVENT rester verts (le défaut `dreamer="local"` conserve le comportement v1).
- **Best-effort partout** : aucune passe ni le bras sonnet ne peut lever/bloquer le rêve (try/except englobant).
- **Sonnet = cadence NOCTURNE** : le bras sonnet (3 calls claude) tourne AU PLUS une fois par DATE (garde kv `last_sonnet_arm`), pour coller au rôle de contrôle + borner le coût.
- **Affect** : local ET sonnet utilisent l'affect RÉEL (`seed_state`) aux 3 conditions (on ne varie que le corpus/menu) ; le TWIN utilise l'affect NEUTRE (`tw_state = neutralize(seed_state)`). L'axe affect est le rôle du twin.
- **Verdict INCHANGÉ** : `ablation_verdict`/`porte_c`/`combined_verdict` ne sont PAS modifiés. Seul `load_cells` gagne un filtre (exclure `meta.source=='consolidate'`).
- **Kill-switches** : `DREAM_SONNET_ARM_ENABLED` (env `ANAMNESE_DREAM_SONNET_ARM`, défaut on) ; twin sous `DREAM_TWIN_ENABLED` existant ; le tout sous `DREAM_ABLATION_ENABLED`.
- **Ne PAS casser** : le rêve local ON, le twin ON, l'ablation/free local, la synthèse, l'émergence, les portes 2026-07-03/07-09.
- **Zéro `claude -p` réel au build** : le bras sonnet est testé `call_fn` mockée.

## File Structure

- **Modify** `config.py` — flag `DREAM_SONNET_ARM_ENABLED` (après les DREAM_* ~ligne 226).
- **Modify** `daemon.py` — généraliser les 2 passes (`dreamer`/`condition`/`ablation`) ; helpers `_sonnet_arm_due`/`_mark_sonnet_arm_done` ; câbler twin OFF/libre + bras sonnet dans `dream()`.
- **Modify** `dream_ablation.py` — `load_cells` exclut `meta.source=='consolidate'`.
- **Modify** `~/AIOS/cockpit/public/dreams.js` — étiquette twin (retirer « ON seul »).
- **Tests** : étendre `tests/test_dream_ablation_pass.py` + `tests/test_dream_free_pass.py` (dreamer param) ; créer `tests/test_sonnet_arm_gate.py` ; étendre/créer `tests/test_dream_ablation_loadcells.py` (filtre consolidation + verdict concluant).

---

### Task 1: Config — flag du bras sonnet

**Files:** Modify `config.py` (~ligne 226) · Test `tests/test_sonnet_arm_gate.py` (bloc config)

**Interfaces:** Produces `config.DREAM_SONNET_ARM_ENABLED: bool`.

- [ ] **Step 1: Failing test**

```python
# tests/test_sonnet_arm_gate.py
import config

def test_sonnet_arm_flag_present():
    assert config.DREAM_SONNET_ARM_ENABLED in (True, False)
```

- [ ] **Step 2: Run → FAIL** `.venv/bin/python -m pytest tests/test_sonnet_arm_gate.py::test_sonnet_arm_flag_present -v` → `AttributeError`.

- [ ] **Step 3: Add flag** — dans `config.py`, juste après `DREAM_ABLATION_ENABLED` (~ligne 222) :

```python
DREAM_SONNET_ARM_ENABLED = os.environ.get("ANAMNESE_DREAM_SONNET_ARM", "1") == "1"  # bras sonnet contrôlé (3 conditions, nocturne)
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git add config.py tests/test_sonnet_arm_gate.py && git commit -m "feat(reve): flag DREAM_SONNET_ARM_ENABLED"`

---

### Task 2: Généraliser les 2 passes (paramètre `dreamer`)

**Files:** Modify `daemon.py` (`_dream_ablation_pass` ~280, `_dream_free_pass` ~310) · Test `tests/test_dream_ablation_pass.py` + `tests/test_dream_free_pass.py`

**Interfaces:**
- Produces `_dream_ablation_pass(mem, night_id, seed_state, menu, call_fn, dreamer="local", condition="brain_off", ablation="neutral_seeds")`
- Produces `_dream_free_pass(mem, night_id, seed_state, call_fn, dreamer="local")`

- [ ] **Step 1: Write failing tests** — AJOUTER à `tests/test_dream_ablation_pass.py` :

```python
def test_ablation_pass_dreamer_and_condition_params(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    out = "###CHOIX###\n- G1\n###REVE###\n- rêve.\n###FIN###"
    # sonnet ON (menu réel) : dreamer + condition + ablation paramétrés
    daemon._dream_ablation_pass(mem, "2026-07-10-0300", {"hormones": {}}, menu, lambda p: out,
                                dreamer="sonnet", condition="brain_on", ablation="real_seeds")
    dreamer, meta = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchone()
    m = json.loads(meta)
    assert dreamer == "sonnet" and m["condition"] == "brain_on" and m["ablation"] == "real_seeds"
```

AJOUTER à `tests/test_dream_free_pass.py` :

```python
def test_free_pass_dreamer_param(tmp_db):
    mem = FakeMem(tmp_db)
    daemon._dream_free_pass(mem, "2026-07-10-0300", {"hormones": {}}, lambda p: "###REVE###\n- x\n###FIN###",
                            dreamer="twin")
    dreamer, meta = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchone()
    assert dreamer == "twin" and json.loads(meta)["condition"] == "brain_off_free"
```

- [ ] **Step 2: Run → FAIL** (`TypeError: unexpected keyword argument 'dreamer'`)

- [ ] **Step 3: Generalize** — remplacer `_dream_ablation_pass` (daemon.py) par :

```python
def _dream_ablation_pass(mem, night_id, seed_state, menu, call_fn, dreamer="local",
                         condition="brain_off", ablation="neutral_seeds"):
    """Cellule menu-REM (JOURNAL-SEUL). Affect de seed_state, graines = `menu`.
    dreamer/condition/ablation paramétrés (défauts = v1 : local, brain_off, neutral_seeds).
    N'écrit RIEN dans le vivant. Best-effort."""
    try:
        if not menu:
            return
        try:
            state_blk = dream_lab.state_block(seed_state)
        except Exception:
            state_blk = ""
        out = call_fn(dream_lab.prompt_rem(state_blk, menu))
        if out is None:
            dream_lab.log_night(mem, night_id, dreamer, seed_state, menu, None, None,
                                written=False,
                                meta={"condition": condition, "ablation": ablation,
                                      "parse": "engine_failed"})
            return
        chosen = dream_lab.parse_choice(out, menu)
        dream_lab.log_night(mem, night_id, dreamer, seed_state, menu, chosen, out,
                            written=False,
                            meta={"condition": condition, "ablation": ablation,
                                  "parse": "ok" if chosen is not None else "parse_failed"})
    except Exception as e:
        try:
            print("[dream] ablation pass raté (rêve non bloqué):", e)
        except Exception:
            pass
```

Et `_dream_free_pass` par :

```python
def _dream_free_pass(mem, night_id, seed_state, call_fn, dreamer="local"):
    """Cellule free-OFF (rêve SANS graines, JOURNAL-SEUL). dreamer paramétré (défaut local).
    N'écrit RIEN dans le vivant. Best-effort."""
    try:
        try:
            state_blk = dream_lab.state_block(seed_state)
        except Exception:
            state_blk = ""
        out = call_fn(dream_lab.prompt_rem_free(state_blk))
        dream_lab.log_night(mem, night_id, dreamer, seed_state, None, None, out,
                            written=False,
                            meta={"condition": "brain_off_free", "ablation": "no_seeds",
                                  "parse": "engine_failed" if out is None else "ok"})
    except Exception as e:
        try:
            print("[dream] free pass raté (rêve non bloqué):", e)
        except Exception:
            pass
```

- [ ] **Step 4: Run → PASS** (nouveaux + les 4 existants) : `.venv/bin/python -m pytest tests/test_dream_ablation_pass.py tests/test_dream_free_pass.py -v`

- [ ] **Step 5: Commit** `git add daemon.py tests/test_dream_ablation_pass.py tests/test_dream_free_pass.py && git commit -m "feat(reve): passes ablation/free paramétrées par dreamer (défaut local inchangé)"`

---

### Task 3: Garde nocturne du bras sonnet (kv)

**Files:** Modify `daemon.py` (helpers près des passes) · Test `tests/test_sonnet_arm_gate.py`

**Interfaces:**
- Produces `_sonnet_arm_due(mem, night_id) -> bool` (True si pas encore tourné pour la DATE de night_id)
- Produces `_mark_sonnet_arm_done(mem, night_id) -> None`

- [ ] **Step 1: Failing tests** — AJOUTER à `tests/test_sonnet_arm_gate.py` :

```python
import daemon

class KvMem:
    def __init__(self): self._kv = {}
    def kv_get(self, k, d=""): return self._kv.get(k, d)
    def kv_set(self, k, v): self._kv[k] = v

def test_sonnet_arm_due_then_marked():
    mem = KvMem()
    assert daemon._sonnet_arm_due(mem, "2026-07-10-0300") is True      # jamais tourné
    daemon._mark_sonnet_arm_done(mem, "2026-07-10-0300")
    assert daemon._sonnet_arm_due(mem, "2026-07-10-0500") is False     # même DATE → plus dû
    assert daemon._sonnet_arm_due(mem, "2026-07-11-0300") is True      # date suivante → dû

def test_sonnet_arm_due_best_effort_on_error():
    class Boom:
        def kv_get(self, *a): raise RuntimeError("x")
    assert daemon._sonnet_arm_due(Boom(), "2026-07-10-0300") is True   # erreur → considère dû
```

- [ ] **Step 2: Run → FAIL** (`AttributeError: _sonnet_arm_due`)

- [ ] **Step 3: Add helpers** — dans `daemon.py`, juste après `_dream_free_pass` :

```python
def _sonnet_arm_due(mem, night_id):
    """True si le bras sonnet contrôlé n'a pas encore tourné pour la DATE de night_id
    (garde kv 'last_sonnet_arm'). Best-effort : erreur kv → considère dû."""
    date = (night_id or "")[:10]
    try:
        return mem.kv_get("last_sonnet_arm", "") != date
    except Exception:
        return True


def _mark_sonnet_arm_done(mem, night_id):
    """Marque le bras sonnet comme fait pour la DATE de night_id. Best-effort."""
    try:
        mem.kv_set("last_sonnet_arm", (night_id or "")[:10])
    except Exception:
        pass
```

- [ ] **Step 4: Run → PASS**

- [ ] **Step 5: Commit** `git add daemon.py tests/test_sonnet_arm_gate.py && git commit -m "feat(reve): garde nocturne kv du bras sonnet"`

---

### Task 4: `load_cells` — exclure les idées de consolidation

**Files:** Modify `dream_ablation.py` (`load_cells` ~135) · Test `tests/test_dream_ablation_loadcells.py`

**Interfaces:** Consumes/Produces `load_cells(conn)` (inchangé en signature ; nouveau filtre `meta.source=='consolidate'`).

- [ ] **Step 1: Failing test** — créer `tests/test_dream_ablation_loadcells.py` :

```python
import json
import dream_ablation as A

def _mk(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, night_id TEXT, "
                 "dreamer TEXT, menu TEXT, content TEXT, meta TEXT)")

def test_load_cells_excludes_consolidation_ideas(tmp_db):
    _mk(tmp_db)
    # idée libre de consolidation (source=consolidate) : NE doit PAS devenir une cellule sonnet
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,menu,content,meta) VALUES "
                   "('2026-07-10','sonnet',NULL,'(rêve) idée libre',?)",
                   (json.dumps({"source": "consolidate", "model": "sonnet"}),))
    # rêve-REM sonnet contrôlé (condition explicite) : DOIT être une cellule
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,menu,content,meta) VALUES "
                   "('2026-07-10','sonnet','[]','###REVE### contrôlé',?)",
                   (json.dumps({"condition": "brain_on", "ablation": "real_seeds"}),))
    tmp_db.commit()
    cells = A.load_cells(tmp_db)["cells"]
    assert ("sonnet", "brain_on") in cells
    contents = [c for by in cells[("sonnet", "brain_on")].values() for c in by]
    assert "###REVE### contrôlé" in contents
    assert "(rêve) idée libre" not in contents        # idée de consolidation EXCLUE
```

- [ ] **Step 2: Run → FAIL** (l'idée de consolidation est incluse).

- [ ] **Step 3: Add filter** — dans `dream_ablation.load_cells`, juste après `m = _json.loads(meta) if meta else {}` :

```python
        if m.get("source") == "consolidate":   # idées libres de consolidation ≠ rêve-REM contrôlé → hors cellules
            continue
```

- [ ] **Step 4: Run → PASS** + non-régression verdict : `.venv/bin/python -m pytest tests/test_dream_ablation_loadcells.py tests/test_dream_ablation.py tests/test_dream_ablation_verdict.py tests/test_dream_porte_c.py -q`

- [ ] **Step 5: Commit** `git add dream_ablation.py tests/test_dream_ablation_loadcells.py && git commit -m "feat(reve): load_cells exclut les idées de consolidation (cellules = rêve-REM contrôlé)"`

---

### Task 5: Câbler `dream()` — twin OFF/libre + bras sonnet

**Files:** Modify `daemon.py` (`dream()` bloc ablation ~499-526)

**Interfaces:** Consumes `_dream_ablation_pass`/`_dream_free_pass` (T2), `_sonnet_arm_due`/`_mark_sonnet_arm_done` (T3), `config.DREAM_SONNET_ARM_ENABLED` (T1), `synthesis_claude.claude_chat`.

- [ ] **Step 1: Write the failing integration test** — créer `tests/test_dream_grid_wiring.py`. Ce test appelle une version réduite du câblage via un helper extrait, OU vérifie la présence des lignes. Approche retenue : extraire la logique de câblage dans une fonction testable `_dream_extra_cells(mem, night_id, seed_state, menu, neutral_menu, tw_state, call_fn, sonnet_fn)` et la tester.

```python
import json, daemon

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self._kv = {}
        conn.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, "
            "content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): raise AssertionError("add interdit (journal-seul)")
    def log_coactivation(self, *a, **k): raise AssertionError("coact interdit")
    def kv_get(self, k, d=""): return self._kv.get(k, d)
    def kv_set(self, k, v): self._kv[k] = v

def _rem(p): return "###CHOIX###\n- G1\n###REVE###\n- x\n###FIN###"

def test_extra_cells_generates_twin_and_sonnet(tmp_db, monkeypatch):
    monkeypatch.setattr(daemon.config, "DREAM_TWIN_ENABLED", True)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_ARM_ENABLED", True)
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    daemon._dream_extra_cells(mem, "2026-07-10-0300", {"hormones": {}}, menu, menu,
                              {"hormones": {}}, _rem, _rem)
    got = {(d, json.loads(mt).get("condition")) for d, mt in
           mem.db.execute("SELECT dreamer, meta FROM dream_log")}
    assert ("twin", "brain_off") in got and ("twin", "brain_off_free") in got
    assert ("sonnet", "brain_on") in got and ("sonnet", "brain_off") in got and ("sonnet", "brain_off_free") in got
    assert mem.kv_get("last_sonnet_arm") == "2026-07-10"        # garde posée

def test_extra_cells_sonnet_once_per_night(tmp_db, monkeypatch):
    monkeypatch.setattr(daemon.config, "DREAM_TWIN_ENABLED", False)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_ARM_ENABLED", True)
    mem = FakeMem(tmp_db); mem.kv_set("last_sonnet_arm", "2026-07-10")   # déjà fait ce soir
    daemon._dream_extra_cells(mem, "2026-07-10-0500", {"hormones": {}}, [{"snippet":"x"}], [{"snippet":"x"}],
                              {"hormones": {}}, _rem, _rem)
    got = [r[0] for r in mem.db.execute("SELECT dreamer FROM dream_log")]
    assert "sonnet" not in got        # garde nocturne respectée
```

- [ ] **Step 2: Run → FAIL** (`AttributeError: _dream_extra_cells`)

- [ ] **Step 3: Extract + implement `_dream_extra_cells`** — ajouter dans `daemon.py` (après `_mark_sonnet_arm_done`) :

```python
def _dream_extra_cells(mem, night_id, seed_state, menu, neutral_menu, tw_state, call_fn, sonnet_fn):
    """Génère les cellules SUPPLÉMENTAIRES de la grille (best-effort, journal-seul) :
    - twin (affect neutre) : OFF-neutre + OFF-libre — 9B local, chaque rêve ;
    - bras sonnet contrôlé (affect réel) : ON + OFF-neutre + OFF-libre — cadence NOCTURNE (garde kv).
    call_fn = moteur local (9B) ; sonnet_fn = claude_chat."""
    if config.DREAM_TWIN_ENABLED and neutral_menu:
        _dream_ablation_pass(mem, night_id, tw_state, neutral_menu, call_fn, dreamer="twin")
        _dream_free_pass(mem, night_id, tw_state, call_fn, dreamer="twin")
    if config.DREAM_SONNET_ARM_ENABLED and _sonnet_arm_due(mem, night_id):
        _dream_ablation_pass(mem, night_id, seed_state, menu, sonnet_fn,
                             dreamer="sonnet", condition="brain_on", ablation="real_seeds")
        _dream_ablation_pass(mem, night_id, seed_state, neutral_menu, sonnet_fn,
                             dreamer="sonnet", condition="brain_off", ablation="neutral_seeds")
        _dream_free_pass(mem, night_id, seed_state, sonnet_fn, dreamer="sonnet")
        _mark_sonnet_arm_done(mem, night_id)
```

Puis, dans `dream()`, DANS le bloc `if config.DREAM_ABLATION_ENABLED:` (après `_dream_free_pass(...)` local, ~ligne 524), ajouter l'appel — en s'assurant que `tw_state` est disponible (le calculer si le bloc twin ne l'a pas déjà fait) :

```python
                # grille complète : twin OFF/libre + bras sonnet contrôlé (best-effort)
                try:
                    import synthesis_claude
                    tw_state_x = dream_lab.neutralize(seed_state)
                    _dream_extra_cells(mem, night_id, seed_state, menu, neutral_menu,
                                       tw_state_x, _call, synthesis_claude.claude_chat)
                except Exception as e:
                    print("[dream] cellules grille sautées (rêve non bloqué):", e)
```

- [ ] **Step 4: Run → PASS** (`test_dream_grid_wiring.py`) + non-régression `tests/test_dream_night.py`.

- [ ] **Step 5: Commit** `git add daemon.py tests/test_dream_grid_wiring.py && git commit -m "feat(reve): dream() génère twin OFF/libre + bras sonnet contrôlé (nocturne)"`

---

### Task 6: Cockpit — étiquette twin + grille

**Files:** Modify `~/AIOS/cockpit/public/dreams.js` (~ligne 77)

- [ ] **Step 1: Update label** — remplacer :

```javascript
    ${modelRow('twin', 'b-twin', '👻 jumeau qwen (affect neutralisé — ON seul)')}
```

par :

```javascript
    ${modelRow('twin', 'b-twin', '👻 jumeau qwen (affect neutralisé — 3 conditions)')}
```

- [ ] **Step 2: Verify** `node --check ~/AIOS/cockpit/public/dreams.js` → exit 0. (La grille se remplit automatiquement : `pickCell(rows, dreamer, cond)` trouve les nouvelles lignes twin/sonnet.)

- [ ] **Step 3** (cockpit hors git) : redémarrer le cockpit pour recharger, `curl` `/api/dreams?night=<date>` pour confirmer les nouvelles lignes après un cycle de rêve.

---

## Self-Review (plan vs objectif)

- **Débloquer le verdict** : sonnet devient un bras contrôlé 3-conditions (T5) + load_cells n'utilise que le REM contrôlé (T4) → Portes A/B/C évaluables ✓.
- **Contrôles** : négatif (OFF-libre, T2/T5), dose-réponse (sonnet ON/OFF, T5), cross-archi (sonnet vs qwen même corpus, T5), plancher (twin OFF/libre, T5), pré-enreg. (verdict inchangé) ✓.
- **Non-régression** : défaut `dreamer='local'` (T2) garde les 4 tests de passes verts ; verdict/portes inchangés ; journal-seul préservé (FakeMem interdit add/coact).
- **Placeholders** : aucun — code réel à chaque étape.
- **Types cohérents** : `_dream_ablation_pass(...dreamer,condition,ablation)`, `_dream_free_pass(...dreamer)`, `_sonnet_arm_due(mem,night_id)->bool`, `_dream_extra_cells(mem,night_id,seed_state,menu,neutral_menu,tw_state,call_fn,sonnet_fn)`.
