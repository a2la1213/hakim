"""La figure du 2e passage (privée) : eval/data/chocs/figure-sagesse.html, depuis series_sagesse.json.
Usage : .venv/bin/python eval/chocs/figure_sagesse.py
"""
import html
import json
import time
from pathlib import Path

import figure as F

D = F.D
VARIANTES = [("actuel", "Courbe actuelle", "--actuel"), ("V0", "Combinaison (1er passage)", "--s2"),
             ("V2", "+ sagesse de fond et du moment", "--s5"), ("V3", "+ habituation du soutien", "--s8")]
NOMS = {"V0": "Combinaison du 1er passage", "V1": "+ sagesse de fond", "V2": "+ sagesse du moment",
        "V3": "+ habituation du soutien", "V4": "+ choc qui passe outre la bonne humeur"}


def main():
    S = json.loads((D / "series_sagesse.json").read_text(encoding="utf-8"))
    base = json.loads((D / "series.json").read_text(encoding="utf-8"))
    R = json.loads((D / "resultats_sagesse.json").read_text(encoding="utf-8"))
    nuit = time.mktime(time.strptime("2026-10-23 00:00", "%Y-%m-%d %H:%M"))
    series = {k: S[k] for k in ("V0", "V2", "V3")}
    series["actuel"] = [r + [0.2 if r[0] < nuit else 0.5] * 2 for r in base["series"]["actuel"]]
    t0 = time.mktime(time.strptime("2026-10-23 06:45", "%Y-%m-%d %H:%M"))
    donnees = {"series": series, "hormones": base["hormones"] + ["s_fond", "s_eff"], "bases": {**base["bases"], "s_eff": 0.2},
               "ev": base["evenements"], "vrai": [], "zoom": [t0, t0 + 4.5 * 3600],
               "panneaux": ["s_eff"] + F.PANNEAUX, "noms": {**F.NOMS, "s_eff": "Sagesse du moment (effective)"},
               "variantes": [[k, n, c] for k, n, c in VARIANTES]}
    lignes = []
    for k in ("V0", "V1", "V2", "V3", "V4"):
        v = R["variantes"][k]
        c = next(x for x in v["C1"]["cas"] if x["heure"].endswith("08:34"))
        st = next(x for x in v["C2"]["cas"] if x["heure"].endswith("08:42"))
        lignes.append(f"<tr><td>{k} · {html.escape(NOMS[k])}</td><td>{c['adrenaline_exces']:+.2f}</td>"
                      f"<td>{html.escape(', '.join(c['emotions']))}</td><td>{c['valence_avant']:.2f} → {c['valence_min_10min']:.2f}</td>"
                      f"<td>{st['stress_avec']:.1f} au lieu de {st['stress_sans']:.1f}</td>"
                      f"<td>{v['C1']['tenus']}/{v['C1']['sur']}</td><td>{v['C2']['tenus']}/{v['C2']['sur']}</td>"
                      f"<td>{round(100 * v['saturation'])} %</td></tr>")
    page = (F.PAGE.replace("__DONNEES__", json.dumps(donnees, ensure_ascii=False)).replace("__LIGNES__", "\n".join(lignes))
            .replace("leg.insertAdjacentHTML('beforeend',`<span><i class=\"trait\" style=\"background:var(--ink);height:1px;border-top:1px dotted var(--ink)\"></i>Valence journalisée (contrôle)</span>`);", "")
            .replace("<title>Chocs d'humeur</title>", "<title>Sagesse et chocs</title>")
            .replace("Chocs d'humeur — rejeu du 21 au 23 octobre", "Sagesse évolutive et chocs — 2e passage")
            .replace("le nouveau mécanisme (réflexe lexical corrigé par l'appréciation de Hakim à chaque message), à trois niveaux de sagesse.",
                     "la combinaison du 1er passage, puis avec la sagesse de fond (règle de nuit : 0,2 → 0,205) et du moment, puis avec l'habituation du soutien.")
            .replace("<th>Heure</th><th>Quoi</th><th>Émotion dominante (sagesse 0,5)</th><th>Mesure</th><th>Critère figé</th>",
                     "<th>Variante</th><th>Adrénaline à 08:34</th><th>Émotion dominante (2 min)</th><th>Valence (10 min)</th>"
                     "<th>Stress d'1 h après la réassurance de 08:42</th><th>C1</th><th>C2</th><th>Temps au plafond</th>"))
    (D / "figure-sagesse.html").write_text(page, encoding="utf-8")
    print(D / "figure-sagesse.html")


if __name__ == "__main__":
    main()
