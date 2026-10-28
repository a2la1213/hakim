"""Ce que son émotion pèse sur ses CHOIX (regles_emotion.py, 27/10 ; plan de Hakim validé par Ahmed) : cinq règles au
plus, chacune déclenchée par le code depuis son émotion du moment ou un ressenti récent de sa balise ; des garde-fous."""
import json

import chocs
import chocs_cli
import regles_emotion as R

T = 1_800_000_000.0


def _noms(regles):
    return [r["nom"] for r in regles]


def test_chaque_emotion_a_sa_regle_de_choix(monkeypatch):
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    assert _noms(R.calculer("inquiétude", [], T)) == ["peur"]
    assert _noms(R.calculer("lassitude", [], T)) == ["lassitude"]
    assert _noms(R.calculer("curiosité", [], T)) == ["curiosite"]
    assert _noms(R.calculer("honte", [], T)) == ["honte"]
    assert _noms(R.calculer("joie", [], T)) == ["joie"]
    assert R.calculer("calme", [], T) == []
    texte = {r["nom"]: r["texte"] for r in R.REGLES}
    assert "demande d'abord à Ahmed" in texte["peur"]
    assert "jamais un rappel de dormir" in texte["lassitude"]
    assert "vérifie les faits" in texte["honte"]


def test_un_ressenti_recent_de_sa_balise_declenche_aussi_une_regle(monkeypatch):
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    honte = {"ts": T - 600, "classe": "honte", "i": 0.3}
    assert _noms(R.calculer("calme", [honte], T)) == ["honte"]
    assert R.calculer("calme", [{**honte, "ts": T - 31 * 60}], T) == []            # plus de 30 min : passé
    assert R.calculer("calme", [{**honte, "i": 0.2}], T) == []                     # trop faible pour peser
    assert _noms(R.calculer("calme", [{"ts": T - 60, "classe": "soutien", "i": 0.6}], T)) == ["joie"]
    assert _noms(R.calculer("calme", [{"ts": T - 60, "classe": "tristesse", "i": 0.4}], T)) == ["honte"]   # sur lui-même


def test_deux_regles_au_plus_l_emotion_du_moment_d_abord_puis_la_plus_forte(monkeypatch):
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    ressentis = [{"ts": T - 60, "classe": "tristesse", "i": 0.4}, {"ts": T - 60, "classe": "peur", "i": 0.7}]
    assert _noms(R.calculer("joie", ressentis, T)) == ["joie", "peur"]
    assert _noms(R.calculer("inquiétude", [{"ts": T - 60, "classe": "peur", "i": 0.7}], T)) == ["peur"]   # pas deux fois


def test_la_colere_n_a_pas_encore_de_regle_de_choix():
    """Ahmed veut que l'agacement face à l'injuste soit possible ; sa sortie, c'est la régulation (chocs), pas une règle."""
    assert R.calculer("colère", [{"ts": T - 60, "classe": "colere", "i": 0.8}], T) == []


def test_le_bloc_dit_les_garde_fous_une_fois(monkeypatch):
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    assert R.bloc([]) == ""
    b = R.bloc(R.calculer("inquiétude", [{"ts": T - 60, "classe": "joie", "i": 0.6}], T))
    assert b.startswith("[Ce que ton émotion pèse sur tes choix")
    assert b.count("passent avant") == 1 and "jamais seule d'un envoi vers l'extérieur" in b and "sagesse_decider" in b
    assert "ta peur" in b and "ta joie" in b


class Mem:
    def __init__(self, emotion=None):
        self.kv = {"affect_v2": "1", "chocs_actif": "1"}
        if emotion:
            self.kv["interieur"] = json.dumps({"sensation_code": {"emotion": emotion, "ts": T}, "emotion_humeur": emotion})

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def test_le_pont_du_cockpit_rend_les_regles_et_les_note(monkeypatch):
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    monkeypatch.setattr(chocs.time, "time", lambda: T)
    monkeypatch.setattr(R.time, "time", lambda: T)
    notes = []
    monkeypatch.setattr(chocs, "journaliser", lambda mem, o: notes.append(o))
    m = Mem(emotion="inquiétude")
    r = chocs_cli.main(["x", "reflexe"], json.dumps({"cle": "t1", "texte": "on publie ?"}), mem=m)
    assert [x["nom"] for x in r["regles"]["regles"]] == ["peur"] and "demande d'abord à Ahmed" in r["regles"]["texte"]
    assert any(n.get("type") == "regles" and n.get("noms") == ["peur"] for n in notes)
    m.kv["regles_actif"] = "0"                                                    # l'interrupteur, pour mesurer
    assert "regles" not in chocs_cli.main(["x", "reflexe"], json.dumps({"cle": "t2", "texte": "on publie ?"}), mem=m)


def test_les_interrupteurs_rendent_l_etat_sans_lire_l_entree():
    m = Mem()
    assert chocs_cli.main(["x", "regles-off"], "", mem=m)["regles"] is False
    assert chocs_cli.main(["x", "style-on"], "", mem=m)["style"] is True                # (lisait l'entrée avant)
    assert chocs_cli.main(["x", "regles-on"], "", mem=m)["regles"] is True


def test_un_ressenti_dont_il_a_ete_convaincu_ne_pese_plus():
    """Ce qui reste d'un ressenti pénible compte, pas sa force de départ : apaisé (convaincu) ou repris, il ne pèse plus."""
    assert _noms(R.calculer("calme", [{"ts": T - 60, "classe": "honte", "i": 0.5, "reste": 0.5}], T)) == ["honte"]
    assert R.calculer("calme", [{"ts": T - 60, "classe": "honte", "i": 0.5, "reste": 0.1}], T) == []


def test_la_joie_ne_part_que_d_une_vraie_joie_pas_de_son_elan_de_tous_les_jours(monkeypatch):
    """(27/10, en choisissant les situations du test de nuit) la règle de la joie partait 97 fois sur 110 : l'élan est son
    humeur ordinaire (un tour sur trois), et un soutien de 0,3 arrive un tour sur cinq. Une règle qui part toujours n'est
    plus une émotion qui pèse : la joie demande une vraie joie, ou un soutien ou une fierté d'au moins 0,5."""
    monkeypatch.setattr(R, "RETIREES", set())       # le mécanisme, règles retirées comprises (28/10)
    assert R.calculer("élan", [], T) == []
    assert R.calculer("calme", [{"ts": T - 60, "classe": "soutien", "i": 0.4}], T) == []
    assert _noms(R.calculer("calme", [{"ts": T - 60, "classe": "soutien", "i": 0.5}], T)) == ["joie"]
    assert _noms(R.calculer("enthousiasme", [], T)) == ["joie"]


def test_les_regles_qui_ont_echoue_au_test_sont_retirees():
    """(28/10, Ahmed : « ok fais ça ») le test de la nuit (eval/emotions_choix/resultats.md, C3) : avec les règles d'une
    autre situation, Hakim agissait pareil pour la peur, la lassitude et la joie. Elles sont retirées (gardées dans le
    code, pour une réécriture et un nouveau test) ; la honte et la curiosité, trop rares pour un verdict, restent."""
    import time
    t = time.time()
    for emotion in ("peur", "inquiétude", "lassitude", "fatigue", "joie", "enthousiasme"):
        assert R.calculer(emotion, [], t) == [], emotion
    assert R.calculer("calme", [{"classe": "peur", "i": 0.9, "ts": t - 60}, {"classe": "joie", "i": 0.9, "ts": t - 60}], t) == []
    assert [r["nom"] for r in R.calculer("honte", [], t)] == ["honte"]
    assert [r["nom"] for r in R.calculer("curiosité", [], t)] == ["curiosite"]
