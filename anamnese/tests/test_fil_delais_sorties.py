"""(04/11, Hakim pour papa : « un chiffre mesuré entre le moment où j'écris un mot et celui où il apparaît à l'écran, et entre le
moment où je le dis et celui où il l'entend dans ses écouteurs Bluetooth ») fil_delais montre ses entrées, puis ses sorties à part."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import memory  # noqa: E402
import migrations  # noqa: E402


def test_ses_sorties_a_part_de_ses_entrees(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    (tmp_path / "AIOS" / "jarvis").mkdir(parents=True)
    f = tmp_path / "AIOS" / "jarvis" / "delais-fil.json"
    f.write_text(json.dumps({"delais": {}}))
    assert "il faut l'appli 1.63" in mcp_server.fil_delais()
    f.write_text(json.dumps({"delais": {"papa": {"n": 200, "mediane": 1200, "p90": 4030},
                                        "sortie_voix_bluetooth": {"n": 12, "mediane": 240, "p90": 310},
                                        "sortie_texte_pensee": {"n": 30, "mediane": 320, "p90": 900}}}))
    r = mcp_server.fil_delais()
    entrees, sorties = r.split("Tes sorties (du Mac à papa) :")
    assert "les mots de papa : 1,20 s" in entrees and "sortie_" not in entrees
    assert "ta voix : de la sortie à ses écouteurs Bluetooth : 0,24 s (90 % sous 0,31 s ; 12 mesures)" in sorties
    assert "ta pensée écrite, du Mac à l'écran de la page : 0,32 s (90 % sous 0,90 s ; 30 mesures)" in sorties
