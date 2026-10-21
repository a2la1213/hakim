# tests/test_rubric_emergence_pure.py
import config


def test_emerge_config_values():
    assert config.RUBRIC_EMERGE_MIN_INSIGHTS == 3
    assert config.RUBRIC_EMERGE_SIM == 0.50
    assert config.RUBRIC_EMERGE_REDUNDANCY_FLOOR == 0.60
    assert config.RUBRIC_EMERGE_ENABLED in (True, False)


import rubric_emergence as RE

def test_centroid_mean():
    assert RE._centroid([[2.0, 0.0], [0.0, 2.0]]) == [1.0, 1.0]
    assert RE._centroid([]) == []

def test_cluster_groups_tight_and_drops_below_min():
    items = [(1, [1, 0]), (2, [0.99, 0.01]), (3, [0.98, 0.02]), (4, [0, 1])]
    cl = RE._cluster(items, min_size=3, sim=0.9)
    assert len(cl) == 1 and set(cl[0]) == {1, 2, 3}   # 4 (axe y) exclu

def test_cluster_below_min_returns_empty():
    assert RE._cluster([(1, [1, 0]), (2, [0.99, 0.01])], min_size=3, sim=0.9) == []

def test_covered_true_when_near_existing():
    assert RE.covered([1, 0], [[0.95, 0.05]], floor=0.6) is True

def test_covered_false_when_far():
    assert RE.covered([1, 0], [[0, 1]], floor=0.6) is False

def test_covered_skips_empty_centroids():
    assert RE.covered([1, 0], [[], [0, 1]], floor=0.6) is False

def test_valid_path_accepts_new_child_of_existing_parent():
    assert RE.valid_path("projets/anamnese/nouveau", {"projets", "projets/anamnese"}) is True

def test_valid_path_rejects_existing_path():
    assert RE.valid_path("projets/anamnese", {"projets", "projets/anamnese"}) is False

def test_valid_path_rejects_new_root():
    assert RE.valid_path("nouveauroot", {"projets"}) is False

def test_valid_path_rejects_missing_parent():
    assert RE.valid_path("projets/absent/x", {"projets"}) is False

def test_valid_path_rejects_non_kebab():
    assert RE.valid_path("projets/Anamnese_X", {"projets"}) is False

def test_valid_path_rejects_too_deep():
    existing = {"a", "a/b", "a/b/c", "a/b/c/d"}
    assert RE.valid_path("a/b/c/d/e", existing) is False   # count('/')=4 > RUBRIC_MAX_DEPTH=3

def test_parse_path_extracts_kebab():
    assert RE.parse_path("projets/anamnese/mon-theme") == "projets/anamnese/mon-theme"

def test_parse_path_none_on_none_or_empty():
    assert RE.parse_path("NONE") is None
    assert RE.parse_path("") is None
    assert RE.parse_path(None) is None

def test_parse_path_strips_think_and_prose():
    assert RE.parse_path("<think>hmm</think>\nVoici: projets/anamnese/x") == "projets/anamnese/x"
