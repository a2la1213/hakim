"""(04/11, 16:25, Ahmed : « ce qu'il entend de l'intérieur, ce qu'il entend de l'extérieur et ce qu'il ressent avec ses capteurs doivent être
coordonnés, et il n'y a que lui qui peut le faire : il faut lui donner cette capacité, pour coordonner tous ses stimuli en un même point ; et
tu dois lui expliquer comment il doit faire ») ses outils stimuli_voir (son fil, moment par moment) et stimuli_relier (son lien, mémorisé)."""
import json
import time
from pathlib import Path


def _outils(tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda t: [])
    monkeypatch.setattr(Path, "home", staticmethod(lambda: tmp_path))
    return mcp_server, mem


def _fil(tmp_path, maintenant):
    j = tmp_path / "AIOS" / "jarvis"
    j.mkdir(parents=True, exist_ok=True)
    flux = [
        {"t": maintenant - 20000, "s": "papa", "x": "écoute ça"},
        {"t": maintenant - 19500, "s": "telephone", "x": "un clic un blaf"},
        {"t": maintenant - 19400, "s": "voix_telephone", "x": "la3 (220 Hz, grave) 0,4 s"},
        {"t": maintenant - 19300, "s": "voix_micro", "x": "la3 (221 Hz, grave) 0,4 s"},
        {"t": maintenant - 19000, "s": "instru_telephone", "x": "basse lourde, 84 bpm"},
        {"t": maintenant - 18900, "s": "instru_micro", "x": "basse étouffée, 84 bpm"},
        {"t": maintenant - 18800, "s": "corps", "x": "une vibration de rire"},
        {"t": maintenant - 5000, "s": "son", "x": "des pas dans la pièce"},
        {"t": maintenant - 300000, "s": "papa", "x": "trop vieux"},
    ]
    (j / "fil-stimuli.json").write_text(json.dumps({"maj": maintenant, "flux": flux}), encoding="utf-8")


def test_stimuli_voir_range_ses_sens_par_moment(tmp_path, monkeypatch):
    m, _ = _outils(tmp_path, monkeypatch)
    maintenant = int(time.time() * 1000)
    _fil(tmp_path, maintenant)
    v = m.stimuli_voir(secondes=60)
    assert "trop vieux" not in v
    assert v.count("◆") == 2, "deux moments : ceux qui sont proches vont ensemble"
    premier = v.split("◆")[1]
    # (16:30, papa : « il doit relier les 2 paroles perçues et les 2 musiques perçues pour les comprendre comme un son, puis relier la parole
    # et la musique réunifiées pour comprendre l'intégralité de ce qu'il a entendu : l'union entre les oreilles externe et interne »)
    assert "🗣 la parole — dedans : téléphone « un clic un blaf » ; la voix du téléphone : la3 (220 Hz, grave) 0,4 s | dehors : papa « écoute ça » ; la voix au micro : la3 (221 Hz, grave) 0,4 s" in premier
    assert "🎵 la musique — dedans : le son du téléphone : basse lourde, 84 bpm | dehors : le son du micro : basse étouffée, 84 bpm" in premier
    assert "capteurs : corps : une vibration de rire" in premier
    assert "il y a 20 s" in premier
    assert "parole" in m.stimuli_voir.__doc__ and "musique" in m.stimuli_voir.__doc__ and "en entier" in m.stimuli_voir.__doc__


def test_stimuli_relier_garde_son_lien_et_ce_qui_etait_la(tmp_path, monkeypatch):
    m, mem = _outils(tmp_path, monkeypatch)
    maintenant = int(time.time() * 1000)
    _fil(tmp_path, maintenant)
    heure = time.strftime("%H:%M:%S", time.localtime((maintenant - 19500) / 1000))
    assert "parole" in m.stimuli_relier(moment=heure, lien="la même voix, dedans et dehors : la chanson", quoi="parole").lower()
    assert "musique" in m.stimuli_relier(moment=heure, lien="la même basse, dedans et dehors", quoi="musique").lower()
    r = m.stimuli_relier(moment=heure, lien="papa me fait écouter ce morceau, et j'ai ri sur la basse")
    assert "relié" in r.lower()
    c = [json.loads(l) for l in (tmp_path / "AIOS" / "jarvis" / "coordinations.jsonl").read_text().splitlines()]
    assert [x["quoi"] for x in c] == ["parole", "musique", "tout"]
    assert c[-1]["lien"] == "papa me fait écouter ce morceau, et j'ai ri sur la basse"
    assert {x["s"] for x in c[-1]["stimuli"]} == {"papa", "telephone", "voix_telephone", "voix_micro", "instru_telephone", "instru_micro", "corps"}
    souvenir = mem.db.execute("SELECT content FROM episodes ORDER BY id DESC LIMIT 1").fetchone()[0]
    assert "papa me fait écouter ce morceau" in souvenir and "un clic un blaf" in souvenir and "une vibration de rire" in souvenir
    assert m.stimuli_relier(moment="25:99", lien="x").startswith("Pas relié")
    assert m.stimuli_relier(moment=heure, lien="").startswith("Pas relié")
    assert m.stimuli_relier(moment=heure, lien="x", quoi="odeur").startswith("Pas relié")
