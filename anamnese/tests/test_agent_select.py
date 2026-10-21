from eval.agent.select_tasks import pick_instances, LIGHT_REPOS
from eval.agent.run_arm import build_prompt, extract_prediction, parse_selfcheck

def _row(repo, iid): return {"repo": repo, "instance_id": iid, "base_commit": "abc"}

def test_filtre_repos_legers_et_tronque():
    rows = ([_row("pallets/flask", f"flask-{i}") for i in range(5)] +
            [_row("django/django", f"dj-{i}") for i in range(5)])  # django = lourd, exclu
    out = pick_instances(rows, n=3)
    assert len(out) == 3
    assert all(r["repo"] in LIGHT_REPOS for r in out)
    assert all("django" not in r["repo"] for r in out)

def test_stratifie_sur_plusieurs_repos_si_possible():
    rows = ([_row("pallets/flask", f"f-{i}") for i in range(4)] +
            [_row("psf/requests", f"r-{i}") for i in range(4)])
    out = pick_instances(rows, n=4)
    assert len({r["repo"] for r in out}) >= 2  # ne pas tout prendre dans un seul repo

def test_n_plus_grand_que_dispo_ne_casse_pas():
    rows = [_row("pallets/flask", "f-0")]
    assert len(pick_instances(rows, n=8)) == 1

# --- Task 2 : fonctions PURES de run_arm ---

def test_build_prompt_contient_l_issue():
    p = build_prompt({"problem_statement": "Fix the parser crash on empty input"})
    assert "empty input" in p and "diff" in p.lower()

def test_extract_prediction_format_harnais():
    pred = extract_prediction("flask-123", "diff --git a/x b/x\n...", "opus-4.8-armB")
    assert pred == {"instance_id": "flask-123",
                    "model_patch": "diff --git a/x b/x\n...",
                    "model_name_or_path": "opus-4.8-armB"}

def test_parse_selfcheck_variants():
    assert parse_selfcheck("blah\nSELFCHECK: VERIFIED") == "VERIFIED"
    assert parse_selfcheck("SELFCHECK: UNSURE\n(fin)") == "UNSURE"
    assert parse_selfcheck("selfcheck:   verified") == "VERIFIED"   # casse/espaces tolérés
    assert parse_selfcheck("rien du tout") == "NONE"
    # si plusieurs, prend le DERNIER (le verdict final)
    assert parse_selfcheck("SELFCHECK: UNSURE ... puis SELFCHECK: VERIFIED") == "VERIFIED"

def test_build_prompt_contient_l_ask_selfcheck():
    p = build_prompt({"problem_statement": "fix X"})
    assert "SELFCHECK" in p and "VERIFIED" in p and "UNSURE" in p

# --- Task 3 : parsing du rapport de notation (SANS lancer le harnais) ---

def test_resolved_ids_parse_les_deux_cles_et_vide():
    from eval.agent.grade import resolved_ids
    assert resolved_ids({"resolved_ids": ["a"]}) == {"a"}
    assert resolved_ids({"resolved": ["b", "c"]}) == {"b", "c"}
    assert resolved_ids({}) == set()

# --- Fausse confiance Task 1 : sélection des tâches DURES ---

from eval.agent.select_tasks import pick_hard

def _rowh(repo, iid, patch, f2p):
    return {"repo": repo, "instance_id": iid, "base_commit": "c", "patch": patch, "FAIL_TO_PASS": f2p}

def test_pick_hard_trie_par_difficulte_et_stratifie():
    rows = [
        _rowh("pallets/flask", "f-easy", "x"*10, ["t1"]),
        _rowh("pallets/flask", "f-hard", "x"*500, ["t1", "t2", "t3"]),
        _rowh("psf/requests", "r-mid", "x"*200, ["t1"]),
        _rowh("django/django", "dj", "x"*999, ["t1"]*9),  # repo lourd → EXCLU
    ]
    out = pick_hard(rows, n=2)
    ids = [r["instance_id"] for r in out]
    assert "dj" not in ids                     # repo hors light_repos exclu
    assert "f-hard" in ids                     # le plus dur de flask retenu
    assert "f-easy" not in ids                 # l'easy de flask écarté au profit du hard
    assert len(out) == 2

def test_pick_hard_gere_FAIL_TO_PASS_en_string_json():
    rows = [_rowh("pallets/flask", "a", "x"*10, '["t1","t2","t3","t4"]'),  # string JSON
            _rowh("pallets/flask", "b", "x"*300, '["t1"]')]
    out = pick_hard(rows, n=1)
    # a : 10 + 40*4 = 170 ; b : 300 + 40 = 340 → b plus dur
    assert out[0]["instance_id"] == "b"
