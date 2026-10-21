"""One-shot : blanchit les embeddings reflection/outreach existants (récupère l'espace),
sans toucher rubric_id ni le contenu. DB temp, jamais data/memory.db."""
import json
import importlib

import pytest

import migrations
from memory import Memory


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [1.0, 0.0, 0.0, 0.0])
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_blanch_reflections_pas_le_savoir(mem):
    blanch = importlib.import_module("scripts.blanch_daemon_embeddings")
    r1 = mem.add("reflection", "pensée", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    r2 = mem.add("outreach", "sollicit", importance=0.5, embedding=[1.0, 0.0, 0.0, 0.0])
    s1 = mem.add("semantic", "fait", importance=0.7, embedding=[1.0, 0.0, 0.0, 0.0])
    # ranger la reflection dans une rubrique pour prouver que rubric_id est préservé
    import rubrics
    rubrics.rubric_create(mem.db, "journal", 0)
    rubrics.attach_episode(mem.db, r1, "journal", 0.9, 0)
    mem.db.commit()
    res = blanch.blanch(str(mem.db.execute("PRAGMA database_list").fetchone()[2]))
    assert res["blanched"] == 2                            # les 2 daemon, pas le semantic
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (r1,)).fetchone()[0]) == []
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (r2,)).fetchone()[0]) == []
    assert json.loads(mem.db.execute("SELECT embedding FROM episodes WHERE id=?", (s1,)).fetchone()[0]) != []
    # rubric_id PRÉSERVÉ (on ne déclasse pas les 903 existants)
    assert mem.db.execute("SELECT rubric_id FROM episodes WHERE id=?", (r1,)).fetchone()[0] is not None


def test_blanch_idempotent(mem):
    blanch = importlib.import_module("scripts.blanch_daemon_embeddings")
    mem.add("reflection", "p", importance=0.4, embedding=[1.0, 0.0, 0.0, 0.0])
    mem.db.commit()
    path = str(mem.db.execute("PRAGMA database_list").fetchone()[2])
    assert blanch.blanch(path)["blanched"] == 1
    assert blanch.blanch(path)["blanched"] == 0           # déjà vides → rien à faire
