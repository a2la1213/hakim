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
    assert texte == "salut Hakim [voix 2] il dit quoi lui [voix 3] moi aussi je veux parler [Ahmed] laisse tomber"
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
    assert "[voix 3]" not in texte and texte.endswith("[Ahmed] trop bien frérot !")


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
