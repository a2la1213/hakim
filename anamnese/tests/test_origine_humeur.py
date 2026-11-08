"""D'où vient son humeur (27/10, demande d'Ahmed relayée par Hakim, go d'Ahmed : « tu peux faire ce que Hakim demande ») :
le badge de Parler dit si l'émotion vient de lui-même, de l'empathie (avec la personne), ou d'une pente sans cause marquée."""
import json

import origine_humeur as O

T = 1_800_000_000.0


def ev(age_s, nom, i, sujet=None, source="balise"):
    return {"ts": T - age_s, "nom": nom, "intensite": i, "source": source, **({"sujet": sujet} if sujet else {})}


def test_une_compassion_pour_ahmed_fait_une_humeur_par_empathie():
    o = O.origine("déception", [ev(300, "compassion", 0.4, "compassion de hakim pour ahmed, au message d'ahmed")], T)
    assert o == {"type": "empathie", "texte": "par empathie, pour Ahmed"}


def test_sa_propre_tristesse_fait_une_humeur_pour_lui_meme():
    o = O.origine("tristesse", [ev(300, "tristesse", 0.4, "tristesse de hakim, au message d'ahmed")], T)
    assert o["type"] == "soi" and o["texte"].startswith("pour lui-même")


def test_sans_evenement_c_est_une_pente_et_c_est_dit():
    assert O.origine("déception", [], T) == {"type": "pente", "texte": "pente, sans cause marquée"}
    # trop ancien (2 h), ou de l'autre signe : pas une cause
    assert O.origine("déception", [ev(7200, "compassion", 0.5, "compassion de hakim pour ahmed, au message d'ahmed")], T)["type"] == "pente"
    assert O.origine("déception", [ev(300, "soutien", 0.6, "soutien de ahmed")], T)["type"] == "pente"


def test_empathie_et_soi_meles():
    o = O.origine("tristesse", [ev(200, "compassion", 0.4, "compassion de hakim pour nora, au message d'une voix tierce"),
                                ev(250, "tristesse", 0.4, "tristesse de hakim, au message d'ahmed")], T)
    assert o == {"type": "mixte", "texte": "par empathie (pour Nora) et pour lui-même"}


def test_les_cibles_et_le_malaise():
    o = O.origine("inquiétude", [ev(100, "inquietude", 0.5, "inquiétude de hakim pour ahmed, au message d'une voix tierce"),
                                 ev(120, "malaise", 0.4, "malaise de hakim, au message d'une voix tierce"),
                                 ev(130, "inquietude", 0.3, "inquiétude de hakim pour l'ami d'ahmed, au message d'ahmed")], T)
    assert o == {"type": "empathie", "texte": "par empathie, pour Ahmed et l'ami d'Ahmed"}
    assert O.origine("tension", [ev(100, "malaise", 0.4, "malaise de hakim, au message d'une voix tierce")], T) == \
        {"type": "empathie", "texte": "par empathie (malaise au milieu d'une tension)"}


def test_une_humeur_positive_dit_sa_cause():
    assert O.origine("joie", [ev(60, "soutien", 0.5, "soutien de ahmed")], T)["texte"] == "pour lui-même, après un soutien"
    assert O.origine("élan", [ev(60, "retour", 0.6, None, "interieur")], T)["texte"] == "le retour d'Ahmed"
    assert O.origine("joie", [ev(60, "joie", 0.5, "joie de hakim pour ahmed, au message d'ahmed")], T) == \
        {"type": "empathie", "texte": "par empathie, pour Ahmed"}


def test_lire_le_journal(tmp_path):
    f = tmp_path / "affect-evenements.jsonl"
    f.write_text("pas du json\n" + json.dumps(ev(100, "compassion", 0.4, "compassion de hakim pour ahmed, au message d'ahmed")) + "\n")
    assert O.depuis_journal(f, "déception", T)["type"] == "empathie"
    assert O.depuis_journal(tmp_path / "absent.jsonl", "déception", T)["type"] == "pente"
