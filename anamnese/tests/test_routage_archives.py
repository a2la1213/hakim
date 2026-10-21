"""(2026-10-21) « archives » n'est jamais choisie par le routage automatique : vu ce jour-là, son centroïde attirait
84 % des échanges mémorisés, que le rappel ignorait ensuite."""
import json
import sqlite3

import migrations
import routing


def test_archives_jamais_routee(tmp_path):
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, ts REAL, role TEXT, content TEXT, importance REAL, embedding TEXT)")
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT, ts REAL)")
    migrations.migrate(conn)
    v = [1.0, 0.0, 0.0]
    for path, c in (("archives", v), ("profil", [0.0, 1.0, 0.0])):
        conn.execute("INSERT INTO rubrics (path, label, centroid, centroid_n, depth, memory_count) VALUES (?,?,?,?,0,5)",
                     (path, path, json.dumps(c), 5))
    conn.commit()
    path, _conf = routing.route_episode(conn, {"role": "episodic", "content": "[Échange avec Ahmed] salut", "embedding": json.dumps(v)})
    assert path != "archives"
    assert not routing.routable("archives") and not routing.routable("archives/vieux") and routing.routable("profil")
