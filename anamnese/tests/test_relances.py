"""Les relances proposées par Hakim (28/10 ; Ahmed, 03:01 : « que tu puisses lancer toi-même le cockpit et le démon, sur
validation de moi » ; plan « Hakim touche à son code avec maman », tâche 8). Hakim propose ; Ahmed accepte d'un geste ;
le cockpit attend le calme et relance."""
import json

import pytest

import avis
import relances


@pytest.fixture(autouse=True)
def _lieux(tmp_path, monkeypatch):
    monkeypatch.setattr(relances, "DOSSIER", tmp_path / "relances")


def test_proposer_une_relance():
    r = relances.proposer("cockpit", "pour allumer ecouter_mon_coeur")
    assert r["quoi"] == "cockpit" and r["etat"] == "proposée"
    f = relances.DOSSIER / f"{r['id']}.json"
    assert json.loads(f.read_text())["raison"] == "pour allumer ecouter_mon_coeur"
    off = [json.loads(l) for l in avis.JOURNAL_OFF.read_text().splitlines()]
    assert off[-1]["type"] == "relance" and off[-1]["etape"] == "proposée" and off[-1]["quoi"] == "cockpit"


def test_une_seule_relance_en_attente_et_seulement_demon_ou_cockpit():
    relances.proposer("demon", "r")
    with pytest.raises(ValueError):
        relances.proposer("cockpit", "une autre")
    with pytest.raises(ValueError):
        relances.proposer("mac", "r")


def test_une_relance_proposee_depuis_plus_d_une_heure_ne_bloque_plus(monkeypatch):
    import time
    with monkeypatch.context() as mp:
        mp.setattr(time, "time", lambda: 1000.0)
        relances.proposer("demon", "vieille")
    assert relances.proposer("cockpit", "neuve")["quoi"] == "cockpit"


def test_l_outil_de_hakim():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
    import mcp_terminal
    assert "proposée à Ahmed" in mcp_terminal.proposer_relance("cockpit", "pour allumer le cœur")
    assert mcp_terminal.proposer_relance("demon", "encore").startswith("Refusé")
