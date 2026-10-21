"""Serveur MCP Anamnèse sur la base désignée par ANAMNESE_BANC_DB (une COPIE), en LECTURE SEULE.

- memory.Memory prend config.DB_PATH par défaut AU MOMENT de son import : le chemin est fixé
  avant tout autre import ;
- seuls les outils de rappel restent enregistrés (les autres, dont memory_store, ne sont même
  pas visibles du modèle) ;
- les effets du rappel (reconsolidation, co-activation, mémoire de travail) sont neutralisés :
  sinon chaque question modifierait la copie partagée et influencerait les suivantes."""
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
OUTILS = ("memory_recall", "reasoning_recall", "facet_search", "self_get")


def preparer():
    if str(RACINE) not in sys.path:
        sys.path.insert(0, str(RACINE))
    import config
    config.DB_PATH = Path(os.environ["ANAMNESE_BANC_DB"])


def _rien(*_a, **_k):
    return None


def serveur_lecture_seule():
    preparer()
    import memory
    for nom in ("_reconsolidate", "log_coactivation", "wm_touch"):
        setattr(memory.Memory, nom, _rien)
    import mcp_server
    outils = mcp_server.mcp._tool_manager._tools
    for nom in list(outils):
        if nom not in OUTILS:
            del outils[nom]
    return mcp_server.mcp


if __name__ == "__main__":
    serveur_lecture_seule().run()
