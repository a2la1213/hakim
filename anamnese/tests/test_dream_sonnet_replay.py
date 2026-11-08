# tests/test_dream_sonnet_replay.py
import json
import dream_sonnet

def _seed_dreamlog(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, "
        "night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, content TEXT, "
        "facets TEXT, written INT, meta TEXT)")
    menu = [{"episode_id": 1, "rubric": "coran", "strate": "recent", "snippet": "racine du prophète", "facets": []}]
    conn.execute("INSERT INTO dream_log (ts,night_id,dreamer,seed_state,menu,chosen,content,facets,written,meta) "
        "VALUES (1.0,'2026-07-09-0300','local',?,?,?,?,'[]',1,?)",
        (json.dumps({"hormones": {}, "humeur": "x", "valence": 0.0, "arousal": 0.5, "compassion": 0.5}),
         json.dumps(menu), json.dumps([1]), "un rêve local", json.dumps({"condition": "brain_on"})))
    conn.commit()
    return menu

def test_build_sonnet_prompt_uses_shared_template():
    menu = [{"episode_id": 1, "rubric": "coran", "strate": "recent", "snippet": "racine", "facets": []}]
    state = {"hormones": {"dopamine": 0.5}, "humeur": "x", "valence": 0.1, "arousal": 0.5, "compassion": 0.5}
    p = dream_sonnet.build_sonnet_prompt(state, menu)
    assert "PHASE DE RÊVE" in p and "[G1]" in p                # même gabarit que qwen

def test_pending_and_replay_logs_sonnet(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)
    assert len(pend) == 1 and pend[0]["night_id"] == "2026-07-09-0300"
    out = "###CHOIX###\n- G1\n###REVE###\n- Peut-être que la racine résonne.\n###FIN###"
    ok = dream_sonnet.replay_pair(tmp_db, pend[0], "brain_on", run_fn=lambda p: out)
    assert ok
    rows = tmp_db.execute("SELECT dreamer, meta, content FROM dream_log WHERE dreamer='sonnet'").fetchall()
    assert len(rows) == 1
    assert json.loads(rows[0][1])["condition"] == "brain_on"
    assert json.loads(rows[0][1])["source"] == "replay"

def test_replay_is_deduped(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)[0]
    out = "###CHOIX###\n- G1\n###REVE###\n- x\n###FIN###"
    dream_sonnet.replay_pair(tmp_db, pend, "brain_on", run_fn=lambda p: out)
    # après un replay, la nuit n'est plus pending
    assert dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10) == []

def test_replay_handles_none(tmp_db):
    _seed_dreamlog(tmp_db)
    pend = dream_sonnet.pending_pairs(tmp_db, "brain_on", limit=10)[0]
    ok = dream_sonnet.replay_pair(tmp_db, pend, "brain_on", run_fn=lambda p: None)
    assert ok is False
    assert tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0] == 0
