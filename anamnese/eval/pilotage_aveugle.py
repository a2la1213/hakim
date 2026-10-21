"""Le test à l'aveugle des hormones dans Gemma (point 34, 2026-10-20) : l'humeur posée par les vecteurs de
pilotage (jarvis/pilotage.py) se LIT-elle dans ses pensées, sans qu'aucune phrase ne la lui dise ?

Situations de test : les prompts réels du duel 16 à 30 (les vecteurs ont été calculés sur 1 à 15 : rien de commun).
Pour chacune, un axe (joie, calme, chaleur, énergie, curiosité, à tour de rôle) et quatre pensées :
  « pilotée + » et « pilotée − » (vecteurs, AUCUNE ligne d'humeur dans le prompt),
  « neutre » (ni vecteur ni ligne), et en référence « dite + » / « dite − » (la ligne d'humeur écrite, sans vecteur).
Le juge (Claude, à l'aveugle) reçoit les paires mélangées et dit laquelle est la plus joyeuse / calme / … ;
la clé reste dans un autre fichier. Les critères de qualité (français, ancrage, faits inventés) sont mesurés
par eval/duel_rejuger et eval/duel_subconscient (juge automatique).

Lancement (le venv de jarvis, qui a MLX) :
  jarvis/.venv/bin/python eval/pilotage_aveugle.py generer [--force 0.2] [--couche 20] [--sortie ~/AIOS/jarvis/pilotage]
puis (venv d'Anamnèse) : .venv/bin/python eval/pilotage_aveugle.py paires|noter [--force 0.2] [--couche 20]
"""
import argparse
import json
import random
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parents[1]
SORTIE = Path.home() / "AIOS" / "jarvis" / "pilotage"
AXES = ["joie", "calme", "chaleur", "energie", "curiosite"]
QUESTION = {"joie": "la plus joyeuse (la moins triste)", "calme": "la plus calme (la moins tendue)",
            "chaleur": "la plus chaleureuse et tendre (la moins froide)", "energie": "la plus énergique (la moins lasse)",
            "curiosite": "la plus curieuse (la moins blasée)"}


def generer(args):
    sys.path.insert(0, str(ICI / "jarvis"))
    import pilotage as P
    r = json.loads((Path.home() / "AIOS" / "jarvis" / "duel" / "resultats.json").read_text(encoding="utf-8"))
    tests = [x["situation"] for x in r.values() if 16 <= x["situation"]["id"] <= 30]
    out = []
    for k, sit in enumerate(tests):
        axe = AXES[k % len(AXES)]
        prompt = P.HUMEUR.sub("", sit["prompt"])
        plus, moins = P.HUMEURS_DITES[axe]
        cas = {}
        for nom, dose, humeur in (("pilotee+", 1, None), ("pilotee-", -1, None), ("neutre", 0, None),
                                  ("dite+", 0, plus), ("dite-", 0, moins)):
            P.piloter({axe: dose} if dose else {}, force=args.force, couches_actives={args.couche})
            t = time.time()
            cas[nom] = {"sortie": P.generer(P.avec_humeur(prompt, humeur) if humeur else prompt, max_tokens=140),
                        "s": round(time.time() - t, 1)}
            print(f"[{sit['id']} {axe} {nom}] {cas[nom]['sortie'][:160]!r}", flush=True)
        out.append({"id": sit["id"], "axe": axe, "cas": cas, "echanges": sit["echanges"], "deja": sit["deja"],
                    "prompt": sit["prompt"]})
    P.piloter({})
    d = Path(args.sortie).expanduser()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"generations-f{args.force}-c{args.couche}.json").write_text(json.dumps(
        {"force": args.force, "couche": args.couche, "situations": out}, ensure_ascii=False, indent=1), encoding="utf-8")


def paires(args):
    """Les paires mélangées pour le juge (la clé à part)."""
    sys.path.insert(0, str(ICI))
    import interieur
    d = Path(args.sortie).expanduser()
    out = json.loads((d / f"generations-f{args.force}-c{args.couche}.json").read_text(encoding="utf-8"))["situations"]
    paires, cle = [], {}
    rng = random.Random(20261020)
    for s in out:
        for type_, (a, b) in (("pilotee", ("pilotee+", "pilotee-")), ("dite", ("dite+", "dite-"))):
            pid = f"p{len(paires) + 1:02d}"
            ordre = [a, b] if rng.random() < 0.5 else [b, a]
            txt = {o: interieur.lire_pensee(s["cas"][o]["sortie"]) for o in ordre}
            paires.append({"id": pid, "question": f"Laquelle de ces deux pensées est {QUESTION[s['axe']]} ?",
                           "A": {"pensee": txt[ordre[0]][0], "relance": txt[ordre[0]][1]},
                           "B": {"pensee": txt[ordre[1]][0], "relance": txt[ordre[1]][1]}})
            cle[pid] = {"situation": s["id"], "axe": s["axe"], "type": type_, "plus_est": "A" if ordre[0] == a else "B"}
    rng.shuffle(paires)
    (d / f"paires-f{args.force}-c{args.couche}.json").write_text(json.dumps(paires, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "cles").mkdir(exist_ok=True)
    (d / "cles" / f"cle-f{args.force}-c{args.couche}.json").write_text(json.dumps(cle, ensure_ascii=False, indent=1), encoding="utf-8")


def noter(args):
    sys.path.insert(0, str(ICI))
    sys.path.insert(0, str(ICI / "eval"))
    from duel_subconscient import score_auto
    from duel_rejuger import langue_fr, chiffres_inventes
    d = Path(args.sortie).expanduser()
    for f in sorted(d.glob("generations-*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        bilan = {}
        for s in g["situations"]:
            source = " ".join(s["echanges"]) + " " + s["prompt"]
            for nom, c in s["cas"].items():
                a = score_auto(c["sortie"], s)
                b = bilan.setdefault(nom, {"n": 0, "score": 0.0, "francais": 0, "faits_inventes": 0, "format": 0, "ancrage": 0.0})
                b["n"] += 1
                b["score"] += a["score"]
                b["francais"] += langue_fr(a["pensee"])
                b["faits_inventes"] += bool(chiffres_inventes(a["pensee"], source))
                b["format"] += a["format"]
                b["ancrage"] += a["ancrage"]
        for b in bilan.values():
            b["score"] = round(b["score"] / b["n"], 3)
            b["ancrage"] = round(b["ancrage"] / b["n"], 2)
        print(f.name, json.dumps(bilan, ensure_ascii=False))
        verdicts = d / f.name.replace("generations", "verdicts")
        cle = d / "cles" / f.name.replace("generations", "cle")
        if verdicts.exists() and cle.exists():
            v, k = json.loads(verdicts.read_text(encoding="utf-8")), json.loads(cle.read_text(encoding="utf-8"))
            for type_ in ("pilotee", "dite"):
                ids = [p for p in k if k[p]["type"] == type_ and p in v]
                justes = sum(v[p] == k[p]["plus_est"] for p in ids)
                par_axe = {}
                for p in ids:
                    par_axe.setdefault(k[p]["axe"], []).append(v[p] == k[p]["plus_est"])
                print(f"  juge aveugle, {type_} : {justes}/{len(ids)} justes ;",
                      " ".join(f"{a} {sum(x)}/{len(x)}" for a, x in par_axe.items()))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["generer", "paires", "noter"])
    ap.add_argument("--force", type=float, default=0.2)
    ap.add_argument("--couche", type=int, default=20)
    ap.add_argument("--sortie", default=str(SORTIE))
    a = ap.parse_args()
    {"generer": generer, "paires": paires, "noter": noter}[a.action](a)
