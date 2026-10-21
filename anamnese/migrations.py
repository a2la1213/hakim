"""Migrations additives Anamnèse 2.0 (Phase 0) — schéma prêt SANS changer le comportement.

`migrate(conn)` prend une connexion sqlite3 DÉJÀ OUVERTE (jamais un chemin) :
- ajoute 8 colonnes NULLABLE à `episodes` (idempotent via PRAGMA table_info,
  SQLite n'ayant pas ADD COLUMN IF NOT EXISTS) ;
- ajoute `centroid_n` à `rubrics` si la table préexiste sans elle (DB migrées
  avec la Phase 1A d'origine) — même mécanisme PRAGMA que pour episodes ;
- crée 8 nouvelles tables + 6 index (`IF NOT EXISTS`) ;
- retourne un résumé de ce qui a RÉELLEMENT été ajouté cet appel
  (listes vides au 2e appel = idempotence).

Décision v2 : PAS de table `rubric_closure` (YAGNI — la hiérarchie passera
par `rubrics.path` + `LIKE` en Phase 1). Les nouvelles tables restent inertes
tant que les phases suivantes ne les remplissent pas : aucune écriture/lecture
existante (`Memory.add`/`Memory.retrieve`) ne change.
"""

# Colonnes à ajouter à `episodes` : [(nom, déclaration SQL), ...]
EPISODE_COLUMNS = [
    ("rubric_id", "INTEGER"),
    ("rubric_conf", "REAL"),
    ("routed_ts", "REAL"),
    ("session_id", "INTEGER"),
    ("enc_valence", "REAL"),
    ("enc_arousal", "REAL"),
    ("last_recall_ts", "REAL"),
    ("recall_count", "INTEGER DEFAULT 0"),
    ("provenance", "TEXT"),             # 'externe' : contenu de tiers ou dérivé d'un tel contenu (provenance.py)
    ("enc_affect", "TEXT"),             # la trace émotionnelle d'encodage (affect.trace, 2026-10-21)
]

# Colonnes à ajouter à `rubrics` si la table préexiste sans elles (rattrapage
# des DB migrées avant l'ajout de centroid_n) : [(nom, déclaration SQL), ...]
RUBRIC_COLUMNS = [
    ("centroid_n", "INTEGER DEFAULT 0"),
]

# Nouvelles tables : [(nom, DDL), ...]
NEW_TABLES_SQL = [
    (
        "rubrics",
        """
        CREATE TABLE IF NOT EXISTS rubrics (
            id           INTEGER PRIMARY KEY,
            path         TEXT UNIQUE NOT NULL,
            label        TEXT,
            parent_id    INTEGER REFERENCES rubrics(id),
            kind_hint    TEXT,
            centroid     TEXT,
            centroid_n   INTEGER DEFAULT 0,
            depth        INTEGER DEFAULT 0,
            memory_count INTEGER DEFAULT 0,
            created_ts   REAL
        )
        """,
    ),
    (
        "facets",
        """
        CREATE TABLE IF NOT EXISTS facets (
            id   INTEGER PRIMARY KEY,
            slug TEXT UNIQUE NOT NULL
        )
        """,
    ),
    (
        "episode_facets",
        """
        CREATE TABLE IF NOT EXISTS episode_facets (
            episode_id INTEGER NOT NULL,
            facet_id   INTEGER NOT NULL,
            weight     REAL DEFAULT 1.0,
            PRIMARY KEY (episode_id, facet_id)
        )
        """,
    ),
    (
        "sessions",
        """
        CREATE TABLE IF NOT EXISTS sessions (
            id           INTEGER PRIMARY KEY,
            started_ts   REAL NOT NULL,
            ended_ts     REAL,
            summary      TEXT,
            rubric_focus INTEGER,
            gap_before_h REAL
        )
        """,
    ),
    (
        "landmarks",
        """
        CREATE TABLE IF NOT EXISTS landmarks (
            id       INTEGER PRIMARY KEY,
            ts       REAL NOT NULL,
            label    TEXT NOT NULL,
            kind     TEXT,
            salience REAL DEFAULT 0.5
        )
        """,
    ),
    (
        # Voies de co-activation (Cerveau 3D P1) : arêtes NON orientées entre
        # épisodes co-remontés (même rappel) ou co-consolidés (même rêve),
        # stockées en ordre canonique a_id < b_id. weight = consolidation de
        # la voie (LTP borné + élagage), future épaisseur d'arête 3D.
        "coactivation",
        """
        CREATE TABLE IF NOT EXISTS coactivation (
            a_id    INTEGER NOT NULL,
            b_id    INTEGER NOT NULL,
            weight  REAL DEFAULT 0.0,
            last_ts REAL,
            PRIMARY KEY (a_id, b_id)
        )
        """,
    ),
    (
        # Positions 3D des souvenirs (Cerveau 3D P2a) : projection PCA de
        # l'embedding (256→3) sur la basis FIGÉE cachée dans kv['brain_basis'].
        # Table RÉGÉNÉRABLE (brain_projection.backfill_layout) — on n'ajoute
        # pas de colonnes à episodes.
        "brain_layout",
        """
        CREATE TABLE IF NOT EXISTS brain_layout (
            episode_id INTEGER PRIMARY KEY,
            x REAL, y REAL, z REAL,
            ts REAL
        )
        """,
    ),
    (
        "dream_log",
        """
        CREATE TABLE IF NOT EXISTS dream_log (
            id         INTEGER PRIMARY KEY,
            ts         REAL NOT NULL,
            night_id   TEXT NOT NULL,
            dreamer    TEXT NOT NULL,
            seed_state TEXT,
            menu       TEXT,
            chosen     TEXT,
            content    TEXT,
            facets     TEXT,
            written    INTEGER DEFAULT 0,
            meta       TEXT
        )
        """,
    ),
    (
        # Liens GÉNÉRATIFS (synthèse abductive) : arête TYPÉE d'un insight vers
        # chaque souvenir source qui l'a enfanté. Couche distincte de coactivation
        # (associatif) — ici l'arête SIGNIFIE « cet insight est né de ces mémoires ».
        "insight_edges",
        """
        CREATE TABLE IF NOT EXISTS insight_edges (
            insight_id INTEGER NOT NULL,
            source_id  INTEGER NOT NULL,
            PRIMARY KEY (insight_id, source_id)
        )
        """,
    ),
]

# Index : [(table cible, DDL), ...] — ceux sur `episodes` sont sautés
# proprement si la table n'existe pas (migrate ne crée PAS episodes).
INDEXES_SQL = [
    (
        "episodes",
        "CREATE INDEX IF NOT EXISTS idx_episodes_rubric ON episodes(rubric_id)",
    ),
    (
        "episodes",
        "CREATE INDEX IF NOT EXISTS idx_episodes_session ON episodes(session_id)",
    ),
    (
        "episode_facets",
        "CREATE INDEX IF NOT EXISTS idx_epfacet_facet ON episode_facets(facet_id)",
    ),
    (
        "coactivation",
        "CREATE INDEX IF NOT EXISTS idx_coact_b ON coactivation(b_id)",
    ),
    ("dream_log", "CREATE INDEX IF NOT EXISTS idx_dreamlog_night ON dream_log(night_id)"),
    ("dream_log", "CREATE INDEX IF NOT EXISTS idx_dreamlog_dreamer ON dream_log(dreamer)"),
    ("insight_edges", "CREATE INDEX IF NOT EXISTS idx_insight_src ON insight_edges(source_id)"),
]


def _table_exists(conn, name):
    return (
        conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
        ).fetchone()
        is not None
    )


def migrate(conn):
    """Applique le schéma 2.0 additif sur `conn`. Idempotent, commit inclus.

    Retourne {"columns_added": [...], "tables_created": [...]} : uniquement
    ce qui a réellement été ajouté par CET appel.
    """
    columns_added = []
    tables_created = []

    # 1. Colonnes NULLABLE sur episodes (sautées si la table n'existe pas)
    if _table_exists(conn, "episodes"):
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(episodes)").fetchall()
        }
        for name, decl in EPISODE_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE episodes ADD COLUMN {name} {decl}")
                columns_added.append(name)

    # 1b. Colonnes sur rubrics si la table préexiste sans elles (DB migrées
    # avant centroid_n) ; une table créée à l'étape 2 les a déjà via le DDL.
    if _table_exists(conn, "rubrics"):
        existing = {
            row[1] for row in conn.execute("PRAGMA table_info(rubrics)").fetchall()
        }
        for name, decl in RUBRIC_COLUMNS:
            if name not in existing:
                conn.execute(f"ALTER TABLE rubrics ADD COLUMN {name} {decl}")
                columns_added.append(name)

    # 2. Nouvelles tables (inertes tant que les phases suivantes n'écrivent pas)
    for name, ddl in NEW_TABLES_SQL:
        if not _table_exists(conn, name):
            conn.execute(ddl)
            tables_created.append(name)

    # 3. Index (seulement si la table cible existe)
    for table, ddl in INDEXES_SQL:
        if _table_exists(conn, table):
            conn.execute(ddl)

    conn.commit()
    return {"columns_added": columns_added, "tables_created": tables_created}
