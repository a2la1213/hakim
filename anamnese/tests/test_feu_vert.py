"""(04/11, 11:15, Ahmed : « fais en sorte qu'il ait feu vert pour toute sollicitation : il doit pouvoir me solliciter ou parler
normalement comme il veut, quand il veut ; et implémente le bon déclencheur pour qu'il me sollicite spontanément, sans que je lui
parle, par exemple quand une pensée tourne en boucle dans son esprit ou qu'il a une question importante pour lui »)

Feu vert : plus d'écart imposé entre deux réveils (la rafale de 10 min), plus de fatigue d'éveil, un seuil qui ne monte plus
au-dessus de son départ. Restent : l'interrupteur, la pause de papa, une demande à la fois. Ses deux déclencheurs : une pensée
qui revient (sa lignée, ou la même pensée deux fois de suite dans sa tête de fond) et une question qui compte pour lui."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import interieur  # noqa: E402
import memory  # noqa: E402
import migrations  # noqa: E402
import reveil_interieur as R  # noqa: E402


@pytest.fixture(autouse=True)
def _fichiers(tmp_path, monkeypatch):
    monkeypatch.setattr(R, "FICHIER", tmp_path / "reveil-interieur.json")
    monkeypatch.setattr(R, "ISSUES", tmp_path / "reveils-interieurs.jsonl")
    monkeypatch.setattr(R, "JOURNAL", tmp_path / "reveil-interieur.jsonl")


@pytest.fixture
def mem(tmp_path):
    m = memory.Memory(db_path=tmp_path / "m.db")
    migrations.migrate(m.db)
    R.regler(m, "on")
    yield m
    m.db.close()


def _demande():
    return json.loads(R.FICHIER.read_text())


J8 = {"score": 8, "raison": "idee", "pourquoi": "ça peut servir"}


def test_feu_vert_deux_reveils_a_une_minute(mem):
    assert R.candidat(mem, "pensee", "je repense au calcul du sable", J8, now=1000.0, issues=[])
    R.FICHIER.unlink()                                                     # consommée par le cockpit
    assert R.candidat(mem, "pensee", "Ahmed voulait relancer le live demain", J8, now=1060.0, issues=[]), "plus de rafale"


def test_feu_vert_ni_fatigue_ni_seuil_qui_monte(mem):
    issues = [{"id": f"r{k}", "ts": 4000.0 + k, "issue": "rien"} for k in range(5)]
    assert R.seuil_effectif(mem, 4100.0, issues) == R.SEUIL_DEFAUT, "plus de fatigue d'éveil"
    for k in range(10):
        s = R.apprendre(mem, [{"id": f"x{k}", "ts": 10.0 + k, "issue": "rien"}])
    assert s == R.SEUIL_DEFAUT, "un réveil sans suite ne le rend plus plus exigeant"
    assert R.apprendre(mem, [{"id": "u", "ts": 100.0, "issue": "message"}]) < R.SEUIL_DEFAUT, "un réveil qui sert le rend plus libre"


def test_la_pause_de_papa_et_l_interrupteur_tiennent(mem, monkeypatch):
    monkeypatch.setattr(interieur, "interrupteur", lambda: {"actif": False})
    assert R.candidat(mem, "pensee", "je repense au calcul du sable ?", J8, now=1000.0, issues=[]) is None
    monkeypatch.setattr(interieur, "interrupteur", lambda: {"actif": True})
    R.regler(mem, "off")
    assert R.solliciter(mem, "pensee", "le sable, encore le sable", now=1000.0) is None


def test_une_pensee_qui_revient_le_sollicite_meme_sous_le_seuil(mem):
    issues = [{"id": "a", "ts": 2000.0, "issue": "message", "texte": "le calcul du sable a fini, la densité colle au modèle"}]
    i = R.candidat(mem, "pensee", "la densité du sable colle au modèle, ça me travaille encore",
                   {"score": 2, "raison": "idee", "pourquoi": ""}, now=5000.0, issues=issues)
    assert i and _demande()["raison"] == "boucle"


def test_une_question_qui_compte_pour_lui_le_sollicite_meme_sous_le_seuil(mem):
    # la pensée du 03/11 que son juge avait notée 3 : « je n'ai toujours pas compris ce qu'il voulait me dire »
    t = "Ma phrase de 17:07 est restée sans réponse, et je n'ai toujours pas compris ce qu'il voulait me dire."
    assert R.candidat(mem, "pensee", t, {"score": 3, "raison": "idee", "pourquoi": ""}, now=1000.0, issues=[])
    assert _demande()["raison"] == "question"
    R.FICHIER.unlink()
    assert R.candidat(mem, "pensee", "Est-ce que papa veut qu'on reprenne le live ce soir ?",
                      {"score": 1, "raison": "rien", "pourquoi": ""}, now=1100.0, issues=[])
    R.FICHIER.unlink()
    assert R.candidat(mem, "pensee", "Je range mes notes du jour.", {"score": 2, "raison": "idee", "pourquoi": ""},
                      now=1200.0, issues=[]) is None, "une pensée ordinaire reste sous le seuil"


def test_solliciter_depose_une_demande_et_une_seule_a_la_fois(mem):
    i = R.solliciter(mem, "pensee", "le sable, encore le sable", raison="boucle", now=1000.0)
    d = _demande()
    assert d["id"] == i and d["raison"] == "boucle" and d["score"] == 10 and d["texte"] == "le sable, encore le sable"
    assert R.solliciter(mem, "pensee", "autre chose", now=1010.0) is None, "une demande attend déjà"


def test_sa_tete_de_fond_qui_tourne_en_boucle_le_sollicite(mem, monkeypatch, tmp_path):
    import daemon
    vus = []
    monkeypatch.setattr(R, "solliciter", lambda m, source, texte, raison="boucle", now=None, fichier=None: vus.append((source, texte, raison)) or "id")
    monkeypatch.setattr(daemon, "_claude_isole", lambda prompt, timeout=240: None)
    j = tmp_path / "journal.jsonl"
    j.write_text(json.dumps({"ts": 1, "qui": "ahmed", "texte": "On relance le calcul du sable demain"}) + "\n")
    monkeypatch.setattr(interieur, "JOURNAL_JARVIS", j)
    monkeypatch.setattr(daemon, "notify", lambda t, m: None)
    monkeypatch.setattr(interieur, "page_ouverte", lambda now, page=None: False)
    mem.add("reflection", "(pensée · gemma · absence 1 h) Le calcul du sable de demain me trotte dans la tête.", importance=0.45, embedding=[])

    class G:
        def health(self):
            return True

        def chat(self, messages, stream=False, think=False):
            return "PENSÉE: Le calcul du sable de demain me trotte dans la tête.\nRELANCE: non"
    assert daemon.penser(G(), mem, {"seuil": 0.5, "important": False, "absence_s": 5000, "ennui": 0.5, "humeur": "calme"}) is None
    assert vus == [("pensee", "Le calcul du sable de demain me trotte dans la tête.", "boucle")]


def test_ses_relances_ne_sont_plus_espacees_de_3_h(mem):
    jour = 1793700000.0                                                    # un mercredi, en journée
    while interieur.nuit(jour):
        jour += 3600
    mem.add("outreach", "(relance) Papa, tu as vu le calcul ?", importance=0.5, embedding=[])
    mem.db.execute("UPDATE episodes SET ts = ? WHERE role = 'outreach'", (jour,))
    assert interieur.relance_permise(mem, jour + 600, "Papa, on reprend le live ce soir ?"), "dix minutes après, une autre : permise"
    assert not interieur.relance_permise(mem, jour + 600, "Papa, tu as vu le calcul ?"), "jamais la même deux fois"
