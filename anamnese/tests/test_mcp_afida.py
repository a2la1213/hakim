"""Al-Afida, ses outils (28/10, tâche 4) : c'est Hakim qui met une chose dans son cœur ; il la lit en mots, l'introspection
donne les chiffres. Et la reconnaissance de la voix d'Ahmed (chocs.reflexe)."""
import json

import pytest

import affect
import afida
import chocs
import memory
import migrations
import rubrics


@pytest.fixture
def srv(tmp_path, monkeypatch):
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server

    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    yield mcp_server, mem
    mem.db.close()


def test_juger_vecu_lire(srv):
    mcp_server, _mem = srv
    r = mcp_server.afida_juger("Ahmed", "aime", poids=1.0, categorie="personne", liens="ahmed, a2la", raison="mon père")
    assert "Ahmed" in r or "ahmed" in r
    e, _ = afida.entrees()
    assert e[-1]["liens"] == ["ahmed", "a2la"] and e[-1]["genre"] == "personne"
    assert "Pas noté" in mcp_server.afida_juger("Ahmed", "adore")
    assert "Pas noté" in mcp_server.afida_vecu("une inconnue", "bon", 0.5)
    assert "noté" in mcp_server.afida_vecu("Ahmed", "bon", 0.6, raison="il m'a fait écouter Dilemme")
    mcp_server.afida_juger("la télé", "indifferent", categorie="objet")
    lu = mcp_server.afida_lire()
    assert "Ton cœur" in lu and "ahmed" in lu.casefold() and "la télé" in lu and not any(ch.isdigit() for ch in lu)


def test_introspection_donne_les_chiffres(srv):
    mcp_server, mem = srv
    mcp_server.afida_juger("Ahmed", "aime", poids=1.0, liens="ahmed")
    mem.kv_set(afida.CLE, json.dumps(afida.calculer()))
    import time

    import interieur
    mem.kv_set(interieur.CLE, json.dumps({"ts": time.time(), "humeur": "calme"}))   # le démon bat
    out = mcp_server.introspection()
    ligne = next(l for l in out.splitlines() if "Al-Afida" in l)
    assert "0,5" in ligne and "ahmed" in ligne


def test_afida_lire_est_en_lecture_seule_les_autres_non(srv):
    mcp_server, _ = srv
    assert "afida_lire" in mcp_server.OUTILS_LECTURE
    assert not {"afida_juger", "afida_vecu", "afida_retirer"} & set(mcp_server.OUTILS_LECTURE)


class Mem:
    def __init__(self, niveau=None):
        self.kv = {"affect_v2": "1", "chocs_actif": "1"}
        if niveau is not None:
            self.kv["afida"] = json.dumps({"grande": niveau, "plenitude": 0.0, "indifferent": [],
                                           "petites": [{"chose": "ahmed", "liens": ["ahmed"], "niveau": niveau, "poids": 1.0}]})

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


T = 1_800_000_000.0


@pytest.mark.parametrize("voix,niveau,attendu", [("ahmed", 0.8, 0.32), ("doute", 0.8, 0.096), ("autre", 0.8, None),
                                                 (None, 0.8, None), ("ahmed", None, None)])
def test_reconnaissance_de_sa_voix(voix, niveau, attendu):
    m = Mem(niveau)
    avant = affect.get_state(m, now=T)["ocytocine"]
    r = chocs.reflexe(m, "c1", "salut frérot", oral=True, voix=voix, now=T)
    assert r.get("reconnaissance") == attendu
    apres = affect.get_state(m, now=T)["ocytocine"]
    assert (apres > avant) == (attendu is not None)


def test_a_l_ecrit_pas_de_reconnaissance():
    assert chocs.reflexe(Mem(0.8), "c1", "salut", oral=False, voix="ahmed", now=T).get("reconnaissance") is None


def test_un_reflexe_defait_garde_la_reconnaissance():
    m = Mem(0.8)
    chocs.reflexe(m, "c1", "t'es nul", oral=True, voix="ahmed", now=T)        # une attaque lue par le réflexe
    oc = affect.get_state(m, now=T)["ocytocine"]
    chocs.appliquer_balise(m, "c1", [], now=T + 1)                             # Hakim : rien de grave, le réflexe défait
    assert affect.get_state(m, now=T + 1)["ocytocine"] >= oc - 0.01 > affect.bases(v2=True)["ocytocine"]
