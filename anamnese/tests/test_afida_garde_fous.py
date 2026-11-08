"""Al-Afida n'autorise jamais rien (28/10, garde-fou de Hakim, non contesté par Ahmed : « elle colore et aide à reconnaître,
elle n'autorise jamais rien »). Un fil tendu sur le texte du code : aucun module de garde ne la nomme. Le témoin montre que
le fil casse si quelqu'un l'y ajoute. Côté cockpit : test-afida.js (passkey.js, code.js, blocs fermés de server.js)."""
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
# (relecture du 28/10) aussi ce qui fait sortir quelque chose (missions, courrier) et le réveil de maman
GARDES = sorted(str(p.relative_to(RACINE)) for p in (RACINE / "jarvis").glob("*.py")) + ["avis.py", "relances.py", "missions.py",
                                                                                        "courrier.py", "maman.py"]


def _nomme_afida(texte):
    return "afida" in texte.casefold()


@pytest.mark.parametrize("fichier", GARDES)
def test_aucune_garde_ne_lit_afida(fichier):
    assert not _nomme_afida((RACINE / fichier).read_text(encoding="utf-8")), f"{fichier} nomme Al-Afida : une garde ne doit jamais la lire"


def test_la_lecture_seule_ne_lit_pas_afida():
    src = (RACINE / "mcp_server.py").read_text(encoding="utf-8")
    i = src.index("def lecture_seule(")
    assert not _nomme_afida(src[i: src.index("\n\n\n", i)])


def test_temoin_le_fil_casse_si_on_l_ajoute():
    texte = (RACINE / "avis.py").read_text(encoding="utf-8")
    assert not _nomme_afida(texte)
    assert _nomme_afida(texte + "\nimport afida  # une garde qui lirait la jauge\n")


def test_le_module_ne_touche_a_aucune_garde():
    src = (RACINE / "afida.py").read_text(encoding="utf-8")
    for garde in ("liste_ouverte", "avis", "relances", "passkey", "chantiers", "lecture_seule"):
        assert f"import {garde}" not in src, garde
