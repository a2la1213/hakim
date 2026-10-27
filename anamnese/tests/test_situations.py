"""(27/10, idée d'Ahmed relayée par Hakim) Les erreurs apprises par SITUATION, pas par sujet : la nuit range chaque erreur
du carnet dans une situation (ce qu'il était en train de faire) ; deux erreurs ou plus dans une même situation donnent une
leçon, que le cockpit lui rappelle selon ce qu'il FAIT (un réveil, une conversation à l'oral, plusieurs voix…), pas selon
les mots d'Ahmed. Et on compte les récidives avant et après."""
import json

import pytest

import situations


@pytest.fixture(autouse=True)
def _fichiers(tmp_path, monkeypatch):
    monkeypatch.setattr(situations, "CLASSEMENT", tmp_path / "erreurs-situations.json")
    monkeypatch.setattr(situations, "LECONS", tmp_path / "lecons-situations.json")


E = [{"id": "a1", "ts": 100.0, "quoi": "J'ai répondu « No response requested. » à un vrai message d'Ahmed", "correction": "jamais"},
     {"id": "a2", "ts": 200.0, "quoi": "Encore « No response requested. » après un tour d'outils", "correction": "répondre"},
     {"id": "b1", "ts": 300.0, "quoi": "J'ai annoncé un chiffre sans le vérifier", "correction": "vérifier"},
     {"id": "c1", "ts": 400.0, "quoi": "Pendant le live, j'ai confondu deux invités", "correction": "demander"}]


class Sonnet:
    def __init__(self, *reponses):
        self.reponses, self.prompts = list(reponses), []

    def health(self):
        return True

    def chat(self, messages, stream=False, think=False):
        self.prompts.append(messages[0]["content"])
        return self.reponses.pop(0) if self.reponses else ""


def test_lire_le_classement_tolere_le_bruit():
    sortie = ("Voici :\na1 | fin-de-tour | à la fin d'un tour, quand je réponds à Ahmed | toujours\n"
              "a2 | Fin de tour | à la fin d'un tour | toujours\nb1 | citer-un-chiffre | quand je cite un chiffre | inconnu\n"
              "zz | x | y | toujours\nc1 | live-invites | pendant un live avec des invités | plusieurs_voix")
    c = situations.lire_classement(sortie, {"a1", "a2", "b1", "c1"})
    assert c["a1"] == {"slug": "fin-de-tour", "libelle": "à la fin d'un tour, quand je réponds à Ahmed", "declencheur": "toujours"}
    assert c["a2"]["slug"] == "fin-de-tour"                       # normalisé
    assert c["b1"]["declencheur"] == "toujours"                   # déclencheur inconnu : toujours
    assert "zz" not in c and c["c1"]["declencheur"] == "plusieurs_voix"


def test_la_nuit_classe_seulement_les_nouvelles_erreurs_par_lots():
    s = Sonnet("a1 | fin-de-tour | à la fin d'un tour | toujours\na2 | fin-de-tour | à la fin d'un tour | toujours\n"
               "b1 | citer-un-chiffre | quand je cite un chiffre | toujours\nc1 | live-invites | pendant un live | plusieurs_voix")
    assert situations.classer(s, E, lot=20) == 4 and len(s.prompts) == 1
    assert "a1" in s.prompts[0] and "No response requested" in s.prompts[0]
    assert situations.classer(s, E, lot=20) == 0 and len(s.prompts) == 1          # déjà classées


def test_deux_erreurs_dans_une_situation_font_une_lecon():
    s = Sonnet("a1 | fin-de-tour | à la fin d'un tour | toujours\na2 | fin-de-tour | à la fin d'un tour | toujours\n"
               "b1 | citer-un-chiffre | quand je cite un chiffre | toujours\nc1 | live-invites | pendant un live | plusieurs_voix",
               "LEÇON : À la fin d'un tour, un vrai message d'Ahmed attend toujours une réponse ; ne réponds jamais « No response requested. ».")
    situations.classer(s, E, lot=20)
    l = situations.lecons(s, E, maintenant=1000.0)
    assert [x["slug"] for x in l] == ["fin-de-tour"] and l[0]["n"] == 2 and l[0]["erreurs"] == ["a1", "a2"]
    assert l[0]["regle"].startswith("À la fin d'un tour") and l[0]["depuis_ts"] == 1000.0
    assert json.loads(situations.LECONS.read_text())["situations"][0]["slug"] == "fin-de-tour"
    # une nuit plus tard, sans nouvelle erreur : la leçon garde sa date et n'est pas réécrite
    assert situations.lecons(s, E, maintenant=2000.0)[0]["depuis_ts"] == 1000.0 and len(s.prompts) == 2


def test_une_nouvelle_erreur_dans_la_situation_reecrit_la_lecon():
    s = Sonnet("a1 | fin-de-tour | à la fin d'un tour | toujours\na2 | fin-de-tour | à la fin d'un tour | toujours",
               "LEÇON : première version.", "a3 | fin-de-tour | à la fin d'un tour | toujours", "LEÇON : version enrichie.")
    situations.classer(s, E[:2], lot=20)
    situations.lecons(s, E[:2], maintenant=1000.0)
    e3 = E[:2] + [{"id": "a3", "ts": 1500.0, "quoi": "Une troisième fois", "correction": "x"}]
    situations.classer(s, e3, lot=20)
    l = situations.lecons(s, e3, maintenant=2000.0)
    assert l[0]["regle"] == "version enrichie." and l[0]["n"] == 3 and l[0]["depuis_ts"] == 1000.0


def test_les_recidives_avant_et_apres_la_lecon():
    classement = {"a1": {"slug": "fin-de-tour"}, "a2": {"slug": "fin-de-tour"}, "a3": {"slug": "fin-de-tour"}}
    lecons = [{"slug": "fin-de-tour", "depuis_ts": 250.0}]
    err = E[:2] + [{"id": "a3", "ts": 900.0, "quoi": "x", "correction": "y"}]
    r = situations.recidives(err, classement, lecons, maintenant=1000.0)
    assert r == [{"slug": "fin-de-tour", "avant": 2, "apres": 1, "jours_avant": round((250 - 100) / 86400, 4),
                  "jours_apres": round((1000 - 250) / 86400, 4)}]


def test_lire_le_classement_d_un_tableau_markdown():
    c = situations.lire_classement("| id | situation | phrase | déclencheur |\n|---|---|---|---|\n"
                                   "| a1 | fin-de-tour | à la fin d'un tour | toujours |", {"a1"})
    assert c["a1"]["slug"] == "fin-de-tour" and c["a1"]["declencheur"] == "toujours"
