"""Les faux « probleme » de la parole (28/10 ; critères figés dans eval/parole_probleme/criteres.md, avant le code).
Les messages d'Ahmed qui déclenchaient « probleme » avec les règles d'avant, étiquetés à l'aveugle (vrai / materiel / faux),
rejoués avec les règles d'après. Les textes restent dans ~/AIOS/jarvis/bancs/parole-probleme/ (jamais publiés).

    python3 -B eval/parole_probleme/rejeu.py extraire | bilan
"""
import json
import sys
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))
import parole_affect  # noqa: E402

JOURNAL = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
SORTIE = Path.home() / "AIOS" / "jarvis" / "bancs" / "parole-probleme"
TEMOINS = ["c'est cassé", "l'appli est cassée", "ça bug encore ton truc", "c'est casse", "ça marche pas"]


def _probleme(texte):
    return dict(parole_affect.evaluer(texte)).get("probleme", 0.0)


def extraire():
    lot = []
    for l in JOURNAL.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(l)
        except ValueError:
            continue
        if d.get("qui") == "ahmed" and _probleme(d.get("texte", "")):
            lot.append({"id": f"p{len(lot) + 1:03d}", "ts": int(d["ts"]), "texte": d["texte"], "avant": _probleme(d["texte"])})
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "messages.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(lot)} messages")


def bilan():
    import datetime
    lot = json.loads((SORTIE / "messages.json").read_text(encoding="utf-8"))
    etiq = json.loads((SORTIE / "etiquettes.json").read_text(encoding="utf-8"))
    par = {"vrai": [], "materiel": [], "faux": []}
    for m in lot:
        m["apres"] = _probleme(m["texte"])
        par[etiq[m["id"]]].append(m)
    vrais = par["vrai"]
    gardes = [m for m in vrais if m["apres"] == m["avant"]]
    c1 = len(gardes) >= 0.95 * len(vrais)
    c2 = all(_probleme(t) == 0.5 for t in TEMOINS)
    heure = lambda m: datetime.datetime.fromtimestamp(m["ts"] / 1000).strftime("%d/%m %H:%M:%S")
    nuit = {heure(m): m["apres"] for m in lot if heure(m) in ("28/10 01:29:05", "28/10 02:12:48")}
    c3 = nuit.get("28/10 02:12:48") == 0.0 and nuit.get("28/10 01:29:05", 1) <= 0.1
    r = {"n": len(lot), "etiquettes": {k: len(v) for k, v in par.items()},
         "C1": {"gardes": len(gardes), "vrais": len(vrais), "passe": c1,
                "perdus": [(m["id"], heure(m), m["avant"], m["apres"]) for m in vrais if m["apres"] != m["avant"]]},
         "C2": {"temoins": {t: _probleme(t) for t in TEMOINS}, "passe": c2},
         "C3": {"cette_nuit": nuit, "passe": c3},
         "rapporte": {k: {"retires": sum(1 for m in par[k] if m["apres"] == 0), "allégés": sum(1 for m in par[k] if 0 < m["apres"] < m["avant"]),
                          "inchangés": sum(1 for m in par[k] if m["apres"] == m["avant"])} for k in ("faux", "materiel")}}
    (SORTIE / "bilan.json").write_text(json.dumps({**r, "detail": lot}, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(r, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    {"extraire": extraire, "bilan": bilan}[sys.argv[1]]()
