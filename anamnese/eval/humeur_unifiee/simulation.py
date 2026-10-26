"""Simulation exhaustive de l'humeur unifiée (attentes figées AVANT : eval/humeur_unifiee/predictions.md).
Usage : .venv/bin/python eval/humeur_unifiee/simulation.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import affect  # noqa: E402
import interieur  # noqa: E402
import sensations  # noqa: E402

T0 = 1_800_000_000.0 + 10 * 3600          # un milieu de journée (l'heure joue sur le circadien)
TENSION, POSITIF = {"tension", "alarme"}, {"joie", "elan", "content"}
SCENARIOS = {
    "S1": ([(0, "attaque", 0.8)], 0, 10, TENSION),
    "S2": ([(60, "soutien", 0.7)], 60, 70, POSITIF),
    "S3": ([(0, "probleme", 0.6), (10, "probleme", 0.6), (20, "probleme", 0.6)], 0, 30, TENSION),
    "S4": ([(0, "echec", 0.9)], 0, 15, TENSION | {"morose"}),
    "S5": ([(0, "tristesse", 0.7)], 0, 15, {"morose", "ennui"}),
    "S6": ([(0, "peur", 0.7)], 0, 10, TENSION),
    "S7": ([(0, "joie", 0.7)], 0, 10, {"joie", "elan"}),
    "S8": ([(0, "affirmation", 0.8)], 0, 10, POSITIF),
    "S9": ([(0, "colere", 0.7)], 0, 10, TENSION),
    "S10": ([], 180, 240, {"morose"}),
    "S11": ([], 110, 120, {"calme", "apaisement"}),
    "S12": ([(0, "soutien", 0.7), (10, "probleme", 0.6)], 10, 20, TENSION),
}
DUREE = {"S10": 240, "S11": 120, "S2": 80}


class _Mem:
    def __init__(self):
        self._kv = {"affect_v2": "1"}

    def kv_get(self, k, d=None):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def jouer(nom):
    evs, debut, fin, attendu = SCENARIOS[nom]
    m, ade, avant, hist, out = _Mem(), sensations.ADENOSINE_BASE, None, [], []
    affect.get_state(m, now=T0 - 3600)
    k = 0
    for minute in range(-30, DUREE.get(nom, 40) + 1):
        t = T0 + 60 * minute
        while k < len(evs) and T0 + 60 * evs[k][0] <= t:
            affect.event(m, evs[k][1], evs[k][2], now=t, sujet="scenario")
            k += 1
        etat = affect.get_state(m, now=t)
        ade = interieur.adenosine(ade, 60, False, nom == "S10", nom == "S10")
        etat = {**etat, "adenosine": ade}
        hist.append(etat)
        passe = hist[-11] if len(hist) > 10 else hist[0]
        sens = sensations.calculer(etat, passe, t, affect.emotion_soudaine(m, now=t), time.localtime(t).tm_hour, sans_coherence=True)
        avant = interieur.humeur_hormonale(sens, avant)
        out.append((minute, avant, interieur.FAMILLE_HUMEUR.get(avant, "calme")))
    fenetre = [x for x in out if debut <= x[0] <= fin]
    run, meilleur = 0, 0
    for _m, _e, code in fenetre:
        run = run + 1 if code in attendu else 0
        meilleur = max(meilleur, run)
    return {"tenu": meilleur >= 3, "minutes_attendues_de_suite": meilleur,
            "humeurs": sorted({e for _m, e, _c in fenetre}), "fin": fenetre[-1][1] if fenetre else None}


def variante(nom):
    """A : un aversif met fin à la surprise ; B : A + bonus de surprise 0,4 (les deux sur une copie en mémoire du module)."""
    import sensations as SE
    orig_event, orig_bonus = affect._event_v2, dict(SE.SOUDAINES)

    def event_a(mem, name, intensity=1.0, now=None, hour=None, sujet=None):
        etat = orig_event(mem, name, intensity, now=now, hour=hour, sujet=sujet)
        if name in affect.AVERSIFS:
            d = json.loads(mem.kv_get("affect") or "{}")
            d["_surprise"] = 0
            mem.kv_set("affect", json.dumps(d))
        return etat
    affect._event_v2 = event_a
    if nom == "B":
        SE.SOUDAINES["surprise"] = ("surprise", 0.4)
    try:
        return {n: jouer(n) for n in SCENARIOS}
    finally:
        affect._event_v2 = orig_event
        SE.SOUDAINES.clear(); SE.SOUDAINES.update(orig_bonus)


def second_tour():
    deja = {"S1", "S3", "S4", "S5", "S6", "S9", "S10", "S11"}
    out = {}
    for v in ("A", "B"):
        r = variante(v)
        out[v] = {"tenus": sorted(n for n, x in r.items() if x["tenu"]), "detail": r}
        print(v, len(out[v]["tenus"]), "/ 12 :", out[v]["tenus"], flush=True)
    ok = [v for v in ("A", "B") if deja <= set(out[v]["tenus"])]
    retenue = max(ok, key=lambda v: (len(out[v]["tenus"]), v == "A")) if ok else None
    print("retenue :", retenue)
    sortie = Path(__file__).resolve().parents[1] / "data" / f"humeur-unifiee-tour2-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps({**out, "retenue": retenue}, ensure_ascii=False, indent=1))


def main():
    res = {n: jouer(n) for n in SCENARIOS}
    for n, r in res.items():
        print(n, json.dumps(r, ensure_ascii=False), flush=True)
    print("tenus :", sum(r["tenu"] for r in res.values()), "/", len(res))
    sortie = Path(__file__).resolve().parents[1] / "data" / f"humeur-unifiee-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    second_tour() if sys.argv[1:] == ["tour2"] else main()
