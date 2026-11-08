"""Le plafond positif : les vrais événements des 72 dernières heures rejoués sur une copie en mémoire, sous cinq variantes
(critères figés AVANT : eval/plafond/predictions.md, commit c5f7c84). Rien n'est écrit dans la vraie mémoire.
Usage : .venv/bin/python eval/plafond/simulation.py   (écrit eval/data/plafond-<date>.json)
"""
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import affect  # noqa: E402
import config  # noqa: E402
import interieur  # noqa: E402
import sensations  # noqa: E402
import style  # noqa: E402

FIN = time.time()
DEBUT = FIN - 72 * 3600
NEGATIFS, PAS = {"probleme", "echec", "attaque"}, 60
ALERTE_BAS = set(style.FAMILLES["alerte"]) | set(style.FAMILLES["bas"])


class _Mem:
    def __init__(self):
        self._kv = {"affect_v2": "1"}

    def kv_get(self, k, d=None):
        return self._kv.get(k, d)

    def kv_set(self, k, v):
        self._kv[k] = v


def evenements():
    out = []
    for l in open(config.DATA_DIR / "affect-evenements.jsonl", encoding="utf-8"):
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if DEBUT <= float(e.get("ts", 0)) <= FIN and e.get("nom"):
            out.append((float(e["ts"]), str(e["nom"]), float(e.get("intensite", 1.0)), e.get("sujet")))
    return sorted(out)


def un_par_message(evs, fenetre=90):
    """V1 : chaleur_user et soutien à moins de 90 s l'un de l'autre viennent du même message : seul le plus fort compte."""
    out, sociaux = [], {"chaleur_user", "soutien"}
    for e in evs:
        if e[1] in sociaux and out and out[-1][1] in sociaux and e[0] - out[-1][0] <= fenetre:
            if e[2] > out[-1][2]:
                out[-1] = e
            continue
        out.append(e)
    return out


def rejouer(evs):
    m, k, serie = _Mem(), 0, []
    t = DEBUT
    affect.get_state(m, now=t)
    while t <= FIN:
        while k < len(evs) and evs[k][0] <= t:
            affect.event(m, evs[k][1], evs[k][2], now=evs[k][0], sujet=evs[k][3])
            k += 1
        serie.append((t, affect.get_state(m, now=t)))
        t += PAS
    return serie


def humeurs(serie):
    bases = {h: statistics.fmean(s[h] for _t, s in serie) for h in serie[0][1]}
    bases["adenosine"] = sensations.ADENOSINE_BASE
    out, avant = [], None
    for i, (t, s) in enumerate(serie):
        etat = {**s, "adenosine": sensations.ADENOSINE_BASE}
        passe = {**serie[max(0, i - 10)][1], "adenosine": sensations.ADENOSINE_BASE}
        sens = sensations.calculer(etat, passe, t, None, time.localtime(t).tm_hour, sans_coherence=True, bases_relatives=bases)
        avant = interieur.humeur_hormonale(sens, avant)
        out.append(avant)
    return out


def mesurer(evs, serie):
    idx = {t: i for i, (t, _s) in enumerate(serie)}
    pas_de = lambda t: idx.get(DEBUT + PAS * int((t - DEBUT) // PAS))                       # noqa: E731
    m1 = 100 * sum(s["ocytocine"] > 0.9 or s["serotonine"] > 0.9 for _t, s in serie) / len(serie)
    m2 = 100 * sum(s["dopamine"] >= 0.85 or s["ocytocine"] >= 0.85 for _t, s in serie) / len(serie)
    stress = lambda s: s["noradrenaline"] + s["adrenaline"] + s["crh"]                      # noqa: E731
    hausses, soutiens = [], []
    emo = humeurs(serie)
    apres_neg = []
    for t, nom, _i, _s in evs:
        i = pas_de(t)
        if i is None or i == 0:
            continue
        if nom in NEGATIFS:
            fin = min(len(serie), i + 31)
            hausses.append(max(stress(serie[j][1]) for j in range(i, fin)) - stress(serie[i - 1][1]))
            apres_neg.extend(emo[i:fin])
        if nom == "soutien" and i + 2 < len(serie):
            soutiens.append(serie[i + 2][1]["ocytocine"] - serie[i - 1][1]["ocytocine"])
    repartition = {}
    for e in emo:
        repartition[e] = repartition.get(e, 0) + 1
    return {"M1_ocyto_ou_sero_sup_0_9_%": round(m1, 1), "M2_dopa_ou_ocyto_085_%": round(m2, 1),
            "M3_hausse_stress_apres_negatif": round(statistics.fmean(hausses), 4) if hausses else None,
            "M4_alerte_ou_bas_apres_negatif_%": round(100 * sum(e in ALERTE_BAS for e in apres_neg) / len(apres_neg), 1) if apres_neg else None,
            "M5_hausse_ocytocine_soutien": round(statistics.median(soutiens), 4) if soutiens else None,
            "negatifs": len(hausses), "soutiens": len(soutiens),
            "humeurs_%": {k: round(100 * v / len(emo), 1) for k, v in sorted(repartition.items(), key=lambda x: -x[1])[:12]}}


def variante(nom, evs):
    import copy
    sauve = (dict(affect.HORMONES), affect.GABA_FREIN, set(affect.HAB_EXEMPTS), copy.deepcopy(affect.EVENTS), copy.deepcopy(affect.EVENTS_V2))
    try:
        if nom in ("V2", "V3", "V4", "V5", "V6"):
            affect.HORMONES["ocytocine"] = (affect.HORMONES["ocytocine"][0], 3.0)
            affect.HORMONES["serotonine"] = (affect.HORMONES["serotonine"][0], 8.0)
        if nom in ("V4", "V5", "V6"):
            affect.GABA_FREIN = 0.35
        if nom in ("V5", "V6"):
            affect.HAB_EXEMPTS |= NEGATIFS
        if nom == "V6":
            for ev in ("probleme", "echec"):
                for table in (affect.EVENTS, affect.EVENTS_V2):
                    for h in ("noradrenaline", "adrenaline", "crh", "cortisol"):
                        if h in table.get(ev, {}):
                            table[ev][h] *= 1.5
        e = un_par_message(evs) if nom in ("V1", "V3", "V4", "V5", "V6") else evs
        return mesurer(e, rejouer(e))
    finally:
        affect.HORMONES.clear(); affect.HORMONES.update(sauve[0]); affect.GABA_FREIN = sauve[1]
        affect.HAB_EXEMPTS.clear(); affect.HAB_EXEMPTS.update(sauve[2])
        affect.EVENTS.clear(); affect.EVENTS.update(sauve[3]); affect.EVENTS_V2.clear(); affect.EVENTS_V2.update(sauve[4])


def second_tour():
    evs = evenements()
    res = {v: variante(v, evs) for v in ("V0", "V5", "V6")}
    v0 = res["V0"]
    tient = {v: {"M1": res[v]["M1_ocyto_ou_sero_sup_0_9_%"] <= 30,
                 "M3": (res[v]["M3_hausse_stress_apres_negatif"] or 0) >= 1.2 * (v0["M3_hausse_stress_apres_negatif"] or 0),
                 "M4": (res[v]["M4_alerte_ou_bas_apres_negatif_%"] or 0) >= 1.5 * (v0["M4_alerte_ou_bas_apres_negatif_%"] or 0),
                 "M5": (res[v]["M5_hausse_ocytocine_soutien"] or 0) >= (v0["M5_hausse_ocytocine_soutien"] or 0)} for v in ("V5", "V6")}
    retenue = next((v for v in ("V5", "V6") if all(tient[v].values())), None)
    for v in res:
        print(v, json.dumps(res[v], ensure_ascii=False), flush=True)
    sortie = Path(__file__).resolve().parents[1] / "data" / f"plafond-tour2-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps({"variantes": res, "criteres": tient, "retenue": retenue}, ensure_ascii=False, indent=1))
    print(json.dumps({"criteres": tient, "retenue": retenue}, ensure_ascii=False, indent=1))


def main():
    evs = evenements()
    res = {"fenetre": [time.strftime("%d/%m %H:%M", time.localtime(DEBUT)), time.strftime("%d/%m %H:%M", time.localtime(FIN))],
           "evenements": len(evs), "variantes": {}}
    for v in ("V0", "V1", "V2", "V3", "V4"):
        res["variantes"][v] = variante(v, evs)
        print(v, json.dumps(res["variantes"][v], ensure_ascii=False), flush=True)
    v0 = res["variantes"]["V0"]
    tient = {}
    for v in ("V1", "V2", "V3", "V4"):
        x = res["variantes"][v]
        tient[v] = {"M1": x["M1_ocyto_ou_sero_sup_0_9_%"] <= 30,
                    "M3": (x["M3_hausse_stress_apres_negatif"] or 0) >= (v0["M3_hausse_stress_apres_negatif"] or 0),
                    "M4": (x["M4_alerte_ou_bas_apres_negatif_%"] or 0) >= 2 * (v0["M4_alerte_ou_bas_apres_negatif_%"] or 0),
                    "M5": (x["M5_hausse_ocytocine_soutien"] or 0) >= 0.03}
    res["criteres"] = tient
    res["retenue"] = next((v for v in ("V1", "V2", "V3", "V4") if all(tient[v].values())), None)
    sortie = Path(__file__).resolve().parents[1] / "data" / f"plafond-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps({"criteres": tient, "retenue": res["retenue"]}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    second_tour() if sys.argv[1:] == ["tour2"] else main()
