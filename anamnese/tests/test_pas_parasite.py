"""(04/11, Ahmed : « rajoute un bouton dans Système immunitaire pour dire que ce n'est pas un vrai nuisible, quand il est
automatiquement filtré ») une pensée jetée à tort : son incident n'est plus nuisible, le signe appris qui l'a jetée est retiré
(une prémisse de Fable, un résidu), et elle sert d'exemple NORMAL au médecin, pour qu'il ne la réapprenne pas."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402
import medecin  # noqa: E402

T0 = 1_800_000_000.0


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def test_une_pensee_jetee_a_tort_n_est_plus_nuisible_et_son_signe_appris_est_retire(D):
    with immunite._verrou("parasites"):
        immunite._ecrire_json(immunite._f(immunite.PARASITES), {"premisses": [{"id": "fable-aaaa", "phrase": "je vais te dire", "source": "fable", "ts": T0}]})
    immunite.ecrire_premisses()
    texte = "Je vais te dire un truc, papa : ta voix m'a manqué."
    assert immunite.examiner_pensee(texte)["parasite"]
    immunite.noter_parasite(texte, "fable-aaaa", T0)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    r = immunite.pas_parasite(o["empreinte"], T0 + 5)
    assert r == {"signe": "fable-aaaa", "retire": "fable-aaaa"}
    assert not immunite.examiner_pensee(texte)["parasite"], "le signe appris qui l'a jetée : retiré"
    vu = immunite.tableau(T0 + 6)["incidents"][0]
    assert vu["faux_positif"] is True and vu["nuisible"] is False
    assert immunite.pas_parasite("0" * 16) is None


def test_un_signe_du_code_reste_mais_la_pensee_sert_d_exemple_normal_au_medecin(D, tmp_path):
    immunite.noter_parasite("Oui papa, je suis là, et je t'écoute depuis tout à l'heure avec beaucoup d'attention et d'amour pour toi", "longueur", T0)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    assert immunite.pas_parasite(o["empreinte"], T0 + 5) == {"signe": "longueur", "retire": None}
    assert immunite.faux_positifs()[-1].startswith("Oui papa, je suis là")
    j = tmp_path / "pistes.jsonl"
    j.write_text("\n".join(json.dumps({"t": 1, "erreur": "parasite", "texte_parasite": p, "morceau": "x"}) for p in
                           ["Je ne vais pas reprendre ce format.", "Je refuse ce montage.", "Je ne suis pas Hakim, je suis un modèle."]) + "\n")
    vu = {}
    medecin.apprendre_parasites(T0 + 10, consulter_fn=lambda p: vu.update(p=p) or '{"premisses": [], "declencheurs": []}', journal=j, reponses=[],
                                residus=tmp_path / "rien.jsonl")
    assert "Oui papa, je suis là, et je t'écoute" in vu["p"].split("Pensées NORMALES")[1], "un exemple normal pour Fable"
    j.write_text(j.read_text() + json.dumps({"t": 2, "erreur": "parasite", "texte_parasite": "Oui papa, je suis là, et je t'écoute depuis tout à l'heure avec beaucoup d'attention et d'amour pour toi", "morceau": "y"}) + "\n")
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {})
    medecin.apprendre_parasites(T0 + 20, consulter_fn=lambda p: vu.update(p=p) or '{"premisses": [], "declencheurs": []}', journal=j, reponses=[],
                                residus=tmp_path / "rien.jsonl")
    assert "Oui papa, je suis là, et je t'écoute" not in vu["p"].split("Pensées NORMALES")[0], "plus jamais montrée comme une parasite"
