import json
import dream_ablation as A

def _mk(conn):
    conn.execute("CREATE TABLE dream_log (id INTEGER PRIMARY KEY AUTOINCREMENT, night_id TEXT, "
                 "dreamer TEXT, menu TEXT, content TEXT, meta TEXT)")

def test_load_cells_excludes_consolidation_ideas(tmp_db):
    _mk(tmp_db)
    # idée libre de consolidation (source=consolidate) : NE doit PAS devenir une cellule sonnet
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,menu,content,meta) VALUES "
                   "('2026-07-10','sonnet',NULL,'(rêve) idée libre',?)",
                   (json.dumps({"source": "consolidate", "model": "sonnet"}),))
    # rêve-REM sonnet contrôlé (condition explicite) : DOIT être une cellule
    tmp_db.execute("INSERT INTO dream_log (night_id,dreamer,menu,content,meta) VALUES "
                   "('2026-07-10','sonnet','[]','###REVE### contrôlé',?)",
                   (json.dumps({"condition": "brain_on", "ablation": "real_seeds"}),))
    tmp_db.commit()
    cells = A.load_cells(tmp_db)["cells"]
    assert ("sonnet", "brain_on") in cells
    contents = [c for by in cells[("sonnet", "brain_on")].values() for c in by]
    assert "###REVE### contrôlé" in contents
    assert "(rêve) idée libre" not in contents        # idée de consolidation EXCLUE
