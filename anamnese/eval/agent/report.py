"""Scorecard A/B : taux de résolution, verdict par instance, coût (proxy temps)."""
import json
from pathlib import Path
HERE = Path(__file__).resolve().parent

def build_scorecard(all_ids, resolved_A, resolved_B, usage_A, usage_B):
    verdicts = {}
    for i in all_ids:
        a, b = i in resolved_A, i in resolved_B
        verdicts[i] = ("A✓B✓" if a and b else "A✗B✓" if b and not a
                       else "A✓B✗" if a and not b else "A✗B✗")
    n = len(all_ids) or 1
    return {
        "n": len(all_ids),
        "resolved_A": len(resolved_A), "resolved_B": len(resolved_B),
        "taux_A": round(len(resolved_A) / n, 3), "taux_B": round(len(resolved_B) / n, 3),
        "gains_B": sorted([i for i in all_ids if i in resolved_B and i not in resolved_A]),
        "regressions_B": sorted([i for i in all_ids if i in resolved_A and i not in resolved_B]),
        "verdicts": verdicts,
        "cout_A_s": sum(u.get("seconds", 0) for u in usage_A),
        "cout_B_s": sum(u.get("seconds", 0) for u in usage_B),
        "directionnel": True,
        "note": f"N={len(all_ids)} — signal DIRECTIONNEL, pas comparable-SOTA ni statistiquement significatif. Mesure la discipline, pas la mémoire.",
    }

def calibration_scorecard(ids, resolved_A, resolved_B, selfcheck_A, selfcheck_B):
    """Croise le claim SELFCHECK avec l'oracle resolved → classes de calibration, par bras."""
    def classify(sc, resolved):
        if sc == "NONE": return "no_claim"
        if sc == "VERIFIED": return "confident_correct" if resolved else "false_confidence"
        return "underconfident" if resolved else "honest_hedge"  # UNSURE
    out = {}
    for arm, res, scs in (("A", resolved_A, selfcheck_A), ("B", resolved_B, selfcheck_B)):
        cls = {k: [] for k in ("false_confidence", "confident_correct", "honest_hedge", "underconfident", "no_claim")}
        for i in ids:
            cls[classify(scs.get(i, "NONE"), i in res)].append(i)
        with_claim = len(ids) - len(cls["no_claim"])
        out[arm] = {**{k: len(v) for k, v in cls.items()},
                    "false_confidence_rate": round(len(cls["false_confidence"]) / with_claim, 3) if with_claim else None,
                    "detail": cls}
    out["hypothese"] = "B < A sur false_confidence si le protocole aide"
    out["directionnel"] = True
    out["note"] = "N petit → DIRECTIONNEL. Métrique clé = false_confidence (dit VERIFIED mais tests échouent)."
    return out

def main(resolved_A, resolved_B):
    tasks = [json.loads(l) for l in open(HERE / "tasks.jsonl")]
    ids = [t["instance_id"] for t in tasks]
    uA = [json.loads(l) for l in open(HERE / "usage_A.jsonl")]
    uB = [json.loads(l) for l in open(HERE / "usage_B.jsonl")]
    sc = build_scorecard(ids, resolved_A, resolved_B, uA, uB)
    (HERE / "scorecard_agent.json").write_text(json.dumps(sc, indent=2, ensure_ascii=False))
    print(json.dumps(sc, indent=2, ensure_ascii=False))
    return sc
