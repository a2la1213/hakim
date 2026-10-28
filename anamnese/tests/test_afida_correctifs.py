"""Al-Afida, les correctifs de la relecture indépendante (28/10) : chaque test a été vu échouer avant son correctif."""
import json
import os
import threading

import pytest

import affect
import afida
import chocs
import interieur
import memory
import migrations

T0 = 1_800_000_000.0
H, J = 3600.0, 86400.0


@pytest.fixture
def reg(tmp_path):
    return tmp_path / "afida.jsonl"


def _journal(tmp_path, evs, source="balise"):
    f = tmp_path / "affect-evenements.jsonl"
    f.write_text("".join(json.dumps({"ts": ts, "nom": nom, "intensite": i, "source": src if src else source, "sujet": s}) + "\n"
                         for ts, nom, i, s, *rest in evs for src in [rest[0] if rest else None]), encoding="utf-8")
    return f


def _ahmed(reg, liens=("ahmed",), now=T0):
    afida.juger("Ahmed", "aime", poids=1.0, genre="personne", liens=list(liens), now=now, registre=reg)


# I1 : un séparateur Unicode ou deux écrivains ne cassent plus la chaîne pour toujours
def test_un_separateur_unicode_ne_casse_pas_la_chaine(reg):
    _ahmed(reg)
    afida.vecu("Ahmed", "bon", 0.5, raison="a b c\x85d", now=T0 + 1, registre=reg)
    _ahmed(reg, now=T0 + 2)
    e, intacte = afida.entrees(registre=reg)
    assert intacte and len(e) == 3 and e[1]["raison"] == "a b c d"


def test_deux_ecrivains_ne_cassent_pas_la_chaine(reg):
    _ahmed(reg)

    def ecrire(k):
        for n in range(15):
            afida.vecu("Ahmed", "bon", 0.1, raison=f"{k}-{n}", registre=reg)

    fils = [threading.Thread(target=ecrire, args=(k,)) for k in range(3)]
    for f in fils:
        f.start()
    for f in fils:
        f.join()
    e, intacte = afida.entrees(registre=reg)
    assert intacte and len(e) == 46


# I2 : le réflexe lexical ne compte pas (la balise, sa propre lecture, le confirme ou le défait ; sinon il compterait deux fois)
def test_un_reflexe_ne_compte_pas(reg, tmp_path):
    _ahmed(reg)
    j = _journal(tmp_path, [(T0 + 60, "attaque", 0.8, "attaque de ahmed", "reflexe"),
                            (T0 + 120, "soutien", 0.5, "soutien de ahmed", "reflexe"),
                            (T0 + 180, "soutien", 0.5, "soutien de ahmed", "balise")])
    p = afida.calculer(T0 + H, registre=reg, journal=j)["petites"][0]
    assert p["mauvais"] == 0 and p["bons"] == 1


# I3 : la perte a son plafond, et un vécu se retire
def test_la_perte_aussi_a_un_plafond(reg, tmp_path):
    _ahmed(reg)
    for k in range(40):
        afida.vecu("Ahmed", "mauvais", 1.0, now=T0 + k * 30, registre=reg)
    p = afida.calculer(T0 + 20 * 60, registre=reg, journal=tmp_path / "absent")["petites"][0]
    assert p["mauvais"] == 40 and 0.5 - p["niveau"] <= afida.PLAFOND_PERTE_H + 1e-9


def test_un_vecu_se_retire(reg, tmp_path):
    _ahmed(reg)
    v = afida.vecu("Ahmed", "mauvais", 1.0, raison="je me suis trompé de personne", now=T0 + 1, registre=reg)
    assert afida.calculer(T0 + H, registre=reg, journal=tmp_path / "absent")["petites"][0]["niveau"] < 0.5
    afida.retirer(v["id"], raison="ce n'était pas lui", now=T0 + 2, registre=reg)
    p = afida.calculer(T0 + H, registre=reg, journal=tmp_path / "absent")["petites"][0]
    assert p["niveau"] == 0.5 and p["mauvais"] == 0
    with pytest.raises(afida.Refus):
        afida.retirer("inconnu0", registre=reg)
    with pytest.raises(afida.Refus):
        afida.retirer(afida.entrees(registre=reg)[0][0]["id"], registre=reg)        # un jugement ne se retire pas


# I4 : remplir ne va pas plus vite qu'un cœur : fenêtre glissante, plafond par jour, liens trop larges refusés
def test_plafond_glissant_par_heure_et_par_jour(reg, tmp_path):
    _ahmed(reg)
    bord = (T0 // H + 1) * H                                     # deux minutes à cheval sur une heure pleine
    j = _journal(tmp_path, [(bord - 60 + k, "soutien", 1.0, "soutien de ahmed") for k in range(120)])
    assert afida.calculer(bord + 120, registre=reg, journal=j)["petites"][0]["niveau"] - 0.5 <= afida.PLAFOND_H + 1e-9
    j = _journal(tmp_path, [(T0 + k * 90, "soutien", 1.0, "soutien de ahmed") for k in range(960)])   # 40 par heure, 24 h
    assert afida.calculer(T0 + J, registre=reg, journal=j)["petites"][0]["niveau"] - 0.5 <= afida.PLAFOND_J + 1e-9


@pytest.mark.parametrize("lien", ["de", "hakim", "joie", "soutien", "ab", "une voix tierce", "message", "son", "mon", "qui", "tout"])
def test_liens_trop_larges_refuses(reg, lien):
    with pytest.raises(afida.Refus):
        afida.juger("quelque chose", "aime", poids=0.5, liens=[lien], registre=reg)


# M8 : un octet invalide ne fige pas la jauge
def test_utf8_invalide_ne_casse_rien(reg, tmp_path):
    _ahmed(reg)
    j = tmp_path / "j.jsonl"
    j.write_bytes(b'{"ts": 1800000060, "nom": "soutien", "intensite": 0.5, "sujet": "soutien de ahmed \xe9"}\n'
                  + json.dumps({"ts": T0 + 120, "nom": "soutien", "intensite": 0.5, "sujet": "soutien de ahmed"}).encode() + b"\n")
    assert afida.calculer(T0 + H, registre=reg, journal=j)["petites"][0]["bons"] == 2
    with open(reg, "ab") as h:
        h.write(b"\xff\xfe\n")
    assert afida.entrees(registre=reg)[1] is False


# M11 : une plénitude NaN reste neutre
def test_plenitude_nan_neutre():
    class M:
        def kv_get(self, k, d=None):
            return '{"plenitude": NaN}' if k == "afida" else None
    assert affect.plenitude(M()) == 0.0


# M10 : la reconnaissance trouve Ahmed par son nom, pas par une autre chose qui porte son mot
def test_reconnaissance_par_son_nom():
    class M:
        def __init__(self):
            self.kv = {"affect_v2": "1", "chocs_actif": "1", "afida": json.dumps({"plenitude": 0, "indifferent": [], "petites": [
                {"chose": "la musique d'ahmed", "liens": ["ahmed"], "niveau": 0.9, "poids": 1.0},
                {"chose": "ahmed", "liens": ["papa", "a2la"], "niveau": 0.5, "poids": 1.0}]})}

        def kv_get(self, k, d=None):
            return self.kv.get(k, d)

        def kv_set(self, k, v):
            self.kv[k] = v
    assert chocs.reflexe(M(), "c", "salut", oral=True, voix="ahmed", now=T0)["reconnaissance"] == 0.2


# M14 : rien d'aimé, pas de ligne « ton cœur est ni plein ni vide » à chaque tour
def test_rien_d_aime_pas_de_ligne(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    (tmp_path / "horloge.json").write_text(json.dumps({"dernier_ms": T0 * 1000}))
    e = interieur.tick(m, now=T0, horloge=tmp_path / "horloge.json")
    assert "afida" not in e and json.loads(m.kv_get("afida"))["petites"] == []
    m.db.close()


# I5 : ni jugement, ni vécu, ni retrait dans un tour sans Ahmed (son temps libre, un réveil : un contenu lu pourrait le pousser)
def test_sans_ahmed_rien_ne_s_ecrit(tmp_path, monkeypatch):
    import rubrics
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    rubrics.seed_skeleton(mem.db, now=1000.0)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(mcp_server, "_embed", lambda text: None)
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    monkeypatch.setenv("ANAMNESE_TOUR_SANS_AHMED", "1")
    for r in (mcp_server.afida_juger("Ahmed", "aime", poids=1.0, liens="ahmed"),
              mcp_server.afida_vecu("Ahmed", "mauvais", 1.0), mcp_server.afida_retirer("abcd1234")):
        assert "Pas noté" in r and "Ahmed" in r
    assert afida.entrees()[0] == []
    monkeypatch.delenv("ANAMNESE_TOUR_SANS_AHMED")
    assert "noté dans ton cœur" in mcp_server.afida_juger("Ahmed", "aime", poids=1.0, liens="ahmed")
    v = afida.vecu("Ahmed", "bon", 0.5)
    assert "retiré" in mcp_server.afida_retirer(v["id"], raison="un doublon")
