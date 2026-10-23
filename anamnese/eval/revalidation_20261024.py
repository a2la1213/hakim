"""Revalidation de l'affect v2 sur journées neuves et critères de la « surprise » (figés AVANT : eval/affect_v2_predictions.md,
section du 2026-10-24, commit e5e5578).

A : les critères déjà figés (P1-P7, S1-S5 au réglage D2-doux, M1-M7) rejoués sur le seul journal des événements affectifs
    depuis le 22/10 00:00 (jamais servi au réglage). B : Q1-Q3 de la surprise, mesurés sur le même rejeu, AVEC les sujets
    (l'attente apprise s'y attache). C : constat du plafond positif. Tout en mémoire (la vraie n'est jamais touchée).
Usage : .venv/bin/python eval/revalidation_20261024.py [a|b|tout]
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect  # noqa: E402
import affect_v2 as E  # noqa: E402
import config  # noqa: E402

NEUF = time.mktime(time.strptime("2026-10-22 00:00", "%Y-%m-%d %H:%M"))
JOURNAL = config.DATA_DIR / "affect-evenements.jsonl"


def journal(depuis=0.0):
    out = []
    for l in open(JOURNAL, encoding="utf-8"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if float(e.get("ts", 0)) >= depuis and e.get("nom"):
            out.append((float(e["ts"]), str(e["nom"]), float(e.get("intensite", 1.0)), e.get("sujet")))
    return sorted(out, key=lambda x: x[0])


def evenements_neufs(jours=7):                      # remplace E.evenements : les journées neuves seulement, sans sujet
    return [(t, n, i) for t, n, i, _s in journal(NEUF)]


def partie_a():
    E.evenements = evenements_neufs
    import affect_v2_soudain as S
    from affect_v2_reglages import p5_prime
    evs = E.evenements()
    s1v1, t1 = E.p1(E.rejouer(evs, False)), E.p3(False)
    S.regler("D2-doux")
    sat = E.p1(E.rejouer(evs, True))
    r2 = S.p2_seconde()
    t3, h5, d6 = E.p3(True), p5_prime(True), E.p6(True)
    st1, st2, al = S.p7(evs)
    c1, neuf = S.s1()
    c2, c3 = S.s2_s3()
    c4, c5 = S.s4(), S.s5(neuf)
    crit = {"P1": sat <= 0.5 * s1v1 if s1v1 else None, "P2''": r2 >= 0.60, "P3": t3 is not None and t3 <= 1.5 * t1,
            "P4": E.p4(), "P5'": h5 is not None and h5 < 12 * 60, "P6": d6 <= 0.05, "P7": st2 <= st1 + 0.02 and al <= 0.05,
            "S1": c1["tenue"], "S2": c2["tenue"], "S3": c3["tenue"], "S4": c4["tenue"], "S5": c5["tenue"]}
    return {"evenements": len(evs), "saturation": {"v1": round(s1v1, 3), "v2": round(sat, 3)}, "P2''": round(r2, 3),
            "P3_min": {"v1": t1, "v2": t3}, "P5'_min": h5, "P6": round(d6, 3),
            "P7": {"stress_v1": round(st1, 3), "stress_v2": round(st2, 3), "alarme": round(al, 3)},
            "S": {"S1": c1, "S2": c2, "S3": c3, "S4": c4, "S5": c5}, "criteres": crit,
            "rates": [k for k, v in crit.items() if v is False]}


def partie_b():
    """Q1, Q3 sur le rejeu avec sujets (attentes apprises depuis le début du journal, comptées sur les journées neuves) ;
    Q2 sur un scénario ; C : le plafond positif."""
    m = E._Mem(True)
    evs = journal(0.0)
    t, fin, k = evs[0][0], evs[-1][0] + 3600, 0
    affect.get_state(m, now=t)
    marques, n, surprise, plafond = [], 0, 0, 0
    while t <= fin:
        while k < len(evs) and evs[k][0] <= t:
            te, nom, i, sujet = evs[k]
            avant = json.loads(m.kv_get("affect") or "{}").get("_surprise")
            affect.event(m, nom, i, now=te, sujet=sujet)
            apres = json.loads(m.kv_get("affect") or "{}").get("_surprise")
            if apres != avant and te >= NEUF:
                marques.append({"quand": time.strftime("%d/%m %H:%M:%S", time.localtime(te)), "nom": nom, "intensite": i,
                                "sujet": sujet})
            k += 1
        if t >= NEUF:
            s = affect.get_state(m, now=t)
            n += 1
            surprise += affect.emotion_soudaine(m, now=t) == "surprise"
            plafond += s["dopamine"] >= 0.85 or s["ocytocine"] >= 0.85
        t += 60
    q1 = [x for x in marques if x["intensite"] < 0.2]
    # Q2 : un sujet chargé de deux « probleme » 0,5, puis un « succes » 0,8 : combien de minutes de « surprise » ?
    m2, t0 = E._Mem(True), 1_800_000_000.0
    affect.get_state(m2, now=t0)
    affect.event(m2, "probleme", 0.5, now=t0, sujet="le calcul de la toupie")
    affect.event(m2, "probleme", 0.5, now=t0 + 1800, sujet="le calcul de la toupie")
    affect.event(m2, "succes", 0.8, now=t0 + 3600, sujet="le calcul de la toupie")
    minutes = sum(affect.emotion_soudaine(m2, now=t0 + 3600 + 60 * j) == "surprise" for j in range(30))
    return {"minutes_echantillonnees": n, "marques_de_surprise": marques, "Q1_petites": q1, "Q1": not q1,
            "part_surprise": round(surprise / max(1, n), 4), "Q2_minutes": minutes, "Q2": minutes >= 10,
            "C_plafond_dopamine_ou_ocytocine_085": round(plafond / max(1, n), 3)}


def main():
    quoi = sys.argv[1] if len(sys.argv) > 1 else "tout"
    taille = JOURNAL.stat().st_size
    res = {"depuis": time.strftime("%d/%m/%Y %H:%M", time.localtime(NEUF)), "regle_surprise": {
        "r_min": getattr(affect, "SURPRISE_R_MIN", None), "duree_max_s": affect.SURPRISE_S}}
    if quoi in ("b", "tout"):
        res["B"] = partie_b()
    if quoi in ("a", "tout"):
        res["A"] = partie_a()
    assert JOURNAL.stat().st_size >= taille            # le rejeu n'écrit jamais dans le vrai journal (il peut grandir seul)
    print(json.dumps(res, ensure_ascii=False, indent=1))
    sortie = Path(__file__).resolve().parent / "data" / f"revalidation-{time.strftime('%Y%m%d-%H%M')}-{quoi}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(f"détail : {sortie}")


if __name__ == "__main__":
    main()
