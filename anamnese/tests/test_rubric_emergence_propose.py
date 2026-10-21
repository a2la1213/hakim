# tests/test_rubric_emergence_propose.py
import rubric_emergence as RE

def test_propose_path_returns_parsed_path():
    seen = {}
    def fake(prompt):
        seen["p"] = prompt
        return "projets/anamnese/mon-theme"
    p = RE.propose_path(fake, ["insight alpha", "insight beta"], {"projets", "projets/anamnese"})
    assert p == "projets/anamnese/mon-theme"
    assert "insight alpha" in seen["p"] and "projets/anamnese" in seen["p"]

def test_propose_path_none_when_model_says_none():
    assert RE.propose_path(lambda p: "NONE", ["x"], {"projets"}) is None

def test_propose_path_none_on_chat_error():
    def boom(p):
        raise RuntimeError("backend down")
    assert RE.propose_path(boom, ["x"], {"projets"}) is None
