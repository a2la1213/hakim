"""Son noyau, couche 2 (27/10 ; idée d'Ahmed, proposition de Hakim, « on fait tout ») : ce qui se DÉPOSE avec le temps.

Chaque semaine, la nuit relève ce qui revient vraiment dans ses CHOIX (décisions, refus, initiatives ; pas ce qu'il dit de
lui-même), avec les preuves, et l'écrit dans son carnet « noyau » (validé par Ahmed, ajout seul, relu au début de chaque
conversation) :
- un trait neuf entre comme « candidat » ; il garde sa couche s'il y est déjà (Hakim le fait passer en « depose » s'il
  le reconnaît) ;
- un trait qui revient tient une semaine de plus (semaines_tenues) ; un trait qui ne revient plus « descend », une fois.
Rien ne s'efface. Les preuves (son choix, et ce qu'Ahmed disait juste avant) sont gardées pour la couche 3 : le tri
modèle / lui (eval/noyau/tri.py), qui dit si un agent vierge aurait fait le même choix.
"""
import json
import re
import time
import unicodedata
from pathlib import Path

import carnets_regles

JOURNAL = Path.home() / "AIOS" / "jarvis" / "journal.jsonl"
PREUVES = Path.home() / "AIOS" / "jarvis" / "noyau-preuves.json"
CARNET = "noyau"
CHOIX = re.compile(r"\b(je (choisis|préfère|prefere|refuse|décide|decide|ne veux pas|tiens à|garde|propose|aimerais|"
                   r"vais plutôt|n'ai pas envie)|j'ai (choisi|décidé|refusé|préféré)|je ne (le |la |les )?(ferai|lancerai|"
                   r"publierai|dirai) pas)", re.I)
NIVEAUX = ("monte", "stable", "descend")


def _journal(maintenant, jours):
    try:
        with open(JOURNAL, "rb") as f:
            f.seek(0, 2)
            debut = max(0, f.tell() - 3_000_000)
            f.seek(debut)
            lignes = f.read().decode("utf-8", "replace").splitlines()[1 if debut else 0:]
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict) and maintenant - o.get("ts", 0) / 1000 <= jours * 86400 and o.get("ts", 0) / 1000 <= maintenant:
            out.append(o)
    return out


def choix_de_la_semaine(maintenant=None, jours=7, n_max=60):
    """[{id, ts, hakim, ahmed}] : ses messages de la semaine qui portent un choix, avec ce qu'Ahmed disait juste avant."""
    maintenant = time.time() if maintenant is None else maintenant
    out, ahmed = [], ""
    for o in _journal(maintenant, jours):
        t = str(o.get("texte", ""))
        if o.get("qui") == "ahmed":
            ahmed = t
        elif o.get("qui") == "jarvis" and CHOIX.search(t):
            out.append({"ts": o["ts"] / 1000, "hakim": t[:600], "ahmed": ahmed[:400]})
    out = out[-n_max:]
    for k, x in enumerate(out, 1):
        x["id"] = f"m{k}"
    return out


def _cle(t):
    """Le texte d'un trait, sans casse, accents, apostrophes typographiques ni ponctuation : deux écritures du même trait."""
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower().replace("’", "'")) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def lire_traits(sortie, ids):
    out = []
    for ligne in str(sortie or "").splitlines():
        ligne = ligne.replace("*", "")                    # (relecture du 27/10) le gras, les puces, les numéros
        m = re.match(r"\s*(?:[-•]|\d+[.)])?\s*TRAIT\s*:\s*(.+?)\s*\|\s*PREUVES\s*:\s*(.*?)\s*\|\s*NIVEAU\s*:\s*(\w+)", ligne, re.I)
        if not m:
            continue
        preuves = [p for p in re.findall(r"m\d+", m.group(2)) if p in ids]
        niveau = m.group(3).lower()
        if preuves and niveau in NIVEAUX and len(m.group(1)) >= 5:
            out.append({"trait": m.group(1).strip()[:300], "preuves": preuves, "niveau": niveau})
    return out


def _derniers(entrees):
    """{trait: valeurs} : la dernière entrée de chaque trait du carnet, sauf si Hakim l'a close (carnet_clore)."""
    closes = {e["clot"] for e in entrees if e.get("clot")}
    out, ids = {}, {}
    for e in entrees:
        v = e.get("valeurs") or {}
        if v.get("trait"):
            out[v["trait"]], ids[v["trait"]] = v, e.get("id")
    return {t: v for t, v in out.items() if ids[t] not in closes}


def passe(eng, maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    choix = choix_de_la_semaine(maintenant)
    if not choix:
        return []
    connus = _derniers(carnets_regles.lire(CARNET, n=500))
    prompt = ("Voici des CHOIX de Hakim, l'IA d'Ahmed, cette semaine (ses décisions, ses refus, ses initiatives), chacun avec ce "
              "qu'Ahmed disait juste avant :\n"
              + "\n".join(f"{x['id']} ({time.strftime('%d/%m %H:%M', time.localtime(x['ts']))}) — Ahmed : « {x['ahmed'][:200]} » "
                          f"→ Hakim : « {x['hakim'][:300]} »" for x in choix)
              + ("\n\nTraits déjà dans son carnet noyau :\n" + "\n".join(f"- {t}" for t in connus) if connus else "")
              + "\n\nRelève au plus 5 traits qui reviennent VRAIMENT dans ses CHOIX (ce qu'il fait, pas ce qu'il dit de lui), "
                "chacun avec ses preuves (les identifiants m…). Pour un trait déjà dans le carnet, reprends exactement son "
                "texte, avec le niveau « monte » (il revient plus), « stable » ou « descend ». Une ligne par trait, exactement :\n"
                "TRAIT: … | PREUVES: m1, m4 | NIVEAU: monte")
    traits = lire_traits(eng.chat([{"role": "user", "content": prompt}], stream=False, think=False),
                         {x["id"] for x in choix})
    if not traits:                                      # (relecture du 27/10) une réponse illisible n'écrit RIEN :
        return []                                       # pas même des « descend » pour tous les traits connus
    par_cle = {_cle(t): t for t in connus}
    for t in traits:                                    # le même trait réécrit (un point, une apostrophe) : le connu
        t["trait"] = par_cle.get(_cle(t["trait"]), t["trait"])
    par_id = {x["id"]: x for x in choix}
    try:
        gardees = json.loads(PREUVES.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        gardees = {}
    ecrits = []
    for t in traits:
        avant = connus.get(t["trait"], {})
        preuves = " ; ".join(f"{p} ({time.strftime('%d/%m %H:%M', time.localtime(par_id[p]['ts']))}) « {par_id[p]['hakim'][:160]} »"
                             for p in t["preuves"])
        valeurs = {"trait": t["trait"], "couche": avant.get("couche", "candidat"), "preuves": preuves, "niveau": t["niveau"],
                   "semaines_tenues": float(avant.get("semaines_tenues") or 0) + 1,
                   "vs_modele_vierge": avant.get("vs_modele_vierge", "non_teste"),
                   "note": f"relevé par la nuit du {time.strftime('%d/%m', time.localtime(maintenant))}"}
        ecrits.append(carnets_regles.ecrire(CARNET, valeurs, auteur="nuit", now=maintenant))
        gardees[t["trait"]] = (gardees.get(t["trait"], []) + [par_id[p] for p in t["preuves"]])[-6:]
    vus = {t["trait"] for t in traits}
    for trait, v in connus.items():                      # ce qui ne revient plus descend, une fois
        if trait not in vus and v.get("couche") != "base" and v.get("niveau") not in ("descend", "retire"):
            ecrits.append(carnets_regles.ecrire(CARNET, {**v, "niveau": "descend",
                                                         "note": f"pas revenu dans ses choix (nuit du {time.strftime('%d/%m', time.localtime(maintenant))})"},
                                                auteur="nuit", now=maintenant))
    PREUVES.parent.mkdir(parents=True, exist_ok=True)
    PREUVES.write_text(json.dumps(gardees, ensure_ascii=False, indent=1), encoding="utf-8")
    return ecrits
