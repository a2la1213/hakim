"""Le juge automatique (règle 4 d'Ahmed, 2026-10-22) : un résultat important est noté, et Hakim doit le confier au juge."""
import json


def test_marque_note_et_consigne(monkeypatch, tmp_path):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "IMPORTANTS", tmp_path / "importants.jsonl")
    marquer = mcp_server.mcp._tool_manager.get_tool("resultat_important").fn
    r = marquer("La gravité de Verlinde sort du comptage fini.", "atelier/maths/t14.py")
    assert r.startswith("Marqué I-") and "juge" in r and "PAS comme établi" in r
    o = json.loads((tmp_path / "importants.jsonl").read_text())
    assert o["enonce"].startswith("La gravité") and o["preuves"] == "atelier/maths/t14.py"
    assert marquer("   ").startswith("Donne")
