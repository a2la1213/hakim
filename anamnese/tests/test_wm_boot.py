"""Tests WM2 — amorçage de session (wm_boot) + surface MCP (working_memory).

wm_boot = le « walk in knowing » : il part de l'état WM PERSISTANT (continuité
inter-session — jamais de remise à zéro), refroidit les scores si l'état est
resté froid (> WM_BOOT_STALE_H → × WM_BOOT_COOL), re-sème depuis les épisodes
récents saillants (fenêtre WM_BOOT_RESEED_H, rôles WM_TOUCH_ROLES uniquement,
max WM_BOOT_RESEED_MAX), puis évince sous le plancher et re-cape.
wm_focus_brief = le focus HYDRATÉ (role/snippet/rubrique), READ-ONLY.
+ Addendum (ruling review WM1) : un voisin de co-activation à weight < 0.5
entre en halo AU PLANCHER (max(WM_FLOOR, 0.3*w)) au lieu d'être mort-né.

DB temporaire migrée (ou legacy pour le cas 6) — JAMAIS data/memory.db
(garde autouse dans conftest.py). mcp_server est importé DANS les fixtures,
`_mem` monkeypatché. Tout est offline et déterministe.
"""

import json
import time

import pytest

import config
import memory
import migrations
import rubrics
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (coactivation + rubriques présentes)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


@pytest.fixture
def srv(tmp_path, monkeypatch):
    """(module mcp_server, Memory temp migrée) — `_mem` monkeypatché, embed neutralisé."""
    m = Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(m.db)
    # 1er import de mcp_server : son `_mem = Memory()` doit tomber sur la DB temp.
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", m)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, m
    m.db.close()


@pytest.fixture
def legacy_srv(tmp_path, monkeypatch, legacy_db):
    """(module mcp_server, Memory sur schéma legacy pré-2.0) — cas 6."""
    m = Memory(db_path=tmp_path / "legacy.db")  # même fichier que la fixture
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: m)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", m)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, m
    m.db.close()


def _fn(mod, name):
    """La fonction d'un outil réellement ENREGISTRÉ auprès de FastMCP."""
    return mod.mcp._tool_manager.get_tool(name).fn


def _reset_wm(m):
    """Efface l'état MDT (add() touche déjà la MDT : le seed la pollue)."""
    m.db.execute("DELETE FROM kv WHERE key='working_memory'")
    m.db.commit()


def _focus(m):
    """{id: score} du focus courant."""
    return {it["id"]: it["score"] for it in m.wm_get()["focus"]}


def _halo(m):
    """{id: score} du halo courant."""
    return {it["id"]: it["score"] for it in m.wm_get()["halo"]}


# --- Cas 1 : wm_boot sur DB vierge — ne lève pas, re-sème les récents saillants ---
def test_wm_boot_virgin_db_reseeds_from_recent_salient(mem):
    # DB totalement vide (aucun épisode, aucun état WM) : compteurs à zéro
    assert mem.wm_boot(1000.0) == {"focus_n": 0, "halo_n": 0, "reseeded": 0}

    ids = [
        mem.add(role, f"episode recent role {role}", importance=imp,
                embedding=[1.0, 0.0], extract_facets=False)
        for role, imp in (("user", 0.9), ("assistant", 0.7),
                          ("semantic", 0.5), ("episodic", 0.4))
    ]
    _reset_wm(mem)  # pas d'état WM : le boot repart des récents saillants
    now = time.time()

    res = mem.wm_boot(now)

    assert res == {"focus_n": 4, "halo_n": 0, "reseeded": 4}
    focus = _focus(mem)
    assert set(focus) == set(ids)  # les tops entrent en focus
    for eid, imp in zip(ids, (0.9, 0.7, 0.5, 0.4)):
        assert focus[eid] == pytest.approx(0.5 * imp)
    assert mem.wm_get()["updated_ts"] == pytest.approx(now)


# --- Cas 2 : continuité — état récent conservé tel quel ; état vieux refroidi ---
def test_wm_boot_continuity_recent_kept_stale_cooled(mem):
    now = 1_000_000.0
    state = {
        "focus": [{"id": 1, "score": 0.8}, {"id": 2, "score": 0.2}],
        "halo": [{"id": 3, "score": 0.3}, {"id": 4, "score": 0.2}],
        "updated_ts": now - 3600.0,  # récent (< WM_BOOT_STALE_H)
    }
    mem.kv_set("working_memory", json.dumps(state))

    res = mem.wm_boot(now)  # aucun épisode récent en DB : pas de re-semis

    # CONTINUITÉ : les items sont conservés, scores STRICTEMENT inchangés
    assert res == {"focus_n": 2, "halo_n": 2, "reseeded": 0}
    assert _focus(mem) == pytest.approx({1: 0.8, 2: 0.2})
    assert _halo(mem) == pytest.approx({3: 0.3, 4: 0.2})
    assert mem.wm_get()["updated_ts"] == pytest.approx(now)  # boot = rafraîchi

    state["updated_ts"] = now - (config.WM_BOOT_STALE_H + 1) * 3600.0  # VIEUX
    mem.kv_set("working_memory", json.dumps(state))

    res = mem.wm_boot(now)

    # refroidi × WM_BOOT_COOL, JAMAIS effacé ; 0.2*0.6=0.12 < WM_FLOOR => évincés
    assert res == {"focus_n": 1, "halo_n": 1, "reseeded": 0}
    assert _focus(mem) == pytest.approx({1: 0.8 * config.WM_BOOT_COOL})
    assert _halo(mem) == pytest.approx({3: 0.3 * config.WM_BOOT_COOL})


# --- Cas 3 : re-semis filtré — daemon exclu, fenêtre 48 h, borné à max 10 ---
def test_wm_boot_reseed_filters_roles_window_and_cap(mem):
    now = time.time()
    seeded = [
        mem.add("semantic", f"savoir recent numero {k}", importance=0.5 + k * 0.01,
                embedding=[1.0, 0.0], extract_facets=False)
        for k in range(12)  # importances 0.50 .. 0.61, distinctes
    ]
    daemon = mem.add("reflection", "rumination du daemon", importance=0.99,
                     embedding=[1.0, 0.0], extract_facets=False)
    cur = mem.db.execute(  # saillant mais HORS fenêtre (60 h > WM_BOOT_RESEED_H)
        "INSERT INTO episodes (ts, role, content, importance, embedding) "
        "VALUES (?,?,?,?,?)",
        (now - 60 * 3600.0, "semantic", "vieux savoir hors fenetre", 0.99, "[]"),
    )
    old = cur.lastrowid
    mem.db.commit()
    _reset_wm(mem)

    res = mem.wm_boot(now)

    assert res == {"focus_n": 10, "halo_n": 0, "reseeded": 10}  # borné à max 10
    focus, halo = _focus(mem), _halo(mem)
    assert set(focus) == set(seeded[2:])  # top-10 par importance, les 2 faibles non
    assert daemon not in focus and daemon not in halo  # 'reflection' PAS semé
    assert old not in focus and old not in halo        # hors fenêtre : PAS semé


# --- Cas 4 : wm_focus_brief — hydraté, trié par score, READ-ONLY ---
def test_wm_focus_brief_hydrated_sorted_readonly(mem):
    rubrics.seed_skeleton(mem.db, now=1000.0)
    long_content = "decision architecture memoire de travail : " + "x" * 120
    a = mem.store_in(long_content, "projets/anamnese", role="semantic",
                     importance=0.8)
    b = mem.add("user", "question courte", importance=0.4,
                embedding=[1.0, 0.0], extract_facets=False)
    _reset_wm(mem)
    mem.wm_touch([a, b], 1000.0)

    before = mem.db.total_changes
    brief = mem.wm_focus_brief()

    assert mem.db.total_changes == before  # READ-ONLY : aucune écriture
    assert [it["id"] for it in brief] == [a, b]  # trié par score décroissant
    assert brief[0]["role"] == "semantic"
    assert brief[0]["rubric_path"] == "projets/anamnese"
    assert brief[0]["score"] == pytest.approx(0.5 * 0.8)
    assert len(brief[0]["snippet"]) <= 120  # snippet borné
    assert brief[0]["snippet"].startswith("decision architecture memoire")
    assert brief[1]["role"] == "user"
    assert brief[1]["rubric_path"] is None  # épisode sans rubrique
    assert brief[1]["snippet"] == "question courte"

    assert [it["id"] for it in mem.wm_focus_brief(max_items=1)] == [a]


# --- Cas 5 : outils MCP — wm_boot renvoie le briefing ; working_memory vide propre ---
def test_mcp_wm_boot_and_working_memory_tools(srv):
    mod, m = srv
    _reset_wm(m)
    assert _fn(mod, "working_memory")() == "MDT vide — wm_boot pour amorcer."

    m.add("semantic", "decision memorable sur la memoire de travail",
          importance=0.9, embedding=[1.0, 0.0], extract_facets=False)
    m.add("user", "question sur anamnese", importance=0.7,
          embedding=[1.0, 0.0], extract_facets=False)
    _reset_wm(m)

    out = _fn(mod, "wm_boot")()

    assert "MDT amorcée : 2 en focus, 0 en halo" in out
    assert "re-semés : 2" in out
    assert "- [semantic] decision memorable sur la memoire de travail (0.45)" in out
    assert "- [user] question sur anamnese (0.35)" in out

    before = m.db.total_changes
    wm = _fn(mod, "working_memory")()
    assert m.db.total_changes == before  # briefing SEUL, sans re-boot ni écriture
    assert "decision memorable" in wm and "question sur anamnese" in wm


# --- Cas 6 : legacy — DB pré-2.0 => wm_boot/working_memory dégradent proprement ---
def test_legacy_db_boot_and_brief_safe(legacy_srv):
    mod, m = legacy_srv
    tables = {r[0] for r in m.db.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "rubrics" not in tables and "coactivation" not in tables

    res = m.wm_boot(time.time())  # épisodes trop vieux (ts~1000) : rien à semer
    assert res == {"focus_n": 0, "halo_n": 0, "reseeded": 0}

    out = _fn(mod, "wm_boot")()  # l'outil MCP ne lève pas non plus
    assert "MDT amorcée : 0 en focus, 0 en halo" in out
    assert _fn(mod, "working_memory")() == "MDT vide — wm_boot pour amorcer."

    m.wm_touch([1, 2], 1000.0)  # état posé à la main sur le schéma legacy
    brief = m.wm_focus_brief()  # hydrate SANS rubriques : rubric_path None
    assert [it["id"] for it in brief] == [2, 1]  # 0.35 > 0.25
    top = brief[0]
    assert (top["role"], top["snippet"], top["rubric_path"]) == (
        "assistant", "salut", None)
    assert top["score"] == pytest.approx(0.5 * 0.7)
    assert "- [assistant] salut (0.35)" in _fn(mod, "working_memory")()


# --- Addendum (ruling review WM1) : voisin à w=0.3 => survit en halo AU PLANCHER ---
def test_halo_floor_low_weight_neighbor_survives(mem):
    a = mem.add("semantic", "episode focus", importance=0.6,
                embedding=[1.0, 0.0], extract_facets=False)
    c = mem.add("semantic", "episode voisin", importance=0.6,
                embedding=[1.0, 0.0], extract_facets=False)
    mem.db.execute(
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (?,?,?,?)",
        (min(a, c), max(a, c), 0.3, 1000.0),  # w < 0.5 : mort-né avant le fix
    )
    mem.db.commit()
    _reset_wm(mem)

    res = mem.wm_touch([a], 1000.0)

    halo = _halo(mem)
    assert c in halo  # AVANT le fix : 0.3*0.3=0.09 < WM_FLOOR => jamais entré
    assert halo[c] == pytest.approx(config.WM_FLOOR)  # entre AU PLANCHER
    assert c not in _focus(mem)
    # et le compteur n'est plus gonflé par un fantôme mort-né
    assert res == {"focus_n": 1, "halo_n": 1, "evicted": 0}
