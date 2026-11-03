"""Tests de routing.py — règles corrigées (Unification ≠ AppLecture) + centroïde.

DB temporaire migrée + squelette seedé — JAMAIS data/memory.db (garde autouse
dans conftest.py). Embeddings synthétiques 2D aux cosinus vérifiés à la main.
SANS LLM : tout est déterministe.
"""

import json

import pytest

import config
import migrations
import routing
import rubrics


@pytest.fixture
def db(legacy_db):
    """DB temp migrée + squelette de rubriques, SANS épisode parasite."""
    migrations.migrate(legacy_db)
    rubrics.seed_skeleton(legacy_db, now=1000.0)
    legacy_db.execute("DELETE FROM episodes")  # retire les 2 seeds du conftest
    legacy_db.commit()
    return legacy_db


def _add_episode(conn, role, content, emb, ts=1000.0):
    cur = conn.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (?,?,?,0.5,?)",
        (ts, role, content, json.dumps(emb)),
    )
    conn.commit()
    return cur.lastrowid


def _set_centroid(conn, path, emb, kind_hint=None):
    conn.execute(
        "UPDATE rubrics SET centroid=?, centroid_n=1, kind_hint=? WHERE path=?",
        (json.dumps(emb), kind_hint, path),
    )
    conn.commit()


def _episode_route(conn, eid):
    return conn.execute(
        "SELECT r.path, e.rubric_conf, e.routed_ts FROM episodes e "
        "LEFT JOIN rubrics r ON r.id = e.rubric_id WHERE e.id=?",
        (eid,),
    ).fetchone()


# --- Cas 1 : route_by_rules — règles corrigées, premier match gagne ---
def test_route_by_rules_corrected_rules():
    # reference Unification -> projets/unification (PAS applecture)
    assert routing.route_by_rules(
        "reference", "[Paper·Al-Husban 2024] charge topologique et cosmogonie"
    ) == ("projets/unification", 0.9)
    # reference coranique explicite -> savoir-applecture
    assert routing.route_by_rules(
        "reference", "[Paper·X] analyse de la sourate 2, versets 1-5"
    ) == ("savoir-applecture", 0.9)
    # rôles introspectifs -> relation-identite
    assert routing.route_by_rules("outreach", "coucou, j'ai pensé à toi") == (
        "relation-identite",
        0.8,
    )
    assert routing.route_by_rules("reflection", "je repense à hier")[0] == "relation-identite"
    assert routing.route_by_rules("dream", "consolidation nocturne")[0] == "relation-identite"
    assert routing.route_by_rules("thought", "note interne")[0] == "relation-identite"
    # reasoning neutre -> meta-apprentissage
    assert routing.route_by_rules(
        "reasoning", "probleme -> etapes -> decision : toujours verifier les bornes"
    ) == ("meta-apprentissage", 0.7)
    # reasoning qui nomme un projet connu -> la rubrique du projet, conf 0.75
    assert routing.route_by_rules(
        "reasoning", "debug du webhook Stripe de Atelier3D : idempotence"
    ) == ("projets/atelier3d", 0.75)
    # semantic neutre -> aucune règle (None), routage centroïde plus tard
    assert routing.route_by_rules("semantic", "fait durable quelconque") is None
    # reference SANS mot-clé -> None aussi (laissé au centroïde, pas de fourre-tout)
    assert routing.route_by_rules("reference", "[Paper·Y] réseaux de neurones") is None


# --- Cas 2 : NON-RÉGRESSION — aucun paper Unification ne tombe dans applecture ---
def test_unification_references_never_route_to_applecture():
    """Le bug corrigé : l'ancien routage envoyait TOUTES les reference vers
    applecture. Les papers Unification (noms propres) doivent aller dans
    projets/unification ; depuis 1B-harden, les papers GÉNÉRIQUES (stellaire,
    unification, cosmogonie, genesis) ne matchent PLUS de règle (None) — ils
    seront routés par centroïde en passe 2, jamais vers applecture."""
    unification_refs = [
        "[Paper·Al-Husban 2023] Sur les invariants topologiques",
        "[Paper·X] Le modèle Soluno et ses implications",
        "[Paper·Z] Charge topologique dans les solitons",
    ]
    generic_refs = [  # 1B-harden : génériques -> aucune règle (centroïde)
        "[Paper·Y] Dynamique stellaire et effondrement",
        "[Paper·W] Vers une théorie de l'unification des champs",
        "[Paper·V] Cosmogonie comparée : genesis et structures primordiales",
    ]
    quran_refs = [
        "[Paper·A] Étude du Coran : structure des chapitres",
        "[Paper·B] Quran corpus: morphological annotation",
        "[Paper·C] AppLecture : embeddings du texte sacré",
        "[Paper·D] La sourate Al-Baqara, analyse thématique",
        "[Paper·E] Le verset du Trône : traditions exégétiques",
        "[Paper·F] Racine arabe k-t-b : dérivations et sens",
    ]
    for content in unification_refs:
        path, conf = routing.route_by_rules("reference", content)
        assert path == "projets/unification", f"misroute: {content!r} -> {path}"
        assert path != "savoir-applecture"
        assert conf == 0.9
    for content in generic_refs:
        res = routing.route_by_rules("reference", content)
        assert res is None, f"générique matché par règle: {content!r} -> {res}"
    for content in quran_refs:
        path, conf = routing.route_by_rules("reference", content)
        assert path == "savoir-applecture", f"misroute: {content!r} -> {path}"
        assert conf == 0.9


# --- Cas 3 : route_by_centroid — nearest, sous-seuil -> parent, vide -> (None, 0.0) ---
def test_route_by_centroid_nearest_parent_fallback_and_empty(db):
    _set_centroid(db, "projets/atelier3d", [1.0, 0.0])
    _set_centroid(db, "projets/anamnese", [0.0, 1.0])

    # proche du 1er centroïde -> sa rubrique, conf = cosinus (~0.99)
    path, conf = routing.route_by_centroid(db, [0.9, 0.1])
    assert path == "projets/atelier3d"
    assert conf == pytest.approx(0.9939, abs=0.001)

    # meilleur cosinus 0.30 < ROUTE_MIN_CONF=0.35 -> remonte au parent (projets)
    assert config.ROUTE_MIN_CONF == 0.35
    path, conf = routing.route_by_centroid(db, [0.3, -0.954])
    assert path == "projets"
    assert conf == pytest.approx(0.30, abs=0.001)

    # embedding vide -> (None, 0.0)
    assert routing.route_by_centroid(db, []) == (None, 0.0)

    # meilleure rubrique = RACINE sous seuil -> None (jamais de « divers »)
    db.execute("UPDATE rubrics SET centroid=NULL, centroid_n=0")
    db.commit()
    _set_centroid(db, "savoir-applecture", [1.0, 0.0])
    assert routing.route_by_centroid(db, [0.3, -0.954]) == (None, 0.0)

    # aucun centroïde nulle part -> (None, 0.0)
    db.execute("UPDATE rubrics SET centroid=NULL, centroid_n=0")
    db.commit()
    assert routing.route_by_centroid(db, [1.0, 0.0]) == (None, 0.0)


# --- Cas 4 : kind_hint — à similarité quasi-égale, le bon kind_hint gagne ---
def test_kind_hint_bonus_breaks_near_ties(db):
    # atelier3d colle un peu MIEUX (cos 1.0 vs 0.98), mais relation-identite
    # porte kind_hint='reflection' : le bonus +0.05 doit inverser le podium.
    _set_centroid(db, "projets/atelier3d", [1.0, 0.0])
    _set_centroid(db, "relation-identite", [0.98, 0.199], kind_hint="reflection")

    # sans hint : la similarité brute gagne
    path, _ = routing.route_by_centroid(db, [1.0, 0.0])
    assert path == "projets/atelier3d"

    # avec role='reflection' : le bonus kind_hint fait gagner relation-identite
    path, conf = routing.route_by_centroid(db, [1.0, 0.0], kind_hint_role="reflection")
    assert path == "relation-identite"
    assert conf <= 1.0  # la conf reste bornée malgré le bonus

    # un rôle qui ne matche aucun kind_hint ne change rien
    path, _ = routing.route_by_centroid(db, [1.0, 0.0], kind_hint_role="semantic")
    assert path == "projets/atelier3d"


# --- Cas 5 : route_all — bootstrap 2 passes, compteurs, NULL, reprenable ---
def test_route_all_two_pass_bootstrap_counters_and_replay(db):
    # épisodes à RÈGLES (passe 1) — leurs embeddings construisent les centroïdes
    e1 = _add_episode(db, "reference", "[Paper·Al-Husban] charge topologique", [1.0, 0.0])
    e2 = _add_episode(db, "reference", "modèle soluno et dynamique stellaire", [0.9, 0.1])
    e3 = _add_episode(db, "reference", "la sourate et ses versets", [0.0, 1.0])
    e4 = _add_episode(db, "reference", "lexique du Coran", [0.1, 0.9])
    e5 = _add_episode(db, "outreach", "coucou !", [])  # règle OK malgré emb vide
    # épisodes NEUTRES (passe 2)
    e6 = _add_episode(db, "semantic", "note proche unification", [0.97, 0.03])
    e7 = _add_episode(db, "user", "question proche applecture", [0.05, 0.95])
    e8 = _add_episode(db, "semantic", "sans embedding", [])  # doit rester NULL
    e9 = _add_episode(db, "semantic", "loin de tout", [0.3, -0.954])  # sous seuil

    stats = routing.route_all(db, now=2000.0)
    assert stats == {"by_rules": 5, "by_centroid": 3, "left_null": 1}

    # passe 1 : règles appliquées ET centroïdes construits
    assert _episode_route(db, e1) == ("projets/unification", 0.9, 2000.0)
    assert _episode_route(db, e3)[0] == "savoir-applecture"
    assert _episode_route(db, e5)[0] == "relation-identite"
    unif_centroid = json.loads(
        db.execute(
            "SELECT centroid FROM rubrics WHERE path='projets/unification'"
        ).fetchone()[0]
    )
    # e1+e2 d'abord ([0.95,0.05]), puis e6 rattaché par centroïde s'y intègre
    assert unif_centroid == pytest.approx([(1 + 0.9 + 0.97) / 3, (0 + 0.1 + 0.03) / 3])

    # passe 2 : les neutres suivent les centroïdes construits en passe 1
    assert _episode_route(db, e6)[0] == "projets/unification"
    assert _episode_route(db, e7)[0] == "savoir-applecture"
    # sous seuil -> rattachement GROSSIER au parent de la meilleure rubrique
    assert _episode_route(db, e9)[0] == "projets"
    # embedding vide, aucune règle -> rubric_id NULL (état neutre valide)
    assert db.execute(
        "SELECT rubric_id FROM episodes WHERE id=?", (e8,)
    ).fetchone() == (None,)

    # REPRENABLE : 2e appel sans force -> rien n'est re-routé (e8 seul retenté)
    stats2 = routing.route_all(db, now=3000.0)
    assert stats2 == {"by_rules": 0, "by_centroid": 0, "left_null": 1}
    assert _episode_route(db, e1)[2] == 2000.0  # routed_ts intact

    # force=True sur un sous-ensemble : re-route (même rubrique, ts rafraîchi)
    stats3 = routing.route_all(db, now=4000.0, episodes=[e1], force=True)
    assert stats3 == {"by_rules": 1, "by_centroid": 0, "left_null": 0}
    assert _episode_route(db, e1) == ("projets/unification", 0.9, 4000.0)
    # pas de double comptage : memory_count d'unification inchangé (e1,e2,e6)
    assert db.execute(
        "SELECT memory_count FROM rubrics WHERE path='projets/unification'"
    ).fetchone() == (3,)
