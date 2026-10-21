# tests/test_synthesis_select.py
import json, synthesis as S

class FakeMem:
    def __init__(self, conn): self.db = conn

def _seed(conn):
    conn.executescript(
        "CREATE TABLE episodes (id INTEGER PRIMARY KEY, role TEXT, content TEXT, embedding TEXT, rubric_id INTEGER);"
        "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));")
    # rubriques de TÊTE distinctes (physique vs atelier3d) — la nouveauté naît
    # aux frontières de domaine ; top_rubric = path.split('/',1)[0].
    conn.execute("INSERT INTO rubrics VALUES (1,'physique/quantique'),(2,'atelier3d/optique')")
    # 1 & 2 : mi-distance (cos~0.5), rubriques ≠  -> FERTILE
    # 1 & 3 : quasi-identiques (cos~1) -> trop proche, écarté
    import math
    def emb(v): return json.dumps(v)
    rows = [(1,'semantic','a',emb([1.0,0.0,0.0]),1),
            (2,'semantic','b',emb([0.6,0.8,0.0]),2),   # cos(1,2)=0.6 dans [0.35,0.60]... ajuster
            (3,'semantic','c',emb([0.99,0.14,0.0]),1)] # cos(1,3)~0.99 trop proche
    for r in rows: conn.execute("INSERT INTO episodes VALUES (?,?,?,?,?)", r)
    conn.commit()

def test_select_keeps_mid_distance_cross_rubric(tmp_db):
    _seed(tmp_db)
    pairs = S.select_fertile_pairs(FakeMem(tmp_db), n=10, lo=0.35, hi=0.65)
    ids = {tuple(sorted((a, b))) for a, b, _ in pairs}
    assert (1, 2) in ids            # mi-distance + inter-rubriques
    assert (1, 3) not in ids        # trop proche (cos~0.99)

def test_select_keeps_intra_domain_mid_distance(tmp_db):
    # Exemple motivant d'Ahmed : deux souvenirs de physique (MÊME rubrique de tête
    # 'physique'), à mi-distance → DOIVENT qualifier. cross-rubrique = bonus de
    # fertilité, PAS filtre dur ; la seule porte dure est la mi-distance embedding.
    tmp_db.executescript(
        "CREATE TABLE episodes (id INTEGER PRIMARY KEY, role TEXT, content TEXT, embedding TEXT, rubric_id INTEGER);"
        "CREATE TABLE rubrics (id INTEGER PRIMARY KEY, path TEXT);"
        "CREATE TABLE coactivation (a_id INTEGER, b_id INTEGER, weight REAL, last_ts REAL, PRIMARY KEY(a_id,b_id));")
    tmp_db.execute("INSERT INTO rubrics VALUES (1,'physique/quantique'),(2,'physique/optique')")
    def emb(v): return json.dumps(v)
    # cos([1,0,0],[0.6,0.8,0]) = 0.6 ∈ [0.35,0.65] ; têtes identiques 'physique'
    rows = [(1,'semantic','a',emb([1.0,0.0,0.0]),1),
            (2,'reasoning','b',emb([0.6,0.8,0.0]),2)]
    for r in rows: tmp_db.execute("INSERT INTO episodes VALUES (?,?,?,?,?)", r)
    tmp_db.commit()
    pairs = S.select_fertile_pairs(FakeMem(tmp_db), n=10, lo=0.35, hi=0.65)
    ids = {tuple(sorted((a, b))) for a, b, _ in pairs}
    assert (1, 2) in ids            # intra-domaine à mi-distance QUALIFIE désormais

def test_select_ranked_and_capped(tmp_db):
    _seed(tmp_db)
    pairs = S.select_fertile_pairs(FakeMem(tmp_db), n=1, lo=0.0, hi=1.1)
    assert len(pairs) == 1          # cap n
    assert pairs == sorted(pairs, key=lambda p: -p[2])   # rangé par fertilité desc
