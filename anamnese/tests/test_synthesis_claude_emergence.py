# tests/test_synthesis_claude_emergence.py
import synthesis_claude as SC
import synthesis
import rubric_emergence


def test_run_claude_triggers_emergence_after_synthesis(monkeypatch):
    order = []
    monkeypatch.setattr(synthesis, "run", lambda *a, **k: order.append("run") or [10, 11])
    monkeypatch.setattr(rubric_emergence, "emerge",
                        lambda mem, chat: order.append("emerge") or ["projets/x/y"])
    ids = SC.run_claude(mem=object(), run_fn=lambda p: "x")
    assert ids == [10, 11]            # retour inchangé (insight_ids)
    assert order == ["run", "emerge"]  # émergence APRÈS la synthèse


def test_run_claude_emergence_is_best_effort(monkeypatch):
    monkeypatch.setattr(synthesis, "run", lambda *a, **k: [7])
    def boom(mem, chat):
        raise RuntimeError("emergence cassée")
    monkeypatch.setattr(rubric_emergence, "emerge", boom)
    assert SC.run_claude(mem=object(), run_fn=lambda p: "x") == [7]   # ne lève pas
