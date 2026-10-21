import json, daemon, config

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.coact = []
        conn.executescript(
            "CREATE TABLE episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, embedding TEXT, importance REAL, rubric_id INTEGER);"
            "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
            "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));"
            "CREATE TABLE insight_edges (insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id));")
    def add(self, role, content, importance=0.5, embedding=None, **k):
        cur = self.db.execute("INSERT INTO episodes (role,content,embedding,importance) VALUES (?,?,?,?)",
                              (role, content, json.dumps(embedding or []), importance)); self.db.commit(); return cur.lastrowid
    def log_coactivation(self, ids, now, boost=0.05): self.coact.append(tuple(ids)); return 1

def test_synthesis_pass_respects_killswitch(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "SYNTHESIS_ENABLED", False)
    called = {"n": 0}
    monkeypatch.setattr(daemon.synthesis, "run", lambda *a, **k: called.__setitem__("n", called["n"] + 1) or [])
    daemon._synthesis_pass(FakeMem(tmp_db), lambda p: "x")
    assert called["n"] == 0                              # kill-switch off → run jamais appelé

def test_synthesis_pass_best_effort(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "SYNTHESIS_ENABLED", True)
    monkeypatch.setattr(daemon.synthesis, "run", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    daemon._synthesis_pass(FakeMem(tmp_db), lambda p: "x")   # ne doit PAS lever
