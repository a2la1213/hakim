"""Orchestre le micro-pilote — ENTRELACÉ (A puis B, tâche par tâche) pour qu'une limite
d'usage frappe les 2 bras À ÉGALITÉ, avec STOP dès qu'un run est bidon (non-mesure : un
`claude -p` de <30s = modèle jamais appelé = limite de forfait). Isolation : run_arm cache
~/.claude/CLAUDE.md pour le bras A (restauré même si crash). Notation container-free par paire.

Usage :  python -m eval.agent.run_pilot         # 3 tâches (6 runs — tient dans une fenêtre)
         python -m eval.agent.run_pilot smoke   # 1 tâche (2 runs — check rapide)"""
import json, sys
from pathlib import Path
from eval.agent import select_tasks, run_arm, grade_local as grade, report
HERE = Path(__file__).resolve().parent

def pilot(n=3, smoke=False, hard=True):
    tasks = select_tasks.main(n=n, hard=hard)
    if not grade.sanity_oracle(tasks[0]):
        raise SystemExit("STOP: le notateur ne valide pas le gold_patch — chaîne cassée, rien n'est dépensé.")
    if smoke:
        tasks = tasks[:1]
    resA, resB, valid_ids, limited = set(), set(), [], []
    scA, scB, uA_all, uB_all = {}, {}, [], []
    pA = open(HERE / "preds_A.jsonl", "w"); pB = open(HERE / "preds_B.jsonl", "w")
    uAf = open(HERE / "usage_A.jsonl", "w"); uBf = open(HERE / "usage_B.jsonl", "w")
    try:
        for t in tasks:
            with run_arm.claude_md_hidden(hide=True):
                predA, uA = run_arm.run_task(t, "A")
            predB, uB = run_arm.run_task(t, "B")
            for f, obj in ((pA, predA), (pB, predB), (uAf, uA), (uBf, uB)):
                f.write(json.dumps(obj) + "\n"); f.flush()
            uA_all.append(uA); uB_all.append(uB)
            scA[t["instance_id"]] = uA.get("selfcheck", "NONE")
            scB[t["instance_id"]] = uB.get("selfcheck", "NONE")
            print(f"  {t['instance_id']} : A={uA.get('seconds')}s/{scA[t['instance_id']]}  B={uB.get('seconds')}s/{scB[t['instance_id']]}")
            if not run_arm.is_valid(uA) or not run_arm.is_valid(uB):
                print(f"⚠️  run bidon sur {t['instance_id']} — STOP.")
                limited.append(t["instance_id"]); break
            valid_ids.append(t["instance_id"])
            if grade.resolve_task(t, predA["model_patch"]): resA.add(t["instance_id"])
            if grade.resolve_task(t, predB["model_patch"]): resB.add(t["instance_id"])
    finally:
        for f in (pA, pB, uAf, uBf): f.close()
    sc = report.build_scorecard(valid_ids, resA, resB, uA_all[:len(valid_ids)], uB_all[:len(valid_ids)])
    sc["taches_valides"] = len(valid_ids); sc["taches_limitees"] = limited
    sc["calibration"] = report.calibration_scorecard(
        valid_ids, resA, resB,
        {i: scA[i] for i in valid_ids}, {i: scB[i] for i in valid_ids})
    (HERE / "scorecard_agent.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False))
    print(json.dumps(sc, indent=2, ensure_ascii=False))
    return sc

if __name__ == "__main__":
    smoke = "smoke" in sys.argv[1:]
    pilot(n=(1 if smoke else 3), smoke=smoke, hard=True)
