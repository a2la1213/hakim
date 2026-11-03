"""(03/11, 13:30, papa via Hakim : « qu'il puisse CRÉER ses propres éléments pour meubler les blancs (un hmm, un euh, un souffle,
une respiration, un petit son) et les PARAMÉTRER (durée, volume, quand ils partent, quel état les déclenche) ; reliés à son
conscient (il les choisit) ET à son subconscient (qui les déclenche seul pendant un trou, selon son état) »)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import meubles as M  # noqa: E402


@pytest.fixture(autouse=True)
def dossier(tmp_path, monkeypatch):
    monkeypatch.setattr(M, "FICHIER", tmp_path / "meubles.json")


def test_ses_meubles_de_depart_sont_la():
    noms = [m["nom"] for m in M.lister()]
    assert {"euh", "hum", "alors", "voyons voir"} <= set(noms)


def test_ses_meubles_de_depart_sont_tous_de_sa_voix():
    """(03/11, 14:12, Ahmed : « t'as pas enlevé le trigger, le petit signal juste avant qu'il parle » ; « il meuble avec sa voix »)
    le souffle et la respiration de départ sonnaient comme un signal : ceux de départ sont tous des paroles."""
    assert all(m.get("texte") for m in M.lister())


def test_il_cree_un_meuble_parle_et_le_regle():
    m = M.creer("mmh", texte="Mmh…", volume=0.8, quand="entre", etats=["tendresse", "hésitation"])
    assert m["texte"] == "Mmh…" and m["quand"] == "entre" and m["etats"] == ["tendresse", "hésitation"]
    M.regler("mmh", volume=0.5, duree_ms=700)
    x = next(m for m in M.lister() if m["nom"] == "mmh")
    assert x["volume"] == 0.5 and x["duree_ms"] == 700
    assert json.loads(M.FICHIER.read_text())                       # gardé sur le disque, pour la page


def test_un_de_ses_sons_ou_un_souffle_peut_etre_un_meuble():
    assert M.creer("petit rire", son="e12", duree_ms=1200)["son"] == "e12"
    assert M.creer("long souffle", genre="souffle", duree_ms=1500, volume=0.4)["genre"] == "souffle"


def test_il_peut_eteindre_ou_oublier_un_meuble_meme_de_depart():
    M.regler("hum", actif=False)
    assert not next(m for m in M.lister() if m["nom"] == "hum")["actif"]
    M.oublier("euh")
    assert "euh" not in [m["nom"] for m in M.lister()]
    M.creer("tss", texte="Tss,")
    M.oublier("tss")
    assert "tss" not in [m["nom"] for m in M.lister()]


@pytest.mark.parametrize("mauvais", [
    dict(nom="", texte="x"), dict(nom="a", texte="x", son="e1"), dict(nom="a"), dict(nom="a", son="12"),
    dict(nom="a", texte="x" * 41), dict(nom="a", genre="cri"), dict(nom="a", texte="x", volume=3),
    dict(nom="a", texte="x", quand="toujours"), dict(nom="a", texte="x", duree_ms=50), dict(nom="a", texte="[[son: e1]]"),
])
def test_ce_qui_n_est_pas_un_meuble_est_refuse(mauvais):
    with pytest.raises(ValueError):
        M.creer(**mauvais)
