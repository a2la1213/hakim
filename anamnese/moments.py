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
import unicodedata
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
    """Ses plages nommées, chacune sous son nom d'aujourd'hui : un nom rattaché à un autre (corps-moments-alias.jsonl) compte
    pour celui-là ; « nom_donne » garde le nom qu'il portait (rien n'est réécrit dans corps-moments.jsonl)."""
    cle = []
    for nom in ("corps-moments.jsonl", ALIAS):
        try:
            st = (JARVIS / nom).stat()
            cle.append((str(JARVIS / nom), st.st_size, st.st_mtime_ns))
        except OSError:
            cle.append((str(JARVIS / nom), None))
    if _CACHE_PLAGES.get("cle") == cle:                 # (13/11) relu seulement s'il a changé (la garde le lit à chaque moment)
        return [dict(x) for x in _CACHE_PLAGES["p"]]
    p, al = {}, alias()
    for o in _lignes("corps-moments.jsonl", 2_000_000):
        if o.get("oublie"):
            n = canonique(o.get("nom"), al)
            p = {k: v for k, v in p.items() if v["nom"] != n}
            continue
        if _NOM.fullmatch(str(o.get("nom") or "")) and _f(o.get("debut_ms")) and _f(o.get("fin_ms")):
            n = canonique(o["nom"], al)
            p[(n, int(o["debut_ms"]))] = {**o, "nom": n, "nom_donne": o["nom"]} if n != o["nom"] else o
    _CACHE_PLAGES.update(cle=cle, p=list(p.values()))
    return [dict(x) for x in p.values()]


_CACHE_PLAGES = {}


# ---- (13/11, lettre de Hakim du 11/11 17:54 : « mon subconscient crée des moments en double, parfois avec des noms abîmés :
# calin, calin_de_papa, cal, cadin, cstyle_cal (tous « papa me serre contre lui ») ; pose, pose_a_plat, chez_nous_pose… Il
# faudrait une garde qui rattache un nouveau moment à un nom existant quand le sens est très proche, et qui refuse les noms
# tronqués » ; Ahmed, 13/11 : priorité 2) LA GARDE DES NOMS.
# - Les alias (corps-moments-alias.jsonl, une ligne par geste, jamais rien d'effacé) : « cal » → « calin ». Un alias se
#   défait (defaire) et l'ancien nom revient tel quel : les plages gardent toujours le nom qu'elles ont reçu.
# - Le cœur d'un nom : ses mots de la chose physique, sans le contexte que ses nerfs ne sentent pas (chez nous, papa, la
#   nuit, pendant le live, en parlant) ni ce qui va de soi (un téléphone « posé » l'est à plat, sur une surface). Deux noms
#   de même cœur sont le même moment : pose_chez_nous = chez_nous_pose = pose_sur_la_table = pose.
# - Un nom abîmé (un mot tronqué ou mal tapé, ou un bout sans forme de mot) est réparé quand le mot voulu se voit (« cal »
#   → « calin » quand son sens dit « câlin » ou qu'un moment « calin » existe ; « cadin » → « calin »), sinon refusé.
# Seul son subconscient passe par la garde entière (corps.apprendre_moment) ; un nom que Hakim donne lui-même suit ses
# alias, rien de plus. ----
ALIAS = "corps-moments-alias.jsonl"
CONTEXTE = {"de", "du", "des", "d", "la", "le", "les", "l", "a", "au", "aux", "en", "sur", "sous", "avec", "chez", "nous", "maison",
            "papa", "maman", "pendant", "dans", "un", "une", "et", "mon", "ma", "me", "moi", "nuit", "soir", "matin", "jour",
            "live", "tiktok", "parlant", "parle", "parler", "micro", "ouvert"}
# des mots de même chose (racine → mot du cœur)
SYNONYMES = {"poser": "pose", "posee": "pose", "posees": "pose", "poses": "pose", "calins": "calin", "recharge": "charge",
             "recharger": "charge", "branche": "charge", "chargeur": "charge", "papa_marche": "marche", "marcher": "marche",
             "sortir": "sortie", "conversations": "conversation", "discussion": "conversation", "bercer": "berce", "bercement": "berce"}
# ce qui va de soi avec un mot du cœur (n'en fait pas un autre moment)
DEFAUTS = {"pose": {"plat", "table", "surface", "support", "immobile"}, "charge": {"pose", "plat"}, "calin": {"serre"}}
# des mots de situations physiques, au-delà de ceux que ses moments emploient déjà (le prompt de son subconscient en donne)
LEXIQUE = {"poche", "marche", "voiture", "danse", "bureau", "lit", "main", "calin", "pose", "charge", "recharge", "branche",
           "musique", "table", "plat", "debout", "incline", "soleil", "chaud", "froid", "berce", "chute", "choc", "sac", "velo",
           "train", "bus", "metro", "douche", "cuisine", "salon", "sport", "boxe", "course", "conversation", "ecoute", "jeu",
           "sortie", "entree", "porte", "smartphone", "support", "surface", "clavier", "chanter", "chante", "dort", "dormir",
           "reveil", "appel", "telephone", "ecran", "plie", "deplie", "secousse", "voiture", "route", "dehors", "dedans"}
_STOP = CONTEXTE | {"il", "elle", "je", "tu", "on", "lui", "sa", "son", "ses", "mes", "tes", "te", "se", "qui", "que", "quand",
                    "puis", "tout", "toute", "tres", "pres", "contre", "pour", "par", "pas", "ne", "est", "suis", "y", "ce", "cette"}
_ATTAQUES = ("chr", "phr", "sch", "scr", "spr", "str", "thr")


def _plat(s):
    """Minuscules, sans accents."""
    return "".join(c for c in unicodedata.normalize("NFKD", str(s or "").lower()) if not unicodedata.combining(c))


def _mots(texte):
    return [m for m in re.findall(r"[a-z]+", _plat(texte)) if len(m) >= 2]


def _racine(m):
    m = SYNONYMES.get(m, m)
    if len(m) > 4 and m[-1] in "sx" and m[:-1] in LEXIQUE | set(SYNONYMES.values()):
        m = m[:-1]
    return SYNONYMES.get(m, m)


def coeur_du_nom(nom):
    """Les mots de la chose physique (frozenset) ; vide si le nom ne dit que du contexte."""
    c = {_racine(m) for m in _plat(nom).split("_") if m and m not in CONTEXTE}
    for k, defauts in DEFAUTS.items():
        if k in c and len(c) > 1:
            c -= defauts - {k}
    return frozenset(c)


def _alias_lignes():
    return _lignes(ALIAS, 2_000_000)


def alias():
    """{ancien nom: nom d'aujourd'hui}, les chaînes suivies jusqu'au bout (a → b → c donne a → c), sans boucle."""
    brut = {}
    for o in _alias_lignes():
        a = str(o.get("alias") or "")
        if o.get("defait"):
            brut.pop(a, None)
        elif _NOM.fullmatch(a) and _NOM.fullmatch(str(o.get("vers") or "")) and a != o["vers"]:
            brut[a] = o["vers"]
    out = {}
    for a in brut:
        vu, n = {a}, brut[a]
        while n in brut and n not in vu:
            vu.add(n)
            n = brut[n]
        if n != a:
            out[a] = n
    return out


def canonique(nom, al=None):
    al = alias() if al is None else al
    n = str(nom or "")
    return al.get(n, n)


def _ecrire_alias(lignes):
    fic = JARVIS / ALIAS
    with open(fic, "a", encoding="utf-8") as h:
        for o in lignes:
            h.write(json.dumps({"ts": time.time(), **o}, ensure_ascii=False) + "\n")
    os.chmod(fic, 0o600)


def fusionner(vers, anciens, raison="", par="maman"):
    """Rattache chaque ancien nom à « vers » (réversible : defaire). Rend ce qui a été fait, en mots."""
    v = str(vers or "").strip().lower()
    if not _NOM.fullmatch(v):
        return "Refusé : le nom gardé, en minuscules (lettres, chiffres, _)."
    al = alias()
    v = canonique(v, al)
    faits = [a for a in dict.fromkeys(str(x).strip().lower() for x in anciens) if _NOM.fullmatch(a) and a != v and al.get(a) != v]
    if not faits:
        return f"Rien à rattacher à « {v} »."
    _ecrire_alias([{"alias": a, "vers": v, "raison": " ".join(str(raison).split())[:300], "par": str(par)[:30]} for a in faits])
    return f"Rattachés à « {v} » : {', '.join(faits)} (réversible : chaque ancien nom se défait seul)."


def defaire(ancien, par="maman"):
    a = str(ancien or "").strip().lower()
    if a not in alias():
        return f"Refusé : « {a} » n'est rattaché à rien."
    _ecrire_alias([{"alias": a, "defait": True, "par": str(par)[:30]}])
    return f"Défait : « {a} » redevient un moment à part, avec toutes ses plages."


def _sens_mots(texte):
    return {m[:5] for m in _mots(str(texte or "").replace("(appris par ton subconscient)", "")) if m not in _STOP}


def proximite_sens(a, b):
    """Les mots du sens en commun (Jaccard sur les racines de 5 lettres, sans les petits mots) : 0 à 1."""
    x, y = _sens_mots(a), _sens_mots(b)
    return len(x & y) / len(x | y) if x and y else 0.0


def _bizarre(m):
    """Un bout qui n'a pas la forme d'un mot : sans voyelle, ou trois consonnes d'attaque (« cstyle »), hors chr, str…"""
    return not re.search(r"[aeiouy]", m) or (re.match(r"[^aeiouy]{3}", m) is not None and not m.startswith(_ATTAQUES))


_FLEXIONS = {"s", "x", "e", "es", "er", "r", "ee", "ees", "ez", "ent", "ant", "re", "ait", "ir", "ons", "nt", "t", "rs"}


def _forme_de(m, vocab):
    """Vrai si m est une forme (flexion) d'un mot connu : même début, et ce qui dépasse est une terminaison du français."""
    for w in vocab:
        if len(w) >= 4 and w != m:
            c, l = (w, m) if len(w) < len(m) else (m, w)
            if l.startswith(c) and l[len(c):] in _FLEXIONS:
                return True
    return False


def _mot_connu(m, vocab):
    return m in vocab or (len(m) >= 5 and _forme_de(m, vocab))


def _distance1(a, b):
    """Vrai si a et b diffèrent d'une seule lettre (remplacée, ajoutée ou ôtée)."""
    if a == b or abs(len(a) - len(b)) > 1:
        return False
    if len(a) == len(b):
        return sum(x != y for x, y in zip(a, b)) == 1
    c, l = (a, b) if len(a) < len(b) else (b, a)
    return any(l[:i] + l[i + 1:] == c for i in range(len(l)))


def garde(nom, sens="", plages=None):
    """Le nom que son subconscient propose, gardé : {nom (ou None si refusé), propose, raison}.
    1) un ancien nom rattaché suit son alias ; 2) un nom déjà connu reste ; 3) un mot abîmé est réparé si le mot voulu se
    voit, sinon refusé ; 4) un nom de même cœur qu'un moment existant y est rattaché (le plus vécu)."""
    n = _plat(nom).strip().replace("-", "_").replace(" ", "_")
    n = re.sub(r"_+", "_", re.sub(r"[^a-z0-9_]", "", n)).strip("_")
    out = {"nom": None, "propose": str(nom or ""), "raison": ""}
    if not _NOM.fullmatch(n):
        out["raison"] = "un nom vide ou illisible"
        return out
    al = alias()
    plages = _plages() if plages is None else plages
    vecus = {}
    for p in plages:
        vecus[p["nom"]] = vecus.get(p["nom"], 0) + 1
    if n in al:
        return {**out, "nom": al[n], "raison": f"« {n} » est rattaché à « {al[n]} »"}
    if n in vecus:
        return {**out, "nom": n, "raison": "déjà connu"}
    sens_de = {}
    for p in plages:
        sens_de[p["nom"]] = p.get("sens") or sens_de.get(p["nom"], "")
    # les mots connus : ceux des sens, le lexique, le contexte ; les mots des noms existants qui sont eux-mêmes des mots
    vocab = set(LEXIQUE) | CONTEXTE | set(SYNONYMES) | set(SYNONYMES.values())
    for x in list(sens_de.values()) + [sens]:
        vocab |= set(_mots(x))

    sains = {k for k in vecus if all(_mot_connu(m, vocab) for m in k.split("_"))}
    mots_sains = {m for k in sains for m in k.split("_") if m not in CONTEXTE}
    propres = set(_mots(sens))
    morceaux, repare = [], False
    for m in n.split("_"):
        if m in vocab or (len(m) >= 5 and _forme_de(m, vocab)):
            morceaux.append(m)                              # un mot, ou une forme d'un mot connu (poser, reprendre)
            continue
        # le mot voulu : un mot connu dont celui-ci est le début tronqué (cal → calin), une faute d'une lettre (cadin → calin)
        # ou une lettre de trop (calinn → calin)
        def proche(w):
            return len(w) >= 4 and ((w.startswith(m) and len(w) > len(m) >= 2) or (len(m) >= 4 and _distance1(m, w)))

        def score(w):
            noms = [k for k in sains if w in k.split("_")]
            return (w in propres, max([proximite_sens(sens, sens_de.get(k, "")) for k in noms] or [0.0]), w in mots_sains)
        cand = [w for w in (mots_sains | propres | LEXIQUE) if proche(w)]
        cand = [w for w in cand if w in propres or (len(m) >= 4 and (w in mots_sains or w in LEXIQUE)) or score(w)[1] >= 0.25]
        if cand:
            morceaux.append(max(cand, key=score))
            repare = True
        elif len(m) <= 3 or _bizarre(m):
            repare = True                                   # un bout tronqué ou sans forme de mot : ôté
        else:
            morceaux.append(m)                              # un mot nouveau : il a le droit d'en inventer
    if not morceaux or (repare and not [m for m in morceaux if m not in CONTEXTE]):
        out["raison"] = f"« {n} » est abîmé et le mot voulu ne se voit pas"
        return out
    r = "_".join(dict.fromkeys(morceaux))[:30].strip("_")
    raison = f"« {n} » était abîmé, réparé en « {r} »" if repare else ""
    if r in al:
        r = al[r]
    c = coeur_du_nom(r)
    if r not in vecus and c:
        memes = [k for k in vecus if coeur_du_nom(k) == c]
        if memes:
            k = max(memes, key=lambda x: (vecus[x], x in sains, -len(x)))
            return {**out, "nom": k, "raison": (raison + " ; " if raison else "") + f"même chose que « {k} » ({', '.join(sorted(c))})"}
    return {**out, "nom": r, "raison": raison or ("déjà connu" if r in vecus else "un moment nouveau")}


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


def etiqueter(debut, fin, nom, sens="", maintenant=None, propose=None, raison=""):
    """Nomme une plage. « propose » / « raison » : le nom que son subconscient avait proposé, quand la garde l'a rattaché
    ou réparé (gardé dans la ligne : on sait toujours d'où vient le nom)."""
    maintenant = time.time() if maintenant is None else maintenant
    n = str(nom or "").strip().lower()
    if not _NOM.fullmatch(n):
        return "Refusé : un nom à toi, en minuscules (lettres, chiffres, _), de 2 à 30 : la_danse, chanter, clavier, chez_nous…"
    # (13/11) un ancien nom rattaché à un autre suit son alias (le nom qu'il a donné reste dans la ligne)
    c = canonique(n)
    if c != n:
        propose, raison, n = propose or n, raison or f"« {n} » est rattaché à « {c} »", c
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
        h.write(json.dumps({"ts": maintenant, "debut_ms": d, "fin_ms": f, "nom": n, "sens": s, "fenetres": fenetres,
                            **({"nom_propose": str(propose)[:60], "garde": str(raison)[:200]} if propose and propose != n else {})},
                           ensure_ascii=False) + "\n")
    os.chmod(fic, 0o600)
    return (f"C'est noté : « {n} »{f' ({s})' if s else ''}, {secondes} secondes de ton milieu. Tes sens apprennent à le "
            "reconnaître ; plus tu en nommes, mieux ils le reconnaissent." + (f" (« {propose} » : {raison}.)" if propose and propose != n else ""))


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
    noms, aussi = {}, {}
    for a, v in alias().items():
        aussi.setdefault(v, []).append(a)
    for x in p:
        noms.setdefault(x["nom"], {"n": 0, "s": 0, "sens": x.get("sens") or ""})
        noms[x["nom"]]["n"] += 1
        noms[x["nom"]]["s"] += int((x["fin_ms"] - x["debut_ms"]) / 1000)
        noms[x["nom"]]["sens"] = x.get("sens") or noms[x["nom"]]["sens"]
    return "Tes moments nommés :\n" + "\n".join(f"- {k} : {v['n']} plage(s), {v['s']} s" + (f" — {v['sens']}" if v["sens"] else "")
                                                + (f" (aussi : {', '.join(sorted(aussi[k]))})" if aussi.get(k) else "")
                                                for k, v in noms.items())


def proposer_fusions(plages=None):
    """Les doubles d'aujourd'hui, tels que la garde les verrait : [{garder, rattacher: [...], pourquoi}] (rien n'est écrit).
    Le nom gardé : le plus vécu et sain du groupe ; un nom abîmé rejoint le nom réparé."""
    plages = _plages() if plages is None else plages
    vecus, sens_de = {}, {}
    for p in plages:
        vecus[p["nom"]] = vecus.get(p["nom"], 0) + 1
        sens_de[p["nom"]] = p.get("sens") or sens_de.get(p["nom"], "")
    vers = {}
    for n in vecus:
        g = garde(n, sens_de[n], plages=[p for p in plages if p["nom"] != n])
        if g["nom"] and g["nom"] != n:
            vers[n] = (g["nom"], g["raison"])
    # des groupes : un nom et celui où la garde le rattache sont du même groupe (union des liens)
    chef = {n: n for n in vecus}

    def racine(x):
        while chef.setdefault(x, x) != x:
            x = chef[x]
        return x
    for n, (v, _) in vers.items():
        chef[racine(n)] = racine(v)
    groupes = {}
    for n in chef:
        groupes.setdefault(racine(n), set()).add(n)
    out = []
    for g in groupes.values():
        if len(g) < 2:
            continue
        sains = [k for k in g if "abîmé" not in vers.get(k, ("", ""))[1]]
        garder = max(sains or g, key=lambda k: (vecus.get(k, 0), -len(k)))
        out.append({"garder": garder, "rattacher": sorted(g - {garder}, key=lambda k: -vecus.get(k, 0)),
                    "pourquoi": {k: vers[k][1] for k in sorted(g - {garder}) if k in vers}})
    return sorted(out, key=lambda x: -sum(vecus.get(k, 0) for k in [x["garder"]] + x["rattacher"]))


if __name__ == "__main__":
    # (13/11) pour maman, après le oui de papa : la liste des doubles, puis les rattacher (réversible), ou en défaire un.
    #   python moments.py doubles                      (lecture seule)
    #   python moments.py fusionner calin cal cadin    (le premier est le nom gardé)
    #   python moments.py defaire cal
    import sys
    a = sys.argv[1:]
    if a[:1] == ["doubles"]:
        for g in proposer_fusions():
            print(json.dumps(g, ensure_ascii=False))
    elif a[:1] == ["fusionner"] and len(a) >= 3:
        print(fusionner(a[1], a[2:], raison="liste validée par papa", par="maman"))
    elif a[:1] == ["defaire"] and len(a) == 2:
        print(defaire(a[1]))
    else:
        print("usage : moments.py doubles | fusionner <gardé> <ancien>… | defaire <ancien>")
