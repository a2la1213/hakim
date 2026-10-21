import datetime
import glob
import os

import config
import daemon


class BMem:
    """mem minimal : db = vraie connexion sqlite (tmp_db) + kv."""
    def __init__(self, conn, kv=None):
        self.db = conn
        self._kv = dict(kv or {})

    def kv_get(self, k, d=""):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def _seed(conn):
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY)")
    conn.execute("INSERT INTO episodes VALUES (1),(2),(3)")
    conn.commit()


def test_backup_creates_file_and_marks_day(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setattr(config, "BACKUP_KEEP", 7)
    _seed(tmp_db)
    mem = BMem(tmp_db)
    daemon._backup_pass(mem)
    today = datetime.date.today().isoformat()
    files = glob.glob(str(tmp_path / "backups" / "auto-*.db"))
    assert len(files) == 1 and files[0].endswith(f"auto-{today}.db")
    assert mem.kv_get("last_backup_day") == today
    # le backup est une vraie copie lisible
    import sqlite3
    assert sqlite3.connect(files[0]).execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 3


def test_backup_skips_when_already_done_today(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "memory.db"))
    today = datetime.date.today().isoformat()
    _seed(tmp_db)
    mem = BMem(tmp_db, kv={"last_backup_day": today})
    daemon._backup_pass(mem)
    assert not os.path.isdir(tmp_path / "backups")     # rien créé (skip cheap)


def test_backup_rotation_keeps_last_n(tmp_db, tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "memory.db"))
    monkeypatch.setattr(config, "BACKUP_KEEP", 3)
    bdir = tmp_path / "backups"
    bdir.mkdir()
    for d in ["2026-07-01", "2026-07-02", "2026-07-03", "2026-07-04", "2026-07-05"]:
        (bdir / f"auto-{d}.db").write_text("x")
    (bdir / "memory-manuel.db").write_text("garde-moi")   # backup manuel : NE doit PAS être roté
    _seed(tmp_db)
    daemon._backup_pass(BMem(tmp_db))
    autos = sorted(p.name for p in bdir.glob("auto-*.db"))
    assert len(autos) == 3                                 # rotation → 3 plus récents (dont aujourd'hui)
    assert (bdir / "memory-manuel.db").exists()            # manuel préservé


def test_backup_best_effort(tmp_db, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", "/proc/nope/memory.db")   # makedirs échouera
    daemon._backup_pass(BMem(tmp_db))                      # ne doit PAS lever
