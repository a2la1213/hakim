"""Les souvenirs rangés dans « archives » (doublons fusionnés, faits périmés) ne remontent plus d'eux-mêmes
(rangement d'Ahmed du 2026-10-20) ; un rappel restreint à « archives » les retrouve."""
import memory
import migrations
import rubrics


def test_archives_hors_du_rappel_ordinaire(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    rubrics.seed_skeleton(m.db, now=1000.0)
    vieux = m.add("semantic", "Le smartphone d'Ahmed : iPhone ou Android ?", embedding=None)
    m.add("semantic", "Le smartphone d'Ahmed est un Galaxy Z Fold 7.", embedding=None)
    textes = lambda **k: " | ".join(str(r) for r in m.retrieve("smartphone d'Ahmed", None, top_k=5, **k))
    assert "iPhone ou Android" in textes()                         # sans rubrique « archives » : inchangé
    rubrics.rubric_create(m.db, "archives", now=1000.0)
    rubrics.attach_episode(m.db, vieux, "archives", conf=1.0, now=1000.0)
    m.db.commit()
    assert "Fold" in textes() and "iPhone ou Android" not in textes()
    assert "iPhone ou Android" in textes(rubric="archives")
    m.db.close()
