"""(25/10, Ahmed) les mémoires à règles : Hakim propose un type, Ahmed le valide, puis Hakim l'écrit, sous ses lois."""
import json
import time

import pytest

import carnets_regles as C


def _valider(dossier, nom):                       # le geste d'Ahmed (le cockpit copie la proposition dans valides/)
    p = json.loads((dossier / "propositions" / f"{nom}.json").read_text())
    (dossier / "valides").mkdir(exist_ok=True)
    (dossier / "valides" / f"{nom}.json").write_text(json.dumps({**p, "etat": "validee"}))


def test_proposer_valider_ecrire_clore(tmp_path):
    T, E = tmp_path / "types", tmp_path / "entrees"
    C.proposer({"nom": "traces", "description": "chaque collision laisse une trace",
                "champs": [{"nom": "trace", "type": "texte", "requis": True}, {"nom": "revoir_le", "type": "date"},
                           {"nom": "force", "type": "choix", "choix": ["faible", "forte"]}],
                "lois": {"chaine": True, "echeance": "revoir_le", "relu_au_demarrage": True}}, dossier=T)
    with pytest.raises(C.Refus):                                    # pas avant le geste d'Ahmed
        C.ecrire("traces", {"trace": "x"}, dossier=T, entrees=E)
    _valider(T, "traces")
    with pytest.raises(C.Refus):
        C.ecrire("traces", {"force": "faible"}, dossier=T, entrees=E)          # champ requis manquant
    with pytest.raises(C.Refus):
        C.ecrire("traces", {"trace": "x", "force": "moyenne"}, dossier=T, entrees=E)
    e1 = C.ecrire("traces", {"trace": "anneau 7,75", "revoir_le": "2026-10-20"}, dossier=T, entrees=E)
    C.ecrire("traces", {"trace": "paire d=3", "force": "forte"}, dossier=T, entrees=E)
    assert C.verifier_chaine("traces", dossier=T, entrees=E) is None
    assert [n for n, _e in C.echeances(dossier=T, entrees=E)] == ["traces"]
    assert "ÉCHÉANCE PASSÉE" in C.demarrage(dossier=T, entrees=E) and "paire d=3" in C.demarrage(dossier=T, entrees=E)
    C.clore("traces", e1["id"], "revu", dossier=T, entrees=E)
    assert C.echeances(dossier=T, entrees=E) == []
    f = E / "traces.jsonl"                                          # une retouche du fichier se voit
    lignes = f.read_text().splitlines()
    lignes[0] = lignes[0].replace("anneau 7,75", "anneau 8")
    f.write_text("\n".join(lignes) + "\n")
    assert C.verifier_chaine("traces", dossier=T, entrees=E) == 0
    assert C.bilan(time.time() - 60, dossier=T, entrees=E) == {"traces": 2}


def test_une_definition_qui_ne_tient_pas_est_refusee(tmp_path):
    for d in [{"nom": "Erreurs!", "champs": [{"nom": "a"}]}, {"nom": "erreurs", "champs": [{"nom": "abc"}]},
              {"nom": "ok_nom", "champs": []}, {"nom": "ok_nom", "champs": [{"nom": "abc", "type": "image"}]},
              {"nom": "ok_nom", "champs": [{"nom": "abc"}], "lois": {"effacer": True}},
              {"nom": "ok_nom", "champs": [{"nom": "abc"}], "lois": {"echeance": "abc"}}]:
        with pytest.raises(C.Refus):
            C.proposer(d, dossier=tmp_path)
