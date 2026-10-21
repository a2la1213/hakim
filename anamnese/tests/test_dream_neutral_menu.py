# tests/test_dream_neutral_menu.py
import dream_lab


def test_load_neutral_seeds_shape():
    seeds = dream_lab.load_neutral_seeds()
    assert len(seeds) >= 30
    ids = [s["id"] for s in seeds]
    assert len(ids) == len(set(ids))                      # ids uniques
    for s in seeds:
        assert set(s) >= {"id", "text", "pseudo_rubric", "strate"}
        assert s["strate"] in ("recent", "moyen", "ancien")
        assert isinstance(s["text"], str) and len(s["text"]) > 10
    rubrics = {s["pseudo_rubric"] for s in seeds}
    assert len(rubrics) >= 5                               # diversité de pseudo-domaines


def test_build_neutral_menu_deterministic():
    seeds = dream_lab.load_neutral_seeds()
    a = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    b = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    assert [it["episode_id"] for it in a] == [it["episode_id"] for it in b]  # reproductible


def test_build_neutral_menu_shape_and_size():
    seeds = dream_lab.load_neutral_seeds()
    menu = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    assert 1 <= len(menu) <= 12
    for it in menu:
        assert set(it) == {"episode_id", "rubric", "strate", "snippet", "facets"}
        assert isinstance(it["facets"], list)
        assert len(it["snippet"]) <= 280


def test_build_neutral_menu_different_nights_differ():
    seeds = dream_lab.load_neutral_seeds()
    m1 = [it["episode_id"] for it in dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")]
    m2 = [it["episode_id"] for it in dream_lab.build_neutral_menu(seeds, "2026-07-10-0300")]
    assert m1 != m2                                       # le tirage dépend du night_id


def test_build_neutral_menu_parse_choice_roundtrip():
    seeds = dream_lab.load_neutral_seeds()
    menu = dream_lab.build_neutral_menu(seeds, "2026-07-09-0300")
    chosen = dream_lab.parse_choice("###CHOIX###\n- G1\n- G3\n###REVE###\n- x\n###FIN###", menu)
    assert chosen == [menu[0]["episode_id"], menu[2]["episode_id"]]


def test_build_neutral_menu_empty_seeds():
    assert dream_lab.build_neutral_menu([], "2026-07-09-0300") == []
