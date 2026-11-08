import json
import types
import daemon
import dream_lab

class FakeMem:
    """mem minimal : dream_log en table réelle (tmp_db) + espions d'écriture."""
    def __init__(self, conn):
        self.db = conn
        self.added, self.coact, self.kv = [], [], {}
        self.db.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY "
            "AUTOINCREMENT, ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, "
            "chosen TEXT, content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): self.added.append((a, k))           # NE DOIT PAS être appelé
    def log_coactivation(self, *a, **k): self.coact.append(a)   # NE DOIT PAS être appelé
    def kv_set(self, k, v): self.kv[k] = v                      # NE DOIT PAS être appelé

def test_ablation_pass_is_journal_only(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "rubric": "science", "strate": "recent",
             "snippet": "la photosynthèse", "facets": []}]
    out = "###CHOIX###\n- G1\n###REVE###\n- Peut-être que la lumière nourrit.\n###FIN###"
    daemon._dream_ablation_pass(mem, "2026-07-09-0300", {"hormones": {}}, menu, lambda p: out)
    rows = mem.db.execute("SELECT dreamer, meta, content FROM dream_log").fetchall()
    assert len(rows) == 1
    dreamer, meta, content = rows[0]
    assert dreamer == "local"
    assert json.loads(meta)["condition"] == "brain_off"
    assert content == out
    # HYGIÈNE : aucune écriture dans le vivant
    assert mem.added == [] and mem.coact == [] and mem.kv == {}

def test_ablation_pass_handles_none_output(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    daemon._dream_ablation_pass(mem, "2026-07-09-0300", {"hormones": {}}, menu, lambda p: None)
    rows = mem.db.execute("SELECT meta FROM dream_log").fetchall()
    assert len(rows) == 1 and json.loads(rows[0][0]).get("parse") == "engine_failed"

def test_ablation_pass_dreamer_and_condition_params(tmp_db):
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    out = "###CHOIX###\n- G1\n###REVE###\n- rêve.\n###FIN###"
    # sonnet ON (menu réel) : dreamer + condition + ablation paramétrés
    daemon._dream_ablation_pass(mem, "2026-07-10-0300", {"hormones": {}}, menu, lambda p: out,
                                dreamer="sonnet", condition="brain_on", ablation="real_seeds")
    dreamer, meta = mem.db.execute("SELECT dreamer, meta FROM dream_log").fetchone()
    m = json.loads(meta)
    assert dreamer == "sonnet" and m["condition"] == "brain_on" and m["ablation"] == "real_seeds"
