"""Serveur MCP « calcul » de Jarvis : exécuter du Python (numpy, scipy, sympy) dans un bac à sable
macOS, sans réseau, sans accès aux fichiers d'Ahmed, sans lancer d'autre programme (jarvis/calcul.py)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP  # noqa: E402

import groupes  # noqa: E402
import calcul  # noqa: E402

mcp = FastMCP("calcul")


@mcp.tool()
def executer_python(code: str, delai_s: int = 60) -> str:
    """Exécute du code Python pour CALCULER : arithmétique exacte, statistiques, algèbre (sympy),
    matrices et numérique (numpy, scipy), dates, conversions, simulations. Utilise-le pour tout
    calcul non trivial au lieu de calculer de tête, et affiche les résultats avec print().
    Bac à sable : pas de réseau, pas d'accès aux fichiers d'Ahmed, pas de shell ni d'autre
    programme ; les fichiers écrits dans le dossier courant sont rendus (lisibles avec Read).
    delai_s : temps de calcul maximal (1 à 300 s)."""
    try:
        return calcul.executer(code, delai_s)
    except Exception as e:
        return f"Exécution impossible : {type(e).__name__}: {e}"[:400]


if __name__ == "__main__":
    groupes.installer_arret()            # le cockpit coupe Jarvis : ses commandes en cours meurent aussi
    mcp.run()
