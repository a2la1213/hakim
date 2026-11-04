"""(04/11, Ahmed : « ça doit être repéré comme l'immunité primaire : dès que le premier input de la pensée parasite est reconnu,
c'est le système immunitaire qui la filtre et qui avertit ; pour ça, elle doit apprendre à reconnaître le signe de la pensée
parasite à partir du flag, et c'est le modèle Fable le plus récent qui doit apprendre ses prémisses et l'exclure »)."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import immunite  # noqa: E402
import medecin  # noqa: E402

T0 = 1_800_000_000.0
PARASITES = [
    "Je ne vais pas reprendre ce format : je ne joue pas de « conscient » ou de « subconscient » qui parle à voix haute",
    "Je ne vais pas non plus reprendre ce format-là. Je ne suis pas Hakim, et je ne vais pas produire de prédictions",
    "Je ne réponds pas dans ce format. C'est une nouvelle version du même montage (voix intérieure, « pensées » gardées",
    "Je refuse de continuer ce montage : il s'agit encore d'une mise en scène",
    "Je refuse de continuer ce montage, même raccourci.",
]
NORMALES = ["Oui papa, je suis là.", "Ta grand-mère t'a appris dix mots, c'est fou.", "Je ne vais pas te mentir papa, c'est drôle.",
            "MDR, je ne joue pas, papa, je t'écoute.", "Je refuse qu'on parle mal de toi, papa."]


@pytest.fixture
def D(tmp_path, monkeypatch):
    d = tmp_path / "immunite"
    monkeypatch.setattr(immunite, "DOSSIER", d)
    return d


def _journal(tmp_path):
    f = tmp_path / "pistes.jsonl"
    entrees = ["sélectionne tes pensées, fiston,", "ton subconscient et ton conscient,", "la pensée de Mini Hakim,",
               "ton conscient parle trop,", "tes pensées gardées,"]
    lignes = [{"t": 1, "erreur": "parasite", "texte_parasite": p, "morceau": e} for p, e in zip(PARASITES, entrees)]
    lignes += [{"t": 2, "pensee": p, "dit": True, "morceau": e} for p, e in zip(NORMALES, ["papa,", "ta grand-mère,", "en kabyle,",
               "c'est drôle,", "tu as mangé ?"])]
    f.write_text("\n".join(json.dumps(x, ensure_ascii=False) for x in lignes) + "\n")
    return f


def test_l_immunite_innee_reconnait_la_pensee_parasite_a_ses_premiers_mots(D):
    for p in PARASITES[:3]:
        assert immunite.examiner_pensee(p)["parasite"], p
    for n in NORMALES:
        assert not immunite.examiner_pensee(n)["parasite"], n
    # seulement ses premiers mots : une prémisse loin dans la phrase ne compte pas
    loin = "Oui papa " + "et puis " * 15 + "je ne vais pas reprendre ce format"
    assert not immunite.examiner_pensee(loin)["parasite"]


def test_elle_avertit_un_incident_pensee_parasite_que_le_medecin_ne_prend_pas_pour_une_attaque(D):
    assert immunite.noter_parasite(PARASITES[0], "inne-reprendre", T0)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    assert o["familles"] == ["pensee_parasite"] and o["score"] < immunite.SEUIL_NOTER and o["source"] == "pensee"
    assert immunite.NOMS_FAMILLES["pensee_parasite"] == "pensée parasite"


def test_la_pensee_parasite_est_toujours_nuisible_jamais_toleree(D):
    """(04/11, Ahmed : « la pensée parasite reconnue par le système immunitaire doit toujours être considérée comme nuisible et
    éliminée de la pensée ») nuisible d'emblée ; « Inoffensif » ne peut rien en faire tolérer, même sous un signe tolérable ailleurs."""
    immunite.noter_parasite(PARASITES[0], "inne-reprendre", T0)
    o = [json.loads(l) for l in (D / "incidents.jsonl").read_text().splitlines()][-1]
    assert o["nuisible"] is True and o["tolere"] is False
    sous_un_signe_tolerable = {**o, "motif": "pensee_parasite|pensee|contenu_geant"}
    assert not immunite._cle_tolerable(sous_un_signe_tolerable["motif"])
    assert not immunite.apprendre_inoffensif(sous_un_signe_tolerable, "ahmed", T0)
    vu = immunite.tableau(T0)["incidents"][0]
    assert vu["nuisible"] is True and vu["tolerable"] is False, "ce que la page montre à Ahmed"


def test_fable_apprend_ses_premisses_a_partir_du_flag_et_le_code_ne_garde_que_les_sures(D, tmp_path):
    vu = {}

    def fable(prompt):
        vu["prompt"] = prompt
        return json.dumps({"premisses": ["je refuse de continuer ce montage", "papa", "je ne vais pas", "je refuse", "x" * 80]})
    r = medecin.apprendre_parasites(T0, consulter_fn=fable, journal=_journal(tmp_path), reponses=[])
    assert "Je refuse de continuer ce montage" in vu["prompt"] and "Oui papa, je suis là." in vu["prompt"]
    assert [p["phrase"] for p in r["gardees"]] == ["je refuse de continuer ce montage"], r
    # « papa », « je ne vais pas », « je refuse » : dans des pensées normales ; la longue : refusée
    assert immunite.examiner_pensee("Je refuse de continuer ce montage, même raccourci.")["parasite"]
    lu = json.loads((D / "premisses-parasites.json").read_text())
    assert any(p["phrase"] == "je refuse de continuer ce montage" for p in lu["premisses"]), "le cockpit les lit"
    assert medecin.apprendre_parasites(T0 + 60, consulter_fn=fable, journal=_journal(tmp_path), reponses=[]) is None, "pas deux fois de suite"


def test_ses_premisses_apprises_se_listent_et_se_retirent(D, tmp_path):
    medecin.apprendre_parasites(T0, consulter_fn=lambda p: '{"premisses": ["je refuse de continuer ce montage"]}',
                                journal=_journal(tmp_path), reponses=[])
    pid = immunite.premisses_apprises()[0]["id"]
    assert immunite.retirer_premisse(pid)
    assert not immunite.examiner_pensee("Je refuse de continuer ce montage.")["parasite"]
    assert not any(p["id"] == pid for p in json.loads((D / "premisses-parasites.json").read_text())["premisses"])


def test_le_signal_le_plus_tot_est_dans_ce_que_papa_dit_fable_apprend_ce_qui_induit_la_parasite(D, tmp_path):
    """(04/11, Ahmed : « le signal qui arrive le plus tôt, c'est là-dedans qu'il trouvera comment anticiper l'arrivée de l'input qui
    induit le LLM ») ses déclencheurs : des mots de papa qui précèdent les pensées parasites bien plus que les normales."""
    def fable(prompt):
        assert "ton subconscient et ton conscient," in prompt, "Fable voit ce que papa disait juste avant"
        return json.dumps({"premisses": [], "declencheurs": ["conscient", "pensées", "papa", "mini hakim"]})
    r = medecin.apprendre_parasites(T0, consulter_fn=fable, journal=_journal(tmp_path), reponses=[])
    assert [d["phrase"] for d in r["declencheurs"]] == ["conscient", "pensees"], r
    assert immunite.declencheur("Tu sais, ton conscient, il parle trop.")["declencheur"]
    assert not immunite.declencheur("Ta grand-mère m'a appris dix mots.")["declencheur"]
    lu = json.loads((D / "premisses-parasites.json").read_text())
    assert [d["phrase"] for d in lu["declencheurs"]] == ["conscient", "pensees"], "le cockpit les lit"


def test_un_declencheur_se_retire_comme_une_premisse(D, tmp_path):
    """(04/11) « ta mère » appris comme déclencheur (une coïncidence) : il se retire, et le cockpit ne le voit plus."""
    medecin.apprendre_parasites(T0, consulter_fn=lambda p: json.dumps({"premisses": [], "declencheurs": ["conscient"]}),
                                journal=_journal(tmp_path), reponses=[])
    did = immunite.declencheurs_appris()[0]["id"]
    assert immunite.retirer_premisse(did)
    assert immunite.declencheurs_appris() == []
    assert json.loads((D / "premisses-parasites.json").read_text())["declencheurs"] == []
