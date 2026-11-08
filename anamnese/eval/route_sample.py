"""Rapport d'échantillon LECTURE SEULE du routage par règles — AVANT le run réel.

Imprime, sur la VRAIE base (`config.DB_PATH`), ce que la passe RÈGLES de
`routing.route_all` ferait : compte par rubrique, et pour CHAQUE mot-clé
Unification/AppLecture la liste des épisodes matchés (id + extrait 80 chars).
C'est le document à relire avec Ahmed avant d'autoriser toute écriture.

GARANTIES de non-écriture :
- la base est ouverte en URI `mode=ro` : SQLite REFUSE physiquement tout
  write (readonly database), quoi que fasse le code appelé ;
- `routing.route_report` ne fait que des SELECT (prouvé par test).

Usage : .venv/bin/python eval/route_sample.py
"""

import pathlib
import sqlite3
import sys

# Permet `python eval/route_sample.py` depuis n'importe où (sys.path[0] = eval/).
_ROOT = pathlib.Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import config   # noqa: E402
import routing  # noqa: E402

EXCERPT_LEN = 80  # extrait de contenu imprimé par hit


def _connect_read_only(db_path):
    """Connexion STRICTEMENT lecture seule (URI mode=ro)."""
    uri = pathlib.Path(db_path).resolve().as_uri() + "?mode=ro"
    return sqlite3.connect(uri, uri=True)


def _excerpt(conn, episode_id):
    row = conn.execute(
        "SELECT content FROM episodes WHERE id=?", (episode_id,)
    ).fetchone()
    content = (row[0] or "") if row else ""
    return content.replace("\n", " ")[:EXCERPT_LEN]


def main():
    conn = _connect_read_only(config.DB_PATH)
    try:
        total = conn.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
        report = routing.route_report(conn)

        print(f"Rapport d'échantillon routage (LECTURE SEULE) — {config.DB_PATH}")
        print(f"{total} épisodes en base.\n")

        print("== Compte par rubrique (passe RÈGLES uniquement) ==")
        for path, n in sorted(
            report["by_rule_counts"].items(), key=lambda kv: (-kv[1], kv[0])
        ):
            print(f"  {path:<24} {n}")
        print(f"  {'(aucune règle -> centroïde/NULL)':<32} {report['unmatched']}")

        for title, keywords in (
            ("Unification", routing.UNIFICATION_KEYWORDS),
            ("AppLecture", routing.QURAN_KEYWORDS),
        ):
            print(f"\n== Hits par mot-clé {title} ==")
            for kw in keywords:
                ids = report["by_keyword"].get(kw, [])
                print(f"-- {kw} : {len(ids)} hit(s)")
                for eid in ids:
                    print(f"   #{eid}  {_excerpt(conn, eid)}")

        print("\nRien n'a été écrit (base ouverte en mode=ro).")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
