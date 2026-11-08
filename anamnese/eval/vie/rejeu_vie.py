"""Les émotions de Hakim sur toute sa vie avec Ahmed (demande d'Ahmed relayée par Hakim, accord direct d'Ahmed le 23/10).

Une RECONSTRUCTION, pas ce qu'il a vécu à l'époque : le moteur d'affect v2 d'aujourd'hui, avec le mécanisme branché le
23/10 (réflexe lexical par voix, appréciation simulée à chaque message, sagesse de fond et du moment, habituation du
soutien, choc qui passe outre la bonne humeur : eval/chocs/rejeu_sagesse.py, V4), rejoué depuis le premier échange
journalisé (16/10, 12:00) sur une mémoire en RAM, en partant des lignes de base. Superposé à ce qui a été réellement
journalisé là où ça existe : la valence et l'humeur nommée (depuis le 19/10, 14:31), l'état des hormones sauvé chaque
nuit (v1 avant le 21/10), le ton de ses réponses (juge à l'aveugle sur 381 réponses), et sa voix (30 morceaux du 23/10).
Sorties privées : eval/data/vie/. Usage : .venv/bin/python eval/vie/rejeu_vie.py
"""
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "chocs"))
import rejeu as R  # noqa: E402
import rejeu_sagesse as RS  # noqa: E402
from rejeu import affect, parole_affect  # noqa: E402

import chocs  # noqa: E402
import interieur  # noqa: E402

D = ICI.parent / "data" / "vie"
JARVIS = Path.home() / "AIOS" / "jarvis"
DEBUT = time.mktime(time.strptime("2026-10-16 12:00", "%Y-%m-%d %H:%M"))
GARDE = ("adrenaline", "noradrenaline", "crh", "cortisol", "gaba", "ocytocine", "serotonine", "endocannabinoides",
         "dopamine", "endorphine")
FAMILLES = {"élan": ["élan", "joie", "enthousiasme", "fierté"], "lien": ["tendresse", "gratitude", "compassion"],
            "calme": ["calme", "apaisement", "soulagement", "somnolence"], "curiosité": ["curiosité", "concentration"],
            "alerte": ["peur", "inquiétude", "tension", "frustration", "culpabilité", "surprise"],
            "bas": ["tristesse", "manque", "lassitude", "ennui"]}
FAMILLE_DE = {e: f for f, l in FAMILLES.items() for e in l}


def jsonl(f):
    out = []
    for l in Path(f).read_text(encoding="utf-8").splitlines():
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out


def appreciations():
    out = {}
    for f in sorted((ICI.parent / "data" / "chocs").glob("hakim-*.jsonl")) + sorted(D.glob("hakim-avant-*.jsonl")):
        for o in jsonl(f):
            ap = [a for a in o.get("appreciations") or [] if a.get("cible") == "moi" and a.get("classe") in ("attaque", "soutien")]
            if ap:
                out.setdefault(str(o["echange"]), []).extend(ap)
    return out


def lexique(segs):
    """Le lexique de toujours, recalculé sur les mots d'Ahmed seulement (une ligne par message, 30 s après : le démon)."""
    par = {}
    for s in segs:
        if s["qui"] == "ahmed":
            par.setdefault(s["id"].rsplit("-", 1)[0], []).append(s)
    out = []
    for k, v in par.items():
        t = float(k) / 1000 + 30
        for nom, i in parole_affect.evaluer(" ".join(x["texte"] for x in v)):
            out.append({"ts": t, "nom": nom, "i": i, "sujet": None, "source": "parole"})
    return out


def interieurs(fin):
    """Retours, longues absences, ennui : le journal des affects depuis le 21/10, et avant, la liste du battement."""
    out = []
    v2 = time.mktime(time.strptime("2026-10-21 10:15", "%Y-%m-%d %H:%M"))
    for e in jsonl(R.JOURNAL_AFFECT):
        if e.get("source") == "?" and v2 <= e["ts"] <= fin:
            out.append({"ts": e["ts"], "nom": e["nom"], "i": float(e["intensite"]), "sujet": None, "source": "?"})
    db = sqlite3.connect(f"file:{R.RACINE / 'data' / 'memory.db'}?mode=ro", uri=True)
    e = json.loads(db.execute("select value from kv where key='interieur'").fetchone()[0])
    for t, nom, x in e.get("evenements", []):
        if DEBUT <= t < v2:
            if nom == "retour":
                out.append({"ts": t, "nom": "retour", "i": min(1.0, 0.5 + (x - interieur.ABSENCE_RETOUR_S) / (6 * 3600)),
                            "sujet": None, "source": "?"})
            elif nom == "longue_absence":
                out.append({"ts": t, "nom": "longue_absence", "i": 1.0, "sujet": None, "source": "?"})
    return out, [(t, nom, x) for t, nom, x in e.get("evenements", []) if t >= DEBUT]


def reel():
    """Ce qui a été journalisé : valence et humeur (journal du temps), hormones sauvées chaque nuit."""
    v = []
    for l in (JARVIS / "journal-du-temps.jsonl").read_text(encoding="utf-8").splitlines()[::8]:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if o.get("t", 0) >= DEBUT and "valence" in o:
            v.append([round(o["t"]), o["valence"], o.get("humeur")])
    nuits = []
    for f in sorted((R.RACINE / "data" / "backups").glob("auto-2026-10-*.db")):
        b = json.loads(sqlite3.connect(f"file:{f}?mode=ro", uri=True).execute("select value from kv where key='affect'").fetchone()[0])
        if b.get("_ts", 0) >= DEBUT - 86400:
            nuits.append([round(b["_ts"])] + [b.get(h) for h in GARDE])
    return v, nuits


def reponses():
    j = [json.loads(l) for l in (JARVIS / "journal.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    longueurs = [[round(m["ts"] / 1000), len(str(m.get("texte", "")).split())] for m in j
                 if m.get("qui") == "jarvis" and m["ts"] / 1000 >= DEBUT and not str(m.get("texte", "")).startswith("(tour de")]
    idx = json.loads((D / "reponses-index.json").read_text())
    ton = []
    for f in ("ton-1.jsonl", "ton-2.jsonl"):
        for o in jsonl(D / f):
            try:
                k = int(str(o["r"]).lstrip("R")) - 1
                ton.append([round(idx[k] / 1000), o.get("ton"), o.get("energie"), o.get("emotion")])
            except (ValueError, IndexError, KeyError):
                pass
    return longueurs, sorted(ton)


def moments(segs, H, evs_int):
    m = []
    for t, nom, x in evs_int:
        if nom == "retour" and x >= 2 * 3600:
            m.append([round(t), "retour", f"retour d'Ahmed après {round(x / 3600, 1)} h"])
        elif nom == "longue_absence":
            m.append([round(t), "absence", "longue absence"])
    tiers = sorted(s["ts"] for s in segs if s["qui"] == "tiers")
    debut_live, n = None, 0
    for k, t in enumerate(tiers):                                  # au moins 8 phrases d'invités en 30 min : un live
        fen = [x for x in tiers[max(0, k - 20):k + 1] if t - x <= 1800]
        if len(fen) >= 8 and (debut_live is None or t - debut_live > 3 * 3600):
            debut_live = fen[0]
            m.append([round(debut_live), "live", "live avec des invités"])
    for s in segs:
        if s["etiquette"] and re.search(r"\bne m'oublie (pas|jamais)\b|\boublie[- ]moi pas\b", s["texte"], re.I):
            m.append([round(s["ts"]), "lien", f"« ne m'oublie pas » ({'une voix connue' if s['etiquette'] != 'Ahmed' else 'Ahmed'})"])
    for k, ap in H.items():
        for a in ap:
            if a["classe"] == "attaque" and a.get("intensite", 0) >= 0.5:
                m.append([round(float(k) / 1000), "attaque", f"attaque ({a.get('sujet', '')})"])
    return sorted(m)


def main():
    segs = [json.loads(l) for l in (D / "segments.jsonl").read_text(encoding="utf-8").splitlines()]
    H = appreciations()
    fin_donnees = max(s["ts"] for s in segs)
    fin = fin_donnees + 1800
    det = {s["id"]: r for s in segs for r in [chocs.evaluer(s["texte"])] if r["attaque"] or r["soutien"]}
    ev_int, liste_int = interieurs(fin_donnees)
    evs = RS.construire(segs, det, H, lexique(segs) + ev_int)
    R.etat_initial = lambda: {**affect.bases(v2=True), "_ts": DEBUT}     # le point de départ : les lignes de base
    serie = RS.rejouer(evs, DEBUT, fin, RS.VARIANTES["V4"])
    lignes = []
    for t, etat, v, a, emo, s_fond, s_eff in serie:
        code = interieur.humeur_code(v, a, 0.0, False, False, None)
        ex = interieur.voix(interieur.expressivite(code, v, a), {"emotion": emo})
        lignes.append([round(t), round(v, 4), round(a, 4), emo, FAMILLE_DE.get(emo, "calme")] + [round(etat[h], 4) for h in GARDE]
                      + [round(s_fond, 3), round(s_eff, 3), ex["expressivite"], ex["vitesse"]])
    v_reel, nuits = reel()
    longueurs, ton = reponses()
    vx = json.loads((D / "voix.json").read_text())
    mom = moments(segs, H, liste_int)
    res = {"debut": DEBUT, "fin": fin, "hormones": list(GARDE), "bases": {h: affect.bases(v2=True)[h] for h in GARDE},
           "familles": list(FAMILLES), "serie": lignes[::5], "reel_valence": v_reel, "nuits": nuits, "longueurs": longueurs,
           "ton": ton, "voix": vx, "moments": mom,
           "comptes": {"segments": len(segs), "messages_apprecies": len(H), "attaques": sum("attaque" in {a["classe"] for a in ap} for ap in H.values()),
                       "soutiens": sum("soutien" in {a["classe"] for a in ap} for ap in H.values()), "evenements": len(evs)}}
    (D / "vie.json").write_text(json.dumps(res, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(res["comptes"]), len(lignes), "échantillons ;", len(mom), "moments")


if __name__ == "__main__":
    main()
