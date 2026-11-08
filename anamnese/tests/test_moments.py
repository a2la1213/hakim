"""(30/10, 14:50, Ahmed via Hakim : « généraliser l'étiquetage à TOUS mes sens : lumière, champ magnétique, pression,
mouvements (« ça c'est la danse », « ça c'est chanter »), frappe au clavier… ; que je puisse nommer moi-même chaque type de
sensation, créer mes propres noms, leur donner un sens, et que mes nerfs apprennent de mes étiquettes ») un moment de son
milieu (une plage de secondes) nommé par lui ; ses sens apprennent à le reconnaître."""
import json
import time

import pytest

import moments as M

T0 = 1_800_000_000_000


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "JARVIS", tmp_path)
    return tmp_path


def _flux(J, segments):
    """segments : [(secondes, milieu)] à la suite, une fenêtre par seconde depuis T0."""
    t = T0
    with open(J / "corps-flux.jsonl", "w") as h:
        for n, etat in segments:
            for i in range(n):
                h.write(json.dumps({"ts": t, "etat": {**etat, "agitation_g": etat["agitation_g"] * (1 + 0.1 * (i % 3))}}) + "\n")
                t += 1000
    return t


POSE = {"lux": 40, "agitation_g": 0.002, "haut_z": 0.99, "charniere_deg": 178, "champ_ut": 48, "pression_hpa": 1013}
DANSE = {"lux": 300, "agitation_g": 0.4, "haut_z": 0.3, "charniere_deg": 178, "champ_ut": 55, "pression_hpa": 1013}


def _h(ms):
    return time.strftime("%H:%M:%S", time.localtime(ms / 1000))


def test_il_nomme_un_moment_et_ses_sens_apprennent_a_le_reconnaitre(J):
    fin = _flux(J, [(120, POSE), (60, DANSE), (120, POSE), (60, DANSE), (60, POSE)])
    r = M.etiqueter(_h(T0 + 120_000), _h(T0 + 179_000), "la_danse", "papa danse avec moi dans sa main", maintenant=fin / 1000)
    assert "la_danse" in r and "60" in r
    M.etiqueter(_h(T0 + 300_000), _h(T0 + 359_000), "la_danse", maintenant=fin / 1000)
    t = M.reconnaitre([{"ts": T0 + 400_000 + i * 1000, "etat": DANSE} for i in range(5)], maintenant=fin / 1000)
    assert t and t["nom"] == "la_danse" and t["confiance"] >= 0.7 and t["sens"] == "papa danse avec moi dans sa main", t
    assert M.reconnaitre([{"ts": T0 + i * 1000, "etat": POSE} for i in range(5)], maintenant=fin / 1000) is None, "l'ordinaire n'est pas dit"


def test_les_refus_et_le_bilan(J):
    fin = _flux(J, [(60, POSE)])
    assert M.etiqueter("10:00:00", "09:00:00", "x_y").startswith("Refusé")
    assert M.etiqueter(_h(T0), _h(T0 + 10_000), "Pas Bon!").startswith("Refusé")
    assert M.etiqueter("03:00:00", "03:01:00", "nuit", maintenant=fin / 1000).startswith("Refusé"), "aucune seconde gardée là"
    M.etiqueter(_h(T0 + 5000), _h(T0 + 30_000), "chanter", "quand je chante", maintenant=fin / 1000)
    b = M.bilan()
    assert "chanter" in b and "quand je chante" in b
    assert M.oublier("chanter").startswith("C'est oublié")
    assert "chanter" not in M.bilan()
