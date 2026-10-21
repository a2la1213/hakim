# Moteur de liens génératifs — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Faire évoluer la mémoire d'associative (coactivation hebbienne) vers abductive : générer et stocker des hypothèses NEUVES nées de la combinaison de souvenirs distants, en local (Ollama 9B, gratuit) avec Claude en escalade optionnelle.

**Architecture:** Un cœur `synthesis.py` agnostique au modèle (`chat_fn` injectable) : sélection-code des paires fertiles → génération abductive → ancrage-embedding → vérification adversariale (meute) → score → stockage 1re classe (`role="insight"` + table `insight_edges` + rétroaction coactivation). Étage local (daemon 9B), étage Claude (`synthesis_claude.py`), cockpit (panneau Insights).

**Tech Stack:** Python 3.14 (.venv), SQLite, `engine.chat` (Ollama), `embeddings.embed` (256-dim), `claude -p` (backend Claude optionnel, mocké au build), cockpit Node.

## Global Constraints

- **Offline 100%** : le cœur (local) ne dépend jamais de Claude/réseau. `synthesis.run(mem, chat_fn, backend, ...)` prend un `chat_fn(prompt)->str` injectable.
- **Anti-slop non-négociable** : ancrage-embedding + vérification adversariale (majorité de sceptiques). Le crible est le cœur de la valeur.
- **Ne PAS casser** : `coactivation` (couche associative), le rêve ON/twin, l'ablation (portes A/B/C), les portes 2026-07-03.
- **Kill-switch** : `config.SYNTHESIS_ENABLED` (env `ANAMNESE_SYNTHESIS`, défaut on).
- **Seuils gravés** : `SYNTH_MID_LO=0.35`, `SYNTH_MID_HI=0.60`, `SYNTH_LOCAL_BATCH=20`, `SYNTH_CLAUDE_TOPN=5`, `SYNTH_SAMPLES=3`, `SYNTH_SKEPTICS=5`, `SYNTH_REFUTE_KILL=3`, `SYNTH_GROUNDING_FLOOR=0.30`, `SYNTH_NOVELTY_MIN=0.15`, `SYNTH_COACT_BOOST=0.05`.
- **Backend = préfixe du contenu** (`(insight·local)` / `(insight·claude)`) ; nouveauté recalculée à la lecture ; pas de colonne meta ajoutée.
- **Zéro `claude -p` au build** : le backend Claude est testé via `chat_fn` mockée.
- Tests : `.venv/bin/python -m pytest` ; fixtures `tmp_db`/`legacy_db` ; guard autouse interdit `data/memory.db`.

## File Structure
- `migrations.py` (modify) — table `insight_edges` + index.
- `synthesis.py` (create) — cœur agnostique (pur + orchestration).
- `config.py` (modify) — `SYNTHESIS_ENABLED` + `SYNTH_*`.
- `daemon.py` (modify) — `_synthesis_pass` + hook dans `dream()`.
- `synthesis_claude.py` (create) — backend Claude (budget, main d'Ahmed).
- `~/AIOS/cockpit/server.js` + `public/` (modify) — endpoint `/api/insights` + panneau.
- Tests : `tests/test_insight_migration.py`, `tests/test_synthesis_pure.py`, `tests/test_synthesis_select.py`, `tests/test_synthesis_genverify.py`, `tests/test_synthesis_run.py`, `tests/test_synthesis_pass.py`, `tests/test_synthesis_claude.py`.

---

### Task 1: Migration `insight_edges`

**Files:**
- Modify: `migrations.py` (ajouter à `NEW_TABLES_SQL` et `INDEXES_SQL`)
- Test: `tests/test_insight_migration.py`

**Interfaces:**
- Consumes: `migrations.migrate(conn)` (existant), `migrations._table_exists` (existant).
- Produces: table `insight_edges(insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id))` + index `idx_insight_src`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_insight_migration.py
import migrations

def test_migrate_creates_insight_edges(tmp_db):
    migrations.migrate(tmp_db)
    cols = [r[1] for r in tmp_db.execute("PRAGMA table_info(insight_edges)")]
    assert cols == ["insight_id", "source_id"]
    # idempotent : re-migrer ne casse pas
    migrations.migrate(tmp_db)
    idx = [r[0] for r in tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='insight_edges'")]
    assert any("idx_insight_src" in n for n in idx)

def test_insight_edges_pk_dedup(tmp_db):
    migrations.migrate(tmp_db)
    tmp_db.execute("INSERT INTO insight_edges VALUES (1, 2)")
    tmp_db.execute("INSERT OR IGNORE INTO insight_edges VALUES (1, 2)")  # doublon ignoré (PK)
    tmp_db.commit()
    assert tmp_db.execute("SELECT COUNT(*) FROM insight_edges").fetchone()[0] == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_insight_migration.py -q`
Expected: FAIL (table `insight_edges` inexistante).

- [ ] **Step 3: Add the table + index**

Dans `migrations.py`, ajouter dans `NEW_TABLES_SQL` (avant le `]` de fin, ~ligne 147) :

```python
    (
        # Liens GÉNÉRATIFS (synthèse abductive) : arête TYPÉE d'un insight vers
        # chaque souvenir source qui l'a enfanté. Couche distincte de coactivation
        # (associatif) — ici l'arête SIGNIFIE « cet insight est né de ces mémoires ».
        "insight_edges",
        """
        CREATE TABLE IF NOT EXISTS insight_edges (
            insight_id INTEGER NOT NULL,
            source_id  INTEGER NOT NULL,
            PRIMARY KEY (insight_id, source_id)
        )
        """,
    ),
```

Et dans `INDEXES_SQL` (~ligne 170) :

```python
    ("insight_edges", "CREATE INDEX IF NOT EXISTS idx_insight_src ON insight_edges(source_id)"),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_insight_migration.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations.py tests/test_insight_migration.py
git commit -m "feat(synthese): migration table insight_edges (liens génératifs typés)"
```

---

### Task 2: Config `SYNTH_*` + `synthesis.py` fonctions PURES

**Files:**
- Modify: `config.py` (constantes `SYNTHESIS_ENABLED` + `SYNTH_*`)
- Create: `synthesis.py`
- Test: `tests/test_synthesis_pure.py`

> **IMPORTANT (ordre) :** les constantes `config.SYNTH_*` doivent exister DÈS cette tâche,
> car les tâches suivantes (T3–T5) les utilisent comme défauts d'arguments (évalués à
> l'import de `synthesis.py`). On les ajoute donc ici, avant tout le reste.

**Files:**
- Test: `tests/test_synthesis_pure.py`

**Interfaces:**
- Produces (toutes PURES, stdlib `math`/`re`) :
  - `grounding_ok(insight_emb, emb_a, emb_b, floor) -> bool`
  - `novelty(insight_emb, existing_embs) -> float` (∈ [0,1])
  - `parse_hypothesis(out) -> str|None`
  - `parse_verdict(out) -> "REFUTE"|"VALIDE"|None`
  - `majority_kill(votes, n_refute_kill) -> bool`
  - `fertility_score(cos, cross_rubric, coact_weight) -> float`
  - `_cos(a, b) -> float` (helper)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synthesis_pure.py
import synthesis as S

def test_cos_and_grounding():
    a = [1.0, 0.0]; b = [0.0, 1.0]; mid = [1.0, 1.0]
    assert abs(S._cos(a, a) - 1.0) < 1e-9
    assert abs(S._cos(a, b)) < 1e-9
    assert S.grounding_ok(mid, a, b, floor=0.30) is True     # relié aux 2
    assert S.grounding_ok(a, a, b, floor=0.30) is False      # orthogonal à b

def test_novelty():
    v = [1.0, 0.0]
    assert S.novelty(v, []) == 1.0
    assert S.novelty(v, [[1.0, 0.0]]) == 0.0                 # identique = pas neuf
    assert S.novelty(v, [[0.0, 1.0]]) == 1.0                 # orthogonal = neuf

def test_parse_hypothesis():
    assert S.parse_hypothesis("NONE") is None
    assert S.parse_hypothesis("  none.  ") is None
    assert S.parse_hypothesis("") is None
    assert S.parse_hypothesis("Peut-être que X résout Y.") == "Peut-être que X résout Y."
    assert S.parse_hypothesis("<think>bla</think>Idée réelle.") == "Idée réelle."

def test_parse_verdict():
    assert S.parse_verdict("RÉFUTÉ : connexion forcée") == "REFUTE"
    assert S.parse_verdict("VALIDE, vrai pont") == "VALIDE"
    assert S.parse_verdict("je ne réfute pas, c'est VALIDE") == "VALIDE"   # dernier verdict
    assert S.parse_verdict("bla") is None

def test_majority_kill():
    assert S.majority_kill(["REFUTE","REFUTE","REFUTE","VALIDE","VALIDE"], 3) is True
    assert S.majority_kill(["REFUTE","REFUTE","VALIDE","VALIDE","VALIDE"], 3) is False

def test_fertility_score():
    central = S.fertility_score(0.475, True, 0.0)
    edge = S.fertility_score(0.60, True, 0.0)
    assert central > edge                                    # pic au centre de la bande
    assert S.fertility_score(0.475, True, 0.0) > S.fertility_score(0.475, False, 0.0)   # inter-rubriques
    assert S.fertility_score(0.475, True, 0.0) > S.fertility_score(0.475, True, 0.5)    # déjà co-activé pénalisé
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_synthesis_pure.py -q`
Expected: FAIL (`ModuleNotFoundError: synthesis`).

- [ ] **Step 3a: Add config constants** (avant `synthesis.py`, car T3–T5 en dépendent à l'import)

Dans `config.py`, à la fin des constantes `DREAM_*`/`DREAM_ABL_*` :

```python
# --- Moteur de liens génératifs (synthèse abductive, 2026-07-09) ---
SYNTHESIS_ENABLED   = os.environ.get("ANAMNESE_SYNTHESIS", "1") == "1"
SYNTH_MID_LO        = 0.35
SYNTH_MID_HI        = 0.60
SYNTH_LOCAL_BATCH   = 20
SYNTH_CLAUDE_TOPN   = 5
SYNTH_SAMPLES       = 3
SYNTH_SKEPTICS      = 5
SYNTH_REFUTE_KILL   = 3
SYNTH_GROUNDING_FLOOR = 0.30
SYNTH_NOVELTY_MIN   = 0.15
SYNTH_COACT_BOOST   = 0.05
```

- [ ] **Step 3b: Implement the pure functions**

```python
"""synthesis.py — Moteur de liens génératifs (synthèse abductive).
Cœur AGNOSTIQUE au modèle : chat_fn(prompt)->str injectable (9B local OU claude -p).
L'intelligence vit dans l'orchestration (sélection-code + crible adversarial), pas
dans le modèle. Fonctions pures en tête (stdlib), orchestration + I/O ensuite."""
import math
import re
import time

import config

# ---------- pur ----------

def _cos(a, b):
    dot = sum(x * y for x, y in zip(a, b))
    na = math.sqrt(sum(x * x for x in a)); nb = math.sqrt(sum(y * y for y in b))
    return dot / (na * nb) if na and nb else 0.0


def grounding_ok(insight_emb, emb_a, emb_b, floor):
    """L'insight est-il relié en EMBEDDING aux DEUX sources (≥ floor) ? Ancrage
    sémantique, pas lexical (une vraie synthèse reformule) → tue le non-sequitur."""
    return _cos(insight_emb, emb_a) >= floor and _cos(insight_emb, emb_b) >= floor


def novelty(insight_emb, existing_embs):
    """1 − max cosinus aux souvenirs existants. 1.0 si aucun (∈ [0,1])."""
    if not existing_embs:
        return 1.0
    return round(1.0 - max(_cos(insight_emb, e) for e in existing_embs), 6)


def parse_hypothesis(out):
    """Hypothèse extraite, ou None si NONE/vide/charabia."""
    if not out:
        return None
    t = re.sub(r"<think>.*?</think>", "", out, flags=re.S | re.I).strip()
    if not t or re.match(r"(?i)^\W*none\b", t):
        return None
    return t


def parse_verdict(out):
    """Dernier verdict d'un sceptique : REFUTE / VALIDE / None."""
    m = re.findall(r"(?i)(r[eé]fut\w*|valid\w*)", out or "")
    if not m:
        return None
    return "REFUTE" if m[-1][:1].lower() == "r" else "VALIDE"


def majority_kill(votes, n_refute_kill):
    """Vrai si ≥ n_refute_kill votes 'REFUTE' → l'insight est tué."""
    return sum(1 for v in votes if v == "REFUTE") >= n_refute_kill


def fertility_score(cos, cross_rubric, coact_weight):
    """Fertilité d'une paire : pic à mi-distance (centre 0.475), bonus inter-rubriques,
    malus si déjà co-activée. Plus haut = plus prometteur pour un lien NEUF."""
    central = max(0.0, 1.0 - abs(cos - 0.475))
    return round(central + (0.30 if cross_rubric else 0.0) - min(0.5, coact_weight or 0.0), 4)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_synthesis_pure.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add config.py synthesis.py tests/test_synthesis_pure.py
git commit -m "feat(synthese): config SYNTH_* + fonctions pures (ancrage, nouveauté, verdicts, fertilité)"
```

---

### Task 3: `select_fertile_pairs`

**Files:**
- Modify: `synthesis.py`
- Test: `tests/test_synthesis_select.py`

**Interfaces:**
- Consumes: `fertility_score`, `_cos` (Task 2) ; `mem.db` (sqlite) ; `config.SYNTH_MID_LO/HI`.
- Produces: `select_fertile_pairs(mem, n, lo=config.SYNTH_MID_LO, hi=config.SYNTH_MID_HI) -> list[(id_a, id_b, fertility)]` — paires de souvenirs substantiels à cosinus ∈ [lo,hi], rubriques de tête ≠, coactivation faible, rangées par fertilité décroissante.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthesis_select.py
import json, synthesis as S

class FakeMem:
    def __init__(self, conn): self.db = conn

def _seed(conn):
    conn.executescript(
        "CREATE TABLE episodes (id INTEGER PRIMARY KEY, role TEXT, content TEXT, embedding TEXT, rubric_id INTEGER);"
        "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));")
    conn.execute("INSERT INTO rubrics VALUES (1,'projets/physique'),(2,'projets/atelier3d')")
    # 1 & 2 : mi-distance (cos~0.5), rubriques ≠  -> FERTILE
    # 1 & 3 : quasi-identiques (cos~1) -> trop proche, écarté
    import math
    def emb(v): return json.dumps(v)
    rows = [(1,'semantic','a',emb([1.0,0.0,0.0]),1),
            (2,'semantic','b',emb([0.6,0.8,0.0]),2),   # cos(1,2)=0.6 dans [0.35,0.60]... ajuster
            (3,'semantic','c',emb([0.99,0.14,0.0]),1)] # cos(1,3)~0.99 trop proche
    for r in rows: conn.execute("INSERT INTO episodes VALUES (?,?,?,?,?)", r)
    conn.commit()

def test_select_keeps_mid_distance_cross_rubric(tmp_db):
    _seed(tmp_db)
    pairs = S.select_fertile_pairs(FakeMem(tmp_db), n=10, lo=0.35, hi=0.65)
    ids = {tuple(sorted((a, b))) for a, b, _ in pairs}
    assert (1, 2) in ids            # mi-distance + inter-rubriques
    assert (1, 3) not in ids        # trop proche (cos~0.99)

def test_select_ranked_and_capped(tmp_db):
    _seed(tmp_db)
    pairs = S.select_fertile_pairs(FakeMem(tmp_db), n=1, lo=0.0, hi=1.1)
    assert len(pairs) == 1          # cap n
    assert pairs == sorted(pairs, key=lambda p: -p[2])   # rangé par fertilité desc
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_synthesis_select.py -q`
Expected: FAIL (`select_fertile_pairs` inexistant).

- [ ] **Step 3: Implement `select_fertile_pairs`**

```python
import json as _json

SUBSTANTIAL_ROLES = ("semantic", "reasoning", "thought", "insight")

def _load_substantial(mem):
    """(id, embedding, top_rubric) des souvenirs substantiels embeddés."""
    ph = ",".join("?" * len(SUBSTANTIAL_ROLES))
    rows = mem.db.execute(
        f"SELECT e.id, e.embedding, COALESCE(r.path,'') FROM episodes e "
        f"LEFT JOIN rubrics r ON r.id = e.rubric_id "
        f"WHERE e.role IN ({ph}) AND e.embedding IS NOT NULL AND e.embedding != '[]'",
        SUBSTANTIAL_ROLES).fetchall()
    out = []
    for eid, emb, path in rows:
        try:
            v = _json.loads(emb)
        except Exception:
            continue
        if v:
            out.append((eid, v, (path.split("/", 1)[0] or "")))
    return out

def _coact_weights(mem):
    """{(a,b) canonique: weight} des arêtes de coactivation existantes."""
    try:
        return {(min(a, b), max(a, b)): w
                for a, b, w in mem.db.execute("SELECT a_id, b_id, weight FROM coactivation")}
    except Exception:
        return {}

def select_fertile_pairs(mem, n, lo=config.SYNTH_MID_LO, hi=config.SYNTH_MID_HI):
    items = _load_substantial(mem)
    coact = _coact_weights(mem)
    scored = []
    for i in range(len(items)):
        ida, va, ra = items[i]
        for j in range(i + 1, len(items)):
            idb, vb, rb = items[j]
            cos = _cos(va, vb)
            if not (lo <= cos <= hi):
                continue
            cross = (ra != rb)
            if not cross:                       # inter-rubriques exigé (la nouveauté naît aux frontières)
                continue
            w = coact.get((min(ida, idb), max(ida, idb)), 0.0)
            scored.append((ida, idb, fertility_score(cos, cross, w)))
    scored.sort(key=lambda p: -p[2])
    return scored[:n]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_synthesis_select.py -q`
Expected: PASS. (Si un cosinus de seed tombe hors bande, ajuster les vecteurs du test pour cos(1,2) ∈ [0.35,0.65].)

- [ ] **Step 5: Commit**

```bash
git add synthesis.py tests/test_synthesis_select.py
git commit -m "feat(synthese): sélection des paires fertiles (mi-distance, inter-rubriques)"
```

---

### Task 4: `generate` + `verify` (chat_fn mockée)

**Files:**
- Modify: `synthesis.py`
- Test: `tests/test_synthesis_genverify.py`

**Interfaces:**
- Consumes: `parse_hypothesis`, `parse_verdict`, `majority_kill` (Task 2).
- Produces:
  - `generate(chat_fn, a_text, b_text, n_samples) -> list[str]` (hypothèses non-NONE).
  - `verify(chat_fn, hypothesis, a_text, b_text, n_skeptics) -> (kept: bool, n_refute: int)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_synthesis_genverify.py
import synthesis as S

def test_generate_filters_none():
    outs = iter(["Hypothèse 1.", "NONE", "Hypothèse 3."])
    hyps = S.generate(lambda p: next(outs), "A", "B", n_samples=3)
    assert hyps == ["Hypothèse 1.", "Hypothèse 3."]

def test_verify_majority_refute_kills():
    outs = iter(["RÉFUTÉ", "RÉFUTÉ", "RÉFUTÉ", "VALIDE", "VALIDE"])
    kept, n_ref = S.verify(lambda p: next(outs), "H", "A", "B", n_skeptics=5)
    assert kept is False and n_ref == 3

def test_verify_survives_when_minority_refute():
    outs = iter(["VALIDE", "VALIDE", "VALIDE", "RÉFUTÉ", "RÉFUTÉ"])
    kept, n_ref = S.verify(lambda p: next(outs), "H", "A", "B", n_skeptics=5)
    assert kept is True and n_ref == 2

def test_prompts_mention_both_sources():
    seen = []
    S.generate(lambda p: (seen.append(p), "x")[1], "SOURCE_A", "SOURCE_B", n_samples=1)
    assert "SOURCE_A" in seen[0] and "SOURCE_B" in seen[0]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_synthesis_genverify.py -q`
Expected: FAIL (`generate`/`verify` inexistants).

- [ ] **Step 3: Implement `generate` + `verify`**

```python
def _gen_prompt(a_text, b_text):
    return (
        "Voici DEUX souvenirs éloignés :\n"
        f"[A] {a_text}\n[B] {b_text}\n\n"
        "Une hypothèse, solution ou question CONCRÈTE émerge-t-elle en les COMBINANT — "
        "quelque chose que ni A ni B ne dit seul ? Si oui : formule-la en 1-2 phrases, "
        "puis « [test: <comment la vérifier concrètement>] ». Sois neuf et précis, pas de banalité.\n"
        "Si la connexion est forcée, vide ou triviale, réponds EXACTEMENT : NONE")

def _skeptic_prompt(hypothesis, a_text, b_text):
    return (
        "Sois un SCEPTIQUE dur. Voici deux souvenirs et une hypothèse censée émerger de leur combinaison :\n"
        f"[A] {a_text}\n[B] {b_text}\nHYPOTHÈSE : {hypothesis}\n\n"
        "Est-ce un VRAI pont (neuf, concret, réellement ancré dans A ET B) ou une connexion "
        "FORCÉE / hallucinée / banale ? Par défaut, doute. Réponds par UN mot : RÉFUTÉ ou VALIDE, "
        "puis une raison courte.")

def generate(chat_fn, a_text, b_text, n_samples):
    """n_samples générations abductives ; garde les hypothèses non-NONE."""
    prompt = _gen_prompt(a_text, b_text)
    hyps = []
    for _ in range(max(1, n_samples)):
        try:
            h = parse_hypothesis(chat_fn(prompt))
        except Exception:
            h = None
        if h:
            hyps.append(h)
    return hyps

def verify(chat_fn, hypothesis, a_text, b_text, n_skeptics):
    """n_skeptics passes « réfute ceci ». -> (kept, n_refute). kept = pas de majorité réfutante."""
    prompt = _skeptic_prompt(hypothesis, a_text, b_text)
    votes = []
    for _ in range(max(1, n_skeptics)):
        try:
            votes.append(parse_verdict(chat_fn(prompt)))
        except Exception:
            votes.append(None)
    n_refute = sum(1 for v in votes if v == "REFUTE")
    return (not majority_kill(votes, config.SYNTH_REFUTE_KILL), n_refute)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_synthesis_genverify.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synthesis.py tests/test_synthesis_genverify.py
git commit -m "feat(synthese): génération abductive + vérification adversariale (chat_fn)"
```

---

### Task 5: `store_insight` + `run` (pipeline complet)

**Files:**
- Modify: `synthesis.py`
- Test: `tests/test_synthesis_run.py`

**Interfaces:**
- Consumes: `select_fertile_pairs`, `generate`, `verify`, `grounding_ok`, `novelty`, `_cos` ; `mem.add`, `mem.log_coactivation`, `embeddings.embed`, `config.SYNTH_*`.
- Produces:
  - `store_insight(mem, hypothesis, source_ids, backend) -> int|None` (insight_id).
  - `run(mem, chat_fn, backend, n_pairs, n_samples=config.SYNTH_SAMPLES, n_skeptics=config.SYNTH_SKEPTICS) -> list[int]`.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthesis_run.py
import json, synthesis as S

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.added = []; self.coact = []
        conn.executescript(
            "CREATE TABLE episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, embedding TEXT, importance REAL, rubric_id INTEGER);"
            "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
            "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));"
            "CREATE TABLE insight_edges (insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id));")
    def add(self, role, content, importance=0.5, embedding=None, **k):
        cur = self.db.execute("INSERT INTO episodes (role,content,embedding,importance) VALUES (?,?,?,?)",
                              (role, content, json.dumps(embedding or []), importance))
        self.db.commit(); self.added.append((role, content)); return cur.lastrowid
    def log_coactivation(self, ids, now, boost=0.05): self.coact.append(tuple(ids)); return 1

def _seed_pairs(conn):
    conn.execute("INSERT INTO rubrics VALUES (1,'projets/physique'),(2,'projets/atelier3d')")
    conn.execute("INSERT INTO episodes (id,role,content,embedding,importance,rubric_id) VALUES "
        "(1,'semantic','les 0 et 1 en rotation',?,0.5,1),(2,'semantic','interactions imparfaites',?,0.5,2)",
        (json.dumps([1.0,0.0,0.0]), json.dumps([0.6,0.8,0.0])))
    conn.commit()

def test_store_insight_creates_episode_edges_and_boost(tmp_db):
    mem = FakeMem(tmp_db); _seed_pairs(tmp_db)
    iid = S.store_insight(mem, "Rendre l'interaction parfaite via les 0/1.", [1, 2], "local")
    row = tmp_db.execute("SELECT role, content FROM episodes WHERE id=?", (iid,)).fetchone()
    assert row[0] == "insight" and row[1].startswith("(insight·local)")
    edges = tmp_db.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (iid,)).fetchall()
    assert sorted(s for (s,) in edges) == [1, 2]
    assert mem.coact and set(mem.coact[0]) == {1, 2}         # rétroaction : sources câblées

def test_run_pipeline_stores_survivors_only(tmp_db, monkeypatch):
    mem = FakeMem(tmp_db); _seed_pairs(tmp_db)
    monkeypatch.setattr(S.embeddings, "embed", lambda t: [0.6, 0.5, 0.0])  # ancré aux 2 sources
    calls = {"n": 0}
    def chat(p):
        # génère une hypothèse, puis tous les sceptiques VALIDENT
        return "NONE" if "SCEPTIQUE" not in p and False else ("Hypothèse concrète." if "COMBINANT" in p else "VALIDE")
    ids = S.run(mem, chat, "local", n_pairs=5)
    assert len(ids) >= 1
    assert all(tmp_db.execute("SELECT role FROM episodes WHERE id=?", (i,)).fetchone()[0] == "insight" for i in ids)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_synthesis_run.py -q`
Expected: FAIL (`store_insight`/`run` inexistants).

- [ ] **Step 3: Implement `store_insight` + `run`**

```python
import embeddings

def store_insight(mem, hypothesis, source_ids, backend):
    """Épisode role='insight' (préfixe backend) + arêtes insight_edges + rétroaction
    coactivation entre les sources. Retourne l'insight_id (ou None si échec)."""
    content = f"(insight·{backend}) {hypothesis}"
    try:
        iid = mem.add("insight", content, importance=config.DREAM_IDEA_IMPORTANCE,
                      embedding=embeddings.embed(content))
    except Exception:
        return None
    if not iid:
        return None
    try:
        mem.db.executemany("INSERT OR IGNORE INTO insight_edges (insight_id, source_id) VALUES (?,?)",
                           [(iid, s) for s in source_ids])
        mem.db.commit()
    except Exception:
        pass
    try:
        mem.log_coactivation(list(source_ids), time.time(), boost=config.SYNTH_COACT_BOOST)
    except Exception:
        pass
    return iid

def _text_of(mem, eid):
    r = mem.db.execute("SELECT content FROM episodes WHERE id=?", (eid,)).fetchone()
    return (r[0] if r else "") or ""

def _emb_of(mem, eid):
    r = mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (eid,)).fetchone()
    try:
        return _json.loads(r[0]) if r and r[0] else []
    except Exception:
        return []

def run(mem, chat_fn, backend, n_pairs, n_samples=config.SYNTH_SAMPLES,
        n_skeptics=config.SYNTH_SKEPTICS):
    """Pipeline complet, best-effort. Retourne les insight_ids créés."""
    created = []
    try:
        pairs = select_fertile_pairs(mem, n_pairs)
    except Exception:
        return created
    for ida, idb, _fert in pairs:
        try:
            a_text, b_text = _text_of(mem, ida), _text_of(mem, idb)
            emb_a, emb_b = _emb_of(mem, ida), _emb_of(mem, idb)
            for hyp in generate(chat_fn, a_text, b_text, n_samples):
                ins_emb = embeddings.embed(hyp)
                if not grounding_ok(ins_emb, emb_a, emb_b, config.SYNTH_GROUNDING_FLOOR):
                    continue
                if novelty(ins_emb, [emb_a, emb_b]) < config.SYNTH_NOVELTY_MIN:
                    continue
                kept, _n = verify(chat_fn, hyp, a_text, b_text, n_skeptics)
                if not kept:
                    continue
                iid = store_insight(mem, hyp, [ida, idb], backend)
                if iid:
                    created.append(iid)
                break                                   # une hypothèse retenue par paire suffit
        except Exception:
            continue
    return created
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_synthesis_run.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synthesis.py tests/test_synthesis_run.py
git commit -m "feat(synthese): store_insight + pipeline run (ancrage→vérif→stockage→rétroaction)"
```

---

### Task 6: Config + hook daemon (étage local)

**Files:**
- Modify: `config.py`, `daemon.py`
- Test: `tests/test_synthesis_pass.py`

**Interfaces:**
- Consumes: `synthesis.run` (Task 5), `config.SYNTHESIS_ENABLED`.
- Produces: `config.SYNTHESIS_ENABLED` + `SYNTH_*` constantes ; `daemon._synthesis_pass(mem, chat_fn) -> None` (best-effort, respecte le kill-switch).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synthesis_pass.py
import json, daemon, config

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.coact = []
        conn.executescript(
            "CREATE TABLE episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, embedding TEXT, importance REAL, rubric_id INTEGER);"
            "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
            "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));"
            "CREATE TABLE insight_edges (insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id));")
    def add(self, role, content, importance=0.5, embedding=None, **k):
        cur = self.db.execute("INSERT INTO episodes (role,content,embedding,importance) VALUES (?,?,?,?)",
                              (role, content, json.dumps(embedding or []), importance)); self.db.commit(); return cur.lastrowid
    def log_coactivation(self, ids, now, boost=0.05): self.coact.append(tuple(ids)); return 1

def test_synthesis_pass_respects_killswitch(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "SYNTHESIS_ENABLED", False)
    called = {"n": 0}
    monkeypatch.setattr(daemon.synthesis, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or [])
    daemon._synthesis_pass(FakeMem(tmp_db), lambda p: "x")
    assert called["n"] == 0                              # kill-switch off → run jamais appelé

def test_synthesis_pass_best_effort(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "SYNTHESIS_ENABLED", True)
    monkeypatch.setattr(daemon.synthesis, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    daemon._synthesis_pass(FakeMem(tmp_db), lambda p: "x")   # ne doit PAS lever
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python -m pytest tests/test_synthesis_pass.py -q`
Expected: FAIL (`daemon._synthesis_pass` / `daemon.synthesis` inexistants).

- [ ] **Step 3: (config déjà ajoutée en Task 2 — rien à faire ici)**

Les constantes `SYNTHESIS_ENABLED` + `SYNTH_*` ont été ajoutées à `config.py` en Task 2 (dépendance d'import de T3–T5). Vérifier juste leur présence : `grep -n "SYNTHESIS_ENABLED" config.py`.

- [ ] **Step 4: Add `_synthesis_pass` + hook in `daemon.py`**

En tête de `daemon.py`, ajouter `import synthesis` (à côté de `import dream_lab`). Puis, juste avant `def dream(eng, mem):` :

```python
def _synthesis_pass(mem, chat_fn):
    """Étage LOCAL du moteur de liens génératifs (best-effort, respecte le kill-switch).
    Ne bloque JAMAIS le rêve : un échec est avalé."""
    if not config.SYNTHESIS_ENABLED:
        return
    try:
        n = synthesis.run(mem, chat_fn, "local", config.SYNTH_LOCAL_BATCH)
        if n:
            print(f"[synthese] {len(n)} lien(s) génératif(s) créé(s)")
    except Exception as e:
        try:
            print("[synthese] passe ratée (rêve non bloqué):", e)
        except Exception:
            pass
```

Puis, dans `dream()`, JUSTE AVANT le curseur final `mem.kv_set("last_dream_maxid", ...)` (et après le bloc ablation), ajouter :

```python
        _synthesis_pass(mem, lambda p: _call(p))   # liens génératifs locaux (9B, gratuit)
```

(`_call` est la closure du rêve qui appelle `eng.chat`.)

- [ ] **Step 5: Run test to verify it passes**

Run: `.venv/bin/python -m pytest tests/test_synthesis_pass.py -q`
Expected: PASS.

- [ ] **Step 6: Run the dream group (no regression)**

Run: `.venv/bin/python -m pytest tests/ -q -k "dream or synthesis or ablation"`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add daemon.py tests/test_synthesis_pass.py
git commit -m "feat(synthese): étage local (hook daemon, kill-switch, best-effort)"
```

---

### Task 7: `synthesis_claude.py` (étage Claude, budget)

**Files:**
- Create: `synthesis_claude.py`
- Test: `tests/test_synthesis_claude.py`

**Interfaces:**
- Consumes: `synthesis.run` (Task 5), `config.SYNTH_CLAUDE_TOPN`.
- Produces: `claude_chat(prompt, timeout=300) -> str|None` (subprocess) ; `run_claude(mem, run_fn=None) -> list[int]` (backend claude, top-N, moins d'échantillons/sceptiques).

- [ ] **Step 1: Write the failing tests (chat_fn mockée — AUCUN claude réel)**

```python
# tests/test_synthesis_claude.py
import synthesis_claude as SC

def test_run_claude_uses_claude_backend(monkeypatch):
    seen = {}
    def fake_run(mem, chat_fn, backend, n_pairs, **k):
        seen.update(backend=backend, n_pairs=n_pairs, kw=k); return [1, 2]
    monkeypatch.setattr(SC.synthesis, "run", fake_run)
    out = SC.run_claude(mem=object(), run_fn=lambda p: "x")
    assert out == [1, 2]
    assert seen["backend"] == "claude"
    assert seen["n_pairs"] == SC.config.SYNTH_CLAUDE_TOPN
    assert seen["kw"].get("n_samples") == 1 and seen["kw"].get("n_skeptics") == 2

def test_claude_chat_builds_command(monkeypatch):
    captured = {}
    class R: returncode = 0; stdout = "réponse"
    monkeypatch.setattr(SC.subprocess, "run", lambda cmd, **k: captured.setdefault("cmd", cmd) or R())
    assert SC.claude_chat("mon prompt") == "réponse"
    assert "claude" in captured["cmd"][0] and "--model" in captured["cmd"] and "sonnet" in captured["cmd"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/python -m pytest tests/test_synthesis_claude.py -q`
Expected: FAIL (`ModuleNotFoundError: synthesis_claude`).

- [ ] **Step 3: Implement `synthesis_claude.py`**

```python
"""Étage CLAUDE du moteur de liens génératifs (budget, main d'Ahmed). Réutilise le
cœur synthesis.run avec claude -p comme backend, sur le TOP des paires (Claude = juge
fort → moins d'échantillons/sceptiques). Testé chat_fn mockée : zéro claude au build."""
import subprocess

import config
import synthesis


def claude_chat(prompt, timeout=300):
    """Backend Claude : un appel claude -p headless, pur texte (aucun outil)."""
    try:
        r = subprocess.run(["claude", "-p", prompt, "--model", "sonnet", "--max-turns", "2",
                            "--allowedTools", ""], capture_output=True, text=True, timeout=timeout)
        return r.stdout if r.returncode == 0 else None
    except Exception as e:
        print("[synthese-claude] claude échoué:", e)
        return None


def run_claude(mem, run_fn=None):
    """Synthèse via Claude sur le top-N des paires fertiles. run_fn injectable (test)."""
    return synthesis.run(mem, run_fn or claude_chat, "claude",
                         config.SYNTH_CLAUDE_TOPN, n_samples=1, n_skeptics=2)


if __name__ == "__main__":
    import sqlite3
    import memory
    m = memory.Memory()
    ids = run_claude(m)
    print(f"[synthese-claude] {len(ids)} lien(s) génératif(s) créé(s)")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `.venv/bin/python -m pytest tests/test_synthesis_claude.py -q`
Expected: PASS.

- [ ] **Step 5: Run whole suite**

Run: `.venv/bin/python -m pytest tests/ -q`
Expected: PASS (aucune régression).

- [ ] **Step 6: Commit**

```bash
git add synthesis_claude.py tests/test_synthesis_claude.py
git commit -m "feat(synthese): étage Claude (top-N paires, budget, testé mocké)"
```

---

### Task 8: Cockpit — endpoint `/api/insights` + panneau 💡

**Files:**
- Modify: `~/AIOS/cockpit/server.js`, `~/AIOS/cockpit/public/dreams.html`, `~/AIOS/cockpit/public/dreams.js`
- Test: `node --check` + curl (pas de suite JS ; vérif manuelle)

**Interfaces:**
- Consumes: la table `insight_edges` + les épisodes `role='insight'` (sqlite -readonly).
- Produces: `GET /api/insights` → `{insights: [{id, ts, content, backend, sources:[{id,snippet}]}]}` ; panneau `💡 Insights` dans le labo des rêves.

- [ ] **Step 1: Add the `/api/insights` endpoint in `server.js`**

Dans `server.js`, à côté des autres routes `/api/dreams*` (après le bloc `/api/dreams/ablation`), ajouter :

```javascript
  if (p === '/api/insights') {
    // Liens génératifs (synthèse abductive) — LECTURE SEULE. Insight + ses sources.
    const ins = await sqlite(
      "SELECT id, ts, content FROM episodes WHERE role='insight' ORDER BY ts DESC LIMIT 60;");
    const out = [];
    for (const r of ins || []) {
      const m = /^\(insight·([a-z]+)\)\s*/.exec(r.content || '');
      const srcs = await sqlite(
        `SELECT e.id, substr(replace(e.content, char(10), ' '), 1, 120) AS snippet ` +
        `FROM insight_edges ie JOIN episodes e ON e.id = ie.source_id WHERE ie.insight_id = ${Number(r.id)};`);
      out.push({ id: r.id, ts: r.ts, backend: m ? m[1] : '?',
                 content: (r.content || '').replace(/^\(insight·[a-z]+\)\s*/, ''),
                 sources: srcs || [] });
    }
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(j({ insights: out }));
  }
```

(Note : `Number(r.id)` valide l'entier avant interpolation — pas d'injection.)

- [ ] **Step 2: Add the panel in `dreams.html`**

Après la `<section id="ablation-card">`, ajouter :

```html
<section class="glass accent" id="insights-card" style="margin-bottom:12px;">
  <div class="sec-label">💡 LIENS GÉNÉRATIFS <span class="dim">· hypothèses nées de souvenirs distants · synthesis</span></div>
  <div id="insights"><div class="dim">chargement…</div></div>
</section>
```

- [ ] **Step 3: Render insights in `dreams.js`**

Ajouter (après `loadAblation()` / son appel) :

```javascript
async function loadInsights() {
  try {
    const d = await (await fetch('/api/insights')).json();
    const items = d.insights || [];
    document.getElementById('insights').innerHTML = items.length ? items.map(it =>
      `<div class="mem" style="border-top:1px solid var(--glass-bd);padding:8px 0">
        <span class="badge" style="font-size:10px">${esc(it.backend)}</span>
        ${esc(it.content)}
        <div class="dim" style="font-size:11px;margin-top:4px">↳ ${it.sources.map(s => esc(s.snippet)).join(' · ')}</div>
      </div>`).join('') : '<div class="dim">(aucun lien génératif encore — le daemon en tisse la nuit)</div>';
  } catch (_) { document.getElementById('insights').innerHTML = '<div class="dim">(indisponible)</div>'; }
}
loadInsights();
```

- [ ] **Step 4: Verify syntax + endpoint**

Run: `cd ~/AIOS/cockpit && node --check server.js && node --check public/dreams.js && echo OK`
Expected: `OK`.
Puis (si le cockpit tourne, sinon après redémarrage manuel) : `curl -s localhost:4317/api/insights` → JSON `{"insights":[...]}` (liste vide au début = normal).

- [ ] **Step 5: Commit (repo cockpit séparé — noter, pas de commit anamnese)**

Le cockpit `~/AIOS/cockpit` est un projet Node distinct. Documenter les 3 fichiers modifiés dans le rapport de tâche ; le commit/versionnage du cockpit est laissé à la main d'Ahmed (comme pour la vue 6 cellules).

---

## Notes d'exécution (hors-build)
- Daemon (gratuit) : à chaque rêve → `_synthesis_pass` tisse ~20 paires locales (9B), garde les survivants.
- Budget : `.venv/bin/python -m synthesis_claude` → top-5 via Claude.
- Cockpit : redémarrer `~/AIOS/cockpit` + rafraîchir → panneau 💡 Liens génératifs.
- Analyse : `SELECT COUNT(*) FROM episodes WHERE role='insight';` + `SELECT * FROM insight_edges;`.
