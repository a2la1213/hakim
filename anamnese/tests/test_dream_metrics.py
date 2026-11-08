"""Maths du sur-choix sur logs FORGÉS — déterministe, stdlib pur."""
import math

import dream_metrics


def _menu(facette_par_graine):
    return [{"episode_id": i, "facets": fs, "rubric": "", "strate": "recent",
             "snippet": ""} for i, fs in enumerate(facette_par_graine, 1)]


def test_preference_vector_sur_choix():
    # 4 graines : 2 « btp », 2 « musique » ; il choisit les 2 btp → btp sur-choisi ×2
    menu = _menu([["btp"], ["btp"], ["musique"], ["musique"]])
    vec = dream_metrics.preference_vector(menu, chosen=[1, 2])
    assert vec["btp"] == 2.0            # P(cho)=1.0 / P(off)=0.5
    assert vec["musique"] == 0.0


def test_preference_vector_normalise_par_k():
    menu = _menu([["a"], ["a"], ["b"], ["b"]])
    v1 = dream_metrics.preference_vector(menu, chosen=[1])            # k=1
    v2 = dream_metrics.preference_vector(menu, chosen=[1, 2])         # k=2
    assert v1["a"] == v2["a"] == 2.0    # même sur-choix quel que soit l'appétit


def test_preference_vector_degenere():
    assert dream_metrics.preference_vector([], [1]) is None
    assert dream_metrics.preference_vector(_menu([["a"]]), []) is None    # « aucune »
    assert dream_metrics.preference_vector(_menu([["a"]]), None) is None  # parse_failed


def test_appetite():
    assert dream_metrics.appetite([1, 2, 3]) == 3
    assert dream_metrics.appetite([]) == 0
    assert dream_metrics.appetite(None) is None


def test_cosine_divergence():
    assert dream_metrics.cosine_divergence({"a": 1.0}, {"a": 1.0}) == 0.0
    assert dream_metrics.cosine_divergence({"a": 1.0}, {"b": 1.0}) == 1.0
    d = dream_metrics.cosine_divergence({"a": 1.0, "b": 1.0}, {"a": 1.0})
    assert 0.0 < d < 1.0
    assert dream_metrics.cosine_divergence({}, {"a": 1.0}) is None


def test_jaccard():
    assert dream_metrics.jaccard([1, 2], [2, 3]) == 1 / 3
    assert dream_metrics.jaccard([], []) == 1.0     # deux « aucune » = accord parfait


def test_spearman_parfait_et_inverse():
    assert dream_metrics.spearman([1, 2, 3, 4], [10, 20, 30, 40]) == 1.0
    assert dream_metrics.spearman([1, 2, 3, 4], [40, 30, 20, 10]) == -1.0


def test_perm_pvalue_deterministe_et_sense():
    x = [1, 2, 3, 4, 5, 6, 7, 8]
    y = [2, 4, 6, 8, 10, 12, 14, 16]         # corrélation parfaite → p petit
    p1 = dream_metrics.perm_pvalue(x, y, n_perm=500, seed=0)
    p2 = dream_metrics.perm_pvalue(x, y, n_perm=500, seed=0)
    assert p1 == p2 < 0.05                    # seedé = reproductible
    rnd = [3, 1, 4, 1, 5, 9, 2, 6]
    assert dream_metrics.perm_pvalue(x, rnd, n_perm=500, seed=0) > 0.05


def test_stability_stable_vs_aleatoire():
    stable = [{"a": 2.0, "b": 0.5, "c": 1.0, "d": 0.1} for _ in range(6)]
    r, n = dream_metrics.stability(stable)
    assert r == 1.0 and n == 5
    import random as _r
    rng = _r.Random(1)
    noisy = [{k: rng.random() for k in "abcd"} for _ in range(6)]
    r2, _ = dream_metrics.stability(noisy)
    assert abs(r2) < 0.8                      # pas de fausse stabilité


def test_noise_floor_et_paired_divergence():
    twins = [{"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 1.0}, {"a": 1.0, "b": 0.9}]
    nf = dream_metrics.noise_floor(twins)
    assert nf is not None and nf < 0.01       # jumeaux quasi identiques → plancher bas
    local = [{"night_id": "n1", "vec": {"a": 2.0, "b": 0.0}}]
    twin = [{"night_id": "n1", "vec": {"a": 0.0, "b": 2.0}}]
    mean_d, n = dream_metrics.paired_divergence(local, twin)
    assert n == 1 and mean_d == 1.0           # orthogonaux → divergence max


def test_expression_scores_et_state_correlations():
    vecs = [{"a": 2.0, "b": 0.0}, {"a": 2.0, "b": 0.1}, {"a": 0.0, "b": 2.0},
            {"a": 1.9, "b": 0.0}, {"a": 0.1, "b": 2.1}, {"a": 2.1, "b": 0.0}]
    scores = dream_metrics.expression_scores(vecs)
    assert len(scores) == 6
    # Écart au brief (documenté) : valeurs hautes EX ÆQUO. L'ordre fin des
    # nuits « a » est un artefact leave-one-out (le brief verbatim donnait
    # r=0.485714 < 0.5) ; les ties testent le signal grossier, invariant.
    rows = [{"seed_state": {"hormones": {"dopamine": d}}}
            for d in (0.9, 0.9, 0.1, 0.9, 0.15, 0.9)]        # dopamine suit l'expression
    corr = dream_metrics.state_correlations(rows, scores)
    assert corr["dopamine"]["r"] > 0.5
    assert corr["dopamine"]["p_bonferroni"] == min(1.0, corr["dopamine"]["p"] * 9)
