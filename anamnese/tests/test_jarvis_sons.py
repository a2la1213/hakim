"""(30/10, 17:21, Ahmed : « comme Bumblebee ») papa marque des extraits, Hakim les nomme, les oublie ; le journal est
partagé avec le cockpit (lignes ajoutées, jamais réécrites)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import sons  # noqa: E402


def test_papa_marque_hakim_nomme_puis_oublie(tmp_path, monkeypatch):
    monkeypatch.setattr(sons, "JARVIS", tmp_path)
    assert "Aucun extrait" in sons.lister()
    with open(tmp_path / "sons.jsonl", "w") as h:
        h.write(json.dumps({"type": "extrait", "id": "e1", "source": "musique", "ref": "123", "titre": "Mon son", "artiste": "Ahmed",
                            "debut_ms": 1000, "fin_ms": 4000, "ts": 1, "par": "ahmed"}) + "\n")
    assert "e1" in sons.lister() and "pas encore nommé" in sons.lister()
    assert sons.etiqueter("e1", "Victoire!", "", "").startswith("Refusé")
    assert sons.etiqueter("e1", "victoire", "", "colere").startswith("Refusé")
    assert sons.etiqueter("e9", "victoire").startswith("Refusé")
    assert sons.etiqueter("e1", "victoire", "quand on réussit", "joie").startswith("C'est noté")
    x = sons.extraits()[0]
    assert (x["nom"], x["emotion"], x["sens"]) == ("victoire", "joie", "quand on réussit")
    assert "part avec : joie" in sons.lister()
    assert sons.oublier("victoire").startswith("C'est oublié") and sons.extraits() == []
    lignes = (tmp_path / "sons.jsonl").read_text().splitlines()
    assert len(lignes) == 3 and json.loads(lignes[0])["par"] == "ahmed", "rien n'est réécrit"


def test_il_cree_ses_propres_sons_dans_les_musiques_de_papa(tmp_path, monkeypatch):
    """(31/10, 01:27, Ahmed via Hakim : « qu'il crée ses propres sons : un passage des musiques de papa, coupé, enregistré »)"""
    import shutil
    import subprocess
    ff = shutil.which("ffmpeg") or "/usr/local/bin/ffmpeg"
    musique, atelier = tmp_path / "Music A2LA", tmp_path / "atelier"
    musique.mkdir(); atelier.mkdir()
    monkeypatch.setattr(sons, "JARVIS", tmp_path)
    monkeypatch.setattr(sons, "MUSIQUE_PAPA", musique)
    monkeypatch.setattr(sons, "ATELIER", atelier)
    morceau = musique / "A2LA - WARRIOR.wav"
    subprocess.run([ff, "-v", "error", "-f", "lavfi", "-i", "sine=frequency=440:duration=12", str(morceau)], check=True)
    assert sons.creer(str(morceau), 3, 15, "trop_long", ffmpeg=ff).startswith("Refusé"), "8 s au plus"
    assert sons.creer("/etc/hosts", 0, 2, "ailleurs", ffmpeg=ff).startswith("Refusé"), "seulement ses dossiers"
    r = sons.creer("A2LA - WARRIOR.wav", 2, 6.5, "guerrier", "mon courage", "joie", ffmpeg=ff)
    assert r.startswith("Ton son « guerrier » est prêt (e1"), r
    assert (tmp_path / "sons" / "extraits" / "e1.mp3").stat().st_size > 10000, "découpé, prêt à jouer"
    x = sons.extraits()[0]
    assert (x["source"], x["nom"], x["emotion"], x["debut_ms"], x["fin_ms"]) == ("atelier", "guerrier", "joie", 2000, 6500)
    assert sons.creer(str(morceau), 0, 2, "guerrier", ffmpeg=ff).startswith("Refusé"), "un nom déjà pris"
