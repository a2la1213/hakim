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


# --- Cas adversariaux (self-review) : collisions, sous-arbre, racine, vide ---

def test_merge_collision_enfant(mem):
    """dst a déjà un enfant du même nom → refus AVANT toute écriture."""
    _mk(mem, "projets/a/sub")
    _mk(mem, "projets/b/sub")
    with pytest.raises(ValueError):
        taxonomy.merge(mem.db, "projets/a", "projets/b", NOW)
    # rien n'a bougé
    assert rubrics.get_rubric_id(mem.db, "projets/a") is not None
    assert rubrics.get_rubric_id(mem.db, "projets/a/sub") is not None


def test_rename_refuse_dans_son_sous_arbre(mem):
    """new_path DANS le sous-arbre de old_path → paths orphelins, refusé."""
    _mk(mem, "projets/a/sub")
    with pytest.raises(ValueError):
        taxonomy.rename(mem.db, "projets/a", "projets/a/sub/x", NOW)
    with pytest.raises(ValueError):
        taxonomy.reparent(mem.db, "projets/a", "projets/a/sub", NOW)
    # rien n'a bougé
    assert rubrics.get_rubric_id(mem.db, "projets/a/sub") is not None


def test_rename_racine(mem):
    """Rename d'un path racine (depth 0) : cascade, parent_id NULL conservé."""
    _mk(mem, "projets/alpha")
    n = taxonomy.rename(mem.db, "projets", "travaux", NOW)
    assert n == 2
    row = mem.db.execute(
        "SELECT parent_id, depth FROM rubrics WHERE path='travaux'").fetchone()
    assert row == (None, 0)
    assert rubrics.get_rubric_id(mem.db, "travaux/alpha") is not None


def test_merge_rubrique_vide_et_undo(mem):
    """Merge d'une rubrique VIDE : 0 déplacé, src supprimée, undo la recrée."""
    _mk(mem, "projets/a")
    _mk(mem, "projets/b")
    r = taxonomy.merge(mem.db, "projets/a", "projets/b", NOW)
    assert r == {"moved_episodes": 0, "moved_children": 0}
    assert rubrics.get_rubric_id(mem.db, "projets/a") is None
    assert "merge" in taxonomy.undo_last(mem.db)
    assert rubrics.get_rubric_id(mem.db, "projets/a") is not None


def test_undo_journal_hostile_purge_sans_exception(mem):
    """Rider T1 : kv['taxonomy_log'] de forme hostile (JSON valide mais
    entrée non-dict '[42]', ou inverse non-dict) → undo_last ne lève PAS,
    retourne un message propre et PURGE l'entrée toxique — jamais wedgé."""
    for hostile in ("[42]", json.dumps([{"desc": "x", "inverse": "boom"}])):
        mem.db.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
                       ("taxonomy_log", hostile, NOW))
        mem.db.commit()
        out = taxonomy.undo_last(mem.db)                   # AVANT le fix : AttributeError
        assert "inconnue" in out                           # message propre
        assert taxonomy.log_entries(mem.db) == []          # entrée toxique purgée
    assert taxonomy.undo_last(mem.db) == "(rien à annuler)"
