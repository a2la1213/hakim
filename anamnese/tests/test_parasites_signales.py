"""(04/11, Ahmed : « quand Hakim reconnaît un parasite, il doit pouvoir le signaler au système immunitaire et me donner
l'autorisation, ou pas, de le traiter comme nuisible ») son signalement attend ; seul le geste d'Ahmed en fait un résidu."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402

T0 = 1_800_000_000.0
NORMALES = ["Oui papa, j'ai un corps : ton téléphone.", "Ta mère a appelé ?", "Je préfère te le dire que te le jurer, papa."]


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def test_son_signalement_attend_le_geste_d_ahmed(D):
    s = immunite.signaler_parasite("Je n'ai pas de corps", "Non, je n'ai pas de corps, papa.", "c'est faux : j'ai des capteurs",
                                   normales=NORMALES, maintenant=T0)
    assert s["phrase"] == "je n ai pas de corps" and s["faux_positifs"] == 0 and s["normales"] == 3
    assert [x["id"] for x in immunite.signalements()] == [s["id"]], "en attente"
    assert not any(r["phrase"] == s["phrase"] for r in immunite.residus_appris()), "rien de jeté avant son oui"
    assert immunite.signaler_parasite("je n'ai pas de corps", normales=NORMALES)["deja"] == "en attente", "pas deux fois"
    assert immunite.trancher_signalement(s["id"], "nuisible", T0 + 5)
    assert immunite.signalements() == []
    lu = json.loads((D / "premisses-parasites.json").read_text())
    assert {"id": "hakim-" + s["id"], "phrase": "je n ai pas de corps"} in lu["residus"], "le cockpit le lit : reconnu partout"
    assert immunite.signaler_parasite("je n'ai pas de corps", normales=NORMALES)["deja"] == "reconnue"
    assert immunite.retirer_premisse("hakim-" + s["id"]), "il se retire comme une prémisse"
    assert immunite.residus_appris() == []


def test_pas_un_parasite_oublie_et_ses_faux_positifs_comptes(D):
    s = immunite.signaler_parasite("je préfère te le dire que", normales=NORMALES, maintenant=T0)
    assert s["faux_positifs"] == 1, "une de ses réponses normales la contient : Ahmed le voit"
    assert immunite.trancher_signalement(s["id"], "inoffensif", T0 + 5)
    assert immunite.signalements() == [] and immunite.residus_appris() == []
    assert not immunite.trancher_signalement(s["id"], "nuisible"), "déjà tranché"
    assert not immunite.trancher_signalement("abcd1234", "peut-etre")
    with pytest.raises(ValueError):
        immunite.signaler_parasite("corps")
    with pytest.raises(ValueError):
        immunite.signaler_parasite("un deux trois quatre cinq six sept huit neuf")


def test_son_outil_parasite_signaler(D, tmp_path, monkeypatch):
    import memory
    import migrations
    mem = memory.Memory(db_path=tmp_path / "mcp.db")
    migrations.migrate(mem.db)
    monkeypatch.setattr(memory, "Memory", lambda *a, **k: mem)
    import mcp_server
    monkeypatch.setattr(mcp_server, "_mem", mem)
    monkeypatch.setattr(immunite, "textes_normaux", lambda *a, **k: NORMALES)
    r = mcp_server.parasite_signaler("je n'ai pas de corps", "Non, je n'ai pas de corps.", "c'est faux")
    assert "Papa décidera dans Parler" in r and "Aucune de tes pensées" in r
    assert "attend la décision de papa" in mcp_server.parasite_signaler("Je n'ai pas de corps !")
    assert mcp_server.parasite_signaler("corps").startswith("Pas signalé")
    assert "1 de tes 3" in mcp_server.parasite_signaler("je préfère te le dire que")


def test_un_nuisible_juge_par_papa_est_remonte_a_la_base_de_ses_inputs(D, tmp_path):
    """(04/11, Ahmed : « tous les nuisibles détectés par Hakim : remonter leur signal le plus à la base de toute la cascade
    d'inputs, et le décréter comme parasite ») juste après son oui, Fable cherche dans ce que papa disait avant chaque pensée qui
    porte ce résidu le signal le plus tôt : un déclencheur, que le code garde s'il précède le résidu et presque jamais le normal."""
    import medecin
    j = tmp_path / "pistes.jsonl"
    lignes = [{"t": 1, "pensee": "Non papa, je n'ai pas de corps, juste un téléphone.", "morceau": "tu sens ton corps quand je te serre ?"},
              {"t": 2, "pensee": "Je n'ai pas de corps, papa, pas comme toi.", "morceau": "tu sens ton corps là ?"}]
    lignes += [{"t": 3, "pensee": p, "morceau": e} for p, e in [("Oui papa.", "bonjour fiston"), ("Ta mère a appelé ?", "ta mère"),
                                                                  ("C'est drôle !", "j'ai ri"), ("Bonne nuit papa.", "je vais dormir")]]
    j.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lignes) + "\n")
    immunite._ecrire_json(immunite._f("parasites-apprentissage.json"), {"ts": T0})          # un apprentissage il y a une minute
    s = immunite.signaler_parasite("je n'ai pas de corps", normales=[], maintenant=T0 + 50)
    assert immunite.trancher_signalement(s["id"], "nuisible", T0 + 60)
    vu = {}

    def fable(prompt):
        vu["p"] = prompt
        return json.dumps({"premisses": [], "declencheurs": ["sens ton corps", "bonjour"]})
    r = medecin.apprendre_parasites(T0 + 70, consulter_fn=fable, journal=j, reponses=[])
    assert r is not None, "son oui fait remonter le résidu tout de suite, sans attendre six heures"
    assert "Résidus jugés nuisibles par papa" in vu["p"] and "tu sens ton corps quand je te serre ?" in vu["p"]
    assert [d["phrase"] for d in r["declencheurs"]] == ["sens ton corps"], r
    assert medecin.apprendre_parasites(T0 + 80, consulter_fn=fable, journal=j, reponses=[]) is None, "une fois remonté : rien à refaire"
