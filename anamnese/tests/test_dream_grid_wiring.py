import json

import daemon


class FakeMem:
    def __init__(self, conn):
        self.db = conn
        conn.execute("CREATE TABLE IF NOT EXISTS dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "ts REAL, night_id TEXT, dreamer TEXT, seed_state TEXT, menu TEXT, chosen TEXT, "
            "content TEXT, facets TEXT, written INT, meta TEXT)")
    def add(self, *a, **k): raise AssertionError("add interdit (journal-seul)")
    def log_coactivation(self, *a, **k): raise AssertionError("coact interdit")


MENU = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]


def _rem(p):
    return "###CHOIX###\n- G1\n###REVE###\n- x\n###FIN###"


def _conds(mem, dreamer):
    return {json.loads(mt).get("condition") for d, mt in
            mem.db.execute("SELECT dreamer, meta FROM dream_log WHERE dreamer=? AND content IS NOT NULL",
                           (dreamer,))}


def test_extra_cells_generates_twin_and_full_sonnet(tmp_db, monkeypatch):
    monkeypatch.setattr(daemon.config, "DREAM_TWIN_ENABLED", True)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_ARM_ENABLED", True)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_CALL_DELAY", 0)
    mem = FakeMem(tmp_db)
    menu = [{"episode_id": "N01", "snippet": "x", "rubric": "", "strate": "recent", "facets": []}]
    daemon._dream_extra_cells(mem, "2026-07-11-0038", {"hormones": {}}, menu, menu,
                              {"hormones": {}}, _rem, _rem)
    assert _conds(mem, "twin") >= {"brain_off", "brain_off_free"}
    assert _conds(mem, "sonnet") == {"brain_on", "brain_off", "brain_off_free"}   # les 3 se font


def test_extra_cells_skips_present_sonnet_cells(tmp_db, monkeypatch):
    monkeypatch.setattr(daemon.config, "DREAM_TWIN_ENABLED", False)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_ARM_ENABLED", True)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_CALL_DELAY", 0)
    mem = FakeMem(tmp_db)
    for co in ("brain_on", "brain_off", "brain_off_free"):     # les 3 déjà présentes (contenu) pour la DATE
        tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES "
                       "('2026-07-11-0038','sonnet','déjà',?)", (json.dumps({"condition": co}),))
    tmp_db.commit()
    before = tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0]

    def boom(p):
        raise AssertionError("sonnet ne doit PAS être rappelé si les 3 cellules existent")

    daemon._dream_extra_cells(mem, "2026-07-11-0639", {"hormones": {}}, [{"snippet": "x"}],
                              [{"snippet": "x"}], {"hormones": {}}, _rem, boom)
    after = tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet'").fetchone()[0]
    assert after == before        # aucune nouvelle ligne sonnet


def test_extra_cells_retries_missing_leaving_present_intact(tmp_db, monkeypatch):
    monkeypatch.setattr(daemon.config, "DREAM_TWIN_ENABLED", False)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_ARM_ENABLED", True)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_CALL_DELAY", 0)
    monkeypatch.setattr(daemon.config, "DREAM_SONNET_RETRIES", 2)
    mem = FakeMem(tmp_db)
    # ON déjà présent → NE doit PAS être re-tenté
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,content,meta) VALUES "
                   "('2026-07-11-0038','sonnet','on ok',?)", (json.dumps({"condition": "brain_on"}),))
    tmp_db.commit()
    calls = {"n": 0}

    def down(p):
        calls["n"] += 1
        return None        # claude down → off + free échouent (engine_failed)

    daemon._dream_extra_cells(mem, "2026-07-11-0639", {"hormones": {}}, MENU,
                              MENU, {"hormones": {}}, _rem, down)
    # ON non re-tenté (contenu présent) ; off + free chacun tenté DREAM_SONNET_RETRIES fois
    assert calls["n"] == 2 * daemon.config.DREAM_SONNET_RETRIES
    on_rows = tmp_db.execute("SELECT COUNT(*) FROM dream_log WHERE dreamer='sonnet' "
                             "AND content IS NOT NULL AND meta LIKE '%brain_on%'").fetchone()[0]
    assert on_rows == 1        # ON intact, aucun doublon
