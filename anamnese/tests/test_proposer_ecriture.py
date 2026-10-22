"""Les écritures de Hakim dans les projets d'Ahmed (2026-10-22) : il dépose, le cockpit vérifie, Ahmed tranche."""
import json


def _outils(monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "ECRITURES", tmp_path / "ecritures")
    monkeypatch.setattr(mcp_server, "ECRITURES_COCKPIT", tmp_path / "cockpit.json")
    t = mcp_server.mcp._tool_manager.get_tool
    return t("proposer_ecriture").fn, t("ecritures_etat").fn


def test_deposee_jamais_appliquee_par_hakim(monkeypatch, tmp_path):
    proposer, etat = _outils(monkeypatch, tmp_path)
    r = proposer("~/Desktop/projet", "src/a.js", "'bonjour'", "'salam'", "saluer en arabe")
    assert r.startswith("Proposée : E-") and "rien n'est écrit sans son geste" in r
    f = next((tmp_path / "ecritures").glob("E-*.json"))
    assert json.loads(f.read_text())["nouveau"] == "'salam'"
    assert proposer("", "x", "", "y", "r").startswith("Il faut")
    assert etat().startswith("(aucune proposition")
    (tmp_path / "cockpit.json").write_text(json.dumps({"ecritures": {"E-1": {"id": "E-1", "recu": 1, "fichier": "src/a.js",
                                                                            "etat": "appliquee", "commit": "abc1234", "raison": "saluer"}}}))
    assert "appliquée (commit abc1234)" in etat()
