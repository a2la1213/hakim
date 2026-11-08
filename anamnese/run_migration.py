"""Runner de la migration Phase 0 — sécurité opérationnelle autour de
`migrations.migrate` (qui reste la seule source de vérité du schéma).

Trois garde-fous, parce que la DB tourne en WAL avec d'autres écrivains
potentiels (daemon, MCP) :
- backup RÉVERSIBLE : `PRAGMA wal_checkpoint(TRUNCATE)` d'abord (rapatrie le
  -wal dans le .db), copie datée ensuite — un `cp` seul raterait les écritures
  encore dans le -wal. Le backup EST le levier de rollback.
- lock fichier atomique (`O_CREAT|O_EXCL`) : WAL = 1 seul writer, on refuse
  deux migrations concurrentes.
- dry-run : ouverture en LECTURE SEULE, rapporte ce qui SERAIT fait sans
  backup ni écriture.

Usage : python run_migration.py [--db PATH] [--dry-run]
Rien ne s'exécute à l'import.
"""

import argparse
import datetime
import os
import shutil
import sqlite3

import config
import migrations


def backup_db(db_path, today=None):
    """Checkpoint WAL puis copie `db_path` vers `<db_path>.bak-<today>`.

    N'écrase JAMAIS un backup existant du même jour (suffixe -2, -3…).
    `today` (str "YYYY-MM-DD") est injectable pour tester sans horloge réelle.
    Retourne le chemin du backup créé.
    """
    db_path = os.fspath(db_path)
    if today is None:
        today = datetime.date.today().isoformat()

    # Connexion courte, dédiée au checkpoint : tout le -wal passe dans le .db,
    # la copie du seul fichier .db est donc complète et fidèle.
    conn = sqlite3.connect(db_path)
    try:
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()

    backup_path = f"{db_path}.bak-{today}"
    n = 2
    while os.path.exists(backup_path):
        backup_path = f"{db_path}.bak-{today}-{n}"
        n += 1
    shutil.copy2(db_path, backup_path)
    return backup_path


def acquire_lock(db_path):
    """Crée `<db_path>.migrate.lock` de façon atomique (O_CREAT|O_EXCL), PID
    dedans. Lève RuntimeError si le lock existe déjà. Retourne son chemin."""
    lock_path = f"{os.fspath(db_path)}.migrate.lock"
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(
            f"migration déjà en cours ou lock orphelin : {lock_path}"
        ) from None
    try:
        os.write(fd, str(os.getpid()).encode("ascii"))
    finally:
        os.close(fd)
    return lock_path


def release_lock(lock_path):
    """Supprime le fichier de lock."""
    os.unlink(lock_path)


def _pending_changes(conn):
    """Ce que `migrations.migrate` FERAIT sur cette DB (lecture seule) —
    calculé depuis les déclarations publiques de migrations, pas redéfini."""
    tables = {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }
    columns = []
    if "episodes" in tables:
        existing = {row[1] for row in conn.execute("PRAGMA table_info(episodes)")}
        columns = [name for name, _ in migrations.EPISODE_COLUMNS if name not in existing]
    pending_tables = [name for name, _ in migrations.NEW_TABLES_SQL if name not in tables]
    return {"columns_added": columns, "tables_created": pending_tables}


def run(db_path, dry_run=False, today=None):
    """Orchestre : lock → backup (sauf dry-run) → migrate (sauf dry-run) →
    release du lock TOUJOURS (try/finally, même si migrate lève).

    Retourne {"backup": path|None, "migrated": dict|None, "dry_run": bool,
    "would": dict|None} (`would` = rapport dry-run, même forme que migrate).
    """
    db_path = os.fspath(db_path)
    lock_path = acquire_lock(db_path)
    try:
        if dry_run:
            # Lecture seule : impossible d'écrire quoi que ce soit par erreur.
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            try:
                would = _pending_changes(conn)
            finally:
                conn.close()
            return {"backup": None, "migrated": None, "dry_run": True, "would": would}

        backup = backup_db(db_path, today=today)
        conn = sqlite3.connect(db_path)
        try:
            migrated = migrations.migrate(conn)
        finally:
            conn.close()
        return {"backup": backup, "migrated": migrated, "dry_run": False, "would": None}
    finally:
        release_lock(lock_path)


def main(argv=None):
    """CLI : python run_migration.py [--db PATH] [--dry-run]."""
    parser = argparse.ArgumentParser(
        description="Migration Phase 0 (backup WAL-checkpoint réversible + lock)."
    )
    parser.add_argument(
        "--db", default=str(config.DB_PATH), help=f"chemin de la DB (défaut : {config.DB_PATH})"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="rapporte ce qui serait fait, sans rien écrire"
    )
    args = parser.parse_args(argv)

    result = run(args.db, dry_run=args.dry_run)
    if result["dry_run"]:
        print(f"[dry-run] DB : {args.db}")
        print(f"[dry-run] colonnes qui seraient ajoutées : {result['would']['columns_added']}")
        print(f"[dry-run] tables qui seraient créées     : {result['would']['tables_created']}")
    else:
        print(f"DB       : {args.db}")
        print(f"Backup   : {result['backup']}")
        print(f"Colonnes ajoutées : {result['migrated']['columns_added']}")
        print(f"Tables créées     : {result['migrated']['tables_created']}")


if __name__ == "__main__":
    main()
