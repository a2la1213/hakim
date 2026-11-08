"""Tests du backup hors-machine (scripts/backup_memory.py) — tout synthétique.

JAMAIS data/memory.db (garde _forbid_real_db active) : source ET destination
sont des tmp_path.
"""

import datetime
import os
import re
import sqlite3
import stat

import pytest

import scripts.backup_memory as backup_mod
from scripts.backup_memory import SAME_VOLUME_WARNING, backup_memory, prune_backups

T0 = datetime.datetime(2027, 1, 1, 3, 15, 0)


def _make_wal_db(tmp_path, name="src.db", rows=3):
    """DB temp en WAL + épisodes ; la connexion reste OUVERTE pour que les
    lignes vivent encore dans le -wal (le backup doit checkpointer AVANT de
    copier, sinon la copie est incomplète)."""
    path = tmp_path / name
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE episodes (id INTEGER PRIMARY KEY, content TEXT)")
    for i in range(rows):
        conn.execute("INSERT INTO episodes (content) VALUES (?)", (f"ep-{i}",))
    conn.commit()
    return path, conn


def test_backup_creates_readable_timestamped_copy(tmp_path):
    src, conn = _make_wal_db(tmp_path, rows=5)
    dest = tmp_path / "bk"
    res = backup_memory(db_path=src, dest_dir=dest, keep=14, now=T0)

    assert re.match(r"^memory-20270101-031500\.db$", res["backup"].rsplit("/", 1)[-1])
    # copie LISIBLE et COMPLÈTE (les 5 lignes, y compris celles du -wal)
    bconn = sqlite3.connect(res["backup"])
    assert bconn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0] == 5
    bconn.close()
    conn.close()


def test_wal_checkpoint_applied_before_copy(tmp_path):
    """Après backup, le -wal source est vidé (TRUNCATE) : tout est dans le .db."""
    src, conn = _make_wal_db(tmp_path, rows=4)
    wal = tmp_path / "src.db-wal"
    assert wal.stat().st_size > 0  # les lignes vivent bien dans le -wal avant
    backup_memory(db_path=src, dest_dir=tmp_path / "bk", keep=14, now=T0)
    assert wal.stat().st_size == 0  # checkpoint TRUNCATE passé
    conn.close()


def test_never_overwrites_same_second(tmp_path):
    src, conn = _make_wal_db(tmp_path)
    dest = tmp_path / "bk"
    r1 = backup_memory(db_path=src, dest_dir=dest, keep=14, now=T0)
    r2 = backup_memory(db_path=src, dest_dir=dest, keep=14, now=T0)
    assert r1["backup"] != r2["backup"]
    assert r2["backup"].endswith("memory-20270101-031500-2.db")
    assert sorted(p.name for p in dest.glob("memory-*.db")) == [
        "memory-20270101-031500-2.db",
        "memory-20270101-031500.db",
    ]
    conn.close()


def test_prune_keeps_last_n(tmp_path):
    src, conn = _make_wal_db(tmp_path)
    dest = tmp_path / "bk"
    keep = 3
    for i in range(keep + 3):  # 6 backups, horloges croissantes
        res = backup_memory(
            db_path=src, dest_dir=dest, keep=keep,
            now=T0 + datetime.timedelta(days=i),
        )
    names = sorted(p.name for p in dest.glob("memory-*.db"))
    assert len(names) == keep
    assert res["kept"] == keep
    # les 3 plus RÉCENTS survivent (jours 3, 4, 5), les plus vieux sont élagués
    assert names == [
        "memory-20270104-031500.db",
        "memory-20270105-031500.db",
        "memory-20270106-031500.db",
    ]
    conn.close()


def test_prune_removes_sidecars_of_old_backups(tmp_path):
    dest = tmp_path / "bk"
    dest.mkdir()
    for i, name in enumerate(["memory-20270101-000000.db", "memory-20270102-000000.db"]):
        (dest / name).write_bytes(b"x")
        (dest / (name + "-wal")).write_bytes(b"w")
        ts = 1_000_000 + i  # mtimes croissants explicites
        os.utime(dest / name, (ts, ts))
    removed = prune_backups(dest, keep=1)
    assert sorted(p.name for p in dest.iterdir()) == [
        "memory-20270102-000000.db",
        "memory-20270102-000000.db-wal",
    ]
    assert len(removed) == 2  # le vieux .db ET son sidecar


def test_missing_source_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        backup_memory(db_path=tmp_path / "absent.db", dest_dir=tmp_path / "bk", keep=3)


def test_dest_dir_created_nested(tmp_path):
    src, conn = _make_wal_db(tmp_path)
    dest = tmp_path / "a" / "b" / "c"
    res = backup_memory(db_path=src, dest_dir=dest, keep=3, now=T0)
    assert dest.is_dir() and (dest / "memory-20270101-031500.db").exists()
    assert res["kept"] == 1
    conn.close()


def test_source_untouched_by_backup(tmp_path):
    """Idempotent côté source : contenu identique avant/après (checkpoint à part)."""
    src, conn = _make_wal_db(tmp_path, rows=2)
    before = conn.execute("SELECT COUNT(*), MAX(content) FROM episodes").fetchone()
    backup_memory(db_path=src, dest_dir=tmp_path / "bk", keep=3, now=T0)
    assert conn.execute("SELECT COUNT(*), MAX(content) FROM episodes").fetchone() == before
    conn.close()


def test_cli_main_prints_backup_path(tmp_path, capsys):
    from scripts.backup_memory import main
    src, conn = _make_wal_db(tmp_path)
    dest = tmp_path / "bk"
    main(["--db", str(src), "--dest", str(dest), "--keep", "2"])
    out = capsys.readouterr().out
    assert "Backup  : " in out and "memory-" in out
    assert "rotation à 2" in out
    conn.close()


def test_backup_files_are_owner_only_0600(tmp_path):
    """Identité personnelle en clair : le backup (ET ses sidecars) passent en
    0600, quel que soit le umask ou le mode de la source. Les sidecars -wal/
    -shm existent encore (vides) tant que la connexion source est ouverte,
    donc ils sont copiés et doivent être protégés aussi."""
    src, conn = _make_wal_db(tmp_path, rows=2)
    os.chmod(src, 0o644)  # source volontairement plus ouverte que 600
    res = backup_memory(db_path=src, dest_dir=tmp_path / "bk", keep=3, now=T0)
    assert res["sidecars"], "les sidecars -wal/-shm devraient être copiés"
    for path in [res["backup"]] + res["sidecars"]:
        assert stat.S_IMODE(os.stat(path).st_mode) == 0o600, path
    conn.close()


def test_same_volume_detected_in_result(tmp_path):
    """src et dest dans le même tmp_path => même volume, flag True."""
    src, conn = _make_wal_db(tmp_path)
    res = backup_memory(db_path=src, dest_dir=tmp_path / "bk", keep=3, now=T0)
    assert res["same_volume"] is True
    conn.close()


def test_cli_warns_when_same_volume(tmp_path, capsys):
    """Le warning même-volume sort sur STDERR (visible en CLI et backup.err)."""
    from scripts.backup_memory import main
    src, conn = _make_wal_db(tmp_path)
    main(["--db", str(src), "--dest", str(tmp_path / "bk"), "--keep", "2"])
    captured = capsys.readouterr()
    assert SAME_VOLUME_WARNING in captured.err
    assert SAME_VOLUME_WARNING not in captured.out
    conn.close()


def test_cli_silent_when_off_volume(tmp_path, capsys, monkeypatch):
    """Dest sur un AUTRE volume (simulé) : aucun warning — le cas nominal visé."""
    from scripts.backup_memory import main
    src, conn = _make_wal_db(tmp_path)
    monkeypatch.setattr(backup_mod, "_same_volume", lambda a, b: False)
    main(["--db", str(src), "--dest", str(tmp_path / "bk"), "--keep", "2"])
    assert SAME_VOLUME_WARNING not in capsys.readouterr().err
    conn.close()


def test_same_volume_helper_assumes_true_on_stat_error(tmp_path):
    """stat impossible => True (warning en trop plutôt que fausse assurance)."""
    assert backup_mod._same_volume(tmp_path / "nope", tmp_path) is True
    assert backup_mod._same_volume(tmp_path, tmp_path) is True


def test_missing_dest_dir_created_with_backup_inside(tmp_path):
    """config.BACKUP_DIR inexistant (simulé par un dest inexistant) : créé
    (mkdir -p) et le backup atterrit dedans, en 0600."""
    src, conn = _make_wal_db(tmp_path)
    dest = tmp_path / "pas-encore-la"
    assert not dest.exists()
    res = backup_memory(db_path=src, dest_dir=dest, keep=3, now=T0)
    assert dest.is_dir()
    assert res["backup"].startswith(str(dest))
    assert stat.S_IMODE(os.stat(res["backup"]).st_mode) == 0o600
    conn.close()
