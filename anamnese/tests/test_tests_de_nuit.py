"""La batterie fixe rejouée chaque nuit (daemon._tests_de_nuit_pass, lot G point 41)."""
import json
import time

import daemon
import memory
import migrations


def test_une_fois_par_nuit_entre_3_et_6_h(tmp_path, monkeypatch):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    monkeypatch.setattr(daemon.config, "DATA_DIR", tmp_path)
    appels = []

    class R:
        def __init__(self, out, code=0):
            self.stdout, self.returncode = out, code

    def faux_run(cmd, **k):
        appels.append(cmd)
        if "pytest" in cmd:
            return R("917 passed, 2 skipped in 33s")
        if any("batterie_hakim" in str(x) for x in cmd):
            return R('{"reussis": 6, "total": 7, "echecs": {"style_street": "trop guindé"}}')
        return R("actuel 7/7")
    monkeypatch.setattr(daemon.subprocess, "run", faux_run)
    lt = time.localtime()
    a = lambda h: time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 30, 0, 0, 0, -1))
    daemon._tests_de_nuit_pass(m, now=a(14))                       # l'après-midi : rien
    assert appels == []
    daemon._tests_de_nuit_pass(m, now=a(3))
    daemon._tests_de_nuit_pass(m, now=a(4))                        # déjà fait cette nuit
    assert len(appels) == 3                                        # code, souvenirs périmés, batterie de Hakim
    r = json.loads((tmp_path / "nuit-tests.jsonl").read_text().splitlines()[0])
    assert r["ok"] and "917 passed" in r["tests"] and "7/7" in r["perimes"]
    assert r["batterie"]["reussis"] == 6 and "style_street" in r["batterie"]["echecs"]
    m.db.close()
