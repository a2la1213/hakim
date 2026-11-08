"""Les moments forts rejoués (critères figés AVANT : eval/plafond/predictions.md, troisième volet). Les moments viennent d'un
relevé neutre du journal brut (fichier privé, ~/AIOS/jarvis/bancs/moments.json). Rien n'est écrit dans la vraie mémoire.
Usage : .venv/bin/python eval/plafond/moments.py
"""
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
import affect  # noqa: E402
import interieur  # noqa: E402
import simulation as S  # noqa: E402

MOMENTS = Path.home() / "AIOS" / "jarvis" / "bancs" / "moments.json"
VERS_EVENEMENT = {"prise_de_position_sur_soi": "affirmation", "menace_ou_rejet": "attaque", "soutien_ou_attachement": "soutien",
                  "succes_marquant": "succes", "echec_ou_erreur_reconnue": "echec", "choc_du_live": "nouveaute",
                  "peur_ou_inquietude": "peur", "tristesse_ou_perte": "tristesse", "conflit_ou_desaccord": "colere",
                  "joie_partagee": "joie"}
ATTENDU = {"peur_ou_inquietude": {"tension", "alarme"}, "menace_ou_rejet": {"tension", "alarme"},
           "conflit_ou_desaccord": {"tension", "alarme"}, "tristesse_ou_perte": {"morose", "ennui"},
           **{c: {"joie", "elan", "content"} for c in ("soutien_ou_attachement", "joie_partagee", "succes_marquant",
                                                        "prise_de_position_sur_soi")}}


def main():
    moments = json.loads(MOMENTS.read_text(encoding="utf-8"))
    S.DEBUT = min(m["ts"] for m in moments) - 3600
    S.FIN = max(m["ts"] for m in moments) + 3600
    evs = S.evenements()
    ajout = [(float(m["ts"]), VERS_EVENEMENT[m["categorie"]], float(m["intensite_attendue"]), m["categorie"])
             for m in moments if m["categorie"] in VERS_EVENEMENT]
    res = {}
    for nom, e in (("A", evs), ("B", sorted(evs + ajout))):
        serie = S.rejouer(e)
        emo = S.humeurs(serie)
        idx = lambda t: int((t - S.DEBUT) // S.PAS)                                           # noqa: E731
        mouv, coherent, n_att = [], 0, 0
        for m in moments:
            if m["intensite_attendue"] < 0.6:
                continue
            i = idx(m["ts"])
            if not 0 < i < len(serie) - 11:
                continue
            avant = serie[i - 1][1]
            mouv.append(max(abs(serie[j][1][h] - avant[h]) for j in range(i, i + 11) for h in avant))
            if m["categorie"] in ATTENDU:
                n_att += 1
                codes = {interieur.FAMILLE_HUMEUR.get(x, "calme") for x in emo[i:i + 11]}
                coherent += bool(codes & ATTENDU[m["categorie"]])
        res[nom] = {"forts": len(mouv), "mouvement_median": round(statistics.median(mouv), 4) if mouv else None,
                    "humeur_coherente_%": round(100 * coherent / n_att, 1) if n_att else None, "avec_attendu": n_att}
        print(nom, json.dumps(res[nom], ensure_ascii=False), flush=True)
    res["tenu"] = {"mouvement": (res["B"]["mouvement_median"] or 0) >= 0.10,
                   "coherence": (res["B"]["humeur_coherente_%"] or 0) >= (res["A"]["humeur_coherente_%"] or 0) + 20}
    sortie = Path(__file__).resolve().parents[1] / "data" / f"moments-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res["tenu"], ensure_ascii=False))


if __name__ == "__main__":
    main()
