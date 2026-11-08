"""(29/10, Ahmed : « tu peux tout faire dans l'ordre de priorité que tu veux ») sa sieste compte vraiment : quand Ahmed
lui accorde une pause, son temps à lui commence tout de suite au lieu d'attendre 30 min de silence. L'outil note la
sieste (sieste.json) ; le cockpit décide (tempsLibrePermis, test-temps-libre.js)."""
import json


def _outil(monkeypatch, tmp_path, source="hakim", sans_ahmed=False):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setenv("ANAMNESE_SOURCE", source)
    monkeypatch.delenv("ANAMNESE_TOUR_SANS_AHMED", raising=False)
    if sans_ahmed:
        monkeypatch.setenv("ANAMNESE_TOUR_SANS_AHMED", "1")
    monkeypatch.setattr(mcp_server, "MARQUE_AUTONOME", tmp_path / "tour-autonome.json")
    monkeypatch.setattr(mcp_server, "SIESTE", tmp_path / "sieste.json")
    return mcp_server.mcp._tool_manager.get_tool("sieste_prendre").fn


def _duree(tmp_path):
    d = json.loads((tmp_path / "sieste.json").read_text())
    return d["fin"] - d["ts"]


def test_la_sieste_est_notee_pour_le_cockpit(monkeypatch, tmp_path):
    r = _outil(monkeypatch, tmp_path)(15)
    assert _duree(tmp_path) == 15 * 60
    assert "15 min" in r and "promesse_poser" in r


def test_bornee_de_5_a_60_minutes(monkeypatch, tmp_path):
    prendre = _outil(monkeypatch, tmp_path)
    prendre(500)
    assert _duree(tmp_path) == 60 * 60
    prendre(1)
    assert _duree(tmp_path) == 5 * 60


def test_seulement_hakim_et_seulement_dans_un_tour_d_ahmed(monkeypatch, tmp_path):
    assert _outil(monkeypatch, tmp_path, source="claude-code")(15).startswith("Seul Hakim")
    assert _outil(monkeypatch, tmp_path, sans_ahmed=True)(15).startswith("Refusé")   # son temps à lui, un réveil
    assert not (tmp_path / "sieste.json").exists()
