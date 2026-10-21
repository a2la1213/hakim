"""scripts/rerouter.py (2026-10-15) : re-ranger les souvenirs rangés AUTOMATIQUEMENT.

- simulation par défaut : rien n'est écrit ;
- les rangements manuels (rubric_conf == 1.0) ne sont jamais touchés ;
- toutes les décisions sont prises sur la même photo des centroïdes, puis appliquées en une
  transaction (l'ordre de traitement ne change rien) ;
- un épisode dont la rubrique ne change pas n'est pas réécrit.

Prédiction écrite avant le code : tout échoue (module absent).
"""

import json

import memory
import migrations
import rubrics
from scripts import rerouter


def _mem(tmp_path):
    mem = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    for p in ("projets/anamnese", "projets/robot-ia"):
        if rubrics.get_rubric_id(mem.db, p) is None:
            rubrics.rubric_create(mem.db, p, now=1000.0)
    return mem


def _episode(mem, contenu, path, conf):
    eid = mem.db.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                         "VALUES (2000, 'semantic', ?, 0.5, ?)", (contenu, json.dumps([0.1] * 8))).lastrowid
    rubrics.attach_episode(mem.db, eid, path, conf, 2000.0)
    return eid


def test_simulation_puis_application(tmp_path):
    mem = _mem(tmp_path)
    mal = _episode(mem, "[Anamnèse] la nuit tourne", "projets/robot-ia", 0.8)
    manuel = _episode(mem, "[Anamnèse] rangé à la main ailleurs", "projets/robot-ia", 1.0)
    bon = _episode(mem, "[robot-ia] déjà au bon endroit", "projets/robot-ia", 0.8)
    plan = rerouter.planifier(mem.db)
    assert [(m["id"], m["vers"]) for m in plan] == [(mal, "projets/anamnese")]
    path_de = lambda eid: mem.db.execute("SELECT r.path FROM episodes e JOIN rubrics r ON r.id=e.rubric_id "
                                         "WHERE e.id=?", (eid,)).fetchone()[0]
    assert path_de(mal) == "projets/robot-ia"                  # simulation : rien d'écrit
    assert rerouter.appliquer(mem.db, plan, now=3000.0) == 1
    assert path_de(mal) == "projets/anamnese"
    assert path_de(manuel) == "projets/robot-ia"               # manuel jamais touché
    routed = mem.db.execute("SELECT routed_ts FROM episodes WHERE id=?", (bon,)).fetchone()[0]
    assert routed == 2000.0                                    # inchangé : pas réécrit
    mem.db.close()


def test_insights_du_demon_jamais_re_ranges(tmp_path):
    mem = _mem(tmp_path)
    eid = mem.db.execute("INSERT INTO episodes (ts, role, content, importance, embedding) "
                         "VALUES (2000, 'insight', '[Anamnèse] motif', 0.5, ?)", (json.dumps([0.1] * 8),)).lastrowid
    rubrics.attach_episode(mem.db, eid, "projets/robot-ia", 0.8, 2000.0)
    assert all(m["id"] != eid for m in rerouter.planifier(mem.db))
    mem.db.close()
