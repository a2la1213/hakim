"""Re-range les souvenirs rangés AUTOMATIQUEMENT avec le routeur actuel (routing.decider).

Simulation par défaut. --appliquer : sauvegarde de la base, puis toutes les décisions (prises
sur la même photo des centroïdes) appliquées en une seule transaction. Les rangements manuels
(rubric_conf == 1.0) ne sont jamais touchés ; un épisode qui ne change pas n'est pas réécrit ;
une décision « aucune rubrique » ne détache rien. Seuls les rôles humains (routing.ROLES_HUMAINS),
mesurés par eval/route_bench.py, sont re-rangés : rejouer les insights du démon sur des
centroïdes qui ont changé depuis leur rangement serait du bruit non mesuré.

Usage : .venv/bin/python -m scripts.rerouter [--appliquer]
"""
import argparse
import collections
import datetime
import pathlib
import sqlite3
import time

import config
import routing
import rubrics


def planifier(conn, roles=None):
    roles = tuple(roles or routing.ROLES_HUMAINS)
    rub = dict(conn.execute("SELECT id, path FROM rubrics"))
    paths, rubs = list(rub.values()), routing._rubriques(conn)
    plan = []
    for eid, role, content, emb, rid in conn.execute(
            "SELECT id, role, content, embedding, rubric_id FROM episodes WHERE rubric_id IS NOT NULL "
            "AND (rubric_conf IS NULL OR rubric_conf < 0.999) "
            f"AND role IN ({','.join('?' * len(roles))}) ORDER BY id", roles).fetchall():
        vers, conf = routing.decider(role, content, rubrics._parse_embedding(emb), paths, rubs)
        if vers and vers != rub.get(rid):
            plan.append({"id": eid, "role": role, "de": rub.get(rid), "vers": vers, "conf": conf})
    return plan


def appliquer(conn, plan, now=None):
    now = time.time() if now is None else now
    if conn.in_transaction:
        conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        for m in plan:
            rubrics._attach_core(conn, m["id"], m["vers"], m["conf"], now)
    except BaseException:
        conn.rollback()
        raise
    conn.commit()
    return len(plan)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--appliquer", action="store_true", help="écrire (après sauvegarde)")
    args = ap.parse_args()
    conn = sqlite3.connect(str(config.DB_PATH), timeout=30)
    plan = planifier(conn)
    print(f"{len(plan)} souvenir(s) changeraient de rubrique")
    print("par rôle :", dict(collections.Counter(m["role"] for m in plan).most_common()))
    print("transitions les plus fréquentes :")
    for (de, vers), n in collections.Counter((m["de"], m["vers"]) for m in plan).most_common(12):
        print(f"  {n:4}  {de} → {vers}")
    if args.appliquer and plan:
        dest = pathlib.Path(config.DB_PATH).parent / "backups" / \
            f"manuel-avant-rerouteur-{datetime.datetime.now():%Y%m%d-%H%M%S}.db"
        dest.parent.mkdir(parents=True, exist_ok=True)
        cible = sqlite3.connect(str(dest))
        conn.backup(cible)
        cible.close()
        print(f"sauvegarde : {dest}")
        print(f"appliqué : {appliquer(conn, plan)} souvenir(s) re-rangé(s)")
    conn.close()


if __name__ == "__main__":
    main()
