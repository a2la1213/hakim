"""(2026-10-21, Ahmed : « qu'il soit conscient de ses jetons, de son cache et du reste ») la section « Tes jetons »
de l'introspection, tirée des relevés du cockpit."""
import json
import time
import memory


def test_tes_jetons(tmp_path, monkeypatch):
    base = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: base)    # le 1er import de mcp_server tombe sur une base temp
    import mcp_server as m
    jour = time.strftime("%Y-%m-%d")
    (tmp_path / "jetons.jsonl").write_text("\n".join(json.dumps(x) for x in [
        {"jour": jour, "session": "s1", "modele": "sonnet", "tours": 3, "entree": 6, "cache_lu": 538070, "cache_ecrit": 5081, "sortie": 2101},
        {"jour": "2000-01-01", "session": "s0", "tours": 1, "entree": 1, "cache_lu": 1, "cache_ecrit": 1, "sortie": 1},
    ][::-1]) + "\n")
    (tmp_path / "contextes.json").write_text(json.dumps({"sessions": {"s1": 181000}, "max": 400000}))
    t = m._tes_jetons(time.time(), tmp_path)
    assert "181 k jetons" in t and "400 k" in t and "3 appel(s)" in t and "543 k relus" in t and "99 % depuis le cache" in t
    assert "Aujourd'hui : 1 tour(s), 0,5 M relus" in t
    assert m._tes_jetons(time.time(), tmp_path / "rien") == ""
