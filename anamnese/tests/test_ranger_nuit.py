"""Le rangement de nuit (ranger_nuit.py, 2026-10-21) : les souvenirs mal rangés des derniers jours, lus et rangés."""
import json
import time

import memory
import migrations
import ranger_nuit
import rubrics


def test_rangement_de_nuit(tmp_path, monkeypatch):
    import config
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    for p in ("projets", "projets/proxipro", "profil"):
        rubrics.rubric_create(m.db, p, now=0)
    a = m.add("episodic", "[Échange avec Ahmed] la base de proxipro", dedup=False)
    b = m.add("episodic", "[Échange avec Ahmed] salut", dedup=False)
    vieux = m.add("episodic", "très ancien", dedup=False)
    m.db.execute("UPDATE episodes SET ts=? WHERE id=?", (time.time() - 30 * 86400, vieux))
    m.db.commit()
    vus = {}
    def lancer(prompt):
        vus["prompt"] = prompt
        return "\n".join([json.dumps({"id": a, "rubrique": "projets/proxipro", "confiance": 0.9}),
                          json.dumps({"id": b, "rubrique": "aucune", "confiance": 0.9})])
    m.db.close()
    r = ranger_nuit.main(appliquer=True, db_path=tmp_path / "m.db", lancer=lancer)
    assert r["ranges"] == 1 and "très ancien" not in vus["prompt"] and "jamais « archives »" in vus["prompt"]
    m2 = memory.Memory(db_path=tmp_path / "m.db")
    assert m2.db.execute("SELECT r.path FROM episodes e JOIN rubrics r ON r.id=e.rubric_id WHERE e.id=?", (a,)).fetchone()[0] == "projets/proxipro"
