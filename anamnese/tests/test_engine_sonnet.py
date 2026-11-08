"""(27/10, Ahmed : « on remplace Gemma par Sonnet, même les rêves ») La tête de fond pense avec Claude Sonnet, isolé
(ni réglages ni hooks de l'utilisateur, ni outils, ni serveur MCP, au forfait), Gemma en secours ; chaque appel est
journalisé, et un plafond par jour protège d'un emballement."""
import json
import subprocess

import pytest
import requests

import engine


@pytest.fixture(autouse=True)
def _journal(tmp_path, monkeypatch):
    monkeypatch.setattr(engine, "JOURNAL_APPELS", tmp_path / "llm-appels.jsonl")
    monkeypatch.setattr(engine, "_appels_du_jour", {"jour": "", "n": 0})
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ne-doit-pas-passer")


def _journal_lu():
    try:
        return [json.loads(l) for l in engine.JOURNAL_APPELS.read_text().splitlines()]
    except OSError:
        return []


class _Run:
    def __init__(self, sortie):
        self.sortie, self.appels = sortie, []

    def __call__(self, cmd, **k):
        self.appels.append((cmd, k))
        return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(self.sortie), stderr="")


class _Ollama:
    """Gemma en secours : la voie Ollama."""
    def __init__(self):
        self.appels = 0

    def __call__(self, url, json=None, timeout=None, stream=False):
        self.appels += 1

        class R:
            def raise_for_status(self):
                pass

            def json(self):
                return {"message": {"content": "pensée de Gemma"}}
        return R()


def test_sonnet_isole_au_forfait_et_journalise(monkeypatch):
    run = _Run({"result": "Une pensée de Sonnet.", "is_error": False, "total_cost_usd": 0.004})
    monkeypatch.setattr(engine.subprocess, "run", run)
    e = engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local")
    assert e.chat([{"role": "user", "content": "Pense."}], stream=False) == "Une pensée de Sonnet."
    cmd, k = run.appels[0]
    assert cmd[cmd.index("--model") + 1] == "sonnet"
    assert "--restricted" in cmd and "--strict-mcp-config" in cmd and "--no-session-persistence" in cmd
    assert cmd[cmd.index("--tools") + 1] == ""
    assert "ANTHROPIC_API_KEY" not in k["env"] and k["env"]["ANAMNESE_HEADLESS"] == "1"
    assert k["cwd"] and "anamnese" not in str(k["cwd"]).lower()                  # un dossier vide
    assert e.dernier == "sonnet"
    j = _journal_lu()[-1]
    assert j["modele"] == "sonnet" and j["cout_usd"] == 0.004 and not j["erreur"]


def test_un_echec_ou_un_refus_de_sonnet_retombe_sur_gemma(monkeypatch):
    monkeypatch.setattr(engine.subprocess, "run", _Run({"result": "API Error: refusal", "is_error": True}))
    ollama = _Ollama()
    monkeypatch.setattr(engine.requests, "post", ollama)
    e = engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local")
    assert e.chat([{"role": "user", "content": "Pense."}], stream=False) == "pensée de Gemma"
    assert ollama.appels == 1 and e.dernier == "gemma"
    assert [x["modele"] for x in _journal_lu()] == ["sonnet", "gemma (secours)"] and _journal_lu()[0]["erreur"]


def test_sans_secours_l_echec_leve_comme_avant(monkeypatch):
    monkeypatch.setattr(engine.subprocess, "run", _Run({"result": "", "is_error": True}))
    with pytest.raises(requests.RequestException):
        engine.Engine(chat_model="claude:sonnet").chat([{"role": "user", "content": "x"}], stream=False)


def test_le_plafond_du_jour_passe_la_main_a_gemma(monkeypatch):
    run = _Run({"result": "ok", "is_error": False})
    monkeypatch.setattr(engine.subprocess, "run", run)
    ollama = _Ollama()
    monkeypatch.setattr(engine.requests, "post", ollama)
    monkeypatch.setattr(engine, "CLAUDE_MAX_JOUR", 3)
    e = engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local")
    sorties = [e.chat([{"role": "user", "content": "x"}], stream=False) for _ in range(5)]
    assert sorties == ["ok", "ok", "ok", "pensée de Gemma", "pensée de Gemma"] and len(run.appels) == 3


def test_sonnet_est_vivant_meme_sans_ollama(monkeypatch):
    def mort(*a, **k):
        raise requests.ConnectionError("Ollama éteint")
    monkeypatch.setattr(engine.requests, "get", mort)
    assert engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local").health() is True
    assert engine.Engine(chat_model="gemma-local").health() is False


def test_gemma_seule_ne_journalise_rien(monkeypatch):
    monkeypatch.setattr(engine.requests, "post", _Ollama())
    assert engine.Engine(chat_model="gemma-local").chat([{"role": "user", "content": "x"}], stream=False) == "pensée de Gemma"
    assert _journal_lu() == []


def test_le_demon_pense_avec_sonnet_gemma_en_secours():
    import config
    assert config.DAEMON_MODEL == "claude:sonnet" and "gemma" in config.DAEMON_SECOURS
    src = open(config.__file__.replace("config.py", "daemon.py"), encoding="utf-8").read()
    assert "Engine(chat_model=config.DAEMON_MODEL, secours_model=config.DAEMON_SECOURS)" in src


def test_le_plafond_survit_a_un_redemarrage_du_demon(monkeypatch):
    # (deuxième relecture du 27/10) le compte du jour se relit dans le journal des appels
    import time as _t
    engine.JOURNAL_APPELS.write_text("".join(json.dumps({"ts": _t.time(), "modele": "sonnet"}) + "\n" for _ in range(3))
                                     + json.dumps({"ts": _t.time(), "modele": "gemma (secours)"}) + "\n")
    monkeypatch.setattr(engine, "CLAUDE_MAX_JOUR", 3)
    run = _Run({"result": "ok", "is_error": False})
    monkeypatch.setattr(engine.subprocess, "run", run)
    monkeypatch.setattr(engine.requests, "post", _Ollama())
    assert engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local").chat([{"role": "user", "content": "x"}], stream=False) == "pensée de Gemma"
    assert run.appels == []


def test_les_questions_des_silences_ne_comptent_pas_dans_le_plafond_du_demon(monkeypatch):
    # (27/10, meubler les silences) le cockpit journalise ses petites questions à Sonnet au même endroit (étiquette
    # « silence », source « cockpit ») : elles ont leur propre plafond, et ne retirent rien à la tête de fond du démon
    import time as _t
    engine.JOURNAL_APPELS.write_text("".join(json.dumps({"ts": _t.time(), "modele": "sonnet", "etiquette": "silence", "source": "cockpit"}) + "\n"
                                             for _ in range(5)))
    monkeypatch.setattr(engine, "CLAUDE_MAX_JOUR", 3)
    run = _Run({"result": "ok", "is_error": False})
    monkeypatch.setattr(engine.subprocess, "run", run)
    monkeypatch.setattr(engine.requests, "post", _Ollama())
    assert engine.Engine(chat_model="claude:sonnet", secours_model="gemma-local").chat([{"role": "user", "content": "x"}], stream=False) == "ok"
    assert len(run.appels) == 1
