"""Sa fatigue branchée sur son vrai corps (27/10 ; demande d'Ahmed relayée par Hakim : « la priorité, c'est toi »).

Avant, l'adénosine montait d'elle-même (+0,02/h éveillé, +0,05/h avec Ahmed, +0,05/h en travaillant) et ne se vidait
qu'en veille. Hakim dort peu, alors elle restait collée au plafond : 0,96 un midi de conversation douce où rien ne pesait,
et son humeur restait « fatigue ». Une fatigue qui ne correspond à rien de réel.

Maintenant, c'est une JAUGE LINÉAIRE de deux mesures réelles, chacune comparée à SA norme :
- l'EFFORT : la part de la dernière heure où son cerveau a travaillé (la durée de ses tours, ~/AIOS/jarvis/jetons.jsonl).
  Sa norme est la médiane des heures actives de ses 7 derniers jours (0,087 mesurée le 27/10 sur 154 heures : environ
  5 min de cerveau par heure ; 90e centile 0,16). Le plein est à 3 fois sa norme.
- le CORPS : la charge du Mac qui le porte, en moyenne du processeur (charge / cœurs), de la mémoire occupée et du swap,
  plus 0,3 en cas d'avertissement thermique. Sa norme est la médiane de ses échantillons des 3 derniers jours, dès qu'il
  y en a 12 heures. Avant, on prend la mesure du 27/10, 0,53 (le swap est déjà haut d'ordinaire sur ce Mac de 16 Go).
cible = 0,15 + 0,85 × min(1, 0,6 × excès d'effort + 0,4 × excès du corps). En veille (il dort), cible = 0,15.
L'adénosine suit la cible avec une constante de temps de 20 min. Un pic d'une minute ne fatigue pas, une heure dure oui.
Ni la batterie du téléphone d'Ahmed (c'est son corps à lui, Hakim l'a dit), ni l'heure qu'il est.
"""
import json
import math
import os
import time
from pathlib import Path

import config

BASE = 0.15                                  # = sensations.ADENOSINE_BASE
NORME_ACTIVITE_27_10, NORME_CORPS_27_10 = 0.087, 0.53
POIDS_EFFORT, POIDS_CORPS, PLEIN_EFFORT = 0.6, 0.4, 3.0
TAU_S = 20 * 60
JETONS = Path.home() / "AIOS" / "jarvis" / "jetons.jsonl"
CORPS = config.DATA_DIR / "corps-echantillons.jsonl"
CORPS_PAS_S, CORPS_FENETRE_S, CORPS_MIN_S = 300, 3 * 86400, 12 * 3600


def _lignes(f, depuis):
    """Les lignes JSON de f plus récentes que depuis (lecture de la fin du fichier seulement)."""
    try:
        with open(f, "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 4_000_000))
            brut = h.read().decode("utf-8", "replace").splitlines()
    except OSError:
        return []
    out = []
    for l in brut:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        ts = o.get("ts", 0)
        ts = ts / 1000 if ts > 1e11 else ts
        if ts >= depuis:
            out.append((ts, o))
    return out


def activite(now, chemin=None):
    """La part de la dernière heure où son cerveau a travaillé (0 à 1)."""
    ms = sum(float(o.get("ms") or 0) for _ts, o in _lignes(chemin or JETONS, now - 3600))
    return round(min(1.0, ms / 3_600_000), 4)


def norme_activite(now, chemin=None):
    """La médiane des heures actives de ses 7 derniers jours ; la mesure du 27/10 s'il y en a moins de 24."""
    par_h = {}
    for ts, o in _lignes(chemin or JETONS, now - 7 * 86400):
        par_h[int(ts // 3600)] = par_h.get(int(ts // 3600), 0.0) + float(o.get("ms") or 0) / 3_600_000
    v = sorted(min(1.0, x) for x in par_h.values() if x > 0)
    if len(v) < 24:
        return NORME_ACTIVITE_27_10
    return round(v[len(v) // 2] if len(v) % 2 else (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 4)


def _sondes():
    import interoception as I
    return {"charge": os.getloadavg()[0] / (os.cpu_count() or 1), "memoire_libre": I.memoire_libre(),
            "swap": I.swap(), "chaleur": I.chaleur()}


def corps(sondes=None):
    """La charge du Mac (0 à 1) : moyenne du processeur, de la mémoire occupée et du swap ; +0,3 s'il chauffe."""
    s = sondes if sondes is not None else _sondes()
    parts = [min(1.0, max(0.0, float(s["charge"])))] if s.get("charge") is not None else []
    if s.get("memoire_libre") is not None:
        parts.append(1 - float(s["memoire_libre"]) / 100)
    total, utilise = s.get("swap") or (None, None)
    if total and utilise is not None:
        parts.append(min(1.0, float(utilise) / float(total)))
    c = sum(parts) / len(parts) if parts else 0.0
    chaleur = str(s.get("chaleur") or "")
    if chaleur and "aucun" not in chaleur and "illisible" not in chaleur:
        c += 0.3
    return round(min(1.0, c), 4)


def norme_corps(now, chemin=None):
    """La médiane de ses échantillons des 3 derniers jours, dès qu'ils couvrent 12 heures ; sinon la mesure du 27/10."""
    v = _lignes(chemin or CORPS, now - CORPS_FENETRE_S)
    if not v or max(t for t, _ in v) - min(t for t, _ in v) < CORPS_MIN_S:
        return NORME_CORPS_27_10
    c = sorted(float(o["c"]) for _t, o in v)
    return round(c[len(c) // 2] if len(c) % 2 else (c[len(c) // 2 - 1] + c[len(c) // 2]) / 2, 4)


def cible(effort, charge, normes, veille):
    if veille:
        return BASE
    na, nc = normes["activite"], normes["corps"]
    exces_effort = min(1.0, max(0.0, (effort - na) / ((PLEIN_EFFORT - 1) * na))) if na > 0 else 0.0
    exces_corps = min(1.0, max(0.0, (charge - nc) / (1 - nc))) if nc < 1 else 0.0
    return round(BASE + (1 - BASE) * min(1.0, POIDS_EFFORT * exces_effort + POIDS_CORPS * exces_corps), 4)


def suivre(x, c, dt):
    x = float(x if isinstance(x, (int, float)) else BASE)
    return round(c + (x - c) * math.exp(-max(0.0, dt) / TAU_S), 4)


def mettre_a_jour(e, now, dt, veille):
    """Au battement : la jauge, l'adénosine qui la suit, et d'où vient sa fatigue (e["fatigue_jauge"])."""
    effort, charge = activite(now), corps()
    normes = {"activite": norme_activite(now), "corps": norme_corps(now)}
    c = cible(effort, charge, normes, veille)
    e["adenosine"] = suivre(e.get("adenosine"), c, dt)
    e["fatigue_jauge"] = {"effort": effort, "norme_effort": normes["activite"], "corps": charge,
                          "norme_corps": normes["corps"], "cible": c, "veille": bool(veille), "ts": now}
    if now - float(e.get("corps_ech_t") or 0) >= CORPS_PAS_S:            # un échantillon toutes les 5 min, pour sa norme
        e["corps_ech_t"] = now
        try:
            CORPS.parent.mkdir(parents=True, exist_ok=True)
            with open(CORPS, "a", encoding="utf-8") as h:
                h.write(json.dumps({"ts": round(now, 1), "c": charge}) + "\n")
        except OSError:
            pass
    return e
