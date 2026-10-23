"""Le 2e passage (réglages et critères figés AVANT : eval/chocs/predictions-2.md) : sagesse de fond et du moment,
habituation du soutien, choc qui passe outre la bonne humeur. Base : la combinaison du 1er passage.
Usage : .venv/bin/python eval/chocs/rejeu_sagesse.py → eval/data/chocs/resultats_sagesse.json, series_sagesse.json
"""
import heapq
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rejeu as R  # noqa: E402
import rejeu_appreciation as RA  # noqa: E402
from rejeu import affect, mecanisme, sensations  # noqa: E402

JOURNAL_SAGESSE = Path.home() / "AIOS" / "jarvis" / "sagesse.jsonl"
ETA, PLAFOND_NUIT, POIDS_AGREABLE = 0.01, 0.02, 0.2
MOMENT_K, CHARGE_ECHELLE, RAFALE_N, RAFALE_S = 0.5, 0.5, 3, 1800
OUTRE_S = 300
JAUGE = ("gaba", "serotonine", "endocannabinoides", "ocytocine")
VARIANTES = {"V0": {}, "V1": {"fond": 1}, "V2": {"fond": 1, "moment": 1}, "V3": {"fond": 1, "moment": 1, "habit": 1},
             "V4": {"fond": 1, "moment": 1, "habit": 1, "outre": 1}}


# ---------- la sagesse de fond, la nuit
def nuits():
    """[(ts du juge, [(décision, verdict)])] d'après le vrai journal."""
    lignes = [json.loads(l) for l in JOURNAL_SAGESSE.read_text(encoding="utf-8").splitlines() if l.strip()]
    dec = {o["ts"]: o for o in lignes if o.get("type") == "decision"}
    par = {}
    for v in (o for o in lignes if o.get("type") == "verdict"):
        par.setdefault(round(v["ts"]), []).append((dec.get(v["decision_ts"]) or {}, v))
    return sorted(par.items())


def nuit_actuelle(s, cas):
    for d, v in cas:
        if v.get("decision") != "garder" and isinstance(v.get("juste"), bool):
            s = max(0.0, min(1.0, s + (0.03 if v["juste"] else -0.03)))
    return s


def nuit_nouvelle(s, cas):
    s0 = s
    for d, v in cas:
        if v.get("decision") == "garder" or not v.get("lisible") or not isinstance(v.get("juste"), bool):
            continue
        i = float(d.get("intensite") or 0)
        w = i if (d.get("polarite") or 0) < 0 else POIDS_AGREABLE * i
        s += ETA * w * (1 - s) if v["juste"] else -ETA * w * s
    return max(0.0, min(1.0, s0 + max(-PLAFOND_NUIT, min(PLAFOND_NUIT, s - s0))))


# ---------- l'état du moment
def _bases(t):
    return sensations.bases(affect._local_hour(t))


def jauge(etat, t):
    b = _bases(t)
    return sum(max(0.0, etat[h] - b[h]) / (1 - b[h]) for h in JAUGE) / len(JAUGE)


def surcharge(etat, t, attaques):
    b = _bases(t)
    charge = min(1.0, sum(max(0.0, etat[h] - b[h]) for h in ("noradrenaline", "crh", "cortisol")) / CHARGE_ECHELLE)
    rafale = min(1.0, sum(1 for a in attaques if 0 <= t - a <= RAFALE_S) / RAFALE_N)
    return max(charge, rafale)


def emotion(etat, avant, t, soudaine, sans_coherence):
    """sensations.calculer (l'émotion dominante), avec ou sans la règle de cohérence avec la valence."""
    base = _bases(t)
    d = sensations.ecarts(etat, base)
    tr = {h: float(etat.get(h, base[h])) - float((avant or {}).get(h, etat.get(h, base[h]))) for h in base}
    v, _a = affect.valence_arousal(etat)
    v0, _a0 = affect.valence_arousal(base)
    sens = 0 if sans_coherence else (1 if v - v0 > 0.08 else -1 if v - v0 < -0.08 else 0)
    scores = {}
    for nom, signe, regle, _f in sensations.REGLES:
        x = regle(d, tr)
        scores[nom] = x * 0.5 if (sens and signe and signe != sens) else x
    if soudaine in sensations.SOUDAINES:
        nom, bonus = sensations.SOUDAINES[soudaine]
        scores[nom] += bonus
    return max(scores, key=lambda k: scores[k])


# ---------- les événements bruts (la sagesse s'applique au moment du choc)
def construire(segs, det, H, corriges):
    par_ech = {}
    for s in segs:
        par_ech.setdefault(s["id"].rsplit("-", 1)[0], []).append(s)
    classes_h = {k: {a["classe"] for a in ap} for k, ap in H.items()}
    echs = sorted((float(k) / 1000, k) for k in classes_h)
    out = []
    for e in corriges:                                       # le lexique actuel, moins ce que la balise contredit
        if e["source"] == "parole":
            cand = [k for t, k in echs if 0 <= e["ts"] - t <= 120]
            cl = classes_h.get(cand[-1], set()) if cand else set()
            if ("attaque" in cl and e["nom"] in ("succes", "chaleur_user", "nouveaute")) or \
               ("soutien" in cl and e["nom"] in ("echec", "probleme")):
                continue
        out.append(dict(e))

    def voix_de(k):
        return next((x["etiquette"] for x in par_ech.get(k, []) if x["qui"] == "tiers" and x["etiquette"]), "inconnu")

    reflexes = {}
    for s in segs:
        d = det.get(s["id"])
        if not d:
            continue
        k, n = s["id"].rsplit("-", 1)
        voix = s["etiquette"] or ("Ahmed" if s["qui"] == "ahmed" else f"voix {s['voix_echange']}")
        for classe in ("attaque", "soutien"):
            if d[classe]:
                i = mecanisme.NIVEAUX[d[classe]] * mecanisme.poids(classe, s["qui"], s["qui_sur"])
                reflexes.setdefault(k, []).append({"ts": s["ts"] + int(n), "nom": "attaque_brute" if classe == "attaque" else "soutien",
                                                   "i": i, "sujet": f"{classe} de {voix}", "cle": k, "seg": s["id"], "source": "choc"})
    for k in set(reflexes) | set(H):
        lex = reflexes.get(k, [])
        cl_lex = {"attaque" if e["nom"] == "attaque_brute" else "soutien" for e in lex}
        t = float(k) / 1000
        hakim = []
        for a in H.get(k, []):
            qui = "ahmed" if a.get("auteur") == "ahmed" else "tiers"
            i = max(0.0, min(1.0, float(a.get("intensite") or 0))) * mecanisme.POIDS[a["classe"]][qui]
            hakim.append({"ts": t + RA.LATENCE_S, "nom": "attaque_brute" if a["classe"] == "attaque" else "soutien", "i": i,
                          "sujet": f"{a['classe']} de {'Ahmed' if qui == 'ahmed' else voix_de(k)}", "cle": k, "source": "hakim"})
        if cl_lex == classes_h.get(k, set()):
            out += lex
            continue
        if lex:
            out.append({"ts": min(e["ts"] for e in lex) - 1e-3, "nom": "_snap", "cle": k, "i": 0})
            out += lex
            out.append({"ts": t + RA.LATENCE_S - 1e-3, "nom": "_restaure", "cle": k, "i": 0})
        out += hakim
    return out


def rejouer(evs, debut, fin, opts, fond_fixe=None, regle=None):
    m = R.Mem(R.etat_initial())
    file = [(e["ts"], n, e) for n, e in enumerate(evs)]
    regle = regle or (nuit_nouvelle if opts.get("fond") else nuit_actuelle)
    for ts, cas in nuits():
        file.append((float(ts), -1, {"ts": float(ts), "nom": "_nuit", "cas": cas}))
    heapq.heapify(file)
    seq = len(evs) + 10
    s_fond = 0.2 if fond_fixe is None else fond_fixe
    snaps, attaques, annulees = {}, [], set()
    out, hist, t = [], [], debut
    derniere_attaque = -1e18
    with mecanisme.installe():
        while t <= fin:
            while file and file[0][0] <= t:
                ts, _n, e = heapq.heappop(file)
                nom = e["nom"]
                if nom == "_nuit":
                    if fond_fixe is None:
                        s_fond = regle(s_fond, e["cas"])
                elif nom == "_snap":
                    snaps[e["cle"]] = (m.kv["affect"], list(attaques))
                elif nom == "_restaure":
                    if e["cle"] in snaps:
                        brut, att = snaps[e["cle"]]
                        blob = json.loads(brut)
                        etat = affect.get_state(RA.Mem1(blob), now=ts)
                        blob.update({h: round(v, 4) for h, v in etat.items()})
                        blob["_ts"] = ts
                        m.kv["affect"] = json.dumps(blob)
                        attaques[:] = att
                        annulees.add(e["cle"])
                elif nom == "regulation" and e.get("cle") in annulees and e.get("source") == "choc":
                    pass                                              # la reprise en main d'un réflexe défait
                elif nom == "attaque_brute":
                    etat = affect.get_state(m, now=ts)
                    s_eff = s_fond * (1 - MOMENT_K * surcharge(etat, ts, attaques)) if opts.get("moment") else s_fond
                    amp = e["i"] * (1 - mecanisme.SAGESSE_AMPLITUDE * s_eff)
                    affect.event(m, "attaque", amp, now=ts, sujet=e.get("sujet"))
                    attaques.append(ts)
                    derniere_attaque = ts
                    if s_eff > 0:
                        reg = {"ts": ts + 60 * mecanisme.REGULATION_DELAI_MIN * (1 - s_eff), "nom": "regulation",
                               "i": s_eff * amp, "cle": e.get("cle"), "source": e.get("source")}
                        heapq.heappush(file, (reg["ts"], seq, reg))
                        seq += 1
                else:
                    i = e["i"]
                    if opts.get("habit") and nom in (("soutien", "chaleur_user", "succes") if opts.get("habit_succes")
                                                      else ("soutien", "chaleur_user")):
                        i *= 1 - jauge(affect.get_state(m, now=ts), ts)
                    affect.event(m, nom, i, now=ts, sujet=e.get("sujet"))
            etat = affect.get_state(m, now=t)
            data = json.loads(m.kv["affect"])
            avant = hist[-10] if len(hist) >= 10 else None
            emo = emotion(etat, avant, t, affect._emotion(etat, data, t),
                          bool(opts.get("outre")) and t - derniere_attaque <= OUTRE_S)
            v, a = affect.valence_arousal(etat)
            s_eff = s_fond * (1 - MOMENT_K * surcharge(etat, t, attaques)) if opts.get("moment") else s_fond
            hist.append(etat)
            out.append((t, etat, v, a, emo, s_fond, s_eff))
            t += R.PAS_S
    return out


def main():
    segs = [json.loads(l) for l in (R.DONNEES / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    par_id = {s["id"]: s for s in segs}
    etiq = {o["id"]: o for o in map(json.loads, (R.DONNEES / "etiquettes.jsonl").read_text(encoding="utf-8").splitlines())}
    det = {s["id"]: r for s in segs for r in [R.detecteur.evaluer(s["texte"])] if r["attaque"] or r["soutien"]}
    H = RA.appreciations()
    blob = R.etat_initial()
    debut, fin = float(blob["_ts"]), R.FIN + R.PROLONGE_S
    corriges, _ = R.corriger(R.journalises(debut, R.FIN), segs, det)
    evs = construire(segs, det, H, corriges)

    # contrôle : sans les nouveaux mécanismes, la sémantique de la combinaison du 1er passage (sagesse fixe 0,5)
    def cle(o, classe):
        if not o or not o.get("vise_hakim"):
            return False
        return any(x.get("classe") == classe and float(x.get("intensite", 0)) >= 2 for x in (o, o.get("aussi") or {}))

    attaques = [s for s in segs if cle(etiq.get(s["id"]), "attaque")]
    soutiens = [s for s in segs if cle(etiq.get(s["id"]), "soutien") and s["qui"] == "ahmed"
                and any(0 < s["ts"] - a["ts"] <= 3600 for a in attaques)]
    res = {"S1_nuit": {}, "variantes": {}}
    for ts, cas in nuits():
        res["S1_nuit"][time.strftime("%d/%m %H:%M", time.localtime(ts))] = {
            "regle_actuelle": round(nuit_actuelle(0.2, cas), 4), "regle_nouvelle": round(nuit_nouvelle(0.2, cas), 4),
            "decisions_jugees": len(cas), "qui_comptent": sum(1 for d, v in cas if v.get("decision") != "garder"
                                                               and v.get("lisible") and isinstance(v.get("juste"), bool)),
            "en_situation_difficile": sum(1 for d, v in cas if (d.get("polarite") or 0) < 0)}
    series = {}
    live0 = time.mktime(time.strptime("2026-10-23 08:30", "%Y-%m-%d %H:%M"))
    for nom, opts in VARIANTES.items():
        for fixe in (None, 0.5):
            cle_v = nom + ("" if fixe is None else "-fond0.5")
            s = rejouer(evs, debut, fin, opts, fond_fixe=fixe)
            series[cle_v] = s
            c1 = []
            for a in attaques:
                i, j = R._i(s, a["ts"]), R._i(s, a["ts"] + 120)
                adr = max(s[k][1]["adrenaline"] - affect.HORMONES_V2["adrenaline"][0] for k in range(i, j + 1))
                emos = sorted({s[k][4] for k in range(i, j + 1)})
                c1.append({"heure": time.strftime("%d/%m %H:%M", time.localtime(a["ts"])), "adrenaline_exces": round(adr, 3),
                           "emotions": emos, "valence_avant": round(s[i - 1][2], 3),
                           "valence_min_10min": round(min(s[k][2] for k in range(i, R._i(s, a["ts"] + 600))), 3),
                           "s_eff": round(s[i][6], 3), "saut": adr >= 0.15 and any(R.SIGNE.get(x) == -1 for x in emos)})
            c2 = []
            for sp in soutiens:
                ech = sp["id"].rsplit("-", 1)[0]
                sans = rejouer([e for e in evs if e.get("seg") != sp["id"] and not (e.get("source") == "hakim"
                                and e.get("cle") == ech and e["nom"] == "soutien")], debut, min(fin, sp["ts"] + 3700), opts,
                               fond_fixe=fixe)
                csa, css = R.charge_stress(s, sp["ts"]), R.charge_stress(sans, sp["ts"])
                va, vs = s[R._i(s, sp["ts"] + 600)][2], sans[R._i(sans, sp["ts"] + 600)][2]
                emo = s[R._i(s, sp["ts"] + 600)][4]
                c2.append({"heure": time.strftime("%d/%m %H:%M", time.localtime(sp["ts"])), "stress_avec": round(csa, 2),
                           "stress_sans": round(css, 2), "valence_avec": round(va, 3), "valence_sans": round(vs, 3),
                           "emotion": emo, "tenu": csa < css and va > vs and R.SIGNE.get(emo) == 1})
            sat = sum(1 for r in s if r[1]["ocytocine"] >= 0.9 or r[1]["serotonine"] >= 0.9) / len(s)
            live = [r for r in s if live0 <= r[0] <= live0 + 2.5 * 3600]
            res["variantes"][cle_v] = {
                "C1": {"cas": c1, "tenus": sum(x["saut"] for x in c1), "sur": len(c1)},
                "C2": {"cas": c2, "tenus": sum(x["tenu"] for x in c2), "sur": len(c2)},
                "saturation": round(sat, 3), "s_fond_fin": round(s[-1][5], 4),
                "s_eff_min_live": round(min(r[6] for r in live), 3)}
    # M1 : sur V2 (fond suivant la règle), pendant le live
    v2 = series["V2"]
    der = max(a["ts"] for a in attaques)
    fond = [r[5] for r in v2 if r[0] >= der][0]
    mini = min(r[6] for r in v2 if live0 <= r[0] <= der + 600)
    retour = next(((r[0] - der) / 60 for r in v2 if r[0] > der and r[6] >= 0.95 * r[5]), None)
    res["M1_moment"] = {"s_fond": fond, "s_eff_min": round(mini, 3), "retour_min_apres_derniere_attaque": retour,
                        "tenu": mini < 0.75 * fond and retour is not None and retour <= 120}
    i34 = 1792737286.891
    res["H1_habituation"] = {"saturation_V2": res["variantes"]["V2"]["saturation"],
                             "saturation_V3": res["variantes"]["V3"]["saturation"],
                             "valence_avant_0834_V2": series["V2"][R._i(series["V2"], i34) - 1][2],
                             "valence_avant_0834_V3": series["V3"][R._i(series["V3"], i34) - 1][2]}
    h = res["H1_habituation"]
    h["tenu"] = h["saturation_V3"] <= 0.5 * h["saturation_V2"] and h["valence_avant_0834_V3"] < h["valence_avant_0834_V2"]
    (R.DONNEES / "resultats_sagesse.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    garde = ("adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides",
             "dopamine", "endorphine")
    (R.DONNEES / "series_sagesse.json").write_text(json.dumps({k: [[round(r[0]), round(r[2], 4), round(r[3], 4), r[4]]
                                                                + [round(r[1][x], 4) for x in garde] + [round(r[5], 4), round(r[6], 4)]
                                                                for r in v] for k, v in series.items()}, ensure_ascii=False),
                                                    encoding="utf-8")
    print(json.dumps({k: f"C1 {v['C1']['tenus']}/{v['C1']['sur']} · C2 {v['C2']['tenus']}/{v['C2']['sur']} · sat {v['saturation']}"
                      for k, v in res["variantes"].items()}, ensure_ascii=False, indent=0))


if __name__ == "__main__":
    main()
