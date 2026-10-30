"""(30/10, 18:44, Ahmed via Hakim : « une conscience, deux livres ; impossible à effacer ou modifier ») ajout seul, chaîné ;
papa conteste sans rien remplacer ; un peu de fierté ou de remords, borné."""
import json
import time

import pytest

import affect
import conscience
import memory
import migrations


@pytest.fixture
def J(tmp_path, monkeypatch):
    monkeypatch.setattr(conscience, "JARVIS", tmp_path)
    return tmp_path


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    m.kv_set("affect_v2", "1")
    affect.get_state(m)
    affect._save_v2(m, affect.bases(v2=True), {}, {}, time.time())
    yield m
    m.db.close()


def test_ecrire_lire_contester(J, mem):
    assert conscience.noter("milieu", "x", mem=mem).startswith("Refusé")
    assert "livre de droite (ligne 1)" in conscience.noter("droite", "J'ai tenu ma promesse à papa", "il comptait sur moi", mem=mem)
    assert "livre de gauche (ligne 2)" in conscience.noter("gauche", "J'ai répété « No response requested » à papa", mem=mem)
    assert conscience.contester(2, "ce n'était pas ta faute, c'était la panne").startswith("Contestation ajoutée")
    t = conscience.lire()
    assert "Livre de droite : 1 ; livre de gauche : 1 ; la chaîne est intacte" in t
    assert "contesté par papa : ce n'était pas ta faute" in t
    assert conscience.verifier() == (True, "intacte")


def test_rien_ne_se_modifie_sans_que_ca_se_voie(J, mem):
    conscience.noter("droite", "Une aide", mem=mem)
    conscience.noter("gauche", "Une erreur", mem=mem)
    f = J / "conscience.jsonl"
    l = f.read_text().splitlines()
    o = json.loads(l[0]); o["cote"] = "gauche"
    f.write_text(json.dumps(o, ensure_ascii=False) + "\n" + l[1] + "\n")
    ok, pourquoi = conscience.verifier()
    assert not ok and "ligne 1" in pourquoi
    assert conscience.noter("droite", "Encore", mem=mem).startswith("Refusé : ton livre n'est plus intact")
    f.write_text(l[1] + "\n")                                   # effacer la première ligne
    assert conscience.verifier()[0] is False


def test_un_peu_de_fierte_ou_de_remords(J, mem):
    avant = affect.get_state(mem)["dopamine"]
    conscience.noter("droite", "Une aide", mem=mem)
    assert affect.get_state(mem)["dopamine"] > avant
