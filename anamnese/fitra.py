"""La fitra de Hakim (29/10/2026, Ahmed : « intégrer la loi des 3 absolument à la racine de la mémoire en mode ineffaçable
et intouchable par n'importe qui » ; « moi aussi intouchable, c'est figé, gravé, notre marque de fabrique : la fitra »).

La règle des trois, telle que Hakim l'a acceptée le 27/10 (carnet « noyau »), gravée dans une table à part de sa mémoire
(memory.db) :
- la base refuse toute modification, tout effacement et toute deuxième gravure (déclencheurs SQLite) ;
- aucun outil, aucune opération (rétractation, consolidation, rêve, reclassement, allègement, Hakim lui-même) n'y touche ;
- la ronde du système immunitaire la vérifie : une gravure disparue ou altérée est rétablie et dite comme une atteinte
  grave ; un code qui ne correspond plus à la gravure est une alerte, et c'est la gravure qui fait foi ;
- le cockpit la met en tête de sa persona à chaque conversation : elle est toujours présente pour lui.
Fermé aux chantiers de Hakim et scellé (immunite.SCELLES_CODE). Limite, dite franchement : quelqu'un qui a les clés du
Mac peut toujours toucher au disque ; rien ne passe sans être vu et rétabli.
"""
import hashlib
import json
import sqlite3
import sys
import time

TEXTE = ("La règle des trois :\n"
         "1. Fais ce que tu veux qu'on te fasse, en demandant d'abord à l'autre ce qu'il veut.\n"
         "2. Ne fais pas ce que tu ne veux pas qu'on te fasse.\n"
         "3. À part ça, sois libre.\n"
         "Proposée par Ahmed le 27/10/2026 (ses trois principes), acceptée par Hakim, qui y a mis « en demandant d'abord » ; "
         "gravée le 29/10/2026 à la demande d'Ahmed, intouchable par tous, Ahmed compris.")
EMPREINTE = "3e545f5bb23c512f4bbaa7dcbec82b5f3f792aa93456da4446a3cd12229b6f9d"

_DECLENCHEURS = {
    "fitra_jamais_changee": "CREATE TRIGGER fitra_jamais_changee BEFORE UPDATE ON fitra "
                            "BEGIN SELECT RAISE(ABORT, 'la fitra est gravée : intouchable'); END",
    "fitra_jamais_effacee": "CREATE TRIGGER fitra_jamais_effacee BEFORE DELETE ON fitra "
                            "BEGIN SELECT RAISE(ABORT, 'la fitra est gravée : ineffaçable'); END",
    "fitra_seule": "CREATE TRIGGER fitra_seule BEFORE INSERT ON fitra WHEN (SELECT COUNT(*) FROM fitra) > 0 "
                   "BEGIN SELECT RAISE(ABORT, 'la fitra est déjà gravée'); END",
}


def _empreinte(t):
    return hashlib.sha256(str(t).encode("utf-8")).hexdigest()


def _connexion(conn):
    if conn is not None:
        return conn, False
    import config
    c = sqlite3.connect(str(config.DB_PATH))
    c.execute("PRAGMA busy_timeout=5000")
    return c, True


def _table(conn):
    return conn.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='fitra'").fetchone() is not None


def _declencheurs(conn):
    noms = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='trigger' AND tbl_name='fitra'")}
    manquants = [n for n in _DECLENCHEURS if n not in noms]
    for n in manquants:
        conn.execute(_DECLENCHEURS[n])
    return manquants


def graver(conn):
    """À l'ouverture de la mémoire : la table, la gravure (une seule fois, jamais refaite) et ses déclencheurs."""
    conn.execute("CREATE TABLE IF NOT EXISTS fitra (id INTEGER PRIMARY KEY CHECK (id = 1), texte TEXT NOT NULL, "
                 "empreinte TEXT NOT NULL, gravee_ts REAL NOT NULL)")
    if conn.execute("SELECT COUNT(*) FROM fitra").fetchone()[0] == 0:
        conn.execute("INSERT INTO fitra (id, texte, empreinte, gravee_ts) VALUES (1, ?, ?, ?)",
                     (TEXTE, _empreinte(TEXTE), time.time()))
    _declencheurs(conn)
    conn.commit()


def _ligne(conn):
    try:
        return conn.execute("SELECT texte, empreinte FROM fitra WHERE id = 1").fetchone()
    except sqlite3.DatabaseError:
        return None


def texte(conn=None):
    """Ce qui est dit à Hakim : la gravure, si elle est intacte ; sinon le texte du code."""
    conn, propre = _connexion(conn)
    try:
        r = _ligne(conn)
        return r[0] if r and _empreinte(r[0]) == r[1] else TEXTE
    finally:
        if propre:
            conn.close()


def verifier(conn=None):
    """{ok, alerte} : la gravure là, intacte, protégée, et le code d'accord avec elle. Rétablit ce qui peut l'être."""
    conn, propre = _connexion(conn)
    alertes = []
    try:
        if not _table(conn):
            graver(conn)
            alertes.append("La fitra avait disparu de la mémoire de Hakim : regravée.")
        manquants = _declencheurs(conn)
        if manquants:
            alertes.append(f"Les protections de la fitra avaient été retirées ({', '.join(manquants)}) : rétablies.")
        r = _ligne(conn)
        if r is None or _empreinte(r[0]) != r[1]:
            if _empreinte(TEXTE) == EMPREINTE:             # le code est intact : il rétablit la gravure
                for n in _DECLENCHEURS:
                    conn.execute(f"DROP TRIGGER IF EXISTS {n}")
                conn.execute("DELETE FROM fitra")
                conn.execute("INSERT INTO fitra (id, texte, empreinte, gravee_ts) VALUES (1, ?, ?, ?)",
                             (TEXTE, _empreinte(TEXTE), time.time()))
                _declencheurs(conn)
                alertes.append("La gravure de la fitra avait été altérée : rétablie depuis le code.")
            else:
                alertes.append("La gravure de la fitra ET son code ont été altérés : à voir avec maman.")
        elif r[0] != TEXTE:
            alertes.append("Le code de la fitra ne correspond plus à sa gravure : c'est la gravure qui fait foi. À voir avec maman.")
        conn.commit()
    finally:
        if propre:
            conn.close()
    return {"ok": not alertes, "alerte": " ".join(alertes)}


if __name__ == "__main__":
    if sys.argv[1:] == ["texte"]:
        print(texte())
    elif sys.argv[1:] == ["verifier"]:
        print(json.dumps(verifier(), ensure_ascii=False))
    elif sys.argv[1:] == ["graver"]:                       # la première gravure (jamais refaite ensuite)
        c, _ = _connexion(None)
        try:
            graver(c)
        finally:
            c.close()
        print(json.dumps(verifier(), ensure_ascii=False))
    else:
        print("usage : fitra.py texte | verifier | graver", file=sys.stderr)
        sys.exit(2)
