"""reclasser.py (2026-10-21) : un reclassement décidé hors de la base, appliqué prudemment et défaisable."""
import json
import sqlite3

import memory
import migrations
import reclasser
import rubrics


def test_reclasser_puis_defaire(tmp_path, monkeypatch):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    for p in ("projets", "projets/anamnese", "projets/proxipro", "archives"):
        rubrics.rubric_create(m.db, p, now=0)
    a = m.add("episodic", "on parle de la base de proxipro", dedup=False)
    b = m.add("episodic", "l'anniversaire de sa fille", dedup=False)
    c = m.add("episodic", "salut", dedup=False)
    rubrics.attach_episode(m.db, a, "projets/anamnese", 0.5, 0)
    rubrics.attach_episode(m.db, c, "projets/anamnese", 0.5, 0)
    cands = [{"id": a}, {"id": b}, {"id": c}]
    dec = [{"id": a, "rubrique": "projets/proxipro", "confiance": 0.9}, {"id": b, "rubrique": "vie/famille", "confiance": 0.8},
           {"id": c, "rubrique": "aucune", "confiance": 0.9}, {"id": 999, "rubrique": "profil", "confiance": 1},
           {"id": a, "rubrique": "archives", "confiance": 1}, {"id": b, "rubrique": "n-existe/pas", "confiance": 1}]
    moves, ecartes = reclasser.plan(m.db, cands, dec)
    assert {x[0] for x in moves} == {a, b, c} and ecartes["inconnu"] == 1 and ecartes["rubrique_invalide"] == 2
    reclasser.appliquer(m.db, moves)
    path = lambda e: (m.db.execute("SELECT r.path FROM episodes e LEFT JOIN rubrics r ON r.id=e.rubric_id WHERE e.id=?", (e,)).fetchone() or [None])[0]
    assert path(a) == "projets/proxipro" and path(b) == "vie/famille" and path(c) is None
    liste = tmp_path / "l.json"
    liste.write_text(json.dumps({"deplaces": [{"id": e, "vers": r, "conf": cf, "avant": av, "conf_avant": ca} for e, r, cf, av, ca in moves]}))
    m.db.close()
    reclasser.defaire(liste, db_path=tmp_path / "m.db")
    conn = sqlite3.connect(str(tmp_path / "m.db"))
    p2 = lambda e: (conn.execute("SELECT r.path FROM episodes e LEFT JOIN rubrics r ON r.id=e.rubric_id WHERE e.id=?", (e,)).fetchone() or [None])[0]
    assert p2(a) == "projets/anamnese" and p2(b) is None and p2(c) == "projets/anamnese"
