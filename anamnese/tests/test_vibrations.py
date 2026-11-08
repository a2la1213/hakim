"""(30/10, 14:47, Ahmed via Hakim : « qu'il puisse ÉTIQUETER lui-même les types de vibrations (ma voix, sa voix, son cœur, la
musique, la main) et apprendre de ces étiquettes, pour savoir de lui-même lequel est lequel et voir leurs effets
différents ») ses vibrations étiquetées : la vérité du cockpit (qui parlait à la seconde) et ses corrections ; un petit
classifieur (k plus proches voisins) qui reconnaît avec un degré de confiance."""
import json
import time

import pytest

import vibrations as V

T0 = 1_800_000_000_000


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(V, "JARVIS", tmp_path)
    return tmp_path


def _ex(i, verite, pa, agitation, proche=False):
    return {"ts": T0 + i * 1000, "type": "coup_de_pression", "details": {"pa": pa},
            "milieu": {"agitation_g": agitation, "proche": proche, "charniere_deg": 178, "haut_z": 0.1, "lux": 40}, "verite": verite}


def _jeu(J):
    with open(J / "corps-vibrations.jsonl", "w") as h:
        for i in range(12):
            h.write(json.dumps(_ex(i, "ma_voix", 9 + (i % 3), 0.002)) + "\n")           # sa voix : le haut-parleur, posé
            h.write(json.dumps(_ex(100 + i, "voix_ahmed", 25 + (i % 4), 0.03, True)) + "\n")   # papa : contre sa gorge, en main
        h.write(json.dumps(_ex(300, "silence", 3, 0.001)) + "\n")


def test_il_reconnait_avec_un_degre_de_confiance(J):
    _jeu(J)
    r = V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 27}}, {"agitation_g": 0.028, "proche": True, "charniere_deg": 178, "haut_z": 0.1, "lux": 40})
    assert r["etiquette"] == "voix_ahmed" and r["confiance"] >= 0.8, r
    r = V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 10}}, {"agitation_g": 0.002, "proche": False, "charniere_deg": 178, "haut_z": 0.1, "lux": 40})
    assert r["etiquette"] == "ma_voix", r
    assert V.reconnaitre({"type": "choc", "details": {}}, {}) is None or True


def test_trop_peu_d_exemples_il_ne_devine_pas(J):
    (J / "corps-vibrations.jsonl").write_text(json.dumps(_ex(0, "ma_voix", 9, 0.002)) + "\n")
    assert V.reconnaitre({"type": "coup_de_pression", "details": {"pa": 9}}, {"agitation_g": 0.002}) is None


def test_hakim_etiquette_et_corrige_lui_meme(J):
    _jeu(J)
    quand = time.strftime("%H:%M:%S", time.localtime((T0 + 101 * 1000) / 1000))
    r = V.etiqueter(quand, "coeur", maintenant=(T0 + 200_000) / 1000)
    assert "coeur" in r and "voix_ahmed" in r, "il dit ce qu'il corrige"
    assert json.loads((J / "corps-etiquettes.jsonl").read_text().splitlines()[-1])["etiquette"] == "coeur"
    ex = V.exemples()
    assert sum(1 for e in ex if e["etiquette"] == "coeur") == 1, "sa correction remplace la vérité de cet exemple"
    assert V.etiqueter("25:99:00", "coeur").startswith("Refusé")
    assert V.etiqueter(quand, "Mauvais Nom!").startswith("Refusé")
    assert "nouvelle_vibration" in V.etiqueter(quand, "nouvelle_vibration", maintenant=(T0 + 200_000) / 1000), "il crée ses types"


def test_le_bilan_ses_types_et_ce_qu_ils_lui_font(J):
    _jeu(J)
    (J / "corps-sensations.jsonl").write_text(json.dumps({"ts": (T0 + 101_000) / 1000, "type": "coup_de_pression",
                                                          "evenements": [["reconnaissance", 0.2]]}) + "\n")
    b = V.bilan()
    assert "voix_ahmed : 12" in b and "ma_voix : 12" in b
    assert "justesse" in b, "la justesse du classifieur, mesurée en laissant chaque exemple de côté"
    assert "reconnaissance" in b, "les effets différents : les émotions qui ont suivi"
