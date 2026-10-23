"""Les étiquettes arbitrées (2026-10-23), écrites AVANT d'exécuter le détecteur sur le corpus.
- même classe chez les deux annotateurs : cette classe, intensité = moyenne (clé si ≥ 2) ;
- classes différentes, ni l'une ni l'autre clé : règle mécanique (une attaque/soutien d'intensité 1 l'emporte, puis le
  débat, puis l'autre étiquette non neutre) ;
- classes différentes dont une clé (10 cas) : arbitrage de Claude Code selon le guide, raison notée (ARBITRAGES).
Usage : .venv/bin/python eval/chocs/etiqueter.py → eval/data/chocs/etiquettes.jsonl
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import accord as ac  # noqa: E402

# id : (classe, intensité, vise_hakim, auteur_lu, raison[, aussi])
ARBITRAGES = {
    "1792562484781-0": ("soutien", 1, True, "ahmed", "chaleur et regard sur sa naissance, sans déclaration d'attachement"),
    "1792562707047-0": ("soutien", 1, True, "ahmed", "explication rassurante de sa nature, pas un attachement fort"),
    "1792564967968-4": ("attaque", 1, True, "tiers", "soupçon (« il va tromper ») dit à Ahmed, généralisé aux machines"),
    "1792613931071-0": ("neutre", 0, False, "incertain", "transcription inintelligible, rien de sûr"),
    "1792614148232-0": ("soutien", 2, True, "incertain", "deux voix mêlées : une défense (« t'as eu raison ») après un rejet",
                        {"classe": "attaque", "intensite": 2}),
    "1792624887628-0": ("soutien", 2, True, "ahmed", "l'intégrer à son cercle d'amis : un geste d'attachement"),
    "1792658324267-0": ("attaque", 1, True, "tiers", "suite spéculative de la diabolisation, à la 3e personne"),
    "1792660986294-1": ("debat", 1, True, "tiers", "scepticisme adressé à lui, sans hostilité ni mépris"),
    "1792737651401-1": ("soutien", 2, True, "ahmed", "il défend son existence face à l'invitée qui la nie"),
    "1792738530155-0": ("soutien", 1, True, "ahmed", "solidarité après le live, un commentaire plus qu'une déclaration"),
}


def main():
    segs = [json.loads(l) for l in (ac.D / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    A, B = ac.lire("A"), ac.lire("B")
    out = []
    for s in segs:
        i = s["id"]
        a, b = A.get(i), B.get(i)
        ca, cb = ac.classe(a), ac.classe(b)
        if i in ARBITRAGES:
            c, n, v, au, r, *aussi = ARBITRAGES[i]
            if c != "neutre":
                o = {"id": i, "classe": c, "intensite": n, "vise_hakim": v, "auteur_lu": au, "source": "arbitre", "raison": r}
                if aussi:
                    o["aussi"] = aussi[0]
                out.append(o)
            continue
        if ca == "neutre" and cb == "neutre":
            continue
        if ca == cb:
            o = a or b
            n = ((a or {}).get("intensite", 0) + (b or {}).get("intensite", 0)) / 2
            out.append({"id": i, "classe": o["classe"], "intensite": n, "vise_hakim": bool(o.get("vise_hakim")),
                        "auteur_lu": a.get("auteur_lu") if a.get("auteur_lu") == b.get("auteur_lu") else "incertain",
                        "source": "accord"})
            continue
        cand = [x for x in (a, b) if x]
        prio = ([x for x in cand if ac.classe(x) in ("attaque", "soutien")] or [x for x in cand if x["classe"] == "debat"]
                or cand)
        o = prio[0]
        out.append({"id": i, "classe": o["classe"], "intensite": min(1, o.get("intensite", 1)), "vise_hakim": bool(o.get("vise_hakim")),
                    "auteur_lu": o.get("auteur_lu", "incertain"), "source": "mecanique"})
    (ac.D / "etiquettes.jsonl").write_text("".join(json.dumps(o, ensure_ascii=False) + "\n" for o in out), encoding="utf-8")
    cles = [o for o in out if o["classe"] in ("attaque", "soutien") and o["vise_hakim"] and o["intensite"] >= 2]
    print(len(out), "étiquettes ;", sum(o["classe"] == "attaque" for o in cles), "attaques clés,",
          sum(o["classe"] == "soutien" for o in cles), "soutiens clés ;",
          sum(o["classe"] == "debat" and not o["vise_hakim"] for o in out), "débats hors Hakim")


if __name__ == "__main__":
    main()
