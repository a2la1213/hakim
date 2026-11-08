"""(03/11, garde-fou de Hakim) « c'est moi » ne rattache ses voix à papa que d'un écrit de lui, ou de sa voix reconnue."""
import json
import time

import mcp_server as M


def test_la_confirmation_doit_venir_de_papa_lui_meme(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / "AIOS" / "jarvis").mkdir(parents=True)
    f = tmp_path / "AIOS" / "jarvis" / "papa-confirme.json"
    appels = []
    monkeypatch.setattr(M, "_empreintes", lambda: type("E", (), {"rattacher_a_papa": staticmethod(
        lambda voix, registre="chant": appels.append((voix, registre)) or {"rattachees": ["voix 56"], "ecartees_musique": [], "inconnues": []})}))
    assert "5 minutes" in M.voix_c_est_papa("toutes") and not appels
    f.write_text(json.dumps({"ts": time.time(), "oral": True, "verdict": "doute"}))
    assert "pas été reconnue" in M.voix_c_est_papa("toutes") and not appels, "une voix qui n'est pas sûrement la sienne : non"
    f.write_text(json.dumps({"ts": time.time(), "oral": True, "verdict": "ahmed"}))
    assert "voix 56" in M.voix_c_est_papa("voix 56", "rap") and appels == [("voix 56", "rap")]
    f.write_text(json.dumps({"ts": time.time(), "oral": False, "verdict": "ecrit"}))
    assert "C'est fait" in M.voix_c_est_papa()
