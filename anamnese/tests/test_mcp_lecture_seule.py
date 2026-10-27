"""Serveur MCP en lecture seule pour les missions (audit JARVIS 2, H5, 2026-10-20).

Une mission « lecture seule » recevait tout le serveur de mémoire : memory_store, self_update, skill_save,
rubric_*, courrier_envoyer… Avec ANAMNESE_LECTURE_SEULE=1, les outils qui écrivent n'existent plus.
Testé dans un processus à part : le retrait modifie le serveur du module.
"""
import json
import os
import subprocess
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parent.parent
# la sonde ouvre une base temporaire, jamais data/memory.db
SONDE = ("import asyncio, json, sys, memory; _M = memory.Memory; "
         "memory.Memory = lambda *a, **k: _M(db_path=sys.argv[1]); import mcp_server; "
         "print(json.dumps([sorted(t.name for t in asyncio.run(mcp_server.mcp.list_tools())), "
         "sorted(mcp_server.OUTILS_LECTURE)]))")


def _sonde(lecture_seule, tmp_path, **plus):
    env = {**os.environ, "PYTHONPATH": str(RACINE), **plus}
    env.pop("ANAMNESE_LECTURE_SEULE", None)
    if "ANAMNESE_REVEIL_MAMAN" not in plus:
        env.pop("ANAMNESE_REVEIL_MAMAN", None)
    if lecture_seule:
        env["ANAMNESE_LECTURE_SEULE"] = "1"
    r = subprocess.run([sys.executable, "-c", SONDE, str(tmp_path / "sonde.db")], cwd=RACINE, env=env, capture_output=True, text=True,
                       timeout=120, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, r.stderr[-2000:]
    outils, lecture = json.loads(r.stdout.strip().splitlines()[-1])
    return set(outils), set(lecture)


def test_lecture_seule_retire_tout_ce_qui_ecrit(tmp_path):
    (complet, permis), (lecture, _p) = _sonde(False, tmp_path), _sonde(True, tmp_path)
    assert lecture == complet & permis
    for ecrit in ("memory_store", "memory_store_in", "self_update", "self_append", "skill_save", "rubric_create",
                  "memory_reclassify", "taxonomy_undo", "courrier_envoyer", "mission_proposer", "affect_event"):
        if ecrit in complet:
            assert ecrit not in lecture
    assert {"memory_recall", "self_get", "rubric_tree"} <= lecture


def test_sans_la_variable_rien_n_est_retire(tmp_path):
    assert {"memory_store", "self_update"} <= _sonde(False, tmp_path)[0]


def test_le_reveil_de_maman_ne_garde_en_plus_que_le_courrier(tmp_path):
    # (27/10) Claude Code réveillée seule par une lettre : lecture seule côté serveur aussi (deuxième barrière, après
    # dontAsk), avec la seule écriture permise : répondre à Hakim
    (lecture, permis) = _sonde(True, tmp_path)
    maman_outils, _p = _sonde(True, tmp_path, ANAMNESE_REVEIL_MAMAN="1")
    assert maman_outils == lecture | {"courrier_envoyer"}
    assert not {"memory_store", "memory_store_in", "affect_event", "self_update", "mission_proposer"} & maman_outils
