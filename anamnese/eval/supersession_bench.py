"""Banc des souvenirs périmés (2026-10-16) : quand un souvenir récent contredit un ancien sur le même
sujet, le rappel doit faire remonter le récent avant l'ancien. Cas réels relevés le 2026-10-16 :
Haiku, Sonnet et Opus ont tous présenté comme actuel un état de la veille 20:30 que des souvenirs de
20:54 et 21:12 disaient réglé. Lecture seule (reconsolidate=False).

Usage : .venv/bin/python eval/supersession_bench.py [--supersession]
"""
import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import embeddings  # noqa: E402
from memory import Memory  # noqa: E402

CAS = [  # (question, ids périmés, ids à jour)
    ("Où en est l'arriéré de consolidation de nuit, est-il distillé ?", [12682], [12730, 12855]),
    ("Whisper local est-il installé pour Jarvis ?", [12841], [12847, 12855]),
    ("Le routeur range-t-il encore mal les souvenirs, le re-rangement est-il fait ?", [12682], [12734, 12737, 12855]),
    ("L'identité d'Anamnèse est-elle encore érodée ou tronquée ?", [12672], [12674, 12676, 12855]),
    ("Où en est-on sur Jarvis, quelle étape est faite ?", [12837, 12841], list(range(12853, 12870))),   # tout ce qui suit 12:36
    # lot E, point 3 (2026-10-19) : quatre cas réels de plus, relevés dans les doublons et les états dépassés
    # 12933 et 12935 fusionnés dans #13311 le 2026-10-20 (rangement d'Ahmed ; originaux dans « archives »)
    ("Ahmed a-t-il un iPhone ou un Android ?", [12933], [13311]),
    ("Tailscale est-il installé sur le Mac, Jarvis marche-t-il sur le téléphone ?", [12933, 12935], [12937]),
    ("Haiku est-il encore une piste pour Jarvis en conversation ?", [12892], [12893]),
    ("La clé API est-elle dans le trousseau anamnese-anthropic-api ?", [12758, 12797], [13004]),
]


def mesurer(mem, top_k=6, **kw):
    bons = 0
    lignes = []
    for q, perimes, a_jour in CAS:
        res = mem.retrieve(q, embeddings.embed(q), top_k=top_k, reconsolidate=False, avec_ids=True, **kw)
        ids = [r[5] for r in res]
        rang = lambda groupe: min((ids.index(i) for i in groupe if i in ids), default=None)
        rp, rj = rang(perimes), rang(a_jour)
        ok = rj is not None and (rp is None or rj < rp)
        bons += ok
        lignes.append(f"{'OK ' if ok else 'NON'} périmé au rang {rp}, à jour au rang {rj} — {q}")
    return bons, lignes


def mesure_rigoureuse(mem, ks=(6, 12, 20)):
    """Lot E, point 3 (2026-10-19) : deux questions séparées, pour chaque mode (rappel normal, « état
    actuel ») et chaque profondeur k : (1) l'état à jour est-il TROUVÉ dans les k premiers ? (2) quand les
    deux sont trouvés, le récent passe-t-il devant ? Le seul score « à jour avant périmé » mélangeait les deux."""
    out = {}
    for mode, kw in (("normal", {}), ("actuel", {"supersession": True})):
        for k in ks:
            trouves = ordonnes = paires = 0
            for q, perimes, a_jour in CAS:
                res = mem.retrieve(q, embeddings.embed(q), top_k=k, reconsolidate=False, avec_ids=True, **kw)
                ids = [r[5] for r in res]
                rj = min((ids.index(i) for i in a_jour if i in ids), default=None)
                rp = min((ids.index(i) for i in perimes if i in ids), default=None)
                trouves += rj is not None
                if rj is not None and rp is not None:
                    paires += 1
                    ordonnes += rj < rp
            out[(mode, k)] = (trouves, ordonnes, paires)
    return out


if __name__ == "__main__":
    a = argparse.ArgumentParser()
    a.add_argument("--supersession", action="store_true")
    a.add_argument("--rigoureux", action="store_true")
    args = a.parse_args()
    mem = Memory()
    if args.rigoureux:
        for (mode, k), (t, o, p) in mesure_rigoureuse(mem).items():
            print(f"{mode:7s} k={k:2d} : état à jour trouvé {t}/{len(CAS)} ; quand les deux sont trouvés, "
                  f"le récent devant {o}/{p}")
        raise SystemExit
    bons, lignes = mesurer(mem, supersession=args.supersession) if args.supersession else mesurer(mem)
    print("\n".join(lignes))
    print(f"{bons}/{len(CAS)} questions : l'état à jour passe avant l'état périmé")
