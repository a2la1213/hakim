"""Backup HORS-MACHINE de la mémoire (data/memory.db) — protéger l'actif entier.

La DB tourne en WAL avec d'autres écrivains potentiels (daemon, MCP), donc
même pattern que run_migration.backup_db :
- `PRAGMA wal_checkpoint(TRUNCATE)` D'ABORD (rapatrie le -wal dans le .db) —
  un `cp` seul raterait les écritures encore dans le -wal ;
- busy_timeout : si un écrivain tient la DB, on ATTEND au lieu d'échouer sec ;
- copie datée `memory-YYYYMMDD-HHMMSS.db` dans BACKUP_DIR (défaut
  $HOME/anamnese-backups/, surchargeable par ANAMNESE_BACKUP_DIR ou --dest) ;
- les sidecars -wal/-shm encore présents (checkpoint incomplet si des
  lecteurs actifs bloquent TRUNCATE) sont copiés aussi : la copie reste
  ouvrable telle quelle par SQLite ;
- n'écrase JAMAIS un backup existant (suffixe -2, -3…) ;
- rotation : garde les BACKUP_KEEP plus récents, élague le reste (avec leurs
  sidecars). Idempotent : relancer ne casse rien ;
- chmod 600 sur chaque fichier copié : la DB est de la donnée d'identité
  personnelle en clair — lisible par le seul propriétaire ;
- détection même-volume (st_dev) : un backup sur le MÊME disque que la source
  ne protège pas d'un disque qui meurt — avertit et recommande de pointer
  ANAMNESE_BACKUP_DIR vers un volume synchronisé (iCloud/Drive) ou externe.

Usage : python scripts/backup_memory.py [--dest PATH] [--db PATH] [--keep N]
Rien ne s'exécute à l'import.
"""

import argparse
import datetime
import os
import re
import shutil
import sqlite3
import sys
from pathlib import Path

# Le script vit dans scripts/ : rendre config importable depuis la racine.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config

BUSY_TIMEOUT_MS = 10_000  # écrivain concurrent (daemon/MCP) : attendre, pas échouer
BACKUP_MODE = 0o600  # identité personnelle en clair : propriétaire seul

# Avertissement même-volume (affiché par main, flag `same_volume` dans le résultat)
SAME_VOLUME_WARNING = (
    "⚠️ backup sur le MÊME volume que la source — pointez ANAMNESE_BACKUP_DIR "
    "vers un volume synchronisé (iCloud/Drive) ou externe"
)

# Nom des backups : memory-YYYYMMDD-HHMMSS[-n].db (+ .db-wal / .db-shm)
_BACKUP_RE = re.compile(r"^memory-\d{8}-\d{6}(-\d+)?\.db$")
_SIDECARS = ("-wal", "-shm")


def _same_volume(a, b):
    """True si `a` et `b` vivent sur le même volume (st_dev identique).

    Un backup même-volume ne protège PAS d'un disque qui meurt — c'est le
    signal du warning. En cas de doute (stat impossible), on suppose True :
    mieux vaut un warning en trop qu'une fausse assurance hors-machine.
    """
    try:
        return os.stat(os.fspath(a)).st_dev == os.stat(os.fspath(b)).st_dev
    except OSError:
        return True


def _checkpoint(db_path):
    """Connexion courte dédiée : tout le -wal passe dans le .db avant copie.

    busy_timeout côté connexion : un writer concurrent fait ATTENDRE le
    checkpoint au lieu de le faire échouer. Un checkpoint partiel (lecteurs
    actifs) n'est PAS une erreur : les sidecars sont copiés en plus.
    """
    conn = sqlite3.connect(os.fspath(db_path), timeout=BUSY_TIMEOUT_MS / 1000.0)
    try:
        conn.execute(f"PRAGMA busy_timeout={BUSY_TIMEOUT_MS}")
        conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        conn.close()


def _list_backups(dest_dir):
    """Backups .db présents dans dest_dir, du plus RÉCENT au plus ancien
    (mtime de création — copyfile, pas copy2 — puis nom en tie-break)."""
    dest_dir = Path(dest_dir)
    if not dest_dir.is_dir():
        return []
    entries = [p for p in dest_dir.iterdir() if _BACKUP_RE.match(p.name)]
    return sorted(entries, key=lambda p: (p.stat().st_mtime, p.name), reverse=True)


def prune_backups(dest_dir, keep):
    """Élague au-delà des `keep` plus récents (+ leurs sidecars). Retourne
    la liste des chemins supprimés."""
    removed = []
    for old in _list_backups(dest_dir)[max(0, int(keep)):]:
        for path in [old] + [Path(str(old) + s) for s in _SIDECARS]:
            if path.exists():
                path.unlink()
                removed.append(str(path))
    return removed


def backup_memory(db_path=None, dest_dir=None, keep=None, now=None):
    """Checkpoint WAL puis copie datée de la DB vers dest_dir, rotation à `keep`.

    N'écrase JAMAIS un backup existant (suffixe -2, -3…). Chaque fichier créé
    passe en 0o600 (donnée d'identité personnelle). `now` (datetime) est
    injectable pour tester sans horloge réelle. Retourne
    {"backup": path, "sidecars": [paths], "pruned": [paths], "kept": int,
     "same_volume": bool} — same_volume=True signale un backup qui ne protège
    pas d'un disque qui meurt (main() affiche le warning).
    """
    db_path = Path(os.fspath(db_path if db_path is not None else config.DB_PATH))
    dest_dir = Path(os.fspath(dest_dir if dest_dir is not None else config.BACKUP_DIR))
    keep = config.BACKUP_KEEP if keep is None else int(keep)
    if not db_path.exists():
        raise FileNotFoundError(f"DB introuvable : {db_path}")
    dest_dir.mkdir(parents=True, exist_ok=True)

    _checkpoint(db_path)

    if now is None:
        now = datetime.datetime.now()
    stamp = now.strftime("%Y%m%d-%H%M%S")
    backup_path = dest_dir / f"memory-{stamp}.db"
    n = 2
    while backup_path.exists():
        backup_path = dest_dir / f"memory-{stamp}-{n}.db"
        n += 1

    # copyfile (PAS copy2) : mtime = instant du backup, pas celui de la
    # source — le tri de rotation et l'âge « dernier backup » (health.py)
    # reposent dessus. chmod 600 : identité personnelle en clair.
    shutil.copyfile(db_path, backup_path)
    os.chmod(backup_path, BACKUP_MODE)
    sidecars = []
    for suffix in _SIDECARS:
        src = Path(str(db_path) + suffix)
        if src.exists():
            dst = Path(str(backup_path) + suffix)
            shutil.copyfile(src, dst)
            os.chmod(dst, BACKUP_MODE)
            sidecars.append(str(dst))

    pruned = prune_backups(dest_dir, keep)
    return {
        "backup": str(backup_path),
        "sidecars": sidecars,
        "pruned": pruned,
        "kept": len(_list_backups(dest_dir)),
        "same_volume": _same_volume(db_path, dest_dir),
    }


def main(argv=None):
    """CLI : python scripts/backup_memory.py [--dest PATH] [--db PATH] [--keep N]."""
    parser = argparse.ArgumentParser(
        description="Backup hors-machine de la mémoire (WAL-checkpoint + copie datée + rotation)."
    )
    parser.add_argument(
        "--dest", default=str(config.BACKUP_DIR),
        help=f"répertoire de destination (défaut : {config.BACKUP_DIR})",
    )
    parser.add_argument(
        "--db", default=str(config.DB_PATH),
        help=f"chemin de la DB source (défaut : {config.DB_PATH})",
    )
    parser.add_argument(
        "--keep", type=int, default=config.BACKUP_KEEP,
        help=f"nombre de backups conservés (défaut : {config.BACKUP_KEEP})",
    )
    args = parser.parse_args(argv)

    result = backup_memory(db_path=args.db, dest_dir=args.dest, keep=args.keep)
    print(f"Backup  : {result['backup']}")
    if result["sidecars"]:
        print(f"Sidecars: {', '.join(result['sidecars'])}")
    if result["pruned"]:
        print(f"Élagués : {len(result['pruned'])} fichier(s)")
    print(f"Conservés dans {args.dest} : {result['kept']} (rotation à {args.keep})")
    if result["same_volume"]:
        # stderr : visible en CLI ET dans backup.err via launchd — un backup
        # même-disque n'est PAS une stratégie hors-machine.
        print(SAME_VOLUME_WARNING, file=sys.stderr)


if __name__ == "__main__":
    main()
