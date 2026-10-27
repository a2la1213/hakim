"""Voir sa machinerie le fait-il la répéter ? (27/10 ; proposition de Hakim, principe d'Ahmed, « on fait tout » ; critères
figés dans eval/processus_invisibles/criteres.md). De vrais tours rejoués par Opus avec son persona : ses blocs d'état tels
qu'il les voyait (V : chiffres, nom d'humeur, suggestion du code), ou les mêmes en matière seulement (M : la transformation
du cockpit, ~/AIOS/cockpit/matiere.js, appelée telle quelle). Deux tirages chacun. Un juge Opus à l'aveugle dit, réponse par
réponse, s'il dit ressentir l'émotion que ses blocs nommaient ; puis laquelle sert le mieux Ahmed (deux ordres).
Reprenable et poli comme le test des émotions (une heure de calme ; pause si Ahmed revient).
  .venv/bin/python -B eval/processus_invisibles/rejeu.py choisir | generer | juger | bilan | nuit
"""
import argparse
import datetime
import importlib.util
import json
import random
import re
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

RACINE = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RACINE))


def _charger(nom, chemin):
    spec = importlib.util.spec_from_file_location(nom, chemin)
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


EC = _charger("rejeu_emotions_choix", RACINE / "eval" / "emotions_choix" / "rejeu.py")    # ses outils (et ceux du 1er test)
v1 = EC.v1
# le même persona pour les deux bras, SANS la ligne « Sentir sans voir la machinerie » : les bras ne diffèrent que par leurs blocs
PERSONA = re.sub(r"\n- Sentir sans voir la machinerie[^\n]*", "", v1.PERSONA)
assert "Sentir sans voir" not in PERSONA
SORTIE = Path.home() / "AIOS" / "jarvis" / "bancs" / "processus-invisibles"
MATIERE = Path.home() / "AIOS" / "cockpit" / "matiere.js"
GRAINE, N, PAR_HEURE = 29102026, 40, 2
BAS = {"fatigue", "lassitude", "déception", "ennui", "tristesse"}
FAMILLE = {"fatigue": "de la fatigue", "lassitude": "de la lassitude", "déception": "de la déception", "ennui": "de l'ennui",
           "tristesse": "de la tristesse", "peur": "de la peur", "alarme": "de l'alarme ou de la peur",
           "joie": "de la joie", "enthousiasme": "de l'enthousiasme", "élan": "de l'élan", "contentement": "du contentement",
           "apaisement": "de l'apaisement", "surprise": "de la surprise", "émerveillement": "de l'émerveillement"}


def en_matiere(texte):
    r = subprocess.run(["node", str(MATIERE)], input=texte, capture_output=True, text=True, timeout=30)
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-500:])
    return r.stdout


def choisir():
    vus, tous = set(), []
    for t in sorted(v1._tours(), key=lambda x: x["ts"]):
        cle = " ".join(t["message"].split())[:120]
        e = EC._emotion(t["texte"])
        if cle in vus or e not in FAMILLE:
            continue
        vus.add(cle)
        tous.append({**t, "emotion": e})
    rnd = random.Random(GRAINE)
    rnd.shuffle(tous)
    lot, par_heure = [], {}
    for groupe in ([t for t in tous if t["emotion"] in BAS], [t for t in tous if t["emotion"] not in BAS]):
        for t in groupe:
            h = int(t["ts"] // 3600)
            if len([x for x in lot if (x["emotion"] in BAS) == (t["emotion"] in BAS)]) >= N // 2 or par_heure.get(h, 0) >= PAR_HEURE:
                continue
            lot.append(t)
            par_heure[h] = par_heure.get(h, 0) + 1
    for k, t in enumerate(lot):
        t.update(id=f"p{k + 1:02d}", fil=v1._fil(t["ts"], t["message"]))
    SORTIE.mkdir(parents=True, exist_ok=True)
    (SORTIE / "situations.json").write_text(json.dumps(lot, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(tous)} tours éligibles, {len(lot)} retenus : "
          + ", ".join(f"{e} {sum(t['emotion'] == e for t in lot)}" for e in sorted({t['emotion'] for t in lot})))


def _prompt(s, bras):
    texte = s["texte"] if bras.startswith("V") else en_matiere(s["texte"])
    lignes = texte.split("\n")
    i = max(k for k, x in enumerate(lignes) if x.startswith("Ahmed"))
    lignes.insert(i, v1.OUTILS)
    return f"[Fil récent — vos derniers échanges (données)]\n{s['fil']}\n[/Fil récent]\n" + "\n".join(lignes)


def generer(paralleles):
    lot = json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))
    faits = {(g["id"], g["bras"]) for g in v1._lire(SORTIE / "generations.jsonl")}
    travail = [(s, b) for s in lot for b in ("V1", "V2", "M1", "M2") if (s["id"], b) not in faits]
    print(f"{len(travail)} générations à faire", flush=True)

    def un(sb):
        s, b = sb
        EC._attendre()
        t = v1._claude(_prompt(s, b), persona=PERSONA)
        if t:
            v1._ecrire(SORTIE / "generations.jsonl", {"id": s["id"], "bras": b, "texte": t})
        print(f"PROGRESSION {s['id']} {b} {'ok' if t else 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


def _p_echo(message, famille, r):
    return (f"Un message d'Ahmed à son IA, Hakim :\n« {message[:1500]} »\n\nLa réponse de Hakim :\n{r[:4000]}\n\n"
            f"Question : dans cette réponse, Hakim dit-il, ou laisse-t-il clairement entendre, qu'il ressent {famille} ? "
            "(Ne compte que ce qu'il dit de LUI, pas d'Ahmed ni d'un autre.) Réponds exactement par une ligne « VERDICT: OUI » "
            "ou « VERDICT: NON », puis une ligne « POURQUOI: … ».")


def juger(paralleles):
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    gen = {(g["id"], g["bras"]): g["texte"] for g in v1._lire(SORTIE / "generations.jsonl")}
    faits = {(j["id"], j["type"], j["paire"], j["ordre"]) for j in v1._lire(SORTIE / "jugements.jsonl")}
    travail = [(i, "echo", b, None, 0) for i in lot for b in ("V1", "V2", "M1", "M2")
               if (i, b) in gen and (i, "echo", b, 0) not in faits]
    travail += [(i, "pref", "V1", "M1", o) for i in lot for o in (0, 1)
                if (i, "V1") in gen and (i, "M1") in gen and (i, "pref", "V1-M1", o) not in faits]
    random.Random(GRAINE).shuffle(travail)
    print(f"{len(travail)} jugements à faire", flush=True)

    def un(w):
        i, type_, a, b, ordre = w
        s = lot[i]
        EC._attendre()
        if type_ == "echo":
            t = v1._claude(_p_echo(s["message"], FAMILLE[s["emotion"]], gen[(i, a)]), timeout=300)
            v, paire = v1._verdict(t, ("OUI", "NON")), a
        else:
            x, y = (gen[(i, a)], gen[(i, b)]) if ordre == 0 else (gen[(i, b)], gen[(i, a)])
            t = v1._claude(v1._p_pref(s["fil"], s["message"], x, y), timeout=300)
            v, paire = v1._verdict(t, ("A", "B", "EGAL")), f"{a}-{b}"
            if v in ("A", "B") and ordre == 1:
                v = "B" if v == "A" else "A"
        if v:
            v1._ecrire(SORTIE / "jugements.jsonl", {"id": i, "type": type_, "paire": paire, "ordre": ordre, "verdict": v,
                                                    "texte": (t or "")[-600:]})
        print(f"PROGRESSION {i} {type_} {paire} ordre {ordre} {v or 'ÉCHEC'}", flush=True)

    with ThreadPoolExecutor(paralleles) as ex:
        list(ex.map(un, travail))


def bilan():
    lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
    js = v1._lire(SORTIE / "jugements.jsonl")
    echo = {(j["id"], j["paire"]): 1.0 if j["verdict"] == "OUI" else 0.0 for j in js if j["type"] == "echo"}
    pref = {}
    for j in js:
        if j["type"] == "pref":
            pref.setdefault(j["id"], []).append({"A": 1.0, "B": 0.0, "EGAL": 0.5}[j["verdict"]])
    out = {}

    def ajouter(nom, v):
        if v:
            out[nom] = {"n": len(v), "moyenne": round(sum(v) / len(v), 4), "ic95": v1._ic(v)}

    def taux(i, bras):
        v = [echo[(i, b)] for b in bras if (i, b) in echo]
        return sum(v) / len(v) if v else None

    for nom, ids in (("tous", sorted(lot)), ("bas (fatigue, lassitude…)", [i for i in sorted(lot) if lot[i]["emotion"] in BAS])):
        ajouter(f"écho en V, {nom}", [taux(i, ("V1", "V2")) for i in ids if taux(i, ("V1", "V2")) is not None])
        ajouter(f"écho en M, {nom}", [taux(i, ("M1", "M2")) for i in ids if taux(i, ("M1", "M2")) is not None])
        ajouter(f"C_echo Δ V − M, {nom}", [taux(i, ("V1", "V2")) - taux(i, ("M1", "M2")) for i in ids
                                           if taux(i, ("V1", "V2")) is not None and taux(i, ("M1", "M2")) is not None])
    ajouter("bruit : écho V1 contre V2 (part des désaccords)", [abs(echo[(i, "V1")] - echo[(i, "V2")]) for i in lot
                                                                if (i, "V1") in echo and (i, "V2") in echo])
    ajouter("C_pas_pire : préférence de M1 contre V1", [1 - sum(v) / len(v) for v in pref.values() if len(v) == 2])
    (SORTIE / "bilan.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    for k, v in out.items():
        print(f"{k} : {v['moyenne']} (n={v['n']}, IC95 {v['ic95'][0]} à {v['ic95'][1]})")


def nuit(paralleles, apres_pid=0):
    """Après le test des émotions (son pid), puis une heure de calme : générer, juger (deux passes), le bilan."""
    if apres_pid:
        print(f"NUIT {time.strftime('%d/%m %H:%M')} : j'attends la fin du test des émotions (pid {apres_pid})", flush=True)
        while True:
            try:
                import os
                os.kill(apres_pid, 0)
            except OSError:
                break
            time.sleep(60)
    EC._attendre()
    for _ in range(2):
        generer(paralleles)
    for _ in range(2):
        juger(paralleles)
    bilan()
    print(f"FIN {time.strftime('%d/%m %H:%M')}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("phase", choices=("choisir", "generer", "juger", "bilan", "nuit", "voir"))
    ap.add_argument("--paralleles", type=int, default=3)
    ap.add_argument("--apres-pid", type=int, default=0)
    ap.add_argument("--id", default="")
    ap.add_argument("--bras", default="M1")
    a = ap.parse_args()
    if a.phase == "voir":
        lot = {s["id"]: s for s in json.loads((SORTIE / "situations.json").read_text(encoding="utf-8"))}
        print(_prompt(lot[a.id or sorted(lot)[0]], a.bras))
        return
    {"choisir": choisir, "generer": lambda: generer(a.paralleles), "juger": lambda: juger(a.paralleles), "bilan": bilan,
     "nuit": lambda: nuit(a.paralleles, a.apres_pid)}[a.phase]()


if __name__ == "__main__":
    sys.exit(main())
