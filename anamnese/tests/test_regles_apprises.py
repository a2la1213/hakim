"""Des erreurs aux règles, niveau 2 (regles_apprises.py, 2026-10-22) : les groupes rendus par Sonnet sont vérifiés."""
import json

import regles_apprises as R

ERREURS = [{"id": f"e{i}", "quoi": f"erreur {i}", "correction": ""} for i in range(8)]


def test_seuls_les_groupes_valides_passent():
    sortie = json.dumps({"groupes": [
        {"nom": "surconfiance", "cause": "conclure plus que la preuve", "erreurs": ["e0", "e1", "e2"], "regle": "La conclusion ne dépasse pas la preuve.", "double": 3},
        {"nom": "trop petit", "erreurs": ["e3", "e4"], "regle": "x"},
        {"nom": "inventé", "erreurs": ["e5", "e6", "zz"], "regle": "y"},
        {"nom": "doublon", "erreurs": ["e0", "e6", "e7"], "regle": "z"},
        {"nom": "bavard", "erreurs": ["e3", "e4", "e5"], "regle": " ".join(["mot"] * 30)}]})
    r = R.regrouper(ERREURS, "1. Une règle.", lancer=lambda p: "Voici : " + sortie)
    assert [g["nom"] for g in r["groupes"]] == ["surconfiance"] and r["groupes"][0]["double"] == 3
    assert {x["nom"] for x in r["refus"]} == {"trop petit", "inventé", "doublon", "bavard"}
    assert "e0" not in r["seules"] and "e7" in r["seules"]


def test_le_prompt_contient_le_carnet_et_les_regles():
    vus = []
    R.regrouper(ERREURS, "1. Tout chiffre est sourcé.", lancer=lambda p: vus.append(p) or "{}")
    assert "e7 : erreur 7" in vus[0] and "Tout chiffre est sourcé" in vus[0]
