"""Les erreurs apprises par SITUATION (27/10 ; idée d'Ahmed, proposition de Hakim). Le balayage du carnet d'erreurs suit
les MOTS du message d'Ahmed : une erreur de principe (« No response requested. » à un vrai message, le 22/10, deux fois
le 25/10, le 27/10) ne remontait jamais, parce que le message parlait d'autre chose.

- La nuit range chaque erreur du carnet dans une SITUATION : ce que Hakim était en train de faire (la fin d'un tour, un
  réveil du cockpit, un live avec des invités, citer un chiffre…), avec un déclencheur que le cockpit sait reconnaître
  au début d'un tour : toujours, reveil, oral, plusieurs_voix.
- Deux erreurs ou plus dans une même situation donnent une LEÇON (« dans telle situation, tel choix tourne mal ; fais
  plutôt… »), écrite pour le cockpit dans ~/AIOS/jarvis/lecons-situations.json ; il la rappelle selon ce que Hakim FAIT.
- La mesure : les récidives par situation, avant et après la date de la leçon (eval/erreurs/criteres.md, figé).
"""
import json
import re
import time
import unicodedata
from pathlib import Path

import config

CLASSEMENT = config.DATA_DIR / "erreurs-situations.json"
LECONS = Path.home() / "AIOS" / "jarvis" / "lecons-situations.json"
DECLENCHEURS = ("toujours", "reveil", "oral", "plusieurs_voix")
N_MIN = 2


def _slug(t):
    t = "".join(c for c in unicodedata.normalize("NFD", str(t).lower()) if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:50]


def _lire(f, defaut):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return defaut


def _ecrire(f, o):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + ".tmp")
    tmp.write_text(json.dumps(o, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(f)


def lire_classement(sortie, ids):
    """{id: {slug, libelle, declencheur}} depuis les lignes « id | slug | libellé | déclencheur »."""
    out = {}
    for ligne in str(sortie or "").splitlines():
        p = [x.strip() for x in ligne.replace("**", "").strip().strip("|").split("|")]   # aussi un tableau markdown
        if len(p) < 3 or p[0] not in ids:
            continue
        slug = _slug(p[1])
        if not slug:
            continue
        dec = _slug(p[3]).replace("-", "_") if len(p) > 3 else "toujours"
        out[p[0]] = {"slug": slug, "libelle": p[2][:160], "declencheur": dec if dec in DECLENCHEURS else "toujours"}
    return out


def classer(eng, erreurs, lot=20):
    """Range les erreurs pas encore classées, par lots ; rend le nombre de nouvelles."""
    c = _lire(CLASSEMENT, {})
    neuves = [e for e in erreurs if e.get("id") and e["id"] not in c]
    connues = {}
    for v in c.values():
        connues.setdefault(v["slug"], v["libelle"])
    n = 0
    for i in range(0, len(neuves), lot):
        paquet = neuves[i:i + lot]
        prompt = ("Tu ranges les erreurs de Hakim, l'IA d'Ahmed, par SITUATION : ce qu'il était en train de FAIRE quand "
                  "l'erreur est arrivée (pas le sujet de la conversation). Exemples : la fin d'un tour d'outils, un réveil "
                  "du cockpit sans message d'Ahmed, un live avec des invités, citer un chiffre ou un résultat, annoncer un "
                  "calcul lancé, une transcription orale ambiguë.\n"
                  + ("Situations déjà connues (réutilise-les quand c'est la même) :\n"
                     + "\n".join(f"- {s} : {l}" for s, l in sorted(connues.items())) + "\n" if connues else "")
                  + "Déclencheur : ce que le cockpit voit au début du tour — « toujours », « reveil » (un tour sans message "
                  "d'Ahmed), « oral » (Ahmed parle à voix haute), « plusieurs_voix » (des invités parlent aussi).\n\n"
                  "Erreurs :\n" + "\n".join(f"{e['id']} : {str(e.get('quoi', ''))[:300]} — correction : "
                                            f"{str(e.get('correction', ''))[:150]}" for e in paquet)
                  + "\n\nRéponds par une ligne par erreur, exactement : id | situation-en-mots-courts | la situation en une "
                    "phrase | déclencheur")
        try:
            r = lire_classement(eng.chat([{"role": "user", "content": prompt}], stream=False, think=False),
                                {e["id"] for e in paquet})
        except Exception:
            continue
        for k, v in r.items():
            connues.setdefault(v["slug"], v["libelle"])
        c.update(r)
        n += len(r)
        _ecrire(CLASSEMENT, c)
    return n


def lecons(eng, erreurs, maintenant=None, n_min=N_MIN):
    """Une leçon par situation qui a au moins n_min erreurs ; réécrite seulement si ses erreurs ont changé. Sa date
    (depuis_ts) reste celle de sa première version : c'est d'elle que partent les récidives."""
    maintenant = time.time() if maintenant is None else maintenant
    c = _lire(CLASSEMENT, {})
    avant = {x["slug"]: x for x in (_lire(LECONS, {}) or {}).get("situations", [])}
    groupes = {}
    for e in sorted(erreurs, key=lambda e: e.get("ts", 0)):
        if e.get("id") in c:
            groupes.setdefault(c[e["id"]]["slug"], []).append(e)
    out = []
    for slug, l in sorted(groupes.items()):
        if len(l) < n_min:
            continue
        ids = [e["id"] for e in l]
        ancienne = avant.get(slug)
        if ancienne and ancienne.get("erreurs") == ids:
            out.append(ancienne)
            continue
        prompt = ("Hakim, l'IA d'Ahmed, a fait plusieurs erreurs dans la MÊME situation : "
                  f"{c[ids[0]]['libelle']}.\n" + "\n".join(f"- {str(e.get('quoi', ''))[:300]} (correction : "
                                                           f"{str(e.get('correction', ''))[:150]})" for e in l)
                  + "\n\nÉcris la leçon de principe, pour lui, à la deuxième personne, en une ou deux phrases : dans cette "
                    "situation, quel choix tourne mal, et que faire à la place. Commence par « LEÇON : ».")
        try:
            t = str(eng.chat([{"role": "user", "content": prompt}], stream=False, think=False) or "")
        except Exception:
            t = ""
        m = re.search(r"LE[ÇC]ON\s*:\s*(.+)", t, re.S | re.I)
        regle = re.sub(r"\s+", " ", (m.group(1) if m else t)).strip()[:400]
        if len(regle) < 15:
            if ancienne:
                out.append(ancienne)
            continue
        out.append({"slug": slug, "libelle": c[ids[0]]["libelle"], "declencheur": c[ids[0]]["declencheur"],
                    "regle": regle, "erreurs": ids, "n": len(ids),
                    "depuis_ts": ancienne["depuis_ts"] if ancienne else maintenant})
    _ecrire(LECONS, {"maj_ts": maintenant, "situations": out})
    return out


def recidives(erreurs, classement, lecons_, maintenant=None):
    """Par leçon : les erreurs de sa situation avant et après sa date, et la durée de chaque période (jours)."""
    maintenant = time.time() if maintenant is None else maintenant
    out = []
    for x in lecons_:
        ts = sorted(e["ts"] for e in erreurs if classement.get(e.get("id"), {}).get("slug") == x["slug"])
        if not ts:
            continue
        d = x["depuis_ts"]
        out.append({"slug": x["slug"], "avant": sum(1 for t in ts if t < d), "apres": sum(1 for t in ts if t >= d),
                    "jours_avant": round((d - ts[0]) / 86400, 4), "jours_apres": round((maintenant - d) / 86400, 4)})
    return out


def passe_nuit(eng, maintenant=None):
    """La passe de nuit : ranger les nouvelles erreurs, puis écrire les leçons."""
    import carnet
    e = carnet.erreurs()
    n = classer(eng, e)
    return n, lecons(eng, e, maintenant)
