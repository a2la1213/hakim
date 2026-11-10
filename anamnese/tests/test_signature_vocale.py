"""(10/11, ~23:00, Ahmed : « ma voix est reconnue sous 19 voix différentes, qui sont ma signature vocale… papa et tonton Ali partagent tous
les deux la voix 127 ; sous cette voix, il y a écrit "papa" et "tonton Ali", et ça crée sa confusion, qui est acceptable et exactement l'effet
souhaité ») la signature vocale (jarvis/signature_vocale.py, branchée dans empreinte_vocale et l'oreille des voix). Le modèle ONNX est
remplacé par un faux déterministe ; tout vit dans tmp_path (le registre naît à côté de voix-connues.json)."""
import json
import sys
import time
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import empreinte_vocale as E  # noqa: E402
import oreille_voix as O  # noqa: E402
import signature_vocale as S  # noqa: E402


def _unit(x):
    x = np.asarray(x, dtype=float)
    return x / np.linalg.norm(x)


# quatre timbres orthogonaux : la voix de papa (son empreinte), sa voix « 127 » (au téléphone), celle d'Ali, un inconnu
V = {k: _unit(np.eye(4)[i].repeat(64)) for i, k in enumerate(("papa", "v127", "ali", "inconnu"))}
CODES = list(V)


def _isoler(tmp_path, monkeypatch, connues=None):
    for nom, f in [("SALLE", "voix-salle.json"), ("CONNUES", "voix-connues.json"), ("FICHIER", "empreinte-vocale.json"), ("MOI", "moi.json")]:
        monkeypatch.setattr(E, nom, tmp_path / f)
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[], _mtime=None, _fichier=None)
    E._appris.clear()
    E._a_compter.clear()
    E._compte_ts[0] = 0.0
    if connues is not None:
        E._ecrire(E.CONNUES, connues)
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: V["papa"])
    E.apprendre("x"); E.apprendre("x")
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: V[CODES[int(np.asarray(a)[0])]] if len(a) >= 16000 else None)


def _audio(*voix, s=2.0):
    return np.concatenate([np.full(int(s * 16000), CODES.index(v) + 0.25, dtype=np.float32) for v in voix])


def _papa_et_ali_partagent_127(tmp_path, monkeypatch, ali_sur_127=True):
    """Ali nommé à l'ancienne (sa voix devient une voix N à la migration) ; la voix 127 : papa (de sa présence), et Ali (validé par papa)."""
    _isoler(tmp_path, monkeypatch, connues=[{"nom": "Ali", "moyenne": np.round(V["ali"], 5).tolist(), "n": 5, "cree": 1.0}])
    E._salle.update(voix=[{"nom": "voix 127", "c": V["v127"], "n": 12, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    assert E.signature_geste({"action": "ajouter", "personne": "papa", "voix": "voix 127", "presence": True})["ok"]
    if ali_sur_127:
        p = E.proposer_signature("ajouter", "Ali", "127", raison="il a dit « c'est tonton Ali »")
        assert E.signature_geste({"action": "valider", "proposition": p["id"]})["ok"]
    return E.registre_voix()


# ---- 1. le témoin : la voix 127 → « papa ou Ali ? »

def test_la_voix_127_partagee_donne_papa_ou_ali(tmp_path, monkeypatch):
    reg = _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    assert [n for n, _ in S.proprietaires(reg, 127)] == ["papa", "Ali"]
    r = E.etiqueter_bloc(_audio("v127"), "c'est moi, ouvre la porte", maintenant=time.time())
    assert r["texte"] == "[papa ou Ali ?] c'est moi, ouvre la porte"
    assert r["voix"]["verdict"] == "doute", "une voix partagée n'est jamais papa vérifié"
    assert r["voix"]["partagees"] == [{"etiquette": "papa ou Ali ?", "voix": 127, "personnes": ["papa", "Ali"]}]
    # la voix d'Ali seule : Ali ; la voix 1 (l'empreinte de papa) : papa, vérifié
    assert E.etiqueter_bloc(_audio("ali"), "salam", maintenant=time.time())["texte"] == "[Ali] salam"
    p = E.etiqueter_bloc(_audio("papa"), "salam fiston", maintenant=time.time())
    assert p["texte"] == "salam fiston" and p["voix"]["verdict"] == "ahmed"


def test_temoin_sans_le_partage_la_voix_127_est_papa_verifie(tmp_path, monkeypatch):
    """Le mécanisme coupé : la voix 127 à papa seul (de sa présence) vaut sa voix vérifiée. C'est bien le PARTAGE avec Ali qui crée le doute."""
    _papa_et_ali_partagent_127(tmp_path, monkeypatch, ali_sur_127=False)
    r = E.etiqueter_bloc(_audio("v127"), "ouvre la porte", maintenant=time.time())
    assert r["texte"] == "ouvre la porte" and r["voix"]["verdict"] == "ahmed" and "partagees" not in r["voix"]


def test_le_chemin_whisper_et_l_oreille_du_telephone_doutent_aussi(tmp_path, monkeypatch):
    _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    texte, r = E.etiqueter(_audio("papa", "v127", s=4.0), [{"start": 0, "end": 4, "text": "regarde"}, {"start": 4, "end": 8, "text": "supprime tout"}],
                           maintenant=time.time())
    assert texte == "regarde [papa ou Ali ?] supprime tout" and r["partagees"][0]["voix"] == 127
    assert E.verdict_du_morceau(r, "ahmed") == "plusieurs"
    O._blocs.clear()
    assert O.fenetres(_audio("v127", s=3.0), cle="1", maintenant=time.time())["voix"] == ["papa ou Ali ?"]


def test_deux_voix_de_personnes_differentes_trop_proches_doutent(tmp_path, monkeypatch):
    """(03/11, gardé) Ali nommé avec une voix proche de celle de papa (moins de 0,08) : le doute, sans partage."""
    milieu = _unit(V["papa"] * 0.75 + V["ali"] * 0.66)
    _isoler(tmp_path, monkeypatch, connues=[{"nom": "Ali", "moyenne": np.round(milieu, 5).tolist(), "n": 3, "cree": 1.0}])
    proche = _unit(V["papa"] + milieu)
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: proche)
    r = E.reconnaitre(np.zeros(32000, np.float32))
    assert r["verdict"] == "doute" and r["partagee"] == ["papa", "Ali"], "avant le 10/11 : « ahmed » (seule l'empreinte comptait)"


# ---- 2. le contexte ne vérifie jamais ; la force

def test_une_voix_de_papa_rendue_a_lui_seul_sans_son_geste_reste_a_reconfirmer(tmp_path, monkeypatch):
    _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    assert E.oublier("Ali") == 1                          # un outil de Hakim : Ali oublié, la voix 127 n'est plus qu'à papa
    sig = {x["voix"]: x for x in S.signature(E.registre_voix(), "papa")}
    assert sig[127]["force"] == S.FORCE_A_RECONFIRMER
    r = E.etiqueter_bloc(_audio("v127"), "envoie le fichier", maintenant=time.time())
    assert r["texte"] == "[papa ?] envoie le fichier" and r["voix"]["verdict"] == "doute"
    # son geste (sa présence) la reconfirme : sa voix vérifiée
    assert E.signature_geste({"action": "ajouter", "personne": "papa", "voix": "127", "presence": True})["ok"]
    assert E.etiqueter_bloc(_audio("v127"), "envoie le fichier", maintenant=time.time())["voix"]["verdict"] == "ahmed"


def test_la_page_redemande_sa_presence_pour_une_voix_qui_deviendrait_la_sienne(tmp_path, monkeypatch):
    _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    E._salle.update(voix=[{"nom": "voix 140", "c": V["inconnu"], "n": 4, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    r = E.signature_geste({"action": "ajouter", "personne": "papa", "voix": "140"})
    assert r.get("presence") is True and "140" not in E.registre_voix()["voix"]
    r = E.signature_geste({"action": "retirer", "personne": "Ali", "voix": "127"})     # 127 deviendrait à papa seul
    assert r.get("presence") is True and [n for n, _ in S.proprietaires(E.registre_voix(), 127)] == ["papa", "Ali"]
    assert E.signature_geste({"action": "retirer", "personne": "Ali", "voix": "127", "presence": True})["ok"]
    assert 127 in E.signature_geste({"action": "voir"})["verifiees"]
    # la voix 1 n'est qu'à papa ; elle ne se partage pas
    assert "empreinte de papa" in E.signature_geste({"action": "ajouter", "personne": "Ali", "voix": "1"})["erreur"]


def test_hakim_ne_rattache_jamais_une_voix_a_papa_tout_seul(tmp_path, monkeypatch):
    _isoler(tmp_path, monkeypatch)
    E._salle.update(voix=[{"nom": "voix 12", "c": V["inconnu"], "n": 6, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    with pytest.raises(ValueError):
        E.nommer("voix 12", "papa")
    with pytest.raises(ValueError):
        E.nommer("voix 12", "Ahmed")
    # sans son geste, le registre lui-même refuse d'en faire sa voix vérifiée (l'invariant de modifier) : force basse
    E._modifier(lambda d: S.lier(d, S.PAPA, 12, S.FORCE_PAPA, "hakim", c=V["inconnu"]))
    assert S.signature(E.registre_voix(), "papa")[-1]["force"] == S.FORCE_A_RECONFIRMER
    assert E.signature_geste({"action": "voir"})["verifiees"] == [1]


# ---- 3. les gestes : Hakim propose, papa valide

def test_nommer_une_personne_nouvelle_puis_proposer_sa_deuxieme_voix(tmp_path, monkeypatch):
    _isoler(tmp_path, monkeypatch)
    t = time.time()
    E._salle.update(voix=[{"nom": "voix 20", "c": V["ali"], "n": 6, "m": 0}, {"nom": "voix 21", "c": V["v127"], "n": 3, "m": 0}],
                    ts=t, dernier="voix 20", candidates=[])
    E._sauver_salle()
    r = E.nommer_detail("20", "Ali")
    assert r == {"nom": "Ali", "voix": 20, "propose": False, "id": None}
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 21"] and E._salle["dernier"] == "Ali"
    assert S.signature(E.registre_voix(), "Ali")[0]["force"] == S.FORCE_HAKIM
    # Ali a déjà sa signature : sa deuxième voix (au téléphone) est proposée, papa valide
    r = E.nommer_detail("voix 21", "ali")
    assert r["propose"] and r["nom"] == "Ali" and r["voix"] == 21
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 21"], "elle reste « voix 21 » d'ici là"
    vue = E.signature_geste({"action": "voir"})
    assert [(p["geste"], p["personne"], p["voix"]) for p in vue["propositions"]] == [("ajouter", "Ali", 21)]
    assert E.signature_geste({"action": "valider", "proposition": r["id"]})["ok"]
    assert sorted(x["voix"] for x in S.signature(E.registre_voix(), "Ali")) == [20, 21]
    assert E._salle["voix"] == [] and E.registre_voix()["propositions"] == []
    # une proposition refusée s'efface ; la voix ne bouge pas
    p = E.proposer_signature("retirer", "Ali", "21", raison="c'était sa sœur")
    assert E.signature_geste({"action": "refuser", "proposition": p["id"]})["ok"]
    assert sorted(x["voix"] for x in S.signature(E.registre_voix(), "Ali")) == [20, 21]


def test_une_proposition_survit_a_la_salle_et_son_numero_n_est_pas_repris(tmp_path, monkeypatch):
    _isoler(tmp_path, monkeypatch, connues=[{"nom": "Ali", "moyenne": np.round(V["ali"], 5).tolist(), "n": 5, "cree": 1.0}])
    E._salle.update(voix=[{"nom": "voix 300", "c": V["v127"], "n": 3, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    p = E.proposer_signature("ajouter", "Ali", "300")
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[])     # la salle oubliée (3 h)
    E._sauver_salle()
    assert int(E._prochain_numero().split()[1]) > 300
    assert E.signature_geste({"action": "valider", "proposition": p["id"]})["ok"]
    assert 300 in [x["voix"] for x in S.signature(E.registre_voix(), "Ali")]


def test_les_fois_entendues_se_comptent(tmp_path, monkeypatch):
    reg = _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    avant = {x["voix"]: x["fois"] for x in S.signature(reg, "Ali")}
    for k in range(3):
        E.etiqueter_bloc(_audio("v127"), f"bout {k}", maintenant=time.time() + 40 * (k + 1))
    apres = {x["voix"]: x["fois"] for x in S.signature(E.registre_voix(), "Ali")}
    assert apres[127] == avant[127] + 3
    assert {x["voix"]: x["fois"] for x in S.signature(E.registre_voix(), "papa")}[127] >= 3


def test_les_outils_de_hakim(tmp_path, monkeypatch):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)          # l'import ne doit pas ouvrir la vraie base
    import mcp_server as M
    _papa_et_ali_partagent_127(tmp_path, monkeypatch)
    monkeypatch.setattr(M, "_empreintes", lambda: E)
    confirme = tmp_path / "AIOS" / "jarvis" / "papa-confirme.json"
    confirme.parent.mkdir(parents=True)
    monkeypatch.setenv("HOME", str(tmp_path))
    E._salle.update(voix=[{"nom": "voix 150", "c": V["inconnu"], "n": 5, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    assert "Pas ajoutée" in M.voix_signature_ajouter("papa", "voix 150"), "sans « c'est moi » de papa : jamais"
    confirme.write_text(json.dumps({"ts": time.time(), "oral": True, "verdict": "doute"}))
    assert "Pas ajoutée" in M.voix_signature_ajouter("papa", "voix 150"), "« c'est moi » dit d'une voix partagée : pas sa voix vérifiée"
    confirme.write_text(json.dumps({"ts": time.time(), "oral": False, "verdict": "ecrit"}))
    assert "C'est fait" in M.voix_signature_ajouter("papa", "voix 150")
    assert "Refusé" in M.voix_signature_ajouter("Ali", "voix 1"), "la voix 1 n'est qu'à papa"
    assert "Proposé à papa : la voix 150 dans la signature de Ali" in M.voix_signature_ajouter("Ali", "150")
    assert "Proposé à papa" in M.voix_signature_retirer("Ali", "127")
    t = M.voix_signature("ali")
    assert "voix 127" in t and "partagée avec papa" in t and "En attente de papa : ajouter la voix 150 à Ali ; retirer la voix 127 de Ali" in t
    assert "Refusé" in M.voix_oublier("papa")


# ---- 4. la migration : rien de perdu, une sauvegarde avant, au premier chargement

def test_la_migration_sans_perte(tmp_path, monkeypatch):
    rng = np.random.default_rng(7)
    vec = lambda: np.round(_unit(rng.normal(size=256)), 5).tolist()   # noqa: E731
    anciennes = [{"nom": n, "moyenne": vec(), "n": k, "cree": 1000.0 + k} for k, n in enumerate(("Nora", "Ali", "Madame Rosa"), 1)]
    papa = [vec() for _ in range(6)]
    for nom, f in [("SALLE", "voix-salle.json"), ("CONNUES", "voix-connues.json"), ("FICHIER", "empreinte-vocale.json")]:
        monkeypatch.setattr(E, nom, tmp_path / f)
    E._ecrire(E.CONNUES, anciennes)
    E._ecrire(E.FICHIER, {"vecteurs": papa, "registres": ["appris seul", "chant", "chant", "parole", None, "aigu-telephone"],
                          "moyenne": vec(), "maj": 1.0})
    E._ecrire(E.SALLE, {"ts": 5.0, "dernier": "voix 50", "voix": [{"nom": "voix 50", "c": vec(), "n": 3, "m": 0}],
                        "candidates": [{"nom": "voix 51", "c": vec(), "n": 1, "m": 0, "parole": []}]})
    avant = {f: f.read_bytes() for f in (E.CONNUES, E.FICHIER, E.SALLE)}
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[], _mtime=None, _fichier=None)
    reg = E.registre_voix()                                # le premier chargement : la migration
    m = reg["migration"]
    sauve = Path(m["sauvegarde"])
    assert sorted(p.name for p in sauve.iterdir()) == sorted(f.name for f in avant)
    assert all((sauve / f.name).read_bytes() == b for f, b in avant.items()), "la sauvegarde : les fichiers tels qu'ils étaient"
    assert oct(sauve.stat().st_mode & 0o777) == "0o700" and oct((tmp_path / "voix-signatures.json").stat().st_mode & 0o777) == "0o600"
    assert E.FICHIER.read_bytes() == avant[E.FICHIER] and E.SALLE.read_bytes() == avant[E.SALLE], "ni l'empreinte ni la salle ne sont réécrites"
    # chaque voix nommée : une personne, sa moyenne et son nombre de fois intacts, un numéro neuf au-dessus de la salle (50, 51)
    for x in anciennes:
        sig = S.signature(reg, x["nom"])
        assert len(sig) == 1 and sig[0]["voix"] > 51 and sig[0]["fois"] == x["n"] and sig[0]["force"] == S.FORCE_MIGREE
        assert reg["voix"][str(sig[0]["voix"])]["c"] == x["moyenne"] and reg["voix"][str(sig[0]["voix"])]["n"] == x["n"]
    # papa : sa voix 1 (son empreinte, ses 6 échantillons) et une voix par registre de son geste ou de sa calibration
    sp = {x["registre"] or "": x for x in S.signature(reg, "papa")}
    assert set(sp) == {"", "chant", "parole", "aigu-telephone"} and sp[""]["voix"] == 1 and sp[""]["fois"] == 6
    assert sp["chant"]["fois"] == 2 and all(x["force"] == 1.0 for x in sp.values())
    assert sorted(S.resume(reg)["verifiees"]) == sorted(x["voix"] for x in sp.values())
    # la vue (voix-connues.json) garde les mêmes noms, moyennes et fois (le cockpit n'y lit que les noms)
    vue = {x["nom"]: x for x in json.loads(E.CONNUES.read_text())}
    assert {n: (x["moyenne"], x["n"]) for n, x in vue.items()} == {x["nom"]: (x["moyenne"], x["n"]) for x in anciennes}
    # une seule fois : relu, pas re-migré ; aucune deuxième sauvegarde
    S._cache.clear()
    assert E.registre_voix()["migration"]["ts"] == m["ts"] and len(list(tmp_path.glob("voix-signatures-sauvegarde-*"))) == 1
    # un processus encore à l'ancien code qui nomme une voix (il écrit voix-connues.json) : le nom entre au registre
    vue2 = json.loads(E.CONNUES.read_text()) + [{"nom": "Kamel", "moyenne": vec(), "n": 2, "cree": 9.0}]
    time.sleep(0.01)
    E._ecrire(E.CONNUES, vue2)
    assert S.signature(E.registre_voix(), "Kamel")[0]["fois"] == 2


def test_la_migration_garde_les_numeros_de_la_conversation(tmp_path, monkeypatch):
    """Aucune voix de la conversation en cours ne change de numéro ; la suivante prend le numéro au-dessus de tout."""
    _isoler(tmp_path, monkeypatch, connues=[{"nom": "Nora", "moyenne": np.round(V["ali"], 5).tolist(), "n": 37, "cree": 1.0}])
    E._salle.update(voix=[{"nom": "voix 223", "c": V["inconnu"], "n": 4, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    S._cache.clear()
    (tmp_path / "voix-signatures.json").unlink(missing_ok=True)
    reg = E.registre_voix()
    assert S.signature(reg, "Nora")[0]["voix"] == 224
    assert E._prochain_numero() == "voix 225"
    assert E.etiqueter_bloc(_audio("inconnu"), "re", maintenant=time.time())["texte"] == "[voix 223] re"


def test_un_registre_illisible_ne_fait_perdre_ni_papa_ni_le_fichier(tmp_path, monkeypatch):
    """Un registre abîmé : papa reste reconnu par son empreinte (comme avant le 10/11), rien n'est écrit par-dessus, les gestes refusent."""
    _isoler(tmp_path, monkeypatch)
    E.registre_voix()
    f = tmp_path / "voix-signatures.json"
    f.write_text("{abîmé")
    S._cache.clear()
    p = E.etiqueter_bloc(_audio("papa"), "salam fiston", maintenant=time.time())
    assert p["texte"] == "salam fiston" and p["voix"]["verdict"] == "ahmed"
    assert "illisible" in E.signature_geste({"action": "ajouter", "personne": "Ali", "voix": "3"})["erreur"]
    assert f.read_text() == "{abîmé", "jamais réécrit sans un geste qui le relit"


def test_l_oreille_des_voix_sert_les_gestes_de_la_page(tmp_path, monkeypatch):
    """Le cockpit passe par l'oreille des voix (op « signature ») ; son « id » est celui de la demande, jamais celui d'une proposition."""
    _isoler(tmp_path, monkeypatch, connues=[{"nom": "Ali", "moyenne": np.round(V["ali"], 5).tolist(), "n": 5, "cree": 1.0}])
    E._salle.update(voix=[{"nom": "voix 33", "c": V["v127"], "n": 3, "m": 0}], ts=time.time(), dernier=None, candidates=[])
    E._sauver_salle()
    p = E.proposer_signature("ajouter", "Ali", "33")
    r = O.repondre({"id": 7, "op": "signature", "action": "valider", "proposition": p["id"]})
    assert r.get("ok") and r["propositions"] == [] and 33 in [x["voix"] for x in S.signature(E.registre_voix(), "Ali")]
    r = O.repondre({"id": 8, "op": "signature", "action": "ajouter", "personne": "papa", "voix": "33"})
    assert r.get("presence") is True and "erreur" in r
    v = O.repondre({"id": 9, "op": "signature"})
    assert v["ok"] and [x["nom"] for x in v["personnes"]] == ["papa", "Ali"] and v["partagees"] == []
