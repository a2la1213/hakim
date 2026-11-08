"""Fausse alerte « backup vieux de 58j » (constatée le 2026-10-15).

Le démon fait une sauvegarde quotidienne data/backups/auto-AAAA-MM-JJ.db, mais health ne
regardait que BACKUP_DIR (~/anamnese-backups) et que les noms memory-*.db. Désormais :
noms auto-* reconnus, et par défaut les DEUX dossiers sont regardés.

Prédiction écrite avant le correctif : les deux tests échouent (warning « vieux de 58j »).
"""

import pathlib

import config
import health
from tests.test_health import NOW, _kv_db, _mk_backup, daemon_up  # noqa: F401 (fixture)


def _sans_alerte_backup(rep):
    return not any("backup" in w.lower() for w in rep["warnings"])


def test_backup_auto_du_demon_reconnu(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 6 * 3600)})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "auto-2027-01-14.db", age_h=20)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert _sans_alerte_backup(rep), rep["warnings"]


def test_par_defaut_les_deux_dossiers(tmp_path, daemon_up, monkeypatch):
    manuels = tmp_path / "anamnese-backups"
    _mk_backup(manuels, "memory-20260818-220056.db", age_h=58 * 24)    # vieux, manuel
    data = tmp_path / "data"
    _mk_backup(data / "backups", "auto-2027-01-15.db", age_h=5)          # frais, démon
    monkeypatch.setattr(config, "BACKUP_DIR", manuels)
    monkeypatch.setattr(config, "DB_PATH", data / "memory.db")
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 6 * 3600)})
    rep = health.health_report(conn, now=NOW)
    assert _sans_alerte_backup(rep), rep["warnings"]
    assert pathlib.Path(rep["last_backup_path"]).name == "auto-2027-01-15.db"


def test_nuit_sautee_n_est_pas_une_panne(tmp_path, daemon_up):
    """Constat 10 : la porte écrit last_consolidation_skip ; health le prend comme signe de vie."""
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 72 * 3600),
                             "last_consolidation_skip": str(NOW - 5 * 3600)})
    _mk_backup(tmp_path / "bk", "auto-2027-01-14.db", age_h=5)
    rep = health.health_report(conn, now=NOW, backup_dir=tmp_path / "bk")
    assert not any("consolidation" in w for w in rep["warnings"]), rep["warnings"]
