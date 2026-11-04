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
    # l'audio : 4 segments de 4 s (04/11 : une voix inconnue n'est une personne qu'après 4 s de parole) ; le faux modèle lit
    # la voix dans le premier échantillon du segment
    voix = ["ahmed", "pote", "troisieme", "ahmed"]
    audio = np.concatenate([np.full(64000, i, dtype=np.float32) for i in range(4)])
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(voix[int(a[0])]))
    E._salle.update(voix=[], ts=0.0, dernier=None)
    segs = [{"start": 4 * i, "end": 4 * i + 4, "text": t} for i, t in enumerate(["salut Hakim", "il dit quoi lui", "moi aussi je veux parler", "laisse tomber"])]
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
    texte, _ = E.etiqueter(np.zeros(64000, dtype=np.float32), [{"start": 0, "end": 4, "text": "salam"}], fichier=f, maintenant=1000.0)
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
    durees, debuts = [2, 2, 4, 2], [0, 2, 4, 8]                  # (04/11) le pote parle 4 s : une vraie voix de la salle
    audio = np.concatenate([np.full(d * 16000, i, dtype=np.float32) for i, d in enumerate(durees)])
    segs = [{"start": a, "end": a + d, "text": t} for a, d, t in zip(debuts, durees, ["salut", "ça va", "wesh", "trop bien frérot !"])]
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
    # 11 s : papa 0-3 s, son pote 3-8 s (04/11 : 4 s au moins pour être une personne), puis l'écho de Hakim 8-11 s ; UN seul
    # segment de Whisper, les mots datés
    audio = np.concatenate([np.full(n, i, dtype=np.float32) for i, n in enumerate((48000, 80000, 48000))])
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec(voix[int(a[0])]))
    E._salle.update(voix=[], ts=0.0, dernier=None)
    mots = [(" salut", 0.2, 0.6), (" Hakim", 0.7, 1.2), (" regarde", 1.4, 2.6), (" non", 3.3, 3.6), (" attends", 3.8, 4.4),
            (" frérot", 4.6, 7.6), (" oui", 9.3, 9.6), (" papa", 9.8, 10.6)]
    segs = [{"start": 0.0, "end": 11.0, "text": "salut Hakim regarde non attends frérot oui papa",
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
    E.etiqueter(np.zeros(64000, dtype=np.float32), [{"start": 0, "end": 4, "text": "la la la"}], fichier=f, maintenant=1000.0)
    monkeypatch.setattr(E, "embedding", lambda a, *x: vec("radio"))
    E.etiqueter(np.zeros(64000, dtype=np.float32), [{"start": 0, "end": 4, "text": "baby baby"}], fichier=f, maintenant=1001.0,
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


# ---- (04/11, Ahmed : « que son attention s'étale sur plusieurs minutes ») des voix PROVISOIRES : mesuré de 13 h à 14 h 45,
# 16 messages sur 216 étiquetés « [voix N] », 15 numéros différents, dont au moins un de papa lui-même. Une voix inconnue
# n'est qu'une candidate tant qu'elle n'a pas parlé 4 s dans les 5 dernières minutes. ----

def _blocs():
    """Quatre timbres orthogonaux : papa, son pote, un inconnu, un autre."""
    return {k: _unit(np.eye(4)[i].repeat(64)) for i, k in enumerate(("ahmed", "pote", "inconnu", "autre"))}


def _papa_appris(tmp_path, monkeypatch, ahmed):
    f = tmp_path / "empreinte.json"
    monkeypatch.setattr(E, "embedding", lambda a, *x: ahmed)
    E.apprendre("x", fichier=f); E.apprendre("x", fichier=f)
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[])
    E._appris.clear()
    return f, tmp_path / "moi-absent.json"


def _dire(monkeypatch, f, moi, t, morceaux, nouveau_tour=True):
    """morceaux : [(vecteur, secondes, texte)], un segment de Whisper chacun (sans mots datés) ; le faux modèle lit la voix
    dans le premier échantillon du segment."""
    audio = np.concatenate([np.full(int(s * E.TAUX), i, dtype=np.float32) for i, (_, s, _) in enumerate(morceaux)])
    monkeypatch.setattr(E, "embedding", lambda a, *x: morceaux[int(a[0])][0])
    segs, debut = [], 0.0
    for _, s, texte in morceaux:
        segs.append({"start": debut, "end": debut + s, "text": texte})
        debut += s
    return E.etiqueter(audio, segs, nouveau_tour=nouveau_tour, fichier=f, moi=moi, maintenant=t)


def test_une_voix_inconnue_de_2_s_reste_a_la_voix_d_avant(tmp_path, monkeypatch):
    v = _blocs()
    f, moi = _papa_appris(tmp_path, monkeypatch, v["ahmed"])
    texte, r = _dire(monkeypatch, f, moi, 1000.0, [(v["ahmed"], 2, "salut Hakim"), (v["inconnu"], 2, "c'est qui lui")])
    assert texte == "salut Hakim c'est qui lui" and r["voix"] == ["Ahmed"]
    assert E._salle["voix"] == [] and len(E._salle["candidates"]) == 1
    # la voix d'avant est la voix 2 (son pote, déjà une voix de la salle) : les 2 s d'une autre inconnue restent à elle
    E._salle["voix"].append({"nom": "voix 2", "c": v["pote"], "n": 5, "m": 0})
    texte, r = _dire(monkeypatch, f, moi, 1010.0, [(v["pote"], 2, "ouais"), (v["autre"], 2, "hmm")])
    assert texte == "[voix 2] ouais hmm" and r["voix"] == ["voix 2"]
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 2"] and len(E._salle["candidates"]) == 2


def test_la_meme_voix_revenue_jusqu_a_4_s_devient_voix_n(tmp_path, monkeypatch):
    rng = np.random.default_rng(4)
    v = _blocs()
    f, moi = _papa_appris(tmp_path, monkeypatch, v["ahmed"])
    proche = lambda k: _unit(v[k] + 0.3 * _unit(rng.normal(size=256)))     # la même voix, jamais tout à fait le même vecteur
    assert _dire(monkeypatch, f, moi, 1000.0, [(v["ahmed"], 2, "salut"), (proche("inconnu"), 2, "bonjour")])[0] == "salut bonjour"
    assert _dire(monkeypatch, f, moi, 1060.0, [(proche("inconnu"), 1.5, "je disais")])[0] == "je disais"     # 3,5 s
    texte, r = _dire(monkeypatch, f, moi, 1120.0, [(proche("inconnu"), 1.0, "voilà")])                       # 4,5 s
    assert texte == "[voix 2] voilà" and r["voix"] == ["voix 2"]
    assert [(x["nom"], x["n"]) for x in E._salle["voix"]] == [("voix 2", 3)] and E._salle["candidates"] == []
    assert _dire(monkeypatch, f, moi, 1130.0, [(proche("inconnu"), 1.0, "encore")])[0] == "[voix 2] encore"
    # dans un même message : 2 s puis 2 s d'une autre voix ; la confirmation arrive au 2e segment
    texte, _ = _dire(monkeypatch, f, moi, 1200.0, [(v["ahmed"], 2, "bon"), (proche("autre"), 2, "moi je"),
                                                   (proche("autre"), 2, "pense que non")])
    assert texte == "bon moi je [voix 3] pense que non"


def test_une_candidate_est_oubliee_apres_5_min(tmp_path, monkeypatch):
    import json
    v = _blocs()
    f, moi = _papa_appris(tmp_path, monkeypatch, v["ahmed"])
    _dire(monkeypatch, f, moi, 1000.0, [(v["inconnu"], 2, "euh")])
    assert len(E._salle["candidates"]) == 1
    _dire(monkeypatch, f, moi, 1301.0, [(v["ahmed"], 2, "bon")])                   # plus de 5 min sans rien : oubliée
    assert E._salle["candidates"] == [] and json.loads(E.SALLE.read_text())["candidates"] == []
    assert _dire(monkeypatch, f, moi, 1302.0, [(v["inconnu"], 2, "re")])[0] == "re"      # elle repart de zéro
    assert E._salle["voix"] == []
    # 4 s dans les 5 DERNIÈRES minutes : 1,5 s toutes les 200 s n'y arrivent jamais (4,5 s en tout, 3 s au plus en 5 min)
    for k, t in enumerate((2000.0, 2200.0, 2400.0)):
        assert _dire(monkeypatch, f, moi, t, [(v["autre"], 1.5, f"bout {k}")])[0] == f"bout {k}"
    assert E._salle["voix"] == []


def test_papa_seul_ne_cree_jamais_de_voix(tmp_path, monkeypatch):
    """papa qui parle 4 min, sa voix jamais tout à fait la même, une fois sur trois dans un registre inhabituel (~0,45) :
    ni voix N, ni candidate."""
    rng = np.random.default_rng(5)
    base = rng.normal(size=256)
    f, moi = _papa_appris(tmp_path, monkeypatch, _unit(base))
    u = _unit(base)
    for k in range(30):
        papa = _unit(base + 0.6 * rng.normal(size=256))
        ailleurs = rng.normal(size=256)
        ailleurs = _unit(ailleurs - np.dot(ailleurs, u) * u)                  # orthogonal à sa voix : ~0,45 avec lui, sans hasard
        inhabituel = _unit(u * 0.45 + ailleurs * 0.9)
        texte, r = _dire(monkeypatch, f, moi, 1000.0 + 10 * k, [(papa, 4, f"phrase {k}"), (inhabituel if k % 3 == 0 else papa, 4, "suite")])
        assert texte == f"phrase {k} suite" and r["voix"] == ["Ahmed"], texte
    assert E._salle["voix"] == [] and E._salle["candidates"] == []


def test_le_fichier_de_salle_ancien_se_relit_et_les_candidates_survivent(tmp_path, monkeypatch):
    import json
    v = _blocs()
    f, moi = _papa_appris(tmp_path, monkeypatch, v["ahmed"])
    # un fichier d'avant le 04/11 : pas de clé « candidates »
    E._ecrire(E.SALLE, {"ts": 1000.0, "dernier": None, "voix": [{"nom": "voix 7", "c": np.round(v["pote"], 5).tolist(), "n": 4}]})
    E._salle.update(voix=[], ts=0.0, dernier=None)
    assert _dire(monkeypatch, f, moi, 1100.0, [(v["pote"], 2, "me revoilà")])[0] == "[voix 7] me revoilà"
    assert E._salle["candidates"] == []
    # une candidate gardée dans le fichier : après une relance du service de voix, ses 2 s comptent encore
    _dire(monkeypatch, f, moi, 1200.0, [(v["inconnu"], 2, "euh")])
    assert json.loads(E.SALLE.read_text())["candidates"][0]["parole"] == [[1200.0, 2.0]]
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[])          # la relance : la mémoire vide, le fichier reste
    assert _dire(monkeypatch, f, moi, 1230.0, [(v["inconnu"], 2, "je disais")])[0] == "[voix 8] je disais"


def test_mot_a_mot_une_candidate_laisse_ses_mots_a_la_voix_d_avant(tmp_path, monkeypatch):
    """Au milieu d'une phrase de papa, 3 s d'une voix inconnue (4 fenêtres de 0,75 s) : pas encore une personne ; ses mots
    vont à la voix qui parlait juste avant dans la phrase (papa), pas à celle du morceau d'avant (la voix 2)."""
    v = _blocs()
    f, moi = _papa_appris(tmp_path, monkeypatch, v["ahmed"])
    E._salle.update(voix=[{"nom": "voix 2", "c": v["pote"], "n": 5, "m": 0}], ts=990.0, dernier="voix 2", candidates=[])
    voix = [v["ahmed"], v["inconnu"], v["ahmed"]]
    audio = np.concatenate([np.full(48000, i, dtype=np.float32) for i in range(3)])
    monkeypatch.setattr(E, "embedding", lambda a, *x: voix[int(a[0])])
    mots = [(" salut", 0.2, 0.6), (" Hakim", 0.7, 1.2), (" regarde", 1.4, 2.6), (" non", 3.3, 3.6), (" attends", 3.8, 4.4),
            (" frérot", 4.6, 5.6), (" bon", 6.3, 6.6), (" ok", 6.8, 8.5)]
    segs = [{"start": 0.0, "end": 9.0, "text": "salut Hakim regarde non attends frérot bon ok",
             "words": [{"word": w, "start": a, "end": b} for w, a, b in mots]}]
    texte, r = E.etiqueter(audio, segs, nouveau_tour=False, fichier=f, moi=moi, maintenant=1000.0)
    assert texte == "[papa] salut Hakim regarde non attends frérot bon ok" and r["voix"] == ["Ahmed"]
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 2"]
    assert [k["parole"] for k in E._salle["candidates"]] == [[[1000.0, 3.0]]]
