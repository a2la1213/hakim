import dream_ablation as A

FULL = {("qwen", "brain_on"): 0.8, ("qwen", "brain_off"): 0.75,
        ("sonnet", "brain_on"): 0.72, ("sonnet", "brain_off"): 0.7}

def test_insufficient_below_min_nights():
    label, _ = A.ablation_verdict(5, FULL, 0.01, {"qwen": 0.5, "sonnet": 0.5})
    assert label == "INSUFFISANT"

def test_prouve_when_all_gates_pass():
    label, _ = A.ablation_verdict(12, FULL, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "PROUVÉ"

def test_non_soutenu_when_seedfollow_fails():
    bad = dict(FULL); bad[("sonnet", "brain_off")] = 0.2      # sonnet ne suit pas ses graines
    label, _ = A.ablation_verdict(12, bad, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_non_soutenu_when_parity_fails():
    bad = dict(FULL); bad[("qwen", "brain_on")] = 0.95; bad[("sonnet", "brain_on")] = 0.62  # écart 0.33 > 0.20
    label, _ = A.ablation_verdict(12, bad, 0.01, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_non_soutenu_when_perm_not_significant():
    label, _ = A.ablation_verdict(12, FULL, 0.20, {"qwen": 0.4, "sonnet": 0.35})
    assert label == "NON SOUTENU"

def test_plausible_when_one_model_leaks():
    # A passe, mais sonnet ne s'effondre pas (persona contribue)
    label, _ = A.ablation_verdict(12, FULL, 0.01, {"qwen": 0.4, "sonnet": 0.1})
    assert label == "PLAUSIBLE++"
