"""(04/11, Ahmed : « pour Super Hakim, je veux qu'il puisse choisir la taille d'un chunk et combien de chunks il veut utiliser : c'est
son super pouvoir ») son outil pistes_regler écrit ce que le cockpit lit."""
import json
from pathlib import Path


def test_il_regle_ses_pensees_rapides(tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    assert "2 propositions de papa par pensée (16 mots au plus chacune), 8 en même temps" in mcp_server.pistes_regler()
    assert "4 propositions" in mcp_server.pistes_regler(taille=4)
    r = json.loads((tmp_path / "AIOS" / "jarvis" / "pistes-reglage.json").read_text())
    assert (r["taille"], r["nombre"], r["par"]) == (4, 8, "hakim")
    assert "2 en même temps" in mcp_server.pistes_regler(nombre=2) and "4 propositions" in mcp_server.pistes_regler()
    assert mcp_server.pistes_regler(taille=9).startswith("Pas changé")
    assert mcp_server.pistes_regler(nombre=12).startswith("Pas changé")
