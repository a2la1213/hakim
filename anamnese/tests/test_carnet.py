"""Les carnets d'honnêteté de Hakim (carnet.py, lot G : points 38, 39, 41)."""
import pytest

import carnet
import evenements


def test_prediction_figee_temoignee_puis_tranchee_et_calibree(tmp_path):
    f = tmp_path / "p.jsonl"
    a = carnet.figer("Le pentagone exact donne φ à 10⁻¹² près", 0.9, "ce soir", fichier=f)
    b = carnet.figer("Le quasi-cristal a 5 pics principaux", 0.6, fichier=f)
    c = carnet.figer("Il pleuvra demain à Exempleville", 0.3, fichier=f)
    assert any(e.get("type") == "prediction" and e["donnees"]["id"] == a["id"] for e in evenements.lire())   # témoin chaîné
    carnet.trancher(a["id"], True, fichier=f)
    carnet.trancher(b["id"], False, "4 pics", fichier=f)
    with pytest.raises(carnet.Refus):
        carnet.trancher(a["id"], False, fichier=f)                        # déjà tranchée
    with pytest.raises(carnet.Refus):
        carnet.figer("x", 2, fichier=f)
    cal = carnet.calibration(f)
    assert cal["n"] == 2 and cal["ouvertes"] == 1
    assert cal["brier"] == round(((0.9 - 1) ** 2 + (0.6 - 0) ** 2) / 2, 3)


def test_carnet_d_erreurs_deux_colonnes(tmp_path):
    fe, fp = tmp_path / "e.jsonl", tmp_path / "p.jsonl"
    carnet.noter_erreur("J'ai dit 3,14 au lieu de 3,1416", "corrigé avec le calcul", fichier=fe)
    assert "« disquette » : 0 (vide" in carnet.resume(fp, fe)
    carnet.noter_erreur("J'ai affirmé une source sans l'avoir lue", "dit à Ahmed", "disquette", fichier=fe)
    assert "⚠" in carnet.resume(fp, fe)
    with pytest.raises(carnet.Refus):
        carnet.noter_erreur("quelque chose", "x", "autre", fichier=fe)


def test_une_confiance_de_0_6_ne_compte_qu_une_fois(tmp_path):
    f = tmp_path / "p.jsonl"
    for c in (0.6, 0.6, 0.2):
        carnet.trancher(carnet.figer(f"Prédiction à {c} numéro {id(c)}", c, fichier=f)["id"], True, fichier=f)
    assert sum(n for _a, _b, n in carnet.calibration(f)["tranches"]) == 3
