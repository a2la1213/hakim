"""Re-range les souvenirs que le routage AUTOMATIQUE avait mis dans « archives » (2026-10-21) : depuis le 20/10, son
centroïde attirait 84 % des échanges mémorisés, et le rappel (memory_recall) ignore « archives » — Hakim ne retrouvait
plus ses conversations avec Ahmed. Seuls les souvenirs rangés là automatiquement (confiance < 1) bougent ; ceux
qu'Ahmed y a rangés à la main (confiance 1, rangement du 20/10) restent. Chaque souvenir repart par le routage normal
(qui ne propose plus « archives ») ; sous la confiance des échanges (0,55), il reste sans rubrique — le rappel
le trouve quand même. Simulation par défaut ; --oui applique après une sauvegarde de la base, et garde la
liste (data/reroutage-archives-<date>.json) pour défaire : --defaire <liste>.
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import config
import rubrics
import routing


def a_rerouter(conn):
    return conn.execute("""SELECT e.id, e.role, e.content, e.embedding, e.rubric_conf FROM episodes e JOIN rubrics r ON r.id = e.rubric_id
        WHERE (r.path = 'archives' OR r.path LIKE 'archives/%') AND (e.rubric_conf IS NULL OR e.rubric_conf < 0.999)""").fetchall()


def main(appliquer=False, db_path=None):
    db_path = Path(db_path or config.DB_PATH)
    conn = sqlite3.connect(str(db_path), timeout=30)
    try:
        lignes = a_rerouter(conn)
        plan, vers = [], {}
        import echanges
        for eid, role, content, emb, conf in lignes:
            path, nconf = routing.route_episode(conn, {"role": role, "content": content, "embedding": emb})
            if path is not None and (nconf or 0.0) < echanges.ROUTAGE_CONF_MIN:
                path = None                                       # mal reconnu : sans rubrique (pas un nouvel aimant)
            plan.append((eid, path, nconf, conf))
            vers[path or "(sans rubrique)"] = vers.get(path or "(sans rubrique)", 0) + 1
        print(f"{len(plan)} souvenir(s) rangés automatiquement dans « archives » ; destinations :")
        for p, n in sorted(vers.items(), key=lambda x: -x[1])[:15]:
            print(f"  {n:5d}  {p}")
        if not appliquer or not plan:
            print("Simulation : rien n'a été écrit. --oui pour appliquer.")
            return plan
        sauvegarde = Path.home() / "anamnese-backups" / f"avant-reroutage-archives-{time.strftime('%Y%m%d-%H%M%S')}.db"
        sauvegarde.parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(str(sauvegarde))
        conn.backup(dest)
        dest.close()
        now = time.time()
        for eid, path, nconf, _conf in plan:
            if path:
                rubrics._attach_core(conn, eid, path, nconf, now)
            else:
                rid = conn.execute("SELECT rubric_id, embedding FROM episodes WHERE id=?", (eid,)).fetchone()
                if rid and rid[0] is not None:
                    rubrics._detach_from(conn, rid[0], rubrics._parse_embedding(rid[1]))
                conn.execute("UPDATE episodes SET rubric_id=NULL, rubric_conf=NULL, routed_ts=NULL WHERE id=?", (eid,))
        conn.commit()
        liste = config.DATA_DIR / f"reroutage-archives-{time.strftime('%Y%m%d-%H%M%S')}.json"
        liste.write_text(json.dumps({"ts": now, "sauvegarde": str(sauvegarde),
                                     "deplaces": [{"id": e, "vers": p, "conf_avant": c} for e, p, _n, c in plan]},
                                    ensure_ascii=False), encoding="utf-8")
        print(f"{len(plan)} souvenir(s) re-rangés ; sauvegarde : {sauvegarde} ; liste : {liste}")
        return plan
    finally:
        conn.close()


def defaire(liste, db_path=None):
    d = json.loads(Path(liste).read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db_path or config.DB_PATH), timeout=30)
    try:
        now = time.time()
        for x in d["deplaces"]:
            rubrics._attach_core(conn, int(x["id"]), "archives", x.get("conf_avant") or 0.5, now)
        conn.commit()
    finally:
        conn.close()
    return len(d["deplaces"])


if __name__ == "__main__":
    if "--defaire" in sys.argv[1:]:
        print(defaire(sys.argv[sys.argv.index("--defaire") + 1]), "souvenir(s) remis dans archives")
    else:
        main(appliquer="--oui" in sys.argv[1:])
