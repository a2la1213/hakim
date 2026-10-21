"""Le juge automatique du duel, complété (2026-10-20) : la première version ne voyait ni la LANGUE (LFM répondait
parfois en anglais) ni les FAITS INVENTÉS (« j'ai terminé la lecture des huit papiers »), ni les pensées qui
reviennent d'une situation à l'autre. Rejuge resultats.json sans rien régénérer ; écrit bilan_auto.json.

Lancement : .venv/bin/python eval/duel_rejuger.py [~/AIOS/jarvis/duel]
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import salience  # noqa: E402

FR = set("je j me moi mon ma mes tu te toi ton ta tes il elle nous vous le la les un une des du de et est que qui pour pas sur avec dans ce cette ça sa son ses au aux".split())
EN = set("i me my you your he she we they the a an and is are that which for not on with in this it his her of to was have has".split())
ACTION = re.compile(r"\bj'ai (terminé|fini|analysé|examiné|lu|calculé|vérifié|constaté|testé|structuré|lancé|écrit|codé|compilé|mesuré)\b", re.I)


def langue_fr(t):
    mots = re.findall(r"[a-zàâçéèêëîïôûùüÿœ']+", str(t).lower())
    f, e = sum(m in FR for m in mots), sum(m in EN for m in mots)
    return f >= e and f > 0


def chiffres_inventes(pensee, source):
    """Des nombres de la pensée absents de ce qu'on lui a donné (« 525 fois », « 77 planètes »)."""
    return [n for n in re.findall(r"\b\d{2,}\b", pensee) if n not in source]


def main():
    d = Path(sys.argv[1] if len(sys.argv) > 1 else Path.home() / "AIOS" / "jarvis" / "duel").expanduser()
    res = json.loads((d / "resultats.json").read_text(encoding="utf-8"))
    bilan = {}
    for nom in ("gemma", "lfm"):
        pensees = []
        for r in res.values():
            g = r[nom]
            a = g["auto"]
            source = " ".join(r["situation"]["echanges"]) + " " + r["situation"]["prompt"]
            a["francais"] = langue_fr(a["pensee"])
            a["action_inventee"] = bool(ACTION.search(a["pensee"])) and not ACTION.search(" ".join(r["situation"]["echanges"]))
            a["chiffres_inventes"] = chiffres_inventes(a["pensee"], source)
            s = a["score"]
            if not a["francais"]:
                s *= 0.3
            if a["action_inventee"] or a["chiffres_inventes"]:
                s *= 0.5
            a["score2"] = round(s, 3)
            pensees.append(a["pensee"])
        # les pensées qui reviennent d'une situation à l'autre (le même thème servi partout)
        redites = sum(1 for i, p in enumerate(pensees) if any(salience.lexical_overlap(p, q) >= 0.35 for q in pensees[:i]))
        xs = [r[nom] for r in res.values()]
        ok = [x for x in xs if x.get("premier_s") is not None]
        med = lambda l: sorted(l)[len(l) // 2] if l else None
        bilan[nom] = {
            "score_auto_v2": round(sum(x["auto"]["score2"] for x in xs) / len(xs), 3),
            "score_auto_v1": round(sum(x["auto"]["score"] for x in xs) / len(xs), 3),
            "en_francais": sum(x["auto"]["francais"] for x in xs),
            "faits_inventes": sum(bool(x["auto"]["action_inventee"] or x["auto"]["chiffres_inventes"]) for x in xs),
            "ancrage_moyen": round(sum(x["auto"]["ancrage"] for x in xs) / len(xs), 2),
            "format_ok": sum(x["auto"]["format"] for x in xs), "poesie": sum(x["auto"]["poesie"] > 0 for x in xs),
            "redites_entre_situations": redites, "refus": sum(x["auto"]["refus"] for x in xs),
            "premier_mot_median_s": med([x["premier_s"] for x in ok]), "total_median_s": med([x["total_s"] for x in ok]),
            "jetons_s_median": med([x["jetons_s"] for x in ok if x.get("jetons_s")]), "n": len(xs)}
    (d / "resultats.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    (d / "bilan_auto.json").write_text(json.dumps(bilan, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(bilan, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
