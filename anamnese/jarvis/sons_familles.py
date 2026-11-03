"""(03/11, Ahmed : « micro ouvert, jamais fermé ; on le laisse apprendre à détecter les sons, les bruits, les voix qui se
mélangent, une seule voix… il faut qu'il apprenne de lui-même à écouter et à focaliser son attention ») ses familles de sons.

Un instant de ce qu'il entend (3 s d'ambiance, envoyées par la page quand le micro est ouvert) devient une forme : ce que
l'encodeur du petit Whisper en comprend (jarvis/stt_vif.py ; la moyenne et l'écart de ses 768 sorties dans le temps).
Toutes ces formes se ressemblent beaucoup (essai du 03/11 : une voix et une musique à 0,97) ; ce qui les distingue, c'est
leur écart à la moyenne de TOUT ce qu'il a entendu (voix et musique tombent à 0,3-0,5, deux voix restent à 0,74). D'où :
il écoute d'abord (ECOUTE_MIN sons, sans rien ranger : sa moyenne se forme), puis il range seul, en familles (« son 1 »,
« son 2 »…) ; chaque famille retient combien de fois elle est venue, avec de la parole ou non, avec plusieurs voix ou une
seule. Hakim les nomme lui-même (« la télé », « la rue », « papa et ses potes ») : nommée, une famille est reconnue par son
nom pour toujours. Rien de l'audio n'est gardé : la forme (des nombres) et des compteurs. ~/AIOS/jarvis/sons-familles.json.
"""
import json
import os
import re
import time
from pathlib import Path

import numpy as np

FICHIER = Path.home() / "AIOS" / "jarvis" / "sons-familles.json"
ECOUTE_MIN = 20               # il écoute d'abord : sa moyenne de tout ce qu'il entend se forme
SEUIL_FAMILLE = 0.6           # la ressemblance (cosinus, écart à sa moyenne) pour être de la même famille
FAMILLES_MAX = 60
MOYENNE_POIDS_MAX = 1000      # la moyenne suit lentement ce qu'il entend (les derniers ~1 000 sons)


def _centre(v, moyenne):
    x = np.asarray(v, dtype=np.float64) - moyenne
    return x / (np.linalg.norm(x) or 1.0)


def _lire(fichier=None):
    try:
        return json.loads(Path(fichier or FICHIER).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"familles": [], "suivant": 1, "entendus": 0}


def _ecrire(d, fichier=None):
    f = Path(fichier or FICHIER)
    f.parent.mkdir(parents=True, exist_ok=True)
    tmp = f.with_name(f.name + f".{os.getpid()}.tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
    os.chmod(tmp, 0o600)
    os.replace(tmp, f)


def entendre(vecteur, fichier=None, maintenant=None, parole=None, voix=0):
    """Range ce qu'il entend : {"famille": son nom, "id", "nouvelle": bool, "fois", "ressemblance"} ; None tant qu'il écoute
    encore (ses ECOUTE_MIN premiers sons), ou pour un vecteur vide."""
    v = np.asarray(vecteur, dtype=np.float64).ravel()
    if not v.size or not np.isfinite(v).all():
        return None
    t = time.time() if maintenant is None else maintenant
    d = _lire(fichier)
    n_tout = int(d.get("entendus", 0)) + 1
    moyenne = np.asarray(d.get("moyenne") or v, dtype=np.float64)
    if moyenne.shape != v.shape:                       # un autre encodeur qu'avant : il réapprend tout
        d, n_tout, moyenne = {"familles": [], "suivant": 1}, 1, v.copy()
    moyenne = moyenne + (v - moyenne) / min(n_tout, MOYENNE_POIDS_MAX)
    d["entendus"], d["moyenne"] = n_tout, moyenne.round(5).tolist()
    if n_tout <= ECOUTE_MIN:
        _ecrire(d, fichier)
        return None
    c = _centre(v, moyenne)
    fam = d.setdefault("familles", [])
    proches = [(float(np.dot(c, _centre(x["c"], moyenne))), x) for x in fam]
    s, x = max(proches, key=lambda p: p[0]) if proches else (-1.0, None)
    nouvelle = x is None or s < SEUIL_FAMILLE
    if nouvelle:
        n = int(d.get("suivant", 1))
        d["suivant"] = n + 1
        x = {"id": n, "nom": f"son {n}", "c": v.round(5).tolist(), "n": 0, "premier": t, "dernier": t, "avec_parole": 0,
             "plusieurs_voix": 0}
        fam.append(x)
        if len(fam) > FAMILLES_MAX:                    # la place manque : la moins entendue des familles sans nom s'en va
            sans_nom = [y for y in fam if re.fullmatch(r"son \d+", y["nom"]) and y is not x]
            if sans_nom:
                fam.remove(min(sans_nom, key=lambda y: (y["n"], y["dernier"])))
    else:
        k = min(x["n"], 50)                            # elle suit ce qu'elle devient, lentement
        x["c"] = ((np.asarray(x["c"]) * k + v) / (k + 1)).round(5).tolist()
    x["n"] += 1
    x["dernier"] = t
    if parole:
        x["avec_parole"] += 1
    if voix and int(voix) >= 2:
        x["plusieurs_voix"] += 1
    _ecrire(d, fichier)
    return {"famille": x["nom"], "id": x["id"], "nouvelle": nouvelle, "fois": x["n"], "ressemblance": round(max(s, 0.0), 2)}


def _nom_valide(nom):
    nom = " ".join(str(nom or "").split())[:60]
    if not nom or not all(c.isalnum() or c in " -'’" for c in nom) or re.fullmatch(r"son\s*\d*", nom, re.IGNORECASE):
        raise ValueError("un nom (lettres, chiffres, espaces, traits d'union, apostrophes), pas « son N »")
    return nom


def nommer(famille, nom, fichier=None):
    """« son 3 » (ou « 3 ») → « la télé » : la famille garde ce nom pour toujours."""
    nom = _nom_valide(nom)
    cle = str(famille or "").strip().lower()
    d = _lire(fichier)
    for x in d.get("familles", []):
        if x["nom"].lower() == cle or cle.isdigit() and x["id"] == int(cle) or cle == f"son {x['id']}":
            ancien, x["nom"] = x["nom"], nom
            _ecrire(d, fichier)
            return {"ancien": ancien, "nom": nom, "fois": x["n"]}
    raise ValueError(f"famille inconnue : « {str(famille)[:40]} » (sons_familles pour la liste)")


def lister(fichier=None):
    """Ses familles, les plus entendues d'abord."""
    return [{"nom": x["nom"], "fois": x["n"], "avec_parole": x["avec_parole"], "plusieurs_voix": x["plusieurs_voix"],
             "premier": x["premier"], "dernier": x["dernier"]}
            for x in sorted(_lire(fichier).get("familles", []), key=lambda y: -y["n"])]
