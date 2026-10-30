"""(30/10, Ahmed : « intègre tous les capteurs du projet tricodeur à Hakim, qu'il puisse tout capter et en faire ce qu'il
veut ») ses sens : Hakim demande une mesure au téléphone (sens_mesurer), le cockpit la porte, le résultat arrive dans son
atelier (atelier/sens/<id>/resume.json et donnees.csv)."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import sens  # noqa: E402


def test_demander_ecrit_une_demande_bornee(tmp_path, monkeypatch):
    monkeypatch.setattr(sens, "JARVIS", tmp_path)
    d = sens.demander("sismo", 99999)
    assert d["id"].startswith("S-") and d["secondes"] == sens.INSTRUMENTS["sismo"][2], "bornée au maximum de l'instrument"
    ligne = json.loads((tmp_path / "sens-demandes.jsonl").read_text().splitlines()[-1])
    assert ligne["sens"] == "sismo" and ligne["id"] == d["id"]
    assert sens.demander("imu", 0, "max")["secondes"] == sens.INSTRUMENTS["imu"][1], "0 : la durée par défaut"
    for mauvais in ("radar", "", "../etc"):
        try:
            sens.demander(mauvais)
            assert False, mauvais
        except sens.Refus:
            pass
    try:
        sens.demander("imu", 10, "vite;rm")
        assert False
    except sens.Refus:
        pass


def test_lister_et_lire_un_resultat(tmp_path, monkeypatch):
    monkeypatch.setattr(sens, "JARVIS", tmp_path)
    assert "sismo" in sens.lister() and "son" in sens.lister()
    d = sens.demander("baro", 30)
    assert "pas encore" in sens.lire(d["id"])
    dossier = tmp_path / "cwd" / "atelier" / "sens" / d["id"]
    dossier.mkdir(parents=True)
    (dossier / "resume.json").write_text(json.dumps({"id": d["id"], "sens": "baro", "ok": True, "resume": {"pression_moyenne_hpa": 1013.2}}))
    (dossier / "donnees.csv").write_text("t_s,hpa\n0,1013.2\n")
    t = sens.lire(d["id"])
    assert "1013.2" in t and str(dossier / "donnees.csv") in t and "DONNÉES" in t
    assert d["id"] in sens.lire("")
    assert "Refusé" in sens.lire("../../secret")


def test_ses_instruments_a_lui(tmp_path, monkeypatch):
    """(30/10, Ahmed : « ses propres modules ») un instrument décrit dans atelier/tricordeur/instruments.json se demande comme
    les autres ; la demande dit à quel module (son Tricordeur) le téléphone la donne."""
    monkeypatch.setattr(sens, "JARVIS", tmp_path)
    t = tmp_path / "cwd" / "atelier" / "tricordeur"
    t.mkdir(parents=True)
    (t / "instruments.json").write_text(json.dumps({"instruments": [
        {"nom": "veilleur", "description": "son sommeil, la nuit", "defaut": 3600, "max": 99999},
        {"nom": "sismo", "description": "j'écrase le sien ?"}, {"nom": "../x"}, {"nom": "de_cosmique", "module": "rm -rf"}]}))
    d = sens.demander("veilleur", 0)
    assert d["module"] == "ch.foldlab.hakim" and d["secondes"] == 3600
    assert sens.demander("veilleur", 10 ** 9)["secondes"] == 86400, "une journée au plus"
    assert "module" not in sens.demander("sismo"), "les siens n'écrasent pas ceux du téléphone"
    for mauvais in ("../x", "de_cosmique"):
        try:
            sens.demander(mauvais)
            assert False, mauvais
        except sens.Refus:
            pass
    assert "veilleur" in sens.lister() and "Tes instruments à toi" in sens.lister()
