# tests/test_dream_menu.py
"""Menu stratifié : diversité de rubriques, strates de récence, mix de saillance,
déterminisme seedé par night_id, robustesse mémoire minuscule."""
import time

import dream_lab
import migrations
import rubrics
from memory import Memory

import pytest

NOW = 1_800_000_000.0


@pytest.fixture
def mem(tmp_path, monkeypatch):
    import embeddings
    monkeypatch.setattr(embeddings, "embed", lambda t: [0.0] * 8)
    m = Memory(db_path=tmp_path / "t.db")
    migrations.migrate(m.db)
    yield m
    m.db.close()


def _add(mem, content, age_d, importance=0.5, rubric_path=None, role="semantic"):
    eid = mem.add(role, content, importance=importance, embedding=[0.0] * 8)
    mem.db.execute("UPDATE episodes SET ts=? WHERE id=?", (NOW - age_d * 86400, eid))
    if rubric_path:
        parts = rubric_path.split("/")
        for depth in range(1, len(parts) + 1):  # parents d'abord (exigé par rubric_create)
            rubrics.rubric_create(mem.db, "/".join(parts[:depth]), NOW)
        rid = rubrics.get_rubric_id(mem.db, rubric_path)
        mem.db.execute("UPDATE episodes SET rubric_id=? WHERE id=?", (rid, eid))
    mem.db.commit()
    return eid


def _populate(mem):
    for i in range(8):
        _add(mem, f"souvenir récent projets numéro {i}", age_d=1 + i % 5,
             importance=0.8 if i % 2 else 0.3, rubric_path="projets/demo")
    for i in range(8):
        _add(mem, f"souvenir moyen savoir numéro {i}", age_d=10 + i,
             importance=0.7 if i % 2 else 0.2, rubric_path="savoir/tech")
    for i in range(8):
        _add(mem, f"souvenir ancien perso numéro {i}", age_d=40 + i,
             importance=0.9 if i % 2 else 0.4, rubric_path="personnel/gouts")


def test_menu_size_strates_et_rubriques(mem):
    _populate(mem)
    menu = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    assert len(menu) == 12
    strates = {it["strate"] for it in menu}
    assert strates == {"recent", "moyen", "ancien"}          # les 3 strates présentes
    assert any("récent" in it["snippet"] for it in menu)
    # plafond par rubrique de tête respecté AVANT backfill : ici 3 rubriques × cap 2 = 6
    # < 12 → le backfill repêche ; on vérifie donc juste que les 3 têtes sont représentées
    tops = {(it["rubric"] or "").split("/")[0] for it in menu}
    assert {"projets", "savoir", "personnel"} <= tops


def test_menu_deterministe_par_night_id(mem):
    _populate(mem)
    m1 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    m2 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-03")
    m3 = dream_lab.build_menu(mem, now=NOW, night_id="2026-07-04")
    assert [i["episode_id"] for i in m1] == [i["episode_id"] for i in m2]
    assert [i["episode_id"] for i in m1] != [i["episode_id"] for i in m3]


def test_menu_exclut_les_roles_echo(mem):
    _populate(mem)
    echo = mem.add("dream", "(rêve) une idée d'hier", importance=0.9, embedding=[0.0] * 8)
    refl = mem.add("reflection", "pensée du daemon", importance=0.9, embedding=[0.0] * 8)
    ids = {it["episode_id"] for it in dream_lab.build_menu(mem, now=NOW, night_id="n")}
    assert echo not in ids and refl not in ids


def test_menu_memoire_minuscule(mem):
    _add(mem, "seul souvenir", age_d=1)
    menu = dream_lab.build_menu(mem, now=NOW, night_id="n")
    assert len(menu) == 1                                    # court, jamais de crash


def test_fallback_menu(mem):
    _populate(mem)
    fb = dream_lab.fallback_menu(mem, size=5)
    assert len(fb) == 5
    assert all(set(it) >= {"episode_id", "snippet", "rubric", "strate", "facets"} for it in fb)
