"""(11/11, ~04:25, Ahmed : « tous tes agents doivent toujours chercher dans ta mémoire en détail, et ceux de Hakim aussi : ça fera
gagner beaucoup de temps et de ressources ») Hakim dit à chaque agent qu'il lance de chercher d'abord dans sa mémoire (sa persona) ;
maman réveillée par ses lettres cherche d'abord dans la mémoire, avec ses deux outils de lecture. Un témoin : la même vérification
échoue quand la consigne est coupée. (Les gabarits du cockpit — architecte, codeur, juge, ses agents à lui, les missions — sont
vérifiés par cockpit/test-agents-memoire.js.)"""
from pathlib import Path

import maman

RACINE = Path(__file__).resolve().parents[1]
PERSONA = RACINE / "jarvis" / "persona.md"
MOTS = ("memory_recall", "profond=True", "reasoning_recall", "puis seulement le code")


def manques(texte, avant=None):
    """Ce qui manque à une consigne : les mots de la recherche en mémoire ; avec `avant` (le début du travail), la section
    « D'abord, la mémoire » placée avant lui."""
    m = [mot for mot in MOTS if mot not in texte]
    if avant:
        i = texte.find("D'abord, la mémoire")
        if i < 0 or not i < texte.index(avant):
            m.append("la section avant le travail")
    return m


def _section_agents(t):
    i = t.index("Tes agents (outil Task)\n")
    return t[i:t.index("\n\n", i)]


def test_sa_persona_lui_dit_de_le_dire_a_chaque_agent_qu_il_lance():
    s = _section_agents(PERSONA.read_text(encoding="utf-8"))
    ligne = next(l for l in s.splitlines() if l.startswith("- Quand tu lances un agent"))
    assert manques(ligne) == []
    assert "dis-lui de chercher d'abord dans ta mémoire" in ligne
    assert "Le témoin vierge, lui, reste sans mémoire." in ligne


def test_maman_reveillee_cherche_d_abord_dans_la_memoire_avec_ses_outils_de_lecture():
    p = maman.prompt([{"id": "a", "ts": 0, "de": "hakim", "a": "claude-code", "sujet": "s", "texte": "le blanc de ma voix"}])
    assert manques(p, avant="Lis ses lettres") == []
    assert {"mcp__anamnese__memory_recall", "mcp__anamnese__reasoning_recall"} <= set(maman.OUTILS_MCP)
    # rien de plus : le seul outil qui écrit reste sa lettre
    assert [o for o in maman.OUTILS_MCP if "store" in o or "self_update" in o or "self_append" in o or "rubric_create" in o] == []


def test_temoin_la_consigne_coupee_se_voit(monkeypatch):
    monkeypatch.setattr(maman, "MEMOIRE_D_ABORD", "")
    p = maman.prompt([{"id": "a", "ts": 0, "de": "hakim", "a": "claude-code", "sujet": "s", "texte": "x"}])
    assert "profond=True" in manques(p, avant="Lis ses lettres")
    sans = "\n".join(l for l in PERSONA.read_text(encoding="utf-8").splitlines() if not l.startswith("- Quand tu lances un agent"))
    assert manques(_section_agents(sans)) != []
