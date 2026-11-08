# tests/test_rubric_emergence_emerge.py
import json
import pytest

import config
import migrations
import rubrics
import rubric_emergence as RE


class FakeMem:
    def __init__(self, conn):
        self.db = conn


@pytest.fixture
def db(legacy_db):
    migrations.migrate(legacy_db)   # rubrics + insight_edges prêts
    return legacy_db


def _mk_rubric(conn, path, centroid=None):
    rubrics.rubric_create(conn, path, 1000.0)
    if centroid is not None:
        conn.execute("UPDATE rubrics SET centroid=?, centroid_n=1 WHERE path=?",
                     (json.dumps(centroid), path))
        conn.commit()


def _mk_insight(conn, emb, content="(insight·claude) hypothèse"):
    cur = conn.execute(
        "INSERT INTO episodes (ts, role, content, importance, embedding) "
        "VALUES (1000.0, 'insight', ?, 0.5, ?)", (content, json.dumps(emb)))
    conn.commit()
    return cur.lastrowid


def test_emerge_creates_rubric_for_novel_cluster(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "autre", centroid=[0.0, 1.0, 0.0])   # LOIN du cluster (axe y)
    ids = [_mk_insight(db, [1.0, 0.0, 0.0]),
           _mk_insight(db, [0.98, 0.02, 0.0]),
           _mk_insight(db, [0.97, 0.03, 0.0])]
    created = RE.emerge(FakeMem(db), lambda p: "projets/anamnese/pouw-graphify")
    assert created == ["projets/anamnese/pouw-graphify"]
    row = db.execute("SELECT id, kind_hint FROM rubrics WHERE path=?",
                     ("projets/anamnese/pouw-graphify",)).fetchone()
    assert row is not None and row[1] == "emerged"
    rid = row[0]
    for i in ids:
        assert db.execute("SELECT rubric_id FROM episodes WHERE id=?", (i,)).fetchone()[0] == rid


def test_emerge_skips_when_theme_already_covered(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "proche", centroid=[1.0, 0.0, 0.0])   # TRÈS proche du cluster
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    calls = {"n": 0}
    def spy(p):
        calls["n"] += 1
        return "projets/anamnese/x"
    created = RE.emerge(FakeMem(db), spy)
    assert created == []
    assert calls["n"] == 0   # garde sémantique : le modèle N'EST PAS appelé si le thème est déjà couvert
    assert db.execute("SELECT COUNT(*) FROM rubrics WHERE kind_hint='emerged'").fetchone()[0] == 0


def test_emerge_no_creation_below_min(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_insight(db, [1.0, 0.0, 0.0])
    _mk_insight(db, [0.98, 0.02, 0.0])   # seulement 2 < MIN_INSIGHTS
    assert RE.emerge(FakeMem(db), lambda p: "projets/anamnese/x") == []


def test_emerge_rejects_invalid_path_from_model(db):
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    _mk_rubric(db, "autre", centroid=[0.0, 1.0, 0.0])
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    # le modèle propose un path dont le PARENT n'existe pas → valid_path le rejette (rien créé).
    # NB : le path a un '/', donc il PASSE parse_path et atteint réellement valid_path (garde exercée).
    calls = {"n": 0}
    def spy(p):
        calls["n"] += 1
        return "nouveauroot/theme"   # parent 'nouveauroot' absent des rubriques existantes
    assert RE.emerge(FakeMem(db), spy) == []
    assert calls["n"] >= 1   # cluster NON couvert → le modèle a été appelé → c'est bien valid_path qui a tranché
    assert db.execute("SELECT COUNT(*) FROM rubrics WHERE kind_hint='emerged'").fetchone()[0] == 0


def test_emerge_respects_killswitch(db, monkeypatch):
    monkeypatch.setattr(config, "RUBRIC_EMERGE_ENABLED", False)
    _mk_rubric(db, "projets")
    _mk_rubric(db, "projets/anamnese")
    for _ in range(3):
        _mk_insight(db, [1.0, 0.0, 0.0])
    assert RE.emerge(FakeMem(db), lambda p: "projets/anamnese/x") == []
