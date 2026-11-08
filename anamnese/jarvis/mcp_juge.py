"""Le terminal du juge de nuit (27/10 ; idée d'Ahmed, « la nuit porte conseil, chez les IA encore plus », relayée par
Hakim ; anamnese/juge_nuit.py). UN seul outil, executer, sous le bac à sable de Hakim (jarvis/terminal.py), mais le juge
LIT tout l'atelier et n'ÉCRIT que dans son dossier à lui (atelier/juge-nuit/<nuit>) : ni réseau, ni téléphone, ni tâche
de fond, ni agent, ni chantier. Le dossier vient de JUGE_DOSSIER, qui doit être sous atelier/juge-nuit."""
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mcp.server.fastmcp import FastMCP  # noqa: E402

import terminal  # noqa: E402

mcp = FastMCP("juge")
DELAI_MAX_S = 600


def dossier():
    racine = (terminal.ATELIER / "juge-nuit").resolve()
    d = Path(os.environ.get("JUGE_DOSSIER", "")).resolve()
    if racine not in d.parents:
        raise ValueError("le dossier du juge doit être sous atelier/juge-nuit")
    d.mkdir(parents=True, exist_ok=True)
    return d


@mcp.tool()
def executer(commande: str, delai_s: int = 120) -> str:
    """Exécute une commande zsh sous bac à sable. Tu LIS tout l'atelier de Hakim (/Users/admin/AIOS/jarvis/cwd/atelier),
    tu n'ÉCRIS que dans ton dossier (le dossier courant). Pour refaire un calcul : copie le script et ses petits fichiers
    d'entrée ici, puis lance la copie. Pas de réseau. Python (numpy, scipy, sympy, mlx) disponible. delai_s : 600 au plus."""
    try:
        return terminal.executer(commande, min(max(1, int(delai_s or 120)), DELAI_MAX_S), atelier=dossier(),
                                 lire_aussi=[terminal.ATELIER], reseau=False, telephone=False)
    except Exception as e:
        return f"Exécution impossible : {type(e).__name__}: {e}"[:400]


if __name__ == "__main__":
    mcp.run()
