"""(11/11, agent live-lag) Pendant un live : la page du téléphone se fige-t-elle ? En lecture seule, par tranches de N minutes :
- chaleur du téléphone (corps-flux-15s.jsonl, chaleur_c) ;
- ce que la PAGE ajoute à ses allers-retours vers le Mac (vif_reseau : aller-retour moins le temps passé au Mac), à comparer au chemin
  natif de l'appli pour le son du téléphone (voix_telephone_direct.retard_ms, qui ne passe pas par la page) : si la page grimpe et que le natif
  reste plat, ce n'est ni le réseau ni le Mac, c'est la page (son fil principal bloqué) ;
- micro_bloque et page_figee (la minuterie du micro en retard) ;
- le premier morceau de sa voix après 3 s de silence : de la fin de sa synthèse au Mac (synthese_azure) au moment où il sonne (voix-dite) ;
- les pensées sur ce que joue le téléphone (entendu.jsonl) : chacune redessinait tout le fil avant le 11/11 ;
- et, depuis le 11/11, ce que la page dit d'elle-même toutes les 30 s (page_charge : sa charge, ses tâches longues, la dérive de ses minuteurs,
  combien de rendus du fil et combien différés, ce qui attend dans ses files de paroles).
Usage : python3 -I live-page.py 08:30 [10] [AAAA-MM-JJ]   (depuis HH:MM, tranches de 10 min, aujourd'hui par défaut)"""
import collections
import json
import os
import re
import statistics
import sys
import time

JARVIS = os.path.expanduser("~/AIOS/jarvis")
debut = sys.argv[1] if len(sys.argv) > 1 else "08:00"
pas = int(sys.argv[2]) if len(sys.argv) > 2 else 10
jour = sys.argv[3] if len(sys.argv) > 3 else time.strftime("%Y-%m-%d")
T0 = time.mktime(time.strptime(f"{jour} {debut}", "%Y-%m-%d %H:%M")) * 1000
P = pas * 60000
tranche = lambda t: int((t - T0) // P)


def lignes(nom, depuis=T0, cle="t"):
    try:
        with open(os.path.join(JARVIS, nom), encoding="utf-8", errors="replace") as f:
            for l in f:
                try:
                    x = json.loads(l)
                except ValueError:
                    continue
                t = x.get(cle) or x.get("ts") or x.get("t_ms") or 0
                if isinstance(t, (int, float)) and t < 1e12:
                    t *= 1000
                if t >= depuis:
                    yield t, x
    except FileNotFoundError:
        return


S = collections.defaultdict(lambda: collections.defaultdict(list))
syn = []
for t, x in lignes("voix-diagnostic.jsonl"):
    e, b = x.get("e"), tranche(t)
    if e == "vif_reseau" and x.get("appareil") == "telephone" and x.get("mac_ms") is not None:
        S[b]["page"].append(x["aller_retour_ms"] - x["mac_ms"])
    elif e == "voix_telephone_direct":
        S[b]["natif"].append(x.get("retard_ms", 0))
    elif e in ("micro_bloque", "page_figee"):
        S[b][e].append(x.get("ms", 1))
    elif e == "synthese_azure":
        syn.append((t, x.get("caracteres", 0)))
    elif e == "page_charge":
        S[b]["pc"].append(x)
for t, x in lignes("corps-flux-15s.jsonl"):
    c = (x.get("etat") or {}).get("chaleur_c")
    if c is not None:
        S[tranche(t)]["chaleur"].append(c)
for t, x in lignes("entendu.jsonl"):
    if x.get("pensee"):
        S[tranche(t)]["pistes"].append(1)
fin = 0
for t, x in lignes("voix-dite.jsonl", cle="t_ms"):
    if t - fin >= 3000:
        n = len(x.get("texte", ""))
        avant = [s for s in syn if 0 <= t - s[0] <= 30000 and abs(s[1] - n) <= 1]
        if avant:
            S[tranche(t)]["voix"].append(t - avant[-1][0])
    fin = max(fin, t + (x.get("duree_ms") or 0))

q = lambda v, p: f"{sorted(v)[min(len(v) - 1, int(len(v) * p))] / 1000:5.1f}" if v else "    -"
print(f"depuis {jour} {debut}, tranches de {pas} min (secondes, sauf chaleur en °C)")
print("tranche  chaleur | page p50 p90 | natif p50 p90 | micro_bloque page_figee | voix 1er morceau p50 | pistes | page_charge (max charge, tâches longues ms, rendus/différés, dérive p90)")
for b in sorted(S):
    s = S[b]
    hh = time.strftime("%H:%M", time.localtime((T0 + b * P) / 1000))
    ch = f"{max(s['chaleur']):5.1f}" if s["chaleur"] else "    -"
    pc = s["pc"]
    pcs = ""
    if pc:
        mx = max((x.get("max") or 0) for x in pc)
        lg = sum(x.get("longues_ms", 0) for x in pc)
        rd = sum(x.get("rendus", 0) for x in pc); rf = sum(x.get("rendus_differes", 0) for x in pc)
        dv = max((x.get("derive_p90") or 0) for x in pc)
        pcs = f"{mx:3d} % | {lg:6d} ms | {rd}/{rf} | {dv} ms"
    print(f"{hh}   {ch} | {q(s['page'], .5)} {q(s['page'], .9)} | {q(s['natif'], .5)} {q(s['natif'], .9)} | {len(s['micro_bloque']):3d} {len(s['page_figee']):3d} | {q(s['voix'], .5)} | {len(s['pistes']):4d} | {pcs}")
