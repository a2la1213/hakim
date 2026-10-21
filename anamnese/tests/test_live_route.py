"""Routage LIVE — add() route chaque nouvel épisode à l'écriture (brief liveroute).

DB temporaire migrée + squelette + centroïdes synthétiques 2D — JAMAIS
data/memory.db (garde autouse dans conftest.py). SANS LLM : déterministe.

Le routage live est PUREMENT ADDITIF : rubric_id n'entre pas dans la formule
de score du rappel (boost-rubrique gaté OUT) — ces tests vérifient donc
l'organisation (rubric_id posé) et la SÛRETÉ (add ne casse jamais), pas la
précision du rappel.
"""

import json

import pytest

import config
import migrations
import routing
import rubrics
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temp migrée + squelette + centroïdes posés (2D)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    m.db.execute(
        "UPDATE rubrics SET centroid='[1.0, 0.0]', centroid_n=1 "
        "WHERE path='projets/anamnese'"
    )
    m.db.execute(
        "UPDATE rubrics SET centroid='[0.0, 1.0]', centroid_n=1 "
        "WHERE path='savoir-applecture'"
    )
    m.db.commit()
    yield m
    m.db.close()


def _route_of(m, eid):
    """(path|None, rubric_conf, routed_ts) de l'épisode eid."""
    return m.db.execute(
        "SELECT r.path, e.rubric_conf, e.routed_ts FROM episodes e "
        "LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id=?",
        (eid,),
    ).fetchone()


# --- Cas 1 : add() sur base squelette+centroïdes -> épisode routé (rubric_id non NULL)
def test_add_routes_new_episode_by_centroid(mem):
    eid = mem.add("semantic", "fait durable quelconque", embedding=[0.9, 0.1])
    assert eid  # add retourne l'id (truthy)
    path, conf, routed_ts = _route_of(mem, eid)
    assert path == "projets/anamnese"  # cosinus([0.9,0.1],[1,0]) ~ 0.994
    assert conf == pytest.approx(0.9939, abs=0.001)
    assert routed_ts is not None


# --- Cas 2 : règle déterministe — reflection -> relation-identite -----------
def test_add_reflection_routed_by_rule_to_relation_identite(mem):
    eid = mem.add("reflection", "je repense à notre échange d'hier",
                  embedding=[0.5, 0.5])
    path, conf, _ = _route_of(mem, eid)
    assert path == "relation-identite"
    assert conf == 0.8  # conf de la règle, pas un cosinus


# --- Cas 3 : SÛRETÉ — route_episode lève -> add() réussit quand même --------
def test_add_survives_route_episode_exception(mem, monkeypatch):
    def boom(conn, episode_row):
        raise RuntimeError("routage cassé exprès")

    monkeypatch.setattr(routing, "route_episode", boom)
    eid = mem.add("semantic", "épisode malgré le routage cassé",
                  embedding=[0.9, 0.1])
    assert eid  # add n'a PAS levé et retourne l'id
    row = mem.db.execute(
        "SELECT content, rubric_id FROM episodes WHERE id=?", (eid,)
    ).fetchone()
    assert row == ("épisode malgré le routage cassé", None)  # inséré, non routé


# --- Cas 4 : kill-switch — LIVE_ROUTE=False -> pas de routage ----------------
def test_live_route_kill_switch(mem, monkeypatch):
    monkeypatch.setattr(config, "LIVE_ROUTE", False)
    eid = mem.add("semantic", "épisode sous kill-switch", embedding=[0.9, 0.1])
    assert eid
    assert _route_of(mem, eid)[0] is None  # rubric_id NULL


# --- Cas 5 : pas d'embedding -> pas de routage (même pas tenté), add OK -----
def test_add_without_embedding_is_not_routed(mem, monkeypatch):
    calls = []

    def spy(conn, episode_row):
        calls.append(episode_row)
        return "projets/anamnese", 0.9

    monkeypatch.setattr(routing, "route_episode", spy)
    # reflection matcherait une RÈGLE : prouve que la garde embedding
    # passe AVANT tout routage (centroïde impossible sans vecteur).
    eid = mem.add("reflection", "pensée sans embedding", embedding=None)
    assert eid
    assert calls == []  # route_episode jamais appelé
    assert _route_of(mem, eid)[0] is None


# --- Cas 6 : legacy (pas de table rubrics) -> add ne lève pas, pas de routage
def test_add_on_legacy_db_without_rubrics_table(tmp_path):
    m = Memory(db_path=tmp_path / "legacy.db")  # schéma d'avant 2.0, non migré
    assert m.db.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='rubrics'"
    ).fetchone() is None
    # voie centroïde (semantic) ET voie règle (reflection -> attach) : les
    # deux traversent des tables absentes -> skip silencieux, add OK.
    e1 = m.add("semantic", "épisode legacy neutre", embedding=[0.1, 0.2])
    e2 = m.add("reflection", "épisode legacy à règle", embedding=[0.3, 0.4])
    assert e1 and e2
    assert m.count() == 2
    m.db.close()


# --- Cas 7 : NON-RÉGRESSION — retour id, wm_touch et log_coactivation intacts
def test_add_return_and_existing_wiring_untouched(mem):
    e1 = mem.add("user", "question sur anamnèse", embedding=[1.0, 0.0])
    e2 = mem.add("assistant", "réponse sur anamnèse", embedding=[0.9, 0.1])
    # retour = l'id inséré (voie historique inchangée)
    ids = [r[0] for r in mem.db.execute("SELECT id FROM episodes ORDER BY id")]
    assert [e1, e2] == ids

    # wm_touch : les rôles WM_TOUCH_ROLES stockés entrent en focus MDT
    focus_ids = {it["id"] for it in mem.wm_get()["focus"]}
    assert {e1, e2} <= focus_ids

    # log_coactivation : le rappel écrivain co-active toujours le top_k
    res = mem.retrieve("anamnèse", [1.0, 0.0], reconsolidate=True)
    assert len(res) == 2 and all(len(r) == 5 for r in res)  # arité 5 stricte
    edge = mem.db.execute(
        "SELECT weight FROM coactivation WHERE a_id=? AND b_id=?",
        (min(e1, e2), max(e1, e2)),
    ).fetchone()
    assert edge is not None and edge[0] > 0
