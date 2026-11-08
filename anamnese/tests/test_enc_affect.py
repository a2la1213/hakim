"""Tests estampillage affectif à l'encodage (enc_valence / enc_arousal).

Tag amygdalien (design 2.0, câblage 2026-07-03) : Memory.add() fige l'état
affectif COURANT sur l'épisode au moment de l'encodage. Best-effort ABSOLU :
DB legacy sans colonnes enc_* ou kv['affect'] corrompu => enc_* restent NULL
et l'écriture n'échoue JAMAIS. Pas de backfill (affect historique inconnu).

DB temporaire (migrée 2.0, ou legacy pour le cas 2) — JAMAIS data/memory.db
(garde autouse dans conftest.py). Tout est offline et déterministe.
"""

import pytest

import affect
import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path):
    """Memory sur DB temporaire migrée 2.0 (colonnes enc_* présentes)."""
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


@pytest.fixture
def legacy_mem(tmp_path):
    """Memory sur DB temporaire NON migrée (schéma legacy, sans enc_*)."""
    m = Memory(db_path=tmp_path / "legacy.db")
    yield m
    m.db.close()


def _enc(m, episode_id):
    """(enc_valence, enc_arousal) relus en base pour un épisode."""
    return m.db.execute(
        "SELECT enc_valence, enc_arousal FROM episodes WHERE id=?",
        (episode_id,),
    ).fetchone()


def test_add_estampille_etat_affectif_courant(mem):
    """Cas 1 : état chaud (succes) => enc_* NON NULL et cohérents avec l'état.

    L'état décroît (quelques ms) entre l'estampille et la relecture : on
    compare à 0.05 près (demi-vies en HEURES, la dérive réelle est ~1e-6).
    """
    affect.event(mem, "succes", 1.0)
    eid = mem.add("user", "grande victoire sur le bug du cockpit")
    assert eid
    row = _enc(mem, eid)
    assert row is not None
    enc_v, enc_a = row
    assert enc_v is not None and enc_a is not None
    v, a = affect.valence_arousal(affect.get_state(mem))
    assert abs(enc_v - v) <= 0.05
    assert abs(enc_a - a) <= 0.05


def test_add_legacy_sans_colonnes_reussit(legacy_mem):
    """Cas 2 : DB legacy SANS enc_* => add() réussit, épisode inséré, zéro exception."""
    cols = {
        r[1] for r in legacy_mem.db.execute("PRAGMA table_info(episodes)")
    }
    assert "enc_valence" not in cols  # le schéma testé est bien legacy
    eid = legacy_mem.add("user", "écriture sur schéma legacy")
    assert eid
    row = legacy_mem.db.execute(
        "SELECT content FROM episodes WHERE id=?", (eid,)
    ).fetchone()
    assert row == ("écriture sur schéma legacy",)


def test_add_affect_corrompu_enc_null(mem):
    """Cas 3 : kv['affect'] illisible => get_state LÈVE (json.loads, comportement
    réel vérifié) => l'estampille est sautée, enc_* restent NULL, add() réussit."""
    mem.kv_set("affect", "not-json")
    eid = mem.add("user", "écriture avec affect corrompu")
    assert eid
    assert _enc(mem, eid) == (None, None)


def test_dedup_ecarte_aucune_ecriture(mem):
    """Cas 4 : dedup=True qui écarte => False et AUCUNE écriture (total_changes)."""
    affect.event(mem, "succes", 1.0)
    assert mem.add("user", "contenu unique pour le test dedup")
    before = mem.db.total_changes
    assert mem.add("user", "contenu unique pour le test dedup", dedup=True) is False
    assert mem.db.total_changes == before


def test_tous_les_roles_estampilles(mem):
    """Tous les rôles sont estampillés (y compris hors WM_TOUCH_ROLES :
    reflection, dream…) : c'est l'état à l'ENCODAGE, quel que soit l'auteur."""
    affect.event(mem, "nouveaute", 0.5)  # un état affectif VÉCU existe
    for role in ("assistant", "semantic", "reflection", "dream"):
        eid = mem.add(role, f"épisode de rôle {role}")
        assert eid
        enc_v, enc_a = _enc(mem, eid)
        assert enc_v is not None and enc_a is not None, role


def test_systeme_vierge_pas_d_estampille(mem):
    """Système VIERGE (aucun événement affectif, kv['affect'] absent) =>
    enc_* restent NULL : on n'estampille pas des baselines jamais éprouvées
    (même honnêteté que le no-backfill). C'est aussi ce qui préserve la
    calibration wm_score des DB de test vierges (suite WM)."""
    assert mem.kv_get("affect") is None
    eid = mem.add("user", "premier épisode avant toute vie affective")
    assert eid
    assert _enc(mem, eid) == (None, None)
