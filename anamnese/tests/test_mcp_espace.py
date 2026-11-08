"""(26/10, Ahmed : « un espace de stockage temporaire : il reprend ce dont il a besoin, et chaque balayage n'ajoute que le
neuf ») l'espace de conversation : tout ce que le balayage a trouvé depuis le début de la conversation, que le tri à part
du cockpit a gardé ou non ; Hakim le fouille avec espace_conversation, puis memory_lire pour le détail."""
import json
import time

import memory
import migrations
import rubrics


def _serveur(tmp_path, monkeypatch, contenu):
    mem = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    f = tmp_path / "espace.json"
    if contenu is not None:
        f.write_text(json.dumps(contenu))
    monkeypatch.setattr(mcp_server, "ESPACE", f)
    return mcp_server


def test_l_espace_se_fouille_par_les_mots_sans_accents(tmp_path, monkeypatch):
    lignes = [{"id": 1, "l": "#1 · 01/09/26 · projets · le gâteau de l'anniversaire de sa fille", "choisi": True},
              {"id": 2, "l": "#2 · 02/09/26 · projets · réglage du routeur de mémoire", "choisi": False},
              {"id": 3, "l": "#3 · 03/09/26 · projets · anniversaire de Nora, le gateau au chocolat", "choisi": False}]
    s = _serveur(tmp_path, monkeypatch, {"session": "s1", "maj": time.time() * 1000, "lignes": lignes})
    r = s.espace_conversation("gateau anniversaire")
    assert "3 souvenirs balayés" in r and "1 déjà reçu" in r
    assert "#1 ·" in r and "#3 ·" in r and "routeur" not in r, "seulement ce qui porte les mots"
    assert "déjà reçu" in r.split("#1 ·")[1].split("\n")[0]
    tout = s.espace_conversation("")
    assert tout.index("#3 ·") < tout.index("#1 ·"), "sans mots : les plus récents d'abord"
    assert "espace_conversation" in s.OUTILS_LECTURE


def test_un_espace_absent_ne_casse_rien(tmp_path, monkeypatch):
    s = _serveur(tmp_path, monkeypatch, None)
    assert "vide" in s.espace_conversation("gateau")
