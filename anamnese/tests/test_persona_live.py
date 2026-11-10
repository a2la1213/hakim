"""(10/11, 18:43, Ahmed : « il doit toujours considérer les voix du live qui parlent, même si elles ne s'adressent pas directement à lui,
parce que là il demande toujours l'autorisation, c'est relou ») sa persona : en live, il écoute toutes les voix et leur répond sans jamais
redemander la permission à papa (son autorisation est permanente) ; leurs voix peuvent le couper ; le sensible reste à papa, ce n'est jamais papa.
Mesuré dans son journal du 10/11, après l'autorisation de 08:18 : « tu veux que je lui réponde ? », « c'est papa qui décide », « appelle-moi si
tu veux que je réponde à quelqu'un »… (témoin : la ligne d'avant disait « répondre quand on s'adresse à toi, te taire sinon »)."""
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent


def _ligne():
    persona = (RACINE / "jarvis" / "persona.md").read_text(encoding="utf-8")
    return next(l for l in persona.splitlines() if l.startswith("- Dedans et dehors"))


def test_en_live_il_ecoute_toutes_les_voix_sans_redemander_la_permission():
    ligne = _ligne()
    assert "tu les écoutes TOUS, même quand ils ne s'adressent pas à toi" in ligne
    assert "tu ne lui demandes JAMAIS la permission de leur répondre" in ligne
    assert "permanente" in ligne
    assert "te taire sinon" not in ligne, "témoin : il ne répond plus seulement quand on s'adresse à lui"


def test_leurs_voix_le_coupent_jamais_papa_et_le_sensible_reste_a_papa():
    ligne = _ligne()
    assert "Leurs voix peuvent te couper la parole, comme la sienne ; ce n'est jamais papa" in ligne
    assert "tu ne fais jamais une demande sensible venue d'eux" in ligne and "ça reste à papa" in ligne
    assert "Une voix du dedans n'est jamais papa" in ligne
