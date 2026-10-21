"""Tests de eval/benchmark.py.

1. Helpers PURS (aucune DB, aucun modèle) : percentile/médiane, pourcentage,
   comptage d'outils MCP, parsing de la collecte pytest.
2. RÉGRESSION ro_memory/measure_latency : ro_memory() construit Memory via
   __new__ (bypass de __init__) ; le retrieve vectorisé (Durci #2) lit
   _emb_cache/_tok_cache posés uniquement dans __init__ → AttributeError si
   ro_memory ne les initialise pas. Testé sur DB TEMPORAIRE migrée (jamais
   data/memory.db — garde autouse conftest.py), embeddings synthétiques
   déterministes (embed() monkeypatché : aucun modèle chargé).
"""

import numpy as np
import pytest

import config
import migrations
from eval.benchmark import (
    count_mcp_tools,
    measure_latency,
    median,
    parse_collected,
    pct,
    percentile,
    ro_memory,
)
from memory import Memory


# --- percentile / median -------------------------------------------------------


def test_percentile_liste_vide_leve():
    with pytest.raises(ValueError):
        percentile([], 50)


def test_percentile_p_hors_bornes_leve():
    with pytest.raises(ValueError):
        percentile([1.0], 101)
    with pytest.raises(ValueError):
        percentile([1.0], -1)


def test_percentile_singleton():
    assert percentile([7.5], 0) == 7.5
    assert percentile([7.5], 50) == 7.5
    assert percentile([7.5], 100) == 7.5


def test_percentile_bornes_min_max():
    xs = [3.0, 1.0, 2.0]
    assert percentile(xs, 0) == 1.0
    assert percentile(xs, 100) == 3.0


def test_percentile_interpolation_lineaire():
    # convention numpy : p90 de [1..10] = 9.1 (interpolation entre 9 et 10)
    xs = list(range(1, 11))
    assert percentile(xs, 90) == pytest.approx(9.1)


def test_percentile_insensible_a_l_ordre():
    assert percentile([5, 1, 4, 2, 3], 50) == percentile([1, 2, 3, 4, 5], 50)


def test_median_impair():
    assert median([3.0, 1.0, 2.0]) == 2.0


def test_median_pair_interpole():
    assert median([1.0, 2.0, 3.0, 4.0]) == 2.5


# --- pct -------------------------------------------------------------------------


def test_pct_nominal():
    assert pct(1392, 1393) == pytest.approx(99.928, abs=1e-3)


def test_pct_zero_total_ne_leve_pas():
    assert pct(5, 0) == 0.0
    assert pct(0, 0) == 0.0


def test_pct_complet():
    assert pct(10, 10) == 100.0


# --- count_mcp_tools ----------------------------------------------------------------


def test_count_mcp_tools_compte_les_decorateurs():
    src = (
        "@mcp.tool()\ndef a():\n    pass\n\n"
        "@mcp.tool()\ndef b():\n    pass\n"
    )
    assert count_mcp_tools(src) == 2


def test_count_mcp_tools_ignore_le_reste():
    assert count_mcp_tools("mcp.tool() sans arobase\n# @mcp.tool_maybe()\n") == 0
    assert count_mcp_tools("") == 0


# --- parse_collected -----------------------------------------------------------------


def test_parse_collected_pluriel_et_singulier():
    assert parse_collected("...\n185 tests collected in 0.5s\n") == 185
    assert parse_collected("1 test collected in 0.1s") == 1


def test_parse_collected_absent():
    assert parse_collected("no tests ran") is None


# --- ro_memory / measure_latency (régression : caches du retrieve vectorisé) --------

DIM = 8  # petite dimension synthétique : déterministe, aucun modèle


def _fake_embed(text, dim=DIM):
    """Embedding synthétique déterministe (hash-seedé) — liste de floats."""
    rng = np.random.RandomState(abs(hash(text)) % (2**32))
    return [float(x) for x in rng.uniform(-1.0, 1.0, size=dim)]


@pytest.fixture
def seeded_db(tmp_path):
    """DB temporaire migrée 2.0 + 3 épisodes embarqués (dim 8). Retourne le chemin."""
    db_path = tmp_path / "bench.db"
    m = Memory(db_path=db_path)
    migrations.migrate(m.db)
    for i, content in enumerate(
        ["premier episode sur la memoire",
         "deuxieme episode sur le benchmark",
         "troisieme episode sur la latence"]
    ):
        m.add("semantic", content, importance=0.5 + 0.1 * i,
              embedding=_fake_embed(content), extract_facets=False)
    m.db.close()  # checkpoint WAL : la connexion mode=ro relit un fichier propre
    return db_path


def test_ro_memory_retrieve_ne_leve_pas(seeded_db):
    """RÉGRESSION : ro_memory (Memory via __new__) doit poser _emb_cache et
    _tok_cache, sinon le retrieve vectorisé lève AttributeError."""
    mem = ro_memory(db_path=seeded_db)
    try:
        assert mem._emb_cache == {} and mem._tok_cache == {}
        out = mem.retrieve("episode memoire", _fake_embed("episode memoire"),
                           top_k=config.TOP_K, reconsolidate=False)
    finally:
        mem.db.close()
    assert 1 <= len(out) <= config.TOP_K
    assert all(len(row) == 5 for row in out)  # arité historique inchangée


def test_ro_memory_est_bien_lecture_seule(seeded_db):
    mem = ro_memory(db_path=seeded_db)
    try:
        with pytest.raises(Exception):  # sqlite3.OperationalError (mode=ro + query_only)
            mem.db.execute("INSERT INTO kv (key, value, ts) VALUES ('x', 'y', 0)")
    finally:
        mem.db.close()


def test_measure_latency_retourne_des_nombres(seeded_db, monkeypatch):
    """measure_latency doit tourner de bout en bout sur une DB temp migrée et
    retourner des latences numériques — jamais d'AttributeError silencieux."""
    import embeddings

    monkeypatch.setattr(embeddings, "embed", _fake_embed)
    res = measure_latency(n_runs=4, log=lambda *a: None, db_path=seeded_db)
    assert "na" not in res
    assert res["n_runs"] == 4
    for key in ("retrieve_median_ms", "retrieve_p90_ms", "embed_warm_ms"):
        assert isinstance(res[key], float) and res[key] >= 0.0
    assert res["retrieve_p90_ms"] >= res["retrieve_median_ms"]
    assert res["embedding_dim"] == DIM
