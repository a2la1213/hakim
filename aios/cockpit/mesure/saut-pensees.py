"""(10/11, agent saut) Ses pensées dites trop tard, en lecture seule : pour chaque pensée que son ribosome a gardée (pistes.jsonl, « garde »),
quand elle a VRAIMENT sonné chez papa (voix-dite.jsonl), et si une pensée plus récente était déjà prête alors qu'elle attendait depuis plus de
« Sauter les morceaux passés » (sauter_passe_s, lu dans audit.jsonl au moment du son). Un morceau qui sonne est rattaché à une pensée quand 80 %
de ses mots y sont, et pas à une réponse écrite de Hakim (conversation.json) qui les contient aussi. Attention : pistes.jsonl ne garde que ses
2 000 dernières lignes, voix-diagnostic.jsonl aussi.
Usage : python3 -I saut-pensees.py 07:35 08:31 [AAAA-MM-JJ] [dossier des journaux]"""
import datetime
import json
import os
import re
import sys
import unicodedata

JARVIS = sys.argv[4] if len(sys.argv) > 4 else os.path.expanduser("~/AIOS/jarvis")


def lignes(f):
    try:
        with open(os.path.join(JARVIS, f), encoding="utf-8") as h:
            for l in h:
                if l.startswith("{"):
                    try:
                        yield json.loads(l)
                    except ValueError:
                        pass
    except OSError:
        return


def mots(s):
    s = unicodedata.normalize("NFD", str(s).lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return [w for w in re.split(r"[^\w]+", s) if len(w) > 1]


def heure(t):
    return datetime.datetime.fromtimestamp(t / 1000).strftime("%H:%M:%S")


def main():
    jour = sys.argv[3] if len(sys.argv) > 3 else datetime.date.today().isoformat()
    a = int(datetime.datetime.fromisoformat(f"{jour} {sys.argv[1]}").timestamp() * 1000)
    b = int(datetime.datetime.fromisoformat(f"{jour} {sys.argv[2]}").timestamp() * 1000)
    pensees = [p for p in lignes("pistes.jsonl") if "ribosome" in p and p.get("garde")]
    if pensees and pensees[0]["t"] > a:
        print(f"(pistes.jsonl commence à {heure(pensees[0]['t'])} : la fenêtre est tronquée)")
    sons = [v for v in lignes("voix-dite.jsonl") if a - 60000 <= v["t_ms"] <= b + 180000]
    try:
        with open(os.path.join(JARVIS, "conversation.json"), encoding="utf-8") as h:
            msgs = json.load(h).get("messages", [])
    except (OSError, ValueError):
        msgs = []
    reponses = [(int(m.get("ts") or m["id"]), set(mots(m.get("texte", "")))) for m in msgs if m.get("qui") == "j"]
    reglages = sorted((x for x in lignes("audit.jsonl") if x.get("action") == "corps:reglages"), key=lambda x: x["ts"])

    def reglage(t, k, d=None):
        v = d
        for x in reglages:
            if x["ts"] > t:
                break
            if k in x:
                v = x[k]
        return v

    for v in sons:
        mv = mots(v["texte"])
        if not mv:
            continue
        rep = any(tr - 120000 <= v["t_ms"] <= tr + 180000 and sum(w in mr for w in mv) / len(mv) >= 0.8 for tr, mr in reponses)
        if rep:
            continue
        best = None
        for i, g in enumerate(pensees):
            if g["t"] - 500 <= v["t_ms"] <= g["t"] + 180000:
                mg = set(mots(g["garde"]))
                if sum(w in mg for w in mv) / len(mv) >= 0.8 and (best is None or g["t"] > pensees[best]["t"]):
                    best = i
        if best is not None:
            pensees[best].setdefault("sons", []).append(v)
    fen = [g for g in pensees if a <= g["t"] < b]
    dites = [g for g in fen if g.get("sons")]
    print(f"{sys.argv[1]}-{sys.argv[2]} : {len(fen)} pensées gardées par son ribosome, {len(dites)} ont sonné "
          f"({sum(1 for g in fen if reglage(g['t'], 'voix_reponse_seule', True))} pendant « sa vraie réponse seulement »)")
    if not dites:
        return
    attentes = sorted((g["sons"][0]["t_ms"] - g["t"]) / 1000 for g in dites)
    print(f"  attente avant le son : médiane {attentes[len(attentes) // 2]:.1f} s, max {attentes[-1]:.1f} s")
    perimees = []
    for g in dites:
        s = g["sons"][0]["t_ms"]
        seuil = (reglage(s, "sauter_passe_s", 3) or 3) * 1000
        plus = [h for h in pensees if g["t"] < h["t"] < s]
        if s - g["t"] >= seuil and plus:
            perimees.append((g, plus, seuil))
    voix = sum((x["sons"][-1]["t_ms"] + x["sons"][-1]["duree_ms"] - x["sons"][0]["t_ms"]) / 1000 for x, _, _ in perimees)
    print(f"  dites alors qu'une plus récente était prête et qu'elles attendaient depuis sauter_passe_s : {len(perimees)} sur {len(dites)} "
          f"({voix:.0f} s de sa voix)")
    for g, plus, seuil in perimees:
        s = g["sons"][0]["t_ms"]
        print(f"   - {heure(g['t'])} « {g['garde'][:60]} » sonne à {heure(s)} ({(s - g['t']) / 1000:.1f} s) ; {len(plus)} plus récente(s), "
              f"la dernière « {plus[-1]['garde'][:40]} » ({heure(plus[-1]['t'])}) ; parole_liee={reglage(s, 'parole_liee')} "
              f"sauter_passe={reglage(s, 'sauter_passe')} ({seuil / 1000:g} s)")
    diag = [x for x in lignes("voix-diagnostic.jsonl") if a <= x.get("t", 0) < b]
    if diag:
        n = lambda e: sum(1 for x in diag if x.get("e") == e)
        groupes = [x.get("morceaux", 1) for x in diag if x.get("e") == "ribosome_dit"]
        print(f"  diagnostic ({heure(diag[0]['t'])}-{heure(diag[-1]['t'])}) : passe_saute {n('passe_saute')}, ribosome_dit {len(groupes)} "
              f"(dont {sum(1 for k in groupes if k > 1)} groupes de 2 à {max(groupes or [1])} morceaux), ribosome_attente {n('ribosome_attente')}")


if __name__ == "__main__":
    main()
