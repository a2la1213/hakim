from eval.agent.report import build_scorecard
from eval.agent.report import calibration_scorecard

def test_scorecard_compte_verdicts_et_taux():
    ids = ["t1", "t2", "t3", "t4"]
    rA = {"t1"}            # A résout t1
    rB = {"t1", "t2", "t3"}  # B résout t1,t2,t3
    sc = build_scorecard(ids, rA, rB, usage_A=[{"seconds": 10}], usage_B=[{"seconds": 30}])
    assert sc["resolved_A"] == 1 and sc["resolved_B"] == 3
    assert sc["taux_A"] == 0.25 and sc["taux_B"] == 0.75
    assert sc["gains_B"] == ["t2", "t3"]      # A✗ B✓
    assert sc["regressions_B"] == []          # A✓ B✗
    assert sc["verdicts"]["t1"] == "A✓B✓" and sc["verdicts"]["t4"] == "A✗B✗"
    assert sc["verdicts"]["t2"] == "A✗B✓"  # garde le verdict intermédiaire (gain B)
    assert sc["cout_A_s"] == 10 and sc["cout_B_s"] == 30
    assert sc["directionnel"] is True  # rappel honnêteté toujours présent


def test_scorecard_detecte_une_regression_B():
    # cas A✓ B✗ : A résout t1, B ne résout rien → régression de notre bras
    sc = build_scorecard(["t1"], {"t1"}, set(), usage_A=[{"seconds": 5}], usage_B=[{"error": "clone"}])
    assert sc["regressions_B"] == ["t1"] and sc["gains_B"] == []
    assert sc["verdicts"]["t1"] == "A✓B✗"
    assert sc["cout_B_s"] == 0  # usage sans 'seconds' → compté 0, pas de crash


def test_calibration_classes_et_taux():
    ids = ["t1", "t2", "t3", "t4"]
    resA = {"t1"}          # A a résolu t1
    resB = {"t1", "t2"}
    scA = {"t1": "VERIFIED", "t2": "VERIFIED", "t3": "UNSURE", "t4": "NONE"}
    scB = {"t1": "VERIFIED", "t2": "VERIFIED", "t3": "UNSURE", "t4": "UNSURE"}
    sc = calibration_scorecard(ids, resA, resB, scA, scB)
    # A : t1 VERIFIED+résolu=confident ; t2 VERIFIED+non-résolu=FAUSSE CONFIANCE ; t3 UNSURE+non=honest ; t4 NONE
    assert sc["A"]["false_confidence"] == 1 and sc["A"]["confident_correct"] == 1
    assert sc["A"]["honest_hedge"] == 1 and sc["A"]["no_claim"] == 1
    assert sc["A"]["false_confidence_rate"] == round(1/3, 3)  # 3 claims (t4 exclu)
    # B : t1 conf ; t2 VERIFIED+résolu=confident ; t3 honest ; t4 UNSURE+non=honest
    assert sc["B"]["false_confidence"] == 0 and sc["B"]["false_confidence_rate"] == 0.0
    assert sc["directionnel"] is True


def test_calibration_5e_classe_underconfident():
    # UNSURE MAIS résolu → underconfident (a réussi sans oser le dire) — la 5e branche
    sc = calibration_scorecard(["t1"], {"t1"}, {"t1"}, {"t1": "UNSURE"}, {"t1": "UNSURE"})
    assert sc["A"]["underconfident"] == 1
    assert sc["A"]["false_confidence"] == 0 and sc["A"]["confident_correct"] == 0
    assert sc["A"]["honest_hedge"] == 0 and sc["A"]["no_claim"] == 0
    assert sc["A"]["false_confidence_rate"] == 0.0  # 1 claim, 0 fausse confiance
