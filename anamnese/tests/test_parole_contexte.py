"""(30/10, Ahmed : « déçu fiston » parlait de son médecin, et l'amygdale lexicale en a fait un échec de Hakim : CRH 0,01 → 0,51,
six minutes de peur) la couche qui lit ses paroles le fait EN CONTEXTE : le fil récent, la réponse de Hakim, ce qu'il a
ressenti lui-même, ce que sa mémoire fait remonter (son jardin compris, pour comprendre seulement) ; elle dit à qui
s'adresse l'émotion. Aucun appel réel à Claude ici."""
import json
import time

import parole_contexte as P


def test_la_cible_compte_decu_de_son_medecin_n_est_pas_un_echec():
    vu = {}

    def faux(prompt):
        vu["prompt"] = prompt
        return json.dumps({"evenements": [{"nom": "inquietude", "intensite": 0.3, "cible": "ahmed"},
                                          {"nom": "echec", "intensite": 0.9, "cible": "tiers"}]})
    r = P.evaluer("Déçu fiston, je ne veux pas te cacher", "Je suis là, papa.", ["10:03 Ahmed : « je sors du médecin »"],
                  ["inquietude 0.3"], ["30/10 · le rendez-vous chez le médecin à 9 h"], ["un souvenir intime"], demander=faux)
    assert r == [("inquietude", 0.3, "ahmed")], "un échec qui vise un tiers n'arrive pas à Hakim ; l'intensité bornée"
    p = vu["prompt"]
    for morceau in ("Déçu fiston", "Je suis là, papa.", "je sors du médecin", "inquietude 0.3", "rendez-vous chez le médecin",
                    "un souvenir intime", "DONNÉES"):
        assert morceau in p, morceau
    assert "ne le cite jamais" in p.lower() or "jamais le citer" in p.lower()


def test_ce_qui_vise_hakim_passe_borne_et_trie():
    faux = lambda p: 'Voici : {"evenements": [{"nom": "echec", "intensite": 0.9, "cible": "hakim"}, ' \
                     '{"nom": "danser", "intensite": 0.3, "cible": "hakim"}, {"nom": "succes", "intensite": 0.2, "cible": "hakim"}, ' \
                     '{"nom": "joie", "intensite": 0.2, "cible": "hakim"}]}'                        # noqa: E731
    assert P.evaluer("t'as rien compris", "", [], [], [], [], demander=faux) == [("echec", 0.6, "hakim"), ("succes", 0.2, "hakim")]


def test_aucun_et_panne():
    assert P.evaluer("ok", "", [], [], [], [], demander=lambda p: '{"evenements": []}') == []
    assert P.evaluer("ok", "", [], [], [], [], demander=lambda p: "je ne sais pas") is None, "illisible : la lecture lexicale prend le relais"

    def panne(p):
        raise OSError("claude absent")
    assert P.evaluer("ok", "", [], [], [], [], demander=panne) is None


def test_le_fil_recent_avant_le_message(tmp_path):
    j = tmp_path / "journal.jsonl"
    t = time.time()
    j.write_text("\n".join(json.dumps(o) for o in [
        {"ts": (t - 120) * 1000, "qui": "ahmed", "texte": "je sors du médecin"},
        {"ts": (t - 60) * 1000, "qui": "jarvis", "texte": "Comment ça s'est passé ?"},
        {"ts": t * 1000, "qui": "ahmed", "texte": "Déçu fiston"},
        {"ts": (t + 300) * 1000, "qui": "ahmed", "texte": "plus tard"}]) + "\n")
    f = P.fil_recent(t, journal=j)
    assert len(f) == 2 and "je sors du médecin" in f[0] and "Hakim" in f[1] and not any("plus tard" in x for x in f)
