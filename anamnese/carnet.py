"""Les carnets d'honnêteté de Hakim (lot G de la liste du 2026-10-19, points 38, 39 et 41 ; « oui à tous », Ahmed,
2026-10-20).

- PRÉDICTIONS FIGÉES (39, 41) : avant un calcul ou une expérience, Hakim fige sa prédiction et sa CONFIANCE
  (0 à 1) ; l'instant est témoigné dans le journal d'événements chaîné (evenements.py) : on ne peut pas la
  réécrire après coup. Quand le résultat tombe, il la tranche (vraie / fausse). La CALIBRATION se mesure : score de
  Brier, et, par tranche de confiance, la part de prédictions justes (à 80 % de confiance, ~80 % justes ?).
- CARNET D'ERREURS (38) : deux colonnes. « bonne foi » : une erreur faite en croyant bien faire, et sa correction.
  « disquette » (une affirmation lancée sans fondement, un bluff) : cette colonne DOIT RESTER VIDE ; si elle se
  remplit, Ahmed le voit (introspection, bilan de la semaine).
"""
import hashlib
import json
import time
import uuid
from pathlib import Path

import config

PREDICTIONS = config.DATA_DIR / "predictions.jsonl"
ERREURS = config.DATA_DIR / "erreurs.jsonl"
COLONNES = ("bonne_foi", "disquette")


class Refus(Exception):
    pass


def _ajouter(f, o):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps(o, ensure_ascii=False) + "\n")


def _lire(f):
    try:
        return [json.loads(l) for l in Path(f).read_text(encoding="utf-8").splitlines() if l.strip()]
    except (OSError, ValueError):
        return []


def figer(enonce, confiance, echeance="", auteur="hakim", fichier=None):
    enonce = str(enonce or "").strip()
    if len(enonce) < 5:
        raise Refus("énoncé trop court")
    try:
        confiance = float(confiance)
    except (TypeError, ValueError):
        raise Refus("confiance : un nombre entre 0 et 1")
    if not 0.0 <= confiance <= 1.0:
        raise Refus("confiance : un nombre entre 0 et 1")
    p = {"type": "prediction", "id": uuid.uuid4().hex[:10], "ts": time.time(), "enonce": enonce[:2000],
         "confiance": round(confiance, 3), "echeance": str(echeance or "")[:100], "auteur": auteur}
    p["empreinte"] = hashlib.sha256(json.dumps(p, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]
    _ajouter(fichier or PREDICTIONS, p)
    try:                                                     # le témoin : l'instant ne se réécrit pas
        import evenements
        evenements.ajouter("prediction", {"id": p["id"], "empreinte": p["empreinte"], "confiance": p["confiance"]}, source=auteur)
    except Exception:
        pass
    return p


def trancher(pid, juste, note="", fichier=None):
    f = fichier or PREDICTIONS
    tout = _lire(f)
    if not any(x.get("type") == "prediction" and x.get("id") == pid for x in tout):
        raise Refus(f"prédiction inconnue : {pid}")
    if any(x.get("type") == "verdict" and x.get("id") == pid for x in tout):
        raise Refus("déjà tranchée")
    _ajouter(f, {"type": "verdict", "id": pid, "ts": time.time(), "juste": bool(juste), "note": str(note or "")[:1000]})
    try:
        import evenements
        evenements.ajouter("verdict", {"id": pid, "juste": bool(juste)}, source="hakim")
    except Exception:
        pass
    return True


def etat(fichier=None):
    tout = _lire(fichier or PREDICTIONS)
    verdicts = {x["id"]: x for x in tout if x.get("type") == "verdict"}
    preds = [x for x in tout if x.get("type") == "prediction"]
    return [{**p, "verdict": verdicts.get(p["id"])} for p in preds]


def calibration(fichier=None):
    """{n, ouvertes, brier, tranches: [(confiance moyenne, part juste, n)]} sur les prédictions tranchées."""
    ps = etat(fichier)
    t = [p for p in ps if p["verdict"]]
    out = {"n": len(t), "ouvertes": len(ps) - len(t), "brier": None, "tranches": []}
    if not t:
        return out
    out["brier"] = round(sum((p["confiance"] - (1.0 if p["verdict"]["juste"] else 0.0)) ** 2 for p in t) / len(t), 3)
    for k in range(5):                                   # tranches entières : 0,6 ne compte qu'une fois
        x = [p for p in t if min(4, int(round(p["confiance"] * 1000)) // 200) == k]
        if x:
            out["tranches"].append((round(sum(p["confiance"] for p in x) / len(x), 2),
                                    round(sum(p["verdict"]["juste"] for p in x) / len(x), 2), len(x)))
    return out


def noter_erreur(quoi, correction, colonne="bonne_foi", auteur="hakim", fichier=None):
    if colonne not in COLONNES:
        raise Refus("colonne : bonne_foi ou disquette")
    quoi = str(quoi or "").strip()
    if len(quoi) < 5:
        raise Refus("décris l'erreur")
    e = {"id": uuid.uuid4().hex[:10], "ts": time.time(), "colonne": colonne, "quoi": quoi[:1500],
         "correction": str(correction or "")[:1500], "auteur": auteur}
    _ajouter(fichier or ERREURS, e)
    return e


def erreurs(fichier=None):
    return _lire(fichier or ERREURS)


def resume(fichier_p=None, fichier_e=None):
    c = calibration(fichier_p)
    e = erreurs(fichier_e)
    bonne = sum(1 for x in e if x["colonne"] == "bonne_foi")
    disq = sum(1 for x in e if x["colonne"] == "disquette")
    lignes = [f"Prédictions figées : {c['n'] + c['ouvertes']} (tranchées {c['n']}, ouvertes {c['ouvertes']})"
              + (f", score de Brier {c['brier']} (0 = parfait, 0,25 = hasard)" if c["brier"] is not None else "")]
    if c["tranches"]:
        lignes.append("Calibration : " + " ; ".join(f"confiance {a:.0%} → {b:.0%} justes (n={n})" for a, b, n in c["tranches"]))
    lignes.append(f"Carnet d'erreurs : {bonne} de bonne foi ; colonne « disquette » : {disq}" + (" ⚠ (elle doit rester vide)" if disq else " (vide, comme il se doit)"))
    return "\n".join(lignes)
