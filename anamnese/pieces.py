"""Les pièces jointes de Hakim (demande d'Ahmed relayée par Hakim, 2026-10-20 08:27 ; accord d'Ahmed : « tu peux
faire ce qu'il dit ») : Hakim joint à son message un fichier qu'Ahmed télécharge depuis la page Parler (Mac et
téléphone), au lieu de lui dicter un chemin.

- Seulement depuis son atelier (~/AIOS/jarvis/cwd/atelier) et les fichiers d'Ahmed (~/AIOS/jarvis/cwd/fichiers) ;
  pas de nom qui sent le secret ; un texte qui contient une clé ou un mot de passe est refusé ; 25 Mo au plus.
- Le fichier est COPIÉ dans ~/AIOS/jarvis/pieces/<id>/ (que ni ses fichiers ni son terminal ne peuvent écrire) :
  ce qu'Ahmed télécharge est ce qui a été joint, même si l'original change ensuite. Index : pieces/index.jsonl.
- Le cockpit voit la marque ⟦pièce:<id>⟧ dans le résultat de l'outil et ajoute la pièce sous le message ; il la
  sert derrière son jeton (et la passkey depuis le téléphone), jamais par une adresse publique.
"""
import hashlib
import json
import os
import stat
import sys
import time
import uuid
from pathlib import Path

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
DOSSIER = JARVIS / "pieces"
TAILLE_MAX = 25 * 1024 * 1024
TEXTES = {".txt", ".md", ".csv", ".json", ".py", ".js", ".html", ".tex", ".log", ".yaml", ".yml", ".xml", ".svg"}


class Refus(Exception):
    pass


def racines(jarvis=None):
    j = Path(jarvis or JARVIS)
    return [j / "cwd" / "atelier", j / "cwd" / "fichiers"]


def _fichiers():
    ici = str(Path(__file__).resolve().parent / "jarvis")
    if ici not in sys.path:
        sys.path.append(ici)
    import fichiers
    return fichiers


def joindre(chemin, titre="", jarvis=None, dossier=None):
    """Copie le fichier parmi les pièces ; rend sa fiche {id, nom, titre, taille, type, sha256}."""
    j = Path(jarvis or JARVIS)
    brut = Path(os.path.expanduser(str(chemin or "")))
    if not brut.is_absolute():
        brut = j / "cwd" / brut                       # « atelier/pour_ahmed/x.txt » : relatif à son dossier de travail
    try:
        p = brut.resolve(strict=True)
    except (OSError, RuntimeError):
        raise Refus(f"fichier introuvable : {chemin}")
    permis = [r.resolve() for r in racines(j) if r.exists()]
    if not any(r in p.parents for r in permis):
        raise Refus("seulement un fichier de ton atelier (~/AIOS/jarvis/cwd/atelier) ou des fichiers d'Ahmed (cwd/fichiers)")
    if not p.is_file():
        raise Refus("ce n'est pas un fichier")
    f = _fichiers()
    if f._SECRETS.search(f._normaliser(p.name)) or p.name.startswith("."):
        raise Refus("ce nom de fichier ressemble à un secret : refusé")
    # relecture Opus (B1) : le fichier peut être échangé entre la vérification et la lecture → on vérifie le fichier
    # OUVERT (son vrai chemin, d'après le système), pas le nom
    try:
        # (relecture indépendante du 27/10, E) O_NONBLOCK : un tube nommé glissé après is_file() ne fige pas le serveur
        fd = os.open(p, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refus("fichier illisible (ou lien symbolique)")
    with os.fdopen(fd, "rb") as h:
        try:
            import fcntl
            vrai = Path(os.fsdecode(fcntl.fcntl(fd, fcntl.F_GETPATH, b"\0" * 1024)).split("\0", 1)[0])
        except (ImportError, AttributeError, OSError):
            vrai = p
        if not any(r in vrai.parents for r in permis) or not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refus("le fichier a changé pendant qu'on le joignait : refusé")
        if os.fstat(fd).st_nlink > 1:            # (27/10) un lien dur ne se voit pas au chemin : il peut cacher un fichier fermé
            raise Refus("un lien dur : refusé (il peut cacher un fichier fermé)")
        contenu = h.read(TAILLE_MAX + 1)
    taille = len(contenu)
    if taille > TAILLE_MAX:
        raise Refus(f"trop gros ({taille // (1024 * 1024)} Mo ; 25 Mo au plus)")
    if p.suffix.lower() in TEXTES:
        texte = contenu.decode("utf-8", "replace")
        if f.masquer(texte) != texte:
            raise Refus("ce fichier contient un secret (clé, jeton, mot de passe) : retire-le avant de le joindre")
    pid = time.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
    d = Path(dossier or j / "pieces")
    (d / pid).mkdir(parents=True, exist_ok=False)
    cible = d / pid / p.name
    tmp = d / pid / f".{p.name}.tmp"
    tmp.write_bytes(contenu)
    os.replace(tmp, cible)
    fiche = {"id": pid, "ts": time.time(), "nom": p.name, "titre": " ".join(str(titre or "").split())[:160],
             "taille": taille, "type": p.suffix.lower().lstrip("."), "sha256": hashlib.sha256(contenu).hexdigest(),
             "origine": str(p.relative_to(j / "cwd"))}
    with open(d / "index.jsonl", "a", encoding="utf-8") as h:
        h.write(json.dumps(fiche, ensure_ascii=False) + "\n")
    return fiche


def lisible(n):
    return f"{n} o" if n < 1024 else (f"{n / 1024:.0f} Ko" if n < 1024 * 1024 else f"{n / (1024 * 1024):.1f} Mo".replace(".", ","))
