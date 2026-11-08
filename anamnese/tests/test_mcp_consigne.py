"""Expérience 1 du banc (pré-enregistrée le 2026-10-15) : la consigne de réponse vit dans la
DESCRIPTION de memory_recall — seul canal vu par le modèle en --restricted comme en session réelle
(les instructions de serveur MCP ne passent pas, vérifié par une sonde).

Prédiction écrite avant le code : échoue (la description ne contient pas la consigne)."""

import memory
import migrations
import rubrics


def test_memory_recall_porte_la_consigne_de_reponse(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    description = mcp_server.mcp._tool_manager.get_tool("memory_recall").description
    for attendu in ("rien de plus", "n'est pas en mémoire", "brièvement", "daté"):
        assert attendu in description, attendu
    mem.db.close()
