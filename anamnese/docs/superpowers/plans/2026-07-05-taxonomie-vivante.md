# Taxonomie vivante — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax.

**Goal:** Le cerveau d'Anamnèse grandit et se réorganise : mutations de taxonomie (rename/reparent/merge/reclassify/undo) transactionnelles et réversibles, création agentique en-session guidée par le routage retourné, émergence nocturne de nœuds depuis les orphelins (opérations douces seulement, imposées par l'allowlist), gardes anti-explosion.

**Architecture:** `taxonomy.py` possède les mutations de haut niveau au-dessus des primitives `rubrics.py` (attach/update_centroid/_detach_from existants — refactor minime : un cœur `_attach_core` SANS commit pour la transactionnalité du merge). Surface MCP fine + `memory_store` qui révèle le routage. Le nocturne est bridé par le HARNAIS (TOOLS de consolidate.py sans merge/reparent), pas seulement par le prompt.

**Tech Stack:** Python 3.14 (.venv, pytest — 373 tests), SQLite, FastMCP, embeddings model2vec via `embeddings.embed`. Spec : `docs/superpowers/specs/2026-07-05-taxonomie-vivante-design.md`.

## Global Constraints

- Tests : DB temporaire migrée, JAMAIS `data/memory.db`. Full suite ≥ 373 avant chaque commit. Monkeypatch `embeddings.embed` dans les tests.
- Mutations TRANSACTIONNELLES : un échec au milieu → rollback complet, jamais d'arbre à moitié muté. `memory.add` reste best-effort (le routage ne casse jamais une écriture).
- Journal d'annulation : `kv['taxonomy_log']` JSON, borné à `TAX_LOG_MAX=20` entrées ; `undo_last` = 1 cran.
- Gardes exactes (spec) : `TAX_DISTINCT_MAX=0.80` (cosinus max avec un centroïde existant pour créer), `TAX_CLUSTER_MIN_SIM=0.55` (cohérence intra-cluster), `TAX_ORPHAN_MIN=3` (masse nocturne). `RUBRIC_MAX_DEPTH` et parent-obligatoire conservés.
- Nocturne = opérations douces UNIQUEMENT, imposé par l'allowlist `TOOLS` de consolidate.py : + `orphans_report`,`rubric_tree`,`rubric_create`,`memory_reclassify` ; JAMAIS `rubric_merge`/`rubric_reparent`/`taxonomy_undo`.
- Chemins de path : kebab-case, validés (`^[a-z0-9\-/]+$`), pas de `/` en tête/queue.
- Branche `taxonomie-vivante` depuis main ; merge --no-ff en fin ; CLAUDE.md (hors git) documenté dans le rapport.

## File Structure

| Fichier | Rôle | Tâche |
|---|---|---|
| `config.py` (modify) | constantes `TAX_*` | 1 |
| `rubrics.py` (modify) | extraire `_attach_core` (sans commit) de `attach_episode` | 1 |
| `taxonomy.py` (create) | mutations + journal + undo + recompute + guard + clusters | 1, 3 |
| `mcp_server.py` (modify) | 6 outils + retour routage de `memory_store` | 2 |
| `~/.claude/CLAUDE.md` (modify) | protocole création/reclassement en-session | 2 |
| `consolidate_prompt.txt` + `consolidate.py` (modify) | étape JARDINAGE + allowlist durcie | 3 |
| `~/AIOS/cockpit` server.js + memory.js (modify) | endpoint + panneau arbre | 4 |
| `tests/test_taxonomy.py`, `tests/test_taxonomy_mcp.py`, `tests/test_taxonomy_growth.py` (create) | suites TDD | 1-3 |

---

### Task 1: `taxonomy.py` — mutations transactionnelles + journal + undo

**Files:**
- Modify: `config.py` (après le bloc DREAM_VERDICT_*), `rubrics.py` (attach_episode ~l.230)
- Create: `taxonomy.py`
- Test: `tests/test_taxonomy.py`

**Interfaces:**
- Consumes: `rubrics.get_rubric_id(conn, path)`, `rubrics.rubric_create(conn, path, now, label, kind_hint)`, `rubrics.update_centroid(conn, rid, emb)` (sans commit), `rubrics._detach_from(conn, rid, emb)` (sans commit), `rubrics._parse_embedding(raw)`, table `rubrics(id,path,label,parent_id,kind_hint,centroid,centroid_n,depth,memory_count,created_ts)`, `config.RUBRIC_MAX_DEPTH`.
- Produces (consommé par Tasks 2-3) :
  - `taxonomy.rename(conn, old_path, new_path, now) -> int` (nb de rubriques renommées, cascade descendants)
  - `taxonomy.relabel(conn, path, label) -> None`
  - `taxonomy.reparent(conn, path, new_parent_path, now) -> int`
  - `taxonomy.merge(conn, src_path, dst_path, now) -> dict {"moved_episodes": int, "moved_children": int}`
  - `taxonomy.reclassify(conn, episode_id, new_path_or_None, now) -> str` (path final ou "orphelin")
  - `taxonomy.recompute_centroid(conn, path) -> int` (nb d'embeddings intégrés)
  - `taxonomy.undo_last(conn) -> str` (description de l'op annulée, ou "(rien à annuler)")
  - `taxonomy.log_entries(conn) -> list[dict]`
  - dans rubrics.py : `_attach_core(conn, episode_id, rubric_path, conf, now)` = corps actuel d'`attach_episode` SANS le `conn.commit()` final ; `attach_episode` devient `_attach_core(...)` + `conn.commit()` (comportement public inchangé).

- [ ] **Step 1: config.py** — ajouter après le bloc DREAM_STATE_CORR_* :

```python
# --- Taxonomie vivante (spec 2026-07-05) ---
TAX_DISTINCT_MAX   = 0.80   # cosinus max avec un centroïde existant pour CRÉER un nœud (sinon: router/fusionner)
TAX_CLUSTER_MIN_SIM = 0.55  # cohérence intra-cluster min pour l'émergence nocturne
TAX_ORPHAN_MIN     = 3      # masse min d'orphelins cohérents pour un nœud nocturne
TAX_LOG_MAX        = 20     # journal d'annulation borné (undo = 1 cran)
```

- [ ] **Step 2: Write the failing tests** — `tests/test_taxonomy.py` :

```python
"""Taxonomie vivante — mutations transactionnelles, cascade, centroïdes, undo.
DB temp migrée, embeddings monkeypatchés, JAMAIS data/memory.db."""
import json
import time

import pytest

import config
import migrations
import rubrics
import taxonomy
from memory import Memory

NOW = 1_800_000_000.0


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _mk(mem, path):
    parts = path.split("/")
    for i in range(len(parts)):
        rubrics.rubric_create(mem.db, "/".join(parts[: i + 1]), NOW)


def _ep(mem, content, path=None, emb=None):
    eid = mem.add("semantic", content, importance=0.5, embedding=emb or [0.5] * 8)
    if path:
        rubrics.attach_episode(mem.db, eid, path, 0.9, NOW)
    return eid


def test_rename_cascade_descendants(mem):
    _mk(mem, "projets/alpha/sub")
    n = taxonomy.rename(mem.db, "projets/alpha", "projets/beta", NOW)
    assert n == 2                                          # alpha + alpha/sub
    paths = {r[0] for r in mem.db.execute("SELECT path FROM rubrics").fetchall()}
    assert "projets/beta" in paths and "projets/beta/sub" in paths
    assert "projets/alpha" not in paths and "projets/alpha/sub" not in paths


def test_rename_refus(mem):
    _mk(mem, "projets/alpha")
    _mk(mem, "projets/beta")
    with pytest.raises(ValueError):                        # cible existe → suggérer merge
        taxonomy.rename(mem.db, "projets/alpha", "projets/beta", NOW)
    with pytest.raises(ValueError):                        # parent absent
        taxonomy.rename(mem.db, "projets/alpha", "fantome/beta", NOW)


def test_reparent_branche(mem):
    _mk(mem, "projets/alpha/sub")
    _mk(mem, "savoir")
    taxonomy.reparent(mem.db, "projets/alpha", "savoir", NOW)
    paths = {r[0] for r in mem.db.execute("SELECT path FROM rubrics").fetchall()}
    assert "savoir/alpha" in paths and "savoir/alpha/sub" in paths
    # depth mis à jour
    d = mem.db.execute("SELECT depth FROM rubrics WHERE path='savoir/alpha/sub'").fetchone()[0]
    assert d == 2


def test_merge_deplace_et_recompute(mem):
    _mk(mem, "projets/a")
    _mk(mem, "projets/b")
    e1 = _ep(mem, "souvenir un", "projets/a", emb=[1.0] * 8)
    e2 = _ep(mem, "souvenir deux", "projets/a", emb=[0.0] * 8)
    _ep(mem, "déjà chez b", "projets/b", emb=[0.5] * 8)
    r = taxonomy.merge(mem.db, "projets/a", "projets/b", NOW)
    assert r["moved_episodes"] == 2
    assert rubrics.get_rubric_id(mem.db, "projets/a") is None          # src supprimée
    rid_b = rubrics.get_rubric_id(mem.db, "projets/b")
    got = {row[0] for row in mem.db.execute(
        "SELECT id FROM episodes WHERE rubric_id=?", (rid_b,)).fetchall()}
    assert {e1, e2} <= got
    # centroïde de b RECALCULÉ depuis les embeddings réels (brute force)
    cen = json.loads(mem.db.execute(
        "SELECT centroid FROM rubrics WHERE id=?", (rid_b,)).fetchone()[0])
    assert cen[0] == pytest.approx((1.0 + 0.0 + 0.5) / 3)


def test_merge_refuse_dst_descendant(mem):
    _mk(mem, "projets/a/sub")
    with pytest.raises(ValueError):
        taxonomy.merge(mem.db, "projets/a", "projets/a/sub", NOW)


def test_reclassify_et_detach(mem):
    _mk(mem, "projets/a")
    _mk(mem, "projets/b")
    eid = _ep(mem, "à déplacer", "projets/a")
    assert taxonomy.reclassify(mem.db, eid, "projets/b", NOW) == "projets/b"
    rid_b = rubrics.get_rubric_id(mem.db, "projets/b")
    row = mem.db.execute("SELECT rubric_id, rubric_conf FROM episodes WHERE id=?", (eid,)).fetchone()
    assert row[0] == rid_b and row[1] == 1.0               # conf 1.0 = choix délibéré
    assert taxonomy.reclassify(mem.db, eid, None, NOW) == "orphelin"
    assert mem.db.execute("SELECT rubric_id FROM episodes WHERE id=?", (eid,)).fetchone()[0] is None


def test_undo_rename_et_merge(mem):
    _mk(mem, "projets/a")
    taxonomy.rename(mem.db, "projets/a", "projets/z", NOW)
    assert "rename" in taxonomy.undo_last(mem.db)
    assert rubrics.get_rubric_id(mem.db, "projets/a") is not None      # revenu
    _mk(mem, "projets/b")
    eid = _ep(mem, "x", "projets/a")
    taxonomy.merge(mem.db, "projets/a", "projets/b", NOW)
    taxonomy.undo_last(mem.db)
    assert rubrics.get_rubric_id(mem.db, "projets/a") is not None      # recréée
    rid_a = rubrics.get_rubric_id(mem.db, "projets/a")
    assert mem.db.execute("SELECT rubric_id FROM episodes WHERE id=?", (eid,)).fetchone()[0] == rid_a


def test_transactionnel_sous_sabotage(mem, monkeypatch):
    """Un crash au milieu d'un merge → RIEN n'a bougé (tout ou rien)."""
    _mk(mem, "projets/a")
    _mk(mem, "projets/b")
    _ep(mem, "un", "projets/a")
    _ep(mem, "deux", "projets/a")
    calls = {"n": 0}
    real = rubrics.update_centroid
    def boom(conn, rid, emb):
        calls["n"] += 1
        if calls["n"] >= 2:
            raise RuntimeError("sabotage")
        return real(conn, rid, emb)
    monkeypatch.setattr(rubrics, "update_centroid", boom)
    with pytest.raises(Exception):
        taxonomy.merge(mem.db, "projets/a", "projets/b", NOW)
    # rollback complet : src existe toujours, épisodes toujours chez src
    rid_a = rubrics.get_rubric_id(mem.db, "projets/a")
    assert rid_a is not None
    n = mem.db.execute("SELECT COUNT(*) FROM episodes WHERE rubric_id=?", (rid_a,)).fetchone()[0]
    assert n == 2


def test_journal_borne(mem):
    _mk(mem, "projets/a")
    for i in range(25):
        taxonomy.rename(mem.db, "projets/a" if i % 2 == 0 else "projets/b",
                        "projets/b" if i % 2 == 0 else "projets/a", NOW)
    assert len(taxonomy.log_entries(mem.db)) <= config.TAX_LOG_MAX
```

- [ ] **Step 3: RED** — `.venv/bin/python -m pytest tests/test_taxonomy.py -v` → FAIL (`ModuleNotFoundError: taxonomy`).

- [ ] **Step 4: rubrics.py — extraire `_attach_core`** : renommer le corps actuel d'`attach_episode` en `_attach_core(conn, episode_id, rubric_path, conf, now)` SANS le `conn.commit()` final, puis :

```python
def attach_episode(conn, episode_id, rubric_path, conf, now):
    """Rattache un épisode (public) — _attach_core + commit. Voir _attach_core."""
    _attach_core(conn, episode_id, rubric_path, conf, now)
    conn.commit()
```
(docstring d'origine déplacée sur `_attach_core` ; AUCUN autre changement.)

- [ ] **Step 5: Implémenter `taxonomy.py`** :

```python
"""Anamnèse — taxonomie VIVANTE : mutations de structure du cerveau.

Le cerveau ne se contente pas de grandir (rubric_create) : il se réorganise —
renommer, reparenter, fusionner, reclasser. Chaque mutation est
TRANSACTIONNELLE (tout ou rien), JOURNALISÉE (kv['taxonomy_log'], borné
TAX_LOG_MAX) et RÉVERSIBLE 1 cran (undo_last), et les centroïdes affectés sont
recalculés depuis les embeddings réels (source de vérité post-mutation).
Spec : docs/superpowers/specs/2026-07-05-taxonomie-vivante-design.md
"""
import json
import re
import time

import config
import rubrics

_PATH_RE = re.compile(r"^[a-z0-9\-]+(/[a-z0-9\-]+)*$")


# ---------- journal (kv) ----------

def _kv_get(conn, key, default=None):
    row = conn.execute("SELECT value FROM kv WHERE key=?", (key,)).fetchone()
    return row[0] if row else default


def _kv_set(conn, key, value):
    conn.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
                 (key, value, time.time()))


def log_entries(conn):
    try:
        return json.loads(_kv_get(conn, "taxonomy_log", "[]"))
    except Exception:
        return []


def _log_op(conn, desc, inverse):
    """Journalise desc + l'op inverse (pour undo). Ne committe pas (dans la tx)."""
    entries = log_entries(conn)
    entries.append({"desc": desc, "inverse": inverse, "ts": time.time()})
    _kv_set(conn, "taxonomy_log", json.dumps(entries[-config.TAX_LOG_MAX:], ensure_ascii=False))


# ---------- helpers ----------

def _check_path(path):
    if not path or not _PATH_RE.match(path):
        raise ValueError(f"path invalide (kebab-case a/b/c attendu) : {path!r}")


def _rid(conn, path):
    rid = rubrics.get_rubric_id(conn, path)
    if rid is None:
        raise ValueError(f"rubrique inexistante : {path!r}")
    return rid


def _subtree(conn, path):
    """[(id, path, depth)] de la rubrique + TOUS ses descendants."""
    like = path + "/%"
    return conn.execute(
        "SELECT id, path, depth FROM rubrics WHERE path=? OR path LIKE ? ORDER BY depth, path",
        (path, like)).fetchall()


def recompute_centroid(conn, path):
    """Recalcule centroïde/centroid_n/memory_count depuis les épisodes attachés.
    Source de vérité après mutation. Retourne le nb d'embeddings intégrés.
    Ne committe pas."""
    rid = _rid(conn, path)
    rows = conn.execute("SELECT embedding FROM episodes WHERE rubric_id=?", (rid,)).fetchall()
    embs = []
    for (raw,) in rows:
        e = rubrics._parse_embedding(raw)
        if e:
            embs.append(e)
    if embs:
        dim = len(embs[0])
        embs = [e for e in embs if len(e) == dim]
        cen = [sum(e[i] for e in embs) / len(embs) for i in range(dim)]
        conn.execute("UPDATE rubrics SET centroid=?, centroid_n=? WHERE id=?",
                     (json.dumps(cen), len(embs), rid))
    else:
        conn.execute("UPDATE rubrics SET centroid=NULL, centroid_n=0 WHERE id=?", (rid,))
    conn.execute("UPDATE rubrics SET memory_count=? WHERE id=?", (len(rows), rid))
    return len(embs)


# ---------- mutations ----------

def rename(conn, old_path, new_path, now, _log=True):
    """Renomme/déplace old_path → new_path, CASCADE sur les descendants.
    Refuse : new existe, parent du new absent, profondeur dépassée.
    Retourne le nb de rubriques renommées."""
    _check_path(old_path); _check_path(new_path)
    _rid(conn, old_path)
    if rubrics.get_rubric_id(conn, new_path) is not None:
        raise ValueError(f"{new_path!r} existe déjà — utiliser merge")
    new_depth = new_path.count("/")
    if new_depth:
        parent = new_path.rsplit("/", 1)[0]
        if rubrics.get_rubric_id(conn, parent) is None:
            raise ValueError(f"parent inexistant : {parent!r}")
        new_parent_id = rubrics.get_rubric_id(conn, parent)
    else:
        new_parent_id = None
    subtree = _subtree(conn, old_path)
    delta = new_depth - old_path.count("/")
    for _id, p, d in subtree:
        if d + delta > config.RUBRIC_MAX_DEPTH:
            raise ValueError(f"profondeur dépassée pour {p!r}")
    try:
        for _id, p, d in subtree:
            np = new_path + p[len(old_path):]
            conn.execute("UPDATE rubrics SET path=?, depth=? WHERE id=?", (np, d + delta, _id))
        conn.execute("UPDATE rubrics SET parent_id=?, label=COALESCE(label,?) WHERE path=?",
                     (new_parent_id, new_path.rsplit("/", 1)[-1], new_path))
        if _log:
            _log_op(conn, f"rename {old_path} → {new_path}",
                    {"op": "rename", "old": new_path, "new": old_path})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return len(subtree)


def relabel(conn, path, label):
    rid = _rid(conn, path)
    old = conn.execute("SELECT label FROM rubrics WHERE id=?", (rid,)).fetchone()[0]
    try:
        conn.execute("UPDATE rubrics SET label=? WHERE id=?", (label, rid))
        _log_op(conn, f"relabel {path}", {"op": "relabel", "path": path, "label": old})
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def reparent(conn, path, new_parent_path, now):
    """Déplace la branche `path` sous new_parent_path (= rename avec cascade)."""
    _check_path(new_parent_path)
    _rid(conn, new_parent_path)
    leaf = path.rsplit("/", 1)[-1]
    return rename(conn, path, f"{new_parent_path}/{leaf}", now)


def merge(conn, src_path, dst_path, now, _log=True):
    """Fond src dans dst : épisodes ré-attachés (conf conservée), enfants
    reparentés sous dst, src supprimée, centroïde de dst recalculé.
    Tout ou rien. Refuse dst ⊂ src."""
    src_id = _rid(conn, src_path)
    _rid(conn, dst_path)
    if dst_path == src_path or dst_path.startswith(src_path + "/"):
        raise ValueError("dst est src ou un descendant de src")
    eps = conn.execute(
        "SELECT id, rubric_conf FROM episodes WHERE rubric_id=?", (src_id,)).fetchall()
    children = conn.execute(
        "SELECT path FROM rubrics WHERE parent_id=?", (src_id,)).fetchall()
    src_row = conn.execute(
        "SELECT label, kind_hint, created_ts FROM rubrics WHERE id=?", (src_id,)).fetchone()
    try:
        moved_children = 0
        for (child_path,) in children:
            leaf = child_path.rsplit("/", 1)[-1]
            # rename SANS log ni commit individuel : on est dans la tx du merge
            _rename_nocommit(conn, child_path, f"{dst_path}/{leaf}")
            moved_children += 1
        for eid, conf in eps:
            rubrics._attach_core(conn, eid, dst_path, conf if conf is not None else 0.9, now)
        conn.execute("DELETE FROM rubrics WHERE id=?", (src_id,))
        recompute_centroid(conn, dst_path)
        if _log:
            _log_op(conn, f"merge {src_path} → {dst_path}",
                    {"op": "unmerge", "src": src_path, "dst": dst_path,
                     "label": src_row[0], "kind_hint": src_row[1],
                     "created_ts": src_row[2],
                     "episode_ids": [e for e, _c in eps],
                     "children": [f"{dst_path}/{c.rsplit('/', 1)[-1]}" for (c,) in children]})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return {"moved_episodes": len(eps), "moved_children": moved_children}


def _rename_nocommit(conn, old_path, new_path):
    """Cascade de rename SANS commit ni log (sous-opération de merge)."""
    subtree = _subtree(conn, old_path)
    delta = new_path.count("/") - old_path.count("/")
    parent = new_path.rsplit("/", 1)[0] if new_path.count("/") else None
    pid = rubrics.get_rubric_id(conn, parent) if parent else None
    for _id, p, d in subtree:
        if d + delta > config.RUBRIC_MAX_DEPTH:
            raise ValueError(f"profondeur dépassée pour {p!r}")
    for _id, p, d in subtree:
        np = new_path + p[len(old_path):]
        conn.execute("UPDATE rubrics SET path=?, depth=? WHERE id=?", (np, d + delta, _id))
    conn.execute("UPDATE rubrics SET parent_id=? WHERE path=?", (pid, new_path))


def reclassify(conn, episode_id, new_path, now, _log=True):
    """Déplace UNE mémoire vers new_path (conf 1.0 = délibéré) ; None → détache
    (redevient orpheline). Retourne le path final ou 'orphelin'."""
    row = conn.execute(
        "SELECT rubric_id, rubric_conf, embedding FROM episodes WHERE id=?",
        (episode_id,)).fetchone()
    if row is None:
        raise ValueError(f"épisode inexistant : {episode_id}")
    old_rid, old_conf, raw_emb = row
    old_path = None
    if old_rid is not None:
        r = conn.execute("SELECT path FROM rubrics WHERE id=?", (old_rid,)).fetchone()
        old_path = r[0] if r else None
    try:
        if new_path is None:
            if old_rid is not None:
                emb = rubrics._parse_embedding(raw_emb)
                rubrics._detach_from(conn, old_rid, emb)
            conn.execute(
                "UPDATE episodes SET rubric_id=NULL, rubric_conf=NULL, routed_ts=NULL WHERE id=?",
                (episode_id,))
            result = "orphelin"
        else:
            rubrics._attach_core(conn, episode_id, new_path, 1.0, now)
            result = new_path
        if _log:
            _log_op(conn, f"reclassify #{episode_id} → {result}",
                    {"op": "reclassify", "episode_id": episode_id,
                     "path": old_path, "conf": old_conf})
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return result


# ---------- undo (1 cran) ----------

def undo_last(conn):
    """Annule la DERNIÈRE mutation (1 cran). Retourne la description annulée."""
    entries = log_entries(conn)
    if not entries:
        return "(rien à annuler)"
    last = entries.pop()
    inv = last.get("inverse") or {}
    op = inv.get("op")
    try:
        if op == "rename":
            rename(conn, inv["old"], inv["new"], time.time(), _log=False)
        elif op == "relabel":
            rid = _rid(conn, inv["path"])
            conn.execute("UPDATE rubrics SET label=? WHERE id=?", (inv["label"], rid))
        elif op == "unmerge":
            rubrics.rubric_create(conn, inv["src"], inv.get("created_ts") or time.time(),
                                  label=inv.get("label"), kind_hint=inv.get("kind_hint"))
            for child in inv.get("children", []):
                leaf = child.rsplit("/", 1)[-1]
                _rename_nocommit(conn, child, f"{inv['src']}/{leaf}")
            now = time.time()
            for eid in inv.get("episode_ids", []):
                rubrics._attach_core(conn, eid, inv["src"], 0.9, now)
            recompute_centroid(conn, inv["src"])
            recompute_centroid(conn, inv["dst"])
        elif op == "reclassify":
            if inv.get("path") is None:
                reclassify(conn, inv["episode_id"], None, time.time(), _log=False)
            else:
                rubrics._attach_core(conn, inv["episode_id"], inv["path"],
                                     inv.get("conf") if inv.get("conf") is not None else 0.9,
                                     time.time())
        else:
            return "(entrée de journal inconnue — rien annulé)"
        _kv_set(conn, "taxonomy_log", json.dumps(entries, ensure_ascii=False))
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    return f"annulé : {last.get('desc', op)}"
```

- [ ] **Step 6: GREEN** — `pytest tests/test_taxonomy.py -v` → 9 PASS. Ajuster si un test révèle un vrai bug d'implémentation (les assertions du plan sont le contrat).
- [ ] **Step 7: Full suite** — ≥ 382. Attention non-régression : `attach_episode` public committe toujours (tests existants).
- [ ] **Step 8: Commit** — `git commit -m "TAX-1: taxonomy.py — mutations transactionnelles (rename/reparent/merge/reclassify) + journal borné + undo 1 cran + recompute centroïdes"`

---

### Task 2: Surface MCP + `memory_store` révèle le routage + protocole

**Files:**
- Modify: `mcp_server.py` (memory_store ~l.30 + nouveaux outils après rubric_tree), `~/.claude/CLAUDE.md` (§ Pendant le travail)
- Test: `tests/test_taxonomy_mcp.py`

**Interfaces:**
- Consumes: `taxonomy.*` (Task 1), `_mem` global, `time`, pattern `tool.fn` des tests MCP existants (cf. tests/test_wm_boot.py fixture `srv`).
- Produces: outils MCP `rubric_rename(old_path, new_path)`, `rubric_reparent(path, new_parent_path)`, `rubric_merge(src_path, dst_path)`, `memory_reclassify(episode_id: int, new_path: str = "")` ("" → None = détacher), `taxonomy_undo()`, `orphans_report(limit: int = 20)` ; `memory_store` retourne `« … → <path> (conf 0.71) »` ou `« … → ORPHELIN (aucune rubrique assez proche) »`.

- [ ] **Step 1: Write the failing tests** — `tests/test_taxonomy_mcp.py` :

```python
"""Surface MCP de la taxonomie vivante + routage révélé par memory_store."""
import time

import pytest

import migrations
import rubrics
from memory import Memory

NOW = time.time()


@pytest.fixture
def srv(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    import mcp_server
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(mcp_server, "_mem", m)
    monkeypatch.setattr(mcp_server, "_embed", lambda t: [0.5] * 8)
    return mcp_server, m


def _fn(mcp_server, name):
    import asyncio
    tool = asyncio.get_event_loop().run_until_complete(mcp_server.mcp.get_tool(name))
    return tool.fn


def test_memory_store_revele_le_routage(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/alpha", NOW)
    # amorcer le centroïde pour que le routage matche
    eid = m.add("semantic", "seed", importance=0.5, embedding=[0.5] * 8)
    rubrics.attach_episode(m.db, eid, "projets/alpha", 0.9, NOW)
    out = _fn(mcp_server, "memory_store")("nouvelle mémoire du même thème", "semantic", 0.6)
    assert "→" in out and ("projets/alpha" in out or "ORPHELIN" in out)


def test_memory_store_orphelin_annonce(srv):
    mcp_server, m = srv                                    # aucune rubrique à centroïde
    out = _fn(mcp_server, "memory_store")("thème totalement neuf", "semantic", 0.6)
    assert "ORPHELIN" in out


def test_outils_mutations(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    rubrics.rubric_create(m.db, "projets/alpha", NOW)
    rubrics.rubric_create(m.db, "savoir", NOW)
    assert "renommée" in _fn(mcp_server, "rubric_rename")("projets/alpha", "projets/beta").lower() \
        or "beta" in _fn(mcp_server, "rubric_tree")("")
    _fn(mcp_server, "rubric_reparent")("projets/beta", "savoir")
    assert "savoir/beta" in _fn(mcp_server, "rubric_tree")("")
    out = _fn(mcp_server, "taxonomy_undo")()
    assert "annulé" in out.lower()


def test_orphans_report(srv):
    mcp_server, m = srv
    m.add("semantic", "orphelin un contenu batiment", importance=0.5, embedding=[0.5] * 8)
    m.add("semantic", "orphelin deux contenu batiment", importance=0.5, embedding=[0.5] * 8)
    out = _fn(mcp_server, "orphans_report")(20)
    assert "orphelin" in out.lower() and "batiment" in out


def test_memory_reclassify_tool(srv):
    mcp_server, m = srv
    rubrics.rubric_create(m.db, "projets", NOW)
    eid = m.add("semantic", "à ranger", importance=0.5, embedding=[0.5] * 8)
    out = _fn(mcp_server, "memory_reclassify")(eid, "projets")
    assert "projets" in out
    out2 = _fn(mcp_server, "memory_reclassify")(eid, "")
    assert "orphelin" in out2.lower()
```
**Note implémenteur** : vérifier le pattern EXACT d'accès aux tools dans les tests MCP existants (tests/test_wm_boot.py) — si c'est `tool.fn` direct sans asyncio, utiliser ce pattern-là (adapter `_fn`).

- [ ] **Step 2: RED**.

- [ ] **Step 3: Implémenter — mcp_server.py**. (a) `memory_store` : après `inserted`, lire le routage :

```python
    if not inserted:
        return f"Ignoré ({kind}) — quasi-doublon récent, non mémorisé."
    routed = ""
    try:
        row = _mem.db.execute(
            "SELECT r.path, e.rubric_conf FROM episodes e LEFT JOIN rubrics r ON r.id=e.rubric_id "
            "WHERE e.id=?", (inserted,)).fetchone()
        if row and row[0]:
            routed = f" → {row[0]} (conf {row[1]:.2f})"
        else:
            routed = " → ORPHELIN (aucune rubrique assez proche — créer un nœud si thème neuf)"
    except Exception:
        pass
    return f"Mémorisé ({kind}, importance={imp:.2f}){routed}"
```

(b) nouveaux outils (après `rubric_tree`) :

```python
@mcp.tool()
def rubric_rename(old_path: str, new_path: str) -> str:
    """Renomme/déplace une rubrique (cascade sur ses sous-rubriques)."""
    import taxonomy
    n = taxonomy.rename(_mem.db, old_path, new_path, time.time())
    return f"Rubrique renommée : {old_path} → {new_path} ({n} nœud(s), annulable via taxonomy_undo)."


@mcp.tool()
def rubric_reparent(path: str, new_parent_path: str) -> str:
    """Déplace une BRANCHE entière sous un nouveau parent."""
    import taxonomy
    n = taxonomy.reparent(_mem.db, path, new_parent_path, time.time())
    return f"Branche déplacée sous {new_parent_path} ({n} nœud(s), annulable)."


@mcp.tool()
def rubric_merge(src_path: str, dst_path: str) -> str:
    """Fusionne src dans dst (mémoires ré-attachées, centroïde recalculé, src supprimée)."""
    import taxonomy
    r = taxonomy.merge(_mem.db, src_path, dst_path, time.time())
    return (f"Fusion {src_path} → {dst_path} : {r['moved_episodes']} mémoire(s), "
            f"{r['moved_children']} sous-rubrique(s) déplacées (annulable).")


@mcp.tool()
def memory_reclassify(episode_id: int, new_path: str = "") -> str:
    """Déplace UNE mémoire vers une meilleure rubrique (conf 1.0). new_path vide = détacher."""
    import taxonomy
    res = taxonomy.reclassify(_mem.db, int(episode_id), new_path or None, time.time())
    return f"Mémoire #{episode_id} → {res}."


@mcp.tool()
def taxonomy_undo() -> str:
    """Annule la DERNIÈRE mutation de taxonomie (1 cran)."""
    import taxonomy
    return taxonomy.undo_last(_mem.db)


@mcp.tool()
def orphans_report(limit: int = 20) -> str:
    """Les mémoires ORPHELINES (sans rubrique) — matière de l'émergence de nœuds.

    Lecture seule. Chaque ligne : #id · extrait · facettes. Utiliser pour décider
    s'il faut créer un nœud (voir gardes : ≥3 cohérents et distincts la nuit)."""
    rows = _mem.db.execute(
        "SELECT id, content, ts FROM episodes WHERE rubric_id IS NULL "
        "AND role IN ('semantic','episodic','reference','reasoning') "
        "ORDER BY ts DESC LIMIT ?", (max(1, min(50, int(limit))),)).fetchall()
    total = _mem.db.execute(
        "SELECT COUNT(*) FROM episodes WHERE rubric_id IS NULL").fetchone()[0]
    if not rows:
        return f"(aucun orphelin récent — total base : {total})"
    import facets_extract
    lines = [f"{total} orphelin(s) au total ; les {len(rows)} plus récents :"]
    for eid, content, _ts in rows:
        try:
            facets = ",".join(s for s, _w in facets_extract.facets_of(_mem.db, eid)[:3])
        except Exception:
            facets = ""
        snippet = (content or "").replace("\n", " ")[:120]
        lines.append(f"#{eid} · {snippet}" + (f" [{facets}]" if facets else ""))
    return "\n".join(lines)
```

- [ ] **Step 4: GREEN + full suite** (≥ 387).

- [ ] **Step 5: CLAUDE.md** — § « Pendant le travail », ajouter après la ligne memory_store :
> - LIRE le routage retourné par `memory_store` (`→ rubrique (conf)` ou `→ ORPHELIN`). Si ORPHELIN/conf faible ET thème vraiment nouveau et significatif : vérifier l'arbre (`rubric_tree`), créer le nœud AU BON ENDROIT (`rubric_create`, kebab-case, sous le parent logique) et y ranger la mémoire (`memory_reclassify`). Ne pas créer un nœud proche d'un existant (router/fusionner à la place). Le cerveau doit GRANDIR — mais délibérément.
> - Quand un mauvais rangement/nommage apparaît au fil de l'échange : `memory_reclassify` / `rubric_rename` / `rubric_merge` / `rubric_reparent` (tout est annulable : `taxonomy_undo`) — en le disant à l'utilisateur.

- [ ] **Step 6: Commit** — `git commit -m "TAX-2: surface MCP des mutations + orphans_report + memory_store révèle le routage ; protocole de croissance en-session"` (+ edit CLAUDE.md consigné au rapport).

---

### Task 3: Gardes (distinctivité/masse) + jardinage nocturne bridé par le harnais

**Files:**
- Modify: `taxonomy.py` (guard + clusters), `mcp_server.py` (rubric_create gardé), `consolidate.py:29-31` (TOOLS), `consolidate_prompt.txt`
- Test: `tests/test_taxonomy_growth.py`

**Interfaces:**
- Consumes: `rubrics` centroids, `config.TAX_DISTINCT_MAX/TAX_CLUSTER_MIN_SIM/TAX_ORPHAN_MIN`.
- Produces: `taxonomy.distinctiveness_guard(conn, emb) -> (ok: bool, closest_path: str|None, sim: float)` ; `taxonomy.orphan_clusters(conn, min_n=config.TAX_ORPHAN_MIN, min_sim=config.TAX_CLUSTER_MIN_SIM) -> list[{"episode_ids": [...], "coherence": float}]` (clustering glouton par similarité cosinus des embeddings orphelins) ; outil MCP `rubric_create` gagne `seed_episode_id: int = 0` (si fourni : garde de distinctivité sur l'embedding de cet épisode ; refus → message suggérant la rubrique proche ; `force=True` outrepasse) ; `orphans_report` annoté clusters ; TOOLS étendu SANS merge/reparent/undo.

- [ ] **Step 1: Write the failing tests** — `tests/test_taxonomy_growth.py` :

```python
"""Gardes anti-explosion : distinctivité, masse/cohérence des clusters d'orphelins,
allowlist nocturne durcie par le harnais."""
import time

import pytest

import config
import migrations
import rubrics
import taxonomy
from memory import Memory

NOW = time.time()


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_distinctiveness_guard(mem):
    rubrics.rubric_create(mem.db, "projets", NOW)
    eid = mem.add("semantic", "seed", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    rubrics.attach_episode(mem.db, eid, "projets", 0.9, NOW)
    ok, closest, sim = taxonomy.distinctiveness_guard(mem.db, [1.0, 0.01, 0.0, 0.0])
    assert ok is False and closest == "projets" and sim > config.TAX_DISTINCT_MAX
    ok2, _c, _s = taxonomy.distinctiveness_guard(mem.db, [0.0, 1.0, 0.0, 0.0])
    assert ok2 is True                                     # orthogonal = distinct


def test_orphan_clusters_coherent_vs_disperse(mem):
    for i in range(3):                                     # trio cohérent
        mem.add("semantic", f"theme neuf {i}", importance=0.5,
                embedding=[1.0, 0.05 * i, 0.0, 0.0])
    mem.add("semantic", "bruit isolé", importance=0.5, embedding=[0.0, 0.0, 1.0, 0.0])
    clusters = taxonomy.orphan_clusters(mem.db)
    assert len(clusters) == 1                              # le trio, pas le bruit
    assert len(clusters[0]["episode_ids"]) == 3
    assert clusters[0]["coherence"] >= config.TAX_CLUSTER_MIN_SIM


def test_rubric_create_mcp_garde(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.5] * 8)
    import mcp_server
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(mcp_server, "_mem", m)
    rubrics.rubric_create(m.db, "projets", NOW)
    eid = m.add("semantic", "seed", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    rubrics.attach_episode(m.db, eid, "projets", 0.9, NOW)
    near = m.add("semantic", "quasi pareil", importance=0.5, embedding=[1.0, 0.01, 0.0, 0.0])
    create = mcp_server.rubric_create.fn if hasattr(mcp_server.rubric_create, "fn") else mcp_server.rubric_create
    out = create("savoir", seed_episode_id=near)           # trop proche de 'projets'
    assert "proche" in out.lower() and rubrics.get_rubric_id(m.db, "savoir") is None
    out2 = create("savoir", seed_episode_id=near, force=True)
    assert rubrics.get_rubric_id(m.db, "savoir") is not None


def test_allowlist_nocturne_durcie():
    import consolidate
    tools = consolidate.TOOLS
    for must in ("orphans_report", "rubric_tree", "rubric_create", "memory_reclassify"):
        assert must in tools
    for banned in ("rubric_merge", "rubric_reparent", "taxonomy_undo"):
        assert banned not in tools                          # opérations lourdes IMPOSSIBLES la nuit
```
**Note implémenteur** : l'accès au tool MCP dans test_rubric_create_mcp_garde doit suivre le pattern des tests MCP existants — adapter si `tool.fn` se prend autrement.

- [ ] **Step 2: RED**.

- [ ] **Step 3: taxonomy.py — guard + clusters** :

```python
def _cosine(a, b):
    if not a or not b or len(a) != len(b):
        return 0.0
    dot = sum(x * y for x, y in zip(a, b))
    na = sum(x * x for x in a) ** 0.5
    nb = sum(y * y for y in b) ** 0.5
    return dot / (na * nb) if na and nb else 0.0


def distinctiveness_guard(conn, emb):
    """(ok, closest_path, sim) — ok=False si emb est trop proche (> TAX_DISTINCT_MAX)
    du centroïde d'une rubrique existante : router/fusionner plutôt que créer."""
    best_path, best_sim = None, 0.0
    for path, raw in conn.execute(
            "SELECT path, centroid FROM rubrics WHERE centroid IS NOT NULL").fetchall():
        sim = _cosine(rubrics._parse_embedding(raw), emb)
        if sim > best_sim:
            best_path, best_sim = path, sim
    return (best_sim <= config.TAX_DISTINCT_MAX), best_path, best_sim


def orphan_clusters(conn, min_n=None, min_sim=None):
    """Clusters cohérents parmi les orphelins (glouton par similarité).
    Retourne [{"episode_ids": [...], "coherence": moyenne des sims au medoid}]
    — seuls les clusters de taille >= min_n et cohérence >= min_sim sortent."""
    min_n = min_n or config.TAX_ORPHAN_MIN
    min_sim = min_sim or config.TAX_CLUSTER_MIN_SIM
    rows = conn.execute(
        "SELECT id, embedding FROM episodes WHERE rubric_id IS NULL "
        "AND role IN ('semantic','episodic','reference','reasoning')").fetchall()
    items = [(eid, rubrics._parse_embedding(raw)) for eid, raw in rows]
    items = [(eid, e) for eid, e in items if e]
    used, clusters = set(), []
    for i, (eid, emb) in enumerate(items):
        if eid in used:
            continue
        members = [(eid, 1.0)]
        for ej, ee in items[i + 1:]:
            if ej in used:
                continue
            s = _cosine(emb, ee)
            if s >= min_sim:
                members.append((ej, s))
        if len(members) >= min_n:
            for m_id, _s in members:
                used.add(m_id)
            coh = sum(s for _m, s in members) / len(members)
            clusters.append({"episode_ids": [m for m, _s in members],
                             "coherence": round(coh, 4)})
    return clusters
```

- [ ] **Step 4: mcp_server.py — `rubric_create` gardé** (remplacer le corps existant) :

```python
@mcp.tool()
def rubric_create(path: str, label: str = "", kind_hint: str = "",
                  seed_episode_id: int = 0, force: bool = False) -> str:
    """Crée une rubrique dans la hiérarchie (ex. 'projets/anamnese/memoire-2.0').

    Le parent doit exister. Si seed_episode_id est fourni, une GARDE de
    distinctivité vérifie que le thème n'est pas déjà couvert par une rubrique
    existante (→ suggérée à la place ; force=True pour outrepasser).
    """
    import taxonomy
    if seed_episode_id and not force:
        row = _mem.db.execute("SELECT embedding FROM episodes WHERE id=?",
                              (int(seed_episode_id),)).fetchone()
        if row:
            emb = rubrics._parse_embedding(row[0])
            ok, closest, sim = taxonomy.distinctiveness_guard(_mem.db, emb)
            if not ok:
                return (f"NON créée : thème trop proche de '{closest}' (sim {sim:.2f} > "
                        f"{config.TAX_DISTINCT_MAX}). Ranger là-bas (memory_reclassify) "
                        f"ou force=True si c'est VRAIMENT distinct.")
    rid = rubrics.rubric_create(
        _mem.db, path, now=time.time(), label=label or None, kind_hint=kind_hint or None
    )
    return f"Rubrique '{path}' prête (id={rid})."
```
(import config déjà présent en tête de mcp_server ; vérifier, sinon l'ajouter.)

- [ ] **Step 5: `orphans_report` annoté** — dans le tool (Task 2), après la liste, appendre les clusters :

```python
    try:
        import taxonomy
        cl = taxonomy.orphan_clusters(_mem.db)
        for c in cl:
            lines.append(f"CLUSTER cohérent ({c['coherence']:.2f}) : "
                         + ", ".join(f"#{i}" for i in c["episode_ids"])
                         + " → candidat à un NOUVEAU nœud")
    except Exception:
        pass
```

- [ ] **Step 6: consolidate.py TOOLS** (l.29-31) :

```python
TOOLS = ("mcp__anamnese__memory_recent,mcp__anamnese__memory_recall,mcp__anamnese__memory_store,"
         "mcp__anamnese__self_get,mcp__anamnese__self_update,mcp__anamnese__affect_event,"
         "mcp__anamnese__reasoning_recall,mcp__anamnese__orphans_report,"
         "mcp__anamnese__rubric_tree,mcp__anamnese__rubric_create,mcp__anamnese__memory_reclassify")
```
(JAMAIS rubric_merge/rubric_reparent/taxonomy_undo — l'interdiction nocturne est dans le HARNAIS.)

- [ ] **Step 7: consolidate_prompt.txt** — ajouter l'étape (après l'étape RÊVE existante) :

```
5. JARDINAGE : mcp__anamnese__orphans_report — si un CLUSTER cohérent (≥3) apparaît ET qu'aucune rubrique existante ne couvre le thème (vérifier mcp__anamnese__rubric_tree) : créer la rubrique (mcp__anamnese__rubric_create, path kebab-case court, sous le parent logique projets/savoir/personnel..., avec seed_episode_id d'un épisode du cluster) puis ranger les orphelins du cluster dedans (mcp__anamnese__memory_reclassify un par un). Ne JAMAIS créer pour moins de 3, ni un thème déjà couvert. Renommer un label trompeur est permis ; fusion et reparent sont INTERDITS la nuit. Consigner dans la TRACE ce qui a été créé.
```
(le numéro « 5. » à adapter à la numérotation réelle du prompt — le lire d'abord.)

- [ ] **Step 8: GREEN + full suite** (≥ 391).
- [ ] **Step 9: Commit** — `git commit -m "TAX-3: gardes distinctivité/masse + clusters d'orphelins + jardinage nocturne (allowlist durcie: ops lourdes impossibles la nuit)"`

---

### Task 4: Cockpit — l'arbre qui grandit (vue Mémoire)

**Files:**
- Modify: `~/AIOS/cockpit/server.js` (nouvel endpoint, après /api/analytics), `~/AIOS/cockpit/public/memory.js` (carte dans renderAnalytics)
- (cockpit NON-git : backup léger `cp server.js server.js.backup-pre-tax` ; append `.v2-report.md`)

**Interfaces:**
- Consumes: helper `sqlite(query)`, `j()`, `esc()` côté client.
- Produces: `GET /api/rubrics` → `{rows: [{path, label, depth, memory_count, created_ts}]}` (ORDER BY path) ; carte « 🌳 ARBRE DES RUBRIQUES » dans l'onglet Analytique (indentation par depth, compteur, date de création — les nœuds < 7 jours badgés « nouveau »).

- [ ] **Step 1: server.js** :

```js
  if (p === '/api/rubrics') {
    // Taxonomie vivante : l'arbre + compteurs + dates (voir le cerveau grandir). Lecture seule.
    const rows = await sqlite(
      'SELECT path, label, depth, memory_count, created_ts FROM rubrics ORDER BY path;');
    res.writeHead(200, { 'Content-Type': 'application/json' });
    return res.end(j({ rows: rows || [] }));
  }
```

- [ ] **Step 2: memory.js — dans renderAnalytics()**, ajouter (avant l'assemblage final) :

```js
  let arbre = '';
  try {
    const rub = await (await fetch('/api/rubrics')).json();
    const now = Date.now() / 1000;
    arbre = chartCard('🌳 ARBRE DES RUBRIQUES', `· ${(rub.rows || []).length} nœuds — le cerveau qui grandit`,
      (rub.rows || []).map(r => `
        <div style="display:flex;gap:8px;align-items:center;font-size:10.5px;margin:2px 0;padding-left:${r.depth * 16}px;">
          <span style="color:${r.depth === 0 ? 'var(--teal-hi)' : 'var(--txt-2)'};">${r.depth === 0 ? '◈' : '└'} ${esc(r.path.split('/').pop())}</span>
          ${now - (r.created_ts || 0) < 7 * 86400 ? '<span class="badge ok" style="font-size:7px;padding:0 6px;">nouveau</span>' : ''}
          <span style="color:var(--txt-4);margin-left:auto;">${r.memory_count} souvenir(s)</span>
        </div>`).join('') || '<div class="kv">(arbre vide)</div>');
  } catch (_) {}
  $('charts').innerHTML = humeur + croissance + facettes + rubriques + roles + reves + arbre;
```
(remplacer la ligne d'assemblage existante ; `esc()` obligatoire sur path.)

- [ ] **Step 3: Verify** — Playwright : `/memory` onglet Analytique → l'arbre s'affiche (15 nœuds actuels, indentés), zéro erreur console. curl `/api/rubrics` → JSON.
- [ ] **Step 4: Append `.v2-report.md`** (section taxonomie).

---

### Task 5: Merge + déploiement

- [ ] Full suite verte (≥ 391). `git checkout main && git merge --no-ff taxonomie-vivante`.
- [ ] Relancer le daemon (`launchctl kickstart -k gui/$(id -u)/com.anamnese.daemon`).
- [ ] NOTE : les nouveaux outils MCP n'apparaissent dans les sessions Claude Code qu'à la (re)connexion du serveur MCP anamnese — le signaler à Ahmed.
- [ ] Vérif réelle : `sqlite3 -readonly data/memory.db "SELECT COUNT(*) FROM rubrics"` avant/après un test de création via CLI python (DB RÉELLE : uniquement une création + undo immédiat, en le disant) OU laisser la première vraie création se faire naturellement en session.
- [ ] Ledger + rapport.
