"""L'empreinte vocale d'Ahmed (jarvis/empreinte_vocale.py, point 18 ; accord d'Ahmed le 2026-10-20) : un indice,
jamais une autorisation. Le modèle ONNX est remplacé ici par un faux déterministe (pas de téléchargement)."""
import sys
from pathlib import Path

import time

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import empreinte_vocale as E  # noqa: E402


def test_fbank_a_la_kaldi_forme_et_moyenne():
    t = np.arange(16000 * 2) / 16000
    f = E.fbank(0.1 * np.sin(2 * np.pi * 440 * t))
    assert f.shape == (1 + (32000 - 400) // 160, 80)
    assert abs(float(f.mean(axis=0).mean())) < 1e-4                     # moyenne retirée (CMN)
    assert E.fbank(np.zeros(100)).shape == (0, 80)                       # trop court


def test_apprendre_puis_reconnaitre(tmp_path, monkeypatch):
    voix = {"ahmed": np.ones(256), "autre": np.r_[np.ones(128), -np.ones(128)]}
    monkeypatch.setattr(E, "embedding", lambda a: voix[a] / np.linalg.norm(voix[a]))
    f = tmp_path / "empreinte.json"
    assert E.reconnaitre("ahmed", fichier=f) is None                     # rien d'appris
    E.apprendre("ahmed", fichier=f)
    assert E.reconnaitre("ahmed", fichier=f) is None                     # un seul échantillon : pas assez
    assert E.apprendre("ahmed", fichier=f) == 2
    assert E.reconnaitre("ahmed", fichier=f)["verdict"] == "ahmed"
    assert E.reconnaitre("autre", fichier=f)["verdict"] == "autre"
    assert oct(f.stat().st_mode & 0o777) == "0o600" and "ahmed" not in f.read_text()


def test_plusieurs_voix_dans_un_message(tmp_path, monkeypatch):
    """Ahmed, puis son pote, puis une 3e personne, puis Ahmed : chacun reconnu, le texte étiqueté."""
    base = {"ahmed": np.r_[np.ones(128), np.zeros(128)], "pote": np.r_[np.zeros(128), np.ones(128)],
            "troisieme": np.r_[np.ones(64), -np.ones(64), np.ones(64), -np.ones(64)]}
    vec = lambda k: base[k] / np.linalg.norm(base[k])
    f = tmp_path / "empreinte.json"
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("ahmed"))
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    # l'audio : 4 segments de 2 s ; le faux modèle lit la voix dans le premier échantillon du segment
    voix = ["ahmed", "pote", "troisieme", "ahmed"]
    audio = np.concatenate([np.full(32000, i, dtype=np.float32) for i in range(4)])
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(voix[int(a[0])]))
    E._salle.update(voix=[], ts=0.0, dernier=None)
    segs = [{"start": 2 * i, "end": 2 * i + 2, "text": t} for i, t in enumerate(["salut Hakim", "il dit quoi lui", "moi aussi je veux parler", "laisse tomber"])]
    texte, r = E.etiqueter(audio, segs, fichier=f, maintenant=1000.0)
    assert texte == "salut Hakim [voix 2] il dit quoi lui [voix 3] moi aussi je veux parler [papa] laisse tomber"   # (03/11) « papa »
    assert r["plusieurs"] and r["voix"] == ["Ahmed", "voix 2", "voix 3"]
    # le morceau suivant du même tour (transcription en continu) : la voix 2 est reconnue comme la même
    voix2 = ["pote"]
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(voix2[0]))
    texte2, _ = E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "ouais"}], nouveau_tour=False, fichier=f, maintenant=1010.0)
    assert texte2 == "[voix 2] ouais"


def test_une_voix_nommee_est_gardee_pour_toujours(tmp_path, monkeypatch):
    monkeypatch.setattr(E, "SALLE", tmp_path / "salle.json")
    monkeypatch.setattr(E, "CONNUES", tmp_path / "connues.json")
    ahmed = np.r_[np.ones(128), np.zeros(128)] / np.sqrt(128)
    pote = np.r_[np.zeros(128), np.ones(128)] / np.sqrt(128)
    f = tmp_path / "ahmed.json"
    monkeypatch.setattr(E, "embedding", lambda a, *x: ahmed)
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    monkeypatch.setattr(E, "embedding", lambda a, *x: pote)
    E._salle.update(voix=[], ts=0.0, dernier=None)
    texte, _ = E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "salam"}], fichier=f, maintenant=1000.0)
    assert texte == "[voix 2] salam"
    assert E.nommer("voix 2", "Karim", maintenant=1000.0) == "Karim"
    # bien plus tard (un autre jour, la salle oubliée) : Karim est reconnu par son nom
    E._salle.update(voix=[], ts=0.0, dernier=None)
    texte2, r = E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "c'est encore moi"}],
                            fichier=f, maintenant=1000.0 + 30 * 86400)
    assert texte2 == "[Karim] c'est encore moi" and r["voix"] == ["Karim"]
    assert E.oublier("Karim") == 1 and E.connues() == []


def test_nommer_avec_le_numero_seul(tmp_path, monkeypatch):
    """(Ahmed, 2026-10-20 : « il n'arrive pas à enregistrer le nom de la voix ») Hakim passait « 10 » pour « voix 10 »."""
    monkeypatch.setattr(E, "SALLE", tmp_path / "salle.json")
    monkeypatch.setattr(E, "CONNUES", tmp_path / "connues.json")
    E._salle.update(voix=[{"nom": f"voix {k}", "c": _unit(np.eye(256)[k]), "n": 3} for k in (2, 10)], ts=time.time(), dernier="voix 10")
    E._sauver_salle()
    for numero, nom in (("10", "Nora"), ("Voix 2", "Karim")):
        assert E.nommer(numero, nom) == nom
    assert sorted(x["nom"] for x in E.connues()) == ["Karim", "Nora"] and E._salle["dernier"] == "Nora"
    with pytest.raises(ValueError, match="voix présentes"):
        E.nommer("voix 99", "Personne")


def _unit(x):
    x = np.asarray(x, dtype=float)
    return x / np.linalg.norm(x)


def test_calibration_par_registres(tmp_path, monkeypatch):
    """(2026-10-20) Ahmed plus aigu depuis son téléphone : 0,04 à 0,47 au lieu de 0,6-0,8. Ses registres appris en
    calibration guidée, sa phrase aiguë est reconnue ; hors calibration, un registre si éloigné n'est pas appris."""
    rng = np.random.default_rng(0)
    normal = _unit(rng.normal(size=256))
    autre_dir = _unit(rng.normal(size=256))
    aigu = _unit(normal * 0.25 + autre_dir)                      # proche de sa voix, mais loin de sa moyenne
    vecs = {"normal": normal, "aigu": aigu}
    monkeypatch.setattr(E, "embedding", lambda a, *x: vecs[a])
    f = tmp_path / "empreinte.json"
    E.apprendre("normal", fichier=f); E.apprendre("normal", fichier=f)
    assert E.reconnaitre("aigu", fichier=f)["verdict"] != "ahmed"
    assert E.apprendre("aigu", fichier=f) is None                 # sans calibration : pris pour une autre voix
    assert E.apprendre("aigu", fichier=f, registre="aigu-telephone", guide=True) == 3
    assert E.apprendre("aigu", fichier=f, registre="aigu-telephone", guide=True) == 4
    assert E.reconnaitre("aigu", fichier=f)["verdict"] == "ahmed"
    assert E.etat(fichier=f)["registres"] == {"aigu-telephone": 2}


def test_registre_inhabituel_plus_proche_de_lui_que_des_autres(tmp_path, monkeypatch):
    """Une phrase d'Ahmed sous le seuil (registre inhabituel) mais bien plus proche de lui que de toute voix entendue :
    c'est lui, pas une « voix 3 »."""
    monkeypatch.setattr(E, "SALLE", tmp_path / "salle.json")
    rng = np.random.default_rng(1)
    ahmed, pote, bruit = (_unit(rng.normal(size=256)) for _ in range(3))
    inhabituel = _unit(ahmed * 0.45 + bruit * 0.9)               # ~0,45 avec lui
    vecs = [ahmed, ahmed, pote, inhabituel]
    f = tmp_path / "empreinte.json"
    monkeypatch.setattr(E, "embedding", lambda a, *x: ahmed)
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vecs[int(a[0])])
    E._salle.update(voix=[], ts=0.0, dernier=None)
    audio = np.concatenate([np.full(32000, i, dtype=np.float32) for i in range(4)])
    segs = [{"start": 2 * i, "end": 2 * i + 2, "text": t} for i, t in enumerate(["salut", "ça va", "wesh", "trop bien frérot !"])]
    texte, r = E.etiqueter(audio, segs, fichier=f, maintenant=2000.0)
    assert "[voix 3]" not in texte and texte.endswith("[papa] trop bien frérot !")


def test_reinitialiser_avec_sauvegarde(tmp_path, monkeypatch):
    rng = np.random.default_rng(2)
    vecs = {k: _unit(rng.normal(size=256)) for k in ("a", "b", "c")}
    monkeypatch.setattr(E, "embedding", lambda a, *x: vecs[a])
    f = tmp_path / "empreinte.json"
    E.apprendre("a", fichier=f); E.apprendre("a", fichier=f)
    E.apprendre("b", fichier=f, registre="aigu-mac", guide=True)
    E.apprendre("c", fichier=f, registre="vite-telephone", guide=True)
    r = E.reinitialiser("calibration-mac", fichier=f)
    assert (r["avant"], r["apres"]) == (4, 3) and Path(r["sauvegarde"]).exists()
    assert E.etat(fichier=f)["registres"] == {"vite-telephone": 1}
    E.reinitialiser("calibration", fichier=f)
    assert E.etat(fichier=f) == {"echantillons": 2, "registres": {}, "modele": E.MODELE.exists()}
    assert E.reconnaitre("a", fichier=f)["verdict"] == "ahmed"            # sa voix ordinaire reste apprise
    E.reinitialiser("tout", fichier=f)
    assert E.etat(fichier=f)["echantillons"] == 0 and E.reconnaitre("a", fichier=f) is None
    assert len(list(tmp_path.glob("empreinte.sauvegarde-*.json"))) >= 1


def test_renommer_une_voix_connue_garde_son_empreinte(tmp_path, monkeypatch):
    """(29/10, Ahmed : « tu la renommes, Inconnu et pas Machine à café ») sans outil pour renommer, Hakim a dû oublier
    la voix, et son empreinte avec."""
    monkeypatch.setattr(E, "CONNUES", tmp_path / "connues.json")
    cafe, karim = np.round(_unit(np.eye(256)[3]), 5).tolist(), np.round(_unit(np.eye(256)[7]), 5).tolist()
    E._ecrire(E.CONNUES, [{"nom": "Machine à café", "moyenne": cafe, "n": 4, "cree": 1.0},
                          {"nom": "Karim", "moyenne": karim, "n": 9, "cree": 2.0}])
    assert E.renommer(" machine à café ", "Inconnu") == "Inconnu"
    k = {x["nom"]: x for x in E.connues()}
    assert set(k) == {"Inconnu", "Karim"} and k["Inconnu"]["moyenne"] == cafe and k["Inconnu"]["n"] == 4
    assert E.renommer("inconnu", "INCONNU") == "INCONNU"                 # sa propre casse : permis
    with pytest.raises(ValueError, match="existe déjà"):
        E.renommer("INCONNU", "karim")
    with pytest.raises(ValueError, match="Ahmed"):
        E.renommer("Karim", "Ahmed")
    with pytest.raises(ValueError, match="voix connues : INCONNU, Karim"):
        E.renommer("Personne", "X")
    assert sorted(x["nom"] for x in E.connues()) == ["INCONNU", "Karim"]


def test_micro_ouvert_mot_a_mot_et_sa_propre_voix(tmp_path, monkeypatch):
    """(03/11, Ahmed : « micro ouvert ; si plusieurs voix se mélangent, il doit pouvoir séparer chaque voix selon le timbre »)
    avec les mots datés, chaque mot va à la voix dont le timbre couvre son instant, même au milieu d'une phrase ; et sa
    PROPRE voix (apprise de ce qu'il dit) est reconnue et mise de côté : ce n'est pas papa qui parle"""
    base = {"ahmed": np.r_[np.ones(128), np.zeros(128)], "pote": np.r_[np.zeros(128), np.ones(128)],
            "hakim": np.r_[np.ones(64), -np.ones(64), np.ones(64), -np.ones(64)]}
    vec = lambda k: base[k] / np.linalg.norm(base[k])
    f, moi = tmp_path / "empreinte.json", tmp_path / "moi.json"
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("ahmed"))
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("hakim"))
    for _ in range(3):
        E.apprendre_moi("x", fichier=moi)
    voix = ["ahmed", "pote", "hakim"]
    # 9 s : papa 0-3 s, son pote 3-6 s, puis l'écho de Hakim 6-9 s ; UN seul segment de Whisper, les mots datés
    audio = np.concatenate([np.full(48000, i, dtype=np.float32) for i in range(3)])
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(voix[int(a[0])]))
    E._salle.update(voix=[], ts=0.0, dernier=None)
    mots = [(" salut", 0.2, 0.6), (" Hakim", 0.7, 1.2), (" regarde", 1.4, 2.6), (" non", 3.3, 3.6), (" attends", 3.8, 4.4),
            (" frérot", 4.6, 5.6), (" oui", 6.3, 6.6), (" papa", 6.8, 8.5)]
    segs = [{"start": 0.0, "end": 9.0, "text": "salut Hakim regarde non attends frérot oui papa",
             "words": [{"word": w, "start": a, "end": b} for w, a, b in mots]}]
    texte, r = E.etiqueter(audio, segs, fichier=f, moi=moi, maintenant=1000.0)
    assert texte == "salut Hakim regarde [voix 2] non attends frérot"
    assert r["voix"] == ["Ahmed", "voix 2"] and r["moi"] == "oui papa"
    # tout le morceau dans sa voix : rien de papa
    texte2, r2 = E.etiqueter(np.full(48000, 2, dtype=np.float32), [{"start": 0, "end": 3, "text": "je regarde"}],
                             fichier=f, moi=moi, maintenant=1001.0)
    assert texte2 == "" and r2["moi"] == "je regarde"


def test_ses_voix_temporaires_rattachees_a_papa_sauf_la_musique(tmp_path, monkeypatch):
    """(03/11, Ahmed via Hakim : « toutes ces voix temporaires, voix 56, 63, 64…, c'est moi, surtout quand je chante : un seul
    registre, papa ») ses voix de la salle rattachées à son empreinte (registre « chant »), sauf celles nées sous la musique"""
    base = {"ahmed": np.r_[np.ones(128), np.zeros(128)], "chant": np.r_[np.zeros(128), np.ones(128)],
            "radio": np.r_[np.ones(64), -np.ones(64), np.ones(64), -np.ones(64)]}
    vec = lambda k: base[k] / np.linalg.norm(base[k])
    f, salle = tmp_path / "empreinte.json", tmp_path / "salle.json"
    monkeypatch.setattr(E, "SALLE", salle)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("ahmed"))
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    E._salle.update(voix=[], ts=0.0, dernier=None)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("chant"))
    E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "la la la"}], fichier=f, maintenant=1000.0)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("radio"))
    E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "baby baby"}], fichier=f, maintenant=1001.0,
                musique=True)
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 2", "voix 3"]
    r = E.rattacher_a_papa("toutes", registre="chant", fichier=f, maintenant=1002.0)
    assert r["rattachees"] == ["voix 2"] and r["ecartees_musique"] == ["voix 3"]
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 3"]
    assert E.etat(f)["registres"] == {"chant": 1}
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("chant"))
    texte, _ = E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "encore"}], fichier=f, maintenant=1003.0)
    assert texte in ("encore", "[papa] encore"), "sa voix chantée est maintenant la sienne"


def test_son_subconscient_reconnait_apprend_et_doute(tmp_path, monkeypatch):
    """(03/11, Ahmed : « la reconnaissance du premier abord est consciente ; puis le tri et la reconnaissance se font dans le
    subconscient, qui envoie juste le nom de celui qui parle, ou son doute entre qui et qui ; plus les voix parlent, plus il
    note que c'est moi ») une voix sûre enrichit seule son empreinte ; deux voix trop proches : « [papa ou Ali ?] »"""
    rng = np.random.default_rng(3)
    base_papa, base_ali = rng.normal(0, 1, 256), rng.normal(0, 1, 256)
    vec = lambda b, bruit=0.0: (lambda x: x / np.linalg.norm(x))(b + bruit * rng.normal(0, 1, 256))
    f, connues = tmp_path / "empreinte.json", tmp_path / "connues.json"
    monkeypatch.setattr(E, "CONNUES", connues)
    monkeypatch.setattr(E, "SALLE", tmp_path / "salle.json")
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(base_papa))
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    import json as _j
    connues.write_text(_j.dumps([{"nom": "Ali", "moyenne": vec(base_ali).round(5).tolist(), "n": 3, "cree": 0}]))
    E._salle.update(voix=[], ts=0.0, dernier=None)
    E._appris.clear()
    # papa, bien reconnu : son empreinte s'enrichit seule (une fois toutes les 2 min au plus)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(base_papa, 0.3))
    avant = E.etat(f)["echantillons"]
    E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "salut"}], fichier=f, maintenant=1000.0)
    assert E.etat(f)["echantillons"] == avant + 1 and E.etat(f)["registres"].get("appris seul") == 1
    E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "encore"}], fichier=f, maintenant=1010.0)
    assert E.etat(f)["echantillons"] == avant + 1, "pas plus d'une fois toutes les 2 min"
    # une voix entre papa et Ali : le doute, avec les deux noms
    milieu = vec(base_papa + base_ali)
    monkeypatch.setattr(E, "embedding", lambda a, *x: milieu)
    texte, r = E.etiqueter(np.zeros(32000, dtype=np.float32), [{"start": 0, "end": 2, "text": "c'est qui"}], fichier=f, maintenant=1200.0)
    assert texte == "[papa ou Ali ?] c'est qui" and r["doute"] == ["papa ou Ali ?"]
