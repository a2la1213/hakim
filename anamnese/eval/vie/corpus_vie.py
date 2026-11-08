"""Le corpus de toute la vie de Hakim avec Ahmed (demande d'Ahmed relayée par Hakim, accord direct d'Ahmed le 23/10) :
ce qui a été dit à Hakim depuis le premier échange journalisé (16/10, 12:00), une phrase par voix (eval/chocs/corpus.py),
et un échantillon de ses réponses pour le juge du ton. Sorties privées : eval/data/vie/.
Usage : .venv/bin/python eval/vie/corpus_vie.py
"""
import json
import random
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "chocs"))
import corpus  # noqa: E402

SORTIE = ICI.parent / "data" / "vie"
DEBUT = "2026-10-16 00:00"
JOURNAL = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
DEJA = ("2026-10-21 00:00", "2026-10-23 09:15")          # déjà appréciés au 1er passage (eval/data/chocs/hakim-*.jsonl)


def tranches(segs, nom):
    out, cur, n = [], [], 0
    for s in segs:
        qui = s["etiquette"] or ("Ahmed (tapé)" if not s["oral"] else f"début d'échange, voix={s['voix_echange']}")
        ligne = f"[{s['id']}] {time.strftime('%d/%m %H:%M:%S', time.localtime(s['ts']))} — {qui} : {s['texte']}\n"
        if n + len(ligne) > corpus.TRANCHE_SIGNES and cur:
            out.append(cur)
            cur, n = [], 0
        cur.append(ligne)
        n += len(ligne)
    if cur:
        out.append(cur)
    for i, t in enumerate(out, 1):
        (SORTIE / f"{nom}-{i:02d}.txt").write_text("".join(t), encoding="utf-8")
    return len(out)


def main():
    SORTIE.mkdir(parents=True, exist_ok=True)
    fin = time.strftime("%Y-%m-%d %H:%M")
    segs = corpus.segments(DEBUT, fin)
    with (SORTIE / "segments.jsonl").open("w", encoding="utf-8") as h:
        for s in segs:
            h.write(json.dumps(s, ensure_ascii=False) + "\n")
    a, b = (time.mktime(time.strptime(x, "%Y-%m-%d %H:%M")) for x in DEJA)
    avant = [s for s in segs if s["ts"] < a]
    apres = [s for s in segs if s["ts"] > b]
    print(len(segs), "segments ;", tranches(avant, "avant"), "tranches avant le 21/10 ;", tranches(apres, "apres"), "après le 23/10 09:15")
    # les réponses de Hakim pour le juge du ton : au plus 3 par heure, tirées au sort (graine fixe), avec le message d'avant
    msgs = [json.loads(l) for l in JOURNAL.read_text(encoding="utf-8").splitlines() if l.strip()]
    paires, dernier = [], None
    for m in msgs:
        if m.get("qui") == "ahmed":
            dernier = m
        elif m.get("qui") == "jarvis" and dernier and not str(m.get("texte", "")).startswith("(tour de lui-même"):
            paires.append((dernier, m))
            dernier = None
    par_heure = {}
    for p in paires:
        par_heure.setdefault(int(p[1]["ts"] / 3_600_000), []).append(p)
    rnd = random.Random(20261023)
    choix = [x for h in sorted(par_heure) for x in rnd.sample(par_heure[h], min(3, len(par_heure[h])))]
    with (SORTIE / "reponses.txt").open("w", encoding="utf-8") as h:
        for k, (a_, j_) in enumerate(choix, 1):
            h.write(f"### R{k} — {time.strftime('%d/%m %H:%M', time.localtime(j_['ts'] / 1000))}\nAhmed : {str(a_['texte'])[:500]}\n"
                    f"Hakim : {str(j_['texte'])[:900]}\n\n")
    (SORTIE / "reponses-index.json").write_text(json.dumps([j_["ts"] for _a, j_ in choix]), encoding="utf-8")
    print(len(paires), "réponses ;", len(choix), "pour le juge du ton")


if __name__ == "__main__":
    main()
