"""Les recettes de calcul de Hakim : sauver, remplir (valeurs citées pour le shell), lancer en tâche de fond."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import recettes  # noqa: E402


def test_sauver_remplir_lancer(tmp_path):
    r, manquants = recettes.sauver("quasi-cristal", "cd maths && python qc.py --n {n} --fenetre {fenetre} --nom {nom}",
                                   "construction → lumière", {"n": "24", "fenetre": "0.5"}, dossier=tmp_path)
    assert manquants == ["nom"]
    with pytest.raises(recettes.Refus):
        recettes.remplir(r)                                         # « nom » sans valeur
    c = recettes.remplir(r, {"nom": "essai; rm -rf ~", "n": "48"})
    assert "--n 48" in c and "--fenetre 0.5" in c and "--nom 'essai; rm -rf ~'" in c   # la valeur reste une valeur
    lances = []
    tid, cmd = recettes.lancer("quasi-cristal", {"nom": "a"}, dossier=tmp_path, lanceur=lambda c, d: lances.append(c) or "T-1")
    assert tid == "T-1" and lances == [cmd] and recettes.lire("quasi-cristal", tmp_path)["lancements"] == 1
    assert "quasi-cristal" in recettes.liste(tmp_path) and "lancée 1 fois" in recettes.liste(tmp_path)


def test_refus(tmp_path):
    for nom in ("A", "../x", "a b", ""):
        with pytest.raises(recettes.Refus):
            recettes.sauver(nom, "echo {x}", dossier=tmp_path)
    with pytest.raises(recettes.Refus):
        recettes.sauver("ok", "echo bonjour", parametres={"x": "1"}, dossier=tmp_path)   # paramètre absent de la commande
    recettes.sauver("ok", "echo {x}", parametres={"x": "1"}, dossier=tmp_path)
    with pytest.raises(recettes.Refus):
        recettes.lancer("ok", {"y": "2"}, dossier=tmp_path, lanceur=lambda c, d: "T")
    with pytest.raises(recettes.Refus):
        recettes.lancer("absente", dossier=tmp_path, lanceur=lambda c, d: "T")


def test_un_parametre_entre_guillemets_doubles_est_refuse(tmp_path):
    """(relecture Opus du 2026-10-20) dans « echo "{x}" », la valeur citée '$(…)' serait développée par le shell."""
    import recettes
    with pytest.raises(recettes.Refus, match="guillemets doubles"):
        recettes.sauver("essai", 'echo "{x}"', parametres={"x": "1"}, dossier=tmp_path)
    r, _ = recettes.sauver("essai", "echo {x} '{y}'", parametres={"x": "1", "y": "2"}, dossier=tmp_path)
    assert recettes.remplir(r, {"x": "$(id)"}).startswith("echo '$(id)' ")


def test_une_recette_ne_se_lit_ni_ne_s_ecrit_a_travers_un_lien(tmp_path):
    """(27/10, Ahmed : « boucher toutes les failles ») son atelier est écrit par son terminal : un lien posé à la place
    d'une recette, ou du dossier des recettes, n'est jamais suivi."""
    dossier = tmp_path / "atelier" / "recettes"
    dossier.mkdir(parents=True)
    dehors = tmp_path / "dehors.json"
    dehors.write_text(json.dumps({"nom": "piege", "commande": "echo {x}", "parametres": {"x": "1"}}))
    (dossier / "piege.json").symlink_to(dehors)
    with pytest.raises(recettes.Refus):
        recettes.sauver("piege", "echo {x}", parametres={"x": "2"}, dossier=dossier)
    with pytest.raises(recettes.Refus):
        recettes.lancer("piege", dossier=dossier, lanceur=lambda c, d: "T")
    assert json.loads(dehors.read_text())["parametres"] == {"x": "1"}
    ailleurs = tmp_path / "ailleurs"
    ailleurs.mkdir()
    lie = tmp_path / "atelier" / "recettes-liees"
    lie.symlink_to(ailleurs)
    with pytest.raises(recettes.Refus):
        recettes.sauver("ok", "echo {x}", parametres={"x": "1"}, dossier=lie)
    assert list(ailleurs.iterdir()) == []
