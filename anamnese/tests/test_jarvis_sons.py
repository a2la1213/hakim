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
