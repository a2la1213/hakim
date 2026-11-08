"""Tests de la mémoire de travail (MDT WM1) — couche d'attention FOCUS+HALO.

La MDT est une couche d'attention à deux étages AU-DESSUS de la LTM :
FOCUS (~WM_FOCUS_CAP, injecté au contexte) + HALO (~WM_HALO_CAP, périphérie
promouvable). État régénérable dans kv['working_memory'] (pointeurs + scores,
pas un nouveau store), mis à jour UNIQUEMENT par les chemins déjà écrivains :
retrieve(reconsolidate=True) et add() hors rôles daemon (reflection/outreach/
dream/thought EXCLUS). Le rappel lecture-seule par défaut ne touche RIEN.
La MDT CONSOMME le rappel : ni le scoring ni l'arité (5) de retrieve ne bougent.

DB temporaire migrée + embeddings synthétiques 2D — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import json

import pytest

import config
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (coactivation + enc_arousal présents)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _reset_wm(mem):
    """Efface l'état MDT (add() touche déjà la MDT : le seed la pollue)."""
    mem.db.execute("DELETE FROM kv WHERE key='working_memory'")
    mem.db.commit()


def _focus(mem):
    """{id: score} du focus courant."""
    return {it["id"]: it["score"] for it in mem.wm_get()["focus"]}


def _halo(mem):
    """{id: score} du halo courant."""
    return {it["id"]: it["score"] for it in mem.wm_get()["halo"]}


def _seed(mem, n=1, importance=0.5, role="semantic"):
    """n épisodes au rôle/importance donnés ; MDT remise à zéro ensuite."""
    ids = [
        mem.add(role, f"episode seed numero {k} imp {importance}",
                importance=importance, embedding=[1.0, 0.0], extract_facets=False)
        for k in range(n)
    ]
    _reset_wm(mem)
    return ids


# --- Cas 1 : wm_get — état vide propre si kv absent/corrompu ; round-trip ---
def test_wm_get_empty_state_and_roundtrip(mem):
    empty = {"focus": [], "halo": [], "updated_ts": 0.0}
    assert mem.wm_get() == empty                      # kv absent

    mem.kv_set("working_memory", "{pas du json")      # JSON invalide
    assert mem.wm_get() == empty
    mem.kv_set("working_memory", json.dumps(["liste"]))  # structure inattendue
    assert mem.wm_get() == empty
    mem.kv_set("working_memory", json.dumps(
        {"focus": [{"id": "x"}], "halo": [], "updated_ts": 1.0}))  # item malformé
    assert mem.wm_get() == empty

    (a,) = _seed(mem, importance=0.6)
    mem.wm_touch([a], 1000.0)                         # round-trip après un touch
    state = mem.wm_get()
    assert state["updated_ts"] == 1000.0
    assert [it["id"] for it in state["focus"]] == [a]
    assert state["focus"][0]["score"] == pytest.approx(0.5 * 0.6)
    assert state["halo"] == []


# --- Cas 2 : promotion — touch => focus, scores bornés ; re-touch => score >= ancien ---
def test_promotion_bounded_scores_and_retouch_monotone(mem):
    a, = _seed(mem, importance=0.6)
    b = mem.add("semantic", "episode b", importance=0.4,
                embedding=[1.0, 0.0], extract_facets=False)
    _reset_wm(mem)

    res = mem.wm_touch([a, b], 1000.0)

    assert res == {"focus_n": 2, "halo_n": 0, "evicted": 0}
    focus = _focus(mem)
    assert set(focus) == {a, b}
    for score in focus.values():
        assert 0.0 <= score <= 1.5                    # borné [0, 1.5]
    assert focus[a] == pytest.approx(0.5 * 0.6)
    assert focus[b] == pytest.approx(0.5 * 0.4)

    old_a, old_b = focus[a], focus[b]
    mem.wm_touch([a], 1010.0)                         # re-touch de a seulement
    focus = _focus(mem)
    assert focus[a] >= old_a                          # jamais de baisse au re-touch
    assert focus[b] == pytest.approx(old_b * config.WM_DECAY)  # b non touché décroît


# --- Cas 3 : décroissance + rétrogradation au-delà de WM_FOCUS_CAP ---
def test_decay_and_demotion_beyond_focus_cap(mem):
    n = config.WM_FOCUS_CAP + 6
    ids = [
        mem.add("semantic", f"episode {k}", importance=0.4 + k * 0.02,
                embedding=[1.0, 0.0], extract_facets=False)
        for k in range(n)                             # scores 0.20 .. 0.49, distincts
    ]
    _reset_wm(mem)

    res = mem.wm_touch(ids, 1000.0)                   # remplit AU-DELÀ du cap

    assert res == {"focus_n": config.WM_FOCUS_CAP, "halo_n": 6, "evicted": 0}
    focus, halo = _focus(mem), _halo(mem)
    assert set(halo) == set(ids[:6])                  # les 6 plus FAIBLES basculent en halo
    assert set(focus) == set(ids[6:])
    strongest = ids[-1]
    before = focus[strongest]

    z = mem.add("semantic", "episode z", importance=0.8,
                embedding=[1.0, 0.0], extract_facets=False)
    _reset_wm(mem)
    mem.kv_set("working_memory", json.dumps(          # ré-injecte l'état d'avant z
        {"focus": [{"id": i, "score": s} for i, s in focus.items()],
         "halo": [{"id": i, "score": s} for i, s in halo.items()],
         "updated_ts": 1000.0}))
    res = mem.wm_touch([z], 1010.0)                   # 2e update : z touché, le reste non

    focus2, halo2 = _focus(mem), _halo(mem)
    assert z in focus2
    # tous les NON-touchés décroissent STRICTEMENT (score *= WM_DECAY)
    assert focus2[strongest] == pytest.approx(before * config.WM_DECAY)
    assert focus2[strongest] < before
    for eid, s in halo.items():
        assert halo2[eid] == pytest.approx(s * config.WM_DECAY)
    # 25 candidats focus, cap 24 : le plus faible rétrograde en halo
    assert res["focus_n"] == config.WM_FOCUS_CAP
    assert res["halo_n"] == 7


# --- Cas 4 : éviction — décroît sous WM_FLOOR => OUT (ni focus, ni halo) ---
def test_eviction_below_floor(mem):
    a, = _seed(mem, importance=0.4)                   # score 0.2, proche du plancher
    keeper = mem.add("semantic", "episode fort", importance=1.0,
                     embedding=[1.0, 0.0], extract_facets=False)
    _reset_wm(mem)
    mem.wm_touch([a, keeper], 1000.0)
    assert a in _focus(mem)

    mem.wm_touch([keeper], 1010.0)                    # a : 0.2 -> 0.17 (>= floor)
    assert _focus(mem)[a] == pytest.approx(0.2 * config.WM_DECAY)
    res = mem.wm_touch([keeper], 1020.0)              # a : 0.17 -> 0.1445 < WM_FLOOR

    assert res["evicted"] == 1
    assert a not in _focus(mem)
    assert a not in _halo(mem)                        # évincé, PAS rétrogradé
    assert keeper in _focus(mem)


# --- Cas 5 : halo nourri par la co-activation — toucher a fait entrer c ---
def test_halo_from_coactivation_neighbors(mem):
    a, c = _seed(mem, n=2, importance=0.6)
    mem.db.execute(
        "INSERT INTO coactivation (a_id, b_id, weight, last_ts) VALUES (?,?,?,?)",
        (min(a, c), max(a, c), 0.5, 1000.0),
    )
    mem.db.commit()

    mem.wm_touch([a], 1000.0)

    assert a in _focus(mem)
    halo = _halo(mem)
    assert c in halo                                  # voisin de co-activation => halo
    assert halo[c] == pytest.approx(0.3 * 0.5)
    assert c not in _focus(mem)                       # promouvable, PAS injecté


# --- Cas 6 : câblage retrieve — reconsolidate=True promeut ; défaut = lecture seule ---
def test_retrieve_wiring_and_default_readonly(mem):
    a = mem.add("semantic", "memoire rubriques anamnese", importance=0.5,
                embedding=[1.0, 0.0], extract_facets=False)
    b = mem.add("semantic", "memoire consolidation sommeil", importance=0.5,
                embedding=[0.9, 0.1], extract_facets=False)
    mem.add("semantic", "tafsir sourate coran", importance=0.5,
            embedding=[0.0, 1.0], extract_facets=False)
    _reset_wm(mem)

    # défaut lecture seule : kv['working_memory'] JAMAIS créé
    rows = mem.retrieve("memoire", [1.0, 0.0], now=2000.0, top_k=2)
    assert rows
    assert mem.kv_get("working_memory") is None

    # reconsolidate=True (voie memory_recall) : le top entre en focus
    mem.retrieve("memoire", [1.0, 0.0], now=2000.0, top_k=2, reconsolidate=True)
    assert set(_focus(mem)) == {a, b}
    assert mem.wm_get()["updated_ts"] == 2000.0

    # défaut à nouveau : la VALEUR kv reste STRICTEMENT inchangée
    raw = mem.kv_get("working_memory")
    mem.retrieve("memoire", [1.0, 0.0], now=2010.0, top_k=2)
    assert mem.kv_get("working_memory") == raw


# --- Cas 7 : câblage add — rôles «vécus» promus, rôles daemon EXCLUS ---
def test_add_wiring_roles_daemon_excluded(mem):
    _reset_wm(mem)
    promoted = [
        mem.add(role, f"episode role {role}", importance=0.9,
                embedding=[1.0, 0.0], extract_facets=False)
        for role in ("user", "assistant", "semantic", "episodic", "reasoning")
    ]
    excluded = [
        mem.add(role, f"rumination role {role}", importance=0.9,
                embedding=[1.0, 0.0], extract_facets=False)
        for role in ("reflection", "outreach", "dream", "thought")
    ]

    focus, halo = _focus(mem), _halo(mem)
    for eid in promoted:
        assert eid in focus                           # store => entre en focus
    for eid in excluded:
        assert eid not in focus and eid not in halo   # le daemon ne remplit PAS la MDT


# --- Cas 8 : legacy — DB sans coactivation/enc_arousal => aucune exception, arité 5 ---
def test_legacy_db_safe_and_retrieve_arity_five(tmp_path, legacy_db):
    m = Memory(db_path=tmp_path / "legacy.db")        # même fichier que la fixture
    try:
        tables = {
            r[0] for r in m.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "coactivation" not in tables           # bien un schéma d'avant P1
        cols = {r[1] for r in m.db.execute("PRAGMA table_info(episodes)")}
        assert "enc_arousal" not in cols

        res = m.wm_touch([1, 2], 1000.0)              # ne lève PAS
        assert res == {"focus_n": 2, "halo_n": 0, "evicted": 0}
        focus = _focus(m)
        assert focus[1] == pytest.approx(0.5 * 0.5)   # importance seule (pas d'arousal)
        assert focus[2] == pytest.approx(0.5 * 0.7)
        assert m.wm_score(2, 1000.0, focus_ids=[1]) == pytest.approx(0.35)

        for reconsolidate in (False, True):           # arité retrieve TOUJOURS 5
            rows = m.retrieve("bonjour", [0.1, 0.2], top_k=2,
                              reconsolidate=reconsolidate)
            assert rows
            for row in rows:
                s, ts, role, content, parts = row     # déballage strict : 5 éléments
                assert len(row) == 5

        tables_after = {
            r[0] for r in m.db.execute(
                "SELECT name FROM sqlite_master WHERE type='table'")
        }
        assert "coactivation" not in tables_after     # skip silencieux, rien créé
    finally:
        m.db.close()
