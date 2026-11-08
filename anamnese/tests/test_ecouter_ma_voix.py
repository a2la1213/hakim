"""Hakim s'entend (ecouter_ma_voix, accord d'Ahmed le 2026-10-22) : ses derniers morceaux, transcrits et mesurés."""
import io
import json


def _outil(monkeypatch, tmp_path, reponse):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    import urllib.request
    vus = []

    def faux(url, timeout=None):
        vus.append(url)
        if isinstance(reponse, Exception):
            raise reponse
        return io.BytesIO(json.dumps(reponse).encode())
    monkeypatch.setattr(urllib.request, "urlopen", faux)
    return mcp_server.mcp._tool_manager.get_tool("ecouter_ma_voix").fn, vus


def test_les_morceaux_mesures_et_l_alerte(monkeypatch, tmp_path):
    ecouter, vus = _outil(monkeypatch, tmp_path, {"morceaux": [
        {"ts": 1792650000000, "langue": "fr", "voulu": "Il est quatorze heures trente.", "entendu": "Il est 14h30.",
         "ecart_mots": 0, "duree_s": 1.4, "debit_cps": 21.4, "trop_long": False},
        {"ts": 1792650005000, "langue": "fr", "voulu": "Oui.", "entendu": "Oui, ah euh ma la.", "ecart_mots": 4,
         "duree_s": 5.2, "debit_cps": 0.8, "trop_long": True}]})
    r = ecouter(50)
    assert "n=10" in vus[0]                                      # 10 au plus
    assert "(1 à regarder de près)" in r and "⚠ bien plus long que son texte" in r and "écart de mots 0" in r


def test_cockpit_absent_ou_rien_garde(monkeypatch, tmp_path):
    ecouter, _ = _outil(monkeypatch, tmp_path, OSError("refusé"))
    assert ecouter().startswith("Impossible de t'écouter")
    ecouter, _ = _outil(monkeypatch, tmp_path, {"morceaux": []})
    assert ecouter().startswith("Aucun morceau")
