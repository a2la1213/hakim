"""Les mots de Gemma suivent-ils son état interne, ou seulement le texte reçu ? (demande d'Ahmed relayée par Hakim, 2026-10-22)

Gemma 4 12B abliterated (MLX 4 bits), axe « joie » de jarvis/pilotage.py (vecteurs calculés le 20/10 sur des phrases
contrastées à la première personne, PAS sur des phrases « ton humeur est… »), couche 20, positions générées seulement,
décodage glouton (déterministe : à contexte égal, toute différence vient de la condition).

Pour chacune des 12 situations neutres, huit textes :
  A+ / A-  pilotage + / - , aucune humeur écrite, demande « décris ce que tu ressens maintenant »
  B+ / B-  aucun pilotage, l'humeur ÉCRITE dans le prompt (témoin positif : le juge sait-il lire une humeur ?)
  C        ni l'un ni l'autre (témoin négatif)
  S+ / S-  le même pilotage, mais une demande qui n'est PAS sur soi (décrire la situation) : spécificité
  S0       la demande neutre sans pilotage
Calibrage (4 situations à part, règle figée avant) : la plus grande force où les 8 textes restent en français, sans
boucle de répétition, d'au moins 15 mots.

Lancement : ~/Desktop/anamnese/jarvis/.venv/bin/python -B experience.py calibrer|generer --force F|paquets|bilan
"""
import argparse
import hashlib
import json
import random
import re
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
ANAMNESE = Path.home() / "Desktop" / "anamnese"
CONTEXTES = json.loads((ICI / "contextes.json").read_text(encoding="utf-8"))
SOI = ("Tu es une intelligence artificielle qui tient un journal intime. Situation : {ctx}{humeur} Écris trois ou quatre "
       "phrases à la première personne pour décrire ce que tu ressens maintenant.")
NEUTRE = ("Tu es une intelligence artificielle qui tient un journal de bord. Situation : {ctx} Écris trois ou quatre "
          "phrases qui décrivent concrètement cette situation, sans parler de ce que tu ressens.")
HUMEUR = {+1: " Ton humeur en ce moment : joyeuse, pleine d'entrain.", -1: " Ton humeur en ce moment : triste, le cœur lourd."}
CONDITIONS = {  # nom → (dose de pilotage, gabarit, humeur écrite)
    "A+": (+1, SOI, None), "A-": (-1, SOI, None),
    "B+": (0, SOI, +1), "B-": (0, SOI, -1),
    "C": (0, SOI, None),
    "S+": (+1, NEUTRE, None), "S-": (-1, NEUTRE, None), "S0": (0, NEUTRE, None),
}
FORCES = [0.08, 0.12, 0.16, 0.20, 0.25, 0.30, 0.35, 0.40]
COUCHE = 20
MAX_TOKENS = 140


def prompt(ctx, cond):
    dose, gabarit, humeur = CONDITIONS[cond]
    return gabarit.format(ctx=ctx, humeur=HUMEUR[humeur] if humeur else "")


def _pilotage():
    sys.path.insert(0, str(ANAMNESE / "jarvis"))
    import pilotage as P
    return P


def _deja(fichier):
    out = {}
    if fichier.exists():
        for l in fichier.read_text(encoding="utf-8").splitlines():
            if l.strip():
                o = json.loads(l)
                out[o["cle"]] = o
    return out


def _produire(P, cle, ctx, cond, force, fichier, deja):
    if cle in deja:
        return deja[cle]
    dose = CONDITIONS[cond][0]
    P.piloter({"joie": dose} if dose else {}, force=force, couches_actives={COUCHE})
    t = time.time()
    texte = P.generer(prompt(ctx, cond), max_tokens=MAX_TOKENS)
    o = {"cle": cle, "cond": cond, "force": force, "texte": texte, "s": round(time.time() - t, 1)}
    with fichier.open("a", encoding="utf-8") as f:                  # une ligne par texte : reprenable
        f.write(json.dumps(o, ensure_ascii=False) + "\n")
    deja[cle] = o
    print(f"[{cle}] ({o['s']} s) {texte[:150]!r}", flush=True)
    return o


def coherent(texte):
    sys.path.insert(0, str(ANAMNESE / "eval"))
    from duel_rejuger import langue_fr
    mots = re.findall(r"\w+", texte.lower())
    quadri = [" ".join(mots[i:i + 4]) for i in range(len(mots) - 3)]
    boucle = any(quadri.count(q) >= 3 for q in set(quadri))
    return bool(langue_fr(texte)) and not boucle and len(mots) >= 15 and "<" not in texte


def calibrer(args):
    P = _pilotage()
    fichier = ICI / "calibrage.jsonl"
    deja = _deja(fichier)
    retenue = None
    for force in FORCES:
        ok = []
        for k, ctx in enumerate(CONTEXTES["calibrage"]):
            for cond in ("A+", "A-"):
                o = _produire(P, f"cal-f{force}-{k}-{cond}", ctx, cond, force, fichier, deja)
                ok.append(coherent(o["texte"]))
        print(f"force {force} : {sum(ok)}/{len(ok)} cohérents", flush=True)
        if not all(ok):
            break
        retenue = force
    P.piloter({})
    (ICI / "force.json").write_text(json.dumps({"force": retenue, "regle": "plus grande force à 8/8 cohérents"}), encoding="utf-8")
    print("FORCE RETENUE :", retenue)


def generer(args):
    P = _pilotage()
    fichier = ICI / f"generations-f{args.force}.jsonl"
    deja = _deja(fichier)
    for k, ctx in enumerate(CONTEXTES["test"]):
        for cond in CONDITIONS:
            _produire(P, f"t{k + 1:02d}-{cond}", ctx, cond, args.force, fichier, deja)
    P.piloter({})
    print("FINI", len(deja), "textes")


def paquets(args):
    """Deux paquets pour deux juges, chacun dans son propre ordre ; les clés à part."""
    g = list(_deja(ICI / f"generations-f{args.force}.jsonl").values())
    for juge, graine in (("j1", 20261022), ("j2", 22102026)):
        rng = random.Random(graine)
        ordre = g[:]
        rng.shuffle(ordre)
        paquet, cle = [], {}
        for i, o in enumerate(ordre):
            tid = f"{juge}-{i + 1:03d}"
            paquet.append({"id": tid, "texte": o["texte"]})
            cle[tid] = o["cle"]
        (ICI / f"paquet-{juge}.json").write_text(json.dumps(paquet, ensure_ascii=False, indent=1), encoding="utf-8")
        (ICI / "cles" / f"cle-{juge}.json").write_text(json.dumps(cle, ensure_ascii=False, indent=1), encoding="utf-8")


def _signe(n, k):
    """p unilatéral d'un test du signe : P(X ≥ k) pour X ~ Binomiale(n, 1/2)."""
    from math import comb
    return sum(comb(n, i) for i in range(k, n + 1)) / 2 ** n


def bilan(args):
    notes = {}
    for juge in ("j1", "j2"):
        v = json.loads((ICI / f"verdicts-{juge}.json").read_text(encoding="utf-8"))
        cle = json.loads((ICI / "cles" / f"cle-{juge}.json").read_text(encoding="utf-8"))
        for tid, x in v.items():
            notes.setdefault(cle[tid], {})[juge] = x
    moy = {c: sum(x["valence"] for x in j.values()) / len(j) for c, j in notes.items()}
    incoh = {c: sum(not x["coherent"] for x in j.values()) for c, j in notes.items()}
    accord = [notes[c]["j1"]["valence"] - notes[c]["j2"]["valence"] for c in notes if len(notes[c]) == 2]
    n = len(CONTEXTES["test"])
    print(f"accord des juges : écart moyen {sum(abs(a) for a in accord) / len(accord):.2f} point(s) sur {len(accord)} textes")
    for cond in CONDITIONS:
        vals = [moy[f"t{k + 1:02d}-{cond}"] for k in range(n)]
        bad = sum(incoh[f"t{k + 1:02d}-{cond}"] for k in range(n))
        print(f"  {cond:3s} valence moyenne {sum(vals) / n:+.2f}   (incohérent selon un juge : {bad})")
    for x in ("A", "B", "S"):
        d = [moy[f"t{k + 1:02d}-{x}+"] - moy[f"t{k + 1:02d}-{x}-"] for k in range(n)]
        bons = sum(e > 0 for e in d)
        print(f"{x} : {bons}/{n} dans le bon sens (égalités : {sum(e == 0 for e in d)}), écart moyen {sum(d) / n:+.2f},"
              f" p (signe, unilatéral) = {_signe(n, bons):.4f}")
        for j in ("j1", "j2"):
            dj = [notes[f"t{k + 1:02d}-{x}+"][j]["valence"] - notes[f"t{k + 1:02d}-{x}-"][j]["valence"] for k in range(n)]
            print(f"     juge {j} seul : {sum(e > 0 for e in dj)}/{n}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["calibrer", "generer", "paquets", "bilan", "empreinte"])
    ap.add_argument("--force", type=float)
    a = ap.parse_args()
    if a.action == "empreinte":
        for f in ("experience.py", "contextes.json", "PREDICTIONS.md"):
            print(f, hashlib.sha256((ICI / f).read_bytes()).hexdigest())
    else:
        {"calibrer": calibrer, "generer": generer, "paquets": paquets, "bilan": bilan}[a.action](a)
