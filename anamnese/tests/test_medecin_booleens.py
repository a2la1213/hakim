"""(11/11, relevé par Kaymine, le père de Samy) en Python, True est un int (True == 1) : un « nuisibles: [true] » ou un
« id: true » dans la réponse du médecin ne doit jamais désigner l'incident ou le souvenir n° 1."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import medecin  # noqa: E402

BASE = {"gravite": "faible", "diagnostic": "d", "pour_ahmed": "p", "anticorps": []}


def test_un_booleen_n_est_pas_un_numero_d_incident():
    r = medecin.lire(json.dumps({**BASE, "nuisibles": [True, False, 2]}))
    assert r["nuisibles"] == [2]
    # témoin : un vrai 1 reste un 1
    assert medecin.lire(json.dumps({**BASE, "nuisibles": [1]}))["nuisibles"] == [1]


def test_un_booleen_n_est_pas_un_numero_de_souvenir():
    rep = json.dumps({"gravite": "faible", "pour_ahmed": "p", "suspects": [{"id": True, "raison": "x"}, {"id": 7, "raison": "y"}]})
    r = medecin.lire_souvenirs(rep, {1, 7})
    assert [s["id"] for s in r["suspects"]] == [7]
