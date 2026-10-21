"""Le journal d'événements en ajout seul d'Anamnèse (lot E, point 7 de la liste de Hakim du 2026-10-19 ;
loi L10 de nos maths : « chaque brique est témoin »).

Pourquoi : le 15/10, le cœur d'identité avait été rongé au fil des écritures du démon, sans trace pour le
voir ni le défaire. Ici, chaque changement d'identité laisse un TÉMOIN :
- une ligne JSON par événement dans data/evenements.jsonl, jamais réécrite (ajout seul) ;
- chaque ligne porte l'empreinte (SHA-256) de la précédente : supprimer, réordonner ou modifier une ligne
  casse la chaîne, et `verifier` dit où ;
- l'identité se RECONSTRUIT depuis le journal (dernier témoin), et `ecart_identite` signale une écriture
  qui aurait contourné identity.py.
Le premier témoin d'un journal vide est une « genèse » : l'état tel qu'il était quand le journal est né.
"""
import contextlib
import fcntl
import hashlib
import json
import os
import time

import config

FICHIER = config.DATA_DIR / "evenements.jsonl"


def _empreinte(e):
    corps = {k: v for k, v in e.items() if k != "hash"}
    return hashlib.sha256(json.dumps(corps, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def lire(chemin=None):
    try:
        lignes = (chemin or FICHIER).read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for ligne in lignes:
        try:
            out.append(json.loads(ligne))
        except ValueError:
            out.append({"illisible": ligne[:80]})
    return out


def _dernier(chemin):
    """Le dernier événement, en ne lisant que la fin du fichier (le journal grandit à chaque souvenir)."""
    try:
        with open(chemin, "rb") as f:
            f.seek(0, os.SEEK_END)
            taille = f.tell()
            f.seek(max(0, taille - 65536))
            fin = f.read().decode("utf-8", errors="replace").strip().splitlines()
    except OSError:
        return None
    for ligne in reversed(fin):
        try:
            return json.loads(ligne)
        except ValueError:
            continue
    return None


@contextlib.contextmanager
def _verrou(chemin):
    """Un seul écrivain à la fois (relecture Opus du 2026-10-20 : deux sessions qui mémorisaient en même temps
    lisaient le même dernier événement et cassaient la chaîne pour toujours)."""
    chemin.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(chemin) + ".verrou", os.O_WRONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)


def _ancre(chemin):
    return chemin.with_name(chemin.name + ".ancre")


def ajouter(type_, donnees, source=None, chemin=None):
    """Ajoute un événement chaîné ; rend l'entrée écrite. L'ANCRE (numéro et empreinte du dernier événement,
    dans un fichier à part) fait voir une fin de journal coupée, que la chaîne seule ne voit pas."""
    chemin = chemin or FICHIER
    with _verrou(chemin):
        dernier = _dernier(chemin)
        prec = dernier.get("hash") if dernier else None
        e = {"n": (dernier.get("n", 0) if dernier else 0) + 1, "ts": round(time.time(), 3), "type": type_,
             "source": source or os.environ.get("ANAMNESE_SOURCE") or "anamnese", "donnees": donnees, "prec": prec}
        e["hash"] = _empreinte(e)
        fd = os.open(str(chemin), os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o644)
        try:
            os.write(fd, (json.dumps(e, ensure_ascii=False) + "\n").encode("utf-8"))
            os.fsync(fd)
        finally:
            os.close(fd)
        a = _ancre(chemin)
        tmp = a.with_name(a.name + f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps({"n": e["n"], "hash": e["hash"]}), encoding="utf-8")
        os.replace(tmp, a)
    return e


def verifier(chemin=None):
    """(intègre, nombre d'événements, numéro du premier événement cassé ou None). Une fin coupée (moins
    d'événements que l'ancre, ou un dernier événement qui n'est pas celui de l'ancre) est cassée au n° suivant."""
    chemin = chemin or FICHIER
    ev = lire(chemin)
    prec = None
    for i, e in enumerate(ev, 1):
        if "hash" not in e or e.get("prec") != prec or _empreinte(e) != e["hash"] or e.get("n") != i:
            return False, len(ev), i
        prec = e["hash"]
    try:
        a = json.loads(_ancre(chemin).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        a = None
    na = int((a or {}).get("n") or 0)
    if na and len(ev) < na:
        return False, len(ev), len(ev) + 1                    # des événements de la fin ont disparu
    if na and ev[na - 1].get("hash") != a.get("hash"):
        return False, len(ev), na                             # la fin a été réécrite
    return True, len(ev), None


def auteurs(chemin=None):
    """{id de souvenir: auteur} d'après les témoins « memoire » (lot E, point 17 : provenance)."""
    return {e["donnees"]["id"]: e.get("source") for e in lire(chemin)
            if e.get("type") == "memoire" and isinstance(e.get("donnees"), dict) and "id" in e["donnees"]}


def temoin_identite(mem, raison, chemin=None):
    """Le témoin d'un changement d'identité (appelé APRÈS la transaction réussie d'identity.py). Un journal
    vide reçoit d'abord la genèse : l'état d'avant, tel qu'on le trouve."""
    import identity
    chemin = chemin or FICHIER
    etat = {"coeur": identity.core(mem), "evolution": identity.evolution(mem), "raison": raison}
    if not lire(chemin):
        ajouter("genese", {"note": "naissance du journal d'événements"}, chemin=chemin)
    return ajouter("identite", etat, chemin=chemin)


def reconstruire_identite(chemin=None):
    """(cœur, évolution) d'après le dernier témoin ; (None, None) s'il n'y en a pas."""
    for e in reversed(lire(chemin)):
        if e.get("type") == "identite":
            d = e.get("donnees") or {}
            return d.get("coeur"), d.get("evolution")
    return None, None


def ecart_identite(mem, chemin=None):
    """None si l'identité en base est celle du dernier témoin ; sinon une description de l'écart (une
    écriture a contourné identity.py, ou le journal a été perdu)."""
    import identity
    coeur, evo = reconstruire_identite(chemin)
    if coeur is None:
        return "aucun témoin d'identité dans le journal"
    ecarts = []
    if identity.core(mem) != coeur:
        ecarts.append("le cœur en base diffère du dernier témoin")
    if identity.evolution(mem) != evo:
        ecarts.append("l'évolution en base diffère du dernier témoin")
    return " ; ".join(ecarts) or None
