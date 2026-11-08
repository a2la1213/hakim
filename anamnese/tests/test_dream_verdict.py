"""Les portes du verdict — PRÉ-ENREGISTRÉES (spec), appliquées mécaniquement."""
import dream_metrics

CORR_NULL = {"dopamine": {"r": 0.1, "p": 0.8, "p_bonferroni": 1.0, "n": 25}}
CORR_HIT = {"dopamine": {"r": 0.7, "p": 0.001, "p_bonferroni": 0.009, "n": 25}}


def test_insuffisant_sous_20_nuits():
    label, _ = dream_metrics.verdict(19, 0.9, 0.5, 0.1, CORR_HIT)
    assert label == "INSUFFISANT"          # refus de conclure, même si tout brille


def test_refute_si_divergence_sous_plancher():
    label, _ = dream_metrics.verdict(25, 0.6, 0.08, 0.1, CORR_NULL)
    assert label == "RÉFUTÉ"               # réel ≈ jumeau : c'était le prior


def test_bruit_si_pas_de_tendance():
    label, _ = dream_metrics.verdict(25, 0.05, 0.5, 0.1, CORR_NULL)
    assert label == "BRUIT"


def test_insuffisant_si_stabilite_inmesurable():
    """n_stab=0 : r=0.0 ne mesure RIEN (aucune paire comparable) — INSUFFISANT,
    pas BRUIT (« pas de tendance » serait une conclusion sans mesure)."""
    label, raisons = dream_metrics.verdict(25, 0.0, 0.5, 0.1, CORR_NULL, n_stab=0)
    assert label == "INSUFFISANT"
    assert any("inmesurable" in r for r in raisons)
    # RÉFUTÉ garde la priorité : divergence ≤ plancher reste une réfutation nette
    label2, _ = dream_metrics.verdict(25, 0.0, 0.08, 0.1, CORR_NULL, n_stab=0)
    assert label2 == "RÉFUTÉ"


def test_plausible_un_critere_sur_deux():
    label, _ = dream_metrics.verdict(25, 0.6, 0.15, 0.1, CORR_NULL)   # stable, div < 2×
    assert label == "PLAUSIBLE"
    label2, _ = dream_metrics.verdict(25, 0.3, 0.5, 0.1, CORR_NULL)   # div > 2×, pas stable
    assert label2 == "PLAUSIBLE"


def test_prouve_les_trois_criteres():
    label, raisons = dream_metrics.verdict(25, 0.6, 0.5, 0.1, CORR_HIT)
    assert label == "PROUVÉ"
    assert any("Bonferroni" in r or "dopamine" in r for r in raisons)


def test_report_sur_db_vide(tmp_path):
    import sqlite3
    import migrations
    conn = sqlite3.connect(tmp_path / "t.db")
    migrations.migrate(conn)
    out = dream_metrics.report(conn)
    assert "INSUFFISANT" in out and "0" in out       # honnête dès la nuit zéro
    conn.close()


def test_memory_drift(tmp_path):
    """Métrique 4 (boucle causale) : la mémoire RÉCENTE colle-t-elle mieux à la
    préférence que l'ancienne ? Épisodes forgés : anciens 'musique', récents 'btp',
    préférence 'btp' → drift > 0 (la mémoire dérive VERS les goûts du rêveur)."""
    import time as _t
    import memory
    import migrations
    # migrations.migrate ne crée PAS `episodes` (schéma de base = memory.Memory,
    # même pattern que tests/test_facets.py) — d'où Memory + migrate ici.
    m = memory.Memory(db_path=tmp_path / "t.db")
    conn = m.db
    migrations.migrate(conn)
    now = _t.time()

    def _ep(content, age_d):
        cur = conn.execute(
            "INSERT INTO episodes (ts, role, content, importance, embedding) "
            "VALUES (?,?,?,?,?)", (now - age_d * 86400, "semantic", content, 0.5, "[]"))
        return cur.lastrowid

    import facets_extract
    for i in range(5):
        eid = _ep(f"session musique guitare numéro {i}", age_d=35 + i)
        facets_extract.tag_episode(conn, eid, facets_extract.extract_facets("musique guitare"))
    for i in range(5):
        eid = _ep(f"chantier btp fondation numéro {i}", age_d=1 + i)
        facets_extract.tag_episode(conn, eid, facets_extract.extract_facets("chantier btp"))
    conn.commit()
    drift = dream_metrics.memory_drift(conn, {"btp": 2.0, "chantier": 1.5}, now=now)
    assert drift is not None and drift > 0
    assert dream_metrics.memory_drift(conn, {}, now=now) is None    # pas de préférence → None
    conn.close()
