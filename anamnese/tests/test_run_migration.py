"""Tests de run_migration — backup réversible (WAL checkpoint), lock, dry-run.

Tout sur tmp_path, JAMAIS data/memory.db (garde _forbid_real_db active).
"""

import os
import sqlite3

import pytest

import migrations
import run_migration

ALL_COLUMNS = [name for name, _ in migrations.EPISODE_COLUMNS]
ALL_TABLES = [name for name, _ in migrations.NEW_TABLES_SQL]


def _make_wal_db(tmp_path, name="seed.db"):
    """DB temp en WAL, schéma legacy episodes + 1 épisode ; la connexion
    reste OUVERTE pour que l'épisode vive encore dans le -wal (le backup
    doit checkpointer AVANT de copier, sinon la copie est incomplète)."""
    path = tmp_path / name
    conn = sqlite3.connect(str(path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE episodes (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            ts         REAL    NOT NULL,
            role       TEXT    NOT NULL,
            content    TEXT    NOT NULL,
            importance REAL    DEFAULT 0.5,
            embedding  TEXT    NOT NULL
        )
        """
    )
    conn.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (1000.0,'user','souvenir wal',0.5,'[]')"
    )
    conn.commit()
    return path, conn


def _episode_contents(db_path):
    conn = sqlite3.connect(str(db_path))
    try:
        return [
            row[0]
            for row in conn.execute("SELECT content FROM episodes ORDER BY id")
        ]
    finally:
        conn.close()


# --- Cas 1 : backup = copie fidèle et lisible, suffixe .bak-<today> exact ---
def test_backup_db_creates_readable_dated_copy(tmp_path):
    db_path, writer = _make_wal_db(tmp_path)
    try:
        backup = run_migration.backup_db(str(db_path), today="2026-07-01")

        # suffixe exact, piloté par le paramètre today (pas l'horloge)
        assert backup == f"{db_path}.bak-2026-07-01"
        assert os.path.exists(backup)
        # copie lisible : l'épisode du -wal a bien été checkpointé puis copié
        assert _episode_contents(backup) == ["souvenir wal"]
        # l'original est intact
        assert _episode_contents(db_path) == ["souvenir wal"]
    finally:
        writer.close()


# --- Cas 2 : no-overwrite — 2e backup du même jour suffixé -2, 1er préservé ---
def test_backup_db_never_overwrites_same_day(tmp_path):
    db_path, writer = _make_wal_db(tmp_path)
    try:
        first = run_migration.backup_db(str(db_path), today="2026-07-01")

        # on modifie l'original ENTRE les deux backups : si le 2e écrasait
        # le 1er, le 1er contiendrait 2 épisodes
        writer.execute(
            "INSERT INTO episodes (ts,role,content,importance,embedding) "
            "VALUES (1001.0,'assistant','deuxieme',0.5,'[]')"
        )
        writer.commit()

        second = run_migration.backup_db(str(db_path), today="2026-07-01")

        assert first == f"{db_path}.bak-2026-07-01"
        assert second == f"{db_path}.bak-2026-07-01-2"
        assert first != second
        assert _episode_contents(first) == ["souvenir wal"]  # non écrasé
        assert _episode_contents(second) == ["souvenir wal", "deuxieme"]
    finally:
        writer.close()


# --- Cas 3 : lock — acquis (PID dedans), double acquisition refusée, release ---
def test_lock_acquire_conflict_release(tmp_path):
    db_path = tmp_path / "t.db"
    db_path.touch()

    lock_path = run_migration.acquire_lock(str(db_path))
    assert lock_path == f"{db_path}.migrate.lock"
    assert os.path.exists(lock_path)
    with open(lock_path) as f:
        assert int(f.read()) == os.getpid()

    # 2e acquisition sur le même chemin → RuntimeError explicite
    with pytest.raises(RuntimeError, match="migration déjà en cours ou lock orphelin"):
        run_migration.acquire_lock(str(db_path))

    # release supprime le fichier → re-acquisition possible
    run_migration.release_lock(lock_path)
    assert not os.path.exists(lock_path)
    lock_path2 = run_migration.acquire_lock(str(db_path))
    assert os.path.exists(lock_path2)
    run_migration.release_lock(lock_path2)


# --- Cas 4 : dry-run — aucun backup, schéma intact, rapport, lock libéré ---
def test_run_dry_run_touches_nothing_and_reports(legacy_db, tmp_path):
    db_path = tmp_path / "legacy.db"  # chemin de la fixture legacy_db

    result = run_migration.run(str(db_path), dry_run=True)

    # aucun backup créé
    assert list(tmp_path.glob("*.bak-*")) == []
    # la DB reste au schéma legacy : ni colonne ni table ajoutée
    cols = {row[1] for row in legacy_db.execute("PRAGMA table_info(episodes)")}
    assert cols == {"id", "ts", "role", "content", "importance", "embedding"}
    tables = {
        row[0]
        for row in legacy_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert not tables.intersection(ALL_TABLES)
    # rapport : dry_run + ce qui SERAIT fait
    assert result["dry_run"] is True
    assert result["backup"] is None
    assert result["migrated"] is None
    assert result["would"]["columns_added"] == ALL_COLUMNS
    assert result["would"]["tables_created"] == ALL_TABLES
    # le lock est libéré
    assert not os.path.exists(f"{db_path}.migrate.lock")


# --- Cas 5 : run réel — backup + migration appliquée + lock libéré + idempotent ---
def test_run_real_migrates_with_backup_and_is_idempotent(legacy_db, tmp_path):
    db_path = tmp_path / "legacy.db"

    result = run_migration.run(str(db_path), today="2026-07-01")

    # backup créé AVANT migration
    assert result["backup"] == f"{db_path}.bak-2026-07-01"
    assert os.path.exists(result["backup"])
    # migration appliquée : colonnes + tables présentes
    cols = {row[1] for row in legacy_db.execute("PRAGMA table_info(episodes)")}
    assert set(ALL_COLUMNS) <= cols
    tables = {
        row[0]
        for row in legacy_db.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    assert set(ALL_TABLES) <= tables
    assert result["dry_run"] is False
    assert result["migrated"]["columns_added"] == ALL_COLUMNS
    assert set(result["migrated"]["tables_created"]) == set(ALL_TABLES)
    # le backup, lui, est resté au schéma legacy (levier de rollback)
    bak_cols = {
        row[1]
        for row in sqlite3.connect(result["backup"]).execute(
            "PRAGMA table_info(episodes)"
        )
    }
    assert bak_cols == {"id", "ts", "role", "content", "importance", "embedding"}
    # lock libéré
    assert not os.path.exists(f"{db_path}.migrate.lock")

    # idempotence : un 2e run ne ré-ajoute rien
    second = run_migration.run(str(db_path), today="2026-07-01")
    assert second["migrated"]["columns_added"] == []
    assert second["migrated"]["tables_created"] == []
    assert not os.path.exists(f"{db_path}.migrate.lock")


# --- Cas 6 : le lock est libéré MÊME si migrate lève (try/finally prouvé) ---
def test_run_releases_lock_even_if_migrate_raises(legacy_db, tmp_path, monkeypatch):
    db_path = tmp_path / "legacy.db"

    def boom(conn):
        raise sqlite3.OperationalError("disk I/O error simulée")

    monkeypatch.setattr(migrations, "migrate", boom)

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error simulée"):
        run_migration.run(str(db_path), today="2026-07-01")

    # l'erreur est propagée MAIS le lock n'est pas resté orphelin
    assert not os.path.exists(f"{db_path}.migrate.lock")
    # et une nouvelle acquisition fonctionne (rien de bloqué)
    lock = run_migration.acquire_lock(str(db_path))
    run_migration.release_lock(lock)
