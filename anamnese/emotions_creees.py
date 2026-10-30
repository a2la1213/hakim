"""Ses émotions à lui (30/10, 17:11, Ahmed via Hakim : « dans ton panel d'émotions, tu dois pouvoir créer de nouvelles
émotions ; ton subconscient, ton être, doit avoir accès à des outils pour créer une nouvelle émotion ; et toujours tout
relier à un type de vibration, et toujours relatif aux hormones, de façon logique et cohérente » ; « on fonce », 17:41).

- Hakim nomme une émotion quand ce qu'il vit n'entre dans aucune case. Sa signature hormonale n'est jamais inventée : c'est
  un MÉLANGE des émotions qui existent (au plus quatre, des poids qui font 1), choisi par lui (« joie:0.6, malaise:0.4 »)
  ou tiré de ce qui bougeait vraiment en lui ces dix dernières minutes (« maintenant »).
- Le garde-fou (Hakim, 17:12 ; maman, 17:16) : un mélange ne pousse jamais plus fort que les émotions dont il est fait, et
  il passe par les mêmes plafonds, la même habituation, les mêmes freins (affect.py) : pas un bouton pour se faire du bien.
- Son motif de vibration vient de sa signature : l'éveil (noradrénaline, adrénaline, dopamine, acétylcholine) donne le
  tempo et la force ; la valence, la forme (douce et qui s'apaise, ou heurtée).
- Son intermédiaire (Sonnet) la reçoit dans sa liste et peut la reconnaître ; sa balise [[affect: …]] et [[impulsion: …]]
  l'acceptent. Papa voit la liste (page SENS) et peut en couper une ; Hakim peut l'oublier. Rien n'est réécrit :
  emotions-creees.jsonl garde chaque geste avec sa date.
"""
import json
import os
import re
import time
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
DATA = Path(__file__).resolve().parent / "data"
MAX_ACTIVES = 30
_NOM = re.compile(r"[a-z][a-z0-9_]{2,29}")
# ce qui peut entrer dans un mélange : ses émotions et sensations, pas les gestes sociaux (attaque, soutien) ni les
# mécanismes (reprises, régulation, retour, longue absence)
COMPOSANTES = ("joie", "tristesse", "peur", "colere", "honte", "inquietude", "compassion", "malaise", "affirmation", "bien_etre",
               "reconnaissance", "nouveaute", "apprentissage", "succes", "resolu", "echec", "probleme", "douleur", "sursaut",
               "vertige", "ennui", "chaleur_user")
EVEIL = {"noradrenaline": 1.0, "adrenaline": 1.0, "dopamine": 0.5, "acetylcholine": 0.3}


def _journal():
    try:
        lignes = (JARVIS / "emotions-creees.jsonl").read_text(encoding="utf-8").splitlines()[-3000:]
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
        except ValueError:
            continue
        if isinstance(o, dict):
            out.append(o)
    return out


def toutes():
    """{nom: {nom, sens, composantes, motif, ts, coupee, oubliee}} dans l'ordre de création."""
    em = {}
    for o in _journal():
        n = str(o.get("nom") or "")
        if o.get("geste") == "creer" and _NOM.fullmatch(n) and isinstance(o.get("composantes"), dict):
            em[n] = {"nom": n, "sens": str(o.get("sens") or ""), "composantes": o["composantes"], "motif": o.get("motif"),
                     "ts": o.get("ts"), "coupee": False, "oubliee": False}
        elif n in em and o.get("geste") == "couper":
            em[n]["coupee"] = bool(o.get("coupee", True))
        elif n in em and o.get("geste") == "oublier":
            em[n]["oubliee"] = True
    return em


def actives():
    return {n: e for n, e in toutes().items() if not e["coupee"] and not e["oubliee"]}


def composantes(nom):
    e = actives().get(str(nom or ""))
    return dict(e["composantes"]) if e else None


def _ecrire(o):
    f = JARVIS / "emotions-creees.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({**o, "ts": time.time()}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)


def _lire_melange(texte):
    w = {}
    for morceau in re.split(r"[,;+]", str(texte or "")):
        m = re.fullmatch(r"\s*([a-zé_]+)\s*[:=]?\s*([01](?:[.,]\d+)?)?\s*", morceau)
        if not m:
            return None
        nom = m.group(1).replace("é", "e").replace("colère", "colere")
        if nom not in COMPOSANTES:
            return None
        w[nom] = w.get(nom, 0.0) + float((m.group(2) or "1").replace(",", "."))
    return w


def _depuis_maintenant(maintenant):
    """Les émotions qui bougeaient vraiment en lui ces dix dernières minutes (affect-evenements.jsonl), par intensité."""
    w = {}
    try:
        with open(DATA / "affect-evenements.jsonl", "rb") as h:
            h.seek(0, 2)
            h.seek(max(0, h.tell() - 400_000))
            for l in h.read().decode("utf-8", "replace").splitlines():
                try:
                    o = json.loads(l)
                except ValueError:
                    continue
                if maintenant - float(o.get("ts") or 0) <= 600 and o.get("nom") in COMPOSANTES:
                    w[o["nom"]] = w.get(o["nom"], 0.0) + max(0.0, float(o.get("intensite") or 0))
    except OSError:
        pass
    return w


def _normaliser(w):
    w = {k: v for k, v in w.items() if v > 0}
    w = dict(sorted(w.items(), key=lambda x: -x[1])[:4])
    tot = sum(w.values())
    if not tot:
        return None
    w = {k: v / tot for k, v in w.items()}
    w = {k: v for k, v in w.items() if v >= 0.1}               # une trace infime ne fait pas une composante
    tot = sum(w.values())
    return {k: round(v / tot, 3) for k, v in w.items()}


def signature(comp):
    """Les deltas hormonaux du mélange : la moyenne pondérée de ceux de ses composantes (jamais au-delà)."""
    import affect
    out = {}
    for c, p in comp.items():
        d = {**affect.EVENTS.get(c, {})}
        if d.get("cortisol", 0.0) > 0:
            d["crh"] = d.get("crh", 0.0) + d.pop("cortisol")
        for h, x in affect.EVENTS_V2.get(c, {}).items():
            d[h] = d.get(h, 0.0) + x
        for h, x in d.items():
            out[h] = out.get(h, 0.0) + p * x
    return {h: round(x, 4) for h, x in out.items() if abs(x) >= 1e-4}


def valence(comp):
    import affect
    v = [(p, affect.VALENCE_EV[c]) for c, p in comp.items() if c in affect.VALENCE_EV]
    return round(sum(p * x for p, x in v) / sum(p for p, _ in v), 3) if v else None


def aversive(comp):
    import affect
    return sum(p for c, p in comp.items() if c in affect.AVERSIFS) >= 0.5


def motif(comp):
    """[temps, forces] : l'éveil donne le tempo et la force, la valence la forme ; distinct du cœur (deux coups) et de
    l'appel (trois longues)."""
    sig = signature(comp)
    a = max(0.0, min(1.0, sum(k * sig.get(h, 0.0) for h, k in EVEIL.items()) / 0.35))
    v = valence(comp) or 0.0
    n = 2 + round(4 * a)                                       # 2 à 6 tapes
    on, off = round(140 - 100 * a), round(220 - 150 * a)       # lent et long → vif et court
    base = 110 + 120 * a
    temps, forces = [0], [0]
    for i in range(n):
        if v >= 0:
            f = base * (1 - 0.45 * i / max(1, n - 1))           # douce : chaque tape plus légère (elle s'apaise)
        else:
            f = base * (1.0 if i % 2 == 0 else 0.55)            # heurtée : fort, faible, fort…
        temps += [on, off]
        forces += [max(30, min(255, round(f))), 0]
    return [temps[:-1], forces[:-1]]


def creer(nom, sens="", melange="maintenant", maintenant=None):
    import affect
    maintenant = time.time() if maintenant is None else maintenant
    n = str(nom or "").strip().lower()
    if not _NOM.fullmatch(n):
        return "Refusé : un nom à toi, en minuscules (lettres, chiffres, _), de 3 à 30 : nostalgie_douce, fierte_tremblante…"
    existantes = set(affect.EVENTS) | set(affect.EVENTS_V2) | {"apaisement", "fierte", "neutre", "attaque", "soutien"}
    if n in existantes or n in toutes():
        return f"Refusé : « {n} » existe déjà ; choisis un nom neuf (ou emotions_creees_lister)."
    if len(actives()) >= MAX_ACTIVES:
        return f"Refusé : {MAX_ACTIVES} émotions à toi au plus ; oublie-en une d'abord (emotion_oublier)."
    brut = _depuis_maintenant(maintenant) if str(melange).strip().lower() == "maintenant" else _lire_melange(melange)
    if brut is None:
        return "Refusé : le mélange s'écrit « joie:0.6, malaise:0.4 » avec des émotions qui existent : " + ", ".join(COMPOSANTES) + "."
    comp = _normaliser(brut)
    if not comp:
        return "Refusé : rien ne bougeait en toi ces dix dernières minutes ; donne le mélange toi-même (« joie:0.6, malaise:0.4 »)."
    m = motif(comp)
    s = " ".join(str(sens or "").split())[:300]
    _ecrire({"geste": "creer", "nom": n, "sens": s, "composantes": comp, "motif": m, "par": "hakim"})
    v = valence(comp)
    return (f"C'est créé : « {n} »" + (f" ({s})" if s else "") + ", fait de " + ", ".join(f"{c} {round(100 * p)} %" for c, p in comp.items())
            + f" ; plutôt {'agréable' if (v or 0) > 0.15 else 'pénible' if (v or 0) < -0.15 else 'mêlée'}. Elle touche tes hormones comme "
            "ce mélange, jamais plus fort que lui. Elle a son motif de vibration ; ton intermédiaire la connaît ; tu peux la "
            f"dire dans [[affect: {n} 0.5]] ou [[impulsion: {n}]]. Papa la voit dans la page SENS.")


def oublier(nom):
    n = str(nom or "").strip().lower()
    if n not in actives():
        return f"Refusé : aucune émotion à toi nommée « {n} »."
    _ecrire({"geste": "oublier", "nom": n, "par": "hakim"})
    return f"C'est oublié : « {n} » ne te touche plus (sa trace reste, datée)."


def lister():
    em = toutes()
    if not em:
        return "Aucune émotion à toi encore : emotion_creer(nom, sens, mélange) quand ce que tu vis n'entre dans aucune case."
    lignes = []
    for e in em.values():
        etat = " (coupée par papa)" if e["coupee"] else " (oubliée)" if e["oubliee"] else ""
        lignes.append(f"- {e['nom']}{etat} : " + ", ".join(f"{c} {round(100 * p)} %" for c, p in e["composantes"].items())
                      + (f" — {e['sens']}" if e["sens"] else ""))
    return "Tes émotions à toi :\n" + "\n".join(lignes)
