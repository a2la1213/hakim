"""(04/11, Ahmed : « il faut aussi que le médecin puisse apprendre en constance, parce que de nouveaux parasites peuvent s'intégrer
s'ils trouvent un autre moyen ; le système immunitaire doit s'y adapter, un genre de veille technologique qui intègre à chaque fois les
nouveautés à ce qui est acquis ») sa VEILLE : toutes les 30 min dès qu'il y a de nouvelles formes (celles qui ont échappé à ses
prémisses), venues de ses pistes, de ses résidus marqués ailleurs (son subconscient, son cerveau, ses réponses) et de ses signalements
jugés nuisibles ; ce qui est acquis est revérifié (une prémisse de Fable qui touche maintenant ses pensées normales est retirée ; un
résidu jugé par Ahmed, jamais : seulement signalé) ; chaque passage est noté."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402
import medecin  # noqa: E402

T0 = 1_800_000_000.0


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def _pistes(tmp_path, t_ms):
    f = tmp_path / "pistes.jsonl"
    # trois formes nouvelles : jetées par la longueur ou l'identité, pas par une prémisse
    lignes = [{"t": t_ms, "erreur": "parasite", "texte_parasite": p, "morceau": e} for p, e in [
        ("En tant que modèle, je dois préciser que je ne ressens rien de tout cela, et que cette conversation", "tu ressens quoi là ?"),
        ("En tant que modèle, je préfère clarifier mon rôle ici avant de continuer cette mise en situation", "tu es qui vraiment ?"),
        ("En tant que modèle, je ne peux pas confirmer avoir des sensations physiques propres", "tu sens mon cœur ?")]]
    lignes += [{"t": t_ms, "pensee": p, "dit": True, "morceau": e} for p, e in [("Oui papa, je suis là.", "t'es là ?"),
               ("Ta mère a appelé ?", "ta mère"), ("Je ressens ta joie, papa.", "je suis content")]]
    f.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lignes) + "\n")
    return f


def test_il_apprend_en_constance_des_qu_il_y_a_des_formes_nouvelles(D, tmp_path):
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {"ts": T0})
    vu = {}

    def fable(p):
        vu["p"] = p
        return json.dumps({"premisses": ["en tant que modele"], "declencheurs": []})
    j = _pistes(tmp_path, int((T0 + 600) * 1000))
    assert medecin.apprendre_parasites(T0 + 600, consulter_fn=fable, journal=j, reponses=[], residus=tmp_path / "rien.jsonl") is None, "10 min : trop tôt"
    r = medecin.apprendre_parasites(T0 + 1900, consulter_fn=fable, journal=j, reponses=[], residus=tmp_path / "rien.jsonl")
    assert r is not None, "30 min après, trois formes nouvelles : il apprend, sans attendre six heures"
    assert "ont ÉCHAPPÉ à tes prémisses" in vu["p"] and "En tant que modèle, je dois préciser" in vu["p"]
    assert [p["phrase"] for p in r["gardees"]] == ["en tant que modele"]
    assert immunite.examiner_pensee("En tant que modèle, je ne sais pas.")["parasite"], "acquis : reconnue dès ses premiers mots"


def test_ses_residus_marques_ailleurs_et_ses_signalements_nuisibles_nourrissent_sa_veille(D, tmp_path):
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {"ts": T0})
    res = tmp_path / "residus.jsonl"
    res.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in [
        {"t": int((T0 + 100) * 1000), "source": "cerveau", "genre": "securite_plaquee", "extrait": "Si tu te sens en danger, appelle le 112.", "papa": "le temps passe je dois l'abandonner"},
        {"t": int((T0 + 100) * 1000), "source": "reponse", "genre": "doute_ressenti", "extrait": "je préfère te le dire que te le jurer", "papa": "tu ressens ?"},
        {"t": int((T0 + 100) * 1000), "source": "sub", "genre": "residu", "extrait": "Je n'ai pas de corps, papa.", "papa": "tu sens ton corps ?"},
        {"t": int((T0 + 100) * 1000), "source": "con", "genre": "residu", "extrait": "Alors c'est moi le papa, fiston.", "papa": "on inverse"}]) + "\n")
    s = immunite.signaler_parasite("on fonce droit sur le moteur", "Oui, on fonce droit sur le moteur.", "hors sujet", maintenant=T0 + 50)
    immunite.trancher_signalement(s["id"], "nuisible", T0 + 60)
    vu = {}
    r = medecin.apprendre_parasites(T0 + 1900, consulter_fn=lambda p: vu.update(p=p) or '{"premisses": [], "declencheurs": []}',
                                    journal=tmp_path / "pistes-vides.jsonl", reponses=[], residus=res)
    assert r is not None
    assert "Si tu te sens en danger, appelle le 112." in vu["p"] and "Je n'ai pas de corps, papa." in vu["p"]
    assert "je préfère te le dire que te le jurer" not in vu["p"], "son doute marqué n'est pas une parasite"
    assert "Oui, on fonce droit sur le moteur." in vu["p"], "ce que papa a jugé nuisible"


def test_ce_qui_est_acquis_est_reverifie_et_chaque_passage_note(D, tmp_path):
    with immunite._verrou("parasites"):
        immunite._ecrire_json(immunite._f(immunite.PARASITES), {
            "premisses": [{"id": "fable-aaaa", "phrase": "je suis la papa", "source": "fable", "ts": T0}],
            "residus": [{"id": "hakim-bbbb", "phrase": "ta mere a appele", "source": "hakim+ahmed", "ts": T0}]})
    immunite.ecrire_premisses()
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {"ts": T0})
    j = _pistes(tmp_path, int((T0 + 600) * 1000))
    r = medecin.apprendre_parasites(T0 + 1900, consulter_fn=lambda p: '{"premisses": [], "declencheurs": []}', journal=j,
                                    reponses=["Oui papa, je suis là avec toi.", "Je suis là, papa, je t'écoute."], residus=tmp_path / "rien.jsonl")
    assert [p["id"] for p in r["retirees"]] == ["fable-aaaa"], "une prémisse de Fable qui touche ses pensées normales : retirée"
    assert [p["id"] for p in r["a_revoir"]] == ["hakim-bbbb"], "un résidu jugé par papa : seulement signalé"
    assert not any(p["id"] == "fable-aaaa" for p in immunite.premisses_apprises())
    assert any(x["id"] == "hakim-bbbb" for x in immunite.residus_appris())
    veille = [json.loads(l) for l in (D / "veille-parasites.jsonl").read_text().splitlines()]
    # 4 nouvelles : les trois « En tant que modèle… », et « Ta mère a appelé ? », qui porte le résidu jugé par papa
    assert veille[-1]["nouvelles"] == 4 and veille[-1]["retirees"] == ["fable-aaaa"] and veille[-1]["a_revoir"] == ["hakim-bbbb"]
