"""Backfill des facettes (Phase 3.5a) — fonction idempotente, exécution à part.

`backfill_facets(conn)` tague chaque épisode SANS facette (extraction bornée
de facets_extract) et SAUTE les déjà taggés : un 2e appel ne fait rien
(tagged=0). L'exécution sur la vraie base est une étape contrôlée séparée :
ce module n'ouvre JAMAIS une DB tout seul (le main exige un --db explicite),
et rien ne s'exécute à l'import.

Usage (étape contrôlée, hors tests) :
    python eval/backfill_facets.py --db data/memory.db
"""

import pathlib
import sys

# Permet `python eval/backfill_facets.py` depuis n'importe où (sys.path[0] = eval/).
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import facets_extract


def backfill_facets(conn):
    """Tague tous les épisodes encore sans facette. Idempotent.

    conn : connexion sqlite3 ouverte sur une base MIGRÉE (tables facets/
    episode_facets présentes, cf. migrations.migrate). Un épisode dont le
    contenu ne donne aucune facette (ou dont toutes les facettes sont
    refusées par le plafond global) reste non taggé et n'est pas compté.
    Retourne {"tagged": épisodes taggés par CET appel,
              "facets_total": taille actuelle du vocabulaire}.
    """
    rows = conn.execute(
        "SELECT id, content FROM episodes "
        "WHERE id NOT IN (SELECT episode_id FROM episode_facets) ORDER BY id"
    ).fetchall()
    tagged = 0
    for episode_id, content in rows:
        pairs = facets_extract.extract_facets(content)
        if pairs and facets_extract.tag_episode(conn, episode_id, pairs) > 0:
            tagged += 1
    facets_total = conn.execute("SELECT COUNT(*) FROM facets").fetchone()[0]
    return {"tagged": tagged, "facets_total": facets_total}


def main():
    import argparse
    import sqlite3

    parser = argparse.ArgumentParser(
        description="Backfill des facettes sur une base migrée (--db explicite)."
    )
    parser.add_argument("--db", required=True, help="chemin de la base SQLite")
    args = parser.parse_args()
    conn = sqlite3.connect(args.db)
    try:
        result = backfill_facets(conn)
    finally:
        conn.close()
    print(f"tagged={result['tagged']} facets_total={result['facets_total']}")


if __name__ == "__main__":
    main()
