# tests/test_dream_free_pass.py
import json, daemon

class FakeMem:
    def __init__(self, conn):
        self.db = conn; self.added = []; self.coact = []; self.kv = {}
        conn.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, "
            "chosen TEXT, content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): self.added.append((a, k))
    def log_coactivation(self, *a, **k): self.coact.append(a)
    def kv_set(self, k, v): self.kv[k] = v

def test_free_pass_is_journal_only(tmp_db):
    mem = FakeMem(tmp_db)
    out = "###REVE###\n- Peut-être que je rêve de rien.\n###FIN###"
    daemon._dream_free_pass(mem, "2026-07-09-0300", {"hormones": {}}, lambda p: out)
    rows = mem.db.execute("SELECT dreamer, menu, meta, content FROM dream_log").fetchall()
    assert len(rows) == 1
    dreamer, menu, meta, content = rows[0]
    assert dreamer == "local" and menu is None
    m = json.loads(meta)
    assert m["condition"] == "brain_off_free" and m["ablation"] == "no_seeds"
    assert content == out
    assert mem.added == [] and mem.coact == [] and mem.kv == {}   # HYGIÈNE

def test_free_pass_handles_none_output(tmp_db):
    mem = FakeMem(tmp_db)
    daemon._dream_free_pass(mem, "2026-07-09-0300", {"hormones": {}}, lambda p: None)
    rows = mem.db.execute("SELECT meta FROM dream_log").fetchall()
    assert len(rows) == 1 and json.loads(rows[0][0]).get("parse") == "engine_failed"

def test_free_pass_dreamer_param(tmp_db):
    mem = FakeMem(tmp_db)
    daemon._dream_free_pass(mem, "2026-07-10-0300", {"hormones": {}}, lambda p: "###REVE###\n- x\n###FIN###",
                            dreamer="twin")
    dreamer, meta = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchone()
    assert dreamer == "twin" and json.loads(meta)["condition"] == "brain_off_free"
