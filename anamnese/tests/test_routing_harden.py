"""Tests Phase 1B-harden — règles Unification spécifiques (word-boundary),
plancher de similarité, et rapport d'échantillon LECTURE SEULE.

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


# --- Cas 1 : frontières de mot — « interstellaire » ne matche plus rien ---
def test_word_boundary_matching():
    # sous-chaîne interdite : « interstellaire » ⊅ « stellaire »/« soluno-stellaire »
    assert routing.route_by_rules("reference", "physique du milieu interstellaire") is None
    # noms propres spécifiques -> règle Unification, conf 0.9
    assert routing.route_by_rules(
        "reference", "Soluno-Stellaire charge topologique"
    ) == ("projets/unification", 0.9)
    assert routing.route_by_rules(
        "reference", "charge topologique du trou noir"
    ) == ("projets/unification", 0.9)


# --- Cas 2 : anti-cross-talk — les génériques ne routent PLUS vers unification ---
def test_generic_keywords_no_cross_talk():
    # « Cosmogonie coranique » : JAMAIS unification (applecture ou None acceptés)
    res = routing.route_by_rules("reference", "Cosmogonie coranique : lecture des versets")
    assert res is None or res[0] == "savoir-applecture"
    # « genesis » générique retiré : aucune règle ne matche (laissé au centroïde)
    assert routing.route_by_rules("reference", "Genesis of black hole binaries") is None
    # « unification » générique retiré aussi (pour les reference)
    assert routing.route_by_rules(
        "reference", "Vers une théorie de l'unification des champs"
    ) is None


# --- Cas 2bis : précédence AppLecture > Unification sur les reference mixtes ---
def test_quranic_reference_citing_al_husban_routes_to_applecture(db):
    """Non-régression #431/#432 : un paper CORANIQUE qui cite incidemment le
    « calendrier al-Husban » doit aller dans savoir-applecture, pas dans
    projets/unification — le signal coranique explicite (quran/sourate/…)
    prime sur une mention al-husban de passage. La règle AppLecture est donc
    évaluée AVANT la règle Unification pour les reference."""
    mixed = (
        "[Paper · Siyam_Ramadan_Root_Analytical_Study_V2.pdf] Ṣiyām and "
        "Ramaḍān in the Quran — A Systematic Root-Analytical Study — si le "
        "calendrier al-Husban (Paper I) est correct, Ramaḍān = M6"
    )
    assert routing.route_by_rules("reference", mixed) == ("savoir-applecture", 0.9)

    # le VRAI paper Unification (aucun mot-clé coranique) reste bien routé :
    # il traverse la règle AppLecture sans matcher et tombe sur Unification
    pure = (
        "[Paper · Al-Husban Soluno-Stellaire v5.5] charge topologique "
        "et calendrier soluno-stellaire"
    )
    assert routing.route_by_rules("reference", pure) == ("projets/unification", 0.9)

    # route_report attribue le hit mixte à la règle GAGNANTE (AppLecture) :
    # compté dans savoir-applecture, et « al-husban » ne le crédite pas
    e_mixed = _add_episode(db, "reference", mixed, [0.0, 1.0])
    report = routing.route_report(db)
    assert report["by_rule_counts"] == {"savoir-applecture": 1}
    assert e_mixed in report["by_keyword"]["quran"]
    assert e_mixed not in report["by_keyword"].get("al-husban", [])


# --- Cas 3 : plancher de similarité — best_sim <= 0 -> (None, 0.0) ---
def test_similarity_floor_never_negative_conf(db):
    _set_centroid(db, "projets/atelier3d", [1.0, 0.0])

    # cosinus -1 : plancher -> (None, 0.0), PAS de fallback parent à conf < 0
    assert routing.route_by_centroid(db, [-1.0, 0.0]) == (None, 0.0)

    # au-dessus du seuil : route normalement (comportement conservé)
    path, conf = routing.route_by_centroid(db, [0.9, 0.1])
    assert path == "projets/atelier3d"
    assert conf == pytest.approx(0.9939, abs=0.001)

    # 0 < sim (~0.30) < ROUTE_MIN_CONF=0.35 : fallback parent CONSERVÉ
    assert config.ROUTE_MIN_CONF == 0.35
    path, conf = routing.route_by_centroid(db, [0.3, -0.954])
    assert path == "projets"
    assert 0 < conf < config.ROUTE_MIN_CONF

    # via route_all : l'épisode anti-corrélé reste NULL et ne contamine
    # AUCUN centroïde (celui du parent « projets » reste vide)
    e = _add_episode(db, "semantic", "vecteur anti-corrélé", [-1.0, 0.0])
    stats = routing.route_all(db, now=2000.0)
    assert stats == {"by_rules": 0, "by_centroid": 0, "left_null": 1}
    assert db.execute(
        "SELECT rubric_id, rubric_conf FROM episodes WHERE id=?", (e,)
    ).fetchone() == (None, None)
    assert db.execute(
        "SELECT centroid, centroid_n FROM rubrics WHERE path='projets'"
    ).fetchone() == (None, 0)


# --- Cas 4 : route_report — comptes, groupement par mot-clé, ZÉRO écriture ---
def test_route_report_counts_keywords_and_never_writes(db):
    e1 = _add_episode(db, "reference", "[Paper·Al-Husban 2023] invariants", [1.0, 0.0])
    e2 = _add_episode(db, "reference", "Le modèle Soluno et la charge topologique", [0.9, 0.1])
    e3 = _add_episode(db, "reference", "la sourate et le Coran", [0.0, 1.0])
    e4 = _add_episode(db, "reference", "[Paper·Y] réseaux de neurones", [0.5, 0.5])
    e5 = _add_episode(db, "reflection", "je repense à hier", [])
    e6 = _add_episode(db, "user", "bonjour", [])

    before = db.total_changes
    report = routing.route_report(db)

    # comptes par rubrique (passe règles UNIQUEMENT, pas de centroïde)
    assert report["by_rule_counts"] == {
        "projets/unification": 2,
        "savoir-applecture": 1,
        "relation-identite": 1,
    }
    assert report["unmatched"] == 2  # e4 (reference neutre) + e6 (user)

    # groupement par mot-clé déclencheur (tous les mots-clés de la règle gagnante)
    assert report["by_keyword"]["al-husban"] == [e1]
    assert report["by_keyword"]["soluno"] == [e2]
    assert report["by_keyword"]["charge topologique"] == [e2]
    assert report["by_keyword"]["sourate"] == [e3]
    assert report["by_keyword"]["coran"] == [e3]
    # les règles SANS mot-clé (rôles introspectifs) ne polluent pas by_keyword
    for ids in report["by_keyword"].values():
        assert e5 not in ids

    # PREUVE de non-écriture : aucun statement d'écriture, tous rubric_id NULL
    assert db.total_changes == before
    assert db.execute(
        "SELECT COUNT(*) FROM episodes WHERE rubric_id IS NOT NULL "
        "OR rubric_conf IS NOT NULL OR routed_ts IS NOT NULL"
    ).fetchone() == (0,)
    assert db.execute(
        "SELECT COUNT(*) FROM rubrics WHERE memory_count != 0 "
        "OR centroid IS NOT NULL"
    ).fetchone() == (0,)


# --- Cas 5 (bonus durcissement) : eval/route_sample.py — CLI lecture seule ---
def test_route_sample_script_prints_and_never_writes(db, tmp_path, monkeypatch, capsys):
    long_ref = (
        "[Paper·Al-Husban 2024] charge topologique : "
        + "x" * 100  # force la troncature à 80 chars dans l'extrait
    )
    e1 = _add_episode(db, "reference", long_ref, [1.0, 0.0])
    e2 = _add_episode(db, "reference", "la sourate et ses chapitres", [0.0, 1.0])
    _add_episode(db, "user", "bonjour", [])

    from eval import route_sample

    # le script lit config.DB_PATH -> pointé sur la DB temp (jamais la vraie)
    monkeypatch.setattr(config, "DB_PATH", tmp_path / "legacy.db")
    route_sample.main()

    out = capsys.readouterr().out
    assert "projets/unification" in out
    assert "savoir-applecture" in out
    assert f"#{e1}" in out and f"#{e2}" in out
    # extrait tronqué à 80 chars : la fin du contenu long n'apparaît pas
    assert long_ref[:80] in out
    assert long_ref not in out
    # CHAQUE mot-clé Unification/AppLecture est listé (même à 0 hit)
    for kw in routing.UNIFICATION_KEYWORDS + routing.QURAN_KEYWORDS:
        assert kw in out

    # lecture SEULE : rien n'a été routé/écrit
    assert db.execute(
        "SELECT COUNT(*) FROM episodes WHERE rubric_id IS NOT NULL"
    ).fetchone() == (0,)
