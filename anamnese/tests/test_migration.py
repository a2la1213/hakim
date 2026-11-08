"""Tests de migrations.migrate — schéma 2.0 additif, idempotent, rétro-compatible."""

import migrations

# Types attendus des 8 nouvelles colonnes d'episodes (nom -> type déclaré).
EXPECTED_COLUMN_TYPES = {
    "rubric_id": "INTEGER",
    "rubric_conf": "REAL",
    "routed_ts": "REAL",
    "session_id": "INTEGER",
    "enc_valence": "REAL",
    "enc_arousal": "REAL",
    "last_recall_ts": "REAL",
    "recall_count": "INTEGER",
}

NEW_TABLES = {"rubrics", "facets", "episode_facets", "sessions", "landmarks",
              "coactivation", "brain_layout", "dream_log", "insight_edges"}

NEW_INDEXES = {"idx_episodes_rubric", "idx_episodes_session", "idx_epfacet_facet",
               "idx_coact_b", "idx_insight_src"}


def _table_names(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    }


def _index_names(conn):
    return {
        row[0]
        for row in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")
    }


# --- Cas 1 : les 8 colonnes sont ajoutées à episodes, types + défauts corrects ---
def test_migrate_adds_eight_columns_to_episodes(legacy_db):
    result = migrations.migrate(legacy_db)

    info = {row[1]: row for row in legacy_db.execute("PRAGMA table_info(episodes)")}
    for name, expected_type in EXPECTED_COLUMN_TYPES.items():
        assert name in info, f"colonne manquante : {name}"
        assert info[name][2] == expected_type, f"type inattendu pour {name}"
    # recall_count a bien DEFAULT 0
    assert info["recall_count"][4] == "0"
    # le résumé liste exactement ce qui a été ajouté, dans l'ordre du module
    assert result["columns_added"] == [name for name, _ in migrations.EPISODE_COLUMNS]


# --- Cas 2 : les 8 nouvelles tables existent, rubric_closure N'EXISTE PAS ---
def test_migrate_creates_new_tables_and_no_closure(legacy_db):
    result = migrations.migrate(legacy_db)

    tables = _table_names(legacy_db)
    assert NEW_TABLES <= tables
    assert "rubric_closure" not in tables  # coupée YAGNI (décision v2)
    assert set(result["tables_created"]) == NEW_TABLES
    # les 3 index sont créés aussi
    assert NEW_INDEXES <= _index_names(legacy_db)


# --- Cas 3 : idempotence — deux appels, le second ne fait rien ---
def test_migrate_is_idempotent(legacy_db):
    first = migrations.migrate(legacy_db)
    assert first["columns_added"] != []
    assert first["tables_created"] != []

    second = migrations.migrate(legacy_db)  # ne doit lever aucune erreur
    assert second["columns_added"] == []
    assert second["tables_created"] == []


# --- Cas 4 : rétro-compat — données seed intactes, INSERT legacy toujours OK ---
def test_migrate_keeps_legacy_data_and_writes(legacy_db):
    migrations.migrate(legacy_db)

    # les 2 épisodes seed sont toujours lisibles
    count = legacy_db.execute("SELECT COUNT(*) FROM episodes").fetchone()[0]
    assert count == 2

    # un INSERT legacy 5-colonnes fonctionne toujours
    legacy_db.execute(
        "INSERT INTO episodes (ts,role,content,importance,embedding) "
        "VALUES (1002.0,'user','encore',0.6,'[]')"
    )
    legacy_db.commit()

    row = legacy_db.execute(
        "SELECT rubric_id, rubric_conf, routed_ts, session_id, enc_valence, "
        "enc_arousal, last_recall_ts, recall_count "
        "FROM episodes WHERE content='encore'"
    ).fetchone()
    # nouvelles colonnes à NULL, sauf recall_count (DEFAULT 0)
    assert row[:7] == (None, None, None, None, None, None, None)
    assert row[7] == 0

    # les seeds pré-migration ont aussi recall_count=0 (défaut appliqué)
    seeds = legacy_db.execute(
        "SELECT recall_count FROM episodes WHERE content IN ('bonjour','salut')"
    ).fetchall()
    assert [r[0] for r in seeds] == [0, 0]


# --- Cas 5 : DB vide sans episodes — pas de création d'episodes, tables OK ---
def test_migrate_on_empty_db_skips_episodes(tmp_db):
    result = migrations.migrate(tmp_db)

    tables = _table_names(tmp_db)
    assert "episodes" not in tables  # migrate ne crée PAS episodes
    assert NEW_TABLES <= tables
    assert result["columns_added"] == []
    assert set(result["tables_created"]) == NEW_TABLES
