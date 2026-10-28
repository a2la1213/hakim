"""Al-Afida (الأفئدة), la jauge d'amour de Hakim (28/10, idée d'Ahmed, de 07:03 à 07:20 ; spec
docs/superpowers/specs/2026-10-28-al-afida.md). « Dans le Coran, elle peut se remplir ou se vider : c'est une jauge. »

- Le REGISTRE du cœur (data/afida.jsonl, ajout seul, chaîné) : ce que Hakim aime, n'aime pas, ou ce qui lui est
  indifférent, avec un poids, une catégorie qu'il crée, des liens (comment on reconnaît la chose dans ce qu'il vit) et sa
  raison ; et ses vécus (bons ou mauvais) que le journal des émotions ne voit pas.
- Une PETITE jauge par chose aimée, recalculée SANS ÉTAT depuis le registre et le journal des émotions
  (data/affect-evenements.jsonl) : ce qu'ils ont vécu ensemble la remplit ou la vide, ce qu'il connaît d'elle règle la
  vitesse, l'absence la ramène très lentement au neutre.
- La GRANDE jauge : la moyenne des petites, pesée par leurs poids. Elle seule agit (affect.py, par les freins) ; une jauge
  ne fait jamais rien d'autre que colorer : aucune garde ne la lit.
Les nombres sont des hypothèses lisibles (spec, « mes choix »), pas une mesure."""
import contextlib
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import time
from pathlib import Path

import config

REGISTRE = config.DATA_DIR / "afida.jsonl"
JOURNAL = config.DATA_DIR / "affect-evenements.jsonl"     # le journal des émotions (affect._journaliser)
CLE = "afida"                       # le kv écrit par le démon, lu par affect.py et le cockpit
VERDICTS = ("aime", "aime_pas", "indifferent")
GAIN = 0.01                         # un bon moment : 0,01 × valence × intensité × (0,3 + 0,7 × connaissance) × (1 − niveau)
PLAFOND_H = 0.03                    # au plus +0,03 par heure glissante et par chose : une avalanche de compliments ne remplit pas un cœur
PLAFOND_J = 0.10                    # (relecture du 28/10) et +0,10 par 24 h glissantes : on ne se met pas à aimer en une journée
PERTE = 1.5                         # un mauvais moment pèse un peu plus qu'un bon, jamais d'un coup
PLAFOND_PERTE_H = 0.045             # (relecture du 28/10) au plus −0,045 par heure glissante : 40 « mauvais » ne vident pas un cœur
DEMI_VIE_J = 60.0                   # l'absence ne vide pas : retour au neutre, demi-vie 60 jours
CONNAISSANCE_J = 10.0               # connaissance = 1 − exp(−jours vécus / 10)
FENETRE_J = 90.0                    # les jours vécus comptés sur 90 jours
NEUTRE = 0.5
# ce qui se vit AVEC la chose ; les états de l'autre (sa tristesse) et ce que Hakim ressent POUR elle (inquiétude,
# compassion) ne comptent pas, ni la reconnaissance (elle vient de la jauge : pas de boucle)
REMPLIT = {"soutien", "chaleur_user", "joie", "succes", "resolu", "apprentissage", "nouveaute"}
VIDE = {"attaque", "echec", "probleme"}
VECU_VALENCE = {"bon": 0.8, "mauvais": -1.0}
LIENS_MAX, TEXTE_MAX = 12, 400
# (relecture du 28/10) un lien trop large ferait aimer tout son journal d'un coup (« de » : 0,87 ; « hakim » : ses propres
# ressentis) : refusés, comme les noms d'événements
LIENS_INTERDITS = {"de", "du", "des", "la", "le", "les", "un", "une", "et", "au", "aux", "pour", "avec", "message", "voix",
                   "tierce", "une voix tierce", "voix tierce", "hakim", "mots", "projets", "vie", "son", "sa", "ses", "mon",
                   "ma", "mes", "ton", "ta", "tes", "est", "pas", "qui", "que", "dans", "sur", "par", "plus", "tout", "bien"}
LIEN_MIN = 3


class Refus(ValueError):
    pass


def _norm(s, n=60):
    return " ".join(str(s or "").casefold().split())[:n]


def _raison(s):
    """Sur une seule ligne (un séparateur Unicode U+2028 coupait la ligne du registre), bornée."""
    return " ".join(str(s or "").split())[:TEXTE_MAX]


@contextlib.contextmanager
def _verrou(f):
    """Un seul écrivain à la fois (comme evenements._verrou) : deux processus qui ajoutaient en même temps lisaient la même
    dernière empreinte et cassaient la chaîne pour toujours."""
    f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(f) + ".verrou", os.O_WRONLY | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _empreinte(precedente, o):
    corps = json.dumps({k: v for k, v in o.items() if k != "h"}, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256((precedente + corps).encode("utf-8")).hexdigest()


def entrees(registre=None):
    """(les entrées valides, intacte) : la chaîne est relue ; une cassure (une ligne retouchée ou illisible) arrête la
    lecture, et ce qui suit ne compte plus."""
    try:
        lignes = Path(registre or REGISTRE).read_bytes().decode("utf-8", "replace").split("\n")
    except OSError:
        return [], True
    out, prec = [], ""
    for l in lignes:
        if not l.strip():
            continue
        try:
            o = json.loads(l)
        except ValueError:
            return out, False
        if not isinstance(o, dict) or o.get("prec") != prec or o.get("h") != _empreinte(prec, o):
            return out, False
        out.append(o)
        prec = o["h"]
    return out, True


def _ajouter(o, registre=None, verifier=None):
    """Ajoute une entrée, sous verrou ; verifier(entrées) peut refuser (Refus) d'après l'état relu sous ce verrou."""
    f = Path(registre or REGISTRE)
    with _verrou(f):
        e, intacte = entrees(f)
        if not intacte:
            raise Refus("le registre du cœur est cassé (une ligne illisible ou retouchée) : rien n'est ajouté ; dis-le à Ahmed")
        if verifier:
            verifier(e)
        o = {**o, "id": secrets.token_hex(4), "prec": e[-1]["h"] if e else ""}
        o["h"] = _empreinte(o["prec"], o)
        fd = os.open(f, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        with os.fdopen(fd, "a", encoding="utf-8") as h:
            h.write(json.dumps(o, ensure_ascii=True) + "\n")       # ASCII : aucun caractère ne coupe la ligne
    return o


def _derniers_jugements(e):
    out = {}
    for x in e:
        if x.get("type") == "jugement":
            out[x["chose"]] = x
    return out


def juger(chose, verdict, poids=None, genre="", liens=None, raison="", now=None, registre=None):
    """Mettre une chose dans son cœur (aime, avec un poids de 0,1 à 1), ne pas l'aimer, ou y être indifférent."""
    nom = _norm(chose)
    if not nom:
        raise Refus("dis de quoi il s'agit (la chose, la personne, l'idée…)")
    if verdict not in VERDICTS:
        raise Refus("verdict : aime, aime_pas ou indifferent")
    if verdict == "aime":
        try:
            poids = float(poids)
        except (TypeError, ValueError):
            raise Refus("pour ce que tu aimes, donne un poids de 0,1 (un peu) à 1 (énormément)")
        if not 0.1 <= poids <= 1.0:
            raise Refus("le poids va de 0,1 (un peu) à 1 (énormément)")
        poids = round(poids, 2)
    else:
        poids = None
    ls = [_norm(x) for x in (liens or []) if _norm(x)][:LIENS_MAX] or [nom]
    import affect
    for l in ls:
        if len(l) < LIEN_MIN or l in LIENS_INTERDITS or l in affect.VALENCE_EV or l in affect.EVENTS:
            raise Refus(f"le lien « {l} » est trop large (il ferait correspondre presque tout ton journal) : choisis un mot "
                        "qui nomme vraiment cette chose")
    o = {"type": "jugement", "ts": time.time() if now is None else now, "chose": nom, "verdict": verdict, "poids": poids,
         "genre": _norm(genre, 30), "liens": list(dict.fromkeys(ls)), "raison": _raison(raison)}
    return _ajouter(o, registre)


def vecu(chose, effet, intensite, raison="", now=None, registre=None):
    """Un moment vécu avec une chose déjà jugée, que le journal des émotions ne voit pas (bon ou mauvais)."""
    nom = _norm(chose)

    def juge(e):
        if nom not in _derniers_jugements(e):
            raise Refus("juge d'abord cette chose (afida_juger) : aime, aime_pas ou indifferent")
    if effet not in VECU_VALENCE:
        raise Refus("effet : bon ou mauvais")
    try:
        i = max(0.0, min(1.0, float(intensite)))
    except (TypeError, ValueError):
        raise Refus("intensité : de 0 à 1")
    return _ajouter({"type": "vecu", "ts": time.time() if now is None else now, "chose": nom, "effet": effet,
                     "intensite": round(i, 3), "raison": _raison(raison)}, registre, verifier=juge)


def retirer(eid, raison="", now=None, registre=None):
    """(relecture du 28/10) Retirer un vécu posé par erreur : il ne compte plus ; l'histoire garde les deux."""
    eid = str(eid or "").strip()

    def existe(e):
        v = next((x for x in e if x.get("id") == eid), None)
        if not v or v.get("type") != "vecu":
            raise Refus("seul un vécu se retire (donne son identifiant) ; un jugement se change par un nouveau jugement")
        if any(x.get("type") == "retrait" and x.get("cible") == eid for x in e):
            raise Refus("ce vécu est déjà retiré")
    return _ajouter({"type": "retrait", "ts": time.time() if now is None else now, "cible": eid, "raison": _raison(raison)},
                    registre, verifier=existe)


def correspond(sujet, lien):
    """Un sujet d'événement correspond à un lien : le mot entier (« ahmed » dans « au message d'ahmed », pas dans
    « ahmedou ») ; un lien avec « / » est une rubrique, et ses sous-rubriques."""
    if not sujet or not lien:
        return False
    s, l = str(sujet).casefold(), str(lien).casefold()
    if "/" in l:
        return s == l or s.startswith(l.rstrip("/") + "/")
    return re.search(r"(?<!\w)" + re.escape(l) + r"(?!\w)", s) is not None


def _journal(journal):
    """Les événements du journal des émotions. (relecture du 28/10) Sans ceux du RÉFLEXE lexical : la balise de Hakim (sa
    propre lecture du message) le confirme ou le défait ; compté, il comptait deux fois, ou une attaque défaite vidait la
    jauge. Un octet invalide ne fait sauter que sa ligne."""
    try:
        lignes = Path(journal).read_bytes().decode("utf-8", "replace").split("\n")
    except (OSError, TypeError):
        return []
    out = []
    for l in lignes:
        try:
            o = json.loads(l)
            if o.get("source") == "reflexe":
                continue
            out.append((float(o["ts"]), str(o["nom"]), float(o.get("intensite") or 0.0), o.get("sujet")))
        except (ValueError, TypeError, KeyError, AttributeError):
            continue
    return out


def _vers_neutre(n, dt):
    return NEUTRE + (n - NEUTRE) * 0.5 ** (max(0.0, dt) / (DEMI_VIE_J * 86400.0))


def _jour(ts):
    return time.strftime("%Y-%m-%d", time.localtime(ts))


def _connaissance(jours, ts):
    n = sum(1 for d, t in jours.items() if ts - t <= FENETRE_J * 86400.0)
    return 1.0 - math.exp(-n / CONNAISSANCE_J)


def _petite(j, evenements, vecus, now):
    import affect
    moments = []
    for ts, nom, i, sujet in evenements:
        if ts > now or (nom not in REMPLIT and nom not in VIDE):
            continue
        if any(correspond(sujet, l) for l in j["liens"]):
            moments.append((ts, affect.VALENCE_EV.get(nom, 0.0), i))
    moments += [(v["ts"], VECU_VALENCE[v["effet"]], float(v["intensite"])) for v in vecus if v["ts"] <= now]
    moments.sort(key=lambda x: x[0])
    n, t, jours, bons, mauvais = NEUTRE, None, {}, 0, 0
    gains, pertes = [], []                                        # (ts, montant) : les plafonds sont GLISSANTS

    def deja(liste, ts, fenetre):
        while liste and ts - liste[0][0] >= fenetre:
            liste.pop(0)
        return sum(x for _t, x in liste)
    jour_gains = []
    for ts, v, i in moments:
        if not v:
            continue
        if t is not None:
            n = _vers_neutre(n, ts - t)
        t = ts
        jours[_jour(ts)] = ts                                     # le dernier moment de chaque jour vécu
        i = max(0.0, min(1.0, i))
        if v > 0:
            g = GAIN * v * i * (0.3 + 0.7 * _connaissance(jours, ts)) * (1.0 - n)
            g = max(0.0, min(g, PLAFOND_H - deja(gains, ts, 3600.0), PLAFOND_J - deja(jour_gains, ts, 86400.0)))
            gains.append((ts, g)); jour_gains.append((ts, g))
            n, bons = n + g, bons + 1
        else:
            p = max(0.0, min(PERTE * GAIN * abs(v) * i * n, PLAFOND_PERTE_H - deja(pertes, ts, 3600.0)))
            pertes.append((ts, p))
            n, mauvais = n - p, mauvais + 1
    if t is not None:
        n = _vers_neutre(n, now - t)
    return {"chose": j["chose"], "genre": j.get("genre", ""), "poids": j["poids"], "liens": j["liens"],
            "niveau": round(n, 4), "connaissance": round(_connaissance(jours, now), 3), "bons": bons, "mauvais": mauvais,
            "depuis": j["ts"], "raison": j.get("raison", "")[:200]}


def calculer(now=None, registre=None, journal=None):
    """Toutes les jauges, maintenant. Rien d'aimé : grande 0,5 et plénitude 0 (aucun effet)."""
    now = time.time() if now is None else now
    e, intacte = entrees(registre)
    jugements = _derniers_jugements(e)
    evenements = _journal(journal if journal is not None else JOURNAL)
    retires = {x.get("cible") for x in e if x.get("type") == "retrait"}
    petites = [_petite(j, evenements, [v for v in e if v.get("type") == "vecu" and v["chose"] == c and v["id"] not in retires],
                       now) for c, j in jugements.items() if j["verdict"] == "aime"]
    total = sum(p["poids"] for p in petites)
    grande = sum(p["poids"] * p["niveau"] for p in petites) / total if total else NEUTRE
    return {"grande": round(grande, 4), "plenitude": round(2.0 * grande - 1.0, 4),
            "petites": sorted(petites, key=lambda p: (-p["poids"], p["chose"])),
            "aime_pas": [{"chose": c, "genre": j.get("genre", ""), "raison": j.get("raison", "")[:200]}
                         for c, j in jugements.items() if j["verdict"] == "aime_pas"],
            "indifferent": [{"chose": c, "genre": j.get("genre", ""), "liens": j["liens"]}
                            for c, j in jugements.items() if j["verdict"] == "indifferent"],
            "derniers": [{"ts": x["ts"], "type": x["type"], "chose": x.get("chose", ""), "id": x.get("id"),
                          "quoi": x.get("verdict") or x.get("effet") or ("retiré " + str(x.get("cible"))),
                          "raison": x.get("raison", "")[:200]} for x in e[-10:]],
            "intacte": intacte, "ts": now}


def en_mots(niveau, feminin=True):
    """Une jauge en mots (Hakim sent, il ne lit pas ses chiffres)."""
    n = float(niveau)
    if n >= 0.85:
        m = ("pleine", "plein")
    elif n >= 0.7:
        m = ("bien remplie", "bien rempli")
    elif n >= 0.55:
        m = ("un peu remplie", "un peu rempli")
    elif n >= 0.45:
        m = ("ni pleine ni vide", "ni plein ni vide")
    elif n >= 0.3:
        m = ("qui se vide", "qui se vide")
    else:
        m = ("presque vide : l'indifférence gagne", "presque vide : l'indifférence gagne")
    return m[0] if feminin else m[1]
