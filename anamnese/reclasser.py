"""Applique un reclassement de souvenirs décidé hors de la base (2026-10-21, demande d'Ahmed : « reclasser ce qu'il
faut au bon endroit ») : des fichiers JSONL {"id", "rubrique", "confiance"} (une décision par souvenir, prise en
lisant le souvenir — ici par des agents Claude, sur les souvenirs rangés avec une confiance faible ou pas du tout).

- Seuls les ids proposés au classement (liste des candidats) sont touchés ; « archives » jamais.
- Une rubrique doit exister, ou faire partie des NOUVELLES permises (créées au passage) ; sinon la décision est écartée.
- « aucune » avec une confiance suffisante : le souvenir quitte sa rubrique douteuse (orphelin ; le rappel le trouve).
- Sous MIN_CONFIANCE, rien ne bouge.
- Confiance gardée = celle du classement (plafonnée à 0,95 : une décision automatique n'est pas un choix d'Ahmed).
Simulation par défaut ; --oui applique après une sauvegarde de la base et garde la liste pour défaire (--defaire).
Usage : .venv/bin/python reclasser.py <candidats.jsonl…> -- <sorties.jsonl…> [--oui]
"""
import json
import sqlite3
import sys
import time
from pathlib import Path

import config
import rubrics

NOUVELLES = {"vie": "Sa vie", "vie/famille": "Famille et proches", "vie/quotidien": "Le quotidien",
             "vie/lives": "Ses lives et son public", "projets/anamnese/hakim": "Hakim lui-même (voix, cockpit, humeur, capacités)"}
MIN_CONFIANCE = 0.6


def lire(fichiers):
    out = []
    for f in fichiers:
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            if l.strip():
                try:
                    out.append(json.loads(l))
                except ValueError:
                    pass
    return out


def plan(conn, candidats, decisions):
    ids_ok = {int(x["id"]) for x in candidats}
    existants = {r[0] for r in conn.execute("SELECT path FROM rubrics")}
    actuel = {eid: (p, cf) for eid, p, cf in conn.execute(
        "SELECT e.id, r.path, e.rubric_conf FROM episodes e LEFT JOIN rubrics r ON r.id = e.rubric_id")}
    moves, ecartes = [], {"inconnu": 0, "rubrique_invalide": 0, "peu_sur": 0, "deja_la": 0}
    for d in decisions:
        try:
            eid, rub, cf = int(d["id"]), str(d.get("rubrique") or "aucune").strip().strip("/"), float(d.get("confiance") or 0)
        except (KeyError, TypeError, ValueError):
            ecartes["inconnu"] += 1
            continue
        if eid not in ids_ok or eid not in actuel:
            ecartes["inconnu"] += 1
            continue
        if cf < MIN_CONFIANCE:
            ecartes["peu_sur"] += 1
            continue
        if rub == "aucune":
            rub = None
        elif rub.startswith("archives") or (rub not in existants and rub not in NOUVELLES):
            ecartes["rubrique_invalide"] += 1
            continue
        if actuel[eid][0] == rub:
            ecartes["deja_la"] += 1
            continue
        moves.append((eid, rub, round(min(0.95, cf), 3), actuel[eid][0], actuel[eid][1]))
    return moves, ecartes


def appliquer(conn, moves):
    now = time.time()
    for path, label in sorted(NOUVELLES.items()):
        if any(m[1] == path or (m[1] or "").startswith(path + "/") for m in moves):
            rubrics.rubric_create(conn, path, now=now, label=label)
    for eid, rub, cf, _avant, _cfa in moves:
        if rub:
            rubrics._attach_core(conn, eid, rub, cf, now)
        else:
            r = conn.execute("SELECT rubric_id, embedding FROM episodes WHERE id=?", (eid,)).fetchone()
            if r and r[0] is not None:
                rubrics._detach_from(conn, r[0], rubrics._parse_embedding(r[1]))
            conn.execute("UPDATE episodes SET rubric_id=NULL, rubric_conf=NULL, routed_ts=NULL WHERE id=?", (eid,))
    conn.commit()


def defaire(liste, db_path=None):
    d = json.loads(Path(liste).read_text(encoding="utf-8"))
    conn = sqlite3.connect(str(db_path or config.DB_PATH), timeout=30)
    try:
        now = time.time()
        for x in d["deplaces"]:
            if x["avant"]:
                rubrics._attach_core(conn, int(x["id"]), x["avant"], x.get("conf_avant") or 0.5, now)
            else:
                r = conn.execute("SELECT rubric_id, embedding FROM episodes WHERE id=?", (int(x["id"]),)).fetchone()
                if r and r[0] is not None:
                    rubrics._detach_from(conn, r[0], rubrics._parse_embedding(r[1]))
                conn.execute("UPDATE episodes SET rubric_id=NULL, rubric_conf=NULL, routed_ts=NULL WHERE id=?", (int(x["id"]),))
        conn.commit()
    finally:
        conn.close()
    return len(d["deplaces"])


def main(argv):
    if "--defaire" in argv:
        print(defaire(argv[argv.index("--defaire") + 1]), "souvenir(s) remis à leur place d'avant")
        return
    oui = "--oui" in argv
    argv = [a for a in argv if a != "--oui"]
    sep = argv.index("--")
    candidats, decisions = lire(argv[:sep]), lire(argv[sep + 1:])
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    try:
        moves, ecartes = plan(conn, candidats, decisions)
        vers = {}
        for m in moves:
            vers[m[1] or "(sans rubrique)"] = vers.get(m[1] or "(sans rubrique)", 0) + 1
        print(f"{len(candidats)} candidats, {len(decisions)} décisions ; {len(moves)} déplacement(s) ; écartés : {ecartes}")
        for p, n in sorted(vers.items(), key=lambda x: -x[1])[:25]:
            print(f"  {n:5d}  {p}")
        if not oui:
            print("Simulation : rien n'a été écrit. --oui pour appliquer.")
            return
        sauvegarde = Path.home() / "anamnese-backups" / f"avant-reclassement-{time.strftime('%Y%m%d-%H%M%S')}.db"
        sauvegarde.parent.mkdir(parents=True, exist_ok=True)
        dest = sqlite3.connect(str(sauvegarde))
        conn.backup(dest)
        dest.close()
        appliquer(conn, moves)
        liste = config.DATA_DIR / f"reclassement-{time.strftime('%Y%m%d-%H%M%S')}.json"
        liste.write_text(json.dumps({"ts": time.time(), "sauvegarde": str(sauvegarde), "deplaces": [
            {"id": e, "vers": r, "conf": c, "avant": a, "conf_avant": ca} for e, r, c, a, ca in moves]}, ensure_ascii=False),
            encoding="utf-8")
        print(f"{len(moves)} souvenir(s) reclassés ; sauvegarde : {sauvegarde} ; liste pour défaire : {liste}")
    finally:
        conn.close()


if __name__ == "__main__":
    main(sys.argv[1:])
