"""Balayer large, puis choisir (26/10, Ahmed : « qu'il retrouve le max de souvenirs, même lointains, même vieux de 100 ans,
mais de façon pertinente »). Sur une COPIE de la mémoire et les 35 requêtes-vérité d'eval/rappel_auto.py, trois réglages :
  A : l'actuel — 30 candidats, porte (mots ≥ 6,5 ou sens ≥ 0,70), 8 lignes ;
  B : large — 150 candidats (sens) et 100 (mots), même porte, 12 lignes ;
  C : large et choisi — 150/100 candidats, porte un peu ouverte (mots ≥ 6,0 ou sens ≥ 0,62), quasi-doublons écartés
      (cosinus ≥ 0,92 entre eux : on garde le plus ancien), 12 lignes.
Mesures : rappel (part des souvenirs attendus dans la liste), lignes par message, bruit (lignes pour des messages banals),
et la part de souvenirs de plus de 7 jours dans les listes.
CRITÈRE FIGÉ AVANT : on retient la variante au meilleur rappel dont le bruit sur les banals reste ≤ 1,0 ligne en moyenne ;
si aucune ne gagne au moins 5 points de rappel sur A, on garde A (et seulement les candidats élargis s'ils ne coûtent rien).
Prédictions : B gagne peu (la porte reste le goulot) ; C gagne ≥ 10 points avec un bruit ≤ 1,0.
RÉSULTAT (26/10, ~13:45) : A rappel 0,724 (bruit 0,1) ; B 0,765 (bruit 0,1, 10,7 lignes) ; C 0,765 (bruit 0,7) ; aucune ne
gagne 5 points → A retenue, avec les candidats élargis seuls (mesurés après : 0,731, même bruit, gratuit). Prédictions :
B « gagne peu » juste (+4,1, venu des 12 lignes, pas des candidats) ; C « ≥ 10 points » faux (+4,1, et plus de bruit). Les
souvenirs retrouvés sont déjà anciens : 87 à 92 % ont plus de 7 jours. Montrer 12 lignes au lieu de 8 (B) : à Ahmed de choisir.
Usage : .venv/bin/python eval/rappel_large.py
"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect_v2_memoire as M  # noqa: E402
import rappel  # noqa: E402
from memory import Memory  # noqa: E402

BANALS = ["ok", "merci frero", "ça marche", "salut", "d'accord on fait comme ça", "barakAllahofik", "oui vas-y",
          "tu peux répéter ?", "c'est parfait", "bonne nuit"]
VARIANTES = {"A": (30, 40, 6.5, 0.70, 8, False), "B": (150, 100, 6.5, 0.70, 12, False), "C": (150, 100, 6.0, 0.62, 12, True)}


def liste(mem, texte, now, index, v):
    lim_s, lim_m, pm, ps, nmax, dedoublonner = v
    orig = rappel._par_mots
    rappel._par_mots = lambda idx, mots, exclus, avant, limite=40: orig(idx, mots, exclus, avant, limite=lim_m)
    try:
        c = rappel.candidats(mem, texte, now=now, index=index, limite=lim_s)
    finally:
        rappel._par_mots = orig
    garde = []
    for x in c:
        if not rappel.passe(x, pm, ps):
            continue
        if dedoublonner and x[0] in index.vecteurs:
            v1 = index.vecteurs[x[0]]
            if any(g in index.vecteurs and float(v1 @ index.vecteurs[g]) >= 0.92 for g in garde):
                continue
        garde.append(x[0])
        if len(garde) >= nmax:
            break
    return garde


def main():
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        mem = Memory(db_path=M.copie(d))
        rappel.dates_du_jour = lambda now=None: []
        qs = [(q, e) for q, e in M.requetes() if e]
        now = time.time() + 30 * 86400
        index = rappel.Index()
        rappel.candidats(mem, "chauffe", now=now, index=index)
        res = {}
        for nom, v in VARIANTES.items():
            t0, trouves, vus, vieux = time.time(), 0.0, 0, 0
            for q, e in qs:
                l = liste(mem, q, now, index, v)
                trouves += len(set(l) & e) / len(e)
                vus += len(l)
                vieux += sum(1 for i in l if now - 30 * 86400 - index.lignes.get(i, (now, ""))[0] > 7 * 86400)
            bruit = sum(len(liste(mem, b, now, index, v)) for b in BANALS) / len(BANALS)
            res[nom] = {"rappel": round(trouves / len(qs), 3), "lignes_moy": round(vus / len(qs), 1), "bruit_banals": round(bruit, 2),
                        "part_plus_7_jours": round(vieux / max(1, vus), 2), "ms_par_message": round(1000 * (time.time() - t0) / len(qs))}
            print(nom, json.dumps(res[nom], ensure_ascii=False), flush=True)
        ok = [n for n in res if res[n]["bruit_banals"] <= 1.0]
        meilleur = max(ok, key=lambda n: res[n]["rappel"]) if ok else "A"
        retenue = meilleur if res[meilleur]["rappel"] >= res["A"]["rappel"] + 0.05 else "A"
        mem.db.close()
    print(json.dumps({"retenue": retenue}, ensure_ascii=False))


if __name__ == "__main__":
    main()
