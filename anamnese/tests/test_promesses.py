"""L'horloge à promesses de Hakim (promesses.py, accord d'Ahmed le 2026-10-22)."""
from datetime import datetime

import pytest

import promesses as P

MIDI = datetime(2026, 10, 22, 12, 0).timestamp()


def test_les_formes_de_l_heure():
    assert P.quand_vers_ts("18:30", MIDI) == datetime(2026, 10, 22, 18, 30).timestamp()
    assert P.quand_vers_ts("18h30", MIDI) == datetime(2026, 10, 22, 18, 30).timestamp()
    assert P.quand_vers_ts("9 h", MIDI) == datetime(2026, 10, 23, 9, 0).timestamp()          # passée : demain
    assert P.quand_vers_ts("+45 min", MIDI) == MIDI + 2700
    assert P.quand_vers_ts("+2 h", MIDI) == MIDI + 7200
    assert P.quand_vers_ts("2026-10-25 10:00", MIDI) == datetime(2026, 10, 25, 10, 0).timestamp()
    with pytest.raises(P.Refus):
        P.quand_vers_ts("demain matin", MIDI)


def test_poser_lister_effacer(tmp_path):
    f = tmp_path / "promesses.json"
    p = P.poser("18:30", "  relancer le calcul du sable  ", MIDI, f)
    assert p["etat"] == "attente" and p["raison"] == "relancer le calcul du sable" and p["id"].startswith("P-")
    assert P.lire(f)["promesses"][0]["id"] == p["id"]
    assert P.effacer(p["id"], f) is True and P.effacer(p["id"], f) is False
    assert P.lire(f)["promesses"][0]["etat"] == "effacee"


def test_jamais_la_nuit_jamais_trop_loin_jamais_sans_raison(tmp_path):
    f = tmp_path / "promesses.json"
    for quand, raison in (("23:30", "x"), ("6:00", "x"), ("2026-12-31 10:00", "x"), ("18:00", "  "), ("+0 min", "x")):
        with pytest.raises(P.Refus):
            P.poser(quand, raison, MIDI, f)
    assert P.lire(f)["promesses"] == []


def test_vingt_en_attente_au_plus(tmp_path):
    f = tmp_path / "promesses.json"
    for i in range(P.EN_ATTENTE_MAX):
        P.poser(f"+{i + 1} min", f"n°{i}", MIDI, f)
    with pytest.raises(P.Refus):
        P.poser("+50 min", "une de trop", MIDI, f)


def test_l_etat_du_cockpit_l_emporte(tmp_path):
    """Le cockpit écrit son propre fichier (tenue, manquée, effacée par Ahmed) : jamais celui de Hakim."""
    import json
    f = tmp_path / "promesses.json"
    p = P.poser("18:30", "vérifier le calcul", MIDI, f)
    (tmp_path / "promesses-etats.json").write_text(json.dumps({p["id"]: "tenue"}))
    assert [x["etat"] for x in P.toutes(f)] == ["tenue"]
    assert P.effacer(p["id"], f) is False                       # déjà tenue : rien à effacer
