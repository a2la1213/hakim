"""La grille de réglages de l'affect v2 (troisième passage ; grille et règle figées avant dans
eval/affect_v2_predictions.md). Usage : .venv/bin/python eval/affect_v2_reglages.py"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect  # noqa: E402
import affect_v2 as E  # noqa: E402

GRILLE = {
    "R0": dict(DESENS_ECHELLE=0.0, DESENS_TAU_ECHELLE=1.0, DESENS_PROLONGE_H=0.0, HAB_FORCE_EXP=1.0),
    "R1": dict(DESENS_ECHELLE=1.0, DESENS_TAU_ECHELLE=1.0, DESENS_PROLONGE_H=0.0, HAB_FORCE_EXP=1.0),
    "R2": dict(DESENS_ECHELLE=0.25, DESENS_TAU_ECHELLE=0.5, DESENS_PROLONGE_H=0.0, HAB_FORCE_EXP=1.0),
    "R3": dict(DESENS_ECHELLE=0.5, DESENS_TAU_ECHELLE=1.0, DESENS_PROLONGE_H=1.0, HAB_FORCE_EXP=1.0),
    "R4": dict(DESENS_ECHELLE=0.25, DESENS_TAU_ECHELLE=0.5, DESENS_PROLONGE_H=0.0, HAB_FORCE_EXP=2.0),
    "R5": dict(DESENS_ECHELLE=0.5, DESENS_TAU_ECHELLE=1.0, DESENS_PROLONGE_H=1.0, HAB_FORCE_EXP=2.0),
    "R6": dict(DESENS_ECHELLE=0.0, DESENS_TAU_ECHELLE=1.0, DESENS_PROLONGE_H=0.0, HAB_FORCE_EXP=2.0),
}


def p5_prime(v2):
    t0 = 1_800_000_000.0
    m = E._Mem(v2)
    v0, _ = affect.valence_arousal(affect.get_state(m, now=t0, hour=12))
    for k in range(6):
        affect.event(m, "echec", 1.0, now=t0 + k * 1200, hour=12)
    t = t0 + 2 * 3600
    for mn in range(0, 12 * 60 + 1, 5):
        tt = t + mn * 60
        if mn % 30 == 0:
            affect.event(m, "chaleur_user", 1.0, now=tt, hour=12)
            affect.event(m, "succes", 1.0, now=tt, hour=12)
        v, _ = affect.valence_arousal(affect.get_state(m, now=tt, hour=12))
        if v >= v0 - 0.05 and mn > 0:
            return mn
    return None


def main():
    evs = E.evenements()
    e1 = E.rejouer(evs, False)
    s1 = E.p1(e1)
    t1 = E.p3(False)
    res = {}
    for nom, reglage in GRILLE.items():
        for k, v in reglage.items():
            setattr(affect, k, v)
        s2 = E.p1(E.rejouer(evs, True))
        r, _ref, _d = E.p2(True)
        t2 = E.p3(True)
        h2 = p5_prime(True)
        d2 = E.p6(True)
        crit = {"P1": s2 <= 0.5 * s1, "P2": r >= 0.8, "P3": t2 is not None and t2 <= 1.5 * t1, "P4": E.p4(),
                "P5'": h2 is not None and h2 < 12 * 60, "P6": d2 <= 0.05}
        res[nom] = {"saturation": round(s2, 3), "P2": round(r, 3), "P3_min": t2, "P5'_min": h2, "P6": round(d2, 3),
                    "tous": all(crit.values()), "criteres": crit}
        print(nom, json.dumps(res[nom], ensure_ascii=False))
    ok = [n for n, x in res.items() if x["tous"]]
    choix = min(ok, key=lambda n: (res[n]["saturation"], list(GRILLE).index(n))) if ok else None
    print(f"\nv1 : saturation {s1:.3f}, retour au calme {t1} min — réglages qui tiennent tout : {ok or 'aucun'} → choix : {choix}")
    sortie = Path(__file__).resolve().parent / "data" / f"affect_v2_reglages-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps({"v1": {"saturation": s1, "P3_min": t1}, "grille": res, "choix": choix}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
