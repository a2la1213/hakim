"""(09/11, Ahmed, 19:29-19:32 : « que tu dissocies ce que disent les autres de mes paroles » ; « reconnaître les signatures vocales en temps
réel pendant le live, et pouvoir les enregistrer à la volée ») l'oreille des voix (jarvis/oreille_voix.py) et le chemin Azure
(empreinte_vocale.etiqueter_bloc). Le modèle ONNX est remplacé par un faux déterministe : la voix est lue dans le premier échantillon
de chaque fenêtre."""
import json
import os
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import empreinte_vocale as E  # noqa: E402
import oreille_voix as O  # noqa: E402

BASE = {"papa": np.r_[np.ones(128), np.zeros(128)], "live": np.r_[np.zeros(128), np.ones(128)],
        "invite": np.r_[np.ones(64), -np.ones(64), np.ones(64), -np.ones(64)], "hakim": np.r_[np.ones(64), np.zeros(128), -np.ones(64)],
        "melange": np.tile([1.0, -1.0], 128)}
CODES = ["papa", "live", "invite", "hakim", "melange"]


def vec(k):
    return BASE[k] / np.linalg.norm(BASE[k])


def audio(*voix, s=4.0):
    """Des morceaux de s secondes ; chaque échantillon porte le code de sa voix (+ 0,5 : jamais muet)."""
    return np.concatenate([np.full(int(s * 16000), CODES.index(v) + 0.5, dtype=np.float32) for v in voix])


def isoler(tmp_path, monkeypatch):
    for nom, f in [("SALLE", "salle.json"), ("CONNUES", "connues.json"), ("FICHIER", "empreinte.json"), ("MOI", "moi.json")]:
        monkeypatch.setattr(E, nom, tmp_path / f)
    E._salle.update(voix=[], ts=0.0, dernier=None, candidates=[], _mtime=None, _fichier=None)
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: vec("papa"))
    E.apprendre("x"); E.apprendre("x")
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: vec(CODES[int(np.asarray(a)[0])]) if len(a) >= 16000 else None)


def test_une_citation_du_live_n_est_jamais_papa(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    r = E.etiqueter_bloc(audio("live", s=2.0), "ولم يكن هناك", maintenant=1000.0)
    assert r["texte"] == "[voix 2] ولم يكن هناك"                  # son numéro temporaire, dès sa première phrase
    assert r["voix"]["verdict"] == "autre" and r["voix"]["locuteurs"] == ["voix 2"]
    # la même voix, plus tard : le même numéro ; papa ensuite : sans étiquette, reconnu
    assert E.etiqueter_bloc(audio("live", s=2.0), "خلي السيئة تشوف", maintenant=1010.0)["texte"] == "[voix 2] خلي السيئة تشوف"
    p = E.etiqueter_bloc(audio("papa", s=2.0), "Wesh fiston, tu m'entends ?", maintenant=1020.0)
    assert p["texte"] == "Wesh fiston, tu m'entends ?" and p["voix"]["verdict"] == "ahmed"


def test_temoin_sans_numero_temporaire_la_citation_passait_pour_papa(tmp_path, monkeypatch):
    """Le mécanisme coupé (numeroter=False, l'ancien etiqueter) : la candidate prête ses mots à papa (le doute du morceau entier la
    marque seulement « [papa ?] »). Ce test prouve que c'est bien le numéro temporaire qui sépare la citation de papa."""
    isoler(tmp_path, monkeypatch)
    vrai = E.etiqueter
    monkeypatch.setattr(E, "etiqueter", lambda *a, **k: vrai(*a, **{**k, "numeroter": False}))
    r = E.etiqueter_bloc(audio("live", s=2.0), "ولم يكن هناك", maintenant=1000.0)
    assert r["texte"] == "[papa ?] ولم يكن هناك"                   # prêtée à papa, seulement mise en doute : pas séparée
    assert r["voix"]["verdict"] == "autre"


def test_papa_puis_une_voix_de_la_piece_dans_le_meme_morceau(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    r = E.etiqueter_bloc(audio("papa", "invite"), "écoute bien fiston moi je viens de la boxe", maintenant=1000.0)
    assert r["texte"].startswith("écoute bien fiston") and "[voix 2]" in r["texte"]
    assert r["voix"]["verdict"] == "plusieurs"


def test_sa_propre_voix_reste_la_sienne(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    for _ in range(3):
        E.apprendre_moi_vecteur(vec("hakim"))
    r = E.etiqueter_bloc(audio("hakim", s=2.0), "Oui papa je suis là", maintenant=1000.0)
    assert r["texte"] == "" and r["moi"] == "Oui papa je suis là" and r["voix"]["verdict"] == "moi"


def test_nommer_une_voix_encore_candidate(tmp_path, monkeypatch):
    """« voix 2, c'est Nora » dès sa première phrase : plus besoin d'attendre ses 4 s de parole."""
    isoler(tmp_path, monkeypatch)
    E.etiqueter_bloc(audio("live", s=2.0), "salam tout le monde", maintenant=time.time())
    assert not E._salle["voix"] and E._salle["candidates"][0]["nom"] == "voix 2"
    assert E.nommer("2", "Nora") == "Nora"
    assert [x["nom"] for x in E.connues()] == ["Nora"]
    assert E.etiqueter_bloc(audio("live", s=2.0), "bonsoir", maintenant=time.time())["texte"] == "[Nora] bonsoir"


def test_la_salle_se_relit_quand_un_autre_processus_l_a_changee(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    E.etiqueter_bloc(audio("live", s=2.0), "salam", maintenant=time.time())
    d = json.loads(E.SALLE.read_text())
    d["voix"].append({"nom": "Rosa", "c": vec("invite").tolist(), "n": 3, "m": 0})   # l'outil voix_nommer, dans son processus
    time.sleep(0.01)
    E.SALLE.write_text(json.dumps(d))
    os.utime(E.SALLE, ns=(time.time_ns(), time.time_ns() + 10_000_000))
    assert E.etiqueter_bloc(audio("invite", s=2.0), "coucou", maintenant=time.time())["texte"] == "[Rosa] coucou"


def test_le_live_en_temps_reel_fenetre_par_fenetre(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    O._blocs.clear()
    t = time.time()
    bloc = audio("live", s=3.0)
    r1 = O.fenetres(bloc, cle="100", maintenant=t)
    assert r1["voix"] == ["voix 2"] and r1["nouvelles"] == ["voix 2"] and r1["fenetres"][0][:2] == [0.0, 1.5]
    # le même bloc, plus long : seules les fenêtres neuves ; une deuxième voix arrive, numérotée tout de suite
    r2 = O.fenetres(np.concatenate([bloc, audio("invite", s=3.0)]), cle="100", maintenant=t + 1.5)
    assert r2["fenetres"][0][0] >= 1.5 and "voix 3" in r2["voix"] and r2["nouvelles"] == ["voix 3"]
    assert all(f[0] >= 1.5 for f in r2["fenetres"])
    # papa au téléphone (un vocal) : reconnu, jamais numéroté
    assert O.fenetres(audio("papa", s=2.0), cle="200", maintenant=t + 3)["voix"] == ["papa"]


def test_pendant_une_musique_aucun_numero_neuf(tmp_path, monkeypatch):
    isoler(tmp_path, monkeypatch)
    O._blocs.clear()
    r = O.fenetres(audio("invite", s=3.0), cle="1", musique=True, maintenant=time.time())
    assert r["voix"] == [] and not E._salle.get("candidates")


def test_une_voix_qui_ressemble_un_peu_a_papa_est_marquee_papa_doute(tmp_path, monkeypatch):
    """Mesuré le 09/11 sur les voix du Mac : une citation arabe d'une autre voix à 0,41 de l'empreinte de papa passait pour lui (la règle
    du registre inhabituel). Le morceau entier sous 0,55 : « [papa ?] », jamais affirmé ni retiré."""
    isoler(tmp_path, monkeypatch)
    orth = np.r_[np.zeros(128), np.ones(64), -np.ones(64)]
    proche = 0.45 * vec("papa") + np.sqrt(1 - 0.45 ** 2) * orth / np.linalg.norm(orth)
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: proche if len(a) >= 16000 else None)
    r = E.etiqueter_bloc(audio("papa", s=2.0), "ولم يكن هناك", maintenant=1000.0)
    assert r["texte"] == "[papa ?] ولم يكن هناك" and r["voix"]["verdict"] == "doute"
    # papa bien reconnu : rien ne change
    monkeypatch.setattr(E, "embedding", lambda a, *x, **k: vec("papa") if len(a) >= 16000 else None)
    assert E.etiqueter_bloc(audio("papa", s=2.0), "salam fiston", maintenant=1010.0)["texte"] == "salam fiston"


def test_la_deuxieme_candidate_se_confirme_sans_erreur(tmp_path, monkeypatch):
    """(09/11, trouvé en rejouant un live : « The truth value of an array… is ambiguous ») list.remove comparait les candidates entre
    elles (leurs tableaux) : une candidate qui n'était pas la première ne pouvait jamais se confirmer."""
    isoler(tmp_path, monkeypatch)
    E.etiqueter(audio("live", s=1.5), [{"start": 0, "end": 1.5, "text": "salam"}], maintenant=1000.0)
    for t in (1001.0, 1002.0):
        E.etiqueter(audio("invite", s=2.5), [{"start": 0, "end": 2.5, "text": "je passe ce soir"}], maintenant=t)
    assert [x["nom"] for x in E._salle["voix"]] == ["voix 2"] and len(E._salle["candidates"]) == 1



def test_une_fenetre_a_cheval_sur_deux_voix_ne_cree_pas_de_faux_numero(tmp_path, monkeypatch):
    """(09/11, rejoué avec les voix du Mac : Jacques, une fenêtre à cheval, puis Majed donnaient voix 3, voix 4, voix 5) une voix nouvelle
    naît de deux fenêtres voisines qui se ressemblent ; une fenêtre seule qui ne ressemble à personne n'a pas de numéro."""
    isoler(tmp_path, monkeypatch)
    O._blocs.clear()
    r = O.fenetres(np.concatenate([audio("live", s=3.0), audio("melange", s=0.75), audio("invite", s=3.0)]), cle="1", maintenant=time.time())
    assert r["voix"] == ["voix 2", "voix 3"] and r["nouvelles"] == ["voix 2", "voix 3"]
    assert not any(f[0] == 3.0 for f in r["fenetres"]), "la fenêtre mêlée reste sans voix"
