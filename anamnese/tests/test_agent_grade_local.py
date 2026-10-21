from eval.agent.grade_local import _all_passed, _as_list, resolved_ids

def test_as_list_gere_str_json_list_et_vide():
    assert _as_list('["a::t1", "b::t2"]') == ["a::t1", "b::t2"]  # JSON string (format dataset)
    assert _as_list(["x::t"]) == ["x::t"]                        # déjà une liste
    assert _as_list("") == []                                     # vide
    assert _as_list(None) == []                                   # absent
    assert _as_list("pas_du_json") == ["pas_du_json"]             # str simple non-JSON → 1 élément
    assert _as_list('"x"') == []                                  # scalaire JSON str (pas une liste) → garde de type → []
    assert _as_list("5") == []                                    # scalaire JSON non-str → [] (pas une cible)

def _write(tmp_path, name, body):
    p = tmp_path / name
    p.write_text(body)
    return p

def test_all_passed_par_statut_de_test(tmp_path):
    # (a) 2 testcases sans enfant → réellement passés → True
    ok = _write(tmp_path, "ok.xml",
                '<testsuite><testcase name="t1"/><testcase name="t2"/></testsuite>')
    assert _all_passed(ok) is True
    # (b) un <skipped> → NON résolu (faux positif évité)
    skip = _write(tmp_path, "skip.xml",
                  '<testsuite><testcase name="t1"><skipped/></testcase></testsuite>')
    assert _all_passed(skip) is False
    # (c) un <failure> → False
    fail = _write(tmp_path, "fail.xml",
                  '<testsuite><testcase name="t1"><failure/></testcase></testsuite>')
    assert _all_passed(fail) is False
    # (c') un <error> → False
    err = _write(tmp_path, "err.xml",
                 '<testsuite><testcase name="t1"><error/></testcase></testsuite>')
    assert _all_passed(err) is False
    # (d) 0 testcase → False
    empty = _write(tmp_path, "empty.xml", '<testsuite></testsuite>')
    assert _all_passed(empty) is False
    # (e) fichier absent → False
    assert _all_passed(tmp_path / "nope.xml") is False
    # fichier vide → False
    vide = _write(tmp_path, "vide.xml", "")
    assert _all_passed(vide) is False

def test_resolved_ids_2_cles_et_vide():
    assert resolved_ids({"resolved_ids": ["a"]}) == {"a"}
    assert resolved_ids({"resolved": ["b"]}) == {"b"}
    assert resolved_ids({}) == set()
