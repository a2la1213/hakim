"""Tests de Memory.store_in + retrieve(rubric=) — rappel par tranche (Phase 1D).

DB temporaire migrée + squelette seedé — JAMAIS data/memory.db (garde autouse
dans conftest.py). Embeddings synthétiques 2D écrits à la main : aucun modèle
chargé, tout est déterministe.
"""

import time

import pytest

import migrations
import rubrics
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire, migrée 2.0 + squelette de rubriques."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    yield m
    m.db.close()


def _seed_slices(mem):
    """2 tranches (projets/*, savoir-applecture) + 1 épisode jamais routé.

    Depuis le routage LIVE, add() route À L'ÉCRITURE tout épisode À embedding
    non vide (les store_in ci-dessus ont construit les centroïdes) : pour
    rester « jamais routé », l'épisode témoin est SANS embedding (le routage
    live le saute par construction — centroïde impossible)."""
    mem.store_in("anamnese memoire rubriques", "projets/anamnese", embedding=[1.0, 0.0])
    mem.store_in("atelier3d pricing stripe", "projets/atelier3d", embedding=[0.9, 0.1])
    mem.store_in("tafsir sourate applecture", "savoir-applecture", embedding=[0.0, 1.0])
    mem.add("user", "episode jamais route")


# --- Cas 1 : store_in — épisode créé + rattaché (conf 1.0), ValueError sinon ---
def test_store_in_creates_and_attaches(mem):
    eid = mem.store_in(
        "decision memoire 2.0",
        "projets/anamnese",
        role="semantic",
        importance=0.8,
        embedding=[1.0, 0.0],
    )
    assert isinstance(eid, int)

    row = mem.db.execute(
        "SELECT role, content, importance, rubric_id, rubric_conf, routed_ts "
        "FROM episodes WHERE id=?",
        (eid,),
    ).fetchone()
    rid = rubrics.get_rubric_id(mem.db, "projets/anamnese")
    assert row[:5] == ("semantic", "decision memoire 2.0", 0.8, rid, 1.0)
    assert row[5] is not None  # routed_ts posé

    # memory_count incrémenté + centroïde nourri par l'embedding fourni
    count, centroid_n = mem.db.execute(
        "SELECT memory_count, centroid_n FROM rubrics WHERE id=?", (rid,)
    ).fetchone()
    assert count == 1 and centroid_n == 1


def test_store_in_defaults_and_no_embedding(mem):
    eid = mem.store_in("fait sans embedding", "technique-transverse")
    role, imp, conf = mem.db.execute(
        "SELECT role, importance, rubric_conf FROM episodes WHERE id=?", (eid,)
    ).fetchone()
    assert (role, imp, conf) == ("semantic", 0.5, 1.0)
    # rattaché (memory_count) mais centroïde intact (embedding vide = no-op sûr)
    count, centroid_n = mem.db.execute(
        "SELECT memory_count, centroid_n FROM rubrics WHERE path=?",
        ("technique-transverse",),
    ).fetchone()
    assert count == 1 and centroid_n == 0


def test_store_in_unknown_rubric_raises_without_orphan(mem):
    with pytest.raises(ValueError):
        mem.store_in("x", "rubrique/inconnue")
    assert mem.count() == 0  # pas d'épisode orphelin inséré avant l'échec


def test_store_in_clamps_importance(mem):
    """store_in borne importance à [0,1] — seul chemin d'écriture qui ne
    clampait pas (memory_store/cli/loop le font). Une importance hors bornes
    (ex. 10) serait durable et noierait la pertinence au rappel."""
    eid_hi = mem.store_in("importance trop haute", "projets/anamnese", importance=10)
    eid_lo = mem.store_in("importance negative", "projets/anamnese", importance=-5)
    imp_hi = mem.db.execute(
        "SELECT importance FROM episodes WHERE id=?", (eid_hi,)
    ).fetchone()[0]
    imp_lo = mem.db.execute(
        "SELECT importance FROM episodes WHERE id=?", (eid_lo,)
    ).fetchone()[0]
    assert imp_hi == 1.0
    assert imp_lo == 0.0


# --- Cas 2 : retrieve(rubric=) — filtre au sous-arbre ; sans rubric, inchangé ---
def test_retrieve_rubric_filters_to_subtree(mem):
    _seed_slices(mem)

    res = mem.retrieve("memoire", [1.0, 0.0], rubric="projets")
    contents = [r[3] for r in res]
    assert "anamnese memoire rubriques" in contents
    assert "atelier3d pricing stripe" in contents  # descendant du sous-arbre
    assert all("applecture" not in c for c in contents)  # autre tranche exclue
    assert all("jamais route" not in c for c in contents)  # non routé exclu

    # sous-arbre plus fin : une seule tranche
    res_fin = mem.retrieve("memoire", [1.0, 0.0], rubric="projets/anamnese")
    assert [r[3] for r in res_fin] == ["anamnese memoire rubriques"]


def test_retrieve_without_rubric_unchanged(mem):
    _seed_slices(mem)
    now = time.time()

    default = mem.retrieve("memoire", [1.0, 0.0], now=now)
    explicit_none = mem.retrieve("memoire", [1.0, 0.0], now=now, rubric=None)
    assert default == explicit_none  # défaut None = comportement historique

    # tous les épisodes restent candidats (y compris le non routé)
    contents = {r[3] for r in default}
    assert contents == {
        "anamnese memoire rubriques",
        "atelier3d pricing stripe",
        "tafsir sourate applecture",
        "episode jamais route",
    }


def test_retrieve_unknown_rubric_raises(mem):
    _seed_slices(mem)
    with pytest.raises(ValueError):
        mem.retrieve("memoire", [1.0, 0.0], rubric="rubrique-inconnue")


# --- Cas 3 : non-régression d'arité — tuples à 5 éléments, avec et sans rubric ---
def test_retrieve_tuple_arity_is_five(mem):
    _seed_slices(mem)

    plain = mem.retrieve("memoire", [1.0, 0.0])
    sliced = mem.retrieve("memoire", [1.0, 0.0], rubric="projets")
    assert plain and sliced
    for row in plain + sliced:
        s, ts, role, content, parts = row  # déballage strict : 5 éléments
        assert isinstance(s, float)
        assert isinstance(ts, float)
        assert isinstance(role, str)
        assert isinstance(content, str)
        assert set(parts) == {"rel", "lex", "rec"}
