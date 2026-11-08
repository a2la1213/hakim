"""Tests de rubrics.py — hiérarchie path-based (sans closure), attach + centroïde O(1).

DB temporaire migrée via migrations.migrate — JAMAIS data/memory.db
(garde autouse dans conftest.py). Embeddings seed connus, écrits à la main.
"""

import json

import pytest

import config
import migrations
import rubrics


@pytest.fixture
def db(legacy_db):
    """DB temp au schéma legacy + migration 2.0 appliquée (rubrics prête)."""
    migrations.migrate(legacy_db)
    return legacy_db


def _add_episode(conn, emb, content="ep", ts=1000.0):
    """Insère un épisode avec un embedding connu, retourne son id."""
    cur = conn.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (?,?,?,0.5,?)",
        (ts, "user", content, json.dumps(emb)),
    )
    conn.commit()
    return cur.lastrowid


def _rubric_row(conn, path):
    return conn.execute(
        "SELECT id, label, parent_id, depth, memory_count, centroid, centroid_n "
        "FROM rubrics WHERE path=?",
        (path,),
    ).fetchone()


def _centroid(conn, path):
    raw = _rubric_row(conn, path)[5]
    return json.loads(raw) if raw else None


# --- Cas 1 : seed_skeleton — paths, parent_id/depth corrects, idempotent ---
def test_seed_skeleton_inserts_all_paths_and_is_idempotent(db):
    created = rubrics.seed_skeleton(db, now=1000.0)
    assert created == len(rubrics.SKELETON) == 15

    paths = {r[0] for r in db.execute("SELECT path FROM rubrics")}
    assert paths == set(rubrics.SKELETON)
    assert "divers" not in paths  # PAS de racine « divers »

    # racine : depth 0, pas de parent
    root = _rubric_row(db, "projets")
    assert root[2] is None and root[3] == 0 and root[1] == "projets"

    # feuille profonde : depth 2, parent = id de projets/atelier3d, label = dernier segment
    parent = _rubric_row(db, "projets/atelier3d")
    leaf = _rubric_row(db, "projets/atelier3d/modelisation")
    assert leaf[3] == 2
    assert leaf[2] == parent[0]
    assert leaf[1] == "modelisation"
    assert parent[3] == 1 and parent[2] == root[0]

    # 2e appel = 0 insertion, rien ne bouge
    assert rubrics.seed_skeleton(db, now=2000.0) == 0
    assert db.execute("SELECT COUNT(*) FROM rubrics").fetchone()[0] == 15


# --- Cas 2 : rubric_create — feuille valide, depth>3 refusé, parent manquant refusé, idempotent ---
def test_rubric_create_validates_and_is_idempotent(db):
    rubrics.seed_skeleton(db, now=1000.0)

    # feuille valide sous un parent existant
    rid = rubrics.rubric_create(db, "projets/anamnese/rubriques", now=1500.0)
    row = _rubric_row(db, "projets/anamnese/rubriques")
    assert row[0] == rid
    assert row[1] == "rubriques"  # label par défaut = dernier segment
    assert row[2] == rubrics.get_rubric_id(db, "projets/anamnese")
    assert row[3] == 2

    # depth 3 encore autorisé (== RUBRIC_MAX_DEPTH)...
    assert config.RUBRIC_MAX_DEPTH == 3
    rubrics.rubric_create(db, "projets/anamnese/rubriques/detail", now=1500.0)
    # ... mais depth 4 refusé
    with pytest.raises(ValueError):
        rubrics.rubric_create(db, "projets/anamnese/rubriques/detail/trop", now=1500.0)

    # parent manquant refusé
    with pytest.raises(ValueError):
        rubrics.rubric_create(db, "inconnu/enfant", now=1500.0)

    # ré-appel sur un path existant → même id, aucune ligne en plus
    before = db.execute("SELECT COUNT(*) FROM rubrics").fetchone()[0]
    assert rubrics.rubric_create(db, "projets/anamnese/rubriques", now=1600.0) == rid
    assert db.execute("SELECT COUNT(*) FROM rubrics").fetchone()[0] == before


# --- Cas 3 : subtree_paths — descendants via LIKE, pas les autres racines ---
def test_subtree_paths_returns_descendants_only(db):
    rubrics.seed_skeleton(db, now=1000.0)
    # piège : sibling partageant le préfixe SANS être un descendant
    rubrics.rubric_create(db, "projets-archives", now=1000.0)

    sub = rubrics.subtree_paths(db, "projets")
    assert set(sub) == {
        "projets",
        "projets/atelier3d",
        "projets/atelier3d/modelisation",
        "projets/atelier3d/pricing-stripe",
        "projets/atelier3d/qa",
        "projets/anamnese",
        "projets/anamnese/daemon-consolidation",
        "projets/anamnese/memoire-2.0",
        "projets/unification",
    }
    assert "savoir-applecture" not in sub
    assert "projets-archives" not in sub

    # sous-arbre intermédiaire
    assert set(rubrics.subtree_paths(db, "projets/atelier3d")) == {
        "projets/atelier3d",
        "projets/atelier3d/modelisation",
        "projets/atelier3d/pricing-stripe",
        "projets/atelier3d/qa",
    }


# --- Cas 4 : rubric_tree — bornes de profondeur + sous-arbre respectés ---
def test_rubric_tree_respects_root_and_max_depth(db):
    rubrics.seed_skeleton(db, now=1000.0)

    tree = rubrics.rubric_tree(db, root_path="projets", max_depth=1)
    assert [n["path"] for n in tree] == [
        "projets",
        "projets/anamnese",
        "projets/atelier3d",
        "projets/unification",
    ]  # trié par path, depth<=1, aucun depth 2
    for node in tree:
        assert set(node) == {"path", "label", "depth", "memory_count"}
        assert node["depth"] <= 1
        assert node["memory_count"] == 0

    # sans filtre : tout le squelette
    assert len(rubrics.rubric_tree(db)) == 15
    # max_depth seul : uniquement les 7 racines du squelette
    roots = rubrics.rubric_tree(db, max_depth=0)
    assert all(n["depth"] == 0 for n in roots) and len(roots) == 7


# --- Cas 5 : attach_episode — colonnes épisode, memory_count, centroïde, ré-attache ---
def test_attach_episode_counts_centroid_and_reattach(db):
    rubrics.seed_skeleton(db, now=1000.0)
    e1 = _add_episode(db, [1.0, 0.0, 0.0, 0.0], "episode un")
    e2 = _add_episode(db, [0.0, 1.0, 0.0, 0.0], "episode deux")

    # 1er épisode : colonnes posées, count=1, centroïde = son embedding
    rubrics.attach_episode(db, e1, "projets/anamnese", conf=0.9, now=2000.0)
    ep = db.execute(
        "SELECT rubric_id, rubric_conf, routed_ts FROM episodes WHERE id=?", (e1,)
    ).fetchone()
    assert ep == (rubrics.get_rubric_id(db, "projets/anamnese"), 0.9, 2000.0)
    assert _rubric_row(db, "projets/anamnese")[4] == 1
    assert _centroid(db, "projets/anamnese") == pytest.approx([1.0, 0.0, 0.0, 0.0])

    # 2e épisode : count=2, centroïde = moyenne des deux (numérique)
    rubrics.attach_episode(db, e2, "projets/anamnese", conf=0.8, now=2100.0)
    assert _rubric_row(db, "projets/anamnese")[4] == 2
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.5, 0.5, 0.0, 0.0])

    # ré-attacher le 1er ailleurs : ancien count redescend à 1, pas de double comptage
    rubrics.attach_episode(db, e1, "projets/atelier3d", conf=0.7, now=2200.0)
    assert _rubric_row(db, "projets/anamnese")[4] == 1
    assert _rubric_row(db, "projets/atelier3d")[4] == 1
    # le centroïde de l'ancienne rubrique ré-équilibre sur ce qui reste (e2)
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.0, 1.0, 0.0, 0.0])
    assert _centroid(db, "projets/atelier3d") == pytest.approx([1.0, 0.0, 0.0, 0.0])
    ep = db.execute(
        "SELECT rubric_id, rubric_conf, routed_ts FROM episodes WHERE id=?", (e1,)
    ).fetchone()
    assert ep == (rubrics.get_rubric_id(db, "projets/atelier3d"), 0.7, 2200.0)

    # ré-attacher au MÊME endroit : conf/ts rafraîchis, count/centroïde inchangés
    rubrics.attach_episode(db, e2, "projets/anamnese", conf=0.95, now=2300.0)
    assert _rubric_row(db, "projets/anamnese")[4] == 1
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.0, 1.0, 0.0, 0.0])


# --- Cas 6 : update_centroid — moyenne courante sur 3 embeddings, vide = no-op ---
def test_update_centroid_running_mean_and_safe_noop(db):
    rubrics.seed_skeleton(db, now=1000.0)
    rid = rubrics.get_rubric_id(db, "technique-transverse")

    def bump(emb):
        # séquence réelle d'attach_episode : centroïde AVANT incrément du count
        rubrics.update_centroid(db, rid, emb)
        db.execute(
            "UPDATE rubrics SET memory_count = memory_count + 1 WHERE id=?", (rid,)
        )

    bump([1.0, 1.0])
    assert _centroid(db, "technique-transverse") == pytest.approx([1.0, 1.0])
    bump([3.0, 3.0])
    assert _centroid(db, "technique-transverse") == pytest.approx([2.0, 2.0])
    bump([5.0, 5.0])
    assert _centroid(db, "technique-transverse") == pytest.approx([3.0, 3.0])

    # embedding vide → no-op sûr (centroïde ET centroid_n inchangés)
    rubrics.update_centroid(db, rid, [])
    assert _centroid(db, "technique-transverse") == pytest.approx([3.0, 3.0])
    # dimension incohérente → no-op sûr aussi
    rubrics.update_centroid(db, rid, [9.0])
    assert _centroid(db, "technique-transverse") == pytest.approx([3.0, 3.0])
    assert _rubric_row(db, "technique-transverse")[6] == 3  # 3 embeddings intégrés


# --- Cas 7 : embeddings vides mêlés aux valides — centroïde NON biaisé (centroid_n) ---
def test_attach_empty_embedding_does_not_bias_centroid(db):
    """Le bug corrigé : avec n = memory_count, vide + [1,0] + [0,1] donnait
    [0.667, 0.333] (le 1er embedding valide comptait double). Avec centroid_n
    (compte des embeddings réellement intégrés), la moyenne est exacte."""
    rubrics.seed_skeleton(db, now=1000.0)
    e_vide = _add_episode(db, [], "episode sans embedding")  # legacy '[]'
    e1 = _add_episode(db, [1.0, 0.0], "episode un")
    e2 = _add_episode(db, [0.0, 1.0], "episode deux")

    # épisode à embedding vide : rattaché (memory_count bouge), centroïde non
    rubrics.attach_episode(db, e_vide, "projets/anamnese", conf=0.5, now=2000.0)
    row = _rubric_row(db, "projets/anamnese")
    assert row[4] == 1 and row[6] == 0
    assert _centroid(db, "projets/anamnese") is None

    # + 2 embeddings valides : centroïde = moyenne EXACTE, pas [0.667, 0.333]
    rubrics.attach_episode(db, e1, "projets/anamnese", conf=0.9, now=2100.0)
    rubrics.attach_episode(db, e2, "projets/anamnese", conf=0.8, now=2200.0)
    row = _rubric_row(db, "projets/anamnese")
    assert row[4] == 3  # memory_count : TOUS les épisodes rattachés
    assert row[6] == 2  # centroid_n : seuls les 2 embeddings valides
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.5, 0.5])

    # détacher un valide : centroïde = moyenne des valides restants
    rubrics.attach_episode(db, e1, "projets/atelier3d", conf=0.7, now=2300.0)
    row = _rubric_row(db, "projets/anamnese")
    assert row[4] == 2 and row[6] == 1
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.0, 1.0])

    # détacher l'épisode à embedding vide : centroïde et centroid_n intacts
    rubrics.attach_episode(db, e_vide, "projets/atelier3d", conf=0.5, now=2400.0)
    row = _rubric_row(db, "projets/anamnese")
    assert row[4] == 1 and row[6] == 1
    assert _centroid(db, "projets/anamnese") == pytest.approx([0.0, 1.0])
    # ... et il n'a pas non plus pollué la rubrique d'arrivée
    row_b = _rubric_row(db, "projets/atelier3d")
    assert row_b[4] == 2 and row_b[6] == 1
    assert _centroid(db, "projets/atelier3d") == pytest.approx([1.0, 0.0])

    # dernier embedding valide détaché : centroïde NULL, centroid_n retombe à 0
    rubrics.attach_episode(db, e2, "projets/atelier3d", conf=0.8, now=2500.0)
    row = _rubric_row(db, "projets/anamnese")
    assert row[4] == 0 and row[6] == 0
    assert _centroid(db, "projets/anamnese") is None
    # rubrique d'arrivée : ordre valide → vide → valide, moyenne exacte aussi
    row_b = _rubric_row(db, "projets/atelier3d")
    assert row_b[4] == 3 and row_b[6] == 2
    assert _centroid(db, "projets/atelier3d") == pytest.approx([0.5, 0.5])


# --- Cas 8 : DB migrée avec l'ancienne Phase 1A (rubrics SANS centroid_n) — ALTER idempotent ---
def test_migrate_adds_centroid_n_to_preexisting_rubrics(legacy_db):
    # simule une DB passée par la Phase 1A d'origine : rubrics sans centroid_n
    legacy_db.execute(
        "CREATE TABLE rubrics ("
        " id INTEGER PRIMARY KEY, path TEXT UNIQUE NOT NULL, label TEXT,"
        " parent_id INTEGER REFERENCES rubrics(id), kind_hint TEXT,"
        " centroid TEXT, depth INTEGER DEFAULT 0,"
        " memory_count INTEGER DEFAULT 0, created_ts REAL)"
    )
    legacy_db.execute(
        "INSERT INTO rubrics (path, label, depth, created_ts, memory_count) "
        "VALUES ('projets','projets',0,999.0,4)"
    )
    legacy_db.commit()

    result = migrations.migrate(legacy_db)
    assert "centroid_n" in result["columns_added"]
    # ligne préexistante : DEFAULT 0 appliqué, memory_count intact
    row = legacy_db.execute(
        "SELECT memory_count, centroid_n FROM rubrics WHERE path='projets'"
    ).fetchone()
    assert row == (4, 0)
    # ré-appel : plus rien à ajouter (idempotence conservée)
    assert migrations.migrate(legacy_db)["columns_added"] == []
