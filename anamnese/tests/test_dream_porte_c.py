# tests/test_dream_porte_c.py
import dream_ablation as A

RET_FULL = {("qwen","brain_on"): 0.5, ("qwen","brain_off_free"): 0.1,
            ("sonnet","brain_on"): 0.45, ("sonnet","brain_off_free"): 0.1}
CONV = {"brain_on": 0.9, "brain_off_free": 0.6}

def test_porte_c_passes_when_collapse_and_convdrop():
    ok, _ = A.porte_c(RET_FULL, CONV)
    assert ok is True                                    # drop 0.4/0.35 ≥0.30 ; conv 0.9-0.6=0.3 ≥0.20

def test_porte_c_fails_when_anamnese_persists():
    ret = dict(RET_FULL); ret[("sonnet","brain_off_free")] = 0.4   # drop 0.05 < 0.30
    ok, _ = A.porte_c(ret, CONV)
    assert ok is False

def test_porte_c_fails_when_convergence_holds():
    conv = {"brain_on": 0.9, "brain_off_free": 0.8}      # drop 0.1 < 0.20
    ok, _ = A.porte_c(RET_FULL, conv)
    assert ok is False

def test_porte_c_incomplete_cell_is_false():
    ret = {("qwen","brain_on"): 0.5, ("qwen","brain_off_free"): 0.1}   # sonnet manquant
    ok, _ = A.porte_c(ret, CONV)
    assert ok is False

def test_combined_verdict():
    assert A.combined_verdict("PROUVÉ", True) == "PROUVÉ"
    assert A.combined_verdict("PROUVÉ", False) == "PLAUSIBLE++"
    assert A.combined_verdict("NON SOUTENU", True) == "NON SOUTENU"
    assert A.combined_verdict("INSUFFISANT", False) == "INSUFFISANT"
