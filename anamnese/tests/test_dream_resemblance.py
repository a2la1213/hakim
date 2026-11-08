import json

import dream_resemblance as R


def _schema(conn):
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, role TEXT, embedding TEXT)")
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, night_id TEXT, "
                 "dreamer TEXT, menu TEXT, content TEXT, meta TEXT)")


def test_cos():
    assert abs(R._cos([1, 0], [1, 0]) - 1.0) < 1e-9
    assert R._cos([1, 0], [0, 1]) == 0.0
    assert R._cos([0, 0], [1, 1]) == 0.0            # norme nulle → 0


def test_corpus_centroid_mean_excludes_non_corpus(tmp_db):
    _schema(tmp_db)
    tmp_db.execute("INSERT INTO episodes VALUES (1,'semantic',?)", (json.dumps([2.0, 0.0]),))
    tmp_db.execute("INSERT INTO episodes VALUES (2,'episodic',?)", (json.dumps([0.0, 2.0]),))
    tmp_db.execute("INSERT INTO episodes VALUES (3,'dream',?)", (json.dumps([9.0, 9.0]),))   # exclu
    tmp_db.execute("INSERT INTO episodes VALUES (4,'insight',?)", (json.dumps([9.0, 9.0]),))  # exclu
    tmp_db.commit()
    assert R.corpus_centroid(tmp_db) == [1.0, 1.0]


def test_corpus_centroid_empty_best_effort(tmp_db):
    _schema(tmp_db)
    assert R.corpus_centroid(tmp_db) == []           # aucun souvenir → []


def test_report_data_gap_on_over_off(tmp_db):
    _schema(tmp_db)
    tmp_db.execute("INSERT INTO episodes VALUES (1,'semantic',?)", (json.dumps([1.0, 0.0]),))   # corpus orienté x
    for co, txt in [("brain_on", "on"), ("brain_off", "off"), ("brain_off_free", "free")]:
        tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES ('2026-07-13','sonnet',?,?)",
                       (txt, json.dumps({"condition": co})))
    tmp_db.commit()
    emb = {"on": [1.0, 0.0], "off": [0.0, 1.0], "free": [0.7, 0.7]}   # ON aligné corpus, OFF orthogonal
    data = R.report_data(tmp_db, lambda t: emb[t])
    assert data["sonnet"]["on"] == 1.0 and data["sonnet"]["off"] == 0.0
    assert data["sonnet"]["gap"] == 1.0                                # ON≫OFF → gap positif
    assert data["centroid_n"] == 1


def test_report_data_no_centroid_is_safe(tmp_db):
    _schema(tmp_db)                                   # pas de souvenirs → pas de centroïde
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES ('2026-07-13','sonnet','x',?)",
                   (json.dumps({"condition": "brain_on"}),))
    tmp_db.commit()
    data = R.report_data(tmp_db, lambda t: [1.0, 0.0])
    assert data["centroid_n"] == 0 and data["sonnet"]["gap"] is None    # rien ne casse
