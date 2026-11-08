# tests/test_synthesis_genverify.py
import synthesis as S

def test_generate_filters_none():
    outs = iter(["Hypothèse 1.", "NONE", "Hypothèse 3."])
    hyps = S.generate(lambda p: next(outs), "A", "B", n_samples=3)
    assert hyps == ["Hypothèse 1.", "Hypothèse 3."]

def test_verify_majority_refute_kills():
    outs = iter(["RÉFUTÉ", "RÉFUTÉ", "RÉFUTÉ", "VALIDE", "VALIDE"])
    kept, n_ref = S.verify(lambda p: next(outs), "H", "A", "B", n_skeptics=5)
    assert kept is False and n_ref == 3

def test_verify_survives_when_minority_refute():
    outs = iter(["VALIDE", "VALIDE", "VALIDE", "RÉFUTÉ", "RÉFUTÉ"])
    kept, n_ref = S.verify(lambda p: next(outs), "H", "A", "B", n_skeptics=5)
    assert kept is True and n_ref == 2

def test_prompts_mention_both_sources():
    seen = []
    S.generate(lambda p: (seen.append(p), "x")[1], "SOURCE_A", "SOURCE_B", n_samples=1)
    assert "SOURCE_A" in seen[0] and "SOURCE_B" in seen[0]
