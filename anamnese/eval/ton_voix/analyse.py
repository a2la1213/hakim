"""L'analyse du test du ton (critères figés : eval/ton_voix/criteres.md). Lit les extraits enregistrés par etalonnage.py,
les mesure avec le modèle local, calcule C1 à C4 et la comparaison à l'énergie seule, et écrit
~/AIOS/jarvis/bancs/ton-voix/resultats.json.

    HF_HUB_OFFLINE=1 jarvis/.venv/bin/python -B eval/ton_voix/analyse.py
"""
import json
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
import ton  # noqa: E402
from etalonnage import BANC, CLIPS, plan  # noqa: E402

ANIMES, CALMES = {"joyeux", "tendu"}, {"triste", "pose"}


def energie_db(x):
    return 20 * math.log10(float(np.sqrt(np.mean(x ** 2))) + 1e-9)


def parole_s(x, seuil_db=-45.0, pas=320):
    """La durée des trames de 20 ms au-dessus de -45 dBFS : une estimation de la parole, pas un détecteur."""
    n = len(x) // pas
    if not n:
        return 0.0
    t = x[:n * pas].reshape(n, pas)
    return float(np.sum(20 * np.log10(np.sqrt(np.mean(t ** 2, axis=1)) + 1e-9) > seuil_db)) * pas / ton.TAUX


def critere(nom, pos, neg, seuil, p_max=None):
    a = ton.auc(pos, neg)
    ic = ton.bootstrap_ic(pos, neg)
    p = ton.permutation_p(pos, neg)
    ok = a >= seuil and (p_max is None or p < p_max)
    return {"critere": nom, "auc": round(a, 3), "ic95": [round(ic[0], 3), round(ic[1], 3)], "p": round(p, 4),
            "seuil": seuil, "p_max": p_max, "n": [len(pos), len(neg)], "passe": bool(ok)}


def main():
    mesures, ecartes, calcul = [], [], []
    ton.mesurer(np.zeros(ton.TAUX, dtype=np.float32))          # chargement et premier passage hors du chronomètre (C4)
    for x in plan():
        f = CLIPS / x["fichier"]
        if not f.exists():
            ecartes.append({**x, "raison": "absent"})
            continue
        s = ton.lire_wav(f)
        if parole_s(s) < 1.0:
            ecartes.append({**x, "raison": "moins d'une seconde de parole"})
            continue
        t = time.perf_counter()
        m = ton.mesurer(s)
        calcul.append((time.perf_counter() - t) / (len(s) / ton.TAUX))
        mesures.append({**x, **m, "energie_db": round(energie_db(s), 2), "duree_s": round(len(s) / ton.TAUX, 2)})

    def val(cle, tons, langue=None):
        return [m[cle] for m in mesures if m["ton"] in tons and (langue is None or m["langue"] == langue)]

    res = {
        "C1": critere("éveil : animés contre calmes", val("arousal", ANIMES), val("arousal", CALMES), 0.80, 0.01),
        "C2": critere("valence : joyeux contre triste et tendu", val("valence", {"joyeux"}),
                      val("valence", {"triste", "tendu"}), 0.75, 0.05),
        "C3": critere("éveil en darija seule", val("arousal", ANIMES, "darija"), val("arousal", CALMES, "darija"), 0.75),
        "C3_francais": critere("éveil en français seul (rapporté)", val("arousal", ANIMES, "fr"),
                               val("arousal", CALMES, "fr"), 0.75),
        "energie": critere("énergie seule : animés contre calmes (rapporté)", val("energie_db", ANIMES),
                           val("energie_db", CALMES), 0.80),
    }
    s5 = 5 * max(calcul) if calcul else float("nan")
    res["C4"] = {"critere": "calcul pour 5 s de parole (le pire extrait)", "s": round(s5, 3), "seuil": 0.5,
                 "passe": bool(s5 <= 0.5)}
    res["energie_vs_modele"] = round(res["energie"]["auc"] - res["C1"]["auc"], 3)
    moyennes = {t: {d: round(float(np.mean(val(d, {t}))), 3) for d in ton.DIMENSIONS} for t in ("joyeux", "triste", "tendu", "pose")
                if val("arousal", {t})}
    sortie = {"ts": time.time(), "modele": ton.MODELE, "n": len(mesures), "ecartes": ecartes, "criteres": res,
              "moyennes_par_ton": moyennes, "mesures": mesures}
    (BANC / "resultats.json").write_text(json.dumps(sortie, ensure_ascii=False, indent=1))
    print(json.dumps({"n": len(mesures), "ecartes": len(ecartes), "criteres": res, "moyennes_par_ton": moyennes},
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
