"""(10/11, agent blancs) Les blancs de sa voix sur une fenêtre de temps, en lecture seule : ce qui a VRAIMENT sonné chez papa (voix-dite.jsonl)
et, pour chaque blanc entre deux bouts d'une même réponse, ce que faisait le bout suivant pendant ce blanc (pas encore demandé, chez Azure,
en file derrière d'autres conversions, en conversion au timbre de rap, prêt mais pas encore joué) ; la file des conversions, celles qui n'ont
jamais sonné, et le premier son après ta parole (tour_temps). Attention : voix-diagnostic.jsonl ne garde que ses 2 000 dernières lignes.
(10/11, 09:50, agent blancs2) l'appariement d'une conversion à son appel Azure et au bout sonné suivait l'ordre d'arrivée : faux depuis la file
à priorités (10/11 07:35) ; il annonçait 13,9 s de file et 64 conversions jamais sonnées sur 107 là où la file était vide (121 conversions sur
127 commencent dès la fin de leur Azure) et 44 jamais sonnées. Maintenant : le bout sonné est relié à la conversion de même durée (son rendu,
à la vitesse de sa voix près) ou de même texte (« car », noté depuis le 10/11), puis à l'appel Azure de même longueur fini juste avant ;
une conversion non reliée qui a sonné hors d'un message (ses réponses au live : voix-dite ne les note pas, bout_dit oui) est comptée à part.
Usage : python3 -I blancs-voix.py 05:30 06:35 [AAAA-MM-JJ]   (par défaut : aujourd'hui)"""
import collections
import datetime
import json
import os
import statistics
import sys

JARVIS = os.path.expanduser("~/AIOS/jarvis")
PRET = "prêt, pas encore joué (réseau, page, respiration)"


def lignes(f):
    try:
        with open(f, encoding="utf-8") as h:
            for l in h:
                if l.startswith("{"):
                    try:
                        yield json.loads(l)
                    except ValueError:
                        pass
    except OSError:
        return


def q(l, p):
    l = sorted(l)
    return l[min(len(l) - 1, int(p * len(l)))] if l else None


def resume(nom, l):
    if not l:
        print(f"{nom} : aucun")
        return
    print(f"{nom} : n={len(l)} · médiane {statistics.median(l) / 1000:.2f} s · p90 {q(l, .9) / 1000:.2f} s · total {sum(l) / 1000:.1f} s")


def proche(n, m):
    return abs(n - m) <= max(2, 0.1 * n)


def relier(sons, conv, azure):
    """chaque bout sonné → sa conversion (même texte si « car » est noté, sinon même durée à la vitesse de sa voix près), puis l'appel Azure
    de même longueur fini juste avant elle"""
    def duree_ok(c, s, v, tol):
        return "rendu_s" in c and abs(c["rendu_s"] / v - s["duree_ms"] / 1000) <= tol
    ratios = []
    for s in sons:                                   # 1er passage : la vitesse de sa voix (rendu / durée sonnée)
        for c in conv:
            if c["t"] <= s["t_ms"] + 400 and s["t_ms"] - c["t"] < 60000 and "rendu_s" in c and s["duree_ms"] > 0:
                r = c["rendu_s"] / (s["duree_ms"] / 1000)
                if 0.85 <= r <= 1.25 and ("car" not in c or proche(c["car"], len(s["texte"]))):
                    ratios.append(r)
    v = statistics.median(ratios) if ratios else 1.0
    pris_c, pris_a = set(), set()
    for s in sons:
        n = len(s["texte"])
        cand = [(abs(c["rendu_s"] / v - s["duree_ms"] / 1000) if "rendu_s" in c else 0, s["t_ms"] - c["t"], i) for i, c in enumerate(conv)
                if i not in pris_c and c["t"] <= s["t_ms"] + 400 and s["t_ms"] - c["t"] < 60000
                and (proche(c["car"], n) if "car" in c else duree_ok(c, s, v, 0.15))]
        if not cand:
            continue
        i = min(cand)[2]
        pris_c.add(i)
        c = conv[i]
        cs = c["t"] - c["ms"]
        ca = [(cs - a["t"], k) for k, a in enumerate(azure) if k not in pris_a and a["t"] <= cs + 50 and cs - a["t"] < 60000 and proche(a["caracteres"], n)]
        a = None
        if ca:
            k = min(ca)[1]
            pris_a.add(k)
            a = azure[k]
        s["p"] = dict(As=a["t"] - a["ms"] if a else None, Ae=a["t"] if a else None, Cs=cs, Ce=c["t"])
        c["son"] = s
    return v


def main(args):
    jour = datetime.date.fromisoformat(args[2]) if len(args) > 2 else datetime.date.today()
    heure = lambda x: int(datetime.datetime.combine(jour, datetime.time.fromisoformat(x)).timestamp() * 1000)
    a0, a1 = heure(args[0]), heure(args[1])
    marge = 120000
    diag = [d for d in lignes(os.path.join(os.environ.get("VOIX_DIAGNOSTIC_DIR", JARVIS), "voix-diagnostic.jsonl")) if a0 - marge <= d.get("t", 0) <= a1 + marge]
    if not diag:
        print("le journal de diagnostic ne couvre pas cette fenêtre (il ne garde que ses 2 000 dernières lignes) : rien à mesurer")
        return
    if diag:
        premier = min(d["t"] for d in diag)
        if premier > a0:
            print(f"(le journal de diagnostic ne commence qu'à {datetime.datetime.fromtimestamp(premier / 1000):%H:%M:%S} : fenêtre raccourcie)")
            a0 = premier
    sons = sorted((d for d in lignes(os.path.join(JARVIS, "voix-dite.jsonl")) if a0 <= d.get("t_ms", 0) <= a1), key=lambda d: d["t_ms"])
    azure = sorted((d for d in diag if d.get("e") == "synthese_azure"), key=lambda d: d["t"])
    conv = sorted((d for d in diag if d.get("e") == "azure_rap"), key=lambda d: d["t"] - d["ms"])
    v = relier(sons, conv, azure)
    print(f"fenêtre {datetime.datetime.fromtimestamp(a0 / 1000):%H:%M:%S} → {datetime.datetime.fromtimestamp(a1 / 1000):%H:%M:%S} · {len(sons)} bouts sonnés "
          f"({sum(1 for s in sons if s.get('p'))} reliés à leur conversion ; vitesse de sa voix {v:.2f})")
    fen = [c for c in conv if a0 <= c["t"] <= a1]
    print("\n— sa voix de rap (Azure, puis conversion au timbre de rap, une à la fois) —")
    resume("Azure", [d["ms"] for d in azure if a0 <= d["t"] <= a1])
    if fen:
        fin_az = [d["t"] for d in azure]
        tout_de_suite = sum(1 for c in fen if any(0 <= c["t"] - c["ms"] - t < 150 for t in fin_az))
        occ = sum(c["ms"] for c in fen) / max(1, a1 - a0)
        print(f"conversions : {len(fen)} · {tout_de_suite} commencent dès la fin de leur Azure · GPU de sa voix occupé {100 * occ:.0f} % du temps")
    resume("file avant la conversion (bouts sonnés)", [s["p"]["Cs"] - s["p"]["Ae"] for s in sons if s.get("p") and s["p"]["Ae"] is not None])
    notes = [c["file_ms"] for c in fen if "file_ms" in c]
    if notes:
        resume("file avant la conversion (notée par le cockpit, toutes)", notes)
    resume("conversion", [c["ms"] for c in fen])
    bouts_dits = [d["t"] for d in diag if d.get("e") == "bout_dit"]
    coupures = [d["t"] for d in diag if d.get("e") in ("relance", "coupure_notee", "coupe_net", "reponse_lachee", "suite_sautee", "epissure_stop")]
    sort = collections.Counter()
    calc = collections.Counter()
    for c in fen:
        if c.get("son"):
            k = "sonnée (voix-dite)"
        elif any(c["t"] - 300 <= t <= c["t"] + 15000 for t in bouts_dits):
            k = "sonnée hors d'un message (bout_dit : ses réponses au live)"
        elif any(c["t"] - c["ms"] - 8000 <= t <= c["t"] + 8000 for t in coupures):
            k = "lâchée : papa reparle ou le coupe"
        else:
            k = "autre (pensée sautée, début gardé…)"
        sort[k] += 1
        calc[k] += c["ms"]
    tot = sum(calc.values()) or 1
    for k, n in sort.most_common():
        print(f"  {k:58s} {n:3d}  {calc[k] / 1000:5.0f} s de calcul ({100 * calc[k] / tot:3.0f} %)")
    sep = [(d["t"] - d.get("attente_voix_ms", 0), d["t"]) for d in diag if d.get("e") == "paroles_azure" and d.get("separee")]
    def chev(c):
        s, e = c["t"] - c["ms"], c["t"]
        return sum(max(0, min(b, e) - max(a, s)) for a, b in sep) / max(1, c["ms"])
    avec = [c for c in fen if c.get("audio_s") and chev(c) > 0.3]
    sans = [c for c in fen if c.get("audio_s") and chev(c) <= 0.05]
    cout = lambda l: statistics.median((c["ms"] / 1000 - 2.7) / c["audio_s"] for c in l) if l else float("nan")
    print(f"coût par seconde de voix : {cout(avec):.2f} s avec une séparation en même temps (n={len(avec)}), {cout(sans):.2f} s sans (n={len(sans)})")
    rognes = [d for d in fen if "azure_s" in d and "rendu_s" in d]
    if rognes:
        print(f"silence retiré (depuis le 10/11) : Azure {statistics.median(d['azure_s'] for d in rognes):.2f} s → rendu {statistics.median(d['rendu_s'] for d in rognes):.2f} s en médiane")
    tours = [d["t"] for d in diag if d.get("e") == "tour_temps" and d.get("son")]
    blancs, etats = [], collections.Counter()
    for x, y in zip(sons, sons[1:]):
        fin = x["t_ms"] + x["duree_ms"]
        g = y["t_ms"] - fin
        if g > 30000 or g < -500 or any(fin - 300 <= t <= y["t_ms"] + 300 for t in tours) or any(x["t_ms"] <= t <= y["t_ms"] for t in coupures):
            continue
        g = max(0, g)
        blancs.append(g)
        p = y.get("p")
        if not g:
            continue
        if not p:
            etats["bout suivant sans conversion reliée (voix gardée)"] += g
            continue
        As = p["As"] if p["As"] is not None else p["Cs"]
        Ae = p["Ae"] if p["Ae"] is not None else p["Cs"]
        for nom, u, w in (("pas encore demandé (sa demande, son intonation)", -1e18, As), ("chez Azure", As, Ae), ("en file derrière d'autres conversions", Ae, p["Cs"]),
                          ("en conversion au timbre de rap", p["Cs"], p["Ce"]), (PRET, p["Ce"], 1e18)):
            o = max(0, min(w, y["t_ms"]) - max(u, fin))
            if o > 0:
                etats[nom] += o
    print("\n— blancs entre deux bouts d'une même réponse (fin du son → début du suivant ; le silence DANS le son n'y est pas) —")
    resume("blancs", blancs)
    total = sum(etats.values()) or 1
    for nom, w in etats.most_common():
        print(f"  {nom:55s} {w / 1000:6.1f} s  {100 * w / total:3.0f} %")
    print("\n— premier son après ta parole (tours oraux) —")
    for k in ("attente_fin_tour_ms", "transcription_ms", "premier_mot_ms", "voix_ms", "total_ms"):
        resume(f"  {k}", [d[k] for d in diag if d.get("e") == "tour_temps" and a0 <= d["t"] <= a1 and d.get(k, -1) >= 0])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
