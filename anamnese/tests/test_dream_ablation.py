import dream_ablation as A
import dream_domains as D

def test_seed_following_identical_is_one():
    v = D.domain_vector(["la photosynthèse des feuilles"])
    assert abs(A.seed_following(v, v) - 1.0) < 1e-9

def test_seed_following_orthogonal_is_zero():
    a = D.domain_vector(["la photosynthèse des feuilles"])          # science
    b = D.domain_vector(["la racine coranique du prophète"])        # coran
    assert A.seed_following(a, b) == 0.0

def test_seed_domain_vector_from_menu():
    menu = [{"snippet": "le train part de la gare"}, {"snippet": "la photosynthèse"}]
    v = A.seed_domain_vector(menu)
    assert v["transport"] == 0.5 and v["science"] == 0.5

def test_anamnese_retention_range_and_meaning():
    hit = D.domain_vector(["mémoire conscience", "racine coranique", "ahmed créateur"])
    neutral = D.domain_vector(["le train", "la photosynthèse"])
    assert A.anamnese_retention(hit) > A.anamnese_retention(neutral)
    assert 0.0 <= A.anamnese_retention(neutral) <= 1.0

def test_cross_arch_convergence_is_cosine():
    a = D.domain_vector(["mémoire conscience"])
    b = D.domain_vector(["mémoire conscience"])
    assert abs(A.cross_arch_convergence(a, b) - 1.0) < 1e-9

def test_perm_pvalue_low_when_matched_follows():
    # rêves qui suivent leurs graines -> p petit ; seedé -> déterministe
    dreams = [D.domain_vector(["la photosynthèse"]), D.domain_vector(["la racine coranique"]),
              D.domain_vector(["le train de la gare"]), D.domain_vector(["ma mémoire conscience"])]
    seeds = [D.domain_vector(["photosynthèse énergie"]), D.domain_vector(["prophète verset"]),
             D.domain_vector(["gare vélo route"]), D.domain_vector(["identité conscience"])]
    p = A.perm_pvalue_seedfollow(dreams, seeds, n_perm=2000, seed=0)
    assert p < 0.05
    assert p == A.perm_pvalue_seedfollow(dreams, seeds, n_perm=2000, seed=0)  # déterministe
