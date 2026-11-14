"""L'édition et les versions du studio (14/11, Ahmed : « pouvoir renommer les pistes de voix et pouvoir modifier manuellement le mix
[…] modifier et enregistrer mes mix » ; « chaque nouveau mix ou master s'enregistre en version v1, v2, v3 au lieu d'écraser
l'ancien » ; des profils « voix téléphone », « voix radio », « voix proche »). Sur de vrais petits sons synthétiques (ffmpeg).
Chaque mécanisme a son TÉMOIN : le même test, le mécanisme coupé (STUDIO_EDITION_COUPE=<nom>), doit échouer."""
import json
import os
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "jarvis"))
import studio  # noqa: E402
import studio_edition as E  # noqa: E402
import studio_mesures as M  # noqa: E402
import studio_projet as SP  # noqa: E402

pytestmark = pytest.mark.skipif(not Path(studio.FFMPEG).exists(), reason="ffmpeg absent")
SR = 44100
E.COUPE = frozenset(x for x in os.environ.get("STUDIO_EDITION_COUPE", "").split(",") if x)


@pytest.fixture(autouse=True)
def isoler(tmp_path, monkeypatch):
    """Jamais le vrai téléphone, le vrai studio ni les vraies tâches."""
    monkeypatch.setattr(studio, "TELEPHONE", tmp_path / "telephone" / "Hakim" / "Chansons")
    monkeypatch.setattr(studio, "DOCUMENTS", tmp_path / "telephone" / "Hakim")
    monkeypatch.setattr(studio, "JOURNAL_DOCUMENTS", tmp_path / "telephone-ecritures.jsonl")
    monkeypatch.setattr(studio, "STUDIO", tmp_path / "chansons" / "studio")
    monkeypatch.setattr(studio, "CHANSONS", tmp_path / "chansons")
    monkeypatch.setattr(studio, "chant_en_cours", lambda taches=None: None)


def _sinus(f, duree, amp=0.3, debut=0.0, fin=None):
    t = np.arange(int(duree * SR)) / SR
    x = amp * np.sin(2 * np.pi * f * t)
    x[t < debut] = 0
    if fin is not None:
        x[t >= fin] = 0
    return np.repeat(x[:, None], 2, axis=1)


def _bruit(duree, amp=0.1, graine=1, debut=0.0, fin=None):
    x = amp * np.random.default_rng(graine).standard_normal((int(duree * SR), 2))
    t = np.arange(len(x)) / SR
    x[t < debut] = 0
    if fin is not None:
        x[t >= fin] = 0
    return x


def _bande(x, f, a=None, b=None):
    """L'énergie (dB) d'un tiers d'octave autour de f."""
    s = (x if a is None else x[int(a * SR): int(b * SR)]).mean(axis=1)
    S = np.abs(np.fft.rfft(s * np.hanning(len(s)))) ** 2
    fr = np.fft.rfftfreq(len(s), 1 / SR)
    sel = (fr > f / 2 ** (1 / 6)) & (fr < f * 2 ** (1 / 6))
    return 10 * np.log10(S[sel].sum() + 1e-20)


@pytest.fixture
def projet(tmp_path):
    """Un projet : une « voix » (bruit large bande de 1 à 5 s) et une « instru » (sinus 110 Hz + bruit, 8 s)."""
    p = SP.nouveau("Essai", tempo=120, tonalite="A minor")
    d = SP.dossier(p["id"])
    M.ecrire_wav(d / "pistes" / "voix.wav", _bruit(8, 0.1, 3, 1.0, 5.0), SR, 32)
    M.ecrire_wav(d / "pistes" / "instru.wav", _sinus(110, 8, 0.3) + _bruit(8, 0.02), SR, 32)

    def remplir(q):
        SP.ajouter_piste(q, "pistes/voix.wav", "voix_papa", "Voix de papa", duree_s=8)
        SP.ajouter_piste(q, "pistes/instru.wav", "instru", "Instru", duree_s=8)
        for t in q["pistes"]:                               # réglages neutres : un mécanisme à la fois
            t["eq"]["coupe_bas_hz"] = 0
            t["comp"]["actif"] = False
            t["reverb"] = 0
            if "pro" in t:
                t["pro"]["actif"] = False
        q["duree_s"] = 8.0
    SP.modifier(p["id"], remplir)
    return p["id"]


def _ed(pid, quoi, **k):
    r = SP.commande({"action": "edition", "quoi": quoi, "id": pid, **k})
    assert r["ok"], r
    return r


# ------------------------------------------------------------------------------------------------ renommer
def test_renommer_une_piste(projet):
    rev = SP.lire(projet)["rev"]
    r = _ed(projet, "renommer", piste="t1", nom="  Couplet  1  ", rev=rev)
    assert r["projet"]["pistes"][0]["nom"] == "Couplet 1" and r["piste"] == "t1"
    assert SP.piste(SP.lire(projet), "couplet 1")["id"] == "t1"              # retrouvée par son nouveau nom
    assert not SP.commande({"action": "edition", "quoi": "renommer", "id": projet, "piste": "t2", "nom": "couplet 1"})["ok"]   # déjà pris
    assert not SP.commande({"action": "edition", "quoi": "renommer", "id": projet, "piste": "t2", "nom": "t1"})["ok"]
    assert not SP.commande({"action": "edition", "quoi": "renommer", "id": projet, "piste": "t2", "nom": "  "})["ok"]
    # par les mots de Hakim (studio_piste regler « nom=… ») : un texte, jamais un nombre
    assert SP.lire_reglages("nom=Refrain final, volume=-2") == {"nom": "Refrain final", "volume_db": -2.0}
    # un renommage n'est pas un réglage de mix
    q = SP.lire(projet)
    E.marquer_main(q, {"nom": "x"})
    assert not (q.get("edition") or {}).get("mix_main")


# ------------------------------------------------------------------------------------------------ les mix nommés
def test_mix_nommes_garder_rappeler_remplacer_renommer_supprimer(projet):
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": -3, "eq": {"medium_db": 4}}, "par": "papa"})
    _ed(projet, "garder_mix", nom="Mon mix")
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": 2, "pan": 0.5, "eq": {"medium_db": -6}}, "par": "papa"})
    SP.commande({"action": "projet", "id": projet, "cible": "club"})
    p = E.pour_la_page(SP.lire(projet))
    assert p["edition_etat"]["mix_courant"] == "Mon mix" and p["edition_etat"]["modifie"] and p["edition_etat"]["mix_main"]
    assert [m["nom"] for m in p["mixes"]] == ["Mon mix"] and "mix" not in p["mixes"][0]          # la page n'a pas les photos
    # une piste ajoutée après le mix reste telle quelle
    SP.modifier(projet, lambda q: SP.ajouter_piste(q, "pistes/voix.wav", "voix_papa", "Prise 2", reglages={"volume_db": -9}))
    r = _ed(projet, "rappeler_mix", nom="mon MIX", rev=SP.lire(projet)["rev"])
    t = SP.piste(r["projet"], "t1")
    assert t["volume_db"] == -3 and t["pan"] == 0 and t["eq"]["medium_db"] == 4
    assert r["projet"]["master"]["cible"] == "streaming" and r["projet"]["master"]["lufs"] == -14
    assert SP.piste(r["projet"], "t3")["volume_db"] == -9 and r["neuves"] == ["t3"] and "t3 Prise 2" in r["dit"]
    assert not E.pour_la_page(r["projet"])["edition_etat"]["modifie"]
    # modifier puis garder sous le même nom : remplacé à sa place
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": -1}, "par": "papa"})
    assert _ed(projet, "garder_mix", nom="Mon mix")["remplace"]
    _ed(projet, "garder_mix", nom="Autre")
    assert [m["nom"] for m in E.lister_mixes(SP.lire(projet))] == ["Mon mix", "Autre"]
    assert SP.piste(_ed(projet, "rappeler_mix", nom="Mon mix")["projet"], "t1")["volume_db"] == -1
    _ed(projet, "renommer_mix", nom="Autre", nouveau="Radio")
    assert not SP.commande({"action": "edition", "quoi": "renommer_mix", "id": projet, "nom": "Radio", "nouveau": "mon mix"})["ok"]
    _ed(projet, "supprimer_mix", nom="Radio")
    assert [m["nom"] for m in E.lister_mixes(SP.lire(projet))] == ["Mon mix"]
    assert not SP.commande({"action": "edition", "quoi": "rappeler_mix", "id": projet, "nom": "Radio"})["ok"]
    # une version d'avant (rev) : refusé, la page recharge
    assert "a changé" in SP.commande({"action": "edition", "quoi": "rappeler_mix", "id": projet, "nom": "Mon mix", "rev": 1})["erreur"]


def test_un_autre_son_sous_le_meme_numero_n_est_jamais_regle(projet):
    """La dernière piste retirée puis une autre ajoutée reprend son numéro : la photo ne se pose pas sur un autre son."""
    _ed(projet, "garder_mix", nom="A")
    SP.modifier(projet, lambda q: q["pistes"].pop())
    SP.modifier(projet, lambda q: SP.ajouter_piste(q, "pistes/voix.wav", "voix_papa", "Autre son", reglages={"volume_db": 5}))
    r = _ed(projet, "rappeler_mix", nom="A")
    assert SP.piste(r["projet"], "t2")["volume_db"] == 5 and r["autre_son"] == ["t2"]


# ------------------------------------------------------------------------------------------------ les versions
def test_chaque_rendu_est_une_version_rien_n_est_ecrase(projet):
    r1 = SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=True)
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": -10}, "par": "papa"})
    r2 = SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=True, nom_version="plus douce")
    p = SP.lire(projet)
    assert [v["v"] for v in p["versions"]] == [1, 2] and r1["v"] == 1 and r2["v"] == 2
    assert p["versions"][1]["nom"] == "plus douce" and p["versions"][0]["nom"] == ""
    for v in p["versions"]:
        assert Path(v["fichiers"]["complet"]["mp3"]).is_file() and Path(v["fichiers"]["complet"]["wav"]).is_file()
    assert p["versions"][0]["fichiers"]["complet"]["mp3"] != p["versions"][1]["fichiers"]["complet"]["mp3"]
    # le téléphone : deux fichiers, jamais un seul écrasé
    assert sorted(x.name for x in studio.TELEPHONE.glob("*.mp3")) == ["Essai v1.mp3", "Essai v2.mp3"]
    # chaque version garde la photo de son mix
    m1 = E.photo_de(SP.dossier(projet), p["versions"][0])
    assert m1["pistes"]["t1"]["volume_db"] == 0 and E.photo_de(SP.dossier(projet), p["versions"][1])["pistes"]["t1"]["volume_db"] == -10
    assert p["versions"][1]["master"]["lufs"] is not None and p["version_suivante"] == 3
    assert p["rendus"][-1]["v"] == 2


def test_revenir_comparer_nommer_supprimer_une_version(projet):
    SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": -10, "eq": {"aigu_db": 3}}, "par": "papa"})
    SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    c = _ed(projet, "comparer", a="v1", b="2")
    assert any("t1 Voix de papa : " in x and "volume_db 0.0 → -10.0" in x and "eq.aigu_db 0.0 → 3.0" in x for x in c["differences"]), c["differences"]
    r = _ed(projet, "revenir", v="v1", rev=SP.lire(projet)["rev"])
    t = SP.piste(r["projet"], "t1")
    assert t["volume_db"] == 0 and t["eq"]["aigu_db"] == 0
    e = E.pour_la_page(r["projet"])["edition_etat"]
    assert e["mix_courant"] == "v1" and not e["modifie"] and e["mix_main"]
    _ed(projet, "nommer_version", v="v2", nom="Voix radio")
    assert E.versions_de(SP.lire(projet))[1]["nom"] == "Voix radio"
    assert _ed(projet, "comparer", a="voix radio", b="v1")["a"]["v"] == 2               # une version par son nom
    # seul papa efface une version ; les fichiers du Mac partent, le numéro n'est jamais repris
    assert not SP.commande({"action": "edition", "quoi": "supprimer_version", "id": projet, "v": "v1", "par": "hakim"})["ok"]
    f = Path(E.versions_de(SP.lire(projet))[0]["fichiers"]["complet"]["mp3"])
    assert _ed(projet, "supprimer_version", v="v1")["effaces"] >= 3 and not f.exists()
    assert [v["v"] for v in E.versions_de(SP.lire(projet))] == [2]
    SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    assert [v["v"] for v in E.versions_de(SP.lire(projet))] == [2, 3]


def test_les_rendus_d_avant_deviennent_des_versions(projet):
    """Un projet rendu avant les versions : ses rendus deviennent v1… dans leur ordre ; le prochain rendu prend la suite."""
    SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)

    def vieux(q):                                         # comme un projet d'avant le 14/11
        for k in ("versions", "version_suivante", "edition"):
            q.pop(k, None)
        q["rendus"] = [dict(q["rendus"][0], nom="ancien-1"), dict(q["rendus"][0], nom="ancien-2")]
        for r in q["rendus"]:
            r.pop("v", None)
    SP.modifier(projet, vieux)
    vs = E.pour_la_page(SP.lire(projet))["versions"]
    assert [(v["v"], v["rendu"], v["photo"]) for v in vs] == [(1, "ancien-1", None), (2, "ancien-2", None)]
    assert "d'avant les versions" in SP.commande({"action": "edition", "quoi": "revenir", "id": projet, "v": "v1"})["erreur"]
    r = SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    assert r["v"] == 3 and [v["v"] for v in SP.lire(projet)["versions"]] == [1, 2, 3]


def test_un_rendu_rate_rend_son_numero(projet, monkeypatch):
    def panne(*a, **k):
        raise RuntimeError("ffmpeg en panne")
    with monkeypatch.context() as m:
        m.setattr(SP, "rendre_bus", panne)
        with pytest.raises(RuntimeError):
            SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    assert SP.lire(projet)["version_suivante"] == 1
    assert SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)["v"] == 1


# ------------------------------------------------------------------------------------------------ le mix à la main
def test_le_mix_a_la_main_est_garde_avant_le_mix_auto(projet):
    SP.commande({"action": "regler", "id": projet, "piste": "t1", "reglages": {"volume_db": -7, "pan": -0.4}, "par": "papa"})
    assert SP.lire(projet)["edition"]["mix_main"]
    r = SP.rendre_projet(projet, "complet", mix_auto=True, envoyer=False)
    p = SP.lire(projet)
    gardes = [m for m in p["mixes"] if m["nom"].startswith("Avant le mix auto du ")]
    assert len(gardes) == 1 and gardes[0]["par"] == "auto"
    assert gardes[0]["mix"]["pistes"]["t1"]["volume_db"] == -7 and gardes[0]["mix"]["pistes"]["t1"]["pan"] == -0.4
    assert any("Avant le mix auto" in x for x in r["journal"])
    assert not p["edition"]["mix_main"] and p["versions"][-1]["mix_auto"] is True
    # un rendu au mix auto sans rien à la main : rien de gardé en plus
    SP.rendre_projet(projet, "complet", mix_auto=True, envoyer=False)
    assert len(SP.lire(projet)["mixes"]) == 1
    # papa reprend son mix : il revient
    t = SP.piste(_ed(projet, "rappeler_mix", nom=gardes[0]["nom"])["projet"], "t1")
    assert t["volume_db"] == -7 and t["pan"] == -0.4


# ------------------------------------------------------------------------------------------------ les profils
def _rendre_piste(pid, tid, tmp_path, nom):
    f = tmp_path / nom
    SP.rendre_bus(SP.lire(pid), SP.dossier(pid), f, seules=[tid])
    return M.lire(f)[0]


def test_profil_voix_telephone_bande_passante(projet, tmp_path):
    """La « voix téléphone » sur un bruit large bande : 100 Hz et 8 kHz s'effondrent (≥ 25 dB) contre 1 kHz ; sans profil, plat."""
    sans = _rendre_piste(projet, "t1", tmp_path, "sans.wav")
    _ed(projet, "appliquer_profil", piste="t1", nom="Voix téléphone")
    avec = _rendre_piste(projet, "t1", tmp_path, "avec.wav")
    rel = lambda x, f: _bande(x, f, 1.5, 4.5) - _bande(x, 1000, 1.5, 4.5)
    assert abs(rel(sans, 8000) - rel(sans, 100) - 19) < 3                    # le bruit blanc : un tiers d'octave grandit avec f (+19 dB)
    assert rel(avec, 100) - rel(sans, 100) < -25 and rel(avec, 8000) - rel(sans, 8000) < -25, (rel(avec, 100), rel(avec, 8000))
    assert abs(rel(avec, 1500) - rel(sans, 1500)) < 6                        # la bande de la voix reste
    p = SP.lire(projet)
    assert SP.piste(p, "t1")["profil"]["nom"] == "voix téléphone" and p["edition"]["mix_main"]


def test_profil_saturation_arrondit_les_cretes_pas_le_faible(projet, tmp_path):
    """La saturation (écrêtage doux) : un sinus fort gagne des harmoniques impaires (3f), un sinus faible ne change pas."""
    d = SP.dossier(projet)
    M.ecrire_wav(d / "pistes" / "fort.wav", _sinus(440, 3, 0.7), SR, 32)
    M.ecrire_wav(d / "pistes" / "faible.wav", _sinus(440, 3, 0.01), SR, 32)

    def poser(q):
        for f, nom in (("pistes/fort.wav", "Fort"), ("pistes/faible.wav", "Faible")):
            t = SP.ajouter_piste(q, f, "ajout", nom, duree_s=3)
            t["profil"] = {"nom": "sat", "actif": True, **E.borner_profil({"saturation": 0.6})}
    SP.modifier(projet, poser)
    fort, faible = _rendre_piste(projet, "t3", tmp_path, "fort.wav"), _rendre_piste(projet, "t4", tmp_path, "faible.wav")
    assert _bande(fort, 1320, 0.5, 2.5) - _bande(fort, 440, 0.5, 2.5) > -30                # la 3e harmonique est là
    ref = _sinus(440, 3, 0.01)
    assert abs(M.db(faible[int(0.5 * SR): int(2.5 * SR)]) - M.db(ref[int(0.5 * SR): int(2.5 * SR)])) < 0.3
    assert _bande(faible, 1320, 0.5, 2.5) - _bande(faible, 440, 0.5, 2.5) < -60


def test_profils_garder_lister_reinitialiser_et_bornes():
    l = E.lister_profils()
    assert [x["nom"] for x in l] == ["voix téléphone", "voix radio", "voix proche", "voix mégaphone"] and all(x["depart"] for x in l)
    x = E.garder_profil("Voix téléphone", dict(E.trouver_profil("voix telephone")["reglages"], coupe_haut_hz=3000))
    assert x["modifie"] and x["reglages"]["coupe_haut_hz"] == 3000
    assert E.supprimer_profil("voix téléphone")["reinitialise"] and E.trouver_profil("voix téléphone")["reglages"]["coupe_haut_hz"] == 3400
    with pytest.raises(E.Refus, match="profil de départ"):
        E.supprimer_profil("voix radio")
    m = E.garder_profil("Ma voix", E.lire_profil("bande=200-9000, pente=18, saturation=3, grave=+2, q=0.1"))
    assert m["reglages"]["coupe_bas_hz"] == 200 and m["reglages"]["coupe_haut_hz"] == 9000 and m["reglages"]["pente"] == 24
    assert m["reglages"]["saturation"] == 1 and m["reglages"]["medium_q"] == 0.3 and m["reglages"]["grave_db"] == 2
    assert E.borner_profil({"coupe_haut_hz": 500, "coupe_bas_hz": 10})["coupe_haut_hz"] == 0
    assert "Ma voix" in [x["nom"] for x in E.lister_profils()]
    E.supprimer_profil("ma voix")
    assert "Ma voix" not in [x["nom"] for x in E.lister_profils()]
    with pytest.raises(E.Refus, match="inconnu"):
        E.lire_profil("couleur=rouge")


def test_le_profil_d_une_piste_se_regle_a_la_main_et_se_garde(projet, tmp_path):
    _ed(projet, "appliquer_profil", piste="t1", nom="voix radio")
    E.supprimer_profil("voix radio") if E.trouver_profil("voix radio")["modifie"] else None
    p = _ed(projet, "regler_profil", piste="t1", reglages={"coupe_haut_hz": 6000, "saturation": 0.1})["projet"]
    pr = SP.piste(p, "t1")["profil"]
    assert pr["coupe_haut_hz"] == 6000 and pr["saturation"] == 0.1 and pr["coupe_bas_hz"] == 450 and pr["nom"] == "voix radio"
    assert E.trouver_profil("voix radio")["reglages"]["coupe_haut_hz"] == 4500        # le profil gardé ne bouge pas
    r = _ed(projet, "garder_profil", piste="t1", nom="Radio claire")
    assert r["profil"]["reglages"]["coupe_haut_hz"] == 6000 and SP.piste(r["projet"], "t1")["profil"]["nom"] == "Radio claire"
    # coupé sans être oublié
    p = _ed(projet, "regler_profil", piste="t1", reglages={"actif": "non"})["projet"]
    assert SP.piste(p, "t1")["profil"]["actif"] is False and E.chaine_profil(SP.piste(p, "t1")["profil"]) == []
    p = _ed(projet, "retirer_profil", piste="t1")["projet"]
    assert "profil" not in SP.piste(p, "t1")


def test_apercu_avant_apres_sur_un_extrait(projet):
    """L'aperçu rend un extrait de la piste seule deux fois : la voix (de 1 à 5 s) choisie là où elle sonne, la « voix téléphone »
    entendue après et pas avant."""
    r = _ed(projet, "apercu", piste="t1", nom="voix téléphone")["apercu"]
    assert 0.4 <= r["debut_s"] <= 1.3 and r["profil"] == "voix téléphone" and r["voix"] == "brute"
    av, ap = M.lire(r["avant"])[0], M.lire(r["apres"])[0]
    assert Path(r["avant"]).parent == SP.dossier(projet) / "rendus" / "apercus"
    assert 11 <= len(av) / SR <= 14
    ecart = lambda x: _bande(x, 8000, 0.5, 3.5) - _bande(x, 1000, 0.5, 3.5)
    assert ecart(av) - ecart(ap) > 20, (ecart(av), ecart(ap))
    assert r["lufs_avant"] > -40 and r["lufs_apres"] > -40 and r["ecart_db"] is not None
    # la lecture placée dans la voix : l'extrait y commence ; une piste muette ou un profil inconnu : refusé proprement
    assert _ed(projet, "apercu", piste="t1", nom="voix proche", debut_s=2.5)["apercu"]["debut_s"] == 2.5
    assert not SP.commande({"action": "edition", "quoi": "apercu", "id": projet, "piste": "t1", "nom": "inconnu"})["ok"]
    assert "n'en a pas" in SP.commande({"action": "edition", "quoi": "apercu", "id": projet, "piste": "t1"})["erreur"]


def test_le_mix_auto_ne_touche_pas_au_profil(projet):
    _ed(projet, "appliquer_profil", piste="t1", nom="voix proche")
    SP.rendre_projet(projet, "complet", mix_auto=True, envoyer=False)
    assert SP.piste(SP.lire(projet), "t1")["profil"]["nom"] == "voix proche"


def test_l_apercu_prend_la_voix_nettoyee_si_elle_est_prete(projet):
    """Les mêmes clés de cache que preparer_pro : une voix déjà nettoyée est celle de l'aperçu (sinon la prise brute)."""
    SP.modifier(projet, lambda q: SP.piste(q, "t1")["pro"].update(actif=True))
    p = SP.lire(projet)
    d = SP.dossier(projet)
    assert E._voix_prete(p, d, SP.piste(p, "t1"))[1] == "brute"
    out, _ = SP.preparer_pro(p, d)
    f, etat = E._voix_prete(p, d, SP.piste(p, "t1"))
    assert etat == "nettoyée" and f == out["t1"]


# ------------------------------------------------------------------------------------------------ la ligne de commande du cockpit
def test_la_page_par_la_ligne_de_commande(projet, tmp_path):
    """Le cockpit lance « studio_projet.py commande » : l'édition y trouve le même module (ses refus restent des refus), et chaque
    projet rendu à la page porte ses versions et l'état de son mix."""
    env = {**os.environ, "JARVIS_DIR": str(tmp_path)}
    py = Path(__file__).resolve().parent.parent / "jarvis" / "studio_projet.py"

    def cmd(q):
        r = subprocess.run([sys.executable, "-B", str(py), "commande"], input=json.dumps(q), capture_output=True, text=True, env=env, timeout=60)
        assert r.returncode == 0, r.stderr[-800:]
        return json.loads(r.stdout.strip().splitlines()[-1])
    r = cmd({"action": "edition", "quoi": "renommer", "id": projet, "piste": "t1", "nom": "Couplet"})
    assert r["ok"] and r["projet"]["pistes"][0]["nom"] == "Couplet"
    assert r["projet"]["edition_etat"] == {"mix_main": False, "mix_courant": None, "modifie": False} and r["projet"]["versions"] == []
    r = cmd({"action": "edition", "quoi": "renommer", "id": projet, "piste": "t2", "nom": "couplet"})
    assert r == {"ok": False, "erreur": "« couplet » est déjà le nom de t1 : choisis-en un autre"}
    r = cmd({"action": "edition", "quoi": "garder_mix", "id": projet, "nom": "A"})
    assert r["projet"]["mixes"][0]["nom"] == "A" and "mix" not in r["projet"]["mixes"][0]
    assert cmd({"action": "lire", "id": projet})["projet"]["edition_etat"]["mix_courant"] == "A"


# ------------------------------------------------------------------------------------------------ les outils de Hakim
def test_les_outils_de_hakim(projet, tmp_path, monkeypatch):
    import memory
    mem = memory.Memory(db_path=tmp_path / "m.db")
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    outil = lambda n: mcp_server.mcp._tool_manager.get_tool(n).fn
    monkeypatch.setenv("ANAMNESE_SOURCE", "claude-code")
    assert outil("studio_mix")("essai") == "Seul Hakim travaille dans le studio."
    assert outil("studio_profil")() == "Seul Hakim travaille dans le studio."
    monkeypatch.setenv("ANAMNESE_SOURCE", "hakim")
    # renommer
    assert outil("studio_piste")("essai", "t1", "renommer", nom="Couplet de papa") == "Renommée : t1 s'appelle maintenant « Couplet de papa »."
    r = outil("studio_piste")("essai", "couplet de papa", "regler", "nom=Refrain, volume=-4")
    assert r.startswith("Réglée.") and "t1 Refrain" in r and "vol -4.0 dB" in r
    assert outil("studio_piste")("essai", "t2", "renommer", nom="refrain").startswith("Refusé : « refrain » est déjà le nom de t1")
    # ses mix
    assert outil("studio_mix")("essai", "garder", nom="Mix A") == "Mix gardé : « Mix A »."
    outil("studio_piste")("essai", "t1", "regler", "volume=2")
    l = outil("studio_mix")("essai", "liste")
    assert "il porte le mix « Mix A » (modifié depuis)" in l and "réglé à la main" in l and "« Mix A » (hakim" in l
    assert outil("studio_mix")("essai", "rappeler", nom="mix a").startswith("Mix « Mix A » rappelé : 2 piste(s) reprises")
    assert SP.piste(SP.lire(projet), "t1")["volume_db"] == -4
    # studio_rendre : « auto » garde un mix fait à la main (sans mix auto), et nomme la version
    vus = []
    monkeypatch.setattr(studio, "_demarrer_travailleur", vus.append)
    r = outil("studio_rendre")("essai", nom="première")
    assert "le mix tel quel" in r and "nouvelle version" in r
    j = json.loads(next((studio.STUDIO / "travaux").glob("J-*.json")).read_text())
    assert j["params"]["mix_auto"] is False and j["params"]["nom_version"] == "première"
    assert studio.travailleur(studio.STUDIO / "travaux") == 1
    a = mcp_server.mcp._tool_manager.get_tool("studio_avis").fn()
    assert "version v1" in a and "Essai v1.mp3" in a
    outil("studio_piste")("essai", "t1", "regler", "volume=-12")
    SP.rendre_projet(projet, "complet", mix_auto=False, envoyer=False)
    v = outil("studio_mix")("essai", "versions")
    assert "v1 « première »" in v and "v2" in v and "mix à la main" in v
    c = outil("studio_mix")("essai", "comparer", version="v1", autre="v2")
    assert "volume_db -4.0 → -12.0" in c and "A à écouter : " in c
    assert outil("studio_mix")("essai", "nommer_version", version="v2", nom="douce") == "v2 s'appelle « douce »."
    assert outil("studio_mix")("essai", "revenir", version="v1").startswith("Le mix de v1 est revenu sur le projet")
    assert SP.piste(SP.lire(projet), "t1")["volume_db"] == -4
    # ses profils
    assert "« voix téléphone » (départ)" in outil("studio_profil")("liste")
    assert "bande 300-3400 Hz" in outil("studio_profil")("voir", "voix telephone")
    assert outil("studio_profil")("appliquer", "voix radio", "essai", "t1").startswith("Profil « voix radio » posé sur t1")
    assert "profil « voix radio »" in outil("studio_projet")("voir", "essai") and ", v2)" in outil("studio_projet")("voir", "essai")
    assert "bande 450-6000 Hz" in outil("studio_profil")("regler", projet="essai", piste="t1", reglages="haut=6000")
    assert outil("studio_profil")("garder", "Radio de papa", "essai", "t1").startswith("Profil gardé : « Radio de papa »")
    ap = outil("studio_profil")("apercu", "voix mégaphone", "essai", "t1")
    assert ap.startswith("Aperçu de « voix mégaphone » sur Refrain") and "AVANT " in ap and "-avant.mp3" in ap
    assert outil("studio_profil")("garder", "Lo-fi", reglages="bande=200-5000, saturation=0.5").startswith("Profil gardé : « Lo-fi »")
    assert outil("studio_profil")("supprimer", "lo-fi") == "Profil « Lo-fi » effacé."
    assert outil("studio_profil")("retirer", projet="essai", piste="t1") == "Profil retiré de t1."
