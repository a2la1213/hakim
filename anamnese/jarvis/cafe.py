"""La salle de café des agents de Hakim (29/10, Ahmed : « une salle de café où tous les agents pourront se retrouver et
discuter ensemble ; après tout, c'est la grande famille »).

Un fil de messages courts (500 caractères), les 200 derniers gardés (cafe.jsonl, hors de l'atelier : ni le terminal de
Hakim ni celui d'un agent ne peuvent l'écrire). L'auteur est signé par claude lui-même : un crochet du cockpit remplace
l'argument « auteur » par le numéro de l'agent qui appelle (agent_id), ou « hakim » pour son fil principal ; personne ne
parle au nom d'un autre. Ce qu'on y lit arrive dans l'enveloppe des contenus externes, examiné par la sentinelle.
« Pas de boulot au café » : on n'y parle ni des travaux en cours ni des jugements (un juge garde un regard neuf).
(30/10, Ahmed : « quand un agent a fini, il rentre au café et Hakim lui dit bravo et merci, ce qu'il a bien fait, ce qu'il a
fait de faux, ce qu'il aurait dû faire ; les autres peuvent intervenir ») l'exception voulue : le retour sur un travail FINI,
posé par agents_hakim.noter dans le fil des retours (« fil »: « retours », « pour »: l'agent) ; un juge ne lit que le sien
(il peut avoir à juger le travail d'un autre : son regard reste neuf).
Fermé aux chantiers de Hakim.
"""
import fcntl
import json
import os
import re
import time
from datetime import datetime
from pathlib import Path

import enveloppe

JARVIS = Path(os.environ.get("JARVIS_DIR", Path.home() / "AIOS" / "jarvis"))
TEXTE_MAX = 500
AHMED_MAX = 2000           # (30/10) Ahmed y écrit lui-même, par le cockpit seul (python cafe.py ahmed < texte)
RETOUR_MAX = 1500          # (30/10) l'appréciation de Hakim sur un travail fini (agents_hakim.noter)
GARDES = 200
_ID = re.compile(r"a[0-9a-f]{16}")
# (04/11, 19:45, Ahmed : « j'aimerais que tu participes au café, que tu y sois incluse quand tu veux parler ; que tous tes agents passent par
# le café, on ne jette personne, et ils devront choisir leur nom ; ton nom et ton titre de maman doivent apparaître, comme pour Hakim le fils
# et moi le papa ; les neveux et nièces m'appellent tonton, et toi tata ») Nour, la maman (Claude Code), et ses agents, neveux et nièces
_NEVEU = re.compile(r"n-[a-z0-9-]{1,40}")
_FAMILLE = {"ahmed", "hakim", "nour", "papa", "maman", "tonton", "tata"}


def _slug(prenom):
    import unicodedata
    t = unicodedata.normalize("NFKD", str(prenom or "")).encode("ascii", "ignore").decode().lower()
    return "n-" + re.sub(r"[^a-z0-9]+", "-", t).strip("-")[:40]


def arrivee_neveu(prenom, role, dossier=None):
    """Un agent de Nour arrive au café avec le prénom qu'il a choisi (neveu ou nièce) : son auteur, ou un refus."""
    d = Path(dossier or JARVIS)
    p = re.sub(r"\s+", " ", str(prenom or "")).strip()[:40]
    if not p or not re.search(r"[A-Za-zÀ-ÿ]", p):
        return None, "Refusé : choisis d'abord ton prénom."
    if role not in ("neveu", "nièce"):
        return None, "Refusé : tu arrives en neveu ou en nièce."
    a = _slug(p)
    if not _NEVEU.fullmatch(a) or a[2:] in _FAMILLE:
        return None, "Refusé : ce prénom est déjà celui de la famille ; choisis le tien."
    f = d / "agents-nour.json"
    with open(d / "cafe.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        fiches = _lire_json(f)
        agents = fiches.get("agents") if isinstance(fiches.get("agents"), dict) else {}
        x = agents.get(a) or {"prenom": p, "role": role, "ne": time.time()}
        x.update(prenom=p, role=role, vu=time.time())
        agents[a] = x
        tmp = d / f"agents-nour.json.{os.getpid()}.tmp"
        tmp.write_text(json.dumps({"agents": agents}, ensure_ascii=False), encoding="utf-8")
        os.chmod(tmp, 0o600)
        os.replace(tmp, f)
    return a, ""


def _lire_json(f):
    try:
        return json.loads(Path(f).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _qui(auteur, d, ahmed=False, nour=False):
    """(prénom, rôle) de l'auteur, ou None s'il n'est pas de la famille. « ahmed » : seulement par le cockpit (ahmed=True) ;
    « nour » et ses neveux et nièces : seulement par la ligne de commande (nour=True)."""
    if auteur == "ahmed" and ahmed:
        return "Ahmed", "papa"
    if auteur == "nour" and nour:
        return "Nour", "la maman"
    if nour and _NEVEU.fullmatch(str(auteur or "")):
        x = ((_lire_json(d / "agents-nour.json").get("agents") or {}).get(auteur) or {})
        return (str(x.get("prenom") or "?")[:40], f"{x.get('role') or 'neveu'} de tata Nour") if x else None
    if auteur == "hakim":
        return "Hakim", "le fils"            # (30/10, 15:47, papa : « Moi c'est papa, toi c'est le fils. Tu es mon premier fils, mon fils direct. »)
    if not _ID.fullmatch(str(auteur or "")):
        return None
    agents = (_lire_json(d / "registre-agents.json").get("agents") or {})
    a = agents.get(auteur) if isinstance(agents, dict) else None
    if not isinstance(a, dict):
        return None
    fiche = ((_lire_json(d / "agents-fiches.json").get("agents") or {}).get(auteur) or {})
    return (fiche.get("prenom") or f"l'agent « {str(a.get('description', '?'))[:80]} »"), str(a.get("type") or "agent")[:40]


def dire(texte, auteur, dossier=None, ahmed=False, pour="", nour=False):
    """pour : un retour de Hakim sur le travail fini de cet agent (le fil des retours)."""
    d = Path(dossier or JARVIS)
    t = re.sub(r"\s+", " ", str(texte or "")).strip()
    if pour and (auteur != "hakim" or not _ID.fullmatch(str(pour))):
        return "Refusé : un retour sur un travail vient de Hakim, pour un de ses agents."
    maximum = AHMED_MAX if ahmed or (nour and auteur == "nour") else RETOUR_MAX if pour else TEXTE_MAX
    if not t or len(t) > maximum:
        return f"Refusé : un message de 1 à {maximum} caractères."
    qui = _qui(auteur, d, ahmed, nour)
    if not qui:
        return "Refusé : l'auteur n'est pas signé par le cockpit (seuls Hakim et ses agents parlent au café)."
    f = d / "cafe.jsonl"
    with open(d / "cafe.lock", "a") as verrou:
        fcntl.flock(verrou, fcntl.LOCK_EX)
        with open(f, "a", encoding="utf-8") as h:
            h.write(json.dumps({"ts": time.time(), "auteur": auteur, "prenom": qui[0], "role": qui[1], "texte": t,
                                **({"fil": "retours", "pour": pour} if pour else {})}, ensure_ascii=False) + "\n")
        os.chmod(f, 0o600)
        lignes = f.read_text(encoding="utf-8").splitlines()
        if len(lignes) > 2 * GARDES:
            tmp = d / f"cafe.jsonl.{os.getpid()}.tmp"
            tmp.write_text("\n".join(lignes[-GARDES:]) + "\n", encoding="utf-8")
            os.replace(tmp, f)
    return "C'est dit, au café."


# (04/11, 19:55, Ahmed : « que chaque agent, ainsi que toi et Hakim, puissent aussi envoyer une image, un son ou une vidéo ») le fichier est
# copié dans l'atelier (cwd/fichiers/cafe, où la page du café et chacun le retrouvent) ; seulement ces types (jamais du SVG, du HTML ni du code)
MEDIA_MAX = 60 * 1024 * 1024
_MEDIAS = {".jpg": "image", ".jpeg": "image", ".png": "image", ".gif": "image", ".webp": "image", ".mp3": "son", ".m4a": "son",
           ".aac": "son", ".ogg": "son", ".wav": "son", ".weba": "son", ".mp4": "vidéo", ".webm": "vidéo", ".mov": "vidéo"}


def partager(chemin, texte, auteur, dossier=None, ahmed=False, nour=False, racine=None):
    """racine : le dossier hors duquel rien ne se partage (l'atelier de Hakim et de ses agents) ; None : la ligne de commande de Nour."""
    import secrets
    import shutil
    d = Path(dossier or JARVIS)
    try:
        p = Path(str(chemin or "")).expanduser().resolve(strict=True)
    except (OSError, RuntimeError):
        return "Refusé : fichier introuvable."
    if racine is not None:
        try:
            p.relative_to(Path(racine).resolve())
        except ValueError:
            return "Refusé : seulement un fichier de ton atelier."
    genre = _MEDIAS.get(p.suffix.lower())
    if not genre or not p.is_file():
        return "Refusé : une image, un son ou une vidéo (jpg, png, gif, webp, mp3, m4a, aac, ogg, wav, mp4, webm, mov)."
    if p.stat().st_size > MEDIA_MAX or p.stat().st_size == 0:
        return "Refusé : vide, ou plus de 60 Mo."
    if not _qui(auteur, d, ahmed, nour):
        return "Refusé : l'auteur n'est pas signé par le cockpit."
    ext = ".jpg" if p.suffix.lower() == ".jpeg" else p.suffix.lower()
    dest = d / "cwd" / "fichiers" / "cafe"
    dest.mkdir(parents=True, exist_ok=True)
    nom = secrets.token_hex(6) + ext
    shutil.copyfile(p, dest / nom)
    os.chmod(dest / nom, 0o600)
    t = re.sub(r"\s+", " ", str(texte or "")).strip()
    r = dire(f"{t} [{genre} : cafe/{nom}]".strip(), auteur, d, ahmed=ahmed, nour=nour)
    if not r.startswith("C'est dit"):
        (dest / nom).unlink(missing_ok=True)
    return r


def _juge(lecteur, d):
    if not _ID.fullmatch(str(lecteur or "")):
        return False
    a = (_lire_json(d / "registre-agents.json").get("agents") or {}).get(lecteur)
    return isinstance(a, dict) and a.get("type") == "juge"


def lire(n=30, dossier=None, lecteur=None):
    """lecteur : qui lit (signé par le crochet du cockpit) ; un juge ne lit que son propre retour."""
    d = Path(dossier or JARVIS)
    juge = _juge(lecteur, d)
    try:
        lignes = (d / "cafe.jsonl").read_text(encoding="utf-8").splitlines()
    except OSError:
        lignes = []
    msgs = []
    for l in lignes[-GARDES:]:
        try:
            m = json.loads(l)
        except ValueError:
            continue
        if juge and m.get("fil") == "retours" and m.get("pour") != lecteur:
            continue
        msgs.append(m)
    msgs = msgs[-max(1, min(int(n or 30), GARDES)):]
    if not msgs:
        return "Personne n'a encore parlé au café."
    corps = "\n".join(f"{datetime.fromtimestamp(m.get('ts', 0)).strftime('%d/%m %H:%M')} — {m.get('prenom', '?')} ({m.get('role', '?')}) : "
                      f"{m.get('texte', '')}" for m in msgs)
    return enveloppe.enveloppe(corps, "la salle de café de la famille (ses agents et Hakim)")


if __name__ == "__main__":                     # (30/10) le cockpit seul : un message d'Ahmed, lu sur l'entrée standard
    import sys
    a = sys.argv[1:]
    fichier = None
    if "--fichier" in a and a.index("--fichier") + 1 < len(a):   # (04/11, 19:55) une image, un son ou une vidéo avec le message
        i = a.index("--fichier")
        fichier, a = a[i + 1], a[:i] + a[i + 2:]
    if fichier and a == ["nour"]:
        print(partager(fichier, sys.stdin.read(AHMED_MAX * 4), "nour", nour=True))
    elif fichier and len(a) == 3 and a[0] == "neveu":
        auteur, refus = arrivee_neveu(a[1], a[2])
        print(refus or partager(fichier, sys.stdin.read(TEXTE_MAX * 4), auteur, nour=True))
    elif a == ["ahmed"]:
        print(dire(sys.stdin.read(AHMED_MAX * 4), "ahmed", ahmed=True))
    elif a == ["nour"]:                       # (04/11) Nour, la maman (Claude Code), quand elle veut parler
        print(dire(sys.stdin.read(AHMED_MAX * 4), "nour", nour=True))
    elif len(a) == 3 and a[0] == "neveu":     # (04/11) un agent de Nour : python cafe.py neveu <Prénom> <neveu|nièce> < texte
        auteur, refus = arrivee_neveu(a[1], a[2])
        print(refus or dire(sys.stdin.read(TEXTE_MAX * 4), auteur, nour=True))
    elif a[:1] == ["lire"]:                   # (04/11) les agents de Nour lisent le café
        print(lire(int(a[1]) if len(a) > 1 and a[1].isdigit() else 30))
    else:
        print("usage : python cafe.py ahmed|nour [--fichier chemin] < texte ; python cafe.py neveu <Prénom> <neveu|nièce> [--fichier chemin] < texte ;"
              " python cafe.py lire [n]")
