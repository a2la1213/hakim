"""Tests des voies de co-activation (Cerveau 3D P1) — LTP entre souvenirs.

Deux souvenirs co-remontés dans le MÊME rappel (retrieve(reconsolidate=True),
la voie memory_recall MCP) ou co-consolidés dans le MÊME rêve renforcent leur
arête non orientée (ordre canonique a_id < b_id) : weight = min(COACT_CAP,
weight + COACT_BOOST). Les voies inutilisées décroissent (demi-vie
COACT_HALFLIFE_H) et sont élaguées sous COACT_PRUNE (élagage synaptique).
Le rappel lecture-seule par défaut (reconsolidate=False) ne logue RIEN.

DB temporaire migrée + embeddings synthétiques 2D — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import sqlite3
import time

import pytest

import config
import daemon
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (table coactivation présente)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _edges(mem):
    """{(a_id, b_id): (weight, last_ts)} — l'état complet de la table."""
    return {
        (a, b): (w, ts)
        for a, b, w, ts in mem.db.execute(
            "SELECT a_id, b_id, weight, last_ts FROM coactivation"
        ).fetchall()
    }


def _seed_episodes(mem):
    """3 épisodes : 2 proches de la requête 'memoire' [1,0], 1 orthogonal."""
    a = mem.add("semantic", "memoire rubriques anamnese", importance=0.5,
                embedding=[1.0, 0.0], extract_facets=False)
    b = mem.add("semantic", "memoire consolidation sommeil", importance=0.5,
                embedding=[0.9, 0.1], extract_facets=False)
    c = mem.add("semantic", "tafsir sourate coran", importance=0.5,
                embedding=[0.0, 1.0], extract_facets=False)
    return a, b, c


# --- Cas 1 : schéma — table coactivation créée par migrate, idempotent ---
def test_schema_coactivation_table_and_idempotence(tmp_db):
    migrations.migrate(tmp_db)

    tables = {
        r[0] for r in tmp_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert "coactivation" in tables
    cols = {row[1]: row for row in tmp_db.execute("PRAGMA table_info(coactivation)")}
    assert set(cols) == {"a_id", "b_id", "weight", "last_ts"}
    indexes = {
        r[0] for r in tmp_db.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }
    assert "idx_coact_b" in indexes

    second = migrations.migrate(tmp_db)  # 2e migrate : AUCUNE erreur, rien à faire
    assert second["tables_created"] == []
    assert second["columns_added"] == []


# --- Cas 2 : log_coactivation — paires canoniques, boost, cap, no-op < 2 ids ---
def test_log_coactivation_pairs_boost_cap_canonical(mem):
    now = 1000.0

    n = mem.log_coactivation([1, 2, 3], now)
    assert n == 3  # C(3,2) : 1-2, 1-3, 2-3
    edges = _edges(mem)
    assert set(edges) == {(1, 2), (1, 3), (2, 3)}  # ordre canonique a < b
    for w, ts in edges.values():
        assert w == pytest.approx(config.COACT_BOOST)
        assert ts == now

    # ré-appel : le poids AUGMENTE (LTP), plafonné à COACT_CAP
    mem.log_coactivation([1, 2, 3], now + 10)
    assert _edges(mem)[(1, 2)][0] == pytest.approx(2 * config.COACT_BOOST)
    for _ in range(20):
        mem.log_coactivation([1, 2, 3], now + 20)
    for w, _ts in _edges(mem).values():
        assert w == pytest.approx(config.COACT_CAP)  # jamais au-dessus du cap

    # < 2 ids (après dédup) : no-op, 0 paire
    before = _edges(mem)
    assert mem.log_coactivation([5], now) == 0
    assert mem.log_coactivation([5, 5], now) == 0
    assert mem.log_coactivation([], now) == 0
    assert _edges(mem) == before

    # ordre NON canonique en entrée : stocké (min, max), jamais de doublon miroir
    assert mem.log_coactivation([3, 1], now + 30) == 1
    edges = _edges(mem)
    assert (3, 1) not in edges
    assert edges[(1, 3)][1] == now + 30
    assert mem.log_coactivation([9, 4], now + 30) == 1
    assert (4, 9) in _edges(mem)


# --- Cas 3 : decay_coactivation — demi-vie + élagage sous COACT_PRUNE ---
def test_decay_halflife_and_prune(mem):
    now = 1_000_000.0
    one_halflife_ago = now - config.COACT_HALFLIFE_H * 3600.0
    mem.db.execute(
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (1,2,0.4,?)",
        (one_halflife_ago,),
    )
    mem.db.execute(  # 0.08 -> 0.04 après une demi-vie : sous COACT_PRUNE=0.05
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (1,3,0.08,?)",
        (one_halflife_ago,),
    )
    mem.db.commit()

    res = mem.decay_coactivation(now)

    assert res == {"decayed": 1, "pruned": 1}
    edges = _edges(mem)
    assert set(edges) == {(1, 2)}          # l'arête faible a été SUPPRIMÉE
    w, ts = edges[(1, 2)]
    assert w == pytest.approx(0.2)         # 0.4 * 0.5^(336h/336h)
    assert ts == now                       # last_ts avancé : décroissance idempotente


# --- Cas 4 : câblage retrieve — co-activation SEULEMENT si reconsolidate=True ---
def test_retrieve_logs_coactivation_only_when_reconsolidating(mem):
    a, b, c = _seed_episodes(mem)
    now = time.time()

    # défaut lecture seule : AUCUNE écriture, AUCUNE arête
    changes0 = mem.db.total_changes
    res = mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=2)
    assert res
    assert mem.db.total_changes == changes0
    assert _edges(mem) == {}

    # reconsolidate=True (voie memory_recall) : arête entre les épisodes du top_k
    mem.retrieve("memoire", [1.0, 0.0], now=now, top_k=2, reconsolidate=True)
    edges = _edges(mem)
    assert set(edges) == {(min(a, b), max(a, b))}  # paires du top_k SEULEMENT
    w, ts = edges[(min(a, b), max(a, b))]
    assert w == pytest.approx(config.COACT_BOOST)
    assert ts == now
    assert not any(c in pair for pair in edges)    # c (hors top_k) : aucune arête


# --- Cas 5 : arité retrieve inchangée (5) dans les DEUX modes ---
def test_retrieve_arity_five_in_both_modes(mem):
    _seed_episodes(mem)
    for reconsolidate in (False, True):
        rows = mem.retrieve("memoire", [1.0, 0.0], top_k=3,
                            reconsolidate=reconsolidate)
        assert rows
        for row in rows:
            s, ts, role, content, parts = row  # déballage strict : 5 éléments
            assert len(row) == 5
            assert set(parts) == {"rel", "lex", "rec"}


# --- Cas 6 : legacy — DB sans table coactivation => aucune exception ---
def test_legacy_db_without_coactivation_table_is_safe(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    try:
        tables = {
            r[0] for r in m.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "coactivation" not in tables  # bien un schéma d'avant P1

        n = m.log_coactivation([1, 2], 1000.0)       # ne lève PAS
        res = m.decay_coactivation(1000.0)           # ne lève PAS

        assert n == 0
        assert res == {"decayed": 0, "pruned": 0}
        tables_after = {
            r[0] for r in m.db.execute("SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert tables_after == tables  # skip silencieux : aucune table apparue
    finally:
        m.db.close()


# --- Cas 7 : câblage dream — co-activation des graines CHOISIES + décroissance, garde-fous intacts ---
class _FakeEng:
    """Moteur factice OFFLINE : health OK, sorties canoniques en séquence
    (format REM à choix libre : le réel choisit les 3 graines, le jumeau aucune)."""
    def __init__(self):
        self.outs = [
            "###CHOIX###\n- G1\n- G2\n- G3\n###REVE###\n"
            "- Peut-être que ces messages sur la mémoire forment un même fil\n###FIN###",
            "###CHOIX###\n- aucune\n###REVE###\n- (rien)\n###FIN###",
        ]
        self.calls = 0

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        out = self.outs[min(self.calls, len(self.outs) - 1)]
        self.calls += 1
        return out


def test_dream_wires_coactivation_and_decay_guardrails_intact(mem, monkeypatch):
    monkeypatch.setattr(daemon.embeddings, "embed", lambda text: [1.0, 0.0])
    monkeypatch.setattr(daemon, "notify",
                        lambda *a, **k: pytest.fail("dream() ne notifie JAMAIS"))
    monkeypatch.setattr(config, "DREAM_EVOLVE_SELF", False)  # identité testée ailleurs
    sources = [
        mem.add("user", f"message humain numéro {k} sur la mémoire",
                importance=0.5, embedding=[1.0, 0.0], extract_facets=False)
        for k in range(3)
    ]
    decay_calls = []
    orig_decay = mem.decay_coactivation
    monkeypatch.setattr(
        mem, "decay_coactivation",
        lambda *a, **k: decay_calls.append((a, k)) or orig_decay(*a, **k),
    )

    daemon.dream(_FakeEng(), mem)

    # 1) co-activation loguée entre les graines CHOISIES par le rêveur RÉEL
    #    (ici les 3 sources du menu, toutes choisies) : exactement C(3,2)
    #    paires, canoniques, boostées une fois — rien d'autre (les épisodes
    #    idée/trace écrits PAR le rêve ne co-activent pas ; le jumeau fantôme
    #    ne co-active JAMAIS). Boost RÉDUIT (COACT_DREAM_BOOST < COACT_BOOST) :
    #    la clique d'un rêve encode « rêvés ensemble », elle ne doit pas
    #    dominer les vraies arêtes de co-rappel.
    expected = {(min(x, y), max(x, y))
                for i, x in enumerate(sources) for y in sources[i + 1:]}
    edges = _edges(mem)
    assert set(edges) == expected
    assert config.COACT_DREAM_BOOST < config.COACT_BOOST
    for w, _ts in edges.values():
        assert w == pytest.approx(config.COACT_DREAM_BOOST)
    # 2) decay_coactivation appelé UNE fois par cycle (comme SHY)
    assert len(decay_calls) == 1
    # 3) garde-fous dream INTACTS : lock relâché, curseurs avancés, spacing actif,
    #    garde last_shy posée (le downscale SHY a bien tourné, une seule fois)
    assert mem.kv_get("dream_lock") == ""
    assert float(mem.kv_get("last_dream", "0")) > 0
    assert int(mem.kv_get("last_dream_maxid", "0")) > 0
    assert mem.kv_get("dream_count") == "1"
    assert float(mem.kv_get("last_shy", "0")) > 0
    assert daemon.should_dream(mem) is False  # DREAM_MIN_SPACING respecté
