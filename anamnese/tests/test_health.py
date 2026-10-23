"""Tests du watchdog santé (health.py) — kv forgés, JAMAIS data/memory.db.

Tout est synthétique : DB tmp_path, backup_dir tmp_path, _daemon_alive
monkeypatché (launchctl/pgrep ne sont pas déterministes en CI/sandbox).

Point clé (fix du watchdog MAL CÂBLÉ) : le signal PRIMAIRE de consolidation
est kv['last_consolidation'] (vraie consolidation Claude Sonnet, écrite par
consolidate.py). kv['last_dream'] (rêve daemon Ollama) est SECONDAIRE : sa
staleness produit une note ℹ️, jamais le ⚠️ en titre.
"""

import json
import os
import sqlite3
import time

import pytest

import consolidate
import health

NOW = 1_800_000_000.0  # horloge injectée : aucun test ne dépend de l'heure réelle
H = 3600.0


# ---------------------------------------------------------------- helpers ---

def _kv_db(tmp_path, rows=None):
    """DB temp avec une table kv forgée (rows = {key: value})."""
    conn = sqlite3.connect(str(tmp_path / "kv.db"))
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, ts REAL NOT NULL)")
    for key, value in (rows or {}).items():
        conn.execute("INSERT INTO kv (key, value, ts) VALUES (?,?,?)", (key, value, NOW))
    conn.commit()
    return conn


def _mk_backup(dirpath, name, age_h):
    """Fichier backup factice daté (mtime = NOW - age_h)."""
    dirpath.mkdir(parents=True, exist_ok=True)
    p = dirpath / name
    p.write_bytes(b"fake")
    os.utime(p, (NOW - age_h * H, NOW - age_h * H))
    return p


@pytest.fixture
def daemon_up(monkeypatch):
    monkeypatch.setattr(health, "_daemon_alive", lambda: True)


@pytest.fixture
def daemon_down(monkeypatch):
    monkeypatch.setattr(health, "_daemon_alive", lambda: False)


# ----------------------------------------------------------- état « frais » ---

def test_fresh_state_no_warnings(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 6 * H),
        "last_dream": str(NOW - 3 * H),
        "working_memory": json.dumps({"focus": [], "halo": [], "updated_ts": NOW - 1 * H}),
    })
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=26)

    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["warnings"] == []
    assert rep["notes"] == []
    assert rep["daemon_alive"] is True
    assert rep["consolidation_age_h"] == pytest.approx(6.0)   # PRIMAIRE = Sonnet
    assert rep["dream_age_h"] == pytest.approx(3.0)           # secondaire = rêve daemon
    assert rep["wm_age_h"] == pytest.approx(1.0)
    assert rep["backup_age_h"] == pytest.approx(26.0)
    assert rep["last_backup_path"].endswith("memory-20270101-030000.db")
    assert rep["db_size_bytes"] > 0  # la DB kv.db existe et n'est pas vide
    conn.close()


def test_fresh_banner_is_green(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 6 * H),
        "last_dream": str(NOW - 3 * H),
    })
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=26)
    banner = health.health_banner(health.health_report(conn, now=NOW, backup_dir=bdir))
    line1 = banner.splitlines()[0]
    assert line1.startswith("✅")
    assert "daemon up" in line1
    assert "consolidation (Sonnet) 6h" in line1
    assert "rêve de Gemma (secondaire) 3h" in line1
    assert "backup 26h" in line1
    conn.close()


# ------------------------------------- PRIMAIRE : last_consolidation (Sonnet) ---

def test_consolidation_fresh_no_warning(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 6 * H)})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["last_consolidation_ts"] == pytest.approx(NOW - 6 * H)
    assert rep["consolidation_age_h"] == pytest.approx(6.0)
    assert not any("consolidation" in w for w in rep["warnings"])
    conn.close()


def test_consolidation_stale_warns(tmp_path, daemon_up):
    """PRIMAIRE stale (>48h) => LE vrai ⚠️ en titre."""
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 72 * H)})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    joined = " | ".join(rep["warnings"])
    assert "consolidation (Sonnet)" in joined and ">48h" in joined
    banner = health.health_banner(rep)
    assert banner.splitlines()[0].startswith("⚠️")
    conn.close()


def test_consolidation_missing_unknown_no_warning(tmp_path, daemon_up):
    """kv['last_consolidation'] absent : inconnu => PAS de warning (rien de prouvé)."""
    conn = _kv_db(tmp_path, {})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["last_consolidation_ts"] is None
    assert rep["consolidation_age_h"] is None
    assert rep["warnings"] == []
    assert "consolidation (Sonnet) ?" in health.health_banner(rep)
    conn.close()


# --------------------------- SECONDAIRE : rêve daemon (le cœur du fix) ---

def test_stale_dream_with_fresh_consolidation_no_headline_warning(tmp_path, daemon_up):
    """LE bug d'origine : rêve daemon mort 9j + consolidation Sonnet fraîche.

    Avant le fix : « ⚠️ pas de consolidation depuis 9j » (fausse alarme).
    Après : banner ✅, zéro warning, juste une note ℹ️ secondaire.
    """
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 6 * H),
        "last_dream": str(NOW - 9 * 24 * H),
    })
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)

    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["warnings"] == []                       # AUCUNE alarme en titre
    assert len(rep["notes"]) == 1
    assert "rêve de Gemma" in rep["notes"][0] and "secondaire" in rep["notes"][0]

    banner = health.health_banner(rep)
    lines = banner.splitlines()
    assert lines[0].startswith("✅")                   # les notes ne passent PAS l'icône au ⚠️
    assert "consolidation (Sonnet) 6h" in lines[0]
    assert "rêve de Gemma (secondaire) 9j" in lines[0]
    assert not any(l.startswith("⚠️") for l in lines)
    assert any(l.startswith("ℹ️") and "rêve de Gemma" in l for l in lines[1:])
    conn.close()


def test_stale_dream_alone_legacy_db_no_warning(tmp_path, daemon_up):
    """DB d'avant le fix (seul last_dream existe, stale 9j) : plus de fausse alarme."""
    conn = _kv_db(tmp_path, {"last_dream": str(NOW - 9 * 24 * H)})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["warnings"] == []
    assert rep["dream_age_h"] == pytest.approx(9 * 24.0)
    assert any("rêve de Gemma" in n for n in rep["notes"])
    assert health.health_banner(rep).splitlines()[0].startswith("✅")
    conn.close()


def test_fresh_dream_no_note(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 6 * H),
        "last_dream": str(NOW - 3 * H),
    })
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["notes"] == []
    conn.close()


# ----------------------------------------------------------- état « stale » ---

def test_stale_everything_warns(tmp_path, daemon_down):
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 72 * H),
        "last_dream": str(NOW - 9 * 24 * H),
        "working_memory": json.dumps({"updated_ts": NOW - 100 * H}),
    })
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=8 * 24)

    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    joined = " | ".join(rep["warnings"])
    assert "daemon DOWN" in joined
    assert "consolidation (Sonnet)" in joined and ">48h" in joined
    assert "backup" in joined and ">7j" in joined
    assert len(rep["warnings"]) == 3
    # le rêve stale reste une NOTE, pas un 4e warning
    assert any("rêve de Gemma" in n for n in rep["notes"])
    conn.close()


def test_stale_banner_has_warning_lines(tmp_path, daemon_down):
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 72 * H)})
    rep = health.health_report(conn, now=NOW, backup_dir=tmp_path / "vide")
    banner = health.health_banner(rep)
    lines = banner.splitlines()
    assert lines[0].startswith("⚠️")
    assert "daemon DOWN" in lines[0]
    # une ligne ⚠️ par warning + une ligne ℹ️ par note, après la ligne d'état
    assert len(lines) == 1 + len(rep["warnings"]) + len(rep["notes"])
    assert all(l.startswith(("⚠️", "ℹ️")) for l in lines[1:])
    conn.close()


def test_no_backup_dir_warns(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {"last_consolidation": str(NOW - 1 * H)})
    rep = health.health_report(conn, now=NOW, backup_dir=tmp_path / "inexistant")
    assert rep["last_backup_ts"] is None
    assert any("AUCUN backup" in w for w in rep["warnings"])
    assert "backup aucun" in health.health_banner(rep)
    conn.close()


# ------------------------------------------------- manquant / legacy / robuste ---

def test_missing_kv_rows_unknown_no_warning(tmp_path, daemon_up):
    """kv vide : consolidation/rêve/MDT inconnus => PAS de warning (rien de prouvé)."""
    conn = _kv_db(tmp_path, {})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["consolidation_age_h"] is None
    assert rep["dream_age_h"] is None
    assert rep["wm_age_h"] is None
    assert rep["warnings"] == []
    assert rep["notes"] == []
    banner = health.health_banner(rep)
    assert "consolidation (Sonnet) ?" in banner
    assert "rêve de Gemma (secondaire) ?" in banner
    assert "MDT ?" in banner
    conn.close()


def test_legacy_db_without_kv_table_no_raise(tmp_path, daemon_down):
    """DB sans AUCUNE table (pré-2.0 extrême) : aucun raise, champs None."""
    conn = sqlite3.connect(str(tmp_path / "bare.db"))
    rep = health.health_report(conn, now=NOW, backup_dir=tmp_path / "vide")
    assert rep["last_consolidation_ts"] is None
    assert rep["last_dream_ts"] is None
    assert rep["wm_updated_ts"] is None
    assert isinstance(rep["warnings"], list)
    assert isinstance(rep["notes"], list)
    assert isinstance(health.health_banner(rep), str)
    conn.close()


def test_garbage_kv_values_no_raise(tmp_path, daemon_up):
    conn = _kv_db(tmp_path, {
        "last_consolidation": "pas-un-float",
        "last_dream": "pas-un-float",
        "working_memory": "{pas du json",
    })
    rep = health.health_report(conn, now=NOW, backup_dir=tmp_path / "vide")
    assert rep["last_consolidation_ts"] is None
    assert rep["last_dream_ts"] is None
    assert rep["wm_updated_ts"] is None
    conn.close()


def test_banner_legacy_report_without_notes_key_no_raise():
    """health_banner sur un report d'ancienne génération (sans 'notes') : OK."""
    banner = health.health_banner({"warnings": [], "daemon_alive": True})
    assert banner.startswith("✅")


def test_daemon_unknown_no_warning(tmp_path, monkeypatch):
    """_daemon_alive indéterminable (None) : 'daemon ?' SANS warning (pas prouvé)."""
    monkeypatch.setattr(health, "_daemon_alive", lambda: None)
    conn = _kv_db(tmp_path, {})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["daemon_alive"] is None
    assert not any("daemon" in w for w in rep["warnings"])
    assert "daemon ?" in health.health_banner(rep)
    conn.close()


def test_report_is_read_only(tmp_path, daemon_up):
    """AUCUNE écriture : total_changes inchangé, schéma inchangé."""
    conn = _kv_db(tmp_path, {
        "last_consolidation": str(NOW - 6 * H),
        "last_dream": str(NOW - 9 * 24 * H),
    })
    before_changes = conn.total_changes
    before_schema = conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0]
    health.health_report(conn, now=NOW, backup_dir=tmp_path / "vide")
    assert conn.total_changes == before_changes
    assert conn.execute("SELECT COUNT(*) FROM sqlite_master").fetchone()[0] == before_schema
    conn.close()


# ------------------------------- consolidate.py écrit le signal PRIMAIRE ---

def test_mark_consolidated_writes_kv_and_health_sees_it(tmp_path, monkeypatch, daemon_up):
    """Boucle complète : consolidate.mark_consolidated => kv => health_report."""
    monkeypatch.setattr(consolidate, "LOG", tmp_path / "consolidate.log")
    db = tmp_path / "kv.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, ts REAL NOT NULL)")
    conn.commit()

    assert consolidate.mark_consolidated(db_path=db, when=NOW - 6 * H) is True

    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=1)
    rep = health.health_report(conn, now=NOW, backup_dir=bdir)
    assert rep["last_consolidation_ts"] == pytest.approx(NOW - 6 * H)
    assert rep["consolidation_age_h"] == pytest.approx(6.0)
    assert rep["warnings"] == []
    conn.close()


def test_mark_consolidated_overwrites_previous(tmp_path, monkeypatch):
    monkeypatch.setattr(consolidate, "LOG", tmp_path / "consolidate.log")
    db = tmp_path / "kv.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT NOT NULL, ts REAL NOT NULL)")
    conn.commit()
    conn.close()

    assert consolidate.mark_consolidated(db_path=db, when=NOW - 24 * H) is True
    assert consolidate.mark_consolidated(db_path=db, when=NOW - 1 * H) is True

    conn = sqlite3.connect(str(db))
    rows = conn.execute("SELECT value FROM kv WHERE key='last_consolidation'").fetchall()
    assert len(rows) == 1
    assert float(rows[0][0]) == pytest.approx(NOW - 1 * H)
    conn.close()


def test_mark_consolidated_missing_db_is_safe(tmp_path, monkeypatch):
    """DB absente : pas de création parasite, pas d'exception, False."""
    monkeypatch.setattr(consolidate, "LOG", tmp_path / "consolidate.log")
    missing = tmp_path / "nexiste-pas.db"
    assert consolidate.mark_consolidated(db_path=missing, when=NOW) is False
    assert not missing.exists()


def test_mark_consolidated_legacy_db_without_kv_is_safe(tmp_path, monkeypatch):
    """DB sans table kv : erreur loguée, False, jamais d'exception."""
    monkeypatch.setattr(consolidate, "LOG", tmp_path / "consolidate.log")
    db = tmp_path / "bare.db"
    sqlite3.connect(str(db)).close()  # fichier DB vide, aucune table
    assert consolidate.mark_consolidated(db_path=db, when=NOW) is False


# ------------------------------------------------------------- formatage ---

def test_fmt_age():
    assert health._fmt_age(None) == "?"
    assert health._fmt_age(0.4) == "<1h"
    assert health._fmt_age(3.2) == "3h"
    assert health._fmt_age(72.0) == "3j"


def test_health_report_default_now(tmp_path, daemon_up):
    """now=None : horloge réelle, âge d'un last_consolidation tout frais ~0."""
    conn = _kv_db(tmp_path, {"last_consolidation": str(time.time())})
    bdir = tmp_path / "bk"
    _mk_backup(bdir, "memory-20270101-030000.db", age_h=0)
    os.utime(bdir / "memory-20270101-030000.db", None)  # mtime = maintenant
    rep = health.health_report(conn, backup_dir=bdir)
    assert rep["consolidation_age_h"] is not None and rep["consolidation_age_h"] < 0.1
    conn.close()
