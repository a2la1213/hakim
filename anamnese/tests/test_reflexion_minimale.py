"""(03/11, Ahmed : « mets tous les modèles en réflexion minimale, ni moyenne ni haute, on va au minimum (Mini Hakim, Hakim,
Super Hakim), et même pour le subconscient et Gemma ») chaque appel de Claude qui fait vivre Hakim demande l'effort le plus
bas que claude accepte (« low ») ; Gemma (Ollama) ne pense pas (think=False)."""
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import config  # noqa: E402


def _effort(argv):
    argv = list(argv)
    return argv[argv.index("--effort") + 1] if "--effort" in argv else None


class _Fini:
    returncode = 0
    stdout = json.dumps({"result": "ok"})


def test_le_niveau_est_le_plus_bas():
    assert config.EFFORT_HAKIM == "low"


def test_son_corps_reflechit_au_minimum(monkeypatch):
    import corps
    vus = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: vus.append(argv) or _Fini())
    corps.demander_claude("x")
    assert _effort(vus[0]) == "low"


def test_le_sonnet_vivant_de_son_corps_aussi(monkeypatch):
    import corps
    vus = []

    class _Proc:
        stdin = stdout = None

    monkeypatch.setattr(subprocess, "Popen", lambda argv, **k: vus.append(argv) or _Proc())
    corps.SonnetVivant()._lancer()
    assert _effort(vus[0]) == "low"


def test_la_lecture_en_contexte_de_ses_paroles(monkeypatch):
    import parole_contexte
    vus = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: vus.append(argv) or _Fini())
    parole_contexte.demander_claude("x")
    assert _effort(vus[0]) == "low"


def test_ses_pensees_importantes(monkeypatch):
    import daemon
    vus = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: vus.append(argv) or _Fini())
    daemon._claude_isole("x")
    assert _effort(vus[0]) == "low"


def test_la_tete_de_fond_du_moteur(monkeypatch):
    import engine
    vus = []
    monkeypatch.setattr(subprocess, "run", lambda argv, **k: vus.append(argv) or _Fini())
    engine.Engine(chat_model="claude:sonnet")._chat_claude([{"role": "user", "content": "x"}], stream=False)
    assert _effort(vus[0]) == "low"


def test_gemma_ne_pense_pas_par_defaut():
    import inspect
    import engine
    assert inspect.signature(engine.Engine.chat).parameters["think"].default is False
