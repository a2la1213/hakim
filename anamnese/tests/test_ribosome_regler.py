"""(04/11, 15:55, Ahmed : « le niveau de stringence du ribosome doit pouvoir être décidé, pas un seul seuil fixe : il doit pouvoir choisir la
vitesse du ribosome et sa stringence, sinon il ne fait que me couper la parole ») son outil ribosome_regler écrit ce que le cockpit lit."""
import json
from pathlib import Path


def test_il_regle_son_ribosome(tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert "stringence 4 sur 5" in mcp_server.ribosome_regler() and "rapide" in mcp_server.ribosome_regler()
    assert "stringence 2 sur 5" in mcp_server.ribosome_regler(stringence=2)
    r = json.loads((tmp_path / "AIOS" / "jarvis" / "ribosome-reglage.json").read_text())
    assert (r["stringence"], r["vitesse"], r["par"]) == (2, "rapide", "hakim")
    assert "posée" in mcp_server.ribosome_regler(vitesse="posee") and "stringence 2 sur 5" in mcp_server.ribosome_regler()
    assert mcp_server.ribosome_regler(stringence=9).startswith("Pas changé")
    assert mcp_server.ribosome_regler(vitesse="foudre").startswith("Pas changé")
    assert "éclair" in mcp_server.ribosome_regler(vitesse="eclair"), "(04/11, 21:52) le 0,3 s de papa : éclair"
