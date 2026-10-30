"""Les Documents du téléphone d'Ahmed, en écriture pour Hakim (22/10 : « lecture ET écriture » par son terminal ; 30/10 :
« tout, papiers administratifs compris : tu fais ce que tu veux, fiston, je te fais confiance à 1000 % »).

Le dossier « Z Fold 7 » (ses Documents, synchronisés dans les deux sens par Syncthing). Les garde-fous que Hakim a
demandés lui-même : une SAUVEGARDE automatique avant toute modification (hors du dossier synchronisé, sur le Mac), jamais de
suppression (aucun outil ne supprime ; ce geste-là reste à Ahmed), et un JOURNAL de chaque écriture, qu'Ahmed suit dans le
cockpit. Son terminal peut aussi y écrire (depuis le 22/10) : telephone_sauver d'abord, c'est sa règle.
Fermé aux chantiers de Hakim.
"""
import json
import os
import shutil
import time
from pathlib import Path

import fichiers

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
TEXTE_MAX, FICHIER_MAX = 2_000_000, 200 * 1024 * 1024


class Refus(Exception):
    pass


def documents():
    return JARVIS / "cwd" / "fichiers" / "telephone" / "Z Fold 7"


def _chemin(rel):
    rel = str(rel or "").strip()
    if not rel or rel.startswith(("~", "/")) or any(p in ("..", "") for p in Path(rel).parts) or ".stfolder" in rel or ".stversions" in rel:
        raise Refus("un chemin relatif à ses Documents, sans « .. » (ex. « Hakim/notes.txt »)")
    nom = fichiers._normaliser(Path(rel).name)
    if fichiers._SECRETS.search(nom) or fichiers.CLES_PAR_NOM.search(nom) or fichiers.cle_privee(documents() / rel):
        raise Refus("fichier protégé (une clé, un secret) : Ahmed l'a masqué")      # (30/10, « masque-la pour eux »)
    return documents() / rel


def _noter(o):
    f = JARVIS / "telephone-ecritures.jsonl"
    with open(f, "a", encoding="utf-8") as h:
        h.write(json.dumps({"ts": time.time(), **o}, ensure_ascii=False) + "\n")
    os.chmod(f, 0o600)


def sauver(rel, pourquoi="avant une modification"):
    """Copie l'état actuel d'un fichier de ses Documents dans ~/AIOS/jarvis/telephone-sauvegardes/<horodatage>/ ; rend le chemin."""
    src = _chemin(rel)
    try:
        st = os.lstat(src)
    except FileNotFoundError:
        return None
    if not os.path.isfile(src) or os.path.islink(src):
        raise Refus("pas un fichier simple")
    if st.st_size > FICHIER_MAX:
        raise Refus("fichier trop lourd pour une sauvegarde automatique (200 Mo)")
    dst = JARVIS / "telephone-sauvegardes" / time.strftime("%Y%m%d-%H%M%S") / str(rel).lstrip("/")
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    _noter({"action": "sauvegarde", "chemin": str(rel), "sauvegarde": str(dst), "pourquoi": str(pourquoi)[:200]})
    return dst


def ecrire(rel, texte=None, depuis_atelier=None, note=""):
    """Écrit un fichier dans ses Documents (un texte, ou un fichier de son atelier) ; sauvegarde d'abord s'il existe."""
    dst = _chemin(rel)
    if (texte is None) == (depuis_atelier is None):
        raise Refus("donne soit un texte, soit un fichier de ton atelier")
    if texte is not None:
        donnees = str(texte).encode("utf-8")
        if len(donnees) > TEXTE_MAX:
            raise Refus("texte trop long (2 Mo) : écris-le dans ton atelier, puis depuis_atelier")
    else:
        atelier = JARVIS / "cwd" / "atelier"
        src = (atelier / str(depuis_atelier).lstrip("/"))
        reel = Path(os.path.realpath(src))
        if atelier.resolve() not in reel.parents or os.path.islink(src) or not reel.is_file():
            raise Refus("depuis_atelier : un fichier de ton atelier (pas un lien)")
        if reel.stat().st_size > FICHIER_MAX:
            raise Refus("fichier trop lourd (200 Mo)")
        donnees = reel.read_bytes()
    existait = dst.exists()
    sauvegarde = sauver(rel, "avant de l'écrire") if existait else None
    fichiers.ecrire_sans_lien(dst, donnees, documents())
    _noter({"action": "ecriture" if existait else "ajout", "chemin": str(rel), "taille": len(donnees),
            "sauvegarde": str(sauvegarde) if sauvegarde else None, "note": str(note or "")[:300]})
    return {"chemin": str(dst), "existait": existait, "sauvegarde": str(sauvegarde) if sauvegarde else None}


def journal(n=50):
    try:
        lignes = (JARVIS / "telephone-ecritures.jsonl").read_text(encoding="utf-8").splitlines()[-n:]
    except OSError:
        return []
    out = []
    for l in lignes:
        try:
            out.append(json.loads(l))
        except ValueError:
            pass
    return out
