"""Le ressenti en réserve sur la Gemma d'Ollama (24/10, piste 3 validée par Ahmed) : même calcul que le chemin MLX, sur
les 20 jetons suivants qu'Ollama rend ; le démon ne décharge plus la Gemma d'Ollama pour lui. Sans Ollama ni MLX ici."""
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


@pytest.fixture
def scanner(monkeypatch):
    pytest.importorskip("numpy")
    import types
    sys.modules.setdefault("pilotage", types.SimpleNamespace())          # le chemin MLX n'est pas chargé ici
    import scanner as S
    return S


def test_les_mots_qui_montent_sous_l_humeur(scanner, monkeypatch):
    neutre = {" une": -0.3, " comme": -2.0, " douce": -4.0, " lour": -6.0, " là": -5.0}
    teinte = {" lour": -0.3, " pesante": -1.9, " une": -4.4, " comme": -3.0, " sour": -4.0, " là": -5.5}
    suites = {" lour": "de, comme", " pesante": " et", " sour": "de"}
    def faux(prompt, n=1, top=20):
        if n == 1:
            d = teinte if "Ton humeur en ce moment" in prompt else neutre
            return {"logprobs": [{"top_logprobs": [{"token": t, "logprob": v} for t, v in d.items()]}]}
        piece = next(p for p in suites if prompt.endswith(p))
        return {"response": suites[piece]}
    monkeypatch.setattr(scanner, "_ollama", faux)
    mots = scanner.ressenti_ollama("morosité", "On a perdu le calcul de la nuit.", sondes=["Au fond de moi, la sensation est"])
    assert [w for w, _ in mots][:3] == ["lourde", "pesante", "sourde"]
    assert mots[0][1] == pytest.approx(5.7)                              # −0,3 − (−6,0)
    assert dict(mots)["pesante"] == pytest.approx(-1.9 - (-6.0))         # absent des 20 neutres : borné par le plus faible
    assert "comme" not in dict(mots) and "une" not in dict(mots)        # mots vides ou en baisse


def test_le_demon_ne_decharge_plus_la_gemma_d_ollama(monkeypatch, tmp_path):
    """Moteur « ollama » (par défaut) : aucun appel pour décharger Gemma ; moteur « mlx » (repli) : elle est déchargée."""
    import daemon
    class Mem:
        def kv_get(self, k):
            return json.dumps({"humeur": "élan"})
    monkeypatch.setattr(daemon, "_derniers_mots_d_ahmed", lambda journal, maintenant: ("Bonjour frérot, on lance ?", 123))
    class R:
        returncode, stdout, stderr = 0, '{"mots": ["vive"]}', ""
    lances = []
    monkeypatch.setattr(daemon.subprocess, "run", lambda *a, **k: lances.append(a) or R())
    for moteur, attendu in (("ollama", 0), ("mlx", 1)):
        appels = []
        def urlopen(req, *a, **k):
            appels.append(getattr(req, "full_url", req))
            class Rep:
                def read(self):
                    return json.dumps({"models": [{"name": "huihui_ai/gemma-4-abliterated:12b"}]}).encode()
            return Rep()
        monkeypatch.setattr("urllib.request.urlopen", urlopen)
        monkeypatch.setenv("JARVIS_RESSENTI_MOTEUR", moteur)
        ok = daemon._ressenti_pass(Mem(), now=1_800_000_000 + 10_000 * attendu, sortie=tmp_path / f"r-{moteur}.json")
        decharges = [u for u in appels if str(u).endswith("/api/generate")]
        assert ok and len(decharges) == attendu, (moteur, appels)
