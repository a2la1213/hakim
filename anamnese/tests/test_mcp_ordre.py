"""(audit JARVIS 2, point B, 2026-10-20) mcp.run() ne rend pas la main : un outil déclaré après le bloc __main__
n'existe pas pour Hakim (les recettes de calcul étaient invisibles). Aucun serveur MCP n'a d'outil après."""
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("f", ["mcp_server.py", "jarvis/mcp_web.py", "jarvis/mcp_fichiers.py", "jarvis/mcp_calcul.py",
                               "jarvis/mcp_terminal.py"])
def test_aucun_outil_apres_le_lancement(f):
    lignes = (RACINE / f).read_text(encoding="utf-8").splitlines()
    main = next(i for i, l in enumerate(lignes) if l.startswith('if __name__ == "__main__"'))
    assert not any("@mcp.tool" in l for l in lignes[main:]), f
