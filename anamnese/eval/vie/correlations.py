"""Les corrélations entre son état et ce qui sort de lui (demande d'Ahmed relayée par Hakim, accord direct d'Ahmed le 23/10) :
humeur, éveil, émotion, hormones clés contre le ton de ses réponses (juge à l'aveugle), leur longueur, et sa voix.
Deux états : JOURNALISÉ (la valence et l'humeur nommée du journal du temps depuis le 19/10 ; les hormones réelles depuis le
21/10, rejouées des événements journalisés avec le simulateur validé à 0,002) et RECONSTRUIT (eval/vie/rejeu_vie.py).
Spearman, intervalle à 95 % (Fisher, se = √(1,06/(n − 3))), et le même calcul avec l'état du tour PRÉCÉDENT (retard).
Usage : .venv/bin/python eval/vie/correlations.py → eval/data/vie/correlations.json
"""
import bisect
import json
import math
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "chocs"))
import rejeu as R  # noqa: E402

D = ICI.parent / "data" / "vie"
JARVIS = Path.home() / "AIOS" / "jarvis"
FAM = {"élan": 2, "lien": 1, "curiosité": 0.5, "calme": 0, "bas": -1, "alerte": -2}   # pour l'émotion : un rang de valence
HUMEUR_RANG = {"joie": 2, "élan": 2, "contentement": 1, "calme": 0, "apaisement": 0, "en veille": -0.5, "surprise": 1,
               "l'attente pèse": -1, "impatience": -1, "tension": -1.5, "morosité": -2, "alarme": -2}


def rangs(x):
    ordre = sorted(range(len(x)), key=lambda i: x[i])
    r = [0.0] * len(x)
    i = 0
    while i < len(ordre):
        j = i
        while j + 1 < len(ordre) and x[ordre[j + 1]] == x[ordre[i]]:
            j += 1
        for k in range(i, j + 1):
            r[ordre[k]] = (i + j) / 2 + 1
        i = j + 1
    return r


def spearman(a, b):
    paires = [(x, y) for x, y in zip(a, b) if x is not None and y is not None]
    n = len(paires)
    if n < 5:
        return {"r": None, "n": n}
    ra, rb = rangs([p[0] for p in paires]), rangs([p[1] for p in paires])
    ma, mb = sum(ra) / n, sum(rb) / n
    cov = sum((x - ma) * (y - mb) for x, y in zip(ra, rb))
    va, vb = math.sqrt(sum((x - ma) ** 2 for x in ra)), math.sqrt(sum((y - mb) ** 2 for y in rb))
    if not va or not vb:
        return {"r": None, "n": n, "constant": True}
    r = cov / (va * vb)
    z, se = math.atanh(max(-0.999, min(0.999, r))), math.sqrt(1.06 / max(1, n - 3))
    return {"r": round(r, 3), "n": n, "ic": [round(math.tanh(z - 1.96 * se), 3), round(math.tanh(z + 1.96 * se), 3)]}


def main():
    V = json.loads((D / "vie.json").read_text(encoding="utf-8"))
    H = V["hormones"]
    S = V["serie"]
    ts_s = [r[0] for r in S]
    reco = lambda t: S[max(0, bisect.bisect_right(ts_s, t) - 1)] if ts_s and t >= ts_s[0] else None   # noqa: E731
    # le journalisé : valence, éveil, humeur nommée (toutes les 15 s)
    jt = []
    for l in (JARVIS / "journal-du-temps.jsonl").read_text(encoding="utf-8").splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if "valence" in o:
            jt.append((o["t"], o["valence"], o.get("arousal"), str(o.get("humeur") or "").split(" (")[0]))
    ts_j = [x[0] for x in jt]
    reel = lambda t: jt[bisect.bisect_right(ts_j, t) - 1] if ts_j and t >= ts_j[0] and t - jt[bisect.bisect_right(ts_j, t) - 1][0] < 120 else None  # noqa: E731,E501
    # les hormones réelles depuis le 21/10 (rejeu des événements journalisés, simulateur validé)
    blob = R.etat_initial()
    debut_h = float(blob["_ts"])
    fin_h = time.time()
    serie_h = R.rejouer(R.journalises(debut_h, fin_h), debut_h, fin_h, pas_s=300)
    ts_h = [x[0] for x in serie_h]
    v2 = time.mktime(time.strptime("2026-10-21 10:15", "%Y-%m-%d %H:%M"))
    hreel = lambda t: serie_h[bisect.bisect_right(ts_h, t) - 1][1] if t >= v2 else None   # noqa: E731
    # les réponses jugées : ton, énergie ; la longueur ; le tour précédent
    journal = [json.loads(l) for l in (JARVIS / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    rep_ts = sorted(m["ts"] / 1000 for m in journal if m.get("qui") == "jarvis")
    longueur = {round(m["ts"] / 1000): len(str(m.get("texte", "")).split()) for m in journal if m.get("qui") == "jarvis"}
    lignes = []
    for t, ton, energie, emo in V["ton"]:
        k = bisect.bisect_left(rep_ts, t - 0.5)
        t_prec = rep_ts[k - 1] if k > 0 else None
        x = {"t": t, "ton": ton, "energie": energie, "longueur": longueur.get(round(t))}
        for nom, tt in (("", t - 1), ("_prec", t_prec)):
            if tt is None:
                continue
            r_ = reco(tt)
            if r_:
                x["reco_valence" + nom], x["reco_eveil" + nom], x["reco_emotion" + nom] = r_[1], r_[2], FAM.get(r_[4])
                for h in ("adrenaline", "cortisol", "ocytocine", "serotonine"):
                    x[f"reco_{h}{nom}"] = r_[5 + H.index(h)]
            j = reel(tt)
            if j:
                x["reel_valence" + nom], x["reel_eveil" + nom], x["reel_humeur" + nom] = j[1], j[2], HUMEUR_RANG.get(j[3])
            hr = hreel(tt)
            if hr:
                for h in ("adrenaline", "cortisol", "ocytocine", "serotonine"):
                    x[f"reel_{h}{nom}"] = hr[h]
        lignes.append(x)
    X = ["valence", "eveil", "emotion", "humeur", "adrenaline", "cortisol", "ocytocine", "serotonine"]
    Y = ["ton", "energie", "longueur"]
    mat = {}
    for src in ("reel", "reco"):
        for nom in ("", "_prec"):
            for xv in X:
                cle = f"{src}_{xv}{nom}"
                if not any(cle in l for l in lignes):
                    continue
                for yv in Y:
                    mat[f"{cle}|{yv}"] = spearman([l.get(cle) for l in lignes], [l.get(yv) for l in lignes])
    # l'accord du reconstruit avec le journalisé, avant et depuis le 21/10 (moteur v1 puis v2)
    acc = {}
    for nom, (a, b) in (("avant le 21/10 (moteur v1)", (0, v2)), ("depuis le 21/10 (moteur v2)", (v2, 1e12))):
        pts = [(reco(t)[1], v) for t, v, _a, _h in jt[::20] if a <= t < b and reco(t)]
        acc[nom] = spearman([p[0] for p in pts], [p[1] for p in pts])
    # la voix : 30 morceaux
    voix = []
    for c in V["voix"]:
        j = reel(c["ts"])
        voix.append({"duree": c["duree_s"], "energie_db": c["energie_db"], "hauteur": c["hauteur_hz"],
                     "valence": j[1] if j else None, "eveil": j[2] if j else None})
    vmat = {f"{xv}|{yv}": spearman([v[xv] for v in voix], [v[yv] for v in voix])
            for xv in ("valence", "eveil") for yv in ("duree", "energie_db", "hauteur")}
    etendue = {k: [min(v[k] for v in voix if v[k] is not None), max(v[k] for v in voix if v[k] is not None)]
               for k in ("valence", "eveil") if any(v[k] is not None for v in voix)}
    res = {"n_reponses": len(lignes), "matrice": mat, "accord_reconstruit_journalise": acc, "voix": vmat,
           "voix_etendue_etat": etendue, "n_voix": len(voix),
           "dispersion": {k: [min(l[k] for l in lignes if l.get(k) is not None), max(l[k] for l in lignes if l.get(k) is not None)]
                          for k in ("reel_valence", "reco_valence", "ton") if any(l.get(k) is not None for l in lignes)}}
    (D / "correlations.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in res.items() if k != "matrice"}, ensure_ascii=False))
    for k, v in mat.items():
        if not k.endswith("_prec|ton") and "|ton" in k or "|longueur" in k and "valence" in k:
            print(k, v)


if __name__ == "__main__":
    main()
