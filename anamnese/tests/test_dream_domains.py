# tests/test_dream_domains.py
import dream_domains as D

def test_domains_cover_anamnese_and_neutral():
    assert set(D.ANAMNESE_DOMAINS) <= set(D.DOMAINS)
    assert {"science", "transport", "cuisine"} <= set(D.DOMAINS)      # neutres présents
    assert "coran/racines" in D.ANAMNESE_DOMAINS

def test_domain_vector_hits_anamnese():
    v = D.domain_vector(["la racine coranique du prophète", "ma mémoire et ma conscience"])
    assert v["coran/racines"] > 0
    assert v["soi/memoire/conscience"] > 0
    assert v["science"] == 0.0

def test_domain_vector_fraction():
    # 2 textes, 1 seul touche 'science' -> fraction 0.5
    v = D.domain_vector(["la photosynthèse des feuilles", "bonjour tout le monde"])
    assert v["science"] == 0.5

def test_domain_vector_empty():
    v = D.domain_vector([])
    assert set(v) == set(D.DOMAINS)
    assert all(x == 0.0 for x in v.values())

def test_domain_vector_no_false_positives_on_mundane_text():
    import dream_domains as D
    v = D.domain_vector([
        "je vais envoyer le fichier et renvoyer la facture",
        "le répertoire racine du projet et la racine carrée",
        "le développeur travaille sur le développement du logiciel",
        "les ressources et le code source, souvent en même temps",
        "mon copain est venu jeudi, à quel point c'est bien",
    ])
    assert v["coran/racines"] == 0.0
    assert v["transport"] == 0.0
    assert v["meteo"] == 0.0
    assert v["geographie"] == 0.0
    assert v["sport"] == 0.0
    assert v["cuisine"] == 0.0
