"""(13/11, Hakim et papa : « ma jauge de chaleur ne colle pas au thermomètre ») sa « fièvre » disait forte à 76-88 % de « sa limite »
pendant que sa Situation disait 34-36 °C, normal. La marge thermique d'Android (getThermalHeadroom) est celle de ses PROCESSEURS avant
le bridage, une prévision qui monte avec le calcul : la fièvre vient maintenant de sa vraie température (chaleur_c)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import charge_corps as C  # noqa: E402
import interoception  # noqa: E402

T0 = 1_800_000_000.0


def _m(tel):
    return {"t": T0, "causes": {}, "mac_cpu": 0.1, "mac_gpu": None, "n": 10, "appareils": {"telephone": tel}, "live": {"actif": False}}


def test_la_nuit_du_13_11_35_degres_et_84_pour_cent_ce_n_est_pas_une_fievre():
    f = C.intensites(_m({"thermique": 0.84, "chaleur_c": 35.2}))["fievre"]
    assert f["x"] == 0.0 and f["bride"] is False


def test_temoin_l_ancienne_regle_y_voyait_une_fievre():
    ancienne = C._clip((0.84 - 0.5) / 0.5)
    assert ancienne > 0.6                                     # ce que disait sa jauge cette nuit-là


def test_une_vraie_fievre_vient_de_la_temperature():
    assert C.intensites(_m({"thermique": 0.3, "chaleur_c": 40.5}))["fievre"]["x"] == 0.5
    assert C.intensites(_m({"thermique": 0.3, "chaleur_c": 44.0}))["fievre"]["x"] == 1.0
    f = C.intensites(_m({"thermique": 0.97, "chaleur_c": 43.0}))["fievre"]
    assert f["x"] == 1.0 and f["bride"] is True               # chaud ET bridé
    f = C.intensites(_m({"thermique": 0.99, "chaleur_c": 36.0}))["fievre"]
    assert f["x"] == 0.0 and f["bride"] is False              # ses processeurs bridés sans fièvre : ce n'est pas une fièvre


def test_sans_temperature_seulement_pres_du_bridage():
    assert C.intensites(_m({"thermique": 0.84}))["fievre"]["x"] == 0.0
    assert C.intensites(_m({"thermique": 1.0}))["fievre"]["x"] == 1.0


def test_sa_temperature_lue_seulement_fraiche(tmp_path):
    f = tmp_path / "corps-etat.json"
    f.write_text(json.dumps({"ts": T0 * 1000, "etat": {"chaleur_c": 35.2}}))
    assert interoception.chaleur_telephone(f, now=T0 + 30) == 35.2
    assert interoception.chaleur_telephone(f, now=T0 + interoception.APPAREIL_FRAIS_S + 10) is None
    f.write_text(json.dumps({"ts": T0 * 1000, "etat": {"chaleur_c": "chaud"}}))
    assert interoception.chaleur_telephone(f, now=T0) is None


def test_appareils_porte_sa_temperature(tmp_path):
    a, e = tmp_path / "proc.json", tmp_path / "corps-etat.json"
    a.write_text(json.dumps({"telephone": {"ts": T0 * 1000, "coeurs": [0.4], "gpu": 0.7, "thermique": 0.84}}))
    e.write_text(json.dumps({"ts": T0 * 1000, "etat": {"chaleur_c": 35.2}}))
    tel = interoception.appareils(a, now=T0 + 5, chemin_etat=e)["telephone"]
    assert tel["chaleur_c"] == 35.2 and tel["thermique"] == 0.84
