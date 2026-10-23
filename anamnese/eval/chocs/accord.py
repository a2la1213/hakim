"""L'accord des deux annotateurs (kappa de Cohen, neutre compris) et la liste des désaccords à trancher.
Usage : .venv/bin/python eval/chocs/accord.py   → eval/data/chocs/desaccords.txt, accord.json
"""
import json
import time
from collections import Counter
from pathlib import Path

D = Path(__file__).resolve().parents[1] / "data" / "chocs"


def lire(prefixe):
    out = {}
    for f in sorted(D.glob(f"annot-{prefixe}-*.jsonl")):
        for l in f.read_text(encoding="utf-8").splitlines():
            try:
                o = json.loads(l)
            except ValueError:
                continue
            if o.get("id"):
                out[o["id"]] = o
    return out


def classe(o):
    if not o:
        return "neutre"
    c = o.get("classe", "neutre")
    if c in ("attaque", "soutien") and not o.get("vise_hakim", True):
        return c + "-hors"
    return c


def kappa(a, b, ids):
    n = len(ids)
    obs = sum(classe(a.get(i)) == classe(b.get(i)) for i in ids) / n
    ca, cb = Counter(classe(a.get(i)) for i in ids), Counter(classe(b.get(i)) for i in ids)
    att = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return round((obs - att) / (1 - att), 3), round(obs, 3)


def main():
    segs = [json.loads(l) for l in (D / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    ids = [s["id"] for s in segs]
    a, b = lire("A"), lire("B")
    inconnus = [i for i in list(a) + list(b) if i not in set(ids)]
    k, obs = kappa(a, b, ids)
    cles = {}
    for nom, x in (("A", a), ("B", b)):
        cles[nom] = Counter(classe(o) for o in x.values())
    # sur les seules classes qui comptent pour les chocs : attaque / soutien qui visent Hakim, intensité ≥ 2
    def cle(o):
        return classe(o) if classe(o) in ("attaque", "soutien") and int(o.get("intensite", 0)) >= 2 else "autre"
    k_cle, obs_cle = kappa({i: {"classe": cle(a.get(i)) if a.get(i) else "autre"} for i in ids},
                           {i: {"classe": cle(b.get(i)) if b.get(i) else "autre"} for i in ids}, ids)
    par = {s["id"]: s for s in segs}
    lignes, accords = [], []
    for i in ids:
        ca, cb = classe(a.get(i)), classe(b.get(i))
        if ca == "neutre" and cb == "neutre":
            continue
        ia, ib = (a.get(i) or {}).get("intensite"), (b.get(i) or {}).get("intensite")
        if ca == cb and ca in ("attaque", "soutien") and (ia or 0) >= 2 and (ib or 0) >= 2:
            accords.append(i)
        if ca != cb or (ca in ("attaque", "soutien") and ((ia or 0) >= 2) != ((ib or 0) >= 2)):
            s = par[i]
            lignes.append(f"[{i}] {time.strftime('%d/%m %H:%M', time.localtime(s['ts']))} — {s['etiquette'] or s['qui']} "
                          f"(système : {s['qui']}{'' if s['qui_sur'] else ', incertain'})\n"
                          f"  A : {ca} {ia} {(a.get(i) or {}).get('auteur_lu', '')} « {(a.get(i) or {}).get('pourquoi', '')} »\n"
                          f"  B : {cb} {ib} {(b.get(i) or {}).get('auteur_lu', '')} « {(b.get(i) or {}).get('pourquoi', '')} »\n"
                          f"  {s['texte'][:700]}\n")
    (D / "desaccords.txt").write_text("\n".join(lignes), encoding="utf-8")
    res = {"segments": len(ids), "kappa_toutes_classes": k, "accord_brut": obs, "kappa_cles": k_cle,
           "accord_brut_cles": obs_cle, "classes_A": cles["A"], "classes_B": cles["B"], "desaccords": len(lignes),
           "cles_en_accord": len(accords), "ids_inconnus": inconnus}
    (D / "accord.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
