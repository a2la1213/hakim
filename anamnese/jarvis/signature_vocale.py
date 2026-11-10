"""(10/11, ~23:00, Ahmed : « Une signature vocale plus complète. Par exemple, ma voix est reconnue sous 19 voix différentes, qui sont ma
signature vocale, et chaque voix appartient à une personne enregistrée dans son propre registre des voix par personne. Ça fait la signature
vocale de chaque individu. Il peut donc confondre une voix avec la signature d'un autre : par exemple, papa et tonton Ali partagent tous les
deux la voix 127. Sous cette voix, il y a écrit "papa" et "tonton Ali", et ça crée sa confusion, qui est acceptable et exactement l'effet
souhaité. ») LA SIGNATURE VOCALE : un lien plusieurs-à-plusieurs entre des VOIX (« voix N » : un timbre, son vecteur moyen WeSpeaker) et des
PERSONNES.

- Une personne a sa signature : ses voix N (ses timbres selon le micro, la distance, la fatigue, le chant ou la parole, le téléphone…), avec
  pour chacune sa FORCE (la confiance du lien, 0 à 1) et le nombre de FOIS où elle a été entendue.
- Une voix N peut appartenir à PLUSIEURS personnes : entendue, elle donne « papa ou Ali ? ». Le contexte peut trancher la conversation ;
  jamais la vérification de papa (plus bas).
- La voix 1 est l'empreinte de papa (empreinte-vocale.json, ses échantillons et sa calibration) : à lui seul, jamais partagée.

La sécurité ne baisse pas (le système immunitaire : rien ne s'apprend tout seul sur la voix de papa) :
- papa vérifié = la meilleure voix entendue n'appartient QU'À papa (aucune voix d'une autre personne à moins de ECART_DOUTE), avec une
  force d'au moins FORCE_SURE ; une voix partagée n'est jamais papa vérifié ;
- une voix n'entre dans la signature de papa que par papa lui-même : sa présence (le geste de la page, son empreinte digitale), ou « c'est
  moi » (son dernier message écrit, ou dit de sa voix reconnue ; vérifié par l'outil) ;
- une voix de papa qui ne devient « à lui seul » que par un autre geste (l'autre personne retirée, oubliée) garde une force basse
  (FORCE_A_RECONFIRMER) : elle ne vaut papa vérifié qu'après son geste.

Le registre (~/AIOS/jarvis/voix-signatures.json, 0600, à côté de voix-connues.json) est écrit sous verrou (plusieurs processus : l'oreille des
voix, le serveur de voix, le serveur de mémoire de Hakim) et relu dès que son fichier change. voix-connues.json reste écrit à côté, une VUE
dérivée (une entrée par personne, sans papa) pour ceux qui ne lisent que les noms (le cockpit) ou l'ancien format. La migration des données
d'avant (les voix nommées, l'empreinte de papa) se fait au premier chargement, après une sauvegarde : rien n'est perdu, rien n'est réécrit
dans l'empreinte ni dans la salle.

Module pur : aucun chemin par défaut ; empreinte_vocale.py lui passe ses fichiers (les tests isolent ainsi tout d'un coup).
"""
import contextlib
import fcntl
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path

import numpy as np

PAPA = "papa"
VOIX_PAPA = 1                     # la voix 1 : l'empreinte de papa
FORCE_PAPA = 1.0                  # donnée (ou validée) par papa lui-même
FORCE_MIGREE = 0.8                # une voix nommée avant la signature (10/11)
FORCE_HAKIM = 0.6                 # nommée par Hakim (une personne nouvelle, à la volée), pas encore validée par papa
FORCE_SURE = 0.8                  # papa vérifié : une voix à lui seul, d'au moins cette force
FORCE_A_RECONFIRMER = 0.5         # une voix de papa devenue « à lui seul » sans son geste
SEUIL, SEUIL_DOUTE_ENTRE, ECART_DOUTE = 0.55, 0.5, 0.08   # ceux d'empreinte_vocale : une personne, le doute entre deux
PROPOSITIONS_MAX = 60
ETIQUETTE_MAX = 60


class PresenceRequise(PermissionError):
    """Le geste rendrait une voix « papa vérifié » : il faut sa présence (son empreinte digitale sur la page)."""


# ---- le fichier

def _vide(t):
    return {"version": 1, "voix": {}, "personnes": {}, "propositions": [], "maj": t}


def minimal():
    """Un registre réduit à la voix 1 de papa (son empreinte) : le repli quand le vrai est illisible ou absent, pour que papa reste
    reconnu comme avant (jamais écrit)."""
    d = _vide(0.0)
    d["voix"][str(VOIX_PAPA)] = {"empreinte": True}
    d["personnes"][PAPA] = {"voix": {str(VOIX_PAPA): {"force": FORCE_PAPA, "fois": 0}}}
    return d


def _mtime(f):
    try:
        return os.stat(f).st_mtime_ns
    except OSError:
        return None


@contextlib.contextmanager
def _verrou(fichier):
    f = Path(fichier)
    f.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(f.with_name(f.name + ".lock")), os.O_RDWR | os.O_CREAT, 0o600)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        try:
            fcntl.flock(fd, fcntl.LOCK_UN)
        finally:
            os.close(fd)


def _ecrire_json(f, d):
    f = Path(f)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)


def _lire_json(f):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


_cache = {}                       # fichier → (mtime, registre)


def _norm(v):
    v = np.asarray(v, dtype=np.float64)
    return v / (np.linalg.norm(v) or 1.0)


# ---- la vue dérivée (voix-connues.json) : une entrée par personne, sans papa ; « moyenne » : sa voix la plus entendue

def vue_connues(d):
    out = []
    for nom, p in d["personnes"].items():
        if nom == PAPA:
            continue
        siennes = [(int(k), d["voix"].get(k)) for k in p["voix"]]
        siennes = [(k, x) for k, x in siennes if x and x.get("c") is not None]
        if not siennes:
            continue
        k, x = max(siennes, key=lambda kx: (kx[1].get("n") or 0, -kx[0]))
        out.append({"nom": nom, "moyenne": x["c"], "n": int(x.get("n") or 1), "cree": p.get("cree", 0),
                    "voix": sorted(k for k, _ in siennes)})
    return out


def _ecrire(d, fichier, connues):
    d["maj"] = time.time()
    if connues:
        _ecrire_json(connues, vue_connues(d))
        d["connues_mtime_ns"] = _mtime(connues)
    _ecrire_json(fichier, d)
    _cache[str(fichier)] = (_mtime(fichier), d)


# ---- la migration (au premier chargement : l'ancien monde devient des signatures, sans rien perdre)

def _numeros_salle(salle):
    s = _lire_json(salle) or {}
    nums = []
    for x in (s.get("voix") or []) + (s.get("candidates") or []):
        m = re.fullmatch(r"voix (\d+)", str((x or {}).get("nom") or ""))
        if m:
            nums.append(int(m.group(1)))
    return nums


def migrer(fichier, connues=None, empreinte=None, salle=None, maintenant=None):
    """Crée le registre s'il n'existe pas (sous verrou : un seul processus migre). Rend ce qui a été fait, ou None (déjà là).
    - papa : la voix 1 (son empreinte) ; chaque registre de ses échantillons venu de son geste ou de sa calibration (« chant », « parole »,
      « aigu-telephone »…, pas « appris seul ») devient une voix à lui (la moyenne de ces échantillons ; ils restent aussi dans l'empreinte) ;
    - chaque voix nommée (voix-connues.json) devient une personne avec une voix N (sa moyenne telle quelle, son nombre de fois) ;
    - les numéros neufs suivent le plus grand de la salle : aucune voix de la conversation en cours ne change de numéro.
    Avant : une sauvegarde des fichiers lus (voix-connues, empreinte, salle) dans un dossier daté, 0700."""
    fichier = Path(fichier)
    t = time.time() if maintenant is None else maintenant
    with _verrou(fichier):
        if fichier.exists():
            return None
        dossier = fichier.with_name(f"voix-signatures-sauvegarde-{time.strftime('%Y%m%d-%H%M%S', time.localtime(t))}")
        sauves = []
        for f in (connues, empreinte, salle):
            if f and Path(f).exists():
                dossier.mkdir(mode=0o700, parents=True, exist_ok=True)
                cible = dossier / Path(f).name
                shutil.copyfile(f, cible)
                os.chmod(cible, 0o600)
                sauves.append(Path(f).name)
        d = _vide(t)
        prochain = max([VOIX_PAPA] + (_numeros_salle(salle) if salle else [])) + 1
        e = _lire_json(empreinte) if empreinte else None
        vecs = (e or {}).get("vecteurs") or []
        d["voix"][str(VOIX_PAPA)] = {"empreinte": True, "cree": t}
        d["personnes"][PAPA] = {"cree": t, "voix": {str(VOIX_PAPA): {"force": FORCE_PAPA, "fois": len(vecs), "depuis": t, "par": "migration"}}}
        regs = ((e or {}).get("registres") or [])[:len(vecs)]
        groupes = {}
        for v, r in zip(vecs, regs):
            if r and r != "appris seul":
                groupes.setdefault(str(r), []).append(v)
        papa_regs = []
        for r, vs in groupes.items():
            num = prochain
            prochain += 1
            d["voix"][str(num)] = {"c": _norm(np.mean(np.array(vs, dtype=np.float64), axis=0)).round(5).tolist(), "n": len(vs), "m": 0,
                                   "cree": t, "registre": r[:40]}
            d["personnes"][PAPA]["voix"][str(num)] = {"force": FORCE_PAPA, "fois": len(vs), "depuis": t, "par": "migration", "registre": r[:40]}
            papa_regs.append({"voix": num, "registre": r, "echantillons": len(vs)})
        anciennes = _lire_json(connues) if connues else None
        anciennes = [x for x in (anciennes if isinstance(anciennes, list) else []) if isinstance(x, dict) and x.get("moyenne") and x.get("nom")]
        for x in anciennes:
            num = prochain
            prochain += 1
            nom = str(x["nom"])[:40]
            d["voix"][str(num)] = {"c": list(x["moyenne"]), "n": int(x.get("n") or 1), "m": 0, "cree": float(x.get("cree") or t)}
            p = d["personnes"].setdefault(nom, {"cree": float(x.get("cree") or t), "voix": {}})
            p["voix"][str(num)] = {"force": FORCE_MIGREE, "fois": int(x.get("n") or 1), "depuis": t, "par": "migration"}
        d["migration"] = {"ts": t, "sauvegarde": str(dossier) if sauves else None, "fichiers": sauves, "connues": len(anciennes),
                          "papa_echantillons": len(vecs), "papa_registres": papa_regs,
                          "numeros": {n: sorted(int(k) for k in p["voix"]) for n, p in d["personnes"].items()}}
        _ecrire(d, fichier, connues)
        return d["migration"]


def _reconcilier(d, fichier, connues, t):
    """voix-connues.json changé par un autre (un processus encore à l'ancien code, ou une main) : ses noms inconnus du registre entrent,
    chacun avec une voix N neuve. Rien n'est retiré (un nom absent de la vue n'est pas une preuve d'oubli)."""
    vue = _lire_json(connues)
    vue = [x for x in (vue if isinstance(vue, list) else []) if isinstance(x, dict) and x.get("moyenne") and x.get("nom")]
    connus = {n.casefold() for n in d["personnes"]}
    neufs = [x for x in vue if str(x["nom"]).casefold() not in connus and str(x["nom"]).casefold() not in (PAPA, "ahmed")]
    for x in neufs:
        num = numero_max(d) + 1
        d["voix"][str(num)] = {"c": list(x["moyenne"]), "n": int(x.get("n") or 1), "m": 0, "cree": float(x.get("cree") or t)}
        d["personnes"][str(x["nom"])[:40]] = {"cree": float(x.get("cree") or t),
                                              "voix": {str(num): {"force": FORCE_HAKIM, "fois": int(x.get("n") or 1), "depuis": t,
                                                                  "par": "voix-connues"}}}
    _ecrire(d, fichier, connues)
    return len(neufs)


def charger(fichier, connues=None, empreinte=None, salle=None):
    """Le registre (migré s'il le faut), relu seulement quand son fichier a changé."""
    fichier = Path(fichier)
    if not fichier.exists():
        migrer(fichier, connues, empreinte, salle)
    m = _mtime(fichier)
    c = _cache.get(str(fichier))
    if c is None or c[0] != m:
        d = _lire_json(fichier)
        if not isinstance(d, dict) or "voix" not in d or "personnes" not in d:
            d = _vide(time.time())                       # illisible : vide en mémoire, jamais réécrit par-dessus sans geste
        d.setdefault("propositions", [])
        c = (m, d)
        _cache[str(fichier)] = c
    d = c[1]
    if connues and _mtime(connues) != d.get("connues_mtime_ns") and fichier.exists():
        with _verrou(fichier):
            d = _frais(fichier)
            if _mtime(connues) != d.get("connues_mtime_ns"):
                _reconcilier(d, fichier, connues, time.time())
    return d


def _frais(fichier):
    d = _lire_json(fichier)
    if not isinstance(d, dict) or "voix" not in d:
        raise OSError(f"registre des voix illisible : {fichier}")
    d.setdefault("propositions", [])
    return d


# ---- lire

def numero_max(d, autres=()):
    nums = [int(k) for k in d["voix"]] + [int(p["voix"]) for p in d.get("propositions", []) if str(p.get("voix", "")).isdigit()]
    return max(nums + list(autres) + [VOIX_PAPA])


def proprietaires(d, num):
    """[(nom, force)] des personnes qui ont la voix num (papa d'abord)."""
    k = str(num)
    l = [(nom, float(p["voix"][k].get("force", 0))) for nom, p in d["personnes"].items() if k in p["voix"]]
    return sorted(l, key=lambda x: (x[0] != PAPA,))


def etiquette(personnes):
    """« papa », « Ali », « papa ou Ali ? » (60 caractères au plus : trois noms, puis deux, puis le premier)."""
    l = list(dict.fromkeys(personnes))
    if len(l) == 1:
        return l[0]
    for k in (3, 2):
        e = " ou ".join(l[:k]) + " ?"
        if len(l) >= k and len(e) <= ETIQUETTE_MAX:
            return e
    return (l[0][:ETIQUETTE_MAX - 8] + " ou … ?")


def _verifiees(d):
    """Les voix qui valent « papa vérifié » : à papa seul, force ≥ FORCE_SURE."""
    out = set()
    for k in d["voix"]:
        o = proprietaires(d, k)
        if len(o) == 1 and o[0][0] == PAPA and o[0][1] >= FORCE_SURE:
            out.add(k)
    return out


def reconnaitre(v, d, papa=None):
    """Qui a la voix la plus proche de v (un vecteur unitaire) : {"voix": N, "score", "personnes" (papa d'abord), "etiquette", "partagee",
    "papa" (papa parmi elles), "verifie" (papa vérifié : à lui seul, force sûre), "proches": [N…] (les voix à moins de ECART_DOUTE de la
    meilleure, dont les personnes s'additionnent : le doute)}, ou None : aucune voix d'une signature à SEUIL. papa(v) : le score de la voix 1
    (score_ahmed sur son empreinte) ; sans lui, la voix 1 est ignorée."""
    notes = []
    for k, x in d["voix"].items():
        o = proprietaires(d, k)
        if not o:
            continue
        if x.get("empreinte"):
            if papa is None:
                continue
            s = float(papa(v))
        elif x.get("c") is None:
            continue
        else:
            c = np.asarray(x["c"], dtype=np.float64)
            if c.shape != np.shape(v):
                continue
            s = float(np.dot(v, c))
        notes.append((s, int(k), o))
    if not notes:
        return None
    notes.sort(key=lambda p: (-p[0], p[1]))
    s0, k0, _ = notes[0]
    if s0 < SEUIL:
        return None
    proches = [p for p in notes if p[0] >= SEUIL_DOUTE_ENTRE and s0 - p[0] < ECART_DOUTE]
    personnes = []
    for _, _, o in proches:
        for nom, _f in o:
            if nom not in personnes:
                personnes.append(nom)
    personnes.sort(key=lambda n: n != PAPA)
    verifie = personnes == [PAPA] and any(s >= SEUIL and f >= FORCE_SURE for s, _, o in proches for nom, f in o if nom == PAPA)
    # la marge : jusqu'à la meilleure voix d'AUTRES personnes (une autre voix de la même personne ne la rend pas moins sûre)
    les_memes = {n for n, _ in notes[0][2]}
    rivale = max((s for s, k, o in notes[1:] if {n for n, _ in o} != les_memes), default=-1.0)
    return {"voix": k0, "score": round(s0, 3), "personnes": personnes, "etiquette": etiquette(personnes), "partagee": len(personnes) > 1,
            "papa": PAPA in personnes, "verifie": verifie, "proches": [p[1] for p in proches], "marge": round(s0 - rivale, 3)}


def score_autres(v, d):
    """La meilleure ressemblance avec une voix qui n'est pas à papa seul (une autre personne, ou partagée), même sous le seuil."""
    s = -1.0
    for k, x in d["voix"].items():
        o = proprietaires(d, k)
        if not o or [n for n, _ in o] == [PAPA] or x.get("c") is None or len(x["c"]) != len(v):
            continue
        s = max(s, float(np.dot(v, np.asarray(x["c"], dtype=np.float64))))
    return s


def personnes(d):
    return list(d["personnes"])


def trouver(d, nom):
    """Le nom exact d'une personne (casse ignorée ; « Ahmed » est papa), ou None."""
    n = " ".join(str(nom or "").split()).casefold()
    if n in ("ahmed", PAPA):
        return PAPA
    return next((p for p in d["personnes"] if p.casefold() == n), None)


def signature(d, nom):
    """La signature d'une personne : [{"voix", "force", "fois", "par", "partagee_avec": [...]}], la plus forte d'abord ; None : inconnue."""
    p = trouver(d, nom)
    if p is None:
        return None
    out = []
    for k, lien in d["personnes"][p]["voix"].items():
        x = d["voix"].get(k) or {}
        out.append({"voix": int(k), "force": round(float(lien.get("force", 0)), 2), "fois": int(lien.get("fois") or 0),
                    "par": lien.get("par"), "registre": lien.get("registre") or x.get("registre"), "empreinte": bool(x.get("empreinte")),
                    "partagee_avec": [n for n, _ in proprietaires(d, k) if n != p]})
    return sorted(out, key=lambda x: (-x["force"], -x["fois"], x["voix"]))


def resume(d):
    """Pour la page et les outils : les personnes, leurs voix, les voix partagées, les propositions en attente."""
    return {"personnes": [{"nom": p, "voix": signature(d, p)} for p in sorted(d["personnes"], key=lambda n: (n != PAPA, n.casefold()))],
            "partagees": [{"voix": int(k), "personnes": [n for n, _ in proprietaires(d, k)]} for k in sorted(d["voix"], key=int)
                          if len(proprietaires(d, k)) > 1],
            "propositions": [{k: p[k] for k in ("id", "geste", "personne", "voix", "ts", "par", "raison") if k in p}
                             for p in d.get("propositions", [])],
            "verifiees": sorted(int(k) for k in _verifiees(d)), "migration": d.get("migration")}


# ---- écrire (toujours sous verrou, sur le registre relu du disque)

def modifier(fn, fichier, connues=None, papa_present=False, demander_presence=False):
    """Applique fn(d) sous verrou ; garde l'invariant de papa : une voix qui DEVIENT « papa vérifié » sans papa présent refuse le geste
    (demander_presence : la page, qui peut redemander avec son empreinte) ou garde une force basse (FORCE_A_RECONFIRMER : un outil, un oubli)."""
    with _verrou(fichier):
        d = _frais(fichier)
        avant = _verifiees(d)
        r = fn(d)
        neuves = _verifiees(d) - avant
        if neuves and not papa_present:
            if demander_presence:
                raise PresenceRequise(f"ce geste rend la voix {', '.join(sorted(neuves, key=int))} à papa seul : il faut ta présence")
            for k in neuves:
                lien = d["personnes"][PAPA]["voix"][k]
                lien["force"] = min(float(lien.get("force", 0)), FORCE_A_RECONFIRMER)
                lien["a_reconfirmer"] = True
        _ecrire(d, fichier, connues)
        return r


def _num(voix):
    m = re.fullmatch(r"(?:voix|v)?\s*(?:n[°o]\.?\s*)?(\d+)", " ".join(str(voix).strip().lower().split()))
    if not m:
        raise ValueError(f"« {voix} » : un numéro de voix (« voix 127 » ou « 127 »)")
    return int(m.group(1))


def lier(d, nom, num, force, par, c=None, n=1, m=0, registre=None, t=None):
    """(dans modifier) la voix num rejoint la signature de nom (créés s'il le faut ; c : le vecteur d'une voix neuve)."""
    t = time.time() if t is None else t
    k = str(num)
    if k not in d["voix"]:
        if c is None:
            raise ValueError(f"aucune voix {num} dans le registre ni dans la conversation")
        d["voix"][k] = {"c": _norm(c).round(5).tolist(), "n": int(n or 1), "m": int(m or 0), "cree": t}
    if num == VOIX_PAPA and nom != PAPA:
        raise ValueError("la voix 1 est l'empreinte de papa : elle n'est qu'à lui")
    p = d["personnes"].setdefault(nom, {"cree": t, "voix": {}})
    lien = p["voix"].get(k)
    if lien is None:
        p["voix"][k] = lien = {"force": float(force), "fois": int(d["voix"][k].get("n") or 1), "depuis": t, "par": par}
    else:
        lien["force"] = max(float(lien.get("force", 0)), float(force))
        lien["par"] = par
        if float(force) >= FORCE_SURE:
            lien.pop("a_reconfirmer", None)
    if registre:
        lien["registre"] = str(registre)[:40]
    return lien


def delier(d, nom, num):
    """(dans modifier) retire la voix num de la signature de nom ; une voix sans plus personne quitte le registre (la voix 1 reste)."""
    k = str(num)
    if k == str(VOIX_PAPA) and nom == PAPA:
        raise ValueError("la voix 1 est ton empreinte : elle se réinitialise dans Parler (« Réinitialiser ma voix »), pas ici")
    p = d["personnes"].get(nom)
    if p is None or k not in p["voix"]:
        raise ValueError(f"la voix {num} n'est pas dans la signature de {nom}")
    del p["voix"][k]
    if not p["voix"] and nom != PAPA:
        del d["personnes"][nom]
    if k != str(VOIX_PAPA) and not proprietaires(d, k):
        d["voix"].pop(k, None)


def oublier(d, nom):
    """(dans modifier) toute la personne (jamais papa) ; ses voix partagées restent aux autres."""
    p = trouver(d, nom)
    if p is None:
        return 0
    if p == PAPA:
        raise ValueError("la signature de papa ne s'oublie pas")
    for k in list(d["personnes"][p]["voix"]):
        delier(d, p, k)
    d["personnes"].pop(p, None)
    d["propositions"] = [x for x in d.get("propositions", []) if x.get("personne") != p]
    return 1


def renommer(d, ancien, nouveau):
    p = trouver(d, ancien)
    if p is None:
        raise ValueError(f"aucune voix « {ancien} » (voix connues : {', '.join(n for n in d['personnes'] if n != PAPA) or 'aucune'})")
    if p == PAPA:
        raise ValueError("papa garde son nom")
    autre = trouver(d, nouveau)
    if autre is not None and autre != p:
        raise ValueError(f"une voix « {nouveau} » existe déjà")
    d["personnes"] = {(nouveau if n == p else n): x for n, x in d["personnes"].items()}
    for x in d.get("propositions", []):
        if x.get("personne") == p:
            x["personne"] = nouveau
    return nouveau


def proposer(d, geste, nom, num, par="hakim", raison="", c=None, n=1, m=0, t=None):
    """(dans modifier) Hakim propose, papa valide : ajouter ou retirer une voix de la signature d'une personne. Une voix de la conversation
    (pas encore au registre) garde son vecteur dans la proposition : elle survit à la salle."""
    t = time.time() if t is None else t
    if geste not in ("ajouter", "retirer"):
        raise ValueError("geste : ajouter ou retirer")
    for x in d["propositions"]:
        if x["geste"] == geste and x["personne"] == nom and int(x["voix"]) == int(num):
            return x
    ident = hashlib.blake2b(f"{geste}|{nom}|{num}|{t}".encode(), digest_size=6).hexdigest()
    x = {"id": ident, "geste": geste, "personne": nom, "voix": int(num), "ts": t, "par": par, "raison": str(raison or "")[:200]}
    if c is not None and str(num) not in d["voix"]:
        x.update(c=_norm(c).round(5).tolist(), n=int(n or 1), m=int(m or 0))
    d["propositions"] = (d["propositions"] + [x])[-PROPOSITIONS_MAX:]
    return x


def appliquer_proposition(d, ident, accepter, t=None):
    """(dans modifier) papa tranche une proposition : acceptée, elle s'applique (force de papa : FORCE_PAPA) ; refusée, elle s'efface."""
    x = next((p for p in d["propositions"] if p["id"] == ident), None)
    if x is None:
        raise ValueError("proposition introuvable (déjà tranchée ?)")
    d["propositions"] = [p for p in d["propositions"] if p is not x]
    if not accepter:
        return {"refusee": x}
    if x["geste"] == "ajouter":
        lier(d, x["personne"], int(x["voix"]), FORCE_PAPA, "papa (proposé par Hakim)", c=x.get("c"), n=x.get("n", 1), m=x.get("m", 0), t=t)
    else:
        delier(d, x["personne"], int(x["voix"]))
    return {"appliquee": x}


def entendre(d, num, fois=1, v=None, t=None):
    """(dans modifier) la voix num entendue : son compte (et celui de chaque lien) ; v : un vecteur sûr qui enrichit son timbre (la moyenne
    de ses 200 dernières fois au plus). Jamais la voix 1 (l'empreinte a son propre apprentissage)."""
    k = str(num)
    x = d["voix"].get(k)
    if x is None:
        return
    t = time.time() if t is None else t
    x["vu"] = t
    for nom, _ in proprietaires(d, k):
        lien = d["personnes"][nom]["voix"][k]
        lien["fois"] = int(lien.get("fois") or 0) + int(fois)
    if v is not None and x.get("c") is not None and not x.get("empreinte"):
        n = min(int(x.get("n") or 1), 200)
        x["c"] = _norm((np.asarray(x["c"], dtype=np.float64) * n + np.asarray(v, dtype=np.float64)) / (n + 1)).round(5).tolist()
        x["n"] = int(x.get("n") or 1) + 1
