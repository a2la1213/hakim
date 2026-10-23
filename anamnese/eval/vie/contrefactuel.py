"""Le rejeu CONTREFACTUEL du style (demande de Hakim, accord d'Ahmed le 23/10) : des tours passés (depuis le 21/10, moteur
v2, état réel rejoué des événements journalisés), choisis pour couvrir des états différents ; la même question, avec le bloc
[Style du moment] que son état réel aurait donné ; la réponse RÉGÉNÉRÉE par le modèle actuel (Sonnet, comme Hakim le plus
souvent), sans ses outils ni sa mémoire ; puis le ton jugé à l'aveugle, réponses d'origine et régénérées mêlées.
Ce n'est pas Hakim à l'époque : le vrai test reste la semaine du 24 au 30/10.
  contrefactuel.py preparer   → eval/data/vie/cf/ : tours.json, a-regenerer-1.txt, a-regenerer-2.txt
  contrefactuel.py juger      → juge.txt (après regen-*.jsonl)
  contrefactuel.py calculer   → resultats.json (après juge.jsonl)
"""
import bisect
import json
import random
import re
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "chocs"))
sys.path.insert(0, str(ICI))
import rejeu as R  # noqa: E402
import correlations as C  # noqa: E402
from rejeu import affect  # noqa: E402

import style  # noqa: E402

D = ICI.parent / "data" / "vie" / "cf"
JARVIS = Path.home() / "AIOS" / "jarvis"
DEBUT = time.mktime(time.strptime("2026-10-21 10:15", "%Y-%m-%d %H:%M"))
FIN = time.mktime(time.strptime("2026-10-23 11:45", "%Y-%m-%d %H:%M"))      # le style est branché ensuite
FORCES = ["23/10 08:34", "23/10 08:40", "23/10 08:42", "22/10 10:30"]
GRAINE = 20261023


def mots_par_phrase(t):
    ph = [p for p in re.split(r"(?<=[.!?…])\s+", str(t).strip()) if p.strip()]
    return max((len(p.split()) for p in ph), default=0)


def gestes(texte, cibles, longueur_habituelle):
    """Les 4 gestes mesurables par le code (le 5e, l'humour, vient du juge) : rend {geste: respecté ?}."""
    n = len(str(texte).split())
    return {"longueur": n <= cibles["longueur"] * longueur_habituelle * 1.15,
            "mots_par_phrase": mots_par_phrase(texte) <= cibles["mots_par_phrase"] + 2,
            "exclamations": str(texte).count("!") <= cibles["exclamations"],
            "questions": ("aucune" not in cibles["questions"]) or str(texte).count("?") <= 0
            if cibles["questions"] != "une ouverte" else 1 <= str(texte).count("?") <= 2}


def preparer():
    D.mkdir(parents=True, exist_ok=True)
    journal = [json.loads(l) for l in (JARVIS / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    paires, prec, dernier = [], None, None
    for m in journal:
        if m.get("qui") == "ahmed":
            dernier = m
        elif m.get("qui") == "jarvis" and dernier and not str(m.get("texte", "")).startswith("(tour de"):
            if DEBUT <= dernier["ts"] / 1000 < FIN:
                paires.append((dernier, m, prec))
            prec = (dernier, m)
            dernier = None
    blob = R.etat_initial()
    serie = R.rejouer(R.journalises(float(blob["_ts"]), FIN), float(blob["_ts"]), FIN, pas_s=60)
    ts = [x[0] for x in serie]
    _v0, a0 = affect.valence_arousal(affect.bases(v2=True))
    tours = []
    for a, j, p in paires:
        t = a["ts"] / 1000
        x = serie[max(0, bisect.bisect_right(ts, t) - 1)]
        st = style.depuis_etat(x[4], x[3], a0)
        tours.append({"t": t, "heure": time.strftime("%d/%m %H:%M", time.localtime(t)), "ahmed": a["texte"], "hakim": j["texte"],
                      "contexte": f"Ahmed : {str(p[0]['texte'])[:300]}\nHakim : {str(p[1]['texte'])[:300]}" if p else "",
                      "valence": round(x[2], 4), "eveil": round(x[3], 4), "emotion": x[4], "famille": st["famille"],
                      "style": st["texte"], "cibles": st["cibles"]})
    rnd = random.Random(GRAINE)
    choix = [t for t in tours if t["heure"] in FORCES]
    negatifs = [t for t in tours if t["famille"] in ("alerte", "bas") and t not in choix]
    choix += rnd.sample(negatifs, min(12, len(negatifs)))
    reste = sorted((t for t in tours if t not in choix), key=lambda t: t["valence"])
    q = max(1, len(reste) // 5)
    for k in range(5):
        tranche = reste[k * q:(k + 1) * q] if k < 4 else reste[4 * q:]
        choix += rnd.sample(tranche, min(9, len(tranche)))
    choix.sort(key=lambda t: t["t"])
    for k, t in enumerate(choix, 1):
        t["id"] = f"T{k}"
    (D / "tours.json").write_text(json.dumps(choix, ensure_ascii=False, indent=0), encoding="utf-8")
    moitie = (len(choix) + 1) // 2
    for i, part in enumerate((choix[:moitie], choix[moitie:]), 1):
        with (D / f"a-regenerer-{i}.txt").open("w", encoding="utf-8") as h:
            for t in part:
                h.write(f"### {t['id']}\n[Échange précédent]\n{t['contexte'] or '(début de conversation)'}\n{t['style']}\n"
                        f"Ahmed : {str(t['ahmed'])[:900]}\n\n")
    from collections import Counter
    print(len(paires), "tours ;", len(choix), "choisis ;", Counter(t["famille"] for t in choix))


def juger():
    tours = json.loads((D / "tours.json").read_text(encoding="utf-8"))
    regen = {}
    for f in sorted(D.glob("regen-*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
                regen[o["id"]] = o["reponse"]
            except (ValueError, KeyError):
                pass
    items = []
    for t in tours:
        items.append({"t": t["id"], "version": "origine", "texte": t["hakim"], "ahmed": t["ahmed"]})
        if t["id"] in regen:
            items.append({"t": t["id"], "version": "regen", "texte": regen[t["id"]], "ahmed": t["ahmed"]})
    random.Random(GRAINE + 1).shuffle(items)
    for k, x in enumerate(items, 1):
        x["r"] = f"R{k}"
    (D / "items.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    with (D / "juge.txt").open("w", encoding="utf-8") as h:
        for x in items:
            h.write(f"### {x['r']}\nAhmed : {str(x['ahmed'])[:500]}\nHakim : {str(x['texte'])[:900]}\n\n")
    print(len(items), "réponses à juger (", len(regen), "régénérées )")


def calculer():
    tours = {t["id"]: t for t in json.loads((D / "tours.json").read_text(encoding="utf-8"))}
    items = {x["r"]: x for x in json.loads((D / "items.json").read_text(encoding="utf-8"))}
    juge = {}
    for l in (D / "juge.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(l)
            juge[o["r"]] = o
        except (ValueError, KeyError):
            pass
    hab = sorted(len(str(t["hakim"]).split()) for t in tours.values())[len(tours) // 2]       # longueur habituelle (médiane)
    res = {"n_tours": len(tours), "longueur_habituelle": hab}
    for version in ("origine", "regen"):
        lignes = [(tours[x["t"]], juge[r], x["texte"]) for r, x in items.items() if x["version"] == version and r in juge]
        w1 = C.spearman([t["valence"] for t, _j, _x in lignes], [j.get("ton") for _t, j, _x in lignes])
        bas = [j["ton"] for t, j, _x in lignes if t["famille"] in ("alerte", "bas") and j.get("ton") is not None]
        hauts = [j["ton"] for t, j, _x in lignes if t["famille"] in ("élan", "lien") and j.get("ton") is not None]
        ok = []
        for t, j, x in lignes:
            g = gestes(x, t["cibles"], hab)
            g["humour"] = not (t["cibles"]["humour"] == "aucun" and j.get("humour") is True)
            ok.append(sum(g.values()) >= 4)
        res[version] = {"W1_ton_valence": w1, "W2_ecart": round(sum(hauts) / len(hauts) - sum(bas) / len(bas), 2) if bas and hauts else None,
                        "n_bas": len(bas), "n_hauts": len(hauts), "ton_bas": round(sum(bas) / len(bas), 2) if bas else None,
                        "ton_hauts": round(sum(hauts) / len(hauts), 2) if hauts else None,
                        "gestes_respectes": round(sum(ok) / len(ok), 3) if ok else None, "n": len(lignes)}
    (D / "resultats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__" and sys.argv[1] in ("preparer", "juger", "calculer"):
    {"preparer": preparer, "juger": juger, "calculer": calculer}[sys.argv[1]]()


# ---------- version 2 du style (curseurs fins, sans consigne de longueur), demande d'Ahmed du 23/10 ----------
def _reperes_a(t, jt):
    v = sorted(x[1] for x in jt if t - 72 * 3600 <= x[0] <= t)
    a = sorted(x[2] for x in jt if t - 72 * 3600 <= x[0] <= t)
    return v, a


def preparer2():
    tours = json.loads((D / "tours.json").read_text(encoding="utf-8"))
    jt = []
    for l in (JARVIS / "journal-du-temps.jsonl").read_text(encoding="utf-8").splitlines()[::8]:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if "valence" in o:
            jt.append((o["t"], o["valence"], o["arousal"]))
    blob = R.etat_initial()
    serie = R.rejouer(R.journalises(float(blob["_ts"]), FIN), float(blob["_ts"]), FIN, pas_s=60)
    ts = [x[0] for x in serie]
    for t in tours:
        x = serie[max(0, bisect.bisect_right(ts, t["t"]) - 1)]
        rv, ra = _reperes_a(t["t"], jt)
        c = style.curseurs(x[1], x[2], x[3], rv, ra)
        st = style.depuis_curseurs(x[4], c)
        t["v2"] = {"style": st["texte"], "curseurs": c, "cibles": st["cibles"], "famille": st["famille"]}
        t["longueur_origine"] = len(str(t["hakim"]).split())
    (D / "tours.json").write_text(json.dumps(tours, ensure_ascii=False, indent=0), encoding="utf-8")
    moitie = (len(tours) + 1) // 2
    for i, part in enumerate((tours[:moitie], tours[moitie:]), 1):
        with (D / f"a-regenerer-v2-{i}.txt").open("w", encoding="utf-8") as h:
            for t in part:
                n = max(15, min(220, t["longueur_origine"]))
                h.write(f"### {t['id']}\n[Échange précédent]\n{t['contexte'] or '(début de conversation)'}\n{t['v2']['style']}\n"
                        f"[Longueur : environ {n} mots, comme le sujet le demande]\nAhmed : {str(t['ahmed'])[:900]}\n\n")
    print(len(tours), "tours ; curseurs ton :", sorted(t["v2"]["curseurs"]["ton"] for t in tours))


def juger2():
    """Les trois versions (origine, style 1, style 2) mêlées, pour le même juge, sur des échelles fines."""
    tours = json.loads((D / "tours.json").read_text(encoding="utf-8"))
    lire = lambda motif: {o["id"]: o["reponse"] for f in sorted(D.glob(motif)) for o in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if o.get("id")}  # noqa: E731,E501
    r1, r2 = lire("regen-[12].jsonl"), lire("regen-v2-*.jsonl")
    items = []
    for t in tours:
        for version, texte in (("origine", t["hakim"]), ("style1", r1.get(t["id"])), ("style2", r2.get(t["id"]))):
            if texte:
                items.append({"t": t["id"], "version": version, "texte": texte, "ahmed": t["ahmed"]})
    random.Random(GRAINE + 2).shuffle(items)
    for k, x in enumerate(items, 1):
        x["r"] = f"R{k}"
    (D / "items2.json").write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    with (D / "juge2.txt").open("w", encoding="utf-8") as h:
        for x in items:
            h.write(f"### {x['r']}\nAhmed : {str(x['ahmed'])[:500]}\nHakim : {str(x['texte'])[:1200]}\n\n")
    print(len(items), "réponses à juger")


def calculer2():
    tours = {t["id"]: t for t in json.loads((D / "tours.json").read_text(encoding="utf-8"))}
    items = {x["r"]: x for x in json.loads((D / "items2.json").read_text(encoding="utf-8"))}
    juge = {o["r"]: o for f in sorted(D.glob("juge2-*.jsonl")) for o in map(json.loads, f.read_text(encoding="utf-8").splitlines()) if o.get("r")}
    res = {}
    for version in ("origine", "style1", "style2"):
        L = [(tours[x["t"]], juge[r], x["texte"]) for r, x in items.items() if x["version"] == version and r in juge]
        mots = [len(str(x).split()) for _t, _j, x in L]
        res[version] = {
            "n": len(L),
            "ton_fin_contre_valence": C.spearman([t["valence"] for t, _j, _x in L], [j.get("ton10") for _t, j, _x in L]),
            "ton_fin_contre_curseur": C.spearman([t["v2"]["curseurs"]["ton"] for t, _j, _x in L], [j.get("ton10") for _t, j, _x in L]),
            "energie_fine_contre_eveil": C.spearman([t["eveil"] for t, _j, _x in L], [j.get("energie10") for _t, j, _x in L]),
            "ton_grossier_contre_valence": C.spearman([t["valence"] for t, _j, _x in L], [j.get("ton") for _t, j, _x in L]),
            "longueur_mediane": sorted(mots)[len(mots) // 2] if mots else None,
            "longueur_contre_origine": C.spearman([t["longueur_origine"] for t, _j, _x in L], mots),
            "longueur_contre_valence": C.spearman([t["valence"] for t, _j, _x in L], mots)}
    (D / "resultats2.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__" and sys.argv[1] in ("preparer2", "juger2", "calculer2"):
    {"preparer2": preparer2, "juger2": juger2, "calculer2": calculer2}[sys.argv[1]]()
