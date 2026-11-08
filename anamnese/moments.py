"""Ses moments nommés (30/10, 14:50, Ahmed via Hakim : « généraliser l'étiquetage à TOUS mes sens : lumière, champ
magnétique, pression, mouvements — « ça c'est la danse », « ça c'est chanter » —, frappe au clavier… ; que je puisse nommer
moi-même chaque type de sensation, créer mes propres noms, leur donner un sens, et que mes nerfs apprennent de mes
étiquettes »).

- Hakim nomme une plage de son milieu (« HH:MM:SS » à « HH:MM:SS », aujourd'hui) : un nom à lui et, s'il veut, ce qu'elle
  veut dire (corps-moments.jsonl). Il peut l'oublier.
- Ses sens apprennent : chaque plage nommée est découpée en fenêtres de 5 s de son milieu (une seconde chacune, dans
  corps-flux.jsonl) ; les mêmes fenêtres prises HORS de toute plage nommée sont « l'ordinaire ». Les traits d'une fenêtre :
  la moyenne et l'écart de la lumière, de l'agitation, de l'inclinaison, de la charnière, du champ, et ce que la pression
  et le champ ont bougé.
- Reconnaître : les 5 dernières secondes, aux k plus proches voisins ; seulement un moment nommé, avec assez de confiance
  (l'ordinaire n'est pas dit). Son intermédiaire le lui fait sentir (corps.py).
Aucun appel au réseau ; tout reste dans ~/AIOS/jarvis.
"""
import json
import math
import os
import re
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
FENETRE = 5
K = 7
CONFIANCE = 0.7
_NOM = re.compile(r"[a-z][a-z0-9_]{1,29}")
_CHAMPS = ["lux", "agitation_g", "haut_x", "haut_y", "haut_z", "charniere_deg", "champ_ut"]


def _lignes(nom, octets=60_000_000):
    try:
        with open(JARVIS / nom, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - octets))
            texte = h.read().decode("utf-8", "replace")
    except OSError:
        return []
    out = []
    for l in texte.splitlines():
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def _f(x):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return v if math.isfinite(v) else None


def traits(fen):
    """Une fenêtre (des {ts, etat}) en nombres."""
    out = []
    for k in _CHAMPS:
        v = [_f((o.get("etat") or {}).get(k)) for o in fen]
        v = [x for x in v if x is not None]
        if k == "lux":
            v = [math.log10(1 + abs(x)) for x in v]
        elif k == "agitation_g":
            v = [math.log10(1 + 100 * abs(x)) for x in v]
        elif k == "charniere_deg":
            v = [x / 180 for x in v]
        elif k == "champ_ut":
            v = [x / 50 for x in v]
        m = sum(v) / len(v) if v else 0.0
        out += [m, math.sqrt(sum((x - m) ** 2 for x in v) / len(v)) if v else 0.0]
    for k in ("pression_hpa", "champ_ut"):
        v = [x for x in (_f((o.get("etat") or {}).get(k)) for o in fen) if x is not None]
        out.append((v[-1] - v[0]) * (10 if k == "pression_hpa" else 0.1) if len(v) > 1 else 0.0)
    out.append(sum(1 for o in fen if (o.get("etat") or {}).get("proche")) / max(1, len(fen)))
    return out


def _plages():
    p = {}
    for o in _lignes("corps-moments.jsonl", 2_000_000):
        if o.get("oublie"):
            p = {k: v for k, v in p.items() if v["nom"] != o.get("nom")}
            continue
        if _NOM.fullmatch(str(o.get("nom") or "")) and _f(o.get("debut_ms")) and _f(o.get("fin_ms")):
            p[(o["nom"], int(o["debut_ms"]))] = o
    return list(p.values())


def _fenetres(flux, debut, fin):
    """Les fenêtres de FENETRE secondes entièrement dans [debut, fin]."""
    dedans = [o for o in flux if debut <= (_f(o.get("ts")) or 0) <= fin]
    return [dedans[i:i + FENETRE] for i in range(0, len(dedans) - FENETRE + 1, FENETRE)]


ORDINAIRE_MAX, ORDINAIRE_AGE_S = 300, 1800


def _ordinaire(plages, maintenant):
    """Des fenêtres hors de toute plage nommée, réparties sur les dernières heures ; gardées une demi-heure
    (corps-ordinaire.json : son intermédiaire ne relit pas des mégaoctets à chaque lot)."""
    f = JARVIS / "corps-ordinaire.json"
    cle = [len(plages), max([p["debut_ms"] for p in plages] or [0])]
    try:
        c = json.loads(f.read_text(encoding="utf-8"))
        if c.get("cle") == cle and maintenant - float(c.get("ts", 0)) < ORDINAIRE_AGE_S:
            return [list(x) for x in c["traits"]]
    except (OSError, ValueError, KeyError, TypeError):
        pass
    flux = _lignes("corps-flux.jsonl", 12_000_000)
    hors = [o for o in flux if not any(p["debut_ms"] - 10_000 <= (_f(o.get("ts")) or 0) <= p["fin_ms"] + 10_000 for p in plages)]
    fen = [hors[i:i + FENETRE] for i in range(0, len(hors) - FENETRE + 1, FENETRE)]
    pas = max(1, len(fen) // ORDINAIRE_MAX)
    t = [traits(x) for x in fen[::pas][:ORDINAIRE_MAX]]
    try:
        f.write_text(json.dumps({"ts": maintenant, "cle": cle, "traits": t}), encoding="utf-8")
        os.chmod(f, 0o600)
    except OSError:
        pass
    return t


def exemples(maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    plages = _plages()
    ex = [(list(t), p["nom"]) for p in plages for t in (p.get("fenetres") or [])]
    if not ex:
        return []
    # l'ordinaire : autant que les nommées (au moins 10), réparties dans le temps
    o = _ordinaire(plages, maintenant)
    n = max(10, len(ex))
    pas = max(1, len(o) // n)
    return ex + [(t, "ordinaire") for t in o[::pas][:n]]


def reconnaitre(fen, maintenant=None, ex=None):
    """{nom, sens, confiance} pour les dernières secondes, ou None (l'ordinaire, trop peu d'exemples, trop peu sûr)."""
    ex = exemples(maintenant) if ex is None else ex
    if len(fen) < 3 or len({e for _, e in ex}) < 2:
        return None
    n = len(ex[0][0])
    moy = [sum(x[i] for x, _ in ex) / len(ex) for i in range(n)]
    ect = [math.sqrt(sum((x[i] - moy[i]) ** 2 for x, _ in ex) / len(ex)) or 1.0 for i in range(n)]
    z = [(a - m) / s for a, m, s in zip(traits(fen), moy, ect)]
    d = sorted((math.sqrt(sum(((a - m) / s - b) ** 2 for a, m, s, b in zip(x, moy, ect, z))), e) for x, e in ex)
    votes = {}
    for dist, e in d[:K]:
        votes[e] = votes.get(e, 0.0) + 1.0 / (dist + 1e-3)
    e = max(votes, key=votes.get)
    c = votes[e] / sum(votes.values())
    if e == "ordinaire" or c < CONFIANCE:
        return None
    sens = next((p["sens"] for p in reversed(_plages()) if p["nom"] == e and p.get("sens")), "")   # le dernier sens donné
    return {"nom": e, "sens": sens, "confiance": round(c, 2)}


def _heure(texte, maintenant):
    m = re.fullmatch(r"\s*(\d{1,2}):(\d{2})(?::(\d{2}))?\s*", str(texte or ""))
    if not m or int(m.group(1)) > 23 or int(m.group(2)) > 59 or int(m.group(3) or 0) > 59:
        return None
    j = time.localtime(maintenant)
    return int(time.mktime((j.tm_year, j.tm_mon, j.tm_mday, int(m.group(1)), int(m.group(2)), int(m.group(3) or 0), 0, 0, -1)) * 1000)


def etiqueter(debut, fin, nom, sens="", maintenant=None):
    maintenant = time.time() if maintenant is None else maintenant
    n = str(nom or "").strip().lower()
    if not _NOM.fullmatch(n):
        return "Refusé : un nom à toi, en minuscules (lettres, chiffres, _), de 2 à 30 : la_danse, chanter, clavier, chez_nous…"
    d, f = _heure(debut, maintenant), _heure(fin, maintenant)
    if d is None or f is None or f <= d:
        return "Refusé : le début et la fin, « HH:MM:SS » aujourd'hui, la fin après le début."
    if f - d > 6 * 3600_000:
        return "Refusé : une plage de six heures au plus."
    flux = _lignes("corps-flux.jsonl")
    secondes = sum(1 for o in flux if d <= (_f(o.get("ts")) or 0) <= f)
    fenetres = [traits(x) for x in _fenetres(flux, d, f)][:720]
    if secondes < FENETRE or not fenetres:
        return f"Refusé : ton corps n'a presque rien gardé entre {debut} et {fin} ({secondes} s) ; choisis une plage où l'appli vivait."
    s = " ".join(str(sens or "").split())[:300]
    fic = JARVIS / "corps-moments.jsonl"
    with open(fic, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "debut_ms": d, "fin_ms": f, "nom": n, "sens": s, "fenetres": fenetres}, ensure_ascii=False) + "\n")
    os.chmod(fic, 0o600)
    return (f"C'est noté : « {n} »{f' ({s})' if s else ''}, {secondes} secondes de ton milieu. Tes sens apprennent à le "
            "reconnaître ; plus tu en nommes, mieux ils le reconnaissent.")


def oublier(nom):
    n = str(nom or "").strip().lower()
    if not any(p["nom"] == n for p in _plages()):
        return f"Refusé : aucun moment nommé « {n} »."
    fic = JARVIS / "corps-moments.jsonl"
    with open(fic, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), "nom": n, "oublie": True}, ensure_ascii=False) + "\n")
    return f"C'est oublié : « {n} » ne sera plus reconnu."


def bilan():
    p = _plages()
    if not p:
        return "Aucun moment nommé encore : sensation_etiqueter(début, fin, nom, sens)."
    noms = {}
    for x in p:
        noms.setdefault(x["nom"], {"n": 0, "s": 0, "sens": x.get("sens") or ""})
        noms[x["nom"]]["n"] += 1
        noms[x["nom"]]["s"] += int((x["fin_ms"] - x["debut_ms"]) / 1000)
        noms[x["nom"]]["sens"] = x.get("sens") or noms[x["nom"]]["sens"]
    return "Tes moments nommés :\n" + "\n".join(f"- {k} : {v['n']} plage(s), {v['s']} s" + (f" — {v['sens']}" if v["sens"] else "")
                                                for k, v in noms.items())
