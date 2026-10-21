# tests/test_insight_migration.py
import migrations

def test_migrate_creates_insight_edges(tmp_db):
    migrations.migrate(tmp_db)
    cols = [r[1] for r in tmp_db.execute("PRAGMA table_info(insight_edges)")]
    assert cols == ["insight_id", "source_id"]
    # idempotent : re-migrer ne casse pas
    migrations.migrate(tmp_db)
    idx = [r[0] for r in tmp_db.execute(
        "SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='insight_edges'")]
    assert any("idx_insight_src" in n for n in idx)

def test_insight_edges_pk_dedup(tmp_db):
    migrations.migrate(tmp_db)
    tmp_db.execute("INSERT INTO insight_edges VALUES (1, 2)")
    tmp_db.execute("INSERT OR IGNORE INTO insight_edges VALUES (1, 2)")  # doublon ignoré (PK)
    tmp_db.commit()
    assert tmp_db.execute("SELECT COUNT(*) FROM insight_edges").fetchone()[0] == 1
