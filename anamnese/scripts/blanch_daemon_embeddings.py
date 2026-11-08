#!/usr/bin/env python3
"""One-shot : blanchit les embeddings des reflection/outreach déjà en base
(journal daemon jamais rappelé) pour récupérer l'espace. NE supprime RIEN,
ne touche PAS rubric_id. À lancer À LA MAIN :
    .venv/bin/python -m scripts.blanch_daemon_embeddings
"""
import sqlite3
import sys
from pathlib import Path

ROLES = ("reflection", "outreach")


def blanch(db_path, dry_run=False):
    conn = sqlite3.connect(str(db_path), timeout=10)
    try:
        ph = ",".join("?" * len(ROLES))
        rows = conn.execute(
            f"SELECT id, LENGTH(embedding) FROM episodes "
            f"WHERE role IN ({ph}) AND embedding != '[]'", ROLES).fetchall()
        reclaimed = sum((n or 0) for _id, n in rows)
        if not dry_run and rows:
            conn.execute(
                f"UPDATE episodes SET embedding='[]' WHERE role IN ({ph}) AND embedding != '[]'",
                ROLES)
            conn.commit()
        return {"blanched": len(rows), "reclaimed_bytes": reclaimed}
    finally:
        conn.close()


def main():
    try:
        import config
        db = Path(config.DB_PATH)
    except Exception:
        db = Path(__file__).resolve().parent.parent / "data" / "memory.db"
    if not db.exists():
        print(f"DB absente : {db}"); return
    # checkpoint WAL avant (bonne pratique ; le VACUUM éventuel reste à la main)
    try:
        c = sqlite3.connect(str(db)); c.execute("PRAGMA wal_checkpoint(TRUNCATE)"); c.close()
    except Exception:
        pass
    try:
        res = blanch(db)
    except Exception as e:  # base verrouillée (daemon actif) : échec propre, jamais de corruption
        print(f"Blanchiment interrompu ({type(e).__name__}: {e}) — la base est "
              f"peut-être verrouillée (daemon actif). Réessaie plus tard ; rien n'a été corrompu.")
        return
    print(f"Blanchi : {res['blanched']} épisode(s) reflection/outreach — "
          f"~{res['reclaimed_bytes']/1048576:.1f} Mo d'embeddings libérés "
          f"(exécuter `VACUUM` pour compacter le fichier si voulu).")


if __name__ == "__main__":
    main()
