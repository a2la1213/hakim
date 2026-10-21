"""Le vrai serveur MCP d'Anamnèse, mais sur une base JETABLE (EVAL_DB) : pour les évaluations qui font tourner un
vrai `claude -p` (consolidation de nuit) sans jamais toucher data/memory.db ni le journal d'événements réel."""
import os
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE))
DB = Path(os.environ["EVAL_DB"]).resolve()
if DB == (RACINE / "data" / "memory.db").resolve():
    sys.exit("EVAL_DB ne peut pas être la vraie mémoire")

import evenements  # noqa: E402
import memory  # noqa: E402

_Memory = memory.Memory
memory.Memory = lambda *a, **k: _Memory(db_path=DB)
evenements.FICHIER = DB.parent / "evenements.jsonl"

import mcp_server  # noqa: E402

mcp_server.DETAILS = DB.parent / "details"
mcp_server.mcp.run()
