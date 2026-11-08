# tests/test_synthesis_claude.py
import synthesis_claude as SC

def test_run_claude_uses_claude_backend(monkeypatch):
    seen = {}
    def fake_run(mem, chat_fn, backend, n_pairs, **k):
        seen.update(backend=backend, n_pairs=n_pairs, kw=k); return [1, 2]
    monkeypatch.setattr(SC.synthesis, "run", fake_run)
    out = SC.run_claude(mem=object(), run_fn=lambda p: "x")
    assert out == [1, 2]
    assert seen["backend"] == "claude"
    assert seen["n_pairs"] == SC.config.SYNTH_CLAUDE_TOPN
    assert seen["kw"].get("n_samples") == 1 and seen["kw"].get("n_skeptics") == 2

def test_claude_chat_builds_command(monkeypatch):
    captured = {}
    class R: returncode = 0; stdout = "réponse"
    monkeypatch.setattr(SC.subprocess, "run", lambda cmd, **k: captured.update(cmd=cmd) or R())
    assert SC.claude_chat("mon prompt") == "réponse"
    assert "claude" in captured["cmd"][0] and "--model" in captured["cmd"] and "sonnet" in captured["cmd"]
