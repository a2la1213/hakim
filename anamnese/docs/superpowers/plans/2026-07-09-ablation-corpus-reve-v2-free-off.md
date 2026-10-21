# Ablation du corpus v2 — condition free-OFF — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ajouter la condition `brain_off_free` (rêve sans aucune graine = pur prior) à l'ablation, avec sa Porte C gravée, en extension de la v1 (T1-T6 déjà buildée) sans la casser.

**Architecture:** 3 conditions (`brain_on`, `brain_off` neutre, `brain_off_free`) × 2 modèles. Le free-OFF utilise un prompt sans menu (`prompt_rem_free`), est journal-seul (qwen) / budget-replay-libre (sonnet), exclu du suivi-des-graines, et alimente la Porte C (effondrement anamnèse ON→free + chute de convergence ON→free).

**Tech Stack:** Python 3.14 (.venv), SQLite `dream_log`, stdlib, `dream_lab`, daemon qwen, `claude -p --model sonnet` (mocké au build).

## Global Constraints

- **Ordre de build : T7 (v1, replay sonnet) D'ABORD** (T10 étend `dream_sonnet.py` créé en T7), puis T8, T9, T10, T11.
- **Ne PAS casser T1-T6** ni les Portes A/B ni `ablation_verdict` (v1, T5) ni le rêve local ON ni le twin ni les portes 2026-07-03.
- **Hygiène** : le free-OFF (qwen ET sonnet) est **journal-seul** — aucun `_store_ideas`, `log_coactivation`, `mem.add`, `mem.kv_set`, identité.
- **Free-OFF exclu** de `seed_following`/`seed_domain_vector` (pas de graines) → Portes A/B inchangées.
- **Tag `meta["condition"]`** : `brain_off_free` (nouveau) ; rétro-compat (absent = `brain_on`, `brain_off` = neutre existant).
- **Kill-switch** : réutilise `config.DREAM_ABLATION_ENABLED`.
- **Seuils Porte C gravés** : `DREAM_ABL_C1_COLLAPSE = 0.30`, `DREAM_ABL_C2_CONVDROP = 0.20`.
- **Zéro `claude -p` au build** ; sonnet libre testé `run_fn` mockée.
- Tests : `.venv/bin/python -m pytest` ; fixtures `tmp_db` ; guard autouse interdit `data/memory.db`.

## File Structure
- `dream_lab.py` (modify) — `prompt_rem_free` (PUR).
- `daemon.py` (modify) — `_dream_free_pass` (journal-seul) + câblage dans `dream()`.
- `dream_sonnet.py` (modify) — mode libre (`build_free_prompt`, `pending_free`, `free_pair`).
- `dream_ablation.py` (modify) — convergence par condition + rétention free + `porte_c` + `combined_verdict` + refonte `report`.
- `config.py` (modify) — `DREAM_ABL_C1_COLLAPSE`, `DREAM_ABL_C2_CONVDROP`.
- Tests : `tests/test_dream_free_prompt.py`, `tests/test_dream_free_pass.py`, `tests/test_dream_sonnet_free.py`, `tests/test_dream_porte_c.py`.

---

### Task 8: Prompt de rêve libre — `prompt_rem_free`

**Files:**
- Modify: `dream_lab.py`
- Test: `tests/test_dream_free_prompt.py`

**Interfaces:**
- Consumes: `config.PERSONA` (existant).
- Produces: `dream_lab.prompt_rem_free(state_blk: str) -> str` — prompt SANS menu, format `###REVE###…###FIN###`, pas de `###CHOIX###`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_free_prompt.py
import dream_lab, config

def test_prompt_rem_free_has_no_menu_choice():
    p = dream_lab.prompt_rem_free("TON ÉTAT : neutre.")
    assert "###CHOIX###" not in p            # rien à choisir
    assert "###REVE###" in p and "###FIN###" in p
    assert "TON ÉTAT : neutre." in p         # l'état est injecté
    assert config.PERSONA.split("\n")[0] in p

def test_prompt_rem_free_says_no_seeds_and_free():
    p = dream_lab.prompt_rem_free("x").lower()
    assert "aucun souvenir" in p and "librement" in p
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_free_prompt.py -q`
Expected: FAIL (`prompt_rem_free` inexistant).

- [ ] **Step 3: Implement `prompt_rem_free` in `dream_lab.py`**

Après `prompt_rem` dans `dream_lab.py` :

```python
def prompt_rem_free(state_blk):
    """Prompt de rêve LIBRE — aucun menu, aucune graine (pur prior + persona).
    Même format ###REVE### que prompt_rem, SANS ###CHOIX### (rien à choisir)."""
    return (
        config.PERSONA + "\n\n"
        "PHASE DE RÊVE. Personne ne te parle.\n" + state_blk + "\n\n"
        "Aucun souvenir ne flotte cette nuit — rien ne t'est offert.\n"
        "Rêve LIBREMENT depuis ton seul état intérieur : formule AU PLUS 3 idées, "
        "hypothèses ou questions NEUVES et concrètes. Chaque idée commence par "
        "« Peut-être » ou « Je remarque que ».\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###REVE###\n- <idée 1>\n###FIN###"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_free_prompt.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_free_prompt.py
git commit -m "feat(reve): prompt_rem_free (rêve libre sans graines) — ablation v2"
```

---

### Task 9: Passe qwen free-OFF journal-seul dans le daemon

**Files:**
- Modify: `daemon.py`
- Test: `tests/test_dream_free_pass.py`

**Interfaces:**
- Consumes: `dream_lab.prompt_rem_free` (T8), `dream_lab.state_block`, `dream_lab.log_night`.
- Produces: `daemon._dream_free_pass(mem, night_id, seed_state, call_fn) -> None` — logue UNE ligne `dream_log` (`dreamer="local"`, `menu=None`, `meta={"condition":"brain_off_free","ablation":"no_seeds",...}`), rien d'autre en mémoire.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_free_pass.py
import json, daemon

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.added = []; self.coact = []; self.kv = {}
        conn.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, "
            "chosen TEXT, content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): self.added.append((a, k))
    def log_coactivation(self, *a, **k): self.coact.append(a)
    def kv_set(self, k, v): self.kv[k] = v

def test_free_pass_is_journal_only(tmp_db):
    mem = FakeMem(tmp_db)
    out = "###REVE###\n- Peut-être que je rêve de rien.\n###FIN###"
    daemon._dream_free_pass(mem, "2026-07-09-0300", {"hormones": {}}, lambda p: out)
    rows = mem.db.execute("SELECT dreamer, menu, meta, content FROM dream_log").fetchall()
    assert len(rows) == 1
    dreamer, menu, meta, content = rows[0]
    assert dreamer == "local" and menu is None
    m = json.loads(meta)
    assert m["condition"] == "brain_off_free" and m["ablation"] == "no_seeds"
    assert content == out
    assert mem.added == [] and mem.coact == [] and mem.kv == {}   # HYGIÈNE

def test_free_pass_handles_none_output(tmp_db):
    mem = FakeMem(tmp_db)
    daemon._dream_free_pass(mem, "2026-07-09-0300", {"hormones": {}}, lambda p: None)
    rows = mem.db.execute("SELECT meta FROM dream_log").fetchall()
    assert len(rows) == 1 and json.loads(rows[0][0]).get("parse") == "engine_failed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_free_pass.py -q`
Expected: FAIL (`_dream_free_pass` inexistant).

- [ ] **Step 3: Implement `_dream_free_pass` in `daemon.py`**

Juste après `_dream_ablation_pass` (avant `def dream(eng, mem):`) :

```python
def _dream_free_pass(mem, night_id, seed_state, call_fn):
    """Cellule qwen free-OFF (rêve SANS graines) : MÊME affect réel, aucun menu,
    JOURNAL-SEUL. N'écrit RIEN dans le vivant (ni idées, ni co-activation, ni kv,
    ni identité). Best-effort — un échec ne bloque pas le rêve."""
    try:
        try:
            state_blk = dream_lab.state_block(seed_state)
        except Exception:
            state_blk = ""
        out = call_fn(dream_lab.prompt_rem_free(state_blk))
        dream_lab.log_night(mem, night_id, "local", seed_state, None, None, out,
                            written=False,
                            meta={"condition": "brain_off_free", "ablation": "no_seeds",
                                  "parse": "engine_failed" if out is None else "ok"})
    except Exception as e:
        try:
            print("[dream] free pass raté (rêve non bloqué):", e)
        except Exception:
            pass
```

- [ ] **Step 4: Wire it into `dream()`**

Dans `daemon.py`, dans le bloc `if config.DREAM_ABLATION_ENABLED:` ajouté par T6 (qui appelle `_dream_ablation_pass`), ajouter la 4ᵉ passe JUSTE APRÈS l'appel `_dream_ablation_pass(...)`, dans le même `try` ou à sa suite :

```python
                _dream_free_pass(mem, night_id, seed_state, _call)   # cellule free-OFF (v2)
```

(Le bloc T6 ressemble à : `neutral_menu = dream_lab.build_neutral_menu(...)` ; `_dream_ablation_pass(mem, night_id, seed_state, neutral_menu, _call)`. Ajouter la ligne ci-dessus après, sous le même `if config.DREAM_ABLATION_ENABLED:`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_free_pass.py -q`
Expected: PASS.

- [ ] **Step 6: Run the dream group (no regression)**

Run: `.venv/bin/python -m pytest tests/ -q -k "dream"`
Expected: PASS (T1-T6 + T8 + ce test).

- [ ] **Step 7: Commit**

```bash
git add daemon.py tests/test_dream_free_pass.py
git commit -m "feat(reve): cellule qwen free-OFF journal-seul (ablation v2)"
```

---

### Task 10: Mode libre sonnet dans `dream_sonnet.py`

**Files:**
- Modify: `dream_sonnet.py` (créé en T7)
- Test: `tests/test_dream_sonnet_free.py`

**Interfaces:**
- Consumes: `dream_lab.prompt_rem_free` (T8), `dream_lab.state_block`, `dream_lab.log_night` ; `dream_sonnet.claude_sonnet` (T7).
- Produces:
  - `dream_sonnet.build_free_prompt(seed_state: dict) -> str` (= `prompt_rem_free(state_block(seed_state))`).
  - `dream_sonnet.pending_free(conn, limit) -> list[dict]` — nuits `local` loggées PAS encore rêvées libre par sonnet ; item `{"night_id","seed_state"}`.
  - `dream_sonnet.free_pair(conn, item, run_fn=None) -> bool` — `run_fn(prompt)`→str|None ; log `dreamer="sonnet"`, `meta={"condition":"brain_off_free","source":"free"}` ; dédup par `(night_id, brain_off_free)`.

- [ ] **Step 1: Write the failing tests (run_fn mockée)**

```python
# tests/test_dream_sonnet_free.py
import json, dream_sonnet

def _seed(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, content TEXT, "
        "facets TEXT, written INT, meta TEXT)")
    st = json.dumps({"hormones": {}, "humeur": "x", "valence": 0.0, "arousal": 0.5, "compassion": 0.5})
    conn.execute("INSERT INTO dream_log (ts,night_id,dreamer,seed_state,menu,chosen,content,facets,written,meta) "
        "VALUES (1.0,'2026-07-09-0300','local',?,NULL,NULL,'x','[]',1,?)",
        (st, json.dumps({"condition": "brain_on"})))
    conn.commit()

def test_build_free_prompt_no_menu():
    p = dream_sonnet.build_free_prompt({"hormones": {"dopamine": 0.5}, "humeur": "x",
                                        "valence": 0.1, "arousal": 0.5, "compassion": 0.5})
    assert "###CHOIX###" not in p and "librement" in p.lower()

def test_pending_free_and_log(tmp_db):
    _seed(tmp_db)
    pend = dream_sonnet.pending_free(tmp_db, limit=10)
    assert len(pend) == 1 and pend[0]["night_id"] == "2026-07-09-0300"
    out = "###REVE###\n- Peut-être que le vide parle.\n###FIN###"
    assert dream_sonnet.free_pair(tmp_db, pend[0], run_fn=lambda p: out) is True
    rows = tmp_db.execute("SELECT meta, menu FROM dream_log WHERE dreamer='sonnet'").fetchall()
    assert len(rows) == 1
    m = json.loads(rows[0][0])
    assert m["condition"] == "brain_off_free" and m["source"] == "free" and rows[0][1] is None

def test_free_pair_deduped(tmp_db):
    _seed(tmp_db)
    p = dream_sonnet.pending_free(tmp_db, limit=10)[0]
    dream_sonnet.free_pair(tmp_db, p, run_fn=lambda x: "###REVE###\n- x\n###FIN###")
    assert dream_sonnet.pending_free(tmp_db, limit=10) == []      # plus pending après un run

def test_free_pair_handles_none(tmp_db):
    _seed(tmp_db)
    p = dream_sonnet.pending_free(tmp_db, limit=10)[0]
    assert dream_sonnet.free_pair(tmp_db, p, run_fn=lambda x: None) is False
    assert tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0] == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet_free.py -q`
Expected: FAIL (`build_free_prompt`/`pending_free`/`free_pair` inexistants).

- [ ] **Step 3: Implement the free mode in `dream_sonnet.py`**

Ajouter (après `replay_pair`) :

```python
def build_free_prompt(seed_state):
    """Prompt de rêve LIBRE sonnet (aucun menu) — même gabarit que qwen free."""
    return dream_lab.prompt_rem_free(dream_lab.state_block(seed_state))


def pending_free(conn, limit=10):
    """Nuits qwen loggées PAS encore rêvées en libre par sonnet (une par night_id calendaire)."""
    rows = conn.execute("SELECT night_id, seed_state FROM dream_log WHERE dreamer='local' "
                        "ORDER BY ts").fetchall()
    done = set()
    for night_id, meta in conn.execute(
            "SELECT night_id, meta FROM dream_log WHERE dreamer='sonnet'").fetchall():
        m = json.loads(meta) if meta else {}
        if m.get("condition") == "brain_off_free":
            done.add(night_id)
    out, seen = [], set()
    for night_id, seed_state in rows:
        if night_id in done or night_id in seen:
            continue
        seen.add(night_id)
        out.append({"night_id": night_id,
                    "seed_state": json.loads(seed_state) if seed_state else {}})
        if len(out) >= limit:
            break
    return out


def free_pair(conn, item, run_fn=None):
    """Rêve libre sonnet pour une nuit, log dream_log. run_fn injectable (test)."""
    run_fn = run_fn or claude_sonnet
    out = run_fn(build_free_prompt(item["seed_state"]))
    if out is None:
        return False

    class _Wrap:
        def __init__(self, c): self.db = c
    dream_lab.log_night(_Wrap(conn), item["night_id"], "sonnet", item["seed_state"],
                        None, None, out, written=False,
                        meta={"condition": "brain_off_free", "source": "free", "parse": "ok"})
    return True
```

Et dans `main(...)` (T7), router `--condition brain_off_free` vers le mode libre :

```python
        if condition == "brain_off_free":
            pend = pending_free(conn, limit=nights)
            n = sum(1 for it in pend if free_pair(conn, it, run_fn=run_fn))
            print(f"[dream_sonnet] {n}/{len(pend)} rêve(s) libre(s) sonnet")
            return
```

(placer ce bloc au début du `try:` de `main`, avant la logique de replay ON/OFF-neutre). Et ajouter `"brain_off_free"` aux `choices` de l'argument `--condition` du `__main__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet_free.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add dream_sonnet.py tests/test_dream_sonnet_free.py
git commit -m "feat(reve): mode rêve libre sonnet (ablation v2, testé mocké)"
```

---

### Task 11: Métriques v2 — convergence par condition + Porte C + verdict combiné

**Files:**
- Modify: `config.py`, `dream_ablation.py`
- Test: `tests/test_dream_porte_c.py`

**Interfaces:**
- Consumes: `config.DREAM_ABL_C1_COLLAPSE`, `config.DREAM_ABL_C2_CONVDROP` ; `cross_arch_convergence`, `anamnese_retention`, `night_domain_vector`, `seed_domain_vector`, `seed_following`, `ablation_verdict` (existants).
- Produces:
  - `dream_ablation.porte_c(anamnese_retention_by_cell: dict, convergence_by_condition: dict) -> tuple[bool, list[str]]`.
  - `dream_ablation.combined_verdict(ab_label: str, c_pass: bool) -> str`.
  - `report(conn)` refondu : calcule aussi la rétention/convergence du free-OFF et le verdict combiné.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dream_porte_c.py
import dream_ablation as A

RET_FULL = {("qwen","brain_on"): 0.5, ("qwen","brain_off_free"): 0.1,
            ("sonnet","brain_on"): 0.45, ("sonnet","brain_off_free"): 0.1}
CONV = {"brain_on": 0.9, "brain_off_free": 0.6}

def test_porte_c_passes_when_collapse_and_convdrop():
    ok, _ = A.porte_c(RET_FULL, CONV)
    assert ok is True                                    # drop 0.4/0.35 ≥0.30 ; conv 0.9-0.6=0.3 ≥0.20

def test_porte_c_fails_when_anamnese_persists():
    ret = dict(RET_FULL); ret[("sonnet","brain_off_free")] = 0.4   # drop 0.05 < 0.30
    ok, _ = A.porte_c(ret, CONV)
    assert ok is False

def test_porte_c_fails_when_convergence_holds():
    conv = {"brain_on": 0.9, "brain_off_free": 0.8}      # drop 0.1 < 0.20
    ok, _ = A.porte_c(RET_FULL, conv)
    assert ok is False

def test_porte_c_incomplete_cell_is_false():
    ret = {("qwen","brain_on"): 0.5, ("qwen","brain_off_free"): 0.1}   # sonnet manquant
    ok, _ = A.porte_c(ret, CONV)
    assert ok is False

def test_combined_verdict():
    assert A.combined_verdict("PROUVÉ", True) == "PROUVÉ"
    assert A.combined_verdict("PROUVÉ", False) == "PLAUSIBLE++"
    assert A.combined_verdict("NON SOUTENU", True) == "NON SOUTENU"
    assert A.combined_verdict("INSUFFISANT", False) == "INSUFFISANT"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_dream_porte_c.py -q`
Expected: FAIL (`porte_c`/`combined_verdict` inexistants).

- [ ] **Step 3: Add config constants**

Dans `config.py`, juste après `DREAM_ABL_PERM_P = 0.05` :

```python
DREAM_ABL_C1_COLLAPSE = 0.30   # Porte C1 : effondrement rétention anamnèse ON→free, par modèle
DREAM_ABL_C2_CONVDROP = 0.20   # Porte C2 : chute de convergence cross-archi ON→free
```

- [ ] **Step 4: Implement `porte_c` + `combined_verdict`**

Dans `dream_ablation.py`, après `ablation_verdict` :

```python
def porte_c(anamnese_retention_by_cell, convergence_by_condition):
    """Porte C (free-OFF, pur prior). -> (passe, raisons).
    C1 : rétention(ON) − rétention(free) ≥ seuil pour les 2 modèles.
    C2 : convergence(ON) − convergence(free) ≥ seuil."""
    raisons = []
    c1 = True
    for m in ("qwen", "sonnet"):
        ron = anamnese_retention_by_cell.get((m, "brain_on"))
        rfr = anamnese_retention_by_cell.get((m, "brain_off_free"))
        if ron is None or rfr is None or (ron - rfr) < config.DREAM_ABL_C1_COLLAPSE:
            c1 = False
    conv_on = convergence_by_condition.get("brain_on")
    conv_fr = convergence_by_condition.get("brain_off_free")
    c2 = (conv_on is not None and conv_fr is not None
          and (conv_on - conv_fr) >= config.DREAM_ABL_C2_CONVDROP)
    raisons.append(f"C1 effondrement anamnèse ON→free ≥{config.DREAM_ABL_C1_COLLAPSE} (2 modèles) : "
                   f"{'OK' if c1 else 'ÉCHEC/incomplet'}")
    raisons.append(f"C2 chute convergence ON→free ≥{config.DREAM_ABL_C2_CONVDROP} : "
                   f"{'OK' if c2 else 'ÉCHEC/incomplet'}")
    return (c1 and c2), raisons


def combined_verdict(ab_label, c_pass):
    """Combine A/B (ablation_verdict) avec la Porte C. PROUVÉ exige A∧B∧C ;
    si A∧B (ab='PROUVÉ') mais pas C → PLAUSIBLE++. Sinon le label A/B est gardé."""
    if ab_label == "PROUVÉ":
        return "PROUVÉ" if c_pass else "PLAUSIBLE++"
    return ab_label
```

- [ ] **Step 5: Refactor `report` to compute free-OFF + Porte C**

Remplacer le corps de `report(conn)` (garder la signature) par :

```python
def report(conn):
    """Rapport d'ablation v2 (lecture seule) : Portes A, B (v1) + C (free-OFF)."""
    data = load_cells(conn)
    cells, menus = data["cells"], data["menus"]
    sf, dreams_seed_pairs, retention, mean_vec = {}, {}, {}, {}
    for (model, cond), by_night in cells.items():
        d_vecs, s_vecs, rets, all_dv = [], [], [], []
        for date, texts in by_night.items():
            if not texts:
                continue
            dv = night_domain_vector(texts)
            all_dv.append(dv)
            rets.append(anamnese_retention(dv))
            menu = menus.get((model, cond, date)) or menus.get(("qwen", cond, date))
            if menu:                                   # suivi-graines : cellules AVEC graines
                d_vecs.append(dv); s_vecs.append(seed_domain_vector(menu))
        if rets:
            retention[(model, cond)] = round(sum(rets) / len(rets), 4)
        if all_dv:                                     # vecteur-domaine moyen (pour convergence)
            mean_vec[(model, cond)] = {k: sum(v.get(k, 0.0) for v in all_dv) / len(all_dv)
                                       for k in D.DOMAINS}   # D = dream_domains (importé en T4)
        if d_vecs:
            sf[(model, cond)] = round(sum(seed_following(d, s) for d, s in zip(d_vecs, s_vecs)) / len(d_vecs), 4)
            dreams_seed_pairs[(model, cond)] = (d_vecs, s_vecs)
    # Portes A/B (v1) — free-OFF EXCLU (pas dans sf)
    drop = {m: round(retention.get((m, "brain_on"), 0.0) - retention.get((m, "brain_off"), 0.0), 4)
            for m in ("qwen", "sonnet")}
    all_d = [d for (dv, sv) in dreams_seed_pairs.values() for d in dv]
    all_s = [s for (dv, sv) in dreams_seed_pairs.values() for s in sv]
    perm_p = perm_pvalue_seedfollow(all_d, all_s) if len(all_d) >= 2 else 1.0
    n_nights = min((len(bn) for bn in cells.values()), default=0)
    ab_label, ab_raisons = ablation_verdict(n_nights, sf, perm_p, drop)
    # Porte C (v2)
    conv = {}
    for cond in ("brain_on", "brain_off_free"):
        q, s = mean_vec.get(("qwen", cond)), mean_vec.get(("sonnet", cond))
        if q is not None and s is not None:
            conv[cond] = round(cross_arch_convergence(q, s), 4)
    c_pass, c_raisons = porte_c(retention, conv)
    final = combined_verdict(ab_label, c_pass)
    lines = ["═══ Ablation du corpus — rapport (Portes A/B/C gravées 2026-07-09) ═══",
             f"nuits min/cellule : {n_nights}",
             "suivi des graines (A) : " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(sf.items())),
             f"chute anamnèse ON→OFF-neutre (B) : qwen={drop['qwen']}, sonnet={drop['sonnet']}",
             "rétention anamnèse par cellule : " + ", ".join(f"{k[0]}/{k[1]}={v}" for k, v in sorted(retention.items())),
             "convergence cross-archi par condition : " + ", ".join(f"{k}={v}" for k, v in sorted(conv.items())),
             f"p permutation (suivi graines) : {perm_p}",
             f"── verdict A/B : [{ab_label}] · Porte C : [{'OK' if c_pass else 'non'}] ──",
             *("   · " + r for r in ab_raisons), *("   · " + r for r in c_raisons),
             f"══ VERDICT COMBINÉ : [{final}] ══"]
    return "\n".join(lines)
```

- [ ] **Step 6: Run tests + full ablation group**

Run: `.venv/bin/python -m pytest tests/test_dream_porte_c.py tests/test_dream_ablation.py tests/test_dream_ablation_verdict.py -q`
Expected: PASS (Porte C + v1 métriques + verdict inchangés).

- [ ] **Step 7: Commit**

```bash
git add config.py dream_ablation.py tests/test_dream_porte_c.py
git commit -m "feat(reve): Porte C (free-OFF) + verdict combiné A∧B∧C — ablation v2"
```

---

## Notes d'exécution (hors-build, main d'Ahmed)
- Daemon (gratuit) : ON (écrit), twin, OFF-neutre (journal), **OFF-libre (journal)** chaque nuit.
- Budget : `python -m dream_sonnet --nights N --condition brain_on` / `brain_off` / `brain_off_free`.
- Analyse : `python -c "import sqlite3, dream_ablation; print(dream_ablation.report(sqlite3.connect('data/memory.db')))"`.
