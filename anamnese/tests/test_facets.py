"""Tests Phase 3.5a — infra facettes : extraction bornée, tagging, hook add,
backfill idempotent, recherche par intersection.

DB temporaire migrée via migrations.migrate — JAMAIS data/memory.db (garde
autouse de conftest.py). Aucun embedding réel : add() reçoit embedding=None,
l'extraction de facettes est purement lexicale (déterministe, offline).
Cette phase ne touche PAS le score de rappel (W_FACET = Phase 3.5b).
"""

import pytest

import config
import facets_extract
import memory
import migrations
from eval.backfill_facets import backfill_facets


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (tables facets/episode_facets prêtes)."""
    m = memory.Memory(db_path=tmp_path / "facets.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _facet_count(conn):
    return conn.execute("SELECT COUNT(*) FROM facets").fetchone()[0]


# --- Cas 1 : extract_facets — normalisation, stopwords, cap 8 ----------------
def test_extract_facets_normalizes_and_caps():
    pairs = facets_extract.extract_facets(
        "Recentrage de la caméra avec orbit-controls dans three.js"
    )
    slugs = {s for s, _ in pairs}
    # accents retirés, stopwords FR écartés (de/la/avec/dans), composés gardés
    assert slugs == {"recentrage", "camera", "orbit-controls", "three.js"}
    assert all(0.0 < w <= 1.0 for _, w in pairs)

    # dédup : trois graphies d'un même mot -> UNE facette, poids max 1.0
    assert facets_extract.extract_facets("Caméra caméra CAMERA") == [("camera", 1.0)]

    # cap FACET_MAX_PER_EPISODE=8 sur un texte long : garde les plus lourds
    long_text = " ".join(f"motcle{i}" for i in range(30)) + " anamnese " * 3
    capped = facets_extract.extract_facets(long_text)
    assert len(capped) == config.FACET_MAX_PER_EPISODE == 8
    assert capped[0] == ("anamnese", 1.0)  # le plus fréquent, poids normalisé

    # vide / que du bruit -> aucune facette, pas de crash
    assert facets_extract.extract_facets("") == []
    assert facets_extract.extract_facets("de la et le un") == []


# --- Cas 2 : normalize_slug — minuscule, sans accents, tirets ----------------
def test_normalize_slug():
    assert facets_extract.normalize_slug("Caméra") == "camera"
    assert facets_extract.normalize_slug("Three.JS") == "three.js"
    assert facets_extract.normalize_slug(" Orbit Controls ") == "orbit-controls"
    assert facets_extract.normalize_slug("") == ""


# --- Cas 3 : upsert_facet — idempotent + plafond global 200 ------------------
def test_upsert_facet_idempotent_and_global_cap(mem):
    fid = mem.upsert_facet("three.js")
    assert isinstance(fid, int)
    assert mem.upsert_facet("three.js") == fid  # idempotent, pas de doublon
    assert _facet_count(mem.db) == 1

    # remplir jusqu'au plafond global exactement
    for i in range(config.FACET_MAX_GLOBAL - 1):
        assert mem.upsert_facet(f"facette-{i}") is not None
    assert _facet_count(mem.db) == config.FACET_MAX_GLOBAL == 200

    # au-delà : nouvelle facette refusée (None), pas de crash, compte inchangé
    assert mem.upsert_facet("de-trop") is None
    assert _facet_count(mem.db) == config.FACET_MAX_GLOBAL

    # une facette EXISTANTE reste résolue malgré le plafond
    assert mem.upsert_facet("three.js") == fid


# --- Cas 4 : tag_episode + facets_of — idempotent (PK composite) -------------
def test_tag_episode_and_facets_of_idempotent(mem):
    eid = mem.add("user", "episode a tagger", extract_facets=False)
    assert mem.facets_of(eid) == []

    mem.tag_episode(eid, [("camera", 0.5), ("three.js", 1.0)])
    assert mem.facets_of(eid) == [("three.js", 1.0), ("camera", 0.5)]

    # 2e appel (même un poids différent) : pas de doublon PK, poids d'origine gardé
    mem.tag_episode(eid, [("camera", 0.9), ("three.js", 1.0)])
    assert mem.facets_of(eid) == [("three.js", 1.0), ("camera", 0.5)]
    assert (
        mem.db.execute(
            "SELECT COUNT(*) FROM episode_facets WHERE episode_id=?", (eid,)
        ).fetchone()[0]
        == 2
    )


# --- Cas 5 : hook Memory.add — extraction auto, opt-out, JAMAIS bloquant -----
def test_add_hook_extracts_facets_and_never_breaks(mem, monkeypatch, tmp_path):
    # extract_facets=True (défaut) : l'épisode ajouté a ses facettes
    eid = mem.add("user", "Recentrage caméra orbit-controls three.js")
    slugs = {s for s, _ in mem.facets_of(eid)}
    assert {"camera", "three.js", "orbit-controls"} <= slugs

    # extract_facets=False : aucune facette
    eid2 = mem.add("user", "Recentrage caméra orbit-controls three.js bis",
                   extract_facets=False)
    assert mem.facets_of(eid2) == []

    # échec d'extraction -> l'add réussit QUAND MÊME (try/except silencieux)
    def boom(_content):
        raise RuntimeError("extraction cassée")

    monkeypatch.setattr(facets_extract, "extract_facets", boom)
    eid3 = mem.add("user", "ecriture malgre echec extraction")
    assert eid3  # écriture non cassée
    row = mem.db.execute(
        "SELECT content FROM episodes WHERE id=?", (eid3,)
    ).fetchone()
    assert row == ("ecriture malgre echec extraction",)
    assert mem.facets_of(eid3) == []
    monkeypatch.undo()

    # rétro-compat : DB legacy NON migrée (pas de table facets) -> add passe
    legacy = memory.Memory(db_path=tmp_path / "legacy-non-migree.db")
    assert legacy.add("user", "ecriture daemon sur base non migree")
    assert legacy.count() == 1
    legacy.db.close()


# --- Cas 6 : backfill_facets — tague les non-taggés, idempotent, compte ------
def test_backfill_facets_tags_untagged_and_is_idempotent(mem):
    e1 = mem.add("user", "Recentrage caméra three.js", extract_facets=False)
    e2 = mem.add("assistant", "Bug orbit-controls corrigé hier", extract_facets=False)
    e3 = mem.add("user", "Migration SQLite mémoire persistante")  # déjà taggé (hook)
    e4 = mem.add("user", "de la et", extract_facets=False)  # rien d'extractible
    before_e3 = mem.facets_of(e3)
    assert before_e3  # le hook a bien taggé e3

    res = backfill_facets(mem.db)
    assert res["tagged"] == 2  # e1 + e2 ; e3 sauté (déjà taggé), e4 vide
    assert res["facets_total"] == _facet_count(mem.db) > 0
    assert {s for s, _ in mem.facets_of(e1)} == {"recentrage", "camera", "three.js"}
    assert "orbit-controls" in {s for s, _ in mem.facets_of(e2)}
    assert mem.facets_of(e3) == before_e3  # intact (idempotence = skip)
    assert mem.facets_of(e4) == []

    # 2e appel : plus rien à tagger
    res2 = backfill_facets(mem.db)
    assert res2["tagged"] == 0
    assert res2["facets_total"] == res["facets_total"]


# --- Cas 7 : search_by_facets — classement par intersection, exclusion -------
def test_search_by_facets_ranks_by_intersection(mem):
    e1 = mem.add("user", "episode camera complet", extract_facets=False)
    e2 = mem.add("user", "episode camera seul", extract_facets=False)
    e3 = mem.add("user", "episode sqlite hors sujet", extract_facets=False)
    mem.tag_episode(e1, [("camera", 1.0), ("three.js", 1.0), ("orbit-controls", 1.0)])
    mem.tag_episode(e2, [("camera", 1.0)])
    mem.tag_episode(e3, [("sqlite", 1.0)])

    # entrée NON normalisée ('Caméra') : normalisée avant la recherche
    res = mem.search_by_facets(["Caméra", "three.js"])
    contents = [r[3] for r in res]
    assert contents == ["episode camera complet", "episode camera seul"]
    assert "episode sqlite hors sujet" not in contents  # 0 commune -> exclu
    assert res[0][0] > res[1][0]  # 2 facettes communes > 1
    assert res[0][4]["facets"] == ["camera", "three.js"]

    # top_k respecté
    assert len(mem.search_by_facets(["camera"], top_k=1)) == 1

    # requête vide / facettes inconnues -> liste vide, pas de crash
    assert mem.search_by_facets([]) == []
    assert mem.search_by_facets(["inconnue-totale"]) == []


# --- Cas 7bis : outil MCP facet_search (wrapper read-only) --------------------
def test_facet_search_tool_wraps_search_by_facets(tmp_path, monkeypatch):
    m = memory.Memory(db_path=tmp_path / "mcp-facets.db")
    migrations.migrate(m.db)
    # 1er import de mcp_server sous la garde conftest : Memory() doit tomber
    # sur la DB temp (même mécanique que tests/test_mcp_rubrics.py).
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", m)

    eid = m.add("user", "recentrage camera three.js orbit", extract_facets=False)
    m.tag_episode(eid, [("camera", 1.0), ("three.js", 1.0)])

    fn = mcp_server.mcp._tool_manager.get_tool("facet_search").fn
    out = fn("Caméra, three.js")
    assert "recentrage camera three.js orbit" in out
    assert "camera" in out and "three.js" in out

    assert "aucun" in fn("facette-inexistante")
    m.db.close()
