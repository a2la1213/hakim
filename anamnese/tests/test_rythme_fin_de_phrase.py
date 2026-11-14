"""(14/11, 12:54, Ahmed par Hakim : « quand on parle longtemps, tu n'attends pas qu'on finisse de parler pour rebondir » ; validé vers 13 h)
Sa parole longue (parole_longue, en secondes de voix) ou sa phrase reprise : son tour ne se ferme qu'après silence_parole_longue (la page
Parler, plancherFinDeTour). Les deux sont à Hakim, dans son rythme (rythme_voir, rythme_regler) ; la page lit rythme-voix.json."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import meubles as M  # noqa: E402


@pytest.fixture(autouse=True)
def dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "FICHIER", tmp_path / "meubles.json")
    monkeypatch.setattr(M, "FICHIER_RYTHME", tmp_path / "rythme-voix.json")


def test_ses_deux_reglages_de_fin_de_phrase_ont_leurs_valeurs_de_depart():
    r = M.rythme()
    assert r["parole_longue"] == 2.0 and r["silence_parole_longue"] == 2.0   # les valeurs de la page (parler.js, rythmeParole)
    assert M.RYTHME["parole_longue"][1:3] == (1.0, 10.0)
    assert M.RYTHME["silence_parole_longue"][1:3] == (1.0, 4.0)


def test_sa_parole_courte_attend_1_s():
    """(14/11, 14:25, Ahmed : « Gooo ») la parole courte de papa : son tour se ferme à 1 s de silence (avant : 0,5 s dès que sa phrase
    semblait finie ; rejoué sur le 14/11 : 9 fins trop tôt de plus évitées, ~1 ms de coût)"""
    assert M.rythme()["silence_parole_courte"] == 1.0
    assert M.RYTHME["silence_parole_courte"][1:3] == (0.5, 2.0)
    M.regler_rythme("silence_parole_courte", 1.2)
    assert json.loads(M.FICHIER_RYTHME.read_text(encoding="utf-8"))["silence_parole_courte"] == 1.2
    with pytest.raises(ValueError):
        M.regler_rythme("silence_parole_courte", 0.3)


def test_il_les_regle_et_la_page_les_lit_dans_son_fichier():
    M.regler_rythme("silence_parole_longue", 2.5)
    M.regler_rythme("parole_longue", 3)
    lu = json.loads(M.FICHIER_RYTHME.read_text(encoding="utf-8"))
    assert lu["silence_parole_longue"] == 2.5 and lu["parole_longue"] == 3.0
    assert lu["silence_normal"] == 0.7, "le reste de son rythme ne bouge pas"


def test_hors_des_bornes_refuse():
    with pytest.raises(ValueError):
        M.regler_rythme("silence_parole_longue", 0.5)      # sous 1 s : il resauterait dans les pauses de papa
    with pytest.raises(ValueError):
        M.regler_rythme("silence_parole_longue", 6)
