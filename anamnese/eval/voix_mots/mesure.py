"""La mesure hebdomadaire : ses mots et sa voix suivent-ils son état ? (critères figés : eval/voix_mots/criteres.md)
  mesure.py preparer [debut] [fin]   → eval/data/voix_mots/<debut>/ : reponses.txt (juge du ton), style.txt (juge du style)
  mesure.py calculer [debut] [fin]   → resultats.json, après les juges (ton.jsonl, style.jsonl dans le même dossier)
Dates au format AAAA-MM-JJ ; par défaut, la fenêtre du test : 2026-10-24 → 2026-10-30.
"""
import bisect
import json
import random
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "vie"))
import correlations as C  # noqa: E402

JARVIS = Path.home() / "AIOS" / "jarvis"
CHOCS = ICI.parents[1] / "data" / "chocs.jsonl"
GRAINE = 20261031
FAMILLES_BASSES, FAMILLES_HAUTES = {"alerte", "bas"}, {"élan", "lien"}


def _jsonl(f):
    out = []
    try:
        for l in Path(f).read_text(encoding="utf-8").splitlines():
            try:
                out.append(json.loads(l))
            except ValueError:
                pass
    except OSError:
        pass
    return out


def fenetre(argv):
    d = argv[2] if len(argv) > 2 else "2026-10-24"
    f = argv[3] if len(argv) > 3 else "2026-10-30"
    return d, time.mktime(time.strptime(d, "%Y-%m-%d")), time.mktime(time.strptime(f, "%Y-%m-%d")) + 86400


def paires(a, b):
    """(message d'Ahmed, réponse de Hakim, style du tour) de la fenêtre, depuis le journal brut et ses archives."""
    msgs = []
    for f in sorted((JARVIS / "archives").glob("journal-*.jsonl")) + [JARVIS / "journal.jsonl"]:
        msgs += _jsonl(f)
    msgs = sorted({(m["ts"], m["qui"]): m for m in msgs if isinstance(m.get("ts"), (int, float))}.values(), key=lambda m: m["ts"])
    styles = sorted((x["ts"], x) for x in _jsonl(CHOCS) if x.get("type") == "style")
    ts_s = [s[0] for s in styles]
    out, dernier = [], None
    for m in msgs:
        t = m["ts"] / 1000
        if m.get("qui") == "ahmed":
            dernier = m
        elif m.get("qui") == "jarvis" and dernier and a <= t < b and not str(m.get("texte", "")).startswith("(tour de"):
            k = bisect.bisect_right(ts_s, dernier["ts"] / 1000 + 5) - 1
            st = styles[k][1] if k >= 0 and dernier["ts"] / 1000 - styles[k][0] < 120 else None
            out.append((dernier, m, st))
            dernier = None
    return out


def preparer(argv):
    nom, a, b = fenetre(argv)
    d = ICI.parents[1] / "eval" / "data" / "voix_mots" / nom
    d.mkdir(parents=True, exist_ok=True)
    par_heure = {}
    for p in paires(a, b):
        par_heure.setdefault(int(p[1]["ts"] / 3_600_000), []).append(p)
    rnd = random.Random(GRAINE)
    choix = [x for h in sorted(par_heure) for x in rnd.sample(par_heure[h], min(3, len(par_heure[h])))]
    with (d / "reponses.txt").open("w", encoding="utf-8") as h1, (d / "style.txt").open("w", encoding="utf-8") as h2:
        for k, (am, jm, st) in enumerate(choix, 1):
            h1.write(f"### R{k}\nAhmed : {str(am['texte'])[:500]}\nHakim : {str(jm['texte'])[:900]}\n\n")
            if st:
                h2.write(f"### R{k}\nConsigne de style : {st['texte']}\nAhmed : {str(am['texte'])[:500]}\nHakim : {str(jm['texte'])[:900]}\n\n")
    (d / "index.json").write_text(json.dumps([{"r": f"R{k}", "ts": jm["ts"] / 1000, "famille": (st or {}).get("famille")}
                                              for k, (_a, jm, st) in enumerate(choix, 1)]), encoding="utf-8")
    print(f"{len(choix)} réponses → {d}")


def calculer(argv):
    nom, a, b = fenetre(argv)
    d = ICI.parents[1] / "eval" / "data" / "voix_mots" / nom
    idx = {x["r"]: x for x in json.loads((d / "index.json").read_text())}
    ton = {o["r"]: o for o in _jsonl(d / "ton.jsonl")}
    sty = {o["r"]: o for o in _jsonl(d / "style.jsonl")}
    jt = [(o["t"], o["valence"], o.get("arousal")) for o in _jsonl(JARVIS / "journal-du-temps.jsonl") if "valence" in o]
    ts_j = [x[0] for x in jt]
    etat = lambda t: jt[bisect.bisect_right(ts_j, t) - 1] if ts_j and t >= ts_j[0] else None   # noqa: E731
    lignes = [(idx[r]["ts"], idx[r]["famille"], o.get("ton")) for r, o in ton.items() if r in idx]
    w1 = C.spearman([(etat(t) or (0, None))[1] for t, _f, _x in lignes], [x for _t, _f, x in lignes])
    bas = [x for _t, f, x in lignes if f in FAMILLES_BASSES and x is not None]
    hauts = [x for _t, f, x in lignes if f in FAMILLES_HAUTES and x is not None]
    w2 = None if len(bas) < 10 or len(hauts) < 10 else round(sum(hauts) / len(hauts) - sum(bas) / len(bas), 2)
    suit = [o.get("suit") for o in sty.values() if isinstance(o.get("suit"), bool)]
    fond = [o.get("fond") for o in sty.values() if isinstance(o.get("fond"), bool)]
    vx = [o for o in _jsonl(JARVIS / "voix-mesures.jsonl") if a <= o.get("ts", 0) < b]
    v1a = C.spearman([(etat(o["ts"]) or (0, 0, None))[2] for o in vx], [o["energie_db"] for o in vx])
    v1b = C.spearman([o.get("exaggeration") for o in vx], [o["energie_db"] for o in vx])
    res = {"W1": {**w1, "tenu": bool(w1.get("r") is not None and w1["n"] >= 150 and w1["r"] >= 0.30)},
           "W2": {"ecart": w2, "n_bas": len(bas), "n_hauts": len(hauts), "tenu": None if w2 is None else w2 >= 0.5},
           "W3": {"part": round(sum(suit) / len(suit), 3) if suit else None, "n": len(suit), "tenu": bool(suit) and sum(suit) / len(suit) >= 0.70},
           "W4": {"part": round(sum(fond) / len(fond), 3) if fond else None, "n": len(fond), "tenu": bool(fond) and sum(fond) / len(fond) >= 0.98},
           "V1": {"energie_eveil": v1a, "energie_expressivite": v1b, "n": len(vx),
                  "tenu": None if len(vx) < 100 else bool((v1a.get("r") or 0) >= 0.30 and (v1b.get("r") or 0) >= 0.30)},
           "hauteur_eveil": C.spearman([(etat(o["ts"]) or (0, 0, None))[2] for o in vx], [o.get("hauteur_hz") for o in vx])}
    (d / "resultats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    {"preparer": preparer, "calculer": calculer}[sys.argv[1]](sys.argv)
