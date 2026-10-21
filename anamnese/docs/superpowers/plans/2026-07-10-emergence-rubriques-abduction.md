# Émergence de rubriques depuis l'abduction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Après que l'abduction (Claude) a créé des insights, le cerveau cluster ses propres insights et, quand un cluster forme un thème neuf qu'aucune rubrique n'a, CRÉE une nouvelle rubrique (Claude seul, gardée) et y range ces insights.

**Architecture:** Nouveau module `rubric_emergence.py` (fonctions PURES + orchestration `emerge(mem, chat_fn)`), branché dans `synthesis_claude.run_claude` **après** la génération des insights. Deux gardes : sémantique (`covered`, distance centroïde) + structurelle (`valid_path`, path neuf sous parent existant). Visibilité cockpit : endpoint `/api/emerged` + panneau 🌱.

**Tech Stack:** Python 3.14 (.venv), SQLite, `embeddings.embed`, `rubrics.rubric_create/attach_episode`, cockpit Node (`~/AIOS/cockpit`). Tests pytest (fixtures `legacy_db`/`tmp_db` de `conftest.py`).

## Global Constraints

- **Claude UNIQUEMENT crée des rubriques** : `emerge` appelée depuis `synthesis_claude.run_claude`, JAMAIS depuis la passe locale 9B (`daemon._synthesis_pass`).
- **Deux gardes non-négociables** : (1) sémantique — cluster dont le centroïde est à cosinus ≥ `RUBRIC_EMERGE_REDUNDANCY_FLOOR` d'une rubrique existante → PAS de création ; (2) structurelle — `valid_path` : path NEUF, niché sous un parent EXISTANT (jamais un nouveau root), segments kebab-case `^[a-z0-9-]+$`, profondeur ≤ `config.RUBRIC_MAX_DEPTH` (=3).
- **Seuils gravés (exacts)** : `RUBRIC_EMERGE_ENABLED` (env `ANAMNESE_RUBRIC_EMERGE`, défaut `"1"`→True), `RUBRIC_EMERGE_MIN_INSIGHTS=3`, `RUBRIC_EMERGE_SIM=0.50`, `RUBRIC_EMERGE_REDUNDANCY_FLOOR=0.60`.
- **Best-effort partout** : aucune étape ne doit lever ni bloquer `run_claude` / le rêve / la consolidation.
- **kind_hint='emerged'** sur les rubriques créées (repérables pour le cockpit + réversibilité).
- **Ne PAS casser** : routage LIVE (`mem.add`), coactivation, ablation (portes A/B/C), `synthesis.run`, portes 2026-07-03. Les tests existants `tests/test_synthesis_claude.py`, `tests/test_rubrics.py`, `tests/test_synthesis_*.py` doivent rester verts.
- **Zéro `claude -p` réel au build** : orchestration + hook testés `chat_fn` mockée.
- Réutilise le cosinus partagé `synthesis._cos` (pas de réimplémentation).

## File Structure

- **Create** `rubric_emergence.py` — pur (`_centroid`, `_cluster`, `covered`, `valid_path`, `parse_path`) + face-modèle (`propose_path`) + orchestration (`emerge`, helpers I/O).
- **Modify** `config.py` — 4 constantes `RUBRIC_EMERGE_*` après le bloc `SYNTH_*` (ligne ~242).
- **Modify** `synthesis_claude.py` — `run_claude` appelle `rubric_emergence.emerge` après `synthesis.run`.
- **Modify** `~/AIOS/cockpit/server.js` — endpoint `/api/emerged`.
- **Modify** `~/AIOS/cockpit/public/dreams.html` — section 🌱 (`#emerged-card` + `#emerged`).
- **Modify** `~/AIOS/cockpit/public/dreams.js` — `loadEmerged()` (fetch + rendu).
- **Create tests** `tests/test_rubric_emergence_pure.py`, `tests/test_rubric_emergence_propose.py`, `tests/test_rubric_emergence_emerge.py`, `tests/test_synthesis_claude_emergence.py`.

---

### Task 1: Config — seuils d'émergence

**Files:**
- Modify: `config.py` (après ligne 242, fin du bloc `SYNTH_*`)
- Test: `tests/test_rubric_emergence_pure.py` (bloc config en tête)

**Interfaces:**
- Produces: `config.RUBRIC_EMERGE_ENABLED: bool`, `config.RUBRIC_EMERGE_MIN_INSIGHTS: int`, `config.RUBRIC_EMERGE_SIM: float`, `config.RUBRIC_EMERGE_REDUNDANCY_FLOOR: float`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_rubric_emergence_pure.py
import config

def test_emerge_config_values():
    assert config.RUBRIC_EMERGE_MIN_INSIGHTS == 3
    assert config.RUBRIC_EMERGE_SIM == 0.50
    assert config.RUBRIC_EMERGE_REDUNDANCY_FLOOR == 0.60
    assert config.RUBRIC_EMERGE_ENABLED in (True, False)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_pure.py::test_emerge_config_values -v`
Expected: FAIL with `AttributeError: module 'config' has no attribute 'RUBRIC_EMERGE_MIN_INSIGHTS'`

- [ ] **Step 3: Add the constants**

In `config.py`, immediately after the `SYNTH_COACT_BOOST` line (~242), add:

```python
# --- Émergence de rubriques depuis l'abduction (Claude seul, gardée) ---
RUBRIC_EMERGE_ENABLED          = os.environ.get("ANAMNESE_RUBRIC_EMERGE", "1") == "1"
RUBRIC_EMERGE_MIN_INSIGHTS     = 3      # taille minimale d'un cluster d'insights
RUBRIC_EMERGE_SIM              = 0.50   # tightness du cluster (cosinus graine↔membre)
RUBRIC_EMERGE_REDUNDANCY_FLOOR = 0.60   # couvert par une rubrique existante si cosinus centroïde ≥ ça
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_pure.py::test_emerge_config_values -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add config.py tests/test_rubric_emergence_pure.py
git commit -m "feat(emerge): seuils config RUBRIC_EMERGE_*"
```

---

### Task 2: `rubric_emergence.py` — fonctions PURES

**Files:**
- Create: `rubric_emergence.py`
- Test: `tests/test_rubric_emergence_pure.py`

**Interfaces:**
- Consumes: `synthesis._cos`, `config.RUBRIC_MAX_DEPTH`.
- Produces:
  - `_centroid(embs: list[list[float]]) -> list[float]` (moyenne ; `[]` si vide)
  - `_cluster(items: list[tuple[int,list[float]]], min_size: int, sim: float) -> list[list[int]]`
  - `covered(cluster_centroid: list[float], rubric_centroids: list[list[float]], floor: float) -> bool`
  - `valid_path(path: str, existing_paths: set[str]) -> bool`
  - `parse_path(out: str|None) -> str|None`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_rubric_emergence_pure.py`:

```python
import rubric_emergence as RE

def test_centroid_mean():
    assert RE._centroid([[2.0, 0.0], [0.0, 2.0]]) == [1.0, 1.0]
    assert RE._centroid([]) == []

def test_cluster_groups_tight_and_drops_below_min():
    items = [(1, [1, 0]), (2, [0.99, 0.01]), (3, [0.98, 0.02]), (4, [0, 1])]
    cl = RE._cluster(items, min_size=3, sim=0.9)
    assert len(cl) == 1 and set(cl[0]) == {1, 2, 3}   # 4 (axe y) exclu

def test_cluster_below_min_returns_empty():
    assert RE._cluster([(1, [1, 0]), (2, [0.99, 0.01])], min_size=3, sim=0.9) == []

def test_covered_true_when_near_existing():
    assert RE.covered([1, 0], [[0.95, 0.05]], floor=0.6) is True

def test_covered_false_when_far():
    assert RE.covered([1, 0], [[0, 1]], floor=0.6) is False

def test_covered_skips_empty_centroids():
    assert RE.covered([1, 0], [[], [0, 1]], floor=0.6) is False

def test_valid_path_accepts_new_child_of_existing_parent():
    assert RE.valid_path("projets/anamnese/nouveau", {"projets", "projets/anamnese"}) is True

def test_valid_path_rejects_existing_path():
    assert RE.valid_path("projets/anamnese", {"projets", "projets/anamnese"}) is False

def test_valid_path_rejects_new_root():
    assert RE.valid_path("nouveauroot", {"projets"}) is False

def test_valid_path_rejects_missing_parent():
    assert RE.valid_path("projets/absent/x", {"projets"}) is False

def test_valid_path_rejects_non_kebab():
    assert RE.valid_path("projets/Anamnese_X", {"projets"}) is False

def test_valid_path_rejects_too_deep():
    existing = {"a", "a/b", "a/b/c", "a/b/c/d"}
    assert RE.valid_path("a/b/c/d/e", existing) is False   # count('/')=4 > RUBRIC_MAX_DEPTH=3

def test_parse_path_extracts_kebab():
    assert RE.parse_path("projets/anamnese/mon-theme") == "projets/anamnese/mon-theme"

def test_parse_path_none_on_none_or_empty():
    assert RE.parse_path("NONE") is None
    assert RE.parse_path("") is None
    assert RE.parse_path(None) is None

def test_parse_path_strips_think_and_prose():
    assert RE.parse_path("<think>hmm</think>\nVoici: projets/anamnese/x") == "projets/anamnese/x"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_pure.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'rubric_emergence'`

- [ ] **Step 3: Create the pure core**

Create `rubric_emergence.py`:

```python
"""rubric_emergence.py — Émergence de rubriques depuis l'abduction.

Quand un CLUSTER d'insights (role='insight') forme un thème neuf qu'AUCUNE rubrique
existante ne couvre, le cerveau CRÉE une nouvelle rubrique (Claude seul) et y range
ces insights. Croissance DÉLIBÉRÉE : deux gardes — sémantique (covered, distance
centroïde) et structurelle (valid_path, path neuf sous parent existant, kebab-case).
Fonctions pures en tête (stdlib), orchestration + I/O ensuite."""
import json as _json
import re
import time

import config
import embeddings
import rubrics
from synthesis import _cos   # cosinus partagé (une seule implémentation)

# ---------- pur ----------

def _centroid(embs):
    """Moyenne (centroïde) d'une liste d'embeddings de même dimension. [] si vide."""
    if not embs:
        return []
    n = len(embs)
    dim = len(embs[0])
    return [sum(e[i] for e in embs) / n for i in range(dim)]


def _cluster(items, min_size, sim):
    """items=[(id, emb)] → clusters d'ids (glouton, déterministe dans l'ordre d'entrée).
    Chaque item rejoint le 1er cluster dont la GRAINE (1er membre) est à cosinus ≥ sim ;
    sinon il ouvre son propre cluster. Ne garde que les clusters de taille ≥ min_size."""
    clusters = []   # [(seed_emb, [ids])]
    for eid, emb in items:
        placed = False
        for seed, ids in clusters:
            if _cos(emb, seed) >= sim:
                ids.append(eid)
                placed = True
                break
        if not placed:
            clusters.append((emb, [eid]))
    return [ids for _seed, ids in clusters if len(ids) >= min_size]


def covered(cluster_centroid, rubric_centroids, floor):
    """Garde SÉMANTIQUE : True si le centroïde du cluster est à cosinus ≥ floor d'AU
    MOINS un centroïde de rubrique existante (thème déjà couvert → pas de création).
    Les centroïdes vides ([]) sont ignorés."""
    return any(_cos(cluster_centroid, rc) >= floor for rc in rubric_centroids if rc)


def valid_path(path, existing_paths):
    """Garde STRUCTURELLE : (a) path NEUF (pas dans existing_paths) ; (b) niché sous un
    parent EXISTANT (contient un '/', parent ∈ existing_paths — jamais un nouveau root) ;
    (c) segments kebab-case ^[a-z0-9-]+$ ; (d) profondeur ≤ config.RUBRIC_MAX_DEPTH."""
    if not path or path in existing_paths:
        return False
    if path.startswith("/") or path.endswith("/") or "/" not in path:
        return False
    if path.count("/") > config.RUBRIC_MAX_DEPTH:
        return False
    if not all(re.fullmatch(r"[a-z0-9-]+", s) for s in path.split("/")):
        return False
    return path.rsplit("/", 1)[0] in existing_paths


def parse_path(out):
    """Extrait le path kebab-case proposé (1re ligne contenant a/b-c), None si NONE/vide."""
    if not out:
        return None
    t = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I).strip()
    if not t or re.match(r"(?i)^\W*none\b", t):
        return None
    for line in t.splitlines():
        m = re.search(r"[a-z0-9-]+(?:/[a-z0-9-]+)+", line.strip().lower())
        if m:
            return m.group(0)
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_pure.py -v`
Expected: PASS (all)

- [ ] **Step 5: Commit**

```bash
git add rubric_emergence.py tests/test_rubric_emergence_pure.py
git commit -m "feat(emerge): fonctions pures (cluster, gardes covered/valid_path, parse_path)"
```

---

### Task 3: `propose_path` — nommage Claude (chat_fn mockée)

**Files:**
- Modify: `rubric_emergence.py` (ajoute `_propose_prompt` + `propose_path`)
- Test: `tests/test_rubric_emergence_propose.py`

**Interfaces:**
- Consumes: `parse_path` (Task 2).
- Produces: `propose_path(chat_fn, insight_texts: list[str], existing_paths: set[str]) -> str|None`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rubric_emergence_propose.py
import rubric_emergence as RE

def test_propose_path_returns_parsed_path():
    seen = {}
    def fake(prompt):
        seen["p"] = prompt
        return "projets/anamnese/mon-theme"
    p = RE.propose_path(fake, ["insight alpha", "insight beta"], {"projets", "projets/anamnese"})
    assert p == "projets/anamnese/mon-theme"
    assert "insight alpha" in seen["p"] and "projets/anamnese" in seen["p"]

def test_propose_path_none_when_model_says_none():
    assert RE.propose_path(lambda p: "NONE", ["x"], {"projets"}) is None

def test_propose_path_none_on_chat_error():
    def boom(p):
        raise RuntimeError("backend down")
    assert RE.propose_path(boom, ["x"], {"projets"}) is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_propose.py -v`
Expected: FAIL with `AttributeError: module 'rubric_emergence' has no attribute 'propose_path'`

- [ ] **Step 3: Add the face-model function**

Append to `rubric_emergence.py` (after `parse_path`, before the I/O section):

```python
# ---------- étape face-modèle (chat_fn injectable) ----------

def _propose_prompt(insight_texts, existing_paths):
    lst = "\n".join(f"- {t}" for t in insight_texts)
    ex = ", ".join(sorted(existing_paths)) or "(aucune)"
    return (
        "Voici un groupe d'insights liés (hypothèses nées de rapprochements de souvenirs) :\n"
        f"{lst}\n\n"
        "Forment-ils un THÈME NEUF qu'AUCUNE de ces rubriques existantes ne couvre ?\n"
        f"Rubriques existantes : {ex}\n\n"
        "Si OUI : réponds UNIQUEMENT par UN chemin kebab-case NEUF, niché sous un PARENT "
        "EXISTANT ci-dessus (ex. projets/anamnese/nom-du-theme). PAS de nouveau niveau racine.\n"
        "Si NON (ça rentre dans une rubrique existante) : réponds NONE.")


def propose_path(chat_fn, insight_texts, existing_paths):
    """Claude nomme un path kebab-case NEUF sous un parent existant, ou None (NONE/erreur)."""
    try:
        out = chat_fn(_propose_prompt(insight_texts, existing_paths))
    except Exception:
        return None
    return parse_path(out)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_propose.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add rubric_emergence.py tests/test_rubric_emergence_propose.py
git commit -m "feat(emerge): propose_path (nommage Claude, chat_fn injectable)"
```

---

### Task 4: `emerge` — orchestration (DB migrée + chat_fn mockée)

**Files:**
- Modify: `rubric_emergence.py` (ajoute helpers I/O + `emerge`)
- Test: `tests/test_rubric_emergence_emerge.py`

**Interfaces:**
- Consumes: `_cluster`, `_centroid`, `covered`, `valid_path`, `propose_path` (Tasks 2-3) ; `rubrics.rubric_create(conn, path, now, kind_hint=...)`, `rubrics.attach_episode(conn, episode_id, path, conf, now)`, `rubrics._parse_embedding`, `config.RUBRIC_EMERGE_*`.
- Produces: `emerge(mem, chat_fn) -> list[str]` (paths créés), helpers `_load_recent_insights(mem)`, `_load_rubric_state(mem)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_rubric_emergence_emerge.py
import json
import pytest

import config
import migrations
import rubrics
import rubric_emergence as RE


class FakeMem:
    def __init__(self, conn):
        self.db = conn


@pytest.fixture
def db(legacy_db):
    migrations.migrate(legacy_db)   # rubrics + insight_edges prêts
    return legacy_db


def _mk_rubric(conn, path, centroid=None):
    rubrics.rubric_create(conn, path, 1000.0)
    if centroid is not None:
        conn.execute("UPDATE rubrics SET centroid=?, centroid_n=1 WHERE path=?",
                     (json.dumps(centroid), path))
        conn.commit()


def _mk_insight(conn, emb, content="(insight·claude) hypothèse"):
    cur = conn.execute(
        "INSERT INTO episodes (ts, role, content, importance, embedding) "
        "VALUES (1000.0, 'insight', ?, 0.5, ?)", (content, json.dumps(emb)))
    conn.commit()
    return cur.lastrowid


def test_emerge_creates_rubric_for_novel_cluster(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "autre", centroid=[0.0, 1.0, 0.0])   # LOIN du cluster (axe y)
    ids = [_mk_insight(db, [1.0, 0.0, 0.0]),
           _mk_insight(db, [0.98, 0.02, 0.0]),
           _mk_insight(db, [0.97, 0.03, 0.0])]
    created = RE.emerge(FakeMem(db), lambda p: "projets/anamnese/pouw-graphify")
    assert created == ["projets/anamnese/pouw-graphify"]
    row = db.execute("SELECT id, kind_hint FROM rubrics WHERE path=?",
                     ("projets/anamnese/pouw-graphify",)).fetchone()
    assert row is not None and row[1] == "emerged"
    rid = row[0]
    for i in ids:
        assert db.execute("SELECT rubric_id FROM episodes WHERE id=?", (i,)).fetchone()[0] == rid


def test_emerge_skips_when_theme_already_covered(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "proche", centroid=[1.0, 0.0, 0.0])   # TRÈS proche du cluster
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    created = RE.emerge(FakeMem(db), lambda p: "projets/anamnese/x")
    assert created == []
    assert db.execute("SELECT COUNT(*) FROM rubrics WHERE kind_hint='emerged'").fetchone()[0] == 0


def test_emerge_no_creation_below_min(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_insight(db, [1.0, 0.0, 0.0])
    _mk_insight(db, [0.98, 0.02, 0.0])   # seulement 2 < MIN_INSIGHTS
    assert RE.emerge(FakeMem(db), lambda p: "projets/anamnese/x") == []


def test_emerge_rejects_invalid_path_from_model(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "autre", centroid=[0.0, 1.0, 0.0])
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    # le modèle propose un NOUVEAU ROOT (interdit par valid_path) → rien créé
    assert RE.emerge(FakeMem(db), lambda p: "nouveauroot") == []
    assert db.execute("SELECT COUNT(*) FROM rubrics WHERE kind_hint='emerged'").fetchone()[0] == 0


def test_emerge_respects_killswitch(db, monkeypatch):
    monkeypatch.setattr(config, "RUBRIC_EMERGE_ENABLED", False)
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    assert RE.emerge(FakeMem(db), lambda p: "projets/anamnese/x") == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_emerge.py -v`
Expected: FAIL with `AttributeError: module 'rubric_emergence' has no attribute 'emerge'`

- [ ] **Step 3: Add the orchestration**

Append to `rubric_emergence.py`:

```python
# ---------- orchestration (lecture + écriture sur mem.db, best-effort) ----------

def _load_recent_insights(mem):
    """(id, emb, text) des insights embeddés PAS déjà dans une rubrique 'emerged'
    (évite de re-traiter un insight déjà rangé par une émergence précédente)."""
    rows = mem.db.execute(
        "SELECT e.id, e.embedding, e.content FROM episodes e "
        "LEFT JOIN rubrics r ON r.id = e.rubric_id "
        "WHERE e.role='insight' AND e.embedding IS NOT NULL AND e.embedding != '[]' "
        "AND (r.kind_hint IS NULL OR r.kind_hint != 'emerged')").fetchall()
    out = []
    for eid, emb, content in rows:
        try:
            v = _json.loads(emb)
        except Exception:
            continue
        if v:
            out.append((eid, v, content or ""))
    return out


def _load_rubric_state(mem):
    """(existing_paths: set, rubric_centroids: list) de TOUTES les rubriques existantes."""
    paths, cents = set(), []
    for path, cent in mem.db.execute("SELECT path, centroid FROM rubrics"):
        paths.add(path)
        v = rubrics._parse_embedding(cent)
        if v:
            cents.append(v)
    return paths, cents


def emerge(mem, chat_fn):
    """Insights récents → clusters → cluster non-couvert → Claude nomme → gardes →
    rubric_create(kind_hint='emerged') + rattache les insights. Best-effort.
    Retourne la liste des paths créés."""
    if not config.RUBRIC_EMERGE_ENABLED:
        return []
    created = []
    try:
        insights = _load_recent_insights(mem)
        clusters = _cluster([(i, e) for i, e, _t in insights],
                            config.RUBRIC_EMERGE_MIN_INSIGHTS, config.RUBRIC_EMERGE_SIM)
        if not clusters:
            return created
        by_id = {i: (e, t) for i, e, t in insights}
        existing_paths, rubric_cents = _load_rubric_state(mem)
    except Exception:
        return created
    now = time.time()
    for ids in clusters:
        try:
            cent = _centroid([by_id[i][0] for i in ids])
            if covered(cent, rubric_cents, config.RUBRIC_EMERGE_REDUNDANCY_FLOOR):
                continue                                     # garde sémantique
            path = propose_path(chat_fn, [by_id[i][1] for i in ids], existing_paths)
            if not path or not valid_path(path, existing_paths):
                continue                                     # garde structurelle
            rubrics.rubric_create(mem.db, path, now, kind_hint="emerged")
            for i in ids:
                rubrics.attach_episode(mem.db, i, path, 0.9, now)
            created.append(path)
            existing_paths.add(path)                         # anti-doublon intra-run
        except Exception:
            continue
    return created
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_rubric_emergence_emerge.py -v`
Expected: PASS (all 5)

- [ ] **Step 5: Run the whole rubrics suite (no regression)**

Run: `.venv/bin/python -m pytest tests/test_rubrics.py tests/test_rubric_emergence_pure.py tests/test_rubric_emergence_propose.py tests/test_rubric_emergence_emerge.py -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add rubric_emergence.py tests/test_rubric_emergence_emerge.py
git commit -m "feat(emerge): orchestration emerge (gardes + rubric_create + attach, best-effort)"
```

---

### Task 5: Hook Claude — `synthesis_claude.run_claude`

**Files:**
- Modify: `synthesis_claude.py` (import + `run_claude`)
- Test: `tests/test_synthesis_claude_emergence.py`

**Interfaces:**
- Consumes: `rubric_emergence.emerge` (Task 4), `synthesis.run`.
- Produces: `run_claude(mem, run_fn=None) -> list` (inchangé : retourne les insight_ids ; déclenche l'émergence après).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synthesis_claude_emergence.py
import synthesis_claude as SC
import synthesis
import rubric_emergence


def test_run_claude_triggers_emergence_after_synthesis(monkeypatch):
    order = []
    monkeypatch.setattr(synthesis, "run", lambda *a, **k: order.append("run") or [10, 11])
    monkeypatch.setattr(rubric_emergence, "emerge",
                        lambda mem, chat: order.append("emerge") or ["projets/x/y"])
    ids = SC.run_claude(mem=object(), run_fn=lambda p: "x")
    assert ids == [10, 11]            # retour inchangé (insight_ids)
    assert order == ["run", "emerge"]  # émergence APRÈS la synthèse


def test_run_claude_emergence_is_best_effort(monkeypatch):
    monkeypatch.setattr(synthesis, "run", lambda *a, **k: [7])
    def boom(mem, chat):
        raise RuntimeError("emergence cassée")
    monkeypatch.setattr(rubric_emergence, "emerge", boom)
    assert SC.run_claude(mem=object(), run_fn=lambda p: "x") == [7]   # ne lève pas
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_synthesis_claude_emergence.py -v`
Expected: FAIL (`order == ["run"]`, émergence pas déclenchée)

- [ ] **Step 3: Wire the hook**

In `synthesis_claude.py`, add `import rubric_emergence` at the top (after `import synthesis`), and replace `run_claude` with:

```python
def run_claude(mem, run_fn=None):
    """Synthèse via Claude sur le top-N des paires fertiles, PUIS émergence de rubriques
    (Claude seul, gardée). run_fn injectable (test). Retourne les insight_ids créés."""
    chat = run_fn or claude_chat
    ids = synthesis.run(mem, chat, "claude", config.SYNTH_CLAUDE_TOPN,
                        n_samples=1, n_skeptics=2)
    try:
        rubric_emergence.emerge(mem, chat)   # crée des rubriques si des insights font thème neuf
    except Exception as e:
        print("[synthese-claude] émergence échouée:", e)
    return ids
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_synthesis_claude_emergence.py tests/test_synthesis_claude.py -v`
Expected: PASS (nouveaux + les 2 existants inchangés)

- [ ] **Step 5: Commit**

```bash
git add synthesis_claude.py tests/test_synthesis_claude_emergence.py
git commit -m "feat(emerge): run_claude déclenche l'émergence de rubriques après la synthèse"
```

---

### Task 6: Cockpit — endpoint `/api/emerged` + panneau 🌱

**Files:**
- Modify: `~/AIOS/cockpit/server.js` (nouvel endpoint, à côté de `/api/insights` ~ligne 458)
- Modify: `~/AIOS/cockpit/public/dreams.html` (section 🌱 après `#insights-card`)
- Modify: `~/AIOS/cockpit/public/dreams.js` (fonction `loadEmerged`)

**Interfaces:**
- Consumes: table `rubrics` (`kind_hint='emerged'`), `episodes` (`role='insight'`, `rubric_id`), helper `sqlite(query)` existant.
- Produces: `GET /api/emerged` → `{emerged:[{path, label, n_insights, sample}]}`.

- [ ] **Step 1: Add the endpoint**

In `~/AIOS/cockpit/server.js`, immediately after the `/api/insights` block (`return res.end(j({ insights: out }));` then its closing `}`), add:

```javascript
  if (p === '/api/emerged') {
    // Rubriques NÉES de l'abduction (kind_hint='emerged') — LECTURE SEULE.
    const rows = await sqlite(
      "SELECT r.path, r.label, " +
      "(SELECT COUNT(*) FROM episodes e WHERE e.rubric_id = r.id AND e.role='insight') AS n_insights, " +
      "(SELECT substr(replace(e.content, char(10), ' '), 1, 120) FROM episodes e " +
      " WHERE e.rubric_id = r.id AND e.role='insight' ORDER BY e.ts DESC LIMIT 1) AS sample " +
      "FROM rubrics r WHERE r.kind_hint='emerged' ORDER BY r.created_ts DESC LIMIT 40;");
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(j({ emerged: rows || [] }));
  }
```

- [ ] **Step 2: Verify server.js parses**

Run: `node --check ~/AIOS/cockpit/server.js`
Expected: no output (exit 0)

- [ ] **Step 3: Add the panel to dreams.html**

In `~/AIOS/cockpit/public/dreams.html`, immediately after the `#insights-card` section (closing `</section>` at line ~59), add:

```html
<section class="glass accent" id="emerged-card" style="margin-bottom:12px;">
  <div class="sec-label">🌱 RUBRIQUES ÉMERGÉES <span class="dim">· catégories nées de l'abduction · rubric_emergence</span></div>
  <div id="emerged"><div class="dim">chargement…</div></div>
</section>
```

- [ ] **Step 4: Add the loader to dreams.js**

In `~/AIOS/cockpit/public/dreams.js`, mirror the insights loader (the block that ends near line 188). Add this function and call it where the insights loader is invoked:

```javascript
async function loadEmerged() {
  try {
    const d = await (await fetch('/api/emerged')).json();
    const items = d.emerged || [];
    document.getElementById('emerged').innerHTML = items.length ? items.map(it =>
      `<div class="row" style="padding:6px 0;border-bottom:1px solid var(--line);">
         <span class="badge">🌱 ${esc(it.path)}</span>
         <span class="dim" style="margin-left:8px;">${it.n_insights} insight(s)</span>
         <div class="dim" style="font-size:11px;margin-top:3px;">${esc(it.sample || '')}</div>
       </div>`).join('')
      : '<div class="dim">aucune rubrique émergée pour l\'instant</div>';
  } catch (_) { document.getElementById('emerged').innerHTML = '<div class="dim">(indisponible)</div>'; }
}
loadEmerged();
```

(Place the `loadEmerged();` call next to the existing insights-loader invocation so it runs on page load. Use the same `esc()` helper already defined in `dreams.js`.)

- [ ] **Step 5: Verify + smoke-test live**

Run: `node --check ~/AIOS/cockpit/public/dreams.js && curl -s -m 8 http://localhost:4317/api/emerged`
Expected: `node --check` exits 0 ; curl returns `{"emerged":[...]}` (may be `[]` if no emerged rubric yet — valid).

- [ ] **Step 6: Commit** (cockpit is a separate repo/dir — commit there if it's git-tracked, else note the change)

```bash
cd ~/AIOS/cockpit && git add server.js public/dreams.html public/dreams.js 2>/dev/null && git commit -m "feat(cockpit): panneau 🌱 rubriques émergées + /api/emerged" 2>/dev/null || echo "cockpit non git — changements en place"
```

---

## Self-Review (plan vs spec)

- **Spec coverage** : émergence Claude-seule (Task 5 hook, jamais 9B) ✓ ; garde sémantique `covered` (Task 2/4) ✓ ; garde structurelle `valid_path` neuf+parent+kebab+profondeur (Task 2/4) ✓ ; kind_hint='emerged' (Task 4) ✓ ; seuils gravés (Task 1) ✓ ; visibilité `/api/emerged` + 🌱 (Task 6) ✓ ; réversibilité (kind_hint + taxonomy_undo, hors code) ✓.
- **Placeholders** : aucun — chaque étape porte le code réel.
- **Type consistency** : `emerge(mem, chat_fn)->list[str]`, `covered(..., floor)->bool`, `valid_path(path, existing_paths)->bool`, `parse_path(out)->str|None` — cohérents Tasks 2→4→5.
- **Non-régression** : Task 4 Step 5 (suite rubrics) + Task 5 Step 4 (test_synthesis_claude existant) verrouillent les portes.
