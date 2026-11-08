"""Migration dream_log : créée, idempotente, colonnes exactes. DB temp uniquement."""
import sqlite3

import migrations


def _cols(conn, table):
    return [r[1] for r in conn.execute(f"PRAGMA table_info({table})").fetchall()]


def test_dream_log_created_and_idempotent(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    r1 = migrations.migrate(conn)
    assert "dream_log" in r1["tables_created"]
    assert _cols(conn, "dream_log") == [
        "id", "ts", "night_id", "dreamer", "seed_state", "menu",
        "chosen", "content", "facets", "written", "meta",
    ]
    r2 = migrations.migrate(conn)          # idempotent : rien de nouveau
    assert "dream_log" not in r2["tables_created"]
    conn.close()


def test_dream_config_constants():
    import config
    assert config.DREAM_MENU_SIZE == 12
    assert config.DREAM_MENU_MAX_PER_RUBRIC == 2
    assert config.DREAM_VERDICT_MIN_NIGHTS == 20
    assert isinstance(config.DREAM_LAB_ENABLED, bool)
    assert "dream" not in config.DREAM_MENU_ROLES        # jamais d'écho
    assert "reflection" not in config.DREAM_MENU_ROLES
