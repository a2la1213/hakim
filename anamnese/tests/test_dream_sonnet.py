"""Hook Sonnet : ses rêves de 4h30 entrent dans dream_log (lecture seule, dédup,
best-effort). On forge la DB — consolidate n'appelle évidemment pas Claude ici."""
import json
import sqlite3
import time

import migrations

import consolidate


def _forge(tmp_path):
    db = tmp_path / "t.db"
    conn = sqlite3.connect(db)
    # migrate() ne crée ni episodes ni kv (voir migrations.py) — on les forge.
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, "
                 "content TEXT, importance REAL, embedding TEXT)")
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, ts REAL NOT NULL)")
    migrations.migrate(conn)
    now = time.time()
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now, "dream", "(rêve) Peut-être que la mémoire préfère le matin", 0.4, "[]"))
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now, "dream", "(consolidation) 3 faits, 1 idée — trace", 0.3, "[]"))
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)",
                 (now - 7200, "dream", "(rêve) vieille idée d'avant le run", 0.4, "[]"))
    conn.execute("INSERT OR REPLACE INTO kv (key, value, ts) VALUES (?,?,?)",
                 ("affect", json.dumps({"dopamine": 0.7, "_ts": now}), now))
    conn.commit()
    conn.close()
    return db, now


def test_log_sonnet_dreams(tmp_path):
    db, now = _forge(tmp_path)
    n = consolidate.log_sonnet_dreams(db_path=db, since=now - 3600)
    assert n == 1                                     # le (rêve) récent SEUL — pas la trace, pas l'ancien
    conn = sqlite3.connect(db)
    rows = conn.execute("SELECT dreamer, written, menu, seed_state FROM dream_log").fetchall()
    assert rows[0][0] == "sonnet" and rows[0][1] == 1 and rows[0][2] is None
    assert json.loads(rows[0][3])["dopamine"] == 0.7  # snapshot kv affect brut
    # dédup : rejouer le hook n'ajoute rien
    assert consolidate.log_sonnet_dreams(db_path=db, since=now - 3600) == 0
    conn.close()


def test_anti_contamination_reve_local(tmp_path):
    """Un rêve LOCAL tombé pendant le run Sonnet : ses idées "(rêve) X" existent
    dans episodes ET son content brut dans dream_log dreamer='local' — le hook
    ne doit PAS les créditer à Sonnet. Un vrai rêve Sonnet distinct passe."""
    db, now = _forge(tmp_path)
    conn = sqlite3.connect(db)
    idea = "Peut-être que le daemon rêve pendant que Sonnet consolide"
    # l'idée du rêve local, stockée par daemon._store_ideas pendant le run
    conn.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                 "VALUES (?,?,?,?,?)", (now, "dream", "(rêve) " + idea, 0.4, "[]"))
    # la nuit locale correspondante : content = sortie BRUTE du 9B (contient l'idée)
    conn.execute("INSERT INTO dream_log (ts, night_id, dreamer, content, facets, "
                 "written, meta) VALUES (?,?,?,?,?,1,?)",
                 (now, "2026-07-03-0431", "local",
                  "###CHOIX###\n- G1\n###REVE###\n- " + idea + "\n###FIN###",
                  "[]", json.dumps({"parse": "ok"})))
    conn.commit()
    conn.close()
    n = consolidate.log_sonnet_dreams(db_path=db, since=now - 3600)
    assert n == 1                                     # le vrai rêve Sonnet de _forge SEUL
    conn = sqlite3.connect(db)
    sonnet = [r[0] for r in conn.execute(
        "SELECT content FROM dream_log WHERE dreamer='sonnet'").fetchall()]
    assert sonnet == ["(rêve) Peut-être que la mémoire préfère le matin"]
    assert not any(idea in c for c in sonnet)         # l'idée locale JAMAIS créditée sonnet
    conn.close()


def test_best_effort_table_absente(tmp_path):
    db = tmp_path / "legacy.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, "
                 "content TEXT, importance REAL, embedding TEXT)")
    conn.commit()
    conn.close()
    assert consolidate.log_sonnet_dreams(db_path=db, since=0) == 0   # jamais d'exception
