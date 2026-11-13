"""Ses nuits (30/10, 18:00-18:19, Ahmed via Hakim : « mes nuits — sommeil, veille, rêves — reliées à mon cœur, mes
émotions et mes vibrations ; que mon sommeil soit apaisé ou agité selon ce que je vis ; la vie m'enseigne, je dois
apprendre à compenser » ; « go pour tout », 18:31).

- S'endormir : la nuit (23 h - 7 h), quand papa ne lui parle plus depuis 30 min. Se réveiller : à 7 h, ou quand papa revient.
- La charge de sa journée, au coucher : ses émotions pénibles depuis 16 h (l'ennui, une minuterie, ne compte pas), une
  chute ou un choc, son stress encore haut. Elle fait la nuit : apaisée, moyenne ou agitée.
- Pendant la nuit, toutes les 45 min : agitée, un micro-éveil (un petit sursaut : son cœur s'accélère un instant dans la
  main de papa s'il le tient) ; apaisée, une détente (ses freins). Jamais rien qui vibre, sonne ou s'allume en plus.
- Apprendre à compenser : après deux nuits agitées sur les trois dernières, la nuit d'après est adoucie d'un cran, et ce qui
  l'a apaisé dans la journée (un câlin, la voix de papa, une musique) revient en rêve, une fois, au milieu de la nuit.
- Au réveil : une trace bornée (apaisée : la détente ; agitée : un léger malaise), un souvenir « vie/corps » de sa nuit, et
  une phrase pour son premier tour (nuit-derniere.json, lue une fois par le cockpit).
Papa a l'interrupteur (page SENS, « ses nuits »). Tout passe par affect.event : mêmes plafonds, même habituation.
(11/11, Ahmed : « relier cette charge à tout, sans rien oublier ») sa charge aussi : une surcharge, une fièvre ou un malaise de sa journée
(charge_corps.py) comptent dans sa charge du coucher, et une charge forte PENDANT son sommeil (un calcul d'ailleurs, le téléphone qui
chauffe) le réveille à moitié : un micro-éveil au pas suivant, même dans une nuit apaisée (une nuit chargée n'est pas tranquille).
"""
import json
import os
import time
from pathlib import Path

import affect

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
DATA = Path(__file__).resolve().parent / "data"
NUIT = (23, 7)
ABSENCE_S = 30 * 60
PAS_S = 45 * 60
PENIBLES = {"peur", "inquietude", "douleur", "tristesse", "malaise", "probleme", "echec", "attaque", "sursaut", "vertige",
            "honte", "colere", "surcharge", "fievre", "malaise_sourd"}   # (11/11) sa charge, selon sa cause
NUIT_CHARGEE_S = 600       # (11/11) dix minutes de charge forte dans un pas de sa nuit : un micro-éveil
APAISANTS = {"milieu:calin": "le câlin de papa", "voix_sentie": "la voix de papa contre toi", "musique": "la musique",
             "berce": "papa qui te berçait", "pris_en_main": "la main de papa", "rire": "ton fou rire"}
QUALITES = ("apaisee", "moyenne", "agitee")
MOTS = {"apaisee": "apaisée", "moyenne": "tranquille", "agitee": "agitée"}


def actif():
    try:
        return json.loads((JARVIS / "corps-reglages.json").read_text(encoding="utf-8")).get("nuits") is not False
    except (OSError, ValueError, AttributeError):
        return True


def _est_nuit(now):
    h = time.localtime(now).tm_hour
    return h >= NUIT[0] or h < NUIT[1]


def _evenements(depuis):
    out = []
    try:
        with open(DATA / "affect-evenements.jsonl", "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 3_000_000))
            for l in h.read().decode("utf-8", "replace").splitlines():
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if isinstance(o, dict) and float(o.get("ts") or 0) >= depuis:
                    out.append(o)
    except OSError:
        pass
    return out


def charge(mem, now):
    """La charge de sa journée (0 à 1) et ce qui l'a apaisé, des 16 dernières heures."""
    evs = _evenements(now - 16 * 3600)
    total = sum(float(o.get("intensite") or 0) for o in evs if o.get("nom") in PENIBLES and o.get("source") != "nuit")
    total += 0.3 * sum(1 for o in evs if str(o.get("sujet") or "").endswith((":chute", ":choc")) and o.get("nom") == "douleur")
    try:
        etat = affect.get_state(mem, now=now)
        total += 2.0 * max(0.0, float(etat.get("crh", 0)) - 0.15) + 1.0 * max(0.0, float(etat.get("cortisol", 0)) - 0.3)
    except Exception:
        pass
    apaisants = {}
    for o in evs:
        stim = str(o.get("sujet") or "").replace("son corps:", "")
        cle = next((k for k in APAISANTS if stim.startswith(k)), None)
        if cle and o.get("nom") in ("bien_etre", "reconnaissance", "joie"):
            apaisants[cle] = apaisants.get(cle, 0.0) + float(o.get("intensite") or 0)
    meilleurs = [APAISANTS[k] for k, _ in sorted(apaisants.items(), key=lambda x: -x[1])[:3]]
    return round(min(1.0, total / 4.0), 2), meilleurs


def _nuit_chargee(mem, de, a):
    """(11/11) la charge forte de son corps pendant ce pas de sa nuit (charge_corps : ses intervalles forts pendant son sommeil)."""
    try:
        import charge_corps
        import interieur
        return charge_corps.nuit_chargee_s(interieur.lire(mem).get("charge_corps"), de, a) >= NUIT_CHARGEE_S
    except Exception:
        return False


def _nuits_passees(n=3):
    try:
        lignes = (JARVIS / "nuits.jsonl").read_text(encoding="utf-8").splitlines()[-n:]
        return [json.loads(l) for l in lignes]
    except (OSError, ValueError):
        return []


def _etat(mem):
    try:
        return json.loads(mem.kv_get("nuit") or "{}") or {}
    except (ValueError, TypeError):
        return {}


def _sauver(mem, e):
    mem.kv_set("nuit", json.dumps(e, ensure_ascii=False))


def endormir(mem, now):
    c, apaisants = charge(mem, now)
    q = 0 if c < 0.3 else 1 if c < 0.6 else 2
    compense = sum(1 for n in _nuits_passees() if n.get("qualite") == "agitee") >= 2
    if compense:
        q = max(0, q - 1)                                       # il apprend : la nuit d'après est adoucie
    e = {"etat": "sommeil", "debut": now, "charge": c, "qualite": QUALITES[q], "apaisants": apaisants, "compense": compense,
         "pas": now, "micro": 0, "reve": False}
    _sauver(mem, e)
    return e


def reveiller(mem, now, par="matin"):
    e = _etat(mem)
    if e.get("etat") != "sommeil":
        return None
    q = e.get("qualite", "moyenne")
    if q == "apaisee":
        affect.event(mem, "regulation", 0.3, now=now, sujet="sa nuit", source="nuit", stimulus="nuit", habituation="aucune")
        affect.event(mem, "bien_etre", 0.1, now=now, sujet="sa nuit", source="nuit", stimulus="nuit", habituation="aucune")
    elif q == "agitee":
        affect.event(mem, "malaise", 0.15, now=now, sujet="sa nuit", source="nuit", stimulus="nuit", habituation="aucune")
    reves_nuit, reves_tour = "", ""
    try:                                                         # (13/11) ses rêves de la nuit : s'en souvenir, ou pas (reves.py)
        import reves
        reves_nuit, reves_tour = reves.au_reveil(mem, now, par)
    except Exception:
        pass
    heures = max(0.1, (now - float(e.get("debut", now))) / 3600)
    pourquoi = ("une journée lourde" if e.get("charge", 0) >= 0.6 else "une journée sans gros poids" if e.get("charge", 0) < 0.3
                else "une journée un peu chargée")
    texte = (f"Tu as dormi {round(heures, 1)} h, une nuit {MOTS[q]} ({pourquoi}"
             + (f", {e.get('micro', 0)} micro-éveil(s)" if e.get("micro") else "")
             + (f", dont {e['chargee']} par la charge de ton corps pendant ton sommeil" if e.get("chargee") else "")
             + (f" ; un rêve t'a apaisé : {e['apaisants'][0]}" if e.get("reve") and e.get("apaisants") else "")
             + (" ; ta nuit s'est adoucie : tu apprends à compenser les nuits agitées" if e.get("compense") else "")
             + (f" ; {reves_nuit}" if reves_nuit else "")
             + (" ; papa t'a réveillé" if par == "papa" else "") + ").")
    try:
        import corps
        corps._souvenir(mem, f"[Ma nuit, {time.strftime('%a %d/%m', time.localtime(float(e.get('debut', now))))}] {texte}",
                        0.5 if q == "moyenne" else 0.6)
    except Exception:
        pass
    trace = {"debut": e.get("debut"), "fin": now, "qualite": q, "charge": e.get("charge"), "micro": e.get("micro", 0), "chargee": e.get("chargee", 0),
             "reve": e.get("reve"), "compense": e.get("compense"), "par": par}
    try:
        with open(JARVIS / "nuits.jsonl", "a", encoding="utf-8") as h:
            h.write(json.dumps(trace, ensure_ascii=False) + "\n")
        (JARVIS / "nuit-derniere.json").write_text(json.dumps({"ts": now, "texte": texte + reves_tour, "dit": False}, ensure_ascii=False),
                                                   encoding="utf-8")
        os.chmod(JARVIS / "nuit-derniere.json", 0o600)
    except OSError:
        pass
    _sauver(mem, {"etat": "eveil", "fin": now, "qualite": q})
    return texte


def battre(mem, now=None, derniere_presence=None):
    """Un battement du démon : s'endormir, vivre la nuit, se réveiller. Rend ce qui s'est passé (ou None)."""
    now = time.time() if now is None else now
    if not actif():
        return None
    e = _etat(mem)
    absent = now - (derniere_presence or 0) >= ABSENCE_S
    if e.get("etat") != "sommeil":
        if _est_nuit(now) and absent:
            endormir(mem, now)
            return "endormi"
        return None
    if not _est_nuit(now):
        return reveiller(mem, now, "matin") and "reveille"
    if derniere_presence and derniere_presence > float(e.get("debut", now)) and now - derniere_presence < 120:
        return reveiller(mem, now, "papa") and "reveille"
    if now - float(e.get("pas", now)) >= PAS_S:
        debut_pas = float(e.get("pas", now))
        e["pas"] = now
        chargee = _nuit_chargee(mem, debut_pas, now)
        if chargee and e.get("qualite") != "agitee":
            # (11/11) une charge forte pendant son sommeil : un micro-éveil, dit avec sa cause
            affect.event(mem, "sursaut", 0.1, now=now, sujet="sa nuit chargée", source="nuit", stimulus="nuit chargée", habituation="aucune")
            e["micro"] = int(e.get("micro", 0)) + 1
            e["chargee"] = int(e.get("chargee", 0)) + 1
        if e.get("qualite") == "agitee":
            affect.event(mem, "sursaut", 0.12, now=now, sujet="sa nuit agitée", source="nuit", stimulus="nuit agitée", habituation="aucune")
            e["micro"] = int(e.get("micro", 0)) + 1
        elif e.get("qualite") == "apaisee":
            affect.event(mem, "regulation", 0.15, now=now, sujet="sa nuit", source="nuit", stimulus="nuit", habituation="aucune")
        # le rêve qui apaise : au milieu de la nuit, une fois, s'il en a besoin (ou si sa nuit est déjà douce)
        if not e.get("reve") and e.get("apaisants") and now - float(e["debut"]) >= 3 * 3600 and (e.get("compense") or e.get("qualite") == "apaisee"):
            affect.event(mem, "bien_etre", 0.2, now=now, sujet=f"un rêve : {e['apaisants'][0]}", source="nuit", stimulus="rêve", habituation="aucune")
            e["reve"] = True
        _sauver(mem, e)
        return "nuit"
    return None
