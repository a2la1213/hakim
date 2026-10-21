"""Sources du banc de continuité : souvenirs humains (semantic, reasoning) rangés sous projets/,
d'au moins LONGUEUR_MIN caractères, au plus `par_projet` par PROJET (projets/X), tirage
déterministe.

v2 (relecture 2026-10-15) : plus d'exigence de rangement manuel (rubric_conf = 1,0) — ce
vivier était à 90 % des rapports de sous-agents — et plafond par projet plutôt que par
sous-rubrique (synod-it pesait 20 % des questions pour 7,8 % des souvenirs)."""
import random
import sqlite3
from pathlib import Path

ROLES = ("semantic", "reasoning")
LONGUEUR_MIN = 200


def sources(db_path, n=60, par_projet=2, graine=2026):
    conn = sqlite3.connect(f"file:{Path(db_path)}?mode=ro", uri=True)
    try:
        rows = conn.execute(
            "SELECT e.id, e.ts, e.role, e.content, r.path FROM episodes e JOIN rubrics r ON r.id = e.rubric_id "
            "WHERE e.role IN (?, ?) AND r.path LIKE 'projets/%' AND length(e.content) >= ? ORDER BY e.id",
            (*ROLES, LONGUEUR_MIN)).fetchall()
    finally:
        conn.close()
    rng = random.Random(graine)
    par = {}
    for row in rows:
        par.setdefault("/".join(row[4].split("/")[:2]), []).append(row)
    choix = []
    for projet in sorted(par):
        lot = list(par[projet])
        rng.shuffle(lot)
        choix += lot[:par_projet]
    rng.shuffle(choix)
    return [{"id": i, "ts": ts, "role": role, "content": c, "rubrique": p} for i, ts, role, c, p in choix[:n]]
