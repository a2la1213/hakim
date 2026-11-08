import json

import config
import daemon


def test_sonnet_arm_config_present():
    assert config.DREAM_SONNET_ARM_ENABLED in (True, False)
    assert config.DREAM_SONNET_RETRIES >= 1
    assert config.DREAM_SONNET_CALL_DELAY >= 0


class DbMem:
    def __init__(self, conn):
        self.db = conn
        conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
                     "night_id TEXT, dreamer TEXT, content TEXT, meta TEXT)")


def test_sonnet_cells_missing_all_when_empty(tmp_db):
    mem = DbMem(tmp_db)
    assert set(daemon._sonnet_cells_missing(mem, "2026-07-11-0038")) == \
        {"brain_on", "brain_off", "brain_off_free"}


def test_sonnet_cells_missing_tracks_content_by_date(tmp_db):
    mem = DbMem(tmp_db)
    # ON avec contenu → présent ; OFF en engine_failed (content NULL) → reste MANQUANT
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES "
                   "('2026-07-11-0038','sonnet','rêve',?)", (json.dumps({"condition": "brain_on"}),))
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES "
                   "('2026-07-11-0038','sonnet',NULL,?)", (json.dumps({"condition": "brain_off"}),))
    tmp_db.commit()
    # même DATE, autre cycle → ON présent, off+free encore à faire
    assert set(daemon._sonnet_cells_missing(mem, "2026-07-11-0639")) == {"brain_off", "brain_off_free"}


def test_sonnet_cells_missing_ignores_consolidation_ideas(tmp_db):
    mem = DbMem(tmp_db)
    # idée de consolidation (dreamer=sonnet, du contenu, mais AUCUNE condition) → ne remplit aucune cellule
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES "
                   "('2026-07-11','sonnet','(rêve) idée libre',?)", (json.dumps({"source": "consolidate"}),))
    tmp_db.commit()
    assert set(daemon._sonnet_cells_missing(mem, "2026-07-11-0038")) == \
        {"brain_on", "brain_off", "brain_off_free"}


def test_sonnet_cells_missing_best_effort_on_error():
    class BadDB:
        def execute(self, *a, **k):
            raise RuntimeError("db down")

    class Boom:
        db = BadDB()

    assert set(daemon._sonnet_cells_missing(Boom(), "2026-07-11-0038")) == \
        {"brain_on", "brain_off", "brain_off_free"}
