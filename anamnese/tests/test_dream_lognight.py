"""Journal dream_log : écritures réel/jumeau, facettes extraites, best-effort."""
import json

import dream_lab
import migrations
from memory import Memory

import pytest


@pytest.fixture
def mem(tmp_path):
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def test_log_reel_et_jumeau(mem):
    st = {"hormones": {}, "humeur": "x", "wm_focus": []}
    menu = [{"episode_id": 1, "rubric": "", "strate": "recent", "snippet": "s", "facets": []}]
    assert dream_lab.log_night(mem, "2026-07-03-0400", "local", st, menu, [1],
                               "Peut-être que le projet batiment avance", True,
                               meta={"parse": "ok"})
    assert dream_lab.log_night(mem, "2026-07-03-0400", "twin", st, menu, [],
                               "(rien)", False)
    rows = mem.db.execute(
        "SELECT dreamer, written, chosen, facets, meta FROM dream_log ORDER BY id").fetchall()
    assert [(r[0], r[1]) for r in rows] == [("local", 1), ("twin", 0)]
    assert json.loads(rows[0][2]) == [1] and json.loads(rows[1][2]) == []
    assert isinstance(json.loads(rows[0][3]), list)              # facettes extraites
    assert json.loads(rows[0][4])["parse"] == "ok"


def test_log_best_effort_ne_leve_jamais(mem):
    mem.db.execute("DROP TABLE dream_log")
    mem.db.commit()
    ok = dream_lab.log_night(mem, "n", "local", None, None, None, "x", True)
    assert ok is False                                           # échec silencieux, pas d'exception


def test_log_best_effort_entree_non_serialisable(mem):
    # 2e mode d'échec : meta non sérialisable en JSON → False, jamais d'exception.
    ok = dream_lab.log_night(mem, "n", "local", None, None, None, "x", True,
                             meta={"x": object()})
    assert ok is False
    assert mem.db.execute("SELECT COUNT(*) FROM dream_log").fetchone()[0] == 0
