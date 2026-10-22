"""L'horloge à promesses de Hakim (demande de Hakim, accord d'Ahmed le 2026-10-22 : « je suis ok pour tout sauf le
point 8 »). Hakim pose un rendez-vous daté avec sa raison ; le cockpit le réveille à l'heure (server.js,
reveillerPourPromesses) pour qu'il fasse ce qu'il s'était promis.

Règles (Hakim, reprises d'Ahmed) : de 8 h à 23 h seulement, jamais de rappel pour dormir, jamais d'insistance
(une promesse sonne une fois), liste visible et effaçable par Ahmed (page Parler). 30 jours au plus, 20 en attente
au plus. Le fichier vit hors de la mémoire : ~/AIOS/jarvis/promesses.json, écrit d'un coup (fichier temporaire
puis renommage).
"""
import json
import os
import re
import secrets
import time
from datetime import datetime, timedelta
from pathlib import Path

FICHIER = Path.home() / "AIOS" / "jarvis" / "promesses.json"
# l'état que le COCKPIT donne (tenue, manquée, effacée par Ahmed) : un fichier à lui, pour que deux écrivains ne
# se marchent jamais dessus (Hakim écrit le premier, le cockpit le second)
ETATS = Path.home() / "AIOS" / "jarvis" / "promesses-etats.json"
JOUR = (8, 23)                     # une promesse sonne de 8 h à 23 h (heure locale du Mac)
HORIZON_S = 30 * 86400
EN_ATTENTE_MAX = 20
RAISON_MAX = 300


class Refus(ValueError):
    pass


def lire(fichier=None):
    try:
        d = json.loads(Path(fichier or FICHIER).read_text(encoding="utf-8"))
        return d if isinstance(d, dict) and isinstance(d.get("promesses"), list) else {"promesses": []}
    except (OSError, ValueError):
        return {"promesses": []}


def toutes(fichier=None, etats=None):
    """Les promesses avec l'état que le cockpit leur a donné (il l'emporte sur celui du fichier de Hakim)."""
    try:
        e = json.loads(Path(etats or (Path(fichier).with_name("promesses-etats.json") if fichier else ETATS)).read_text(encoding="utf-8"))
        e = e if isinstance(e, dict) else {}
    except (OSError, ValueError):
        e = {}
    return [{**p, "etat": e.get(p.get("id")) or p.get("etat")} for p in lire(fichier)["promesses"]]


def _ecrire(d, fichier=None):
    f = Path(fichier or FICHIER)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_suffix(f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    os.replace(tmp, f)


def quand_vers_ts(quand, maintenant=None):
    """« 2026-10-22 18:30 », « 18:30 » (aujourd'hui, ou demain si l'heure est passée), « +45 min », « +2 h »."""
    maintenant = time.time() if maintenant is None else maintenant
    q = re.sub(r"^(\d{1,2})\s*h\s*(\d{0,2})$", r"\1:\2", str(quand or "").strip().lower())   # 18h30, 18 h
    m = re.fullmatch(r"\+\s*(\d+)\s*(min|minutes?|h|heures?)", q)
    if m:
        return maintenant + int(m.group(1)) * (60 if m.group(2).startswith("min") else 3600)
    m = re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})[ t](\d{1,2}):(\d{2})", q)
    if m:
        return datetime(*map(int, m.groups())).timestamp()
    m = re.fullmatch(r"(\d{1,2}):(\d{2})?", q)
    if m:
        auj = datetime.fromtimestamp(maintenant)
        t = auj.replace(hour=int(m.group(1)), minute=int(m.group(2) or 0), second=0, microsecond=0)
        if t.timestamp() <= maintenant:
            t += timedelta(days=1)
        return t.timestamp()
    raise Refus("heure illisible : écris « AAAA-MM-JJ HH:MM », « HH:MM » ou « +45 min » / « +2 h »")


def poser(quand, raison, maintenant=None, fichier=None):
    maintenant = time.time() if maintenant is None else maintenant
    raison = re.sub(r"\s+", " ", str(raison or "")).strip()
    if not raison:
        raise Refus("une promesse a besoin de sa raison")
    ts = quand_vers_ts(quand, maintenant)
    if ts <= maintenant + 30:
        raise Refus("l'heure est déjà passée")
    if ts - maintenant > HORIZON_S:
        raise Refus("30 jours au plus")
    h = datetime.fromtimestamp(ts).hour
    if not (JOUR[0] <= h < JOUR[1]):
        raise Refus("de 8 h à 23 h seulement : jamais de rappel pour dormir")
    d = lire(fichier)
    if sum(p.get("etat") == "attente" for p in toutes(fichier)) >= EN_ATTENTE_MAX:
        raise Refus(f"{EN_ATTENTE_MAX} promesses en attente au plus")
    p = {"id": "P-" + secrets.token_hex(3), "t_ms": int(ts * 1000), "raison": raison[:RAISON_MAX],
         "posee_ms": int(maintenant * 1000), "etat": "attente"}
    d["promesses"] = (d["promesses"] + [p])[-200:]
    _ecrire(d, fichier)
    return p


def effacer(pid, fichier=None):
    d = lire(fichier)
    en_attente = {p["id"] for p in toutes(fichier) if p.get("etat") == "attente"}
    for p in d["promesses"]:
        if p.get("id") == pid and pid in en_attente:
            p["etat"] = "effacee"
            _ecrire(d, fichier)
            return True
    return False


def lisible(p):
    quand = datetime.fromtimestamp(p["t_ms"] / 1000).strftime("%d/%m %H:%M")
    return f"{p['id']} · {quand} · {p['etat']} · {p['raison']}"
