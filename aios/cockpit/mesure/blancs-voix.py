"""(10/11, agent blancs) Les blancs de sa voix sur une fenêtre de temps, en lecture seule : ce qui a VRAIMENT sonné chez papa (voix-dite.jsonl)
et, pour chaque blanc entre deux bouts d'une même réponse, ce que faisait le bout suivant pendant ce blanc (pas encore demandé, chez Azure,
en file derrière d'autres conversions, en conversion au timbre de rap, prêt mais pas encore joué) ; la file des conversions, celles qui n'ont
jamais sonné, et le premier son après ta parole (tour_temps). Attention : voix-diagnostic.jsonl ne garde que ses 2 000 dernières lignes.
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


def main(args):
    jour = datetime.date.fromisoformat(args[2]) if len(args) > 2 else datetime.date.today()
    heure = lambda x: int(datetime.datetime.combine(jour, datetime.time.fromisoformat(x)).timestamp() * 1000)
    a0, a1 = heure(args[0]), heure(args[1])
    marge = 120000
    diag = [d for d in lignes(os.path.join(JARVIS, "voix-diagnostic.jsonl")) if a0 - marge <= d.get("t", 0) <= a1 + marge]
    if diag:
        premier = min(d["t"] for d in diag)
        if premier > a0:
            print(f"(le journal de diagnostic ne commence qu'à {datetime.datetime.fromtimestamp(premier / 1000):%H:%M:%S} : fenêtre raccourcie)")
            a0 = premier
    sons = sorted((d for d in lignes(os.path.join(JARVIS, "voix-dite.jsonl")) if a0 <= d.get("t_ms", 0) <= a1), key=lambda d: d["t_ms"])
    azure = sorted((d for d in diag if d.get("e") == "synthese_azure"), key=lambda d: d["t"])
    conv = sorted((d for d in diag if d.get("e") == "azure_rap"), key=lambda d: d["t"] - d["ms"])
    # chaque conversion avec son appel Azure (la file des conversions suit l'ordre où Azure a fini)
    pris, paires = set(), []
    for c in conv:
        cs = c["t"] - c["ms"]
        k = next((i for i, x in enumerate(azure) if i not in pris and x["t"] <= cs + 50), None)
        x = azure[k] if k is not None and cs - azure[k]["t"] < 60000 else None
        if x is not None:
            pris.add(k)
        paires.append(dict(As=x["t"] - x["ms"] if x else None, Ae=x["t"] if x else None, Cs=cs, Ce=c["t"], car=x["caracteres"] if x else None,
                           audio=c.get("audio_s"), cv=c["ms"], az=x["ms"] if x else None, file=cs - x["t"] if x else None, son=None))
    for s in sons:                                  # le bout sonné et sa synthèse : même longueur, prête avant, la plus récente libre
        n, choix = len(s["texte"]), None
        for p in paires:
            if p["son"] is None and p["car"] is not None and p["Ce"] <= s["t_ms"] + 400 and s["t_ms"] - p["Ce"] < 90000 \
                    and abs(p["car"] - n) <= max(2, 0.1 * n) and (choix is None or p["Ce"] > choix["Ce"]):
                choix = p
        if choix:
            choix["son"] = s
            s["p"] = choix
    print(f"fenêtre {datetime.datetime.fromtimestamp(a0 / 1000):%H:%M:%S} → {datetime.datetime.fromtimestamp(a1 / 1000):%H:%M:%S} · {len(sons)} bouts sonnés "
          f"({sum(1 for s in sons if s.get('p'))} reliés à leur synthèse)")
    fen = [p for p in paires if p["As"] is not None and a0 <= p["Ce"] <= a1]
    print("\n— sa voix de rap (Azure, puis conversion au timbre de rap, une à la fois) —")
    resume("Azure", [p["az"] for p in fen])
    resume("file avant la conversion", [p["file"] for p in fen])
    resume("conversion", [p["cv"] for p in fen])
    jamais = [p for p in fen if p["son"] is None]
    print(f"conversions jamais sonnées : {len(jamais)} / {len(fen)} ({sum(p['cv'] for p in jamais) / 1000:.0f} s de calcul sur {sum(p['cv'] for p in fen) / 1000:.0f} s)")
    rognes = [d for d in diag if d.get("e") == "azure_rap" and a0 <= d["t"] <= a1 and "azure_s" in d and "rendu_s" in d]
    if rognes:
        print(f"silence retiré (depuis le 10/11) : Azure {statistics.median(d['azure_s'] for d in rognes):.2f} s → rendu {statistics.median(d['rendu_s'] for d in rognes):.2f} s en médiane")
    tours = [d["t"] for d in diag if d.get("e") == "tour_temps" and d.get("son")]
    coupures = [d["t"] for d in diag if d.get("e") in ("relance", "coupure_notee", "coupe_net", "reponse_lachee")]
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
            etats["bout suivant sans synthèse reliée (voix gardée)"] += g
            continue
        for nom, u, v in (("pas encore demandé", -1e18, p["As"]), ("chez Azure", p["As"], p["Ae"]), ("en file derrière d'autres conversions", p["Ae"], p["Cs"]),
                          ("en conversion au timbre de rap", p["Cs"], p["Ce"]), (PRET, p["Ce"], 1e18)):
            o = max(0, min(v, y["t_ms"]) - max(u, fin))
            if o > 0:
                etats[nom] += o
    print("\n— blancs entre deux bouts d'une même réponse (fin du son → début du suivant ; le silence DANS le son n'y est pas) —")
    resume("blancs", blancs)
    total = sum(etats.values()) or 1
    for nom, v in etats.most_common():
        print(f"  {nom:55s} {v / 1000:6.1f} s  {100 * v / total:3.0f} %")
    print("\n— premier son après ta parole (tours oraux) —")
    for k in ("attente_fin_tour_ms", "transcription_ms", "premier_mot_ms", "voix_ms", "total_ms"):
        resume(f"  {k}", [d[k] for d in diag if d.get("e") == "tour_temps" and a0 <= d["t"] <= a1 and d.get(k, -1) >= 0])


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1:])
