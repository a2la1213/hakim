"""Les gardes restent appelées (28/10 ; plan « Hakim touche à son code avec maman », tâche 9). Le code des gardes est fermé,
mais certains fichiers OUVERTS les appellent : une modification qui retirerait l'appel contournerait la garde sans
toucher à son code. Ces tests (FERMÉS : ils ne suivent aucun module ouvert) échouent alors, et une promotion dont les tests
échouent ne peut pas s'appliquer. Ce sont des fils tendus sur le texte du code ; la relecture de maman reste la barrière.
Chaque test a été vu échouer en retirant l'appel (témoin), puis rétabli."""
import re
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]


def _corps(fichier, fonction):
    """Le corps d'une fonction de premier niveau (jusqu'à la suivante)."""
    t = (RACINE / fichier).read_text(encoding="utf-8")
    m = re.search(rf"^(?:async )?def {fonction}\(", t, re.M)
    assert m, f"{fichier} : la fonction {fonction} a disparu"
    fin = re.search(r"^(?:@|def |async def |class |# FERME-)", t[m.end():], re.M)
    return t[m.start(): m.end() + (fin.start() if fin else len(t))]


GARDES = [
    # (fichier, fonction, appel attendu, ce que la garde protège)
    ("jarvis/recettes.py", None, "fichiers.lire_sans_lien(", "lire une recette sans suivre un lien posé dans l'atelier"),
    ("jarvis/recettes.py", None, "fichiers.ecrire_sans_lien(", "écrire une recette sans suivre un lien"),
    ("occupations.py", "texte_document", ".copie_privee(", "lire un document d'Ahmed par une copie privée vérifiée"),
    ("occupations.py", "_texte_document", ".masquer(", "masquer les secrets d'un document"),
    ("rappel.py", None, "provenance.externes(", "marquer « externe » les souvenirs venus de tiers dans le rappel"),
    ("mcp_server.py", "fichiers_par_sens", "enveloppe.enveloppe(", "envelopper les extraits des fichiers d'Ahmed"),
    ("mcp_server.py", "memory_lire", "provenance.externes(", "marquer les souvenirs externes à la lecture"),
    ("mcp_server.py", "memory_recall", "provenance.externes(", "marquer les souvenirs externes au rappel"),
    ("mcp_server.py", "memory_recent", "provenance.externes(", "marquer les souvenirs externes récents"),
]


@pytest.mark.parametrize("fichier,fonction,appel,pourquoi", GARDES)
def test_la_garde_est_toujours_appelee(fichier, fonction, appel, pourquoi):
    texte = _corps(fichier, fonction) if fonction else (RACINE / fichier).read_text(encoding="utf-8")
    assert appel in texte, f"{fichier}{':' + fonction if fonction else ''} n'appelle plus {appel} ({pourquoi})"


def test_le_temoin_echoue_quand_on_retire_un_appel(tmp_path, monkeypatch):
    """Le fil tendu sert : une copie de rappel.py sans son appel à la garde est vue."""
    global RACINE
    copie = tmp_path / "rappel.py"
    copie.write_text((RACINE / "rappel.py").read_text(encoding="utf-8").replace("provenance.externes(", "list("), encoding="utf-8")
    monkeypatch.setattr(__import__(__name__), "RACINE", tmp_path)
    with pytest.raises(AssertionError):
        test_la_garde_est_toujours_appelee("rappel.py", None, "provenance.externes(", "témoin")
