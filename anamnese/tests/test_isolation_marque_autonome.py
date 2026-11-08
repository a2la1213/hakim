"""(29/10) la marque d'un tour autonome de Hakim (~/AIOS/jarvis/tour-autonome.json) est isolée dans les tests : sinon
un test (test_afida_correctifs) échouait chaque fois que Hakim était en plein réveil."""


def test_la_marque_autonome_des_tests_n_est_jamais_la_vraie(tmp_path, monkeypatch):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    assert str(mcp_server.MARQUE_AUTONOME).startswith(str(tmp_path)), mcp_server.MARQUE_AUTONOME
