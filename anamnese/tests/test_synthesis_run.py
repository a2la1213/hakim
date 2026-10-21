# tests/test_synthesis_run.py
import json, synthesis as S

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.added = []; self.coact = []
        conn.executescript(
            "CREATE TABLE episodes (id INTEGER PRIMARY KEY AUTOINCREMENT, role TEXT, content TEXT, embedding TEXT, importance REAL, rubric_id INTEGER);"
            "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
            "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));"
            "CREATE TABLE insight_edges (insight_id INTEGER, source_id INTEGER, PRIMARY KEY(insight_id, source_id));")
    def add(self, role, content, importance=0.5, embedding=None, **k):
        cur = self.db.execute("INSERT INTO episodes (role,content,embedding,importance) VALUES (?,?,?,?)",
                              (role, content, json.dumps(embedding or []), importance))
        self.db.commit(); self.added.append((role, content)); return cur.lastrowid
    def log_coactivation(self, ids, now, boost=0.05): self.coact.append(tuple(ids)); return 1

def _seed_pairs(conn):
    conn.execute("INSERT INTO rubrics VALUES (1,'projets/physique'),(2,'projets/atelier3d')")
    conn.execute("INSERT INTO episodes (id,role,content,embedding,importance,rubric_id) VALUES "
        "(1,'semantic','les 0 et 1 en rotation',?,0.5,1),(2,'semantic','interactions imparfaites',?,0.5,2)",
        (json.dumps([1.0,0.0,0.0]), json.dumps([0.6,0.8,0.0])))
    conn.commit()

def test_store_insight_creates_episode_edges_and_boost(tmp_db):
    mem = FakeMem(tmp_db); _seed_pairs(tmp_db)
    iid = S.store_insight(mem, "Rendre l'interaction parfaite via les 0/1.", [1, 2], "local")
    row = tmp_db.execute("SELECT role, content FROM episodes WHERE id=?", (iid,)).fetchone()
    assert row[0] == "insight" and row[1].startswith("(insight·local)")
    edges = tmp_db.execute("SELECT source_id FROM insight_edges WHERE insight_id=?", (iid,)).fetchall()
    assert sorted(s for (s,) in edges) == [1, 2]
    assert mem.coact and set(mem.coact[0]) == {1, 2}         # rétroaction : sources câblées

def test_run_pipeline_stores_survivors_only(tmp_db, monkeypatch):
    mem = FakeMem(tmp_db); _seed_pairs(tmp_db)
    monkeypatch.setattr(S.embeddings, "embed", lambda t: [0.6, 0.5, 0.0])  # ancré aux 2 sources
    calls = {"n": 0}
    def chat(p):
        # génère une hypothèse, puis tous les sceptiques VALIDENT
        return "NONE" if "SCEPTIQUE" not in p and False else ("Hypothèse concrète." if "COMBINANT" in p else "VALIDE")
    ids = S.run(mem, chat, "local", n_pairs=5)
    assert len(ids) >= 1
    assert all(tmp_db.execute("SELECT role FROM episodes WHERE id=?", (i,)).fetchone()[0] == "insight" for i in ids)
