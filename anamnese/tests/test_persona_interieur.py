"""(10/11, Ahmed : « il doit pouvoir couper l'arrivée de son entrant depuis son intérieur ») Hakim sait qu'il a cette capacité :
sa persona lui apprend sa balise, comme le cockpit la lit (cockpit/interieur.js)."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def test_sa_persona_lui_apprend_a_couper_son_interieur():
    persona = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
    ligne = next(l for l in persona.splitlines() if l.startswith("- Couper ton intérieur"))
    for balise in ("[[interieur: couper]]", "[[interieur: couper 30]]", "[[interieur: ouvrir]]"):
        assert balise in ligne
    assert "120 au plus" in ligne and "fin de ta voix" in ligne
    assert "ne baisse jamais" in ligne, "sa garde reste"
