# tests/test_synthesis_pure.py
import synthesis as S

def test_cos_and_grounding():
    a = [1.0, 0.0]; b = [0.0, 1.0]; mid = [1.0, 1.0]
    assert abs(S._cos(a, a) - 1.0) < 1e-9
    assert abs(S._cos(a, b)) < 1e-9
    assert S.grounding_ok(mid, a, b, floor=0.30) is True     # relié aux 2
    assert S.grounding_ok(a, a, b, floor=0.30) is False      # orthogonal à b

def test_novelty():
    v = [1.0, 0.0]
    assert S.novelty(v, []) == 1.0
    assert S.novelty(v, [[1.0, 0.0]]) == 0.0                 # identique = pas neuf
    assert S.novelty(v, [[0.0, 1.0]]) == 1.0                 # orthogonal = neuf

def test_parse_hypothesis():
    assert S.parse_hypothesis("NONE") is None
    assert S.parse_hypothesis("  none.  ") is None
    assert S.parse_hypothesis("") is None
    assert S.parse_hypothesis("Peut-être que X résout Y.") == "Peut-être que X résout Y."
    assert S.parse_hypothesis("<think>bla</think>Idée réelle.") == "Idée réelle."

def test_parse_verdict():
    assert S.parse_verdict("RÉFUTÉ : connexion forcée") == "REFUTE"
    assert S.parse_verdict("VALIDE, vrai pont") == "VALIDE"
    # prompt verdict-FIRST : le PREMIER token décide, même si la raison contient l'autre mot
    assert S.parse_verdict("RÉFUTÉ : connexion non valide") == "REFUTE"    # vote-kill préservé malgré 'valide' dans la raison
    assert S.parse_verdict("VALIDE, rien à réfuter ici") == "VALIDE"       # le premier token gagne
    assert S.parse_verdict("bla") is None

def test_majority_kill():
    assert S.majority_kill(["REFUTE","REFUTE","REFUTE","VALIDE","VALIDE"], 3) is True
    assert S.majority_kill(["REFUTE","REFUTE","VALIDE","VALIDE","VALIDE"], 3) is False

def test_fertility_score():
    central = S.fertility_score(0.475, True, 0.0)
    edge = S.fertility_score(0.60, True, 0.0)
    assert central > edge                                    # pic au centre de la bande
    assert S.fertility_score(0.475, True, 0.0) > S.fertility_score(0.475, False, 0.0)   # inter-rubriques
    assert S.fertility_score(0.475, True, 0.0) > S.fertility_score(0.475, True, 0.5)    # déjà co-activé pénalisé
