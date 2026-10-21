"""Quatrième et cinquième passages de l'affect v2 : P2 reformulé (à marge égale), émotions soudaines, subconscient.
Grille, critères et règle figés AVANT le code et la mesure (eval/affect_v2_predictions.md, commits 5deb0c9, 0eb744a).
Usage : .venv/bin/python eval/affect_v2_soudain.py"""
import copy
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect  # noqa: E402
import affect_v2 as E  # noqa: E402
from affect_v2_reglages import p5_prime  # noqa: E402

T0, MIDI = 1_800_000_000.0, 12
DESENS = {"D0": (0.0, 1.0, 0.0), "D1": (1.0, 1.0, 0.0), "D2": (0.25, 0.5, 0.0), "D3": (0.5, 1.0, 1.0)}
GRILLE = {f"{d}-{p}": (*DESENS[d], p == "doux") for d in DESENS for p in ("dur", "doux")}


def regler(nom):
    e, t, prol, doux = GRILLE[nom]
    affect.DESENS_ECHELLE, affect.DESENS_TAU_ECHELLE, affect.DESENS_PROLONGE_H, affect.PLAFOND_DOUX = e, t, prol, doux


def ev(m, nom, t, i=1.0, sujet=None):
    return affect.event(m, nom, i, now=t, hour=MIDI, sujet=sujet)


def st(m, t):
    return affect.get_state(m, now=t, hour=MIDI)


def a_la_base(m, t, garder=None):
    """Les niveaux remis à leur base, l'appris gardé (tout ce qui commence par _, ou seulement `garder`)."""
    d = json.loads(m._kv["affect"])
    gardes = {k: v for k, v in d.items() if k.startswith("_") and (garder is None or k in garder)}
    if garder is not None and "_cog" in garder and "_cog" in d:
        gardes["_cog"] = {"V": d["_cog"].get("V", {})}
    m._kv["affect"] = json.dumps({**affect.bases(v2=True), **gardes, "_ts": t})


def hausse(m, nom, t, i, sujet=None, h="adrenaline", apres_s=0):
    avant = st(m, t)[h]
    ev(m, nom, t, i, sujet)
    return st(m, t + apres_s)[h] - avant


def p2_seconde():
    frais = E._Mem(True)
    st(frais, T0)
    ref = hausse(frais, "succes", T0, 1.0, h="dopamine")
    m, t = E._Mem(True), T0
    for k in range(10):
        ev(m, "succes", t, 0.3)
        t += 360
    a_la_base(m, t)
    return hausse(m, "succes", t, 1.0, h="dopamine") / ref


def p7(evs):
    """(part du temps stress ≥ 0,85 en v1, en v2 ; part du temps « alarme » en v2) sur le rejeu."""
    parts = []
    for v2 in (False, True):
        m = E._Mem(v2)
        t, fin, k, n, stress, alarme = evs[0][0], evs[-1][0] + 6 * 3600, 0, 0, 0, 0
        affect.get_state(m, now=t)
        while t <= fin:
            while k < len(evs) and evs[k][0] <= t:
                affect.event(m, evs[k][1], evs[k][2], now=evs[k][0])
                k += 1
            s = affect.get_state(m, now=t)
            n += 1
            stress += s["noradrenaline"] >= 0.85 or s["cortisol"] >= 0.85
            alarme += v2 and affect.emotion_soudaine(m, now=t) == "alarme"
            t += 600
        parts.append((stress / n, alarme / n))
    return parts[0][0], parts[1][0], parts[1][1]


def s1():
    m = E._Mem(True)
    st(m, T0)
    neuf = hausse(m, "nouveaute", T0, 1.0, "un bruit inconnu", apres_s=60)
    m = E._Mem(True)
    for k in range(5):
        ev(m, "succes", T0 + k * 86400, 0.3, "le jardin")
    familier = hausse(m, "nouveaute", T0 + 5 * 86400, 1.0, "le jardin", apres_s=60)
    m = E._Mem(True)
    st(m, T0)
    faible = hausse(m, "nouveaute", T0, 0.3, "un bruit inconnu", apres_s=60)
    return {"neuf": round(neuf, 3), "familier": round(familier, 3), "faible": round(faible, 3),
            "tenue": neuf >= 0.25 and familier <= 0.5 * neuf and faible < 0.10}, neuf


def _histoire():
    m, t = E._Mem(True), T0
    for k in range(5):
        ev(m, "succes", t - (5 - k) * 86400, 0.3, "le jardin")
    for k in range(3):
        ev(m, "echec", t + k * 7200, 1.0, "le déploiement")
    return m, t + 2 * 7200


def _rapport(m, t):
    st(m, t)
    jumeau = copy.deepcopy(m)
    return hausse(m, "probleme", t, 0.5, "le déploiement") / max(1e-9, hausse(jumeau, "probleme", t, 0.5, "le jardin"))


def s2_s3():
    m, t = _histoire()
    r2 = _rapport(m, t + 6 * 3600)
    m, t = _histoire()
    t += 6 * 3600
    for k in range(3):
        ev(m, "resolu", t + k * 3600, 1.0, "le déploiement")
    r3a = _rapport(m, t + 3 * 3600)
    m, t = _histoire()
    r3b = _rapport(m, t + 96 * 3600)
    return ({"rapport": round(r2, 3), "tenue": r2 >= 1.5},
            {"apres_resolu": round(r3a, 3), "apres_96h": round(r3b, 3), "tenue": r3a < 1.25 and r3b < 1.25})


def s4():
    res = {}
    for physio_egale in (True, False):
        hausses = []
        for prealable in ("echec", "succes"):
            m = E._Mem(True)
            for k in range(3):
                ev(m, prealable, T0 + k * 600)
            t = T0 + 3 * 600
            if physio_egale:
                a_la_base(m, t, garder={"_vm", "_cog"})
            hausses.append(hausse(m, "succes", t, 0.6, h="dopamine"))
        res["physio_egale" if physio_egale else "complet"] = [round(x, 3) for x in hausses]
    pe, co = res["physio_egale"], res["complet"]
    res["tenue"] = pe[0] >= 1.5 * pe[1] and co[0] > co[1]
    return res


def s5(neuf):
    m, t = E._Mem(True), T0
    for k in range(10):
        ev(m, "nouveaute", t, 0.3, "le même bruit")
        t += 360
    h = hausse(m, "nouveaute", t, 1.0, "un sujet neuf", apres_s=60)
    return {"hausse": round(h, 3), "rapport": round(h / neuf, 3), "tenue": h >= 0.7 * neuf}


def main():
    evs = E.evenements()
    s1v1, t1 = E.p1(E.rejouer(evs, False)), E.p3(False)
    res = {}
    for nom in GRILLE:
        regler(nom)
        sat = E.p1(E.rejouer(evs, True))
        r2 = p2_seconde()
        t3, h5, d6 = E.p3(True), p5_prime(True), E.p6(True)
        st1, st2, al = p7(evs)
        c1, neuf = s1()
        c2, c3 = s2_s3()
        crit = {"P1": sat <= 0.5 * s1v1, "P2''": r2 >= 0.60, "P3": t3 is not None and t3 <= 1.5 * t1, "P4": E.p4(),
                "P5'": h5 is not None and h5 < 12 * 60, "P6": d6 <= 0.05, "P7": st2 <= st1 + 0.02 and al <= 0.05,
                "S1": c1["tenue"], "S2": c2["tenue"], "S3": c3["tenue"]}
        c4, c5 = s4(), s5(neuf)
        crit.update(S4=c4["tenue"], S5=c5["tenue"])
        res[nom] = {"saturation": round(sat, 3), "P2''": round(r2, 3), "P3_min": t3, "P5'_min": h5, "P6": round(d6, 3),
                    "P7": {"stress_v1": round(st1, 3), "stress_v2": round(st2, 3), "alarme": round(al, 3)},
                    "S1": c1, "S2": c2, "S3": c3, "S4": c4, "S5": c5,
                    "rates": [k for k, v in crit.items() if not v], "tous": all(crit.values())}
        print(nom, json.dumps(res[nom], ensure_ascii=False))
    regler("D2-doux")                                    # les valeurs par défaut du module (choisies au 5e passage)
    ok = [n for n, x in res.items() if x["tous"]]
    # règle du cinquième passage (figée avant, 0eb744a) : le moins saturé ; à égalité, une désensibilisation gardée (le
    # réel), puis la réactivité P2ʺ la plus haute, puis l'ordre de la grille (au quatrième : saturation puis ordre)
    choix = min(ok, key=lambda n: (res[n]["saturation"], n.startswith("D0"), -res[n]["P2''"],
                                   list(GRILLE).index(n))) if ok else None
    print(f"\n{len(evs)} événements rejoués ; v1 : saturation {s1v1:.3f}, retour au calme {t1} min")
    print(f"réglages qui tiennent tout : {ok or 'aucun'} → choix : {choix}")
    sortie = Path(__file__).resolve().parent / "data" / f"affect_v2_soudain-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.parent.mkdir(parents=True, exist_ok=True)
    sortie.write_text(json.dumps({"evenements": len(evs), "v1": {"saturation": s1v1, "P3_min": t1}, "grille": res,
                                  "choix": choix}, ensure_ascii=False, indent=1))
    print(f"détail : {sortie}")


if __name__ == "__main__":
    main()
