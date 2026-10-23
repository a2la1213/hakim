"""Ses agents : les lister, en arrêter un (jarvis/agents_hakim.py, 2026-10-23) — la demande écrite, la réponse du cockpit."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import agents_hakim as A  # noqa: E402


def _dossier(tmp_path):
    (tmp_path / "agents-en-cours.json").write_text(json.dumps({"agents": [
        {"id": "t1", "description": "Juge du calcul", "type": "juge", "ts": 1_800_000_000_000},
        {"id": "t2", "description": "Codeur du banc", "type": "codeur"}]}))
    return tmp_path


def test_lister_et_trouver(tmp_path):
    d = _dossier(tmp_path)
    assert "t1 : « Juge du calcul » (agent juge, depuis 10 min)" in A.lister(d, maintenant=1_800_000_600)
    assert A.trouver("t2", d)["id"] == "t2" and A.trouver("juge du CALCUL", d)["id"] == "t1"
    assert A.trouver("du", d) is None                     # ambigu : deux agents le contiennent
    assert "Aucun" in A.lister(tmp_path / "vide")


def test_l_arret_passe_par_le_cockpit_et_revient(tmp_path):
    d = _dossier(tmp_path)

    def cockpit():                                       # le cockpit lit la demande et répond
        for _ in range(40):
            f = d / "agents-arreter.jsonl"
            if f.exists():
                q = json.loads(f.read_text().splitlines()[-1])
                (d / "agents-arrets.jsonl").write_text(json.dumps({"demande": q["demande"], "ok": True, "id": q["id"]}) + "\n")
                return
            time.sleep(0.05)
    threading.Thread(target=cockpit).start()
    r = A.demander_arret("Juge du calcul", "il tourne en rond", d, attente_s=3, pas_s=0.05)
    assert "arrêté" in r and json.loads((d / "agents-arreter.jsonl").read_text())["id"] == "t1"
    assert "pas" in A.demander_arret("inconnu", "x", d) or "ne trouve pas" in A.demander_arret("inconnu", "x", d)
    assert "raison" in A.demander_arret("t2", "  ", d)
