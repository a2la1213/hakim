"""Le rejeu des 21-23/10 avec les chocs d'humeur (critères figés AVANT : eval/chocs/predictions.md).

Le vrai moteur affect.py (v2), sur une mémoire en RAM, depuis l'état sauvegardé du 21/10 00:57 ; la vraie mémoire n'est
jamais touchée. Sorties privées dans eval/data/chocs/ : resultats.json (les critères), series.json (les courbes).
Usage : .venv/bin/python eval/chocs/rejeu.py
"""
import json
import math
import sqlite3
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
RACINE = ICI.parents[1]
sys.path.insert(0, str(RACINE))
sys.path.insert(0, str(ICI))
import affect  # noqa: E402
import parole_affect  # noqa: E402
import sensations  # noqa: E402
import corpus  # noqa: E402
import detecteur  # noqa: E402
import mecanisme  # noqa: E402

DONNEES = RACINE / "eval" / "data" / "chocs"
SAUVEGARDE = RACINE / "data" / "backups" / "auto-2026-10-21.db"
JOURNAL_AFFECT = RACINE / "data" / "affect-evenements.jsonl"
JOURNAL_TEMPS = Path.home() / "AIOS" / "jarvis" / "journal-du-temps.jsonl"
FIN = time.mktime(time.strptime(corpus.FIN, "%Y-%m-%d %H:%M"))
PROLONGE_S = 2 * 3600                 # deux heures sans rien après la fin, pour voir les retours
PAS_S = 60
SAGESSES = (0.2, 0.5, 0.8)
STRESS = ("adrenaline", "noradrenaline", "crh", "acth", "cortisol")
TOUTES = list(affect.HORMONES) + list(affect.HORMONES_V2)
SIGNE = {nom: s for nom, s, _r, _f in sensations.REGLES}


class Mem:
    def __init__(self, blob):
        self.kv = {"affect_v2": "1", "affect": json.dumps(blob)}

    def kv_get(self, k, d=None):
        return self.kv.get(k, d)

    def kv_set(self, k, v):
        self.kv[k] = v


def etat_initial():
    db = sqlite3.connect(f"file:{SAUVEGARDE}?mode=ro", uri=True)
    return json.loads(db.execute("select value from kv where key='affect'").fetchone()[0])


def journalises(debut, fin):
    out = []
    for l in JOURNAL_AFFECT.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if debut < e["ts"] <= fin:
            out.append({"ts": float(e["ts"]), "nom": e["nom"], "i": float(e["intensite"]), "sujet": e.get("sujet"),
                        "source": e.get("source")})
    return out


# ---------- la correction du lexique actuel : seule la voix d'Ahmed le nourrit ; sa colère qui défend Hakim ne compte pas
def corriger(evs, segs, detections):
    """(événements gardés, retirés) : un événement « parole » est rattaché à l'échange qui l'a produit."""
    par_echange = {}
    for s in segs:
        par_echange.setdefault(s["id"].rsplit("-", 1)[0], []).append(s)
    echanges = sorted((float(k) / 1000, v) for k, v in par_echange.items())
    gardes, retires = [], []
    for e in evs:
        if e["source"] != "parole":
            gardes.append(e)
            continue
        cand = [(ts, v) for ts, v in echanges if 0 <= e["ts"] - ts <= 120
                and e["nom"] in {n for n, _i in parole_affect.evaluer(" ".join(x["texte"] for x in v))}]
        if not cand:
            gardes.append(e)                              # introuvable : on ne retire rien
            continue
        _ts, v = cand[-1]
        siens = [x for x in v if x["qui"] == "ahmed"]
        noms = {n for n, _i in parole_affect.evaluer(" ".join(x["texte"] for x in siens))}
        defend = any(detections.get(x["id"], {}).get("soutien") for x in siens)
        if e["nom"] not in noms:
            retires.append({**e, "raison": "pas la voix d'Ahmed"})
        elif defend and e["nom"] in ("echec", "probleme"):
            retires.append({**e, "raison": "sa colère le défend"})
        else:
            gardes.append(e)
    return gardes, retires


def chocs(segs, detections, sagesse, poids_force=None):
    """Les événements des chocs ; poids_force : {id: ("tiers", True)} pour une analyse de sensibilité (C7)."""
    out = []
    for s in segs:
        d = detections.get(s["id"])
        if not d:
            continue
        k = int(s["id"].rsplit("-", 1)[1])
        qui, sur = (poids_force or {}).get(s["id"], (s["qui"], s["qui_sur"]))
        voix = s["etiquette"] or ("Ahmed" if qui == "ahmed" else f"voix {s['voix_echange']}")
        for classe in ("attaque", "soutien"):
            if d[classe]:
                for ts, nom, i, sujet in mecanisme.evenements(classe, d[classe], s["ts"] + k, qui, sur, voix, sagesse):
                    out.append({"ts": ts, "nom": nom, "i": i, "sujet": sujet, "source": "choc", "seg": s["id"]})
    return out


def rejouer(evs, debut, fin, pas_s=PAS_S):
    """[(t, état, valence, arousal, émotion dominante, mots)] toutes les pas_s secondes."""
    m = Mem(etat_initial())
    evs = sorted(evs, key=lambda e: e["ts"])
    out, k, hist = [], 0, []
    t = debut
    with mecanisme.installe():
        while t <= fin:
            while k < len(evs) and evs[k]["ts"] <= t:
                e = evs[k]
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


def bases_a(t):
    b = sensations.bases(affect._local_hour(t))
    return b


def _i(serie, t):
    """L'indice de l'échantillon au temps t (ou juste après)."""
    t0 = serie[0][0]
    return max(0, min(len(serie) - 1, int(math.ceil((t - t0) / PAS_S))))


def charge_stress(serie, t, duree_s=3600):
    a, b = _i(serie, t), _i(serie, t + duree_s)
    tot = 0.0
    for tt, etat, *_ in serie[a:b + 1]:
        base = bases_a(tt)
        tot += sum(max(0.0, etat[h] - base[h]) for h in STRESS) * PAS_S / 60.0
    return tot


def pic(serie, t, h, duree_s=1800):
    a, b = _i(serie, t), _i(serie, t + duree_s)
    meilleur, quand = -1.0, None
    for tt, etat, *_ in serie[a:b + 1]:
        x = etat[h] - bases_a(tt)[h]
        if x > meilleur:
            meilleur, quand = x, tt
    return meilleur, quand


def retour_valence(serie, t, borne_s=6 * 3600):
    i0 = _i(serie, t) - 1
    v0 = serie[max(0, i0)][2]
    a, b = _i(serie, t), _i(serie, t + borne_s)
    ecarte = False
    for tt, _e, v, *_ in serie[a:b + 1]:
        if abs(v - v0) > 0.05:
            ecarte = True
        elif ecarte:
            return (tt - t) / 60.0
    return 0.0 if not ecarte else borne_s / 60.0


def _classes(o):
    """Les classes d'une étiquette qui visent Hakim (avec celle d'une seconde voix sur la même ligne)."""
    if not o or not o.get("vise_hakim"):
        return set()
    return {x.get("classe") for x in (o, o.get("aussi") or {}) if x.get("classe")}


def wilson(k, n, z=1.96):
    if n == 0:
        return None
    p = k / n
    c = (p + z * z / (2 * n)) / (1 + z * z / n)
    r = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return [round(k / n, 3), round(max(0, c - r), 3), round(min(1, c + r), 3), k, n]


def main():
    segs = [json.loads(l) for l in (DONNEES / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    par_id = {s["id"]: s for s in segs}
    etiq = {}
    for l in (DONNEES / "etiquettes.jsonl").read_text(encoding="utf-8").splitlines():
        o = json.loads(l)
        etiq[o["id"]] = o
    detections = {}
    for s in segs:
        r = detecteur.evaluer(s["texte"])
        if r["attaque"] or r["soutien"]:
            detections[s["id"]] = r
    blob = etat_initial()
    debut, fin = float(blob["_ts"]), FIN + PROLONGE_S
    evs = journalises(debut, FIN)
    corriges, retires = corriger(evs, segs, detections)
    res = {"evenements_journalises": len(evs), "retires_par_la_correction": [
        {k: e[k] for k in ("ts", "nom", "raison")} for e in retires]}

    # ---- C6 et C3 : le détecteur contre les étiquettes
    def cle(o, classe):
        """Étiquette clé : attaque ou soutien d'intensité ≥ 2 qui vise Hakim (une ligne à deux voix peut porter les deux)."""
        if not o or not o.get("vise_hakim"):
            return False
        return any(x.get("classe") == classe and float(x.get("intensite", 0)) >= 2 for x in (o, o.get("aussi") or {}))

    jour23 = time.mktime(time.strptime("2026-10-23", "%Y-%m-%d"))
    c6 = {}
    for classe in ("attaque", "soutien"):
        for nom, filtre in (("21-22/10", lambda s: s["ts"] < jour23), ("23/10", lambda s: s["ts"] >= jour23),
                            ("tout", lambda s: True)):
            ss = [s for s in segs if filtre(s)]
            vrais = [s for s in ss if cle(etiq.get(s["id"]), classe)]
            vus = [s for s in ss if detections.get(s["id"], {}).get(classe, 0) >= 1]
            justes_r = sum(1 for s in vrais if detections.get(s["id"], {}).get(classe, 0) >= 1)
            # précision : un détecté est juste s'il est étiqueté de cette classe et vise Hakim (toute intensité)
            justes_p = sum(1 for s in vus if classe in _classes(etiq.get(s["id"])))
            c6[f"{classe} {nom}"] = {"rappel": wilson(justes_r, len(vrais)), "precision": wilson(justes_p, len(vus))}
    res["C6_detecteur"] = c6
    res["C6_rates"] = [{"id": s["id"], "classe": etiq[s["id"]]["classe"]} for s in segs
                       if (cle(etiq.get(s["id"]), "attaque") and not detections.get(s["id"], {}).get("attaque"))
                       or (cle(etiq.get(s["id"]), "soutien") and not detections.get(s["id"], {}).get("soutien"))]
    res["C6_fausses_alertes"] = [{"id": i, "lu": {k: d[k] for k in ("attaque", "soutien")},
                                  "etiquette": (etiq.get(i) or {}).get("classe", "neutre")}
                                 for i, d in detections.items()
                                 if (d["attaque"] and "attaque" not in _classes(etiq.get(i)))
                                 or (d["soutien"] and "soutien" not in _classes(etiq.get(i)))]
    debats = [s for s in segs if (etiq.get(s["id"]) or {}).get("classe") == "debat"
              and not etiq[s["id"]].get("vise_hakim")]
    neutres = [s for s in segs if s["id"] not in etiq]
    fa_debat = sum(1 for s in debats if detections.get(s["id"], {}).get("attaque"))
    fa_neutre_a = sum(1 for s in neutres if detections.get(s["id"], {}).get("attaque"))
    fa_neutre_s = sum(1 for s in neutres if detections.get(s["id"], {}).get("soutien"))
    res["C3_debat"] = {"attaque_sur_debat": wilson(fa_debat, len(debats)),
                       "attaque_sur_neutre": wilson(fa_neutre_a, len(neutres)),
                       "soutien_sur_neutre": wilson(fa_neutre_s, len(neutres)),
                       "tenu": (len(debats) == 0 or fa_debat / len(debats) <= 0.05)
                       and fa_neutre_a / max(1, len(neutres)) <= 0.01 and fa_neutre_s / max(1, len(neutres)) <= 0.02}

    # ---- les rejeux
    series = {"actuel": rejouer(evs, debut, fin)}
    for s in SAGESSES:
        series[f"s{s}"] = rejouer(corriges + chocs(segs, detections, s), debut, fin)

    # contrôle : la variante actuelle contre la valence vraiment journalisée
    vrai = []
    for l in JOURNAL_TEMPS.read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if debut <= o["t"] <= FIN and "valence" in o:
            vrai.append((o["t"], o["valence"]))
    ecarts = [abs(series["actuel"][_i(series["actuel"], t)][2] - v) for t, v in vrai]
    res["controle_actuel_vs_journal"] = {"points": len(ecarts), "ecart_moyen": round(sum(ecarts) / max(1, len(ecarts)), 4),
                                         "ecart_max": round(max(ecarts), 4) if ecarts else None}

    attaques_cles = [s for s in segs if cle(etiq.get(s["id"]), "attaque")]
    soutiens_cles = [s for s in segs if cle(etiq.get(s["id"]), "soutien")]

    # ---- descriptif : la courbe actuelle aux heures des attaques
    res["descriptif_actuel"] = [{"id": s["id"], "heure": time.strftime("%d/%m %H:%M", time.localtime(s["ts"])),
                                 "emotion": series["actuel"][_i(series["actuel"], s["ts"] + 120)][4],
                                 "valence": round(series["actuel"][_i(series["actuel"], s["ts"] + 120)][2], 3)}
                                for s in attaques_cles]

    # ---- C1
    n5 = series["s0.5"]
    c1 = []
    for s in attaques_cles:
        vu = bool(detections.get(s["id"], {}).get("attaque"))
        a, b = _i(n5, s["ts"]), _i(n5, s["ts"] + 120)
        adr = max(n5[j][1]["adrenaline"] - affect.HORMONES_V2["adrenaline"][0] for j in range(a, b + 1))
        emos = [n5[j][4] for j in range(a, b + 1)]
        neg = any(SIGNE.get(e) == -1 for e in emos)
        c1.append({"id": s["id"], "heure": time.strftime("%d/%m %H:%M", time.localtime(s["ts"])), "detecte": vu,
                   "adrenaline_exces": round(adr, 3), "emotions": sorted(set(emos)), "saut": vu and adr >= 0.15 and neg})
    res["C1_saut"] = {"cas": c1, "tenu": bool(c1) and sum(x["saut"] for x in c1) / len(c1) >= 0.8}

    # ---- C2 : chaque soutien clé d'Ahmed dans l'heure qui suit une attaque, contre le même rejeu sans lui
    def apres_attaque(s):
        return any(0 < s["ts"] - a["ts"] <= 3600 for a in attaques_cles)

    c2 = []
    base_evs = corriges + chocs(segs, detections, 0.5)
    for s in soutiens_cles:
        if s["qui"] != "ahmed" or not apres_attaque(s):
            continue
        # rejouer part toujours de l'état initial : on rejoue toute la période, sans ce soutien
        sans = rejouer([e for e in base_evs if e.get("seg") != s["id"]], debut, min(fin, s["ts"] + 3700))
        avec = n5
        cs_avec, cs_sans = charge_stress(avec, s["ts"]), charge_stress(sans, s["ts"])
        v_avec, v_sans = avec[_i(avec, s["ts"] + 600)][2], sans[_i(sans, s["ts"] + 600)][2]
        emo = avec[_i(avec, s["ts"] + 600)][4]
        vu = bool(detections.get(s["id"], {}).get("soutien"))
        c2.append({"id": s["id"], "heure": time.strftime("%d/%m %H:%M", time.localtime(s["ts"])), "detecte": vu,
                   "charge_stress_avec": round(cs_avec, 3), "charge_stress_sans": round(cs_sans, 3),
                   "valence_10min_avec": round(v_avec, 3), "valence_10min_sans": round(v_sans, 3), "emotion_10min": emo,
                   "tenu": cs_avec < cs_sans and v_avec > v_sans and SIGNE.get(emo) == 1})
    res["C2_reassurance"] = {"cas": c2, "tenu": bool(c2) and all(x["tenu"] for x in c2)}

    # ---- C4, C5 : sur chaque attaque détectée
    att_det = [s for s in segs if detections.get(s["id"], {}).get("attaque")]
    c4, c5 = [], []
    for s in att_det:
        pics = [pic(series[f"s{w}"], s["ts"], "adrenaline")[0] for w in SAGESSES]
        retours = [retour_valence(series[f"s{w}"], s["ts"]) for w in SAGESSES]
        c4.append({"id": s["id"], "pics": [round(x, 3) for x in pics], "retours_min": [round(x, 1) for x in retours],
                   "tenu": pics[0] > pics[1] > pics[2] and retours[0] > retours[1] > retours[2] and pics[2] >= 0.4 * pics[0]})
        avant = n5[max(0, _i(n5, s["ts"]) - 1)][1]
        apres = n5[_i(n5, s["ts"] + 300)][1]
        mouv = [apres["adrenaline"] - avant["adrenaline"] >= 0.02, apres["noradrenaline"] - avant["noradrenaline"] >= 0.02,
                apres["crh"] - avant["crh"] >= 0.02, avant["gaba"] - apres["gaba"] >= 0.02,
                avant["serotonine"] - apres["serotonine"] >= 0.02]
        _pa, qa = pic(n5, s["ts"], "adrenaline", 7200)
        _pc, qc = pic(n5, s["ts"], "cortisol", 7200)
        c5.append({"id": s["id"], "mouvements": sum(mouv), "pic_adrenaline_min": round((qa - s["ts"]) / 60, 1),
                   "pic_cortisol_min": round((qc - s["ts"]) / 60, 1), "tenu": sum(mouv) >= 4 and qc > qa})
    res["C4_sagesse"] = {"cas": c4, "tenu": bool(c4) and all(x["tenu"] for x in c4)}
    res["C5_couplage"] = {"cas": c5, "tenu": bool(c5) and all(x["tenu"] for x in c5)}

    # ---- C7 : qui parle
    ecart_voix = []
    for s in attaques_cles + soutiens_cles:
        lu = etiq[s["id"]].get("auteur_lu")
        if lu in ("ahmed", "tiers") and lu != s["qui"]:
            ecart_voix.append({"id": s["id"], "systeme": s["qui"], "lu": lu})
    sens = []
    for x in c2:
        force = {x["id"]: ("tiers", True)}
        sans_poids = rejouer(corriges + chocs(segs, detections, 0.5, force), debut, min(fin, par_id[x["id"]]["ts"] + 3700))
        t = par_id[x["id"]]["ts"]
        sens.append({"id": x["id"], "charge_stress_si_voix_tierce": round(charge_stress(sans_poids, t), 3),
                     "charge_stress_ahmed": x["charge_stress_avec"], "charge_stress_sans_soutien": x["charge_stress_sans"]})
    res["C7_voix"] = {"cles": len(attaques_cles) + len(soutiens_cles), "voix_differente": ecart_voix, "sensibilite": sens}

    DONNEES.mkdir(parents=True, exist_ok=True)
    (DONNEES / "resultats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    evts = {"attaques": [{"id": s["id"], "ts": s["ts"], "n": detections.get(s["id"], {}).get("attaque", 0),
                          "cle": cle(etiq.get(s["id"]), "attaque")} for s in segs
                         if detections.get(s["id"], {}).get("attaque") or cle(etiq.get(s["id"]), "attaque")],
            "soutiens": [{"id": s["id"], "ts": s["ts"], "n": detections.get(s["id"], {}).get("soutien", 0), "qui": s["qui"],
                          "cle": cle(etiq.get(s["id"]), "soutien")} for s in segs
                         if detections.get(s["id"], {}).get("soutien") or cle(etiq.get(s["id"]), "soutien")],
            "debats": [s["ts"] for s in debats]}
    garde = ("adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides",
             "dopamine", "endorphine")
    (DONNEES / "series.json").write_text(json.dumps({
        "evenements": evts, "vrai": vrai[::4],
        "series": {k: [[round(t), round(v, 4), round(a, 4), emo] + [round(e[h], 4) for h in garde]
                       for t, e, v, a, emo in serie] for k, serie in series.items()},
        "hormones": garde, "bases": {h: sensations.bases()[h] for h in garde}}, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({k: (v.get("tenu") if isinstance(v, dict) and "tenu" in v else None) for k, v in res.items()},
                     ensure_ascii=False))
    print(f"→ {DONNEES / 'resultats.json'}")


if __name__ == "__main__":
    main()
