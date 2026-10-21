"""Tests de la reconsolidation bornée (Phase R1) — retrieve(reconsolidate=).

Effet de test : les épisodes RÉELLEMENT renvoyés par un rappel explicite
(reconsolidate=True) sont renforcés — spacing-aware (pas de re-bump dans
RECONSOLIDATE_SPACING), plafonné (RECONSOLIDATE_CAP), incrément décroissant
(RECONSOLIDATE_STEP / (1 + recall_count)). Le défaut reconsolidate=False est
STRICTEMENT lecture seule (harness/éval et appelants existants intacts).

DB temporaire migrée + embeddings synthétiques 2D — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est déterministe (now explicite).
"""

import time

import pytest

import config
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (colonnes recall_count/last_recall_ts)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _seed(mem):
    """3 épisodes : 2 proches de la requête 'memoire' [1,0], 1 orthogonal (hors top_k)."""
    a = mem.add("semantic", "memoire rubriques anamnese", importance=0.5,
                embedding=[1.0, 0.0], extract_facets=False)
    b = mem.add("semantic", "memoire consolidation sommeil", importance=0.5,
                embedding=[0.9, 0.1], extract_facets=False)
    c = mem.add("semantic", "tafsir sourate coran", importance=0.5,
                embedding=[0.0, 1.0], extract_facets=False)
    return a, b, c


def _state(mem, eid):
    """(importance, recall_count, last_recall_ts) d'un épisode."""
    return mem.db.execute(
        "SELECT importance, recall_count, last_recall_ts FROM episodes WHERE id=?",
        (eid,),
    ).fetchone()


# --- Cas 1 : défaut reconsolidate=False = STRICTEMENT lecture seule ---
def test_default_is_strictly_readonly(mem):
    a, b, c = _seed(mem)
    before = mem.db.execute(
        "SELECT id, importance, recall_count, last_recall_ts FROM episodes ORDER BY id"
    ).fetchall()
    changes0 = mem.db.total_changes

    res = mem.retrieve("memoire", [1.0, 0.0], top_k=2)  # défaut = pas de kwarg

    assert mem.db.total_changes == changes0  # AUCUNE écriture
    after = mem.db.execute(
        "SELECT id, importance, recall_count, last_recall_ts FROM episodes ORDER BY id"
    ).fetchall()
    assert after == before
    assert res
    for row in res:
        s, ts, role, content, parts = row  # arité 5
        assert len(row) == 5


# --- Cas 2 : reconsolidate=True bump le top_k renvoyé, PAS le reste ---
def test_reconsolidate_bumps_topk_only(mem):
    a, b, c = _seed(mem)
    now = time.time()

    res = mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=2, reconsolidate=True)
    assert {r[3] for r in res} == {
        "memoire rubriques anamnese", "memoire consolidation sommeil"
    }

    for eid in (a, b):
        imp, rc, lrt = _state(mem, eid)
        assert rc == 1
        assert lrt == now
        assert imp == pytest.approx(0.5 + config.RECONSOLIDATE_STEP)  # 0.55
        assert imp <= config.RECONSOLIDATE_CAP

    # HORS top_k : strictement inchangé
    assert _state(mem, c) == (0.5, 0, None)


# --- Cas 3 : spacing — pas de re-bump immédiat ; re-bump après SPACING ---
def test_spacing_no_immediate_rebump_then_rebump(mem):
    a, b, c = _seed(mem)
    now = time.time()

    mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=2, reconsolidate=True)
    state1 = _state(mem, a)
    assert state1[1] == 1  # recall_count après 1er bump

    # 2e rappel IMMÉDIAT (now + 1 <= SPACING) : rien ne bouge
    mem.retrieve("memoire", [1.0, 0.0], now=now + 1, top_k=2, reconsolidate=True)
    assert _state(mem, a) == state1
    assert _state(mem, b)[1] == 1

    # 3e rappel ESPACÉ (> SPACING) : re-bump
    later = now + config.RECONSOLIDATE_SPACING + 400  # now + 4000
    mem.retrieve("memoire", [1.0, 0.0], now=later, top_k=2, reconsolidate=True)
    imp, rc, lrt = _state(mem, a)
    assert rc == 2
    assert lrt == later
    assert imp > state1[0]


# --- Cas 4 : incrément DÉCROISSANT — le 2e gain (espacé) < le 1er ---
def test_decreasing_increment(mem):
    a, b, c = _seed(mem)
    now = time.time()
    imp0 = _state(mem, a)[0]

    mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=2, reconsolidate=True)
    imp1 = _state(mem, a)[0]
    gain1 = imp1 - imp0

    mem.retrieve("memoire", [1.0, 0.0],
                 now=now + config.RECONSOLIDATE_SPACING + 400,
                 top_k=2, reconsolidate=True)
    imp2 = _state(mem, a)[0]
    gain2 = imp2 - imp1

    assert gain1 == pytest.approx(config.RECONSOLIDATE_STEP)          # 0.05
    assert gain2 == pytest.approx(config.RECONSOLIDATE_STEP / 2)      # 0.025
    assert 0 < gain2 < gain1


# --- Cas 5 : plafond — jamais au-dessus de 0.9 ; jamais RABAISSÉ non plus ---
def test_cap_never_exceeded_never_lowered(mem):
    near_cap = mem.add("semantic", "memoire importante", importance=0.89,
                       embedding=[1.0, 0.0], extract_facets=False)
    above_cap = mem.add("semantic", "tafsir essentiel", importance=0.95,
                        embedding=[0.0, 1.0], extract_facets=False)
    now = time.time()

    # 0.89 -> plafonné à 0.9, pas 0.94
    mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=1, reconsolidate=True)
    imp, rc, _ = _state(mem, near_cap)
    assert imp == pytest.approx(config.RECONSOLIDATE_CAP)
    assert rc == 1

    # re-bump espacé : toujours 0.9, jamais au-dessus
    mem.retrieve("memoire", [1.0, 0.0],
                 now=now + config.RECONSOLIDATE_SPACING + 400,
                 top_k=1, reconsolidate=True)
    imp, rc, _ = _state(mem, near_cap)
    assert imp <= config.RECONSOLIDATE_CAP
    assert imp == pytest.approx(config.RECONSOLIDATE_CAP)
    assert rc == 2

    # au-dessus du cap (0.95) : le plafond borne le GAIN, il ne rabaisse pas
    mem.retrieve("tafsir", [0.0, 1.0], now=now, top_k=1, reconsolidate=True)
    imp, rc, _ = _state(mem, above_cap)
    assert imp == pytest.approx(0.95)  # inchangée (pas de baisse à 0.9)
    assert rc == 1                     # mais le rappel est bien compté


# --- Cas 6 : rétro-compat legacy — DB sans recall_count => lecture seule, sans lever ---
def test_legacy_db_degrades_to_readonly(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    try:
        cols = {r[1] for r in m.db.execute("PRAGMA table_info(episodes)").fetchall()}
        assert "recall_count" not in cols  # bien un schéma d'avant 2.0

        res = m.retrieve("bonjour", None, reconsolidate=True)  # ne lève PAS

        assert res  # le rappel fonctionne
        for row in res:
            s, ts, role, content, parts = row  # arité 5 conservée
        # lecture seule : importances seed intactes, aucune colonne apparue
        assert [r[0] for r in m.db.execute(
            "SELECT importance FROM episodes ORDER BY id"
        ).fetchall()] == [0.5, 0.7]
        cols_after = {r[1] for r in m.db.execute("PRAGMA table_info(episodes)").fetchall()}
        assert cols_after == cols
    finally:
        m.db.close()


# --- Cas 7 : arité 5 prouvée dans les DEUX modes ---
def test_arity_five_in_both_modes(mem):
    _seed(mem)
    for reconsolidate in (False, True):
        rows = mem.retrieve("memoire", [1.0, 0.0], top_k=3,
                            reconsolidate=reconsolidate)
        assert rows
        for row in rows:
            s, ts, role, content, parts = row  # déballage strict : 5 éléments
            assert isinstance(s, float)
            assert isinstance(ts, float)
            assert isinstance(role, str)
            assert isinstance(content, str)
            assert set(parts) == {"rel", "lex", "rec"}
