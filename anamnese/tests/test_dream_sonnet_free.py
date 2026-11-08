import json, dream_sonnet

def _seed(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, content TEXT, "
        "facets TEXT, written INT, meta TEXT)")
    st = json.dumps({"hormones": {}, "humeur": "x", "valence": 0.0, "arousal": 0.5, "compassion": 0.5})
    conn.execute("INSERT INTO dream_log (ts,night_id,dreamer,seed_state,menu,chosen,content,facets,written,meta) "
        "VALUES (1.0,'2026-07-09-0300','local',?,NULL,NULL,'x','[]',1,?)",
        (st, json.dumps({"condition": "brain_on"})))
    conn.commit()

def test_build_free_prompt_no_menu():
    p = dream_sonnet.build_free_prompt({"hormones": {"dopamine": 0.5}, "humeur": "x",
                                        "valence": 0.1, "arousal": 0.5, "compassion": 0.5})
    assert "###CHOIX###" not in p and "librement" in p.lower()

def test_pending_free_and_log(tmp_db):
    _seed(tmp_db)
    pend = dream_sonnet.pending_free(tmp_db, limit=10)
    assert len(pend) == 1 and pend[0]["night_id"] == "2026-07-09-0300"
    out = "###REVE###\n- Peut-être que le vide parle.\n###FIN###"
    assert dream_sonnet.free_pair(tmp_db, pend[0], run_fn=lambda p: out) is True
    rows = tmp_db.execute("SELECT meta, menu FROM dream_log WHERE dreamer='sonnet'").fetchall()
    assert len(rows) == 1
    m = json.loads(rows[0][0])
    assert m["condition"] == "brain_off_free" and m["source"] == "free" and rows[0][1] is None

def test_free_pair_deduped(tmp_db):
    _seed(tmp_db)
    p = dream_sonnet.pending_free(tmp_db, limit=10)[0]
    dream_sonnet.free_pair(tmp_db, p, run_fn=lambda x: "###REVE###\n- x\n###FIN###")
    assert dream_sonnet.pending_free(tmp_db, limit=10) == []      # plus pending après un run

def test_free_pair_handles_none(tmp_db):
    _seed(tmp_db)
    p = dream_sonnet.pending_free(tmp_db, limit=10)[0]
    assert dream_sonnet.free_pair(tmp_db, p, run_fn=lambda x: None) is False
    assert tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0] == 0
