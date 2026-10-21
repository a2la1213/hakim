"""Réglage du rappel automatique (rappel.py) sur une COPIE de la vraie mémoire : pour les 35 requêtes-vérité, la part
des souvenirs attendus que le balayage retrouve (dans les 30 candidats, puis dans la liste courte de 8 au-dessus du
seuil), sens seul contre sens + mots-clés ; et, pour des messages banals (« ok », « merci »…), combien de lignes
arrivent quand même (le bruit). Usage : .venv/bin/python eval/rappel_auto.py"""
import json
import os
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import affect_v2_memoire as M  # noqa: E402  (copie de la base, requêtes-vérité)
import rappel  # noqa: E402
from memory import Memory  # noqa: E402

BANALS = ["ok", "merci frero", "ça marche", "salut", "d'accord on fait comme ça", "barakAllahofik", "oui vas-y",
          "tu peux répéter ?", "c'est parfait", "bonne nuit"]


def main():
    with tempfile.TemporaryDirectory(dir=os.environ.get("TMPDIR")) as d:
        mem = Memory(db_path=M.copie(d))
        qs = [(q, e) for q, e in M.requetes() if e]
        now = time.time() + 30 * 86400            # rien n'est « récent » : on mesure tout le stock
        res = {}
        index = rappel.Index()
        rappel.candidats(mem, "chauffe", now=now, index=index)
        t0 = time.time()
        par_q = []
        for q, e in qs:
            c = rappel.candidats(mem, q, now=now, index=index)
            par_q.append((e, c))
        ms = 1000 * (time.time() - t0) / len(qs)
        cand_banals = [rappel.candidats(mem, b, now=now) for b in BANALS]
        for pm in (5.0, 6.0, 6.5, 7.0, 8.0):
            for ps in (0.55, 0.62, 0.7, 1.1):
                trouves = vus = 0
                for e, c in par_q:
                    liste = [x[0] for x in c if rappel.passe(x, pm, ps)][:rappel.LIGNES_MAX]
                    trouves += len(set(liste) & e) / len(e)
                    vus += len(liste)
                bruit = sum(len([x for x in c if rappel.passe(x, pm, ps)][:rappel.LIGNES_MAX]) for c in cand_banals) / len(BANALS)
                res[f"mots ≥ {pm} ou sens ≥ {ps}"] = {"rappel@8": round(trouves / len(qs), 3), "lignes_moy": round(vus / len(qs), 1),
                                                      "bruit_banals": round(bruit, 1)}
        large = sum(len({x[0] for x in c} & e) / len(e) for e, c in par_q) / len(qs)
        bruit = None
        mem.db.close()
    print(json.dumps({"requetes": len(qs), "ms_par_message": round(ms), "rappel@30_large": round(large, 3),
                      "grille": res}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
