"""Escalade (escalate.py) : un warning de santé actionnable → notification
(mockée) + brief SDD dans brief_dir. Best-effort ABSOLU, dédup par marqueur.

Forme RÉELLE consommée = celle de health.health_report(conn) :
{"warnings": [<str>, ...], "notes": [<str>, ...], ...} — les problèmes
actionnables sont les STRINGS de `warnings` ; les `notes` n'escaladent JAMAIS.
"""

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))

import escalate
import health


def test_escalate_ecrit_un_brief(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(escalate, "notify", lambda t, m: calls.append((t, m)))
    report = {"warnings": ["daemon DOWN (launchd/processus introuvable)"], "notes": []}
    r = escalate.escalate(report, brief_dir=tmp_path)
    assert r["notified"] is True and calls                     # notif émise
    assert r["brief_path"] is not None
    brief = pathlib.Path(r["brief_path"])
    assert brief.exists() and brief.parent == tmp_path         # brief écrit dans brief_dir
    body = brief.read_text(encoding="utf-8")
    assert "daemon" in body.lower()                            # le symptôme est dedans
    # Gabarit SDD : contexte, symptôme, diagnostic, lancement 1 clic.
    low = body.lower()
    assert "symptôme" in low and "diag" in low and "lance" in low


def test_escalate_dedup_et_sain_si_rien(tmp_path, monkeypatch):
    monkeypatch.setattr(escalate, "notify", lambda t, m: None)
    # Rien à faire : aucun warning => pas de notif, pas de brief.
    r0 = escalate.escalate({"warnings": [], "notes": []}, brief_dir=tmp_path)
    assert r0["notified"] is False and r0["brief_path"] is None
    rep = {"warnings": ["AUCUN backup dans /tmp/nulle-part"], "notes": []}
    r1 = escalate.escalate(rep, brief_dir=tmp_path)
    assert r1["notified"] is True
    r2 = escalate.escalate(rep, brief_dir=tmp_path)            # 2e fois = dédup
    assert r2["notified"] is False and r2["brief_path"] is None


def test_escalate_dedup_a_fenetre_recidive_apres_ttl(tmp_path, monkeypatch):
    """Dédup À FENÊTRE : muet dans les 24h, mais un problème qui RÉCIDIVE au-delà
    ré-escalade (un warning statique 'daemon DOWN' ne doit pas rester muet à vie)."""
    import os
    import time
    monkeypatch.setattr(escalate, "notify", lambda t, m: None)
    rep = {"warnings": ["daemon DOWN (launchd/processus introuvable)"], "notes": []}
    assert escalate.escalate(rep, brief_dir=tmp_path)["notified"] is True       # 1re fois
    assert escalate.escalate(rep, brief_dir=tmp_path)["notified"] is False      # récent → muet
    # vieillir le marqueur au-delà du TTL → récidive ré-escalade
    marker = next((tmp_path / ".escalated").iterdir())
    old = time.time() - (escalate.DEDUP_TTL_H + 1) * 3600
    os.utime(marker, (old, old))
    assert escalate.escalate(rep, brief_dir=tmp_path)["notified"] is True       # récidive → ré-escalade


def test_escalate_ignore_les_notes(tmp_path, monkeypatch):
    """Les notes ℹ️ (ex. rêve daemon stale) sont douces : JAMAIS d'escalade."""
    calls = []
    monkeypatch.setattr(escalate, "notify", lambda t, m: calls.append((t, m)))
    rep = {"warnings": [], "notes": ["rêve daemon inactif depuis 9j"]}
    r = escalate.escalate(rep, brief_dir=tmp_path)
    assert r["notified"] is False and not calls
    assert not list(tmp_path.glob("*.md"))


def test_escalate_best_effort_jamais_d_exception(tmp_path, monkeypatch):
    """Rapport pourri, notify qui explose, brief_dir en lecture impossible :
    escalate ne lève JAMAIS (un watchdog qui plante serait pire que rien)."""
    def boom(t, m):
        raise RuntimeError("osascript KO")
    monkeypatch.setattr(escalate, "notify", boom)
    # notify explose => le warning est quand même briefé, et rien ne remonte.
    r = escalate.escalate({"warnings": ["daemon DOWN"], "notes": []}, brief_dir=tmp_path)
    assert isinstance(r, dict) and set(r) == {"notified", "brief_path"}
    # Entrées dégénérées : None, mauvais types, warnings non-str.
    assert escalate.escalate(None, brief_dir=tmp_path)["notified"] is False
    assert escalate.escalate({"warnings": "pas-une-liste"}, brief_dir=tmp_path) is not None
    assert escalate.escalate({"warnings": [None, 42]}, brief_dir=tmp_path) is not None
    # brief_dir inécrivable (fichier à la place d'un dossier) => sain.
    f = tmp_path / "pas-un-dossier"
    f.write_text("x")
    assert escalate.escalate({"warnings": ["daemon DOWN"]}, brief_dir=f)["notified"] is False


def test_health_banner_branche_l_escalade(tmp_path, monkeypatch):
    """Le banner (là où le bilan est produit) déclenche l'escalade — best-effort :
    si escalate explose, le banner sort quand même intact."""
    seen = []
    monkeypatch.setattr(escalate, "escalate", lambda rep, brief_dir=None: seen.append(rep))
    # Hors pytest (on simule la prod), l'escalade se déclenche sur warning.
    monkeypatch.delenv("PYTEST_CURRENT_TEST", raising=False)
    rep = {"warnings": ["daemon DOWN (launchd/processus introuvable)"], "notes": []}
    banner = health.health_banner(rep)
    assert "⚠️" in banner and seen and seen[0] is rep
    # escalate qui explose ne casse JAMAIS le banner.
    def boom(rep, brief_dir=None):
        raise RuntimeError("escalade KO")
    monkeypatch.setattr(escalate, "escalate", boom)
    assert "⚠️" in health.health_banner(rep)
    # Pas de warning => pas d'escalade.
    seen.clear()
    monkeypatch.setattr(escalate, "escalate", lambda rep, brief_dir=None: seen.append(rep))
    health.health_banner({"warnings": [], "notes": []})
    assert not seen


def test_health_banner_n_escalade_pas_sous_pytest(monkeypatch):
    """Garde anti-effet-de-bord : sous pytest (PYTEST_CURRENT_TEST posé), le
    banner n'escalade pas — les tests santé forgent des warnings sans arrêt."""
    seen = []
    monkeypatch.setattr(escalate, "escalate", lambda rep, brief_dir=None: seen.append(rep))
    assert "PYTEST_CURRENT_TEST" in __import__("os").environ  # posé par pytest
    health.health_banner({"warnings": ["daemon DOWN"], "notes": []})
    assert not seen
