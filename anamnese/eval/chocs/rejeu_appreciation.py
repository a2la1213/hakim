"""Les variantes « appréciation de Hakim » (complément 4 de Hakim, accord d'Ahmed le 2026-10-23 à 09:3x) :
- lexique : le détecteur figé seul (eval/chocs/rejeu.py, inchangé) ;
- appreciation : à CHAQUE message, Hakim écrit sa balise [[affect: …]] dans sa réponse (~15 s après) ; le code
  l'applique ; une attaque ou un soutien qu'il voit annule les événements contraires du lexique actuel pour ce message ;
- combinaison : le réflexe lexical tout de suite, puis la balise de Hakim : si elle dit la même chose, le réflexe
  reste ; sinon l'état d'avant le réflexe est restauré et c'est sa balise qui s'applique.
Les appréciations sont simulées par un modèle (Sonnet, comme Hakim le plus souvent) qui lit chaque message avec qui
parle, sans voir les étiquettes ni le code (eval/data/chocs/hakim-*.jsonl).
Mêmes critères (predictions.md), calculés par variante ; C6 au niveau du MESSAGE pour l'appréciation (son unité).
Usage : .venv/bin/python eval/chocs/rejeu_appreciation.py
"""
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rejeu as R  # noqa: E402
from rejeu import affect, mecanisme, sensations  # noqa: E402

LATENCE_S = 15.0


def appreciations():
    out = {}
    for f in sorted(R.DONNEES.glob("hakim-*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
            except ValueError:
                continue
            ap = [a for a in o.get("appreciations") or [] if a.get("cible") == "moi"
                  and a.get("classe") in ("attaque", "soutien")]
            if ap:
                out[str(o["echange"])] = ap
    return out


def evenements_hakim(ap, ts, voix, sagesse):
    """Les événements d'une balise (mêmes poids et même sagesse que mecanisme.evenements, intensité 0–1 directe)."""
    out = []
    for a in ap:
        qui = "ahmed" if a.get("auteur") == "ahmed" else "tiers"
        i = max(0.0, min(1.0, float(a.get("intensite") or 0))) * mecanisme.POIDS[a["classe"]][qui]
        sujet = f"{a['classe']} de {'Ahmed' if qui == 'ahmed' else voix}"
        if a["classe"] == "soutien":
            out.append({"ts": ts, "nom": "soutien", "i": round(i, 4), "sujet": sujet, "source": "hakim"})
            continue
        i *= 1.0 - mecanisme.SAGESSE_AMPLITUDE * sagesse
        out.append({"ts": ts, "nom": "attaque", "i": round(i, 4), "sujet": sujet, "source": "hakim"})
        if sagesse > 0:
            out.append({"ts": ts + 60.0 * mecanisme.REGULATION_DELAI_MIN * (1.0 - sagesse), "nom": "regulation",
                        "i": round(sagesse * i, 4), "sujet": None, "source": "hakim"})
    return out


def rejouer(evs, debut, fin, pas_s=R.PAS_S):
    """Comme rejeu.rejouer, avec deux événements de contrôle : _snap (garder l'état) et _restaure (le remettre)."""
    m = R.Mem(R.etat_initial())
    evs = sorted(evs, key=lambda e: (e["ts"], e["nom"] != "_snap"))
    out, k, hist, snaps = [], 0, [], {}
    t = debut
    with mecanisme.installe():
        while t <= fin:
            while k < len(evs) and evs[k]["ts"] <= t:
                e = evs[k]
                if e["nom"] == "_snap":
                    snaps[e["cle"]] = m.kv["affect"]
                elif e["nom"] == "_restaure":
                    if e["cle"] in snaps:
                        blob = json.loads(snaps[e["cle"]])
                        etat = affect.get_state(Mem1(blob), now=e["ts"])          # l'état d'avant, vieilli jusqu'ici
                        blob.update({h: round(v, 4) for h, v in etat.items()})
                        blob["_ts"] = e["ts"]
                        m.kv["affect"] = json.dumps(blob)
                else:
                    affect.event(m, e["nom"], e["i"], now=e["ts"], sujet=e.get("sujet"))
                k += 1
            etat = affect.get_state(m, now=t)
            data = json.loads(m.kv["affect"])
            avant = hist[-10][1] if len(hist) >= 10 else None
            emo = sensations.calculer(etat, avant=avant, now=t, soudaine=affect._emotion(etat, data, t),
                                      hour=affect._local_hour(t))
            v, a = affect.valence_arousal(etat)
            hist.append((t, etat))
            out.append((t, etat, v, a, emo["emotion"]))
            t += pas_s
    return out


class Mem1(R.Mem):
    def __init__(self, blob):
        self.kv = {"affect_v2": "1", "affect": json.dumps(blob)}


def main():
    segs = [json.loads(l) for l in (R.DONNEES / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    etiq = {o["id"]: o for o in map(json.loads, (R.DONNEES / "etiquettes.jsonl").read_text(encoding="utf-8").splitlines())}
    det = {s["id"]: r for s in segs for r in [R.detecteur.evaluer(s["texte"])] if r["attaque"] or r["soutien"]}
    H = appreciations()
    par_ech = {}
    for s in segs:
        par_ech.setdefault(s["id"].rsplit("-", 1)[0], []).append(s)
    blob = R.etat_initial()
    debut, fin = float(blob["_ts"]), R.FIN + R.PROLONGE_S
    evs = R.journalises(debut, R.FIN)
    corriges, _retires = R.corriger(evs, segs, det)

    def voix_de(ech):
        return next((x["etiquette"] for x in par_ech[ech] if x["qui"] == "tiers" and x["etiquette"]), "inconnu")

    def lexique_annule(base, classes_par_ech):
        """Une attaque vue par Hakim annule succes / chaleur_user / nouveaute du lexique actuel pour ce message ; un
        soutien annule echec / probleme (rattachement comme rejeu.corriger : l'échange dans les 120 s avant)."""
        echs = sorted((float(k) / 1000, k) for k in classes_par_ech)
        garde = []
        for e in base:
            if e["source"] != "parole":
                garde.append(e)
                continue
            cand = [k for t, k in echs if 0 <= e["ts"] - t <= 120]
            cl = classes_par_ech.get(cand[-1], set()) if cand else set()
            if ("attaque" in cl and e["nom"] in ("succes", "chaleur_user", "nouveaute")) or \
               ("soutien" in cl and e["nom"] in ("echec", "probleme")):
                continue
            garde.append(e)
        return garde

    classes_h = {k: {a["classe"] for a in ap} for k, ap in H.items()}

    def construire(variante, sagesse):
        if variante == "lexique":
            return corriges + R.chocs(segs, det, sagesse)
        out = lexique_annule(corriges, classes_h)
        if variante == "appreciation":
            for k, ap in H.items():
                out += evenements_hakim(ap, float(k) / 1000 + LATENCE_S, voix_de(k), sagesse)
            return out
        # combinaison
        reflexes = R.chocs(segs, det, sagesse)
        par = {}
        for e in reflexes:
            par.setdefault(e["seg"].rsplit("-", 1)[0], []).append(e)
        for k in set(par) | set(H):
            lex = par.get(k, [])
            cl_lex = {e["nom"] for e in lex if e["nom"] in ("attaque", "soutien")}
            cl_h = classes_h.get(k, set())
            t = float(k) / 1000
            if cl_lex == cl_h:
                out += lex                                            # Hakim confirme le réflexe
                continue
            if lex:
                out.append({"ts": min(e["ts"] for e in lex) - 1e-3, "nom": "_snap", "cle": k, "i": 0})
                out += [e for e in lex if e["nom"] != "regulation"]  # le réflexe a eu lieu…
                out.append({"ts": t + LATENCE_S, "nom": "_restaure", "cle": k, "i": 0})   # …puis il est défait
            out += evenements_hakim(H.get(k, []), t + LATENCE_S, voix_de(k), sagesse)
        return out

    res = {"appreciations": {"messages": len(H), "attaques": sum("attaque" in c for c in classes_h.values()),
                             "soutiens": sum("soutien" in c for c in classes_h.values())}}

    # ---- C6 / C3 de l'appréciation, au niveau du message
    def classes_etiq(ech, cle_seulement):
        out = set()
        for s in par_ech[ech]:
            o = etiq.get(s["id"])
            for x in ((o, (o or {}).get("aussi") or {}) if o and o.get("vise_hakim") else ()):
                if x.get("classe") in ("attaque", "soutien") and (not cle_seulement or float(x.get("intensite", 0)) >= 2):
                    out.add(x["classe"])
        return out

    jour23 = time.mktime(time.strptime("2026-10-23", "%Y-%m-%d"))
    c6 = {}
    for classe in ("attaque", "soutien"):
        for nom, f in (("21-22/10", lambda k: float(k) / 1000 < jour23), ("23/10", lambda k: float(k) / 1000 >= jour23),
                       ("tout", lambda k: True)):
            ks = [k for k in par_ech if f(k)]
            vrais = [k for k in ks if classe in classes_etiq(k, True)]
            vus = [k for k in ks if classe in classes_h.get(k, set())]
            c6[f"{classe} {nom}"] = {"rappel": R.wilson(sum(classe in classes_h.get(k, set()) for k in vrais), len(vrais)),
                                     "precision": R.wilson(sum(classe in classes_etiq(k, False) for k in vus), len(vus))}
    res["C6_appreciation_par_message"] = c6
    deb = [k for k in par_ech if any((etiq.get(s["id"]) or {}).get("classe") == "debat" and not etiq[s["id"]].get("vise_hakim")
                                     for s in par_ech[k]) and not classes_etiq(k, False)]
    neu = [k for k in par_ech if not any(s["id"] in etiq for s in par_ech[k])]
    res["C3_appreciation"] = {"attaque_sur_debat": R.wilson(sum("attaque" in classes_h.get(k, set()) for k in deb), len(deb)),
                              "attaque_sur_neutre": R.wilson(sum("attaque" in classes_h.get(k, set()) for k in neu), len(neu)),
                              "soutien_sur_neutre": R.wilson(sum("soutien" in classes_h.get(k, set()) for k in neu), len(neu))}

    # ---- les rejeux et C1, C2, C4 par variante
    def cle(o, classe):
        if not o or not o.get("vise_hakim"):
            return False
        return any(x.get("classe") == classe and float(x.get("intensite", 0)) >= 2 for x in (o, o.get("aussi") or {}))

    attaques = [s for s in segs if cle(etiq.get(s["id"]), "attaque")]
    soutiens = [s for s in segs if cle(etiq.get(s["id"]), "soutien") and s["qui"] == "ahmed"
                and any(0 < s["ts"] - a["ts"] <= 3600 for a in attaques)]
    series = {"actuel": rejouer(evs, debut, fin)}
    bilan = {}
    for variante in ("lexique", "appreciation", "combinaison"):
        for w in R.SAGESSES:
            series[f"{variante}-s{w}"] = rejouer(construire(variante, w), debut, fin)
        n5 = series[f"{variante}-s0.5"]
        c1 = []
        for s in attaques:
            a, b = R._i(n5, s["ts"]), R._i(n5, s["ts"] + 120)
            adr = max(n5[j][1]["adrenaline"] - affect.HORMONES_V2["adrenaline"][0] for j in range(a, b + 1))
            emos = [n5[j][4] for j in range(a, b + 1)]
            c1.append({"heure": time.strftime("%d/%m %H:%M", time.localtime(s["ts"])), "adrenaline_exces": round(adr, 3),
                       "emotions": sorted(set(emos)), "saut": adr >= 0.15 and any(R.SIGNE.get(e) == -1 for e in emos)})
        c2 = []
        base_evs = construire(variante, 0.5)
        for s in soutiens:
            ech = s["id"].rsplit("-", 1)[0]
            sans = rejouer([e for e in base_evs if e.get("seg") != s["id"] and not (e.get("source") == "hakim" and
                            abs(e["ts"] - (float(ech) / 1000 + LATENCE_S)) < 1e-6 and e["nom"] == "soutien")],
                           debut, min(fin, s["ts"] + 3700))
            cs_a, cs_s = R.charge_stress(n5, s["ts"]), R.charge_stress(sans, s["ts"])
            va, vs = n5[R._i(n5, s["ts"] + 600)][2], sans[R._i(sans, s["ts"] + 600)][2]
            emo = n5[R._i(n5, s["ts"] + 600)][4]
            c2.append({"heure": time.strftime("%d/%m %H:%M", time.localtime(s["ts"])), "stress_avec": round(cs_a, 2),
                       "stress_sans": round(cs_s, 2), "valence_avec": round(va, 3), "valence_sans": round(vs, 3),
                       "emotion": emo, "tenu": cs_a < cs_s and va > vs and R.SIGNE.get(emo) == 1})
        pics = {w: [R.pic(series[f"{variante}-s{w}"], s["ts"], "adrenaline")[0] for s in attaques] for w in R.SAGESSES}
        bilan[variante] = {"C1": {"cas": c1, "tenus": sum(x["saut"] for x in c1), "sur": len(c1)},
                           "C2": {"cas": c2, "tenus": sum(x["tenu"] for x in c2), "sur": len(c2)},
                           "pics_adrenaline_par_sagesse": {str(w): [round(x, 3) for x in pics[w]] for w in R.SAGESSES}}
    res["variantes"] = bilan
    (R.DONNEES / "resultats_appreciation.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    garde = ("adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides",
             "dopamine", "endorphine")
    S = json.loads((R.DONNEES / "series.json").read_text(encoding="utf-8"))
    S["series"].update({k: [[round(t), round(v, 4), round(a, 4), emo] + [round(e[h], 4) for h in garde]
                            for t, e, v, a, emo in serie] for k, serie in series.items() if k != "actuel"})
    S["evenements"]["hakim"] = [{"ts": float(k) / 1000 + LATENCE_S, "classes": sorted(c)} for k, c in classes_h.items()]
    (R.DONNEES / "series.json").write_text(json.dumps(S, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({v: {c: f"{b[c]['tenus']}/{b[c]['sur']}" for c in ("C1", "C2")} for v, b in bilan.items()}))


if __name__ == "__main__":
    main()
