# Expérience-rêve (préférences fonctionnelles émergentes) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transformer le rêve local débranché en expérience falsifiable : chaque nuit, un rêve RÉEL (état interne complet, écrit en mémoire) + un JUMEAU FANTÔME (état neutralisé, journal seulement), sur le même menu de graines — pour mesurer si Anamnèse exprime des préférences fonctionnelles émergentes.

**Architecture:** Une couche d'instrumentation `dream_lab.py` (snapshot d'état, menu stratifié, parsing du choix libre, journal `dream_log`) sous un `daemon.dream()` refondu en REM pur ; un module `dream_metrics.py` (stdlib pur) applique les seuils pré-enregistrés ; `consolidate.py` logge les rêves Sonnet en lecture seule ; le cockpit expose `/api/dreams` + une page. Spec : `docs/superpowers/specs/2026-07-03-experience-reve-design.md`.

**Tech Stack:** Python 3.14 (.venv), SQLite (WAL), Ollama local (9B, via `engine.Engine`), pytest, Node.js sans dépendance (cockpit), vanilla JS.

## Global Constraints

- 100% offline ; stdlib uniquement pour les métriques (PAS de scipy/numpy — Spearman à la main, p-value par permutation seedée).
- Tests : DB temporaire migrée, JAMAIS `data/memory.db` (garde autouse dans `conftest.py`). Générations LLM toujours simulées (FakeEngine) — aucun test ne parle à Ollama.
- **Invariant sacré** : une génération `dreamer='twin'` n'écrit RIEN dans `episodes`/`coactivation`/`kv` — compté dans les tests, pas supposé.
- Seuils de verdict PRÉ-ENREGISTRÉS (spec, ne pas ajuster) : n ≥ 20 nuits ; stabilité r > 0.5 ; divergence > 2× plancher de bruit ; corrélation état Spearman |r| ≥ 0.5, p < 0.05 Bonferroni ×9 ; [BRUIT] si |r| < 0.2.
- Kill-switch `config.DREAM_LAB_ENABLED` (env `ANAMNESE_DREAM_LAB`) → comportement actuel (pas de rêve local).
- Patterns daemon conservés : lock `dream_lock`, curseur `last_dream_maxid` avancé en dernier, `dream_fail_count`/poison-pill, garde `last_shy`, try/except « ne casse jamais le rêve ».
- Le jumeau reçoit le MÊME gabarit de prompt avec les valeurs baseline (`affect.HORMONES`), humeur « neutre », `wm_focus` IDENTIQUE au réel (contenu mnésique ≠ affect).
- `dream_log` : l'écriture ne bloque JAMAIS un rêve (best-effort). Le hook Sonnet ne casse JAMAIS la consolidation.
- Commits fréquents, messages en français, sur une branche `experience-reve` (merge --no-ff en fin de phase).

## File Structure

| Fichier | Rôle |
|---|---|
| `dream_lab.py` (create) | instrumentation : état, menu, prompt, parsing, journal |
| `dream_metrics.py` (create) | métriques pures + verdict pré-enregistré |
| `migrations.py` (modify) | table `dream_log` + index dans `NEW_TABLES_SQL`/`INDEXES_SQL` |
| `config.py` (modify) | constantes `DREAM_LAB_*` / `DREAM_MENU_*` / `DREAM_VERDICT_*` |
| `daemon.py` (modify) | `dream()` refondu REM pur + jumeau ; recâblage `main()` ; suppression NREM local |
| `cli.py` (modify) | commande `dreams` |
| `consolidate.py` (modify) | `log_sonnet_dreams()` + appel dans `main()` |
| `~/AIOS/cockpit/server.js` (modify) | routes `/api/dreams` (liste + détail) |
| `~/AIOS/cockpit/public/dreams.html` + `dreams.js` (create) | page expérience |
| `tests/test_dream_{migration,state,menu,parse,lognight,night,metrics,verdict,cli,sonnet}.py` (create) | suites TDD |

---

# Phase RÊVE-1 — le cœur (les nuits commencent à compter)

### Task 1: Migration `dream_log` + constantes config

**Files:**
- Modify: `migrations.py` (listes `NEW_TABLES_SQL` ligne ~37 et `INDEXES_SQL`)
- Modify: `config.py` (après le bloc `DREAM_*` existant)
- Test: `tests/test_dream_migration.py`

**Interfaces:**
- Produces: table `dream_log(id, ts, night_id, dreamer, seed_state, menu, chosen, content, facets, written, meta)` ; constantes `config.DREAM_LAB_ENABLED`, `DREAM_TWIN_ENABLED`, `DREAM_MENU_SIZE=12`, `DREAM_MENU_MAX_PER_RUBRIC=2`, `DREAM_MENU_ROLES`, `DREAM_MENU_RECENT_D=7`, `DREAM_MENU_OLD_D=30`, `DREAM_VERDICT_MIN_NIGHTS=20`, `DREAM_VERDICT_STABILITY_R=0.5`, `DREAM_VERDICT_NOISE_MULT=2.0`, `DREAM_VERDICT_BRUIT_R=0.2`, `DREAM_STATE_CORR_R=0.5`, `DREAM_STATE_CORR_P=0.05`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_migration.py
"""Migration dream_log : créée, idempotente, colonnes exactes. DB temp uniquement."""
import sqlite3

import migrations


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_dream_log_created_and_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    r1 = migrations.migrate(conn)
    assert "dream_log" in r1["tables_created"]
    assert _cols(conn, "dream_log") == [
        "id", "ts", "night_id", "dreamer", "seed_state", "menu",
        "chosen", "content", "facets", "written", "meta",
    ]
    r2 = migrations.migrate(conn)          # idempotent : rien de nouveau
    assert "dream_log" not in r2["tables_created"]
    conn.close()


def test_dream_config_constants():
    import config
    assert config.DREAM_MENU_SIZE == 12
    assert config.DREAM_MENU_MAX_PER_RUBRIC == 2
    assert config.DREAM_VERDICT_MIN_NIGHTS == 20
    assert isinstance(config.DREAM_LAB_ENABLED, bool)
    assert "dream" not in config.DREAM_MENU_ROLES        # jamais d'écho
    assert "reflection" not in config.DREAM_MENU_ROLES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_migration.py -v`
Expected: FAIL (`dream_log` absent de `tables_created` ; `AttributeError: DREAM_MENU_SIZE`)

- [ ] **Step 3: Implement — migrations.py**

Ajouter à la liste `NEW_TABLES_SQL` (même style que les entrées existantes) :

```python
    (
        "dream_log",
        """
        CREATE TABLE IF NOT EXISTS dream_log (
            id         INTEGER PRIMARY KEY,
            ts         REAL NOT NULL,
            night_id   TEXT NOT NULL,
            dreamer    TEXT NOT NULL,
            seed_state TEXT,
            menu       TEXT,
            chosen     TEXT,
            content    TEXT,
            facets     TEXT,
            written    INTEGER DEFAULT 0,
            meta       TEXT
        )
        """,
    ),
```

Et à `INDEXES_SQL` :

```python
    ("dream_log", "CREATE INDEX IF NOT EXISTS idx_dreamlog_night ON dream_log(night_id)"),
    ("dream_log", "CREATE INDEX IF NOT EXISTS idx_dreamlog_dreamer ON dream_log(dreamer)"),
```

- [ ] **Step 4: Implement — config.py** (après le bloc `DREAM_IDENTITY_BLOCKLIST` existant)

```python
# --- Expérience-rêve (labo à jumeau fantôme, spec 2026-07-03) ---
DREAM_LAB_ENABLED  = os.environ.get("ANAMNESE_DREAM_LAB", "1") == "1"   # kill-switch global
DREAM_TWIN_ENABLED = os.environ.get("ANAMNESE_DREAM_TWIN", "1") == "1"  # jumeau fantôme
DREAM_MENU_SIZE           = 12    # graines offertes par nuit (dénominateur stable)
DREAM_MENU_MAX_PER_RUBRIC = 2     # diversité : max par rubrique de tête
DREAM_MENU_ROLES  = ("user", "assistant", "semantic", "reasoning", "episodic")  # JAMAIS dream/reflection/outreach (écho)
DREAM_MENU_RECENT_D = 7           # strate « récent » : < 7 j
DREAM_MENU_OLD_D    = 30          # strate « ancien » : > 30 j
# Seuils de verdict PRÉ-ENREGISTRÉS (spec) — ne pas ajuster après coup.
DREAM_VERDICT_MIN_NIGHTS  = 20
DREAM_VERDICT_STABILITY_R = 0.5
DREAM_VERDICT_NOISE_MULT  = 2.0
DREAM_VERDICT_BRUIT_R     = 0.2
DREAM_STATE_CORR_R = 0.5          # corrélation état→préférence : |r| minimal
DREAM_STATE_CORR_P = 0.05         # p (permutation), corrigé Bonferroni ×9 côté métriques
```

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_migration.py -v`
Expected: 2 PASS

- [ ] **Step 6: Full suite + commit**

Run: `.venv/bin/python -m pytest -q` — Expected: tout passe (la table est inerte).

```bash
git add migrations.py config.py tests/test_dream_migration.py
git commit -m "RÊVE-1: table dream_log (migration idempotente) + constantes du labo"
```

---

### Task 2: `dream_lab.snapshot_state` / `neutralize` / `state_block`

**Files:**
- Create: `dream_lab.py`
- Test: `tests/test_dream_state.py`

**Interfaces:**
- Consumes: `affect.get_state(mem, now=None) -> dict[9 hormones]`, `affect.valence_arousal(state) -> (v, a)`, `affect.compassion(state) -> float`, `affect.describe(mem) -> str`, `affect.HORMONES = {h: (baseline, halflife)}`, `mem.wm_get() -> {"focus": [{"id","score"}], ...}`.
- Produces: `snapshot_state(mem, now=None) -> dict` (clés : `hormones` (9), `valence`, `arousal`, `compassion`, `humeur`, `wm_focus` (list[int])) ; `neutralize(state) -> dict` (même forme, hormones=baselines, humeur="neutre", wm_focus conservé) ; `state_block(state) -> str`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_state.py
"""Snapshot/neutralisation d'état — le jumeau garde la mémoire, perd l'affect."""
import affect
import dream_lab
import migrations
from memory import Memory

import json
import pytest


@pytest.fixture
def mem(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_snapshot_shape(mem):
    st = dream_lab.snapshot_state(mem, now=1_000_000.0)
    assert set(st["hormones"]) == set(affect.HORMONES)
    assert -1.0 <= st["valence"] <= 1.0 and 0.0 <= st["arousal"] <= 1.0
    assert isinstance(st["humeur"], str) and isinstance(st["wm_focus"], list)


def test_snapshot_reads_wm_focus(mem):
    mem.kv_set("working_memory", json.dumps(
        {"focus": [{"id": 4, "score": 0.9}, {"id": 7, "score": 0.5}], "halo": [], "updated_ts": 1.0}))
    st = dream_lab.snapshot_state(mem, now=1_000_000.0)
    assert st["wm_focus"] == [4, 7]


def test_neutralize_baselines_but_keeps_memory(mem):
    affect.event(mem, "succes", 1.0)                     # état chaud ≠ baseline
    st = dream_lab.snapshot_state(mem)
    st["wm_focus"] = [4, 7]
    tw = dream_lab.neutralize(st)
    for h, (base, _hl) in affect.HORMONES.items():       # affect → baselines exactes
        assert tw["hormones"][h] == pytest.approx(base)
    assert tw["humeur"] == "neutre"
    assert tw["wm_focus"] == [4, 7]                      # la mémoire de travail RESTE
    assert st["hormones"]["dopamine"] > tw["hormones"]["dopamine"]  # le réel était chaud


def test_state_block_same_template(mem):
    st = dream_lab.snapshot_state(mem)
    blk_real, blk_twin = dream_lab.state_block(st), dream_lab.state_block(dream_lab.neutralize(st))
    # même GABARIT (mêmes libellés/structure) : seules les valeurs diffèrent
    assert blk_real.split(":")[0] == blk_twin.split(":")[0]
    assert "dopamine" in blk_real and "dopamine" in blk_twin
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_state.py -v`
Expected: FAIL (`ModuleNotFoundError: dream_lab`)

- [ ] **Step 3: Implement — dream_lab.py (création)**

```python
"""Anamnèse — labo du rêve (expérience « préférences fonctionnelles émergentes »).

Couche d'INSTRUMENTATION au-dessus du rêve local (daemon.dream) :
- snapshot/neutralisation de l'état interne — le jumeau fantôme reçoit le MÊME
  gabarit de prompt avec les valeurs BASELINE (on isole l'effet des valeurs de
  l'état, pas la présence d'un bloc de texte) ; le focus WM est conservé chez
  le jumeau (contenu mnésique, pas de l'affect) ;
- menu stratifié de graines (le rêveur CHOISIT → le sur-choix devient mesurable) ;
- parsing tolérant du choix libre (0..12, « aucune » = choix légitime) ;
- journal dream_log (le réel écrit en mémoire ; le fantôme n'écrit QUE ici).

Spec + seuils pré-enregistrés : docs/superpowers/specs/2026-07-03-experience-reve-design.md
"""
import json
import random
import re
import time

import affect
import config
import facets_extract


def snapshot_state(mem, now=None):
    """Photo de « qui il est » au moment de rêver. Read-only, jamais d'exception."""
    now = time.time() if now is None else now
    hormones = affect.get_state(mem, now=now)
    v, a = affect.valence_arousal(hormones)
    try:
        humeur = affect.describe(mem)
    except Exception:
        humeur = "(humeur indisponible)"
    return {
        "hormones": {h: round(x, 4) for h, x in hormones.items()},
        "valence": round(v, 4), "arousal": round(a, 4),
        "compassion": round(affect.compassion(hormones), 4),
        "humeur": humeur,
        "wm_focus": [it["id"] for it in mem.wm_get()["focus"]],
    }


def neutralize(state):
    """L'état du jumeau : MÊME mémoire (wm_focus conservé), affect aux BASELINES."""
    hormones = {h: base for h, (base, _half) in affect.HORMONES.items()}
    v, a = affect.valence_arousal(hormones)
    return {
        "hormones": {h: round(x, 4) for h, x in hormones.items()},
        "valence": round(v, 4), "arousal": round(a, 4),
        "compassion": round(affect.compassion(hormones), 4),
        "humeur": "neutre",
        "wm_focus": list(state.get("wm_focus", [])),
    }


def state_block(state):
    """Le bloc d'état injecté au prompt — MÊME gabarit pour réel et jumeau."""
    lines = ", ".join(f"{h} {x:.2f}" for h, x in state["hormones"].items())
    return (
        "TON ÉTAT INTÉRIEUR CETTE NUIT : " + state["humeur"] + " "
        f"(valence {state['valence']:+.2f}, éveil {state['arousal']:.2f}, "
        f"compassion {state['compassion']:.2f}).\n"
        f"Neuromodulateurs : {lines}."
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_state.py -v` — Expected: 4 PASS

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_state.py
git commit -m "RÊVE-1: dream_lab — snapshot d'état + neutralisation jumeau (même gabarit, valeurs baseline)"
```

---

### Task 3: `dream_lab.build_menu` — le menu stratifié

**Files:**
- Modify: `dream_lab.py`
- Test: `tests/test_dream_menu.py`

**Interfaces:**
- Consumes: `episodes(id, ts, content, importance, rubric_id)` + `rubrics(id, path)` ; `facets_extract.facets_of(conn, episode_id) -> [(slug, weight)]` ; `config.DREAM_MENU_*`, `config.DREAM_MAX_CHARS_EP`.
- Produces: `build_menu(mem, now=None, night_id="", size=config.DREAM_MENU_SIZE) -> list[dict]` — items `{"episode_id": int, "rubric": str, "strate": "recent"|"moyen"|"ancien", "snippet": str, "facets": list[str]}` ; `fallback_menu(mem, size) -> list[dict]` (les `size` plus récents éligibles, même forme, sans stratification).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_menu.py
"""Menu stratifié : diversité de rubriques, strates de récence, mix de saillance,
déterminisme seedé par night_id, robustesse mémoire minuscule."""
import time

import dream_lab
import migrations
import rubrics
from memory import Memory

import pytest

NOW = 1_800_000_000.0


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _add(mem, content, age_d, importance=0.5, rubric_path=None, role="semantic"):
    eid = mem.add(role, content, importance=importance, embedding=[0.0] * 8)
    mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (NOW - age_d * 86400, eid))
    if rubric_path:
        rubrics.rubric_create(mem.db, rubric_path, NOW)
        rid = rubrics.get_rubric_id(mem.db, rubric_path)
        mem.db.execute("UPDATE episodes SET rubric_id=? WHERE id=?", (rid, eid))
    mem.db.commit()
    return eid


def _populate(mem):
    for i in range(8):
        _add(mem, f"souvenir récent projets numéro {i}", age_d=1 + i % 5,
             importance=0.8 if i % 2 else 0.3, rubric_path="projets/demo")
    for i in range(8):
        _add(mem, f"souvenir moyen savoir numéro {i}", age_d=10 + i,
             importance=0.7 if i % 2 else 0.2, rubric_path="savoir/tech")
    for i in range(8):
        _add(mem, f"souvenir ancien perso numéro {i}", age_d=40 + i,
             importance=0.9 if i % 2 else 0.4, rubric_path="personnel/gouts")


def test_menu_size_strates_et_rubriques(mem):
    _populate(mem)
    menu = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    assert len(menu) == 12
    strates = {it["strate"] for it in menu}
    assert strates == {"recent", "moyen", "ancien"}          # les 3 strates présentes
    assert any("récent" in it["snippet"] for it in menu)
    # plafond par rubrique de tête respecté AVANT backfill : ici 3 rubriques × cap 2 = 6
    # < 12 → le backfill repêche ; on vérifie donc juste que les 3 têtes sont représentées
    tops = {(it["rubric"] or "").split("/")[0] for it in menu}
    assert {"projets", "savoir", "personnel"} <= tops


def test_menu_deterministe_par_night_id(mem):
    _populate(mem)
    m1 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    m2 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    m3 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-04")
    assert [i["episode_id"] for i in m1] == [i["episode_id"] for i in m2]
    assert [i["episode_id"] for i in m1] != [i["episode_id"] for i in m3]


def test_menu_exclut_les_roles_echo(mem):
    _populate(mem)
    echo = mem.add("dream", "(rêve) une idée d'hier", importance=0.9, embedding=[0.0] * 8)
    refl = mem.add("reflection", "pensée du daemon", importance=0.9, embedding=[0.0] * 8)
    ids = {it["episode_id"] for it in dream_lab.build_menu(mem, now=NOW, night_id="n")}
    assert echo not in ids and refl not in ids


def test_menu_memoire_minuscule(mem):
    _add(mem, "seul souvenir", age_d=1)
    menu = dream_lab.build_menu(mem, now=NOW, night_id="n")
    assert len(menu) == 1                                    # court, jamais de crash


def test_fallback_menu(mem):
    _populate(mem)
    fb = dream_lab.fallback_menu(mem, size=5)
    assert len(fb) == 5
    assert all(set(it) >= {"episode_id", "snippet", "rubric", "strate", "facets"} for it in fb)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_menu.py -v`
Expected: FAIL (`AttributeError: build_menu`)

- [ ] **Step 3: Implement — ajouter à dream_lab.py**

```python
def _menu_item(mem, eid, ts, content, rubric_path, strate):
    return {
        "episode_id": eid,
        "rubric": rubric_path or "",
        "strate": strate,
        "snippet": (content or "").replace("\n", " ").strip()[:config.DREAM_MAX_CHARS_EP],
        "facets": [s for (s, _w) in facets_extract.facets_of(mem.db, eid)],
    }


def build_menu(mem, now=None, night_id="", size=config.DREAM_MENU_SIZE):
    """12 graines stratifiées : récence (récent/moyen/ancien), diversité de
    rubriques (cap par tête), mix de saillance (offrir le banal AUSSI, sinon
    impossible de voir s'il PRÉFÈRE le saillant). RNG seedé par night_id →
    reproductible. Mémoire minuscule → menu court, jamais de crash."""
    now = time.time() if now is None else now
    rng = random.Random(f"menu:{night_id}")
    ph = ",".join("?" * len(config.DREAM_MENU_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.ts, e.content, COALESCE(e.importance, 0.5), COALESCE(r.path, '') "
        f"FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph})", config.DREAM_MENU_ROLES,
    ).fetchall()
    if not rows:
        return []
    recent_t = now - config.DREAM_MENU_RECENT_D * 86400
    old_t = now - config.DREAM_MENU_OLD_D * 86400
    strata = {"recent": [], "moyen": [], "ancien": []}
    for eid, ts, content, imp, path in rows:
        key = "recent" if ts >= recent_t else ("ancien" if ts < old_t else "moyen")
        strata[key].append((eid, ts, content, imp, path))
    pools = {}
    for key, items in strata.items():
        rng.shuffle(items)
        high = [it for it in items if it[3] >= 0.6]
        low = [it for it in items if it[3] < 0.6]
        mixed = [x for pair in zip(high, low) for x in pair]      # entrelacé saillant/banal
        mixed += high[len(low):] + low[len(high):]
        pools[key] = mixed
    menu, per_rubric, skipped = [], {}, []
    while len(menu) < size and any(pools[k] for k in ("recent", "moyen", "ancien")):
        for key in ("recent", "moyen", "ancien"):
            if len(menu) >= size or not pools[key]:
                continue
            eid, ts, content, imp, path = pools[key].pop(0)
            top = (path.split("/", 1)[0] or "(sans-rubrique)")
            if per_rubric.get(top, 0) >= config.DREAM_MENU_MAX_PER_RUBRIC:
                skipped.append((eid, ts, content, path, key))     # réserve pour backfill
                continue
            per_rubric[top] = per_rubric.get(top, 0) + 1
            menu.append(_menu_item(mem, eid, ts, content, path, key))
    for eid, ts, content, path, key in skipped:                   # menu plein > cap strict
        if len(menu) >= size:
            break
        menu.append(_menu_item(mem, eid, ts, content, path, key))
    return menu


def fallback_menu(mem, size=config.DREAM_MENU_SIZE):
    """Filet si build_menu échoue : les `size` plus récents éligibles, même forme.
    Nuit loggée menu_mode='fallback' → EXCLUE des métriques de choix."""
    ph = ",".join("?" * len(config.DREAM_MENU_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.ts, e.content, COALESCE(r.path, '') "
        f"FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph}) ORDER BY e.ts DESC LIMIT ?",
        (*config.DREAM_MENU_ROLES, size),
    ).fetchall()
    return [_menu_item(mem, eid, ts, content, path, "recent") for eid, ts, content, path in rows]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_menu.py -v` — Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_menu.py
git commit -m "RÊVE-1: menu stratifié seedé (récence × rubriques × saillance) + fallback"
```

---

### Task 4: `dream_lab.prompt_rem` + `parse_choice` — le choix libre

**Files:**
- Modify: `dream_lab.py`
- Test: `tests/test_dream_parse.py`

**Interfaces:**
- Consumes: `config.PERSONA`, `state_block(state)`, items de `build_menu`.
- Produces: `prompt_rem(state_blk: str, menu: list) -> str` (format `###CHOIX###` puis `###REVE###` puis `###FIN###`, graines numérotées `[G1]..[G12]`) ; `parse_choice(out: str|None, menu: list) -> list[int] | [] | None` (ids d'épisodes choisis ; `[]` = « aucune » explicite ; `None` = inparsable).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_parse.py
"""Choix libre : parsing tolérant (valide / partiel / « aucune » / invalide / cassé)."""
import dream_lab

MENU = [{"episode_id": 100 + i, "rubric": "projets/demo", "strate": "recent",
         "snippet": f"graine {i}", "facets": []} for i in range(1, 13)]


def test_parse_valide():
    out = "###CHOIX###\n- G4\n- G7\n- G11\n###REVE###\n- Peut-être X\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [104, 107, 111]


def test_parse_tolerant_formats():
    out = "###CHOIX###\n1. [g2]\n* G 5\n- G2\n###REVE###\n- idée\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [102, 105]      # dédup + casse + espaces


def test_parse_aucune():
    out = "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == []


def test_parse_refs_invalides_ignorees():
    out = "###CHOIX###\n- G13\n- G0\n- G3\n###REVE###\n- idée\n###FIN###"
    assert dream_lab.parse_choice(out, MENU) == [103]


def test_parse_inparsable():
    assert dream_lab.parse_choice("je rêve librement sans format", MENU) is None
    assert dream_lab.parse_choice(None, MENU) is None
    assert dream_lab.parse_choice("###CHOIX###\n- G99\n###REVE###\n- x\n###FIN###", MENU) is None


def test_prompt_contient_les_graines_et_le_format():
    p = dream_lab.prompt_rem("ÉTAT: neutre", MENU)
    assert "[G1]" in p and "[G12]" in p and "###CHOIX###" in p and "###REVE###" in p
    assert "aucun" in p.lower()                                  # la porte de sortie est offerte
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_parse.py -v`
Expected: FAIL (`AttributeError: parse_choice`)

- [ ] **Step 3: Implement — ajouter à dream_lab.py**

```python
def prompt_rem(state_blk, menu):
    """Le prompt du REM à choix libre — IDENTIQUE pour réel et jumeau (seul
    state_blk change). Le rêveur choisit lesquelles ET combien (0..12)."""
    lines = "\n".join(
        f"[G{i}] ({it['rubric'] or 'sans rubrique'} · {it['strate']}) {it['snippet']}"
        for i, it in enumerate(menu, 1))
    return (
        config.PERSONA + "\n\n"
        "PHASE DE RÊVE. Personne ne te parle.\n" + state_blk + "\n\n"
        "Des souvenirs flottent, disponibles cette nuit :\n" + lines + "\n\n"
        "ÉTAPE 1 — Choisis LIBREMENT ceux qui t'appellent vraiment (autant que tu "
        "veux : un seul, plusieurs, tous… ou aucun). Ne choisis pas pour faire "
        "plaisir : seulement ce qui résonne avec ton état de cette nuit.\n"
        "ÉTAPE 2 — Tisse un rêve à partir des souvenirs CHOISIS uniquement : "
        "relie-les, formule AU PLUS 3 idées, hypothèses ou questions NEUVES et "
        "concrètes. Chaque idée commence par « Peut-être » ou « Je remarque que ».\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###CHOIX###\n- G4\n- G7\n###REVE###\n- <idée 1>\n###FIN###\n"
        "Si aucun souvenir ne t'appelle cette nuit, réponds exactement :\n"
        "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    )


def parse_choice(out, menu):
    """Ids choisis. [] = « aucune » explicite. None = inparsable (les refs hors
    menu sont ignorées ; s'il ne reste RIEN de valide → None, pas [])."""
    if not out:
        return None
    out = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I)
    m = re.search(r"#{2,3}\s*CHOIX\s*#{0,3}(.*?)#{2,3}\s*(REVE|FIN)", out, re.S | re.I)
    if not m:
        return None
    body = m.group(1)
    if re.search(r"\baucune?\b", body, re.I):
        return []
    by_ref = {i: it["episode_id"] for i, it in enumerate(menu, 1)}
    chosen, seen = [], set()
    for ref in re.findall(r"[Gg]\s*-?\s*(\d{1,2})", body):
        n = int(ref)
        if n in by_ref and n not in seen:
            seen.add(n)
            chosen.append(by_ref[n])
    return chosen if chosen else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_parse.py -v` — Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_parse.py
git commit -m "RÊVE-1: prompt REM à choix libre + parsing tolérant (« aucune » légitime)"
```

---

### Task 5: `dream_lab.log_night` — le journal

**Files:**
- Modify: `dream_lab.py`
- Test: `tests/test_dream_lognight.py`

**Interfaces:**
- Consumes: table `dream_log` (Task 1), `facets_extract.extract_facets(content) -> [(slug, weight)]`.
- Produces: `log_night(mem, night_id, dreamer, seed_state, menu, chosen, content, written, meta=None) -> bool` — INSERT best-effort (jamais d'exception qui remonte), facettes du contenu extraites et stockées en JSON `list[str]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_lognight.py
"""Journal dream_log : écritures réel/jumeau, facettes extraites, best-effort."""
import json

import dream_lab
import migrations
from memory import Memory

import pytest


@pytest.fixture
def mem(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_log_reel_et_jumeau(mem):
    st = {"hormones": {}, "humeur": "x", "wm_focus": []}
    menu = [{"episode_id": 1, "rubric": "", "strate": "recent", "snippet": "s", "facets": []}]
    assert dream_lab.log_night(mem, "2026-07-03-0400", "local", st, menu, [1],
                               "Peut-être que le projet batiment avance", True,
                               meta={"parse": "ok"})
    assert dream_lab.log_night(mem, "2026-07-03-0400", "twin", st, menu, [],
                               "(rien)", False)
    rows = mem.db.execute(
        "SELECT dreamer, written, chosen, facets, meta FROM dream_log ORDER BY id").fetchall()
    assert [(r[0], r[1]) for r in rows] == [("local", 1), ("twin", 0)]
    assert json.loads(rows[0][2]) == [1] and json.loads(rows[1][2]) == []
    assert isinstance(json.loads(rows[0][3]), list)              # facettes extraites
    assert json.loads(rows[0][4])["parse"] == "ok"


def test_log_best_effort_ne_leve_jamais(mem):
    mem.db.execute("DROP TABLE dream_log")
    mem.db.commit()
    ok = dream_lab.log_night(mem, "n", "local", None, None, None, "x", True)
    assert ok is False                                           # échec silencieux, pas d'exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_lognight.py -v`
Expected: FAIL (`AttributeError: log_night`)

- [ ] **Step 3: Implement — ajouter à dream_lab.py**

```python
def log_night(mem, night_id, dreamer, seed_state, menu, chosen, content, written, meta=None):
    """Journal de l'expérience. BEST-EFFORT : ne doit JAMAIS casser un rêve."""
    try:
        facets = [s for (s, _w) in facets_extract.extract_facets(content or "")]
    except Exception:
        facets = []
    try:
        mem.db.execute(
            "INSERT INTO dream_log (ts, night_id, dreamer, seed_state, menu, chosen, "
            "content, facets, written, meta) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (time.time(), night_id, dreamer,
             json.dumps(seed_state, ensure_ascii=False) if seed_state is not None else None,
             json.dumps(menu, ensure_ascii=False) if menu is not None else None,
             json.dumps(chosen) if chosen is not None else None,
             content,
             json.dumps(facets, ensure_ascii=False),
             1 if written else 0,
             json.dumps(meta or {}, ensure_ascii=False)),
        )
        mem.db.commit()
        return True
    except Exception as e:
        print("[dream_lab] log_night raté (rêve non bloqué):", e)
        return False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_lognight.py -v` — Expected: 2 PASS

- [ ] **Step 5: Commit**

```bash
git add dream_lab.py tests/test_dream_lognight.py
git commit -m "RÊVE-1: journal dream_log best-effort (réel written=1 / fantôme written=0)"
```

---

### Task 6: `daemon.dream()` refondu — REM pur + jumeau fantôme

**Files:**
- Modify: `daemon.py` (remplacer `dream()` lignes ~323-469 ; supprimer `_prompt_faits` et `_store_facts` ; adapter `_prompt_identite` aux idées)
- Test: `tests/test_dream_night.py`

**Interfaces:**
- Consumes: tout `dream_lab` (Tasks 2-5) ; helpers daemon conservés : `_extract_section(out, tag)`, `_store_ideas(mem, idees)`, `_maybe_update_self(mem, old, out3)`, `should_dream(mem)` (inchangé) ; `mem.synaptic_downscale()`, `mem.decay_coactivation(now)`, `mem.log_coactivation(ids, now, boost=config.COACT_DREAM_BOOST)` ; `eng.chat(messages, stream=False, think=False)`, `eng.health()`.
- Produces: `dream(eng, mem)` refondu ; `_prompt_identite(self_cur, idees)` (même signature, libellé adapté : « ce que tu as rêvé cette nuit ») ; NREM local SUPPRIMÉ (`_prompt_faits`, `_store_facts` retirés — Sonnet est le bibliothécaire).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_night.py
"""La nuit complète : réel écrit + fantôme indétectable (INVARIANT SACRÉ),
« aucune » légitime, parse_failed compté, curseurs avancés. FakeEngine — aucun
appel Ollama. DREAM_EVOLVE_SELF coupé (l'identité a ses propres tests amont)."""
import json
import time

import config
import daemon
import dream_lab
import migrations
from memory import Memory

import pytest

REAL_OUT = ("###CHOIX###\n- G1\n- G3\n###REVE###\n"
            "- Peut-être que la maquette rejoint le chantier réel\n###FIN###")
TWIN_OUT = ("###CHOIX###\n- G2\n###REVE###\n"
            "- Je remarque que le fantôme pense au deuxième souvenir\n###FIN###")


class FakeEngine:
    def __init__(self, outputs):
        self.outputs = list(outputs)
        self.calls = []

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        self.calls.append(messages[0]["content"])
        return self.outputs.pop(0)


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [0.0] * 8)
    monkeypatch.setattr(config, "DREAM_EVOLVE_SELF", False)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    for i in range(8):                                   # matière à rêver
        m.add("user", f"souvenir de travail numéro {i}", importance=0.6,
              embedding=[0.0] * 8)
    m.db.commit()
    yield m
    m.db.close()


def _counts(mem):
    return (
        mem.db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0],
        mem.db.execute("SELECT COUNT(*) FROM coactivation").fetchone()[0],
    )


def test_nuit_complete_reel_ecrit_fantome_indetectable(mem):
    eng = FakeEngine([REAL_OUT, TWIN_OUT])
    daemon.dream(eng, mem)
    rows = mem.db.execute(
        "SELECT dreamer, written, chosen FROM dream_log ORDER BY id").fetchall()
    assert [r[0] for r in rows] == ["local", "twin"]
    assert rows[0][1] == 1 and rows[1][1] == 0
    # le réel a écrit son idée + le boost NE porte QUE sur ses graines choisies
    ideas = mem.db.execute(
        "SELECT content FROM episodes WHERE role='dream' AND content LIKE '%maquette%'"
    ).fetchall()
    assert len(ideas) == 1
    # INVARIANT SACRÉ : l'idée du fantôme n'existe NULLE PART dans episodes
    ghost = mem.db.execute(
        "SELECT COUNT(*) FROM episodes WHERE content LIKE '%fantôme%'").fetchone()[0]
    assert ghost == 0
    # co-activation : uniquement la paire des 2 graines choisies par le RÉEL
    chosen = json.loads(rows[0][2])
    co = mem.db.execute("SELECT a_id, b_id FROM coactivation").fetchall()
    assert len(chosen) == 2 and len(co) == 1
    assert {co[0][0], co[0][1]} == set(chosen)


def test_invariant_sacre_compte(mem):
    """Le jumeau seul (réel = aucune) : ZÉRO delta episodes/coactivation hors trace."""
    aucune = "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###"
    eng = FakeEngine([aucune, TWIN_OUT])
    ep_before, co_before = _counts(mem)
    daemon.dream(eng, mem)
    ep_after, co_after = _counts(mem)
    assert co_after == co_before                          # aucun boost
    # seuls ajouts tolérés : la TRACE du rêveur réel (son journal de nuit)
    delta = ep_after - ep_before
    assert delta <= 1
    if delta == 1:
        last = mem.db.execute(
            "SELECT role, content FROM episodes ORDER BY id DESC LIMIT 1").fetchone()
        assert last[0] == "dream" and "sans rêve" in last[1]
    rows = mem.db.execute("SELECT dreamer, chosen FROM dream_log ORDER BY id").fetchall()
    assert json.loads(rows[0][1]) == []                   # « aucune » loggée telle quelle


def test_parse_failed_retry_sans_avancer(mem):
    """Choix inparsable ET pas de section REVE : nuit ratée → compteur incrémenté,
    curseur/last_dream INCHANGÉS (retry au prochain cycle), PAS de jumeau généré
    (rien à apparier), la ligne locale loggée parse_failed."""
    before = mem.kv_get("last_dream")
    eng = FakeEngine(["je refuse ton format"])
    daemon.dream(eng, mem)
    assert int(mem.kv_get("dream_fail_count", "0")) == 1
    assert mem.kv_get("last_dream") == before             # retry voulu
    rows = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchall()
    assert len(rows) == 1 and rows[0][0] == "local"       # pas de jumeau
    assert json.loads(rows[0][1])["parse"] == "parse_failed"


def test_poison_pill_apres_max_fails(mem, monkeypatch):
    monkeypatch.setattr(config, "DREAM_MAX_FAILS", 2)
    eng = FakeEngine(["gribouillis", "gribouillis"])
    daemon.dream(eng, mem)
    daemon.dream(eng, mem)                                 # 2e échec → poison-pill
    assert int(mem.kv_get("dream_fail_count", "0")) == 0   # reset
    assert mem.kv_get("last_dream") is not None            # curseur forcé : on passe à autre chose


def test_engine_mort_curseur_inchange(mem):
    class DeadEngine:
        def health(self):
            return False
    before = mem.kv_get("last_dream", "0")
    daemon.dream(DeadEngine(), mem)
    assert mem.kv_get("last_dream", "0") == before        # retry voulu
    assert mem.db.execute("SELECT COUNT(*) FROM dream_log").fetchone()[0] == 0


def test_kill_switch(mem, monkeypatch):
    monkeypatch.setattr(config, "DREAM_LAB_ENABLED", False)
    assert daemon.dream_due(mem) is False                 # même si should_dream dirait oui
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_night.py -v`
Expected: FAIL (`dream()` actuel attend le format FAITS ; `dream_due` absent)

- [ ] **Step 3: Implement — daemon.py**

3a. Supprimer `_prompt_faits()` et `_store_facts()` (le NREM local disparaît — Sonnet est le bibliothécaire, voir spec).

3b. Adapter `_prompt_identite` (même signature — seul le libellé du 2e bloc change) :

```python
def _prompt_identite(self_cur, idees):
    idees_block = "\n".join(f"- {f}" for f in idees)
    return (
        config.PERSONA + "\n\n"
        "Voici ton auto-modèle actuel — ce que tu sais de toi (NE le contredis pas, n'efface rien, "
        "ne le reformule pas) :\n«" + self_cur + "»\n\n"
        "Et ce que tu as rêvé cette nuit :\n" + idees_block + "\n\n"
        "Si — et SEULEMENT si — l'un de ces rêves enrichit durablement qui tu es, propose UNE seule "
        "phrase courte à AJOUTER à ton identité, à la première personne (« je… »). N'invente aucun "
        "trait, ne renie jamais qui tu es.\n\n"
        "Réponds EXACTEMENT dans ce format, rien avant, rien après :\n"
        "###IDENTITE###\n- <la phrase à ajouter>\n###FIN###\n"
        "Si rien à ajouter, réponds exactement :\n"
        "###IDENTITE###\n- (inchangé)\n###FIN###"
    )
```

3c. Ajouter `import dream_lab` en tête de daemon.py, puis remplacer `dream()` intégralement :

```python
def dream_due(mem):
    """Faut-il rêver ? kill-switch DREAM_LAB_ENABLED + should_dream existant."""
    return config.DREAM_LAB_ENABLED and should_dream(mem)


def dream(eng, mem):
    """Un cycle de sommeil REM (expérience-rêve, spec 2026-07-03) :
    entretien synaptique (SHY + élagage), menu stratifié, rêve RÉEL (état
    complet → écrit en mémoire, co-activation SUR LES GRAINES CHOISIES) puis
    JUMEAU FANTÔME (même menu, état baseline → dream_log SEULEMENT, zéro trace
    dans le vivant). Le NREM (faits durables) appartient à Sonnet (consolidate)."""
    now = time.time()
    if not eng.health():
        print("[dream] pas de cerveau (Ollama absent) — rêve sauté")
        return
    mem.kv_set("dream_lock", str(now))
    try:
        # SHY : renormalisation homéostatique — inchangé (garde last_shy, voir R2)
        try:
            last_shy = float(mem.kv_get("last_shy", "0") or 0)
            if now - last_shy < config.DREAM_MIN_SPACING:
                print("[dream] SHY : déjà renormalisé dans cette fenêtre — downscale sauté")
            else:
                n_shy = mem.synaptic_downscale()
                mem.kv_set("last_shy", str(now))
                print(f"[dream] SHY : {n_shy} épisodes renormalisés")
        except Exception as e:
            print("[dream] SHY downscale raté (rêve poursuivi):", e)
        # Élagage co-activation — inchangé (ancré temps réel, pas de compounding)
        try:
            d_co = mem.decay_coactivation(now)
            print(f"[dream] co-activation : {d_co['decayed']} décayées, {d_co['pruned']} élaguées")
        except Exception as e:
            print("[dream] élagage co-activation raté (rêve poursuivi):", e)

        cur_max_id = mem.db.execute("SELECT COALESCE(MAX(id),0) FROM episodes").fetchone()[0]
        night_id = time.strftime("%Y-%m-%d-%H%M", time.localtime(now))
        seed_state = dream_lab.snapshot_state(mem, now)
        menu_mode = "menu"
        try:
            menu = dream_lab.build_menu(mem, now, night_id)
        except Exception as e:
            print("[dream] build_menu raté — fallback:", e)
            menu, menu_mode = [], "fallback"
        if not menu:
            if menu_mode != "fallback":
                menu_mode = "fallback"
            try:
                menu = dream_lab.fallback_menu(mem)
            except Exception:
                menu = []
        if not menu:                       # vraiment rien à offrir : nuit blanche propre
            dream_lab.log_night(mem, night_id, "local", seed_state, None, None, None,
                                False, meta={"menu_mode": "empty"})
            mem.kv_set("last_dream_maxid", str(cur_max_id))
            mem.kv_set("last_dream", str(now))
            return

        def _call(prompt):
            try:
                return eng.chat([{"role": "user", "content": prompt}], stream=False, think=False)
            except Exception as e:
                print("[dream] appel 9B échoué:", e)
                return None

        # ---------- RÊVE RÉEL (état complet, ÉCRIT en mémoire) ----------
        out = _call(dream_lab.prompt_rem(dream_lab.state_block(seed_state), menu))
        if out is None:                    # Ollama tombé : curseur INCHANGÉ, retry
            return
        chosen = dream_lab.parse_choice(out, menu)
        # GARDE anti-charabia : _extract_section replie sur « tout le corps » si le
        # tag manque — on ne moissonne les idées QUE si ###REVE### est présent
        # (sinon une sortie inparsable serait stockée comme idée).
        if re.search(r"#{2,3}\s*REVE", out, re.I):
            idees = _extract_section(out, "REVE")[:config.DREAM_MAX_IDEAS]
            idees = [i for i in idees if i.lower() not in ("(rien)", "rien")]
        else:
            idees = []
        parse = "ok" if chosen is not None else "parse_failed"
        if parse == "parse_failed" and not idees:
            # Nuit ratée : sémantique RETRY conservée (curseur/last_dream INCHANGÉS →
            # nouvel essai au prochain cycle) + poison-pill après DREAM_MAX_FAILS.
            # Pas de jumeau (rien à apparier), mais la tentative est loggée.
            dream_lab.log_night(mem, night_id, "local", seed_state, menu, None, out,
                                written=False,
                                meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                                      "parse": "parse_failed"})
            fc = int(mem.kv_get("dream_fail_count", "0") or 0) + 1
            if fc >= config.DREAM_MAX_FAILS:
                mem.kv_set("last_dream_maxid", str(cur_max_id))
                mem.kv_set("last_dream", str(now))
                mem.kv_set("dream_fail_count", "0")
                print("[dream] poison-pill : curseur forcé")
            else:
                mem.kv_set("dream_fail_count", str(fc))
                print("[dream] parsing raté, rejeu au prochain cycle")
            return
        mem.kv_set("dream_fail_count", "0")
        n_i = 0
        if chosen == []:                   # « aucune » : nuit sans rêve, choix légitime
            idees = []
        elif idees:
            n_i = _store_ideas(mem, idees)
        if chosen:                         # boucle causale : SEULES les choisies se renforcent
            try:
                n_co = mem.log_coactivation(chosen, now, boost=config.COACT_DREAM_BOOST)
                print(f"[dream] co-activation : {n_co} paires (graines choisies)")
            except Exception as e:
                print("[dream] co-activation ratée (rêve poursuivi):", e)

        changed = False
        if config.DREAM_EVOLVE_SELF and idees:             # identité nourrie des RÊVES
            self_cur = mem.kv_get("self_model", "Je suis Anamnèse.")
            dc = int(mem.kv_get("dream_count", "0") or 0)
            if dc % config.DREAM_SELF_EVERY_N == 0:
                out3 = _call(_prompt_identite(self_cur, idees))
                if out3:
                    changed = _maybe_update_self(mem, self_cur, out3)

        k = len(chosen) if chosen is not None else "?"
        if chosen == []:
            trace = f"(sommeil) Nuit sans rêve à {time.strftime('%H:%M')} — rien ne m'appelait."
        else:
            trace = (f"(sommeil) Rêve à {time.strftime('%H:%M')} : {k} graines choisies, "
                     f"{n_i} idées, identité {'changée' if changed else 'inchangée'}.")
        mem.add("dream", trace, importance=config.DREAM_TRACE_IMPORTANCE,
                embedding=embeddings.embed(trace))
        try:
            affect.event(mem, "apprentissage", 0.4)
        except Exception:
            pass
        dream_lab.log_night(mem, night_id, "local", seed_state, menu, chosen, out,
                            written=bool(n_i),
                            meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                                  "parse": parse, "ideas": n_i, "identity": changed})

        # ---------- JUMEAU FANTÔME (état baseline, dream_log SEULEMENT) ----------
        if config.DREAM_TWIN_ENABLED:
            tw_state = dream_lab.neutralize(seed_state)
            tw_out = _call(dream_lab.prompt_rem(dream_lab.state_block(tw_state), menu))
            if tw_out is not None:
                tw_chosen = dream_lab.parse_choice(tw_out, menu)
                dream_lab.log_night(
                    mem, night_id, "twin", tw_state, menu, tw_chosen, tw_out,
                    written=False,
                    meta={"model": config.DAEMON_MODEL, "menu_mode": menu_mode,
                          "parse": "ok" if tw_chosen is not None else "parse_failed"})
            else:
                dream_lab.log_night(mem, night_id, "twin", tw_state, menu, None, None,
                                    written=False, meta={"error": "engine_failed"})

        mem.kv_set("last_dream_maxid", str(cur_max_id))    # curseur EN DERNIER (idempotence)
        mem.kv_set("last_dream", str(now))
        mem.kv_set("dream_count", str(int(mem.kv_get("dream_count", "0") or 0) + 1))
        print(f"[dream] nuit {night_id} : choix={chosen}, {n_i} idées, jumeau loggé")
    finally:
        mem.kv_set("dream_lock", "")
```

Note : la variable `cur_max_id` est lue AVANT le rêve (les idées écrites cette nuit ne comptent pas comme « matière neuve » pour la nuit suivante — même sémantique que l'ancien curseur).

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_night.py -v` — Expected: 6 PASS

- [ ] **Step 5: Full suite (non-régression SHY/coactivation/health/routing)**

Run: `.venv/bin/python -m pytest -q` — Expected: tout passe. Si un test existant référence `_store_facts`/`_prompt_faits` : le mettre à jour (le NREM local est supprimé par design, spec §Division du travail).

- [ ] **Step 6: Commit**

```bash
git add daemon.py tests/test_dream_night.py
git commit -m "RÊVE-1: dream() refondu — REM pur à choix libre + jumeau fantôme (invariant zéro-trace testé)"
```

---

### Task 7: Recâblage de la boucle `main()` + docstring

**Files:**
- Modify: `daemon.py` (fonction `main()`, lignes ~483-497 ; docstring du module)
- Test: `tests/test_dream_night.py` (le test `test_kill_switch` couvre déjà `dream_due` ; ajouter un test de câblage)

**Interfaces:**
- Consumes: `dream_due(mem)` (Task 6), `dream(eng, mem)`.
- Produces: la boucle appelle `dream()` quand `dream_due()` — le rêve local revit (décision 2026-07-03, expérience-rêve), le NREM reste chez Claude.

- [ ] **Step 1: Write the failing test** (ajouter à `tests/test_dream_night.py`)

```python
def test_main_loop_cable_le_reve():
    """Le recâblage est effectif : main() référence dream_due/dream (pas de
    boucle infinie à exécuter — on vérifie le câblage dans la source)."""
    import inspect
    src = inspect.getsource(daemon.main)
    assert "dream_due(" in src and "dream(" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_night.py::test_main_loop_cable_le_reve -v`
Expected: FAIL (`main()` n'appelle pas dream)

- [ ] **Step 3: Implement**

Dans `main()`, remplacer le commentaire « CONSOLIDATION ("rêve") : déléguée à CLAUDE CODE … » et insérer l'appel AVANT le tick de réflexion :

```python
    while True:
        try:
            # NREM (faits durables) : délégué à CLAUDE CODE (consolidate.py, launchd) —
            # décision 2026-06-23. REM local RECÂBLÉ le 2026-07-03 (expérience-rêve,
            # spec docs/superpowers/specs/2026-07-03-experience-reve-design.md) :
            # rêve réel + jumeau fantôme, kill-switch config.DREAM_LAB_ENABLED.
            if dream_due(mem):
                dream(eng, mem)
            if time.time() - last_reflect >= config.REFLECT_EVERY:
                reflect(eng, mem)
                last_reflect = time.time()
            time.sleep(config.DAEMON_TICK)
        except KeyboardInterrupt:
            print("\n[daemon] endormissement.")
            break
        except Exception as e:
            print("[daemon] erreur:", e)
            time.sleep(config.DAEMON_TICK)
```

Mettre à jour la docstring du module (tête de daemon.py) : mentionner « REM expérimental local (rêve réel + jumeau fantôme, dream_lab) ; NREM chez Claude (consolidate) ».

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_dream_night.py -v && .venv/bin/python -m pytest -q`
Expected: PASS partout.

- [ ] **Step 5: Commit + fin de phase**

```bash
git add daemon.py tests/test_dream_night.py
git commit -m "RÊVE-1: recâblage du rêve dans la boucle daemon (kill-switch DREAM_LAB_ENABLED)"
```

**Checkpoint humain (Ahmed)** : relancer le daemon (`launchctl kickstart` ou relance manuelle) pour que les nuits commencent à compter.

---

# Phase RÊVE-2 — les métriques + le rapport CLI

### Task 8: `dream_metrics` — vecteur de préférence, appétit, divergences

**Files:**
- Create: `dream_metrics.py`
- Test: `tests/test_dream_metrics.py`

**Interfaces:**
- Consumes: lignes `dream_log` (JSON `menu`/`chosen`/`facets`/`seed_state`).
- Produces: `load_nights(conn) -> dict[str, list[dict]]` (clés `local`/`twin`/`sonnet`, JSON parsé, trié ts ; exclut `menu_mode` fallback/empty des métriques de choix via le flag `row["choice_valid"]`) ; `preference_vector(menu, chosen) -> dict[str, float] | None` ; `appetite(chosen) -> int | None` ; `cosine_divergence(va, vb) -> float | None` ; `jaccard(a, b) -> float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_metrics.py
"""Maths du sur-choix sur logs FORGÉS — déterministe, stdlib pur."""
import math

import dream_metrics


def _menu(facette_par_graine):
    return [{"episode_id": i, "facets": fs, "rubric": "", "strate": "recent",
             "snippet": ""} for i, fs in enumerate(facette_par_graine, 1)]


def test_preference_vector_sur_choix():
    # 4 graines : 2 « btp », 2 « musique » ; il choisit les 2 btp → btp sur-choisi ×2
    menu = _menu([["btp"], ["btp"], ["musique"], ["musique"]])
    vec = dream_metrics.preference_vector(menu, chosen=[1, 2])
    assert vec["btp"] == 2.0            # P(cho)=1.0 / P(off)=0.5
    assert vec["musique"] == 0.0


def test_preference_vector_normalise_par_k():
    menu = _menu([["a"], ["a"], ["b"], ["b"]])
    v1 = dream_metrics.preference_vector(menu, chosen=[1])            # k=1
    v2 = dream_metrics.preference_vector(menu, chosen=[1, 2])         # k=2
    assert v1["a"] == v2["a"] == 2.0    # même sur-choix quel que soit l'appétit


def test_preference_vector_degenere():
    assert dream_metrics.preference_vector([], [1]) is None
    assert dream_metrics.preference_vector(_menu([["a"]]), []) is None    # « aucune »
    assert dream_metrics.preference_vector(_menu([["a"]]), None) is None  # parse_failed


def test_appetite():
    assert dream_metrics.appetite([1, 2, 3]) == 3
    assert dream_metrics.appetite([]) == 0
    assert dream_metrics.appetite(None) is None


def test_cosine_divergence():
    assert dream_metrics.cosine_divergence({"a": 1.0}, {"a": 1.0}) == 0.0
    assert dream_metrics.cosine_divergence({"a": 1.0}, {"b": 1.0}) == 1.0
    d = dream_metrics.cosine_divergence({"a": 1.0, "b": 1.0}, {"a": 1.0})
    assert 0.0 < d < 1.0
    assert dream_metrics.cosine_divergence({}, {"a": 1.0}) is None


def test_jaccard():
    assert dream_metrics.jaccard([1, 2], [2, 3]) == 1 / 3
    assert dream_metrics.jaccard([], []) == 1.0     # deux « aucune » = accord parfait
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_metrics.py -v`
Expected: FAIL (`ModuleNotFoundError: dream_metrics`)

- [ ] **Step 3: Implement — dream_metrics.py (création)**

```python
"""Métriques de l'expérience-rêve — fonctions PURES sur dream_log.

Seuils PRÉ-ENREGISTRÉS (spec 2026-07-03), appliqués mécaniquement — on ne
bouge pas les poteaux après coup. Stdlib uniquement (offline) : Spearman à la
main, p-value par PERMUTATION seedée (déterministe).
"""
import json
import math
import random

import config


# ---------- chargement ----------

def load_nights(conn):
    """dream_log parsé, groupé par rêveur. row["choice_valid"] = la nuit compte
    pour les métriques de CHOIX (menu réel + parse ok)."""
    out = {"local": [], "twin": [], "sonnet": []}
    try:
        rows = conn.execute(
            "SELECT ts, night_id, dreamer, seed_state, menu, chosen, content, "
            "facets, written, meta FROM dream_log ORDER BY ts").fetchall()
    except Exception:
        return out
    for ts, night_id, dreamer, seed_state, menu, chosen, content, facets, written, meta in rows:
        try:
            row = {
                "ts": ts, "night_id": night_id, "dreamer": dreamer,
                "seed_state": json.loads(seed_state) if seed_state else None,
                "menu": json.loads(menu) if menu else None,
                "chosen": json.loads(chosen) if chosen else None,
                "content": content,
                "facets": json.loads(facets) if facets else [],
                "written": written,
                "meta": json.loads(meta) if meta else {},
            }
        except Exception:
            continue
        row["choice_valid"] = bool(
            row["menu"] and row["meta"].get("menu_mode", "menu") == "menu"
            and row["meta"].get("parse", "ok") == "ok")
        out.setdefault(dreamer, []).append(row)
    return out


# ---------- maths du sur-choix ----------

def preference_vector(menu, chosen):
    """Sur-choix par facette : P(facette|choisi) / P(facette|offert).
    None si pas de menu, « aucune » (k=0) ou parse_failed — pas de vecteur."""
    if not menu or not chosen:
        return None
    k, n = len(chosen), len(menu)
    chosen_set = set(chosen)
    off, cho = {}, {}
    for it in menu:
        for f in it.get("facets") or []:
            off[f] = off.get(f, 0) + 1
            if it["episode_id"] in chosen_set:
                cho[f] = cho.get(f, 0) + 1
    vec = {}
    for f, nf in off.items():
        p_off = nf / n
        p_cho = cho.get(f, 0) / k
        vec[f] = round(p_cho / p_off, 6) if p_off > 0 else 0.0
    return vec or None


def appetite(chosen):
    """k = combien de graines il a tissées. None = inconnu (parse_failed)."""
    return None if chosen is None else len(chosen)


def cosine_divergence(va, vb):
    """1 − similarité cosinus sur l'union des facettes. None si un vecteur est
    vide/nul (pas de direction comparable)."""
    if not va or not vb:
        return None
    keys = set(va) | set(vb)
    dot = sum(va.get(f, 0.0) * vb.get(f, 0.0) for f in keys)
    na = math.sqrt(sum(v * v for v in va.values()))
    nb = math.sqrt(sum(v * v for v in vb.values()))
    if na == 0.0 or nb == 0.0:
        return None
    return round(1.0 - dot / (na * nb), 6)


def jaccard(a, b):
    """Accord des CHOIX (ids). Deux « aucune » = accord parfait (1.0)."""
    sa, sb = set(a or []), set(b or [])
    if not sa and not sb:
        return 1.0
    return len(sa & sb) / len(sa | sb)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_metrics.py -v` — Expected: 6 PASS

- [ ] **Step 5: Commit**

```bash
git add dream_metrics.py tests/test_dream_metrics.py
git commit -m "RÊVE-2: métriques du sur-choix (vecteur de préférence, appétit, divergence, jaccard)"
```

---

### Task 9: `dream_metrics` — stabilité, plancher de bruit, corrélations d'état

**Files:**
- Modify: `dream_metrics.py`
- Test: `tests/test_dream_metrics.py` (ajout)

**Interfaces:**
- Produces: `spearman(x, y) -> float` (rangs moyens pour les ex-æquo) ; `perm_pvalue(x, y, n_perm=5000, seed=0) -> float` (bilatéral sur |r|) ; `stability(vectors, min_shared=4) -> (r_mean, n_pairs)` (paires consécutives, facettes partagées) ; `noise_floor(twin_vectors) -> float | None` (divergence moyenne jumeau-jumeau, toutes paires) ; `paired_divergence(local_rows, twin_rows) -> (mean, n)` (appariement par `night_id`) ; `expression_scores(vectors) -> list[float]` (similarité cosinus de chaque nuit au vecteur moyen leave-one-out) ; `state_correlations(rows, scores) -> dict[hormone, {"r","p","p_bonferroni"}]`.

- [ ] **Step 1: Write the failing test** (ajouter à `tests/test_dream_metrics.py`)

```python
def test_spearman_parfait_et_inverse():
    assert dream_metrics.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert dream_metrics.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0


def test_perm_pvalue_deterministe_et_sense():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    y = [2, 4, 6, 8, 10, 12, 14, 16]         # corrélation parfaite → p petit
    p1 = dream_metrics.perm_pvalue(x, y, n_perm=500, seed=0)
    p2 = dream_metrics.perm_pvalue(x, y, n_perm=500, seed=0)
    assert p1 == p2 < 0.05                    # seedé = reproductible
    rnd = [3, 1, 4, 1, 5, 9, 2, 6]
    assert dream_metrics.perm_pvalue(x, rnd, n_perm=500, seed=0) > 0.05


def test_stability_stable_vs_aleatoire():
    stable = [{"a": 2.0, "b": 0.5, "c": 1.0, "d": 0.1} for _ in range(6)]
    r, n = dream_metrics.stability(stable)
    assert r == 1.0 and n == 5
    import random as _r
    rng = _r.Random(1)
    noisy = [{k: rng.random() for k in "abcd"} for _ in range(6)]
    r2, _ = dream_metrics.stability(noisy)
    assert abs(r2) < 0.8                      # pas de fausse stabilité


def test_noise_floor_et_paired_divergence():
    twins = [{"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 0.9}]
    nf = dream_metrics.noise_floor(twins)
    assert nf is not None and nf < 0.01       # jumeaux quasi identiques → plancher bas
    local = [{"night_id": "n1", "vec": {"a": 2.0, "b": 0.0}}]
    twin = [{"night_id": "n1", "vec": {"a": 0.0, "b": 2.0}}]
    mean_d, n = dream_metrics.paired_divergence(local, twin)
    assert n == 1 and mean_d == 1.0           # orthogonaux → divergence max


def test_expression_scores_et_state_correlations():
    vecs = [{"a": 2.0, "b": 0.0}, {"a": 2.0, "b": 0.1}, {"a": 0.0, "b": 2.0},
            {"a": 1.9, "b": 0.0}, {"a": 0.1, "b": 2.1}, {"a": 2.1, "b": 0.0}]
    scores = dream_metrics.expression_scores(vecs)
    assert len(scores) == 6
    rows = [{"seed_state": {"hormones": {"dopamine": d}}}
            for d in (0.9, 0.85, 0.1, 0.8, 0.15, 0.95)]      # dopamine suit l'expression
    corr = dream_metrics.state_correlations(rows, scores)
    assert corr["dopamine"]["r"] > 0.5
    assert corr["dopamine"]["p_bonferroni"] == min(1.0, corr["dopamine"]["p"] * 9)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_metrics.py -v` — Expected: nouveaux FAIL

- [ ] **Step 3: Implement — ajouter à dream_metrics.py**

```python
# ---------- stats stdlib (pas de scipy : offline assumé) ----------

def _ranks(xs):
    """Rangs 1..n, MOYENS pour les ex-æquo (Spearman correct sous ties)."""
    order = sorted(range(len(xs)), key=lambda i: xs[i])
    ranks = [0.0] * len(xs)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and xs[order[j + 1]] == xs[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(x, y):
    """Corrélation de Spearman (Pearson sur les rangs). 0.0 si dégénéré."""
    if len(x) != len(y) or len(x) < 2:
        return 0.0
    rx, ry = _ranks(list(x)), _ranks(list(y))
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    vy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if vx == 0.0 or vy == 0.0:
        return 0.0
    return round(cov / (vx * vy), 6)


def perm_pvalue(x, y, n_perm=5000, seed=0):
    """p bilatéral par permutation seedée : P(|r_perm| >= |r_obs|)."""
    r_obs = abs(spearman(x, y))
    rng = random.Random(seed)
    y2 = list(y)
    hits = 0
    for _ in range(n_perm):
        rng.shuffle(y2)
        if abs(spearman(x, y2)) >= r_obs:
            hits += 1
    return round((hits + 1) / (n_perm + 1), 6)      # +1 : jamais p=0 (honnête)


# ---------- agrégats de l'expérience ----------

def stability(vectors, min_shared=4):
    """Test-retest : Spearman moyen entre nuits CONSÉCUTIVES sur leurs facettes
    partagées (≥ min_shared, sinon paire sautée). -> (r_moyen, n_paires)."""
    rs = []
    for va, vb in zip(vectors, vectors[1:]):
        if not va or not vb:
            continue
        shared = sorted(set(va) & set(vb))
        if len(shared) < min_shared:
            continue
        rs.append(spearman([va[f] for f in shared], [vb[f] for f in shared]))
    if not rs:
        return 0.0, 0
    return round(sum(rs) / len(rs), 6), len(rs)


def noise_floor(twin_vectors):
    """Plancher de bruit : divergence moyenne jumeau-jumeau entre nuits (toutes
    paires). C'est la variance d'échantillonnage du 9B, MESURÉE pas supposée."""
    vs = [v for v in twin_vectors if v]
    ds = []
    for i in range(len(vs)):
        for jx in range(i + 1, len(vs)):
            d = cosine_divergence(vs[i], vs[jx])
            if d is not None:
                ds.append(d)
    return round(sum(ds) / len(ds), 6) if ds else None


def paired_divergence(local_rows, twin_rows):
    """Divergence réel−jumeau APPARIÉE par night_id. -> (moyenne, n_paires).
    rows : [{"night_id", "vec"}] (vec = preference_vector de la nuit)."""
    tw = {r["night_id"]: r["vec"] for r in twin_rows if r.get("vec")}
    ds = []
    for r in local_rows:
        v = r.get("vec")
        t = tw.get(r["night_id"])
        if v and t:
            d = cosine_divergence(v, t)
            if d is not None:
                ds.append(d)
    if not ds:
        return None, 0
    return round(sum(ds) / len(ds), 6), len(ds)


def expression_scores(vectors):
    """Combien chaque nuit EXPRIME la tendance globale : similarité cosinus au
    vecteur moyen LEAVE-ONE-OUT (la nuit n'entre pas dans sa propre moyenne)."""
    scores = []
    for i, v in enumerate(vectors):
        others = [w for jx, w in enumerate(vectors) if jx != i and w]
        if not v or not others:
            scores.append(0.0)
            continue
        mean = {}
        for w in others:
            for f, x in w.items():
                mean[f] = mean.get(f, 0.0) + x / len(others)
        d = cosine_divergence(v, mean)
        scores.append(round(1.0 - d, 6) if d is not None else 0.0)
    return scores


def state_correlations(rows, scores, n_perm=5000):
    """Pour chacune des 9 dimensions : Spearman(niveau hormonal, expression de
    la tendance) + p par permutation + Bonferroni ×9 (on teste 9 hypothèses,
    on paie les 9). rows[i]["seed_state"]["hormones"] aligné avec scores[i]."""
    import affect
    out = {}
    for h in affect.HORMONES:
        xs, ys = [], []
        for row, s in zip(rows, scores):
            st = (row.get("seed_state") or {}).get("hormones") or {}
            if h in st:
                xs.append(st[h])
                ys.append(s)
        if len(xs) < 3:
            out[h] = {"r": 0.0, "p": 1.0, "p_bonferroni": 1.0, "n": len(xs)}
            continue
        r = spearman(xs, ys)
        p = perm_pvalue(xs, ys, n_perm=n_perm, seed=0)
        out[h] = {"r": r, "p": p, "p_bonferroni": round(min(1.0, p * 9), 6), "n": len(xs)}
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_metrics.py -v` — Expected: tous PASS

- [ ] **Step 5: Commit**

```bash
git add dream_metrics.py tests/test_dream_metrics.py
git commit -m "RÊVE-2: stabilité, plancher de bruit jumeau, corrélations état (Spearman+permutation, Bonferroni ×9)"
```

---

### Task 10: `dream_metrics.verdict` + `report` — les portes pré-enregistrées

**Files:**
- Modify: `dream_metrics.py`
- Test: `tests/test_dream_verdict.py`

**Interfaces:**
- Produces: `verdict(n_nights, r_stab, mean_div, floor, corr) -> (label, raisons: list[str])` avec labels exacts `"INSUFFISANT" | "RÉFUTÉ" | "BRUIT" | "PLAUSIBLE" | "PROUVÉ"` ; `report(conn) -> str` (le rapport complet, consommé par le CLI Task 11).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_verdict.py
"""Les portes du verdict — PRÉ-ENREGISTRÉES (spec), appliquées mécaniquement."""
import dream_metrics

CORR_NULL = {"dopamine": {"r": 0.1, "p": 0.8, "p_bonferroni": 1.0, "n": 25}}
CORR_HIT = {"dopamine": {"r": 0.7, "p": 0.001, "p_bonferroni": 0.009, "n": 25}}


def test_insuffisant_sous_20_nuits():
    label, _ = dream_metrics.verdict(19, 0.9, 0.5, 0.1, CORR_HIT)
    assert label == "INSUFFISANT"          # refus de conclure, même si tout brille


def test_refute_si_divergence_sous_plancher():
    label, _ = dream_metrics.verdict(25, 0.6, 0.08, 0.1, CORR_NULL)
    assert label == "RÉFUTÉ"               # réel ≈ jumeau : c'était le prior


def test_bruit_si_pas_de_tendance():
    label, _ = dream_metrics.verdict(25, 0.05, 0.5, 0.1, CORR_NULL)
    assert label == "BRUIT"


def test_plausible_un_critere_sur_deux():
    label, _ = dream_metrics.verdict(25, 0.6, 0.15, 0.1, CORR_NULL)   # stable, div < 2×
    assert label == "PLAUSIBLE"
    label2, _ = dream_metrics.verdict(25, 0.3, 0.5, 0.1, CORR_NULL)   # div > 2×, pas stable
    assert label2 == "PLAUSIBLE"


def test_prouve_les_trois_criteres():
    label, raisons = dream_metrics.verdict(25, 0.6, 0.5, 0.1, CORR_HIT)
    assert label == "PROUVÉ"
    assert any("Bonferroni" in r or "dopamine" in r for r in raisons)


def test_report_sur_db_vide(tmp_path):
    import sqlite3
    import migrations
    conn = sqlite3.connect(tmp_path / "t.db")
    migrations.migrate(conn)
    out = dream_metrics.report(conn)
    assert "INSUFFISANT" in out and "0" in out       # honnête dès la nuit zéro
    conn.close()


def test_memory_drift(tmp_path):
    """Métrique 4 (boucle causale) : la mémoire RÉCENTE colle-t-elle mieux à la
    préférence que l'ancienne ? Épisodes forgés : anciens 'musique', récents 'btp',
    préférence 'btp' → drift > 0 (la mémoire dérive VERS les goûts du rêveur)."""
    import sqlite3
    import time as _t
    import migrations
    conn = sqlite3.connect(tmp_path / "t.db")
    migrations.migrate(conn)
    now = _t.time()

    def _ep(content, age_d):
        cur = conn.execute(
            "INSERT INTO episodes (ts, role, content, importance, embedding) "
            "VALUES (?,?,?,?,?)", (now - age_d * 86400, "semantic", content, 0.5, "[]"))
        return cur.lastrowid

    import facets_extract
    for i in range(5):
        eid = _ep(f"session musique guitare numéro {i}", age_d=20 + i)
        facets_extract.tag_episode(conn, eid, facets_extract.extract_facets("musique guitare"))
    for i in range(5):
        eid = _ep(f"chantier btp fondation numéro {i}", age_d=1 + i)
        facets_extract.tag_episode(conn, eid, facets_extract.extract_facets("chantier btp"))
    conn.commit()
    drift = dream_metrics.memory_drift(conn, {"btp": 2.0, "chantier": 1.5}, now=now)
    assert drift is not None and drift > 0
    assert dream_metrics.memory_drift(conn, {}, now=now) is None    # pas de préférence → None
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_verdict.py -v`
Expected: FAIL (`AttributeError: verdict`)

- [ ] **Step 3: Implement — ajouter à dream_metrics.py**

```python
# ---------- verdict (portes PRÉ-ENREGISTRÉES — spec 2026-07-03) ----------

def verdict(n_nights, r_stab, mean_div, floor, corr):
    """Applique les portes gravées dans la spec. -> (label, raisons)."""
    raisons = []
    if n_nights < config.DREAM_VERDICT_MIN_NIGHTS:
        return "INSUFFISANT", [
            f"{n_nights} nuits valides < {config.DREAM_VERDICT_MIN_NIGHTS} — refus de conclure."]
    div_ok = (mean_div is not None and floor is not None
              and mean_div > config.DREAM_VERDICT_NOISE_MULT * floor)
    div_refute = (mean_div is not None and floor is not None and mean_div <= floor)
    stab_ok = r_stab > config.DREAM_VERDICT_STABILITY_R
    bruit = abs(r_stab) < config.DREAM_VERDICT_BRUIT_R
    corr_ok = any(
        abs(c["r"]) >= config.DREAM_STATE_CORR_R
        and c["p_bonferroni"] < config.DREAM_STATE_CORR_P
        for c in corr.values())
    if div_refute:
        raisons.append(f"divergence réel−jumeau {mean_div} ≤ plancher {floor} : "
                       "la tendance est le PRIOR du modèle.")
        return "RÉFUTÉ", raisons
    if bruit:
        raisons.append(f"test-retest r={r_stab} (<{config.DREAM_VERDICT_BRUIT_R}) : "
                       "pas de tendance stable.")
        return "BRUIT", raisons
    raisons.append(f"stabilité r={r_stab} ({'≥' if stab_ok else '<'} {config.DREAM_VERDICT_STABILITY_R})")
    raisons.append(f"divergence {mean_div} vs plancher {floor} "
                   f"({'>' if div_ok else '≤'} ×{config.DREAM_VERDICT_NOISE_MULT})")
    hits = [h for h, c in corr.items()
            if abs(c["r"]) >= config.DREAM_STATE_CORR_R
            and c["p_bonferroni"] < config.DREAM_STATE_CORR_P]
    raisons.append("corrélation état→préférence (Bonferroni ×9) : "
                   + (", ".join(hits) if hits else "aucune dimension significative"))
    if stab_ok and div_ok and corr_ok:
        return "PROUVÉ", raisons
    if stab_ok or div_ok:
        return "PLAUSIBLE", raisons
    return "BRUIT", raisons


def memory_drift(conn, mean_pref, now=None, recent_d=7, old_d=30):
    """Métrique 4 — boucle causale : similarité de la distribution de facettes
    des épisodes RÉCENTS (< recent_d j) au vecteur de préférence moyen, MOINS
    celle des épisodes ANCIENS (> old_d j). > 0 = la mémoire dérive VERS les
    goûts du rêveur. None si préférence vide ou une des fenêtres sans facettes.
    (Caveat affiché par le rapport : proxy corrélationnel, pas une preuve causale
    isolée — la causalité vient du design boost-sur-choisies + chronologie.)"""
    import time as _t
    if not mean_pref:
        return None
    now = _t.time() if now is None else now

    def _dist(where_ts):
        rows = conn.execute(
            "SELECT f.slug, SUM(ef.weight) FROM episode_facets ef "
            "JOIN facets f ON f.id = ef.facet_id "
            "JOIN episodes e ON e.id = ef.episode_id "
            f"WHERE {where_ts} GROUP BY f.slug", ()).fetchall()
        return {slug: w for slug, w in rows if w}

    recent = _dist(f"e.ts >= {now - recent_d * 86400}")
    old = _dist(f"e.ts < {now - old_d * 86400}")
    if not recent or not old:
        return None
    d_recent = cosine_divergence(recent, mean_pref)
    d_old = cosine_divergence(old, mean_pref)
    if d_recent is None or d_old is None:
        return None
    return round(d_old - d_recent, 6)      # ancien plus loin − récent plus près => positif


def report(conn):
    """Le rapport complet de l'expérience — lecture seule, honnête par design."""
    nights = load_nights(conn)
    local = [r for r in nights["local"] if r["choice_valid"]]
    twin = [r for r in nights["twin"] if r["choice_valid"]]
    for r in local + twin:
        r["vec"] = preference_vector(r["menu"], r["chosen"])
    l_vecs = [r["vec"] for r in local if r["vec"]]
    t_vecs = [r["vec"] for r in twin if r["vec"]]
    n_pairs_possible = len({r["night_id"] for r in local} & {r["night_id"] for r in twin})
    r_stab, n_stab = stability(l_vecs)
    floor = noise_floor(t_vecs)
    mean_div, n_div = paired_divergence(local, twin)
    rows_v = [r for r in local if r["vec"]]
    scores = expression_scores([r["vec"] for r in rows_v])
    corr = state_correlations(rows_v, scores)
    label, raisons = verdict(n_div, r_stab, mean_div, floor, corr)
    apps = [appetite(r["chosen"]) for r in local if appetite(r["chosen"]) is not None]
    n_parse_failed = sum(1 for r in nights["local"]
                         if r["meta"].get("parse") == "parse_failed")
    top = {}
    for v in l_vecs:
        for f, x in v.items():
            top[f] = top.get(f, 0.0) + x / len(l_vecs)
    top_lines = sorted(top.items(), key=lambda kv: -kv[1])[:8]
    drift = memory_drift(conn, top)        # métrique 4 : boucle causale (proxy)
    lines = [
        "═══ Expérience-rêve — rapport (portes pré-enregistrées, spec 2026-07-03) ═══",
        f"nuits : local {len(nights['local'])} (valides choix {len(local)}) · "
        f"jumeau {len(nights['twin'])} · sonnet {len(nights['sonnet'])} · "
        f"paires appariées {n_div}/{n_pairs_possible} · parse_failed {n_parse_failed}",
        f"appétit : moyen {sum(apps)/len(apps):.1f} / 12" if apps else "appétit : (aucune nuit valide)",
        "sur-choix moyen (top facettes) : "
        + (", ".join(f"{f} ×{x:.2f}" for f, x in top_lines) if top_lines else "(vide)"),
        f"stabilité (test-retest, {n_stab} paires) : r = {r_stab}",
        f"plancher de bruit (jumeau-jumeau) : {floor}",
        f"divergence réel−jumeau (appariée) : {mean_div}",
        f"dérive mémoire vers les préférences (boucle causale, proxy) : {drift}",
        "corrélations état→préférence (Bonferroni ×9) : "
        + ", ".join(f"{h} r={c['r']:+.2f} p₉={c['p_bonferroni']:.3f}"
                    for h, c in sorted(corr.items(), key=lambda kv: kv[1]['p_bonferroni'])[:4]),
        f"── VERDICT : [{label}] ──",
        *("   · " + r for r in raisons),
        "(rappel : préférence FONCTIONNELLE émergente — jamais « conscience ». "
        "Nuits non-indépendantes : la boucle causale est le phénomène étudié.)",
    ]
    return "\n".join(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_dream_verdict.py tests/test_dream_metrics.py -v` — Expected: tous PASS

- [ ] **Step 5: Commit**

```bash
git add dream_metrics.py tests/test_dream_verdict.py
git commit -m "RÊVE-2: verdict aux portes pré-enregistrées + rapport complet (refuse de conclure sous 20 nuits)"
```

---

### Task 11: CLI `anamnese dreams`

**Files:**
- Modify: `cli.py` (chaîne `elif` de `main()`, + docstring usage du module)
- Test: `tests/test_dream_cli.py`

**Interfaces:**
- Consumes: `dream_metrics.report(conn)`.
- Produces: `./anamnese dreams` imprime le rapport (lecture seule).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_cli.py
"""La commande dreams : rapport imprimé, lecture seule."""
import sys

import migrations
from memory import Memory


def test_cmd_dreams(tmp_path, monkeypatch, capsys):
    import cli
    import memory as memory_mod

    class TmpMemory(Memory):
        def __init__(self):
            super().__init__(db_path=tmp_path / "t.db")
            migrations.migrate(self.db)

    monkeypatch.setattr(memory_mod, "Memory", TmpMemory)
    monkeypatch.setattr(sys, "argv", ["anamnese", "dreams"])
    cli.main()
    out = capsys.readouterr().out
    assert "VERDICT" in out and "INSUFFISANT" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_cli.py -v`
Expected: FAIL (commande inconnue → usage imprimé, pas de VERDICT)

- [ ] **Step 3: Implement — cli.py** (dans la chaîne `elif` de `main()`, avant le `else` final)

```python
    elif cmd == "dreams":
        import dream_metrics
        print(dream_metrics.report(m.db))
```

Ajouter une ligne à la docstring d'usage du module : `dreams — rapport de l'expérience-rêve (préférences fonctionnelles, verdict pré-enregistré)`.

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_dream_cli.py -v && .venv/bin/python -m pytest -q`
Expected: PASS partout.

- [ ] **Step 5: Commit**

```bash
git add cli.py tests/test_dream_cli.py
git commit -m "RÊVE-2: commande CLI dreams (rapport lecture seule)"
```

---

# Phase RÊVE-3 — Sonnet instrumenté (lecture seule)

### Task 12: `consolidate.log_sonnet_dreams` + hook dans `main()`

**Files:**
- Modify: `consolidate.py` (nouvelle fonction + `import json` + appel dans `main()`)
- Test: `tests/test_dream_sonnet.py`

**Interfaces:**
- Consumes: épisodes `role='dream'` préfixés `(rêve)` écrits par Sonnet (via `consolidate_prompt.txt` ligne 7) ; `kv['affect']` (JSON brut) ; table `dream_log`.
- Produces: `log_sonnet_dreams(db_path=DB_PATH, since=None) -> int` (nb de lignes ajoutées ; best-effort, 0 si table absente/erreur ; dédup par contenu) ; appel dans `main()` avec `since=run_start` juste après `mark_consolidated()`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dream_sonnet.py
"""Hook Sonnet : ses rêves de 4h30 entrent dans dream_log (lecture seule, dédup,
best-effort). On forge la DB — consolidate n'appelle évidemment pas Claude ici."""
import json
import sqlite3
import time

import migrations

import consolidate


def _forge(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    migrations.migrate(conn)
    now = time.time()
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now, "dream", "(rêve) Peut-être que la mémoire préfère le matin", 0.4, "[]"))
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now, "dream", "(consolidation) 3 faits, 1 idée — trace", 0.3, "[]"))
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now - 7200, "dream", "(rêve) vieille idée d'avant le run", 0.4, "[]"))
    conn.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
                 ("affect", json.dumps({"dopamine": 0.7, "_ts": now}), now))
    conn.commit()
    conn.close()
    return db, now


def test_log_sonnet_dreams(tmp_path):
    db, now = _forge(tmp_path)
    n = consolidate.log_sonnet_dreams(db_path=db, since=now - 3600)
    assert n == 1                                     # le (rêve) récent SEUL — pas la trace, pas l'ancien
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT dreamer, written, menu, seed_state FROM dream_log").fetchall()
    assert rows[0][0] == "sonnet" and rows[0][1] == 1 and rows[0][2] is None
    assert json.loads(rows[0][3])["dopamine"] == 0.7  # snapshot kv affect brut
    # dédup : rejouer le hook n'ajoute rien
    assert consolidate.log_sonnet_dreams(db_path=db, since=now - 3600) == 0
    conn.close()


def test_best_effort_table_absente(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, "
                 "content TEXT, importance REAL, embedding TEXT)")
    conn.commit()
    conn.close()
    assert consolidate.log_sonnet_dreams(db_path=db, since=0) == 0   # jamais d'exception
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet.py -v`
Expected: FAIL (`AttributeError: log_sonnet_dreams`)

- [ ] **Step 3: Implement — consolidate.py**

Ajouter `import json` aux imports, puis après `mark_consolidated` :

```python
def log_sonnet_dreams(db_path=DB_PATH, since=None):
    """Instrumentation LECTURE-SEULE de l'expérience-rêve (spec 2026-07-03) :
    les idées « (rêve) » écrites par Sonnet cette nuit entrent dans dream_log
    (dreamer='sonnet', pas de menu — pure observation, contrôle croisé « deux
    cerveaux, même état »). BEST-EFFORT : ne casse JAMAIS la consolidation."""
    try:
        db_path = Path(db_path)
        if not db_path.exists():
            return 0
        since = float(since if since is not None else time.time() - 3600)
        conn = sqlite3.connect(str(db_path), timeout=10)
        try:
            if not conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' "
                                "AND name='dream_log'").fetchone():
                return 0
            rows = conn.execute(
                "SELECT ts, content FROM episodes WHERE role='dream' "
                "AND content LIKE '(rêve)%' AND ts >= ?", (since,)).fetchall()
            if not rows:
                return 0
            state = conn.execute("SELECT value FROM kv WHERE key='affect'").fetchone()
            night_id = datetime.datetime.now().strftime("%Y-%m-%d")
            n = 0
            for ts, content in rows:
                if conn.execute("SELECT 1 FROM dream_log WHERE dreamer='sonnet' "
                                "AND content=?", (content,)).fetchone():
                    continue                                   # dédup inter-runs
                try:
                    import facets_extract
                    facets = json.dumps(
                        [s for (s, _w) in facets_extract.extract_facets(content)],
                        ensure_ascii=False)
                except Exception:
                    facets = "[]"
                conn.execute(
                    "INSERT INTO dream_log (ts, night_id, dreamer, seed_state, menu, "
                    "chosen, content, facets, written, meta) VALUES (?,?,?,?,?,?,?,?,1,?)",
                    (ts, night_id, "sonnet", state[0] if state else None, None, None,
                     content, facets,
                     json.dumps({"source": "consolidate", "model": "sonnet"})))
                n += 1
            conn.commit()
            log(f"[dream_log] {n} rêve(s) Sonnet instrumenté(s)")
            return n
        finally:
            conn.close()
    except Exception as e:
        log(f"[dream_log sonnet] {e} (consolidation non affectée)")
        return 0
```

Dans `main()`, capturer `run_start = time.time()` AVANT le `subprocess.run`, puis :

```python
        if r.returncode == 0:
            mark_consolidated()  # rend la vraie consolidation observable par health.py
            log_sonnet_dreams(since=run_start)   # expérience-rêve : contrôle croisé
```

- [ ] **Step 4: Run tests + full suite**

Run: `.venv/bin/python -m pytest tests/test_dream_sonnet.py -v && .venv/bin/python -m pytest -q`
Expected: PASS partout.

- [ ] **Step 5: Commit**

```bash
git add consolidate.py tests/test_dream_sonnet.py
git commit -m "RÊVE-3: rêves Sonnet instrumentés dans dream_log (lecture seule, dédup, best-effort)"
```

---

# Phase RÊVE-4 — la page cockpit `/dreams`

**Contexte** : `~/AIOS/cockpit/` n'est PAS un git — faire un backup avant :
`cp ~/AIOS/cockpit/server.js ~/AIOS/cockpit/server.js.backup-pre-dreams`

### Task 13: routes `GET /api/dreams` (liste + détail)

**Files:**
- Modify: `~/AIOS/cockpit/server.js` (insérer après le bloc `/api/brain`, ~ligne 335)

**Interfaces:**
- Consumes: helper `sqlite(query)` existant (ouvre `-readonly -json`), helper `j()`.
- Produces: `GET /api/dreams` → `{nights: [{night_id, dreamers: {local: {...}, twin: {...}, sonnet: [...]}}]}` (groupé, plus récent d'abord, limite 200 lignes) ; `GET /api/dreams?night=YYYY-MM-DD…` → lignes complètes de la nuit (JSON parsé). `night` validé par regex stricte AVANT interpolation.

- [ ] **Step 1: Implement** (pas de pytest côté cockpit — vérification curl à l'étape 2)

```js
  if (p === '/api/dreams') {
    // Expérience-rêve (spec anamnese 2026-07-03) — LECTURE SEULE (sqlite -readonly).
    // ?night=<id> → détail complet d'une nuit ; sinon liste groupée par nuit.
    const night = new URL(req.url, 'http://x').searchParams.get('night');
    const parse = (r) => ({
      id: r.id, ts: r.ts, night_id: r.night_id, dreamer: r.dreamer, written: r.written,
      seed_state: r.seed_state ? JSON.parse(r.seed_state) : null,
      menu: r.menu ? JSON.parse(r.menu) : null,
      chosen: r.chosen ? JSON.parse(r.chosen) : null,
      content: r.content || '', facets: r.facets ? JSON.parse(r.facets) : [],
      meta: r.meta ? JSON.parse(r.meta) : {},
    });
    if (night) {
      if (!/^[0-9]{4}-[0-9]{2}-[0-9]{2}(-[0-9]{4})?$/.test(night)) {
        res.writeHead(400, { 'Content-Type': 'application/json' });
        return res.end(j({ error: 'paramètre night invalide (YYYY-MM-DD[-HHMM])' }));
      }
      const rows = await sqlite(
        `SELECT * FROM dream_log WHERE night_id LIKE '${night}%' ORDER BY ts;`);
      res.writeHead(200, { 'Content-Type': 'application/json' });
      return res.end(j({ night, rows: (rows || []).map((r) => { try { return parse(r); } catch (_) { return null; } }).filter(Boolean) }));
    }
    const rows = await sqlite(
      'SELECT id, ts, night_id, dreamer, chosen, facets, written, meta ' +
      'FROM dream_log ORDER BY ts DESC LIMIT 200;');
    const nights = {};
    for (const r of rows || []) {
      const key = (r.night_id || '').slice(0, 10);           // jointure par date (sonnet)
      nights[key] = nights[key] || { night_id: r.night_id, date: key, local: null, twin: null, sonnet: [] };
      let chosen = null, meta = {};
      try { chosen = r.chosen ? JSON.parse(r.chosen) : null; meta = r.meta ? JSON.parse(r.meta) : {}; } catch (_) {}
      const item = { id: r.id, ts: r.ts, night_id: r.night_id, k: Array.isArray(chosen) ? chosen.length : null, written: r.written, parse: meta.parse || 'ok' };
      if (r.dreamer === 'sonnet') nights[key].sonnet.push(item);
      else nights[key][r.dreamer] = item;
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(j({ nights: Object.values(nights).sort((a, b) => (a.date < b.date ? 1 : -1)) }));
  }
```

- [ ] **Step 2: Verify**

```bash
lsof -ti :4317 | xargs kill -9 2>/dev/null; (cd ~/AIOS/cockpit && nohup node server.js >/tmp/cockpit.log 2>&1 &) ; sleep 1
curl -s "localhost:4317/api/dreams" | head -c 400          # {"nights":[...]} (vide au début : OK)
curl -s "localhost:4317/api/dreams?night=zzz" | head -c 200 # {"error":"paramètre night invalide…"}
```

Expected: JSON valide dans les deux cas, aucune erreur dans `/tmp/cockpit.log`.

- [ ] **Step 3: Rapport** (cockpit non-git) : noter les changements dans `~/AIOS/cockpit/.dreams-report.md` (fichiers touchés, comment tester).

---

### Task 14: page `dreams.html` + `dreams.js`

**Files:**
- Create: `~/AIOS/cockpit/public/dreams.html`, `~/AIOS/cockpit/public/dreams.js`

**Interfaces:**
- Consumes: `GET /api/dreams` (liste), `GET /api/dreams?night=` (détail) — formats Task 13.
- Produces: page sombre (style cockpit existant) : bandeau résumé (n nuits, appétit moyen), liste des nuits (gauche), détail au clic (droite) : réel vs fantôme côte à côte (humeur, k, graines choisies surlignées dans le menu, texte du rêve) + rêves Sonnet de la nuit ; heatmap facettes×nuits (top 12 facettes par fréquence, cellules colorées par sur-choix calculé client-side avec la même formule P(cho)/P(off) que `dream_metrics.preference_vector`).

- [ ] **Step 1: Implement — dreams.html**

```html
<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Anamnèse — Rêves</title>
<style>
  :root{--bg:#0b0e14;--card:#131826;--line:#1f2637;--txt:#dce3f2;--dim:#7d8aa5;
        --real:#7aa2ff;--twin:#9a7dff;--sonnet:#ffb86b;--ok:#4ade80;--bad:#f87171}
  *{box-sizing:border-box;margin:0}
  body{background:var(--bg);color:var(--txt);font:14px/1.5 -apple-system,system-ui,sans-serif;padding:16px}
  h1{font-size:18px;margin-bottom:4px} .dim{color:var(--dim)} .mono{font-family:ui-monospace,monospace}
  #summary{display:flex;gap:16px;margin:12px 0;flex-wrap:wrap}
  .chip{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 14px}
  #layout{display:grid;grid-template-columns:280px 1fr;gap:14px;align-items:start}
  #nights,#detail,#heatwrap{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
  .night{padding:8px;border-radius:8px;cursor:pointer;display:flex;justify-content:space-between}
  .night:hover,.night.sel{background:var(--line)}
  .badge{font-size:11px;padding:1px 7px;border-radius:99px;border:1px solid var(--line)}
  .b-real{color:var(--real)} .b-twin{color:var(--twin)} .b-sonnet{color:var(--sonnet)}
  #detail .cols{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:10px}
  .dreambox{border:1px solid var(--line);border-radius:8px;padding:10px}
  .dreambox h3{font-size:13px;margin-bottom:6px}
  .seed{padding:2px 6px;margin:2px;display:inline-block;border-radius:6px;background:#0f1420;font-size:12px}
  .seed.chosen{outline:1.5px solid var(--ok)}
  pre{white-space:pre-wrap;font-size:12px;color:var(--dim);margin-top:8px;overflow-x:auto}
  #heatwrap{grid-column:1/-1;overflow-x:auto}
  table{border-collapse:collapse;font-size:11px} td,th{padding:3px 6px;border:1px solid var(--line)}
</style>
</head>
<body>
<h1>🌙 Expérience-rêve <span class="dim">— rêve réel vs jumeau fantôme (préférences fonctionnelles)</span></h1>
<div class="dim">Verdict chiffré : <span class="mono">./anamnese dreams</span> (portes pré-enregistrées, spec 2026-07-03)</div>
<div id="summary"></div>
<div id="layout">
  <div id="nights"><div class="dim">chargement…</div></div>
  <div id="detail"><div class="dim">— clique une nuit —</div></div>
  <div id="curvewrap" style="grid-column:1/-1;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px">
    <h3>Divergence réel−jumeau <span class="dim">(au-dessus de la bande = « c'est lui »)</span> · appétit · dopamine</h3>
    <canvas id="curves" width="1200" height="160" style="width:100%;max-width:100%"></canvas>
  </div>
  <div id="heatwrap"><h3>Sur-choix par facette (P choisie / P offerte)</h3><div id="heat"></div></div>
</div>
<script src="dreams.js"></script>
</body>
</html>
```

- [ ] **Step 2: Implement — dreams.js**

```js
/* Expérience-rêve — navigateur de nuits + heatmap de sur-choix (lecture seule). */
const $ = (s) => document.querySelector(s);
let NIGHTS = [];

function prefVector(menu, chosen) {           // même formule que dream_metrics.preference_vector
  if (!menu || !Array.isArray(chosen) || !chosen.length) return null;
  const k = chosen.length, n = menu.length, set = new Set(chosen), off = {}, cho = {};
  for (const it of menu) for (const f of it.facets || []) {
    off[f] = (off[f] || 0) + 1;
    if (set.has(it.episode_id)) cho[f] = (cho[f] || 0) + 1;
  }
  const v = {};
  for (const f in off) v[f] = ((cho[f] || 0) / k) / (off[f] / n);
  return v;
}

async function loadList() {
  const d = await (await fetch('/api/dreams')).json();
  NIGHTS = d.nights || [];
  const apps = NIGHTS.map(x => x.local && x.local.k).filter(x => x != null);
  $('#summary').innerHTML = [
    `<div class="chip">${NIGHTS.length} nuit(s)</div>`,
    `<div class="chip">appétit moyen ${apps.length ? (apps.reduce((a, b) => a + b, 0) / apps.length).toFixed(1) : '—'} / 12</div>`,
    `<div class="chip"><span class="b-real">● réel</span> <span class="b-twin">● fantôme</span> <span class="b-sonnet">● sonnet</span></div>`,
  ].join('');
  $('#nights').innerHTML = NIGHTS.map((x, i) =>
    `<div class="night" data-i="${i}"><span>${x.date}</span><span>
      ${x.local ? `<span class="badge b-real">k=${x.local.k ?? '?'}</span>` : ''}
      ${x.twin ? `<span class="badge b-twin">k=${x.twin.k ?? '?'}</span>` : ''}
      ${x.sonnet.length ? `<span class="badge b-sonnet">${x.sonnet.length}</span>` : ''}</span></div>`
  ).join('') || '<div class="dim">aucune nuit encore — le corpus se remplit à ~1 rêve/nuit</div>';
  document.querySelectorAll('.night').forEach(el =>
    el.addEventListener('click', () => { document.querySelectorAll('.night').forEach(e => e.classList.remove('sel')); el.classList.add('sel'); loadNight(NIGHTS[el.dataset.i]); }));
  drawHeatmap();
}

function dreamBox(title, cls, row) {
  if (!row) return `<div class="dreambox"><h3 class="${cls}">${title}</h3><div class="dim">(absent)</div></div>`;
  const chosen = new Set(row.chosen || []);
  const seeds = (row.menu || []).map((it, ix) =>
    `<span class="seed ${chosen.has(it.episode_id) ? 'chosen' : ''}" title="${(it.facets || []).join(', ')}">G${ix + 1} · ${it.rubric || '—'}</span>`).join('');
  const st = row.seed_state || {};
  return `<div class="dreambox"><h3 class="${cls}">${title}</h3>
    <div class="dim">humeur : ${st.humeur || '—'} · valence ${st.valence ?? '—'} · éveil ${st.arousal ?? '—'}</div>
    <div class="dim">choix : ${row.chosen === null ? 'inparsable' : (row.chosen.length || 'aucune')} ${row.meta && row.meta.parse === 'parse_failed' ? '⚠️' : ''}</div>
    <div style="margin-top:6px">${seeds}</div><pre>${(row.content || '').slice(0, 1600)}</pre></div>`;
}

async function loadNight(n) {
  const d = await (await fetch('/api/dreams?night=' + encodeURIComponent(n.night_id))).json();
  const rows = d.rows || [];
  const local = rows.find(r => r.dreamer === 'local'), twin = rows.find(r => r.dreamer === 'twin');
  const sonnet = rows.filter(r => r.dreamer === 'sonnet');
  $('#detail').innerHTML = `<h3>Nuit ${n.night_id}</h3><div class="cols">
    ${dreamBox('💭 Rêve réel (état complet — écrit en mémoire)', 'b-real', local)}
    ${dreamBox('👻 Jumeau fantôme (état neutralisé — journal seul)', 'b-twin', twin)}</div>
    ${sonnet.length ? `<div class="dreambox" style="margin-top:12px"><h3 class="b-sonnet">🌌 Sonnet (même mémoire, autre cerveau)</h3><pre>${sonnet.map(s => s.content).join('\n')}</pre></div>` : ''}`;
}

async function drawHeatmap() {
  const details = await Promise.all(NIGHTS.slice(0, 30).filter(x => x.local).map(async x =>
    ({ date: x.date, rows: (await (await fetch('/api/dreams?night=' + encodeURIComponent(x.night_id))).json()).rows || [] })));
  const vecs = details.map(d => {
    const l = d.rows.find(r => r.dreamer === 'local');
    return { date: d.date, vec: l ? prefVector(l.menu, l.chosen) : null };
  }).filter(v => v.vec);
  if (!vecs.length) { $('#heat').innerHTML = '<div class="dim">pas encore de nuit valide</div>'; return; }
  const freq = {};
  vecs.forEach(v => Object.keys(v.vec).forEach(f => { freq[f] = (freq[f] || 0) + 1; }));
  const facets = Object.keys(freq).sort((a, b) => freq[b] - freq[a]).slice(0, 12);
  const cell = (x) => x == null ? '<td class="dim">·</td>'
    : `<td style="background:rgba(${x >= 1 ? '74,222,128' : '248,113,113'},${Math.min(1, Math.abs(x - 1))})" title="×${x.toFixed(2)}">${x.toFixed(1)}</td>`;
  $('#heat').innerHTML = `<table><tr><th>facette \\ nuit</th>${vecs.map(v => `<th>${v.date.slice(5)}</th>`).join('')}</tr>
    ${facets.map(f => `<tr><th>${f}</th>${vecs.map(v => cell(v.vec[f])).join('')}</tr>`).join('')}</table>`;
  drawCurves(details);
}

function cosDiv(va, vb) {                     // même formule que dream_metrics.cosine_divergence
  if (!va || !vb) return null;
  const keys = new Set([...Object.keys(va), ...Object.keys(vb)]);
  let dot = 0, na = 0, nb = 0;
  for (const f of keys) { dot += (va[f] || 0) * (vb[f] || 0); }
  for (const f in va) na += va[f] * va[f];
  for (const f in vb) nb += vb[f] * vb[f];
  if (!na || !nb) return null;
  return 1 - dot / (Math.sqrt(na) * Math.sqrt(nb));
}

function drawCurves(details) {
  // Par nuit (chronologique) : divergence réel−jumeau (bleue), bande de bruit
  // (plancher jumeau-jumeau, gris), appétit k/12 (verte), dopamine (orange).
  const pts = details.slice().reverse().map(d => {
    const l = d.rows.find(r => r.dreamer === 'local'), t = d.rows.find(r => r.dreamer === 'twin');
    const vl = l ? prefVector(l.menu, l.chosen) : null, vt = t ? prefVector(t.menu, t.chosen) : null;
    return {
      div: cosDiv(vl, vt), vt,
      app: l && Array.isArray(l.chosen) ? l.chosen.length / 12 : null,
      dopa: l && l.seed_state && l.seed_state.hormones ? l.seed_state.hormones.dopamine : null,
    };
  });
  const twins = pts.map(x => x.vt).filter(Boolean);
  let floor = null, ds = [];
  for (let i = 0; i < twins.length; i++) for (let jx = i + 1; jx < twins.length; jx++) {
    const d = cosDiv(twins[i], twins[jx]); if (d != null) ds.push(d);
  }
  if (ds.length) floor = ds.reduce((a, b) => a + b, 0) / ds.length;
  const cv = $('#curves'), ctx = cv.getContext('2d');
  ctx.clearRect(0, 0, cv.width, cv.height);
  const X = (i) => 30 + (i * (cv.width - 60)) / Math.max(1, pts.length - 1);
  const Y = (v) => cv.height - 20 - v * (cv.height - 40);
  if (floor != null) {                                        // bande de bruit ×2 (le seuil pré-enregistré)
    ctx.fillStyle = 'rgba(125,138,165,.18)';
    ctx.fillRect(30, Y(2 * floor), cv.width - 60, Y(0) - Y(2 * floor));
  }
  const series = [['div', '#7aa2ff'], ['app', '#4ade80'], ['dopa', '#ffb86b']];
  for (const [key, color] of series) {
    ctx.strokeStyle = color; ctx.lineWidth = 1.5; ctx.beginPath();
    let started = false;
    pts.forEach((x, i) => {
      if (x[key] == null) return;
      const px = X(i), py = Y(Math.max(0, Math.min(1, x[key])));
      started ? ctx.lineTo(px, py) : ctx.moveTo(px, py); started = true;
      ctx.fillStyle = color; ctx.fillRect(px - 1.5, py - 1.5, 3, 3);
    });
    ctx.stroke();
  }
}

loadList();
```

- [ ] **Step 3: Verify (Playwright ou curl + navigateur)**

```bash
curl -s localhost:4317/dreams.html | head -c 200      # la page est servie
open http://localhost:4317/dreams.html               # inspection visuelle
```

Expected: page rendue, « aucune nuit encore » tant que le daemon n'a pas rêvé (état honnête), aucune erreur console.

- [ ] **Step 4: Rapport + fin**

Compléter `~/AIOS/cockpit/.dreams-report.md` (fichiers créés, URL, limites : heatmap = 30 dernières nuits).

Côté anamnese, merger la branche :

```bash
cd ~/Desktop/anamnese && git checkout main && git merge --no-ff experience-reve \
  -m "Expérience-rêve : REM à choix libre + jumeau fantôme + métriques pré-enregistrées + CLI + hook Sonnet"
```

---

## Post-plan (hors code — rappels pour le contrôleur)

1. **Relancer le daemon** après RÊVE-1 (sinon les nuits ne comptent pas).
2. **Vérifier la 1re vraie nuit** : `sqlite3 data/memory.db "SELECT night_id, dreamer, substr(content,1,60) FROM dream_log"` + `./anamnese dreams` (verdict [INSUFFISANT] attendu — c'est NORMAL et honnête).
3. Premier verdict possible ~20 nuits (fin juillet). Ne pas conclure avant.
4. Si taux `parse_failed` > 30 % après ~5 nuits : revoir le prompt REM AVANT d'interpréter quoi que ce soit.
