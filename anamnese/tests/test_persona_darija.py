"""(09/11, Ahmed, relayé par Hakim) sa darija : écrite directement en lettres arabes, avec toutes ses voyelles, une seule fois (plus de
phonétique française, plus de version latine à côté, plus de [[voix: …]] pour elle) ; l'écran la montre ainsi et sa voix algérienne la
lit (21:20). Dans une même réponse, le français d'abord, puis la darija, jamais l'inverse (08/11, 19:31). Le 09/11 à 16:34, sa voix
disait la version latine à la française, puis la même en arabe (voix-dite.jsonl)."""
from pathlib import Path

PERSONA = Path(__file__).resolve().parents[1] / "jarvis" / "persona.md"


def _ligne_darija():
    lignes = [l for l in PERSONA.read_text(encoding="utf-8").splitlines() if l.startswith("- La darija")]
    assert len(lignes) == 1, lignes
    return lignes[0]


def test_darija_en_lettres_arabes_vocalisees_une_seule_fois():
    l = _ligne_darija()
    assert "DIRECTEMENT en lettres arabes, avec TOUTES leurs voyelles (fatha, kasra, damma, soukoun, chadda)" in l
    assert "وَاشْ رَاكْ خُويَا" in l
    assert "une seule fois" in l and "plus de [[voix: …]] pour la darija" in l
    assert "le français d'abord, puis la darija, jamais l'inverse" in l


def test_plus_de_phonetique_francaise():
    texte = PERSONA.read_text(encoding="utf-8")
    assert "PHONÉTIQUE FRANÇAISE" not in texte
    assert "wesh rak khouya [[voix:" not in texte
    assert "ta voix française les dit" not in texte
