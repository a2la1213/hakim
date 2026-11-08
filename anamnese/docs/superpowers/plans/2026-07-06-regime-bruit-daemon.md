# Régime du bruit daemon — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Exclure `reflection`/`outreach` du rappel par défaut (correction) et arrêter de les embedder (efficience, ~36 Mo/an), sans suppression — le journal de métacognition reste complet.

**Architecture:** `retrieve` gagne un `exclude_roles` (défaut daemon) appliqué SEULEMENT quand aucun `kinds` positif n'est passé. Le daemon écrit reflection/outreach avec `embedding=[]`. Un script one-shot (manuel) blanchit les embeddings existants. Les orphelins ainsi créés restent invisibles au jardinage nocturne (orphans_report est role-filtré).

**Tech Stack:** Python 3.14 (.venv, pytest — 403 tests), SQLite, model2vec via `embeddings.embed`. Spec : `docs/superpowers/specs/2026-07-06-regime-bruit-daemon-design.md`.

## Global Constraints

- Tests : DB temp migrée, monkeypatch `embeddings.embed`, JAMAIS `data/memory.db`. Full suite ≥ 403 avant chaque commit.
- `exclude_roles` NE s'applique QUE si `kinds` est None/vide (un `kinds` positif gouverne — rétro-compat totale : le rêve `kinds=["semantic"]` et `reasoning_recall kinds=["reasoning"]` inchangés).
- `RECALL_EXCLUDE_ROLES = ("reflection", "outreach")` — exact.
- Rétention = AUCUNE suppression. Le one-shot NE tourne pas tout seul (Ahmed le lance).
- Branche `regime-bruit-daemon` depuis main ; merge --no-ff en fin.

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `config.py` (modify) | `RECALL_EXCLUDE_ROLES` | 1 |
| `memory.py` (modify, retrieve ~l.260-296) | param `exclude_roles` + filtre | 1 |
| `daemon.py` (modify l.99, l.113-114) | `embedding=[]` sur reflection/outreach | 2 |
| `scripts/blanch_daemon_embeddings.py` (create) | one-shot blanchiment | 3 |
| `tests/test_recall_exclude.py`, `tests/test_daemon_noembed.py` (create) | suites TDD | 1-2 |

---

### Task 1: `retrieve` exclut reflection/outreach par défaut

**Files:**
- Modify: `config.py` (après le bloc TAX_*), `memory.py` (signature retrieve ~l.260 + boucle filtre ~l.296)
- Test: `tests/test_recall_exclude.py`

**Interfaces:**
- Produces: `Memory.retrieve(self, query_text, query_emb, now=None, top_k=config.TOP_K, kinds=None, rubric=None, reconsolidate=False, exclude_roles=config.RECALL_EXCLUDE_ROLES)` — quand `kinds` est fourni il gouverne (exclude ignoré) ; sinon les rôles de `exclude_roles` sont retirés des candidats ; `config.RECALL_EXCLUDE_ROLES = ("reflection", "outreach")`.

- [ ] **Step 1: Write the failing test** — `tests/test_recall_exclude.py` :

```python
"""Le bruit daemon (reflection/outreach) est exclu du rappel PAR DÉFAUT, mais
inclus si explicitement demandé via kinds. DB temp, jamais data/memory.db."""
import pytest

import config
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _seed(mem):
    # même embedding pour tous → même pertinence ; seul le rôle diffère
    mem.add("semantic", "fait durable batiment", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.add("reflection", "pensée daemon sur batiment", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.add("outreach", "sollicitation batiment", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()


def test_recall_defaut_exclut_reflection_outreach(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6)
    roles = {r[2] for r in res}
    assert "semantic" in roles
    assert "reflection" not in roles and "outreach" not in roles


def test_kinds_positif_prime_sur_exclude(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6, kinds=["reflection"])
    roles = {r[2] for r in res}
    assert roles == {"reflection"}                      # kinds gouverne, exclude ignoré


def test_exclude_roles_surchargeable(mem):
    _seed(mem)
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6, exclude_roles=())
    roles = {r[2] for r in res}
    assert "reflection" in roles                        # exclude vidé → tout revient
```

- [ ] **Step 2: RED** — `.venv/bin/python -m pytest tests/test_recall_exclude.py -v` → FAIL (reflection/outreach encore ramenés ; `exclude_roles` inconnu).

- [ ] **Step 3: config.py** — ajouter après le bloc TAX_* :

```python
# --- Régime du bruit daemon (spec 2026-07-06) ---
RECALL_EXCLUDE_ROLES = ("reflection", "outreach")  # exclus du rappel PAR DÉFAUT (journal daemon, jamais rappelé)
```

- [ ] **Step 4: memory.py — signature retrieve** (~l.260) : ajouter le paramètre en fin :

```python
    def retrieve(self, query_text, query_emb, now=None, top_k=config.TOP_K, kinds=None,
                 rubric=None, reconsolidate=False, exclude_roles=config.RECALL_EXCLUDE_ROLES):
```

- [ ] **Step 5: memory.py — boucle de filtre** (~l.296) : remplacer

```python
            if kinds and role not in kinds:
                continue
```
par

```python
            if kinds:
                if role not in kinds:
                    continue
            elif exclude_roles and role in exclude_roles:
                continue
```
(quand `kinds` est fourni il gouverne seul ; sinon `exclude_roles` retire le bruit daemon.)

- [ ] **Step 6: GREEN + full suite** — `pytest tests/test_recall_exclude.py -v` (3 PASS) puis `pytest -q` (≥ 406). Vérifier qu'aucun test existant de recall ne casse (les appels via `memory_recall` sans kinds verront désormais l'exclusion — si un test existant attendait une reflection au rappel par défaut, c'est le comportement voulu à corriger).

- [ ] **Step 7: Commit** — `git commit -m "Régime bruit daemon T1: retrieve exclut reflection/outreach du rappel par défaut (kinds positif prime, surchargeable)"`

---

### Task 2: le daemon n'embedde plus reflection/outreach

**Files:**
- Modify: `daemon.py` (l.99 reflection, l.113-114 outreach)
- Test: `tests/test_daemon_noembed.py`

**Interfaces:**
- Consumes: `mem.add(role, content, importance, embedding)` (embedding=[] accepté — routing/facets déjà best-effort sur vide) ; `config.RECALL_EXCLUDE_ROLES` (T1).

- [ ] **Step 1: Write the failing test** — `tests/test_daemon_noembed.py` :

```python
"""Le daemon écrit reflection/outreach SANS embedding (économie compute+stockage) :
ils deviennent orphelins, absents du recall et du jardinage — mais lus par texte
(de-echo, rêve, dashboard). DB temp, jamais data/memory.db."""
import json

import pytest

import config
import daemon
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    monkeypatch.setattr(daemon.embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


class FakeEng:
    def health(self):
        return True
    def chat(self, messages, stream=False, think=False):
        # une pensée + PROACTIF non (pas d'outreach ici)
        return "Une intuition neuve sur le batiment.\nPROACTIF: non"


def test_reflection_ecrite_sans_embedding(mem, monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed",
                        lambda t: (_ for _ in ()).throw(AssertionError("embed appelé !")))
    # reflect ne doit PAS appeler embed pour la reflection
    daemon.reflect(FakeEng(), mem)
    row = mem.db.execute(
        "SELECT embedding, rubric_id FROM episodes WHERE role='reflection' ORDER BY id DESC LIMIT 1"
    ).fetchone()
    assert row is not None
    assert json.loads(row[0]) == []                      # embedding vide
    assert row[1] is None                                # orphelin (non routé)


def test_reflection_absente_du_recall_et_orphans(mem):
    mem.add("reflection", "pensée batiment", importance=0.4, embedding=[])
    mem.add("semantic", "fait batiment", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()
    res = mem.retrieve("batiment", [1.0, 0.0, 0.0, 0.0], top_k=6)
    assert "reflection" not in {r[2] for r in res}       # exclue du recall (T1)
    # orphans_report (via mcp) exclut déjà reflection par rôle — vérif directe du filtre :
    import taxonomy
    clusters = taxonomy.orphan_clusters(mem.db)
    ids = [i for c in clusters for i in c["episode_ids"]]
    refl_id = mem.db.execute("SELECT id FROM episodes WHERE role='reflection'").fetchone()[0]
    assert refl_id not in ids                            # invisible au jardinage nocturne


def test_de_echo_toujours_actif_sans_embedding(mem):
    # 2 pensées quasi-identiques → la 2e sautée par la de-echo (lexical sur TEXTE, pas embedding)
    eng = FakeEng()
    daemon.reflect(eng, mem)
    n1 = mem.db.execute("SELECT COUNT(*) FROM episodes WHERE role='reflection'").fetchone()[0]
    daemon.reflect(eng, mem)                              # même sortie → doublon
    n2 = mem.db.execute("SELECT COUNT(*) FROM episodes WHERE role='reflection'").fetchone()[0]
    assert n2 == n1                                       # anti-boucle intact
```

- [ ] **Step 2: RED** — FAIL (reflect appelle encore embed).

- [ ] **Step 3: daemon.py** — l.99 :

```python
    mem.add("reflection", out[:600], importance=0.4, embedding=[])
```
l.113-114 (outreach) :

```python
            mem.add("outreach", f"(sollicitation spontanée) {msg}", importance=0.5,
                    embedding=[])
```
(RIEN d'autre : la de-echo `salience.lexical_overlap`, l'anti-spam, la lecture du rêve/dashboard travaillent sur `content` — intacts.)

- [ ] **Step 4: GREEN + full suite** (≥ 409). Vérifier `test_dream_night.py`/`test_shy.py` (ils forgent des reflections ?) — si un test attendait une reflection embeddée, adapter (embedding=[] est le comportement voulu).

- [ ] **Step 5: Commit** — `git commit -m "Régime bruit daemon T2: le daemon n'embedde plus reflection/outreach (orphelins, hors recall/jardinage, lus par texte) — ~36 Mo/an économisés"`

---

### Task 3: script one-shot de blanchiment (déclenché manuellement)

**Files:**
- Create: `scripts/blanch_daemon_embeddings.py`
- Test: `tests/test_blanch_oneshot.py`

**Interfaces:**
- Produces: `blanch(db_path, dry_run=False) -> dict {"blanched": int, "reclaimed_bytes": int}` — met `embedding='[]'` sur reflection/outreach dont l'embedding n'est pas déjà vide ; NE touche PAS rubric_id ; retourne le compte + octets estimés. `main()` : backup (checkpoint WAL) puis blanch sur `config.DB_PATH`, imprime le bilan. Best-effort, jamais destructif au-delà du blanchiment d'embedding.

- [ ] **Step 1: Write the failing test** — `tests/test_blanch_oneshot.py` :

```python
"""One-shot : blanchit les embeddings reflection/outreach existants (récupère l'espace),
sans toucher rubric_id ni le contenu. DB temp, jamais data/memory.db."""
import json
import importlib

import pytest

import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_blanch_reflections_pas_le_savoir(mem):
    blanch = importlib.import_module("scripts.blanch_daemon_embeddings")
    r1 = mem.add("reflection", "pensée", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    r2 = mem.add("outreach", "sollicit", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    s1 = mem.add("semantic", "fait", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    # ranger la reflection dans une rubrique pour prouver que rubric_id est préservé
    import rubrics
    rubrics.rubric_create(mem.db, "journal", 0)
    rubrics.attach_episode(mem.db, r1, "journal", 0.9, 0)
    mem.db.commit()
    res = blanch.blanch(str(mem.db.execute("PRAGMA database_list").fetchone()[2]))
    assert res["blanched"] == 2                            # les 2 daemon, pas le semantic
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (r1,)).fetchone()[0]) == []
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (r2,)).fetchone()[0]) == []
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (s1,)).fetchone()[0]) != []
    # rubric_id PRÉSERVÉ (on ne déclasse pas les 903 existants)
    assert mem.db.execute("SELECT rubric_id FROM episodes WHERE id=?", (r1,)).fetchone()[0] is not None


def test_blanch_idempotent(mem):
    blanch = importlib.import_module("scripts.blanch_daemon_embeddings")
    mem.add("reflection", "p", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()
    path = str(mem.db.execute("PRAGMA database_list").fetchone()[2])
    assert blanch.blanch(path)["blanched"] == 1
    assert blanch.blanch(path)["blanched"] == 0           # déjà vides → rien à faire
```

- [ ] **Step 2: RED** — FAIL (module absent).

- [ ] **Step 3: Implémenter `scripts/blanch_daemon_embeddings.py`** :

```python
#!/usr/bin/env python3
"""One-shot : blanchit les embeddings des reflection/outreach déjà en base
(journal daemon jamais rappelé) pour récupérer l'espace. NE supprime RIEN,
ne touche PAS rubric_id. À lancer À LA MAIN :
    .venv/bin/python -m scripts.blanch_daemon_embeddings
"""
import sqlite3
import sys
from pathlib import Path

ROLES = ("reflection", "outreach")


def blanch(db_path, dry_run=False):
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ph = ",".join("?" * len(ROLES))
        rows = conn.execute(
            f"SELECT id, LENGTH(embedding) FROM episodes "
            f"WHERE role IN ({ph}) AND embedding != '[]'", ROLES).fetchall()
        reclaimed = sum((n or 0) for _id, n in rows)
        if not dry_run and rows:
            conn.execute(
                f"UPDATE episodes SET embedding='[]' WHERE role IN ({ph}) AND embedding != '[]'",
                ROLES)
            conn.commit()
        return {"blanched": len(rows), "reclaimed_bytes": reclaimed}
    finally:
        conn.close()


def main():
    try:
        import config
        db = Path(config.DB_PATH)
    except Exception:
        db = Path(__file__).resolve().parent.parent / "data" / "memory.db"
    if not db.exists():
        print(f"DB absente : {db}"); return
    # checkpoint WAL avant (bonne pratique ; le VACUUM éventuel reste à la main)
    try:
        c = sqlite3.connect(str(db)); c.execute("PRAGMA wal_checkpoint(TRUNCATE)"); c.close()
    except Exception:
        pass
    res = blanch(db)
    print(f"Blanchi : {res['blanched']} épisode(s) reflection/outreach — "
          f"~{res['reclaimed_bytes']/1048576:.1f} Mo d'embeddings libérés "
          f"(exécuter `VACUUM` pour compacter le fichier si voulu).")


if __name__ == "__main__":
    main()
```
(Note : `scripts/` doit être un package importable — s'il manque un `__init__.py`, en ajouter un vide ; vérifier d'abord `ls scripts/`.)

- [ ] **Step 4: GREEN + full suite** (≥ 411).
- [ ] **Step 5: Commit** — `git commit -m "Régime bruit daemon T3: script one-shot blanch_daemon_embeddings (récupère l'espace des embeddings daemon existants, manuel, non destructif)"`

---

### Task 4: Merge + déploiement

- [ ] Full suite verte. `git checkout main && git merge --no-ff regime-bruit-daemon`.
- [ ] Relancer le daemon (`launchctl kickstart -k gui/$(id -u)/com.anamnese.daemon`) pour qu'il arrête d'embedder.
- [ ] Vérif réelle : `./anamnese recall "un sujet"` ne ramène plus de reflection ; `sqlite3 -readonly data/memory.db "SELECT role,COUNT(*) FROM episodes WHERE role IN ('reflection','outreach') AND embedding!='[]'"` (baseline avant le one-shot).
- [ ] NE PAS lancer le one-shot automatiquement — présenter à Ahmed : « `cd ~/Desktop/anamnese && .venv/bin/python -m scripts.blanch_daemon_embeddings` récupère les 4,8 Mo quand tu veux (puis `VACUUM` optionnel pour compacter). »
- [ ] Ledger + rapport.
