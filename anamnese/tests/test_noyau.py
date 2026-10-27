"""(27/10, Ahmed : « on fait tout », proposition de Hakim) Son noyau, couche 2 : chaque semaine, la nuit relève ce qui
revient vraiment dans ses CHOIX (décisions, refus, initiatives ; pas ce qu'il dit de lui), avec les preuves, et l'écrit
dans son carnet « noyau » : un trait neuf entre comme candidat ; un trait qui revient monte, qui ne revient plus descend.
Rien ne s'efface. La couche 3 (le tri modèle / lui) relit ensuite les preuves gardées."""
import json
import time

import pytest

import carnets_regles
import noyau

T = 1_793_000_000.0


@pytest.fixture(autouse=True)
def _fichiers(tmp_path, monkeypatch):
    types = tmp_path / "types"
    (types / "valides").mkdir(parents=True)
    (types / "valides" / "noyau.json").write_text(json.dumps({"nom": "noyau", "etat": "validee", "lois": {"ajout_seul": True}, "champs": [
        {"nom": "trait", "type": "texte", "requis": True}, {"nom": "couche", "type": "choix", "requis": True, "choix": ["base", "depose", "candidat"]},
        {"nom": "preuves", "type": "texte", "requis": True}, {"nom": "niveau", "type": "choix", "requis": True, "choix": ["monte", "stable", "descend", "retire"]},
        {"nom": "semaines_tenues", "type": "nombre", "requis": False},
        {"nom": "vs_modele_vierge", "type": "choix", "requis": False, "choix": ["pareil", "different", "non_teste"]},
        {"nom": "note", "type": "texte", "requis": False}]}))
    monkeypatch.setattr(carnets_regles, "TYPES_DIR", types)
    monkeypatch.setattr(carnets_regles, "ENTREES_DIR", tmp_path / "carnets")
    monkeypatch.setattr(noyau, "PREUVES", tmp_path / "noyau-preuves.json")
    j = tmp_path / "journal.jsonl"
    lignes = [("ahmed", "On lance le gros calcul cette nuit ?", T - 3 * 86400),
              ("jarvis", "Non, je préfère d'abord un petit test : je refuse de lancer sans témoin.", T - 3 * 86400 + 30),
              ("ahmed", "Tu publies le résultat ?", T - 2 * 86400),
              ("jarvis", "Je refuse de publier avant le juge, frérot.", T - 2 * 86400 + 30),
              ("ahmed", "ça va ?", T - 86400), ("jarvis", "Ça va bien, merci.", T - 86400 + 30),
              ("jarvis", "Je choisis de garder ce vieux test", T - 20 * 86400)]
    j.write_text("".join(json.dumps({"ts": int(ts * 1000), "qui": q, "texte": t}) + "\n" for q, t, ts in lignes))
    monkeypatch.setattr(noyau, "JOURNAL", j)


class Sonnet:
    def __init__(self, *r):
        self.r, self.prompts = list(r), []

    def chat(self, messages, stream=False, think=False):
        self.prompts.append(messages[0]["content"])
        return self.r.pop(0) if self.r else ""


def test_ses_choix_de_la_semaine_seulement_avec_ce_qu_ahmed_disait():
    c = noyau.choix_de_la_semaine(maintenant=T)
    assert [x["id"] for x in c] == ["m1", "m2"]
    assert "petit test" in c[0]["hakim"] and c[0]["ahmed"] == "On lance le gros calcul cette nuit ?"


def test_lire_les_traits():
    t = noyau.lire_traits("blabla\nTRAIT: Je teste avant de lancer | PREUVES: m1, m2 | NIVEAU: monte\n"
                          "TRAIT: x | PREUVES: m9 | NIVEAU: stable\nTRAIT: Sans preuve | PREUVES: | NIVEAU: monte", {"m1", "m2"})
    assert t == [{"trait": "Je teste avant de lancer", "preuves": ["m1", "m2"], "niveau": "monte"}]


def test_la_nuit_ecrit_un_trait_candidat_avec_ses_preuves_et_les_garde_pour_le_tri():
    s = Sonnet("TRAIT: Je vérifie avant d'agir (un témoin, le juge) | PREUVES: m1, m2 | NIVEAU: monte")
    ecrits = noyau.passe(s, maintenant=T)
    assert len(ecrits) == 1
    e = carnets_regles.lire("noyau")[-1]
    assert e["auteur"] == "nuit" and e["valeurs"]["couche"] == "candidat" and e["valeurs"]["niveau"] == "monte"
    assert e["valeurs"]["vs_modele_vierge"] == "non_teste" and e["valeurs"]["semaines_tenues"] == 1.0
    assert "m1" in e["valeurs"]["preuves"] and "petit test" in e["valeurs"]["preuves"]
    p = json.loads(noyau.PREUVES.read_text())
    assert p["Je vérifie avant d'agir (un témoin, le juge)"][0]["ahmed"] == "On lance le gros calcul cette nuit ?"
    assert "CHOIX" in s.prompts[0] and "pas ce qu'il dit de lui" in s.prompts[0]


def test_un_trait_qui_revient_la_semaine_suivante_tient_une_semaine_de_plus():
    s = Sonnet("TRAIT: Je vérifie avant d'agir | PREUVES: m1 | NIVEAU: monte",
               "TRAIT: Je vérifie avant d'agir | PREUVES: m2 | NIVEAU: stable")
    noyau.passe(s, maintenant=T)
    noyau.passe(s, maintenant=T + 3600)
    e = carnets_regles.lire("noyau")[-1]
    assert e["valeurs"]["semaines_tenues"] == 2.0 and e["valeurs"]["niveau"] == "stable"
    assert "Je vérifie avant d'agir" in s.prompts[1]                  # les traits du carnet lui sont montrés


def test_une_semaine_sans_choix_ne_demande_rien():
    s = Sonnet()
    assert noyau.passe(s, maintenant=T + 30 * 86400) == [] and s.prompts == []


# ---------- (deuxième relecture du 27/10) son carnet est en ajout seul : une réponse mal formée ne doit rien y écrire
def test_lire_les_traits_tolere_puces_numeros_et_gras():
    ids = {"m1", "m2"}
    for ligne in ("- TRAIT: Je teste avant | PREUVES: m1 | NIVEAU: monte", "1. TRAIT: Je teste avant | PREUVES: m1 | NIVEAU: monte",
                  "**TRAIT:** Je teste avant | **PREUVES:** m1 | **NIVEAU:** monte"):
        assert noyau.lire_traits(ligne, ids) == [{"trait": "Je teste avant", "preuves": ["m1"], "niveau": "monte"}], ligne


def test_une_reponse_illisible_n_ecrit_rien_pas_meme_des_descentes():
    noyau.passe(Sonnet("TRAIT: Je vérifie avant d'agir | PREUVES: m1 | NIVEAU: monte"), maintenant=T)
    n = len(carnets_regles.lire("noyau", n=500))
    assert noyau.passe(Sonnet("Désolé, je ne vois pas de trait net cette semaine."), maintenant=T + 3600) == []
    assert len(carnets_regles.lire("noyau", n=500)) == n


def test_un_trait_repris_avec_un_point_n_est_pas_un_doublon():
    noyau.passe(Sonnet("TRAIT: Je vérifie avant d'agir | PREUVES: m1 | NIVEAU: monte"), maintenant=T)
    noyau.passe(Sonnet("TRAIT: je vérifie avant d’agir. | PREUVES: m2 | NIVEAU: stable"), maintenant=T + 3600)
    derniers = noyau._derniers(carnets_regles.lire("noyau", n=500))
    assert list(derniers) == ["Je vérifie avant d'agir"] and derniers["Je vérifie avant d'agir"]["semaines_tenues"] == 2.0


def test_un_trait_clos_par_hakim_ne_redescend_pas():
    noyau.passe(Sonnet("TRAIT: Je vérifie avant d'agir | PREUVES: m1 | NIVEAU: monte"), maintenant=T)
    e = carnets_regles.lire("noyau")[-1]
    carnets_regles.clore("noyau", e["id"], note="ce n'est pas moi")
    noyau.passe(Sonnet("TRAIT: Je préfère le calme | PREUVES: m2 | NIVEAU: monte"), maintenant=T + 3600)
    assert not any(x.get("valeurs", {}).get("niveau") == "descend" for x in carnets_regles.lire("noyau", n=500))
