"""Toucher à son propre code, sans danger (lot H, point 30 de la liste du 2026-10-19 ; règles proposées par
Hakim, calquées sur Anamnèse : modules/proposed puis /promote, cœur immuable).

- Un CHANTIER est une copie d'un projet dans l'atelier de Hakim : il y modifie ce qu'il veut avec son
  terminal ; l'original n'est jamais touché, la base de mémoire n'est pas copiée (data/ n'est pas suivi).
- `tester` lance la suite de tests du projet sous un bac à sable, sur un INSTANTANÉ de la copie.
- `proposer` fabrique une PROMOTION : le patch, le résultat des tests de CET état exact, la liste des fichiers
  touchés, ceux du CŒUR signalés, et un résumé. Elle va dans ~/AIOS/jarvis/cwd/promotions.
- Rien n'est jamais appliqué automatiquement : Ahmed (ou Claude Code avec son accord) l'applique, en commit
  à part ; un `git revert` la défait.

Refonte après la relecture Opus du 2026-10-20 (la première version permettait de sortir du bac à sable) :
- le dépôt git de chaque chantier vit HORS de l'atelier (PRIVE/<nom>.git) ; git ne lit jamais une
  configuration que Hakim peut écrire (ni ~/.gitconfig, ni un .git de la copie : aucun .git n'y est permis),
  ni hooks, ni fsmonitor, ni filtres, ni sous-modules ;
- les tests tournent sur une extraction de l'arbre git (git archive) dans PRIVE/<nom>-essai, hors de
  l'atelier : Hakim ne peut ni la modifier pendant les tests, ni y glisser un fichier ignoré ; le profil du
  bac à sable est écrit dans PRIVE (aucun lien symbolique à suivre) ;
- le résultat des tests est attaché à l'EMPREINTE de l'arbre (git write-tree), plus à des dates ;
- le CŒUR est repéré par motifs, renommages compris (--no-renames) ; liens symboliques et exécutables signalés.
"""
import io
import hashlib
import json
import os
import re
import shutil
import stat
import signal
import subprocess
import sys
import tarfile
import time
from pathlib import Path

import terminal

PROJETS = {"anamnese": Path.home() / "Desktop" / "anamnese"}
CHANTIERS = terminal.ATELIER / "chantiers"
PRIVE = Path.home() / "AIOS" / "jarvis" / "chantiers-prive"          # hors de cwd : ni lu ni écrit par Hakim
# le vrai git d'Xcode s'il est là : le relais /usr/bin/git passe par xcrun, qui veut écrire son cache dans /var/folders —
# refusé quand ce code tourne lui-même dans un bac à sable (les tests d'un chantier d'Anamnèse) (C1, 2026-10-20)
GIT = next((g for g in ("/Applications/Xcode.app/Contents/Developer/usr/bin/git", "/Library/Developer/CommandLineTools/usr/bin/git")
            if Path(g).exists()), "/usr/bin/git")
PROMOTIONS = Path.home() / "AIOS" / "jarvis" / "cwd" / "promotions"
ESSAIS_SIMULTANES = 2
DELAI_TESTS_S = 600                    # la vraie suite : ~200 s sous ce bac à sable (2026-10-20)
# le cœur : une promotion qui y touche est signalée en tête, relecture humaine obligatoire
COEUR = [re.compile(m) for m in (
    r"(^|/)conftest\.py$", r"(^|/)(pytest\.ini|pyproject\.toml|setup\.cfg|tox\.ini|requirements[^/]*\.txt)$",
    r"^(identity|evenements|memory|migrations|config|engine|registre|consolidate|mcp_server|daemon|health|interieur|"
    r"occupations|spontaneite|index_fichiers|cli)\.py$",
    r"^jarvis/(persona\.md|[a-z_]+\.py)$", r"(^|/)\.git", r"\.(sh|command|plist|sb)$", r"(^|/)\.env", r"^tests/")
]


class Refus(Exception):
    pass


def _nom(nom):
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,40}", str(nom or "")):
        raise Refus("nom de chantier : lettres minuscules, chiffres et tirets (2 à 41 caractères)")
    return nom


def _lieux(nom, chantiers=None):
    """(copie, prive) d'un chantier, vérifiés : la copie est un vrai dossier de CHANTIERS (aucun lien
    symbolique en chemin : l'atelier est écrit par Hakim, il pourrait en poser un)."""
    nom = _nom(nom)
    if chantiers is None:
        base, prive = CHANTIERS, PRIVE
        if base.is_symlink() or base.resolve() != terminal.ATELIER.resolve() / "chantiers":
            raise Refus("le dossier des chantiers a été déplacé ou remplacé par un lien : refusé")
    else:
        base = Path(chantiers)
        prive = base.parent / ".prive"
    copie = base / nom
    if copie.is_symlink() or (copie.exists() and copie.resolve() != base.resolve() / nom):
        raise Refus("la copie est un lien symbolique : refusé")
    return copie, prive


def _git(args, gitdir, travail=None, timeout=120, entree=None, texte=True):
    """git sur le dépôt PRIVÉ du chantier, jamais sur une configuration écrite depuis l'atelier."""
    vide = Path(gitdir).parent / ".maison-git"
    vide.mkdir(parents=True, exist_ok=True)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(vide), "XDG_CONFIG_HOME": str(vide), "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_ATTR_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "LANG": "C.UTF-8",
           "GIT_DIR": str(gitdir), "GIT_NO_REPLACE_OBJECTS": "1", "GIT_OPTIONAL_LOCKS": "0"}
    if travail is not None:
        env["GIT_WORK_TREE"] = str(travail)
    surete = ["-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", "-c", "core.attributesFile=/dev/null",
              "-c", "core.untrackedCache=false", "-c", "diff.ignoreSubmodules=all", "-c", "status.submoduleSummary=false",
              "-c", "core.symlinks=true", "-c", "protocol.allow=never", "-c", "protocol.file.allow=always"]
    r = subprocess.run([GIT, *surete, *args], cwd=str(gitdir), capture_output=True, text=texte,
                       timeout=timeout, env=env, input=entree)
    if r.returncode != 0:
        err = r.stderr if texte else r.stderr.decode("utf-8", "replace")
        raise Refus(f"git {' '.join(args[:2])} : {err.strip()[:300]}")
    return r.stdout


def _meta(prive, nom):
    try:
        return json.loads((prive / f"{nom}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise Refus(f"chantier inconnu : {nom}")


def _sans_git_imbrique(copie):
    """Aucun .git dans la copie (un dépôt imbriqué apporterait sa propre configuration)."""
    for racine, dossiers, fichiers in os.walk(copie, followlinks=False):
        if ".git" in dossiers or ".git" in fichiers:
            raise Refus(f"un .git est apparu dans la copie ({Path(racine).relative_to(copie) / '.git'}) : retire-le")
        dossiers[:] = [d for d in dossiers if d not in (".tmp", "__pycache__", ".pytest_cache")]


SPECIAUX = {"120000": "lien symbolique", "100755": "exécutable", "160000": "sous-module"}
EXCLUS = ".tmp/\n__pycache__/\n*.pyc\n.pytest_cache/\n.DS_Store\n"
JAMAIS_COPIES = ("dataset", "data")


def ouvrir(nom, projet="anamnese", projets=None, chantiers=None):
    """Copie le projet dans l'atelier (une branche hakim/<nom>). Rend le chemin de la copie."""
    projets = projets or PROJETS
    if projet not in projets:
        raise Refus(f"projet inconnu (permis : {', '.join(projets)})")
    copie, prive = _lieux(nom, chantiers)
    gitdir = prive / f"{nom}.git"
    if (prive / f"{nom}.json").exists() and copie.is_dir():
        return copie
    if copie.exists() or gitdir.exists():
        raise Refus(f"un chantier {nom} existe à moitié : choisis un autre nom")
    prive.mkdir(parents=True, exist_ok=True, mode=0o700)
    # git clone ne prend pas GIT_DIR : lancé directement, depuis PRIVE, sur le dépôt d'origine (celui d'Ahmed)
    env = {"PATH": "/usr/bin:/bin", "HOME": str(prive / ".maison-git"), "GIT_CONFIG_GLOBAL": "/dev/null",
           "GIT_CONFIG_NOSYSTEM": "1", "GIT_TERMINAL_PROMPT": "0", "LANG": "C.UTF-8"}
    (prive / ".maison-git").mkdir(exist_ok=True)
    r = subprocess.run([GIT, "-c", "core.hooksPath=/dev/null", "clone", "--bare", "--no-hardlinks", "--quiet",
                        str(projets[projet]), str(gitdir)], cwd=str(prive), env=env, capture_output=True, text=True, timeout=300)
    if r.returncode != 0:
        raise Refus(f"git clone : {r.stderr.strip()[:300]}")
    _git(["config", "core.bare", "false"], gitdir)
    (gitdir / "info").mkdir(exist_ok=True)
    (gitdir / "info" / "exclude").write_text(EXCLUS, encoding="utf-8")
    # (audit JARVIS 2, M4, 2026-10-20) jamais les données d'entraînement (dataset/ : des conversations) dans l'atelier :
    # extraction partielle — ces fichiers restent dans l'index sans être écrits (skip-worktree), donc le patch ne
    # les supprime pas non plus
    _git(["config", "core.sparseCheckout", "true"], gitdir)
    _git(["config", "core.sparseCheckoutCone", "false"], gitdir)
    (gitdir / "info" / "sparse-checkout").write_text("/*\n" + "".join(f"!/{d}/\n" for d in JAMAIS_COPIES), encoding="utf-8")
    base = _git(["rev-parse", "HEAD"], gitdir).strip()
    # extraite dans PRIVE puis déplacée dans l'atelier : jamais d'écriture git à travers un chemin de l'atelier
    tmp = prive / f".{nom}-extraction"
    shutil.rmtree(tmp, ignore_errors=True)
    tmp.mkdir()
    _git(["checkout", "--quiet", "-f", "-b", f"hakim/{nom}"], gitdir, travail=tmp)
    copie.parent.mkdir(parents=True, exist_ok=True)
    os.rename(tmp, copie)
    (prive / f"{nom}.json").write_text(json.dumps({"projet": projet, "ouvert": time.time(), "base": base}), encoding="utf-8")
    return copie


def _copier_par_descripteurs(fd, dest, rel=""):
    """Le dossier ouvert `fd` recopié dans `dest`, maillon par maillon (O_NOFOLLOW) : un lien est recopié COMME lien
    (git le montre, jamais suivi), un tube ou un lien dur est refusé ; ferme `fd`."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        for nom in sorted(os.listdir(fd)):
            if nom in (".tmp", "__pycache__", ".pytest_cache"):
                continue
            if nom == ".git":
                raise Refus(f"un .git est apparu dans la copie ({rel or '.'}/.git) : retire-le")
            st = os.stat(nom, dir_fd=fd, follow_symlinks=False)
            if stat.S_ISLNK(st.st_mode):
                os.symlink(os.readlink(nom, dir_fd=fd), dest / nom)
            elif stat.S_ISDIR(st.st_mode):
                _copier_par_descripteurs(os.open(nom, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=fd),
                                         dest / nom, f"{rel}/{nom}")
            elif stat.S_ISREG(st.st_mode):
                with os.fdopen(os.open(nom, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=fd), "rb") as h:
                    s2 = os.fstat(h.fileno())
                    if not stat.S_ISREG(s2.st_mode) or s2.st_nlink > 1:
                        raise Refus(f"{rel}/{nom} : un lien dur ou un fichier échangé dans la copie : refusé")
                    with open(dest / nom, "wb") as o:
                        shutil.copyfileobj(h, o)
                os.chmod(dest / nom, s2.st_mode & 0o755)
    except OSError as e:
        raise Refus(f"copie illisible ({rel or '.'}) : {e.strerror}") from e
    finally:
        os.close(fd)


def _arbre(copie, gitdir):
    """L'empreinte de l'état de la copie (tout ce qui irait dans le patch) : git add -A puis write-tree.
    (27/10, relecture indépendante) git ne travaille JAMAIS sur le chemin de l'atelier : une tâche de fond pouvait échanger
    la copie contre un lien vers un dossier fermé entre la vérification et git (le contenu entrait dans l'arbre, puis dans
    le patch). La copie est d'abord recopiée par descripteurs dans un instantané privé, que rien de l'atelier n'atteint."""
    import fichiers
    instant = Path(gitdir).parent / f".{Path(gitdir).stem}-instantane"
    shutil.rmtree(instant, ignore_errors=True)
    try:
        fd = fichiers._dossier_sans_lien(copie.parent.parent, (copie.parent.name, copie.name), creer=False)
    except (fichiers.Refus, OSError):
        raise Refus("la copie est un lien symbolique, ou introuvable : refusé")
    try:
        _copier_par_descripteurs(fd, instant)
        _git(["add", "-A"], gitdir, travail=instant)
        return _git(["write-tree"], gitdir).strip()
    finally:
        shutil.rmtree(instant, ignore_errors=True)


def _ports_locaux():
    """Les ports TCP déjà à l'écoute sur ce Mac (cockpit, Ollama, VS Code, claude…) : les tests n'y touchent pas."""
    try:
        r = subprocess.run(["/usr/sbin/lsof", "-nP", "-iTCP", "-sTCP:LISTEN", "-Fn"], capture_output=True, text=True, timeout=20)
        ports = {int(m) for m in re.findall(r"^n.*:(\d+)$", r.stdout, re.M)}
    except (OSError, subprocess.SubprocessError):
        ports = set()
    return sorted(ports | {4317, 11434})


def _profil_tests(essai, venv, original=None, ports=()):
    """Le bac à sable des tests, calqué sur celui du terminal : écriture seulement dans l'essai ; lecture du
    dossier personnel limitée à l'essai, au venv, aux outils Python et aux modèles déjà téléchargés, plus le
    CODE du projet d'origine (fichiers .py/.txt/.md de la racine, de jarvis/ et de tests/ ; certains modules y
    pointent en chemin absolu ; un groupe optionnel n'est pas compris, d'où trois motifs) — jamais data/, dataset/,
    .git, un .env, ni /tmp ; réseau : seulement la
    boucle locale, sauf les ports déjà ouverts sur le Mac."""
    maison = str(Path.home())
    hf = Path.home() / ".cache" / "huggingface"
    lectures = "".join(f' (subpath "{p}")' for p in [essai, venv, hf, *terminal._chemins_outils()])
    orig = ""
    if original:
        o = re.sub(r"([.^$*+?()\[\]{}|\\])", r"\\\1", str(Path(original).resolve()))
        # (un groupe optionnel « (…)? » n'est pas compris par le bac à sable : vu le 2026-10-20 → trois motifs)
        orig = "\n(allow file-read-data" + "".join(f' (regex #"^{o}/{d}[^./][^/]*\\.(py|txt|md)$")'
                                                   for d in ("", "jarvis/", "tests/")) + ")"
    refus_ports = "".join(f' (remote ip "localhost:{p}")' for p in ports)
    programmes = "".join(f' (literal "{p}")' for p in terminal.PROGRAMMES_REFUSES)
    services = "".join(f' (global-name "{n}")' for n in terminal.SERVICES_REFUSES)
    # TOUT refusé par défaut, comme le terminal (relecture JARVIS 2, C1 et M2, 2026-10-20) : plus de « allow default »,
    # et plus aucune socket Unix (ssh-agent, Docker, tailscaled…) ; la boucle locale reste, sauf les ports déjà ouverts
    return f"""(version 1)
(deny default)
(import "system.sb")
(allow process-fork)
(allow process-exec)
(deny process-exec{programmes})
(allow process-info* (target same-sandbox))
(allow signal (target same-sandbox))
(allow sysctl-read)
(allow file-read-metadata)
(allow file-read* (literal "/") (subpath "/usr") (subpath "/bin") (subpath "/sbin") (subpath "/System") (subpath "/Library")
  (subpath "/opt") (subpath "/Applications/Xcode.app/Contents/Developer") (subpath "/private/etc")
  (subpath "/private/var/db/timezone") (subpath "/private/var/select") (subpath "/private/var/db/xcode_select_link") (literal "/dev") (literal "/dev/null") (literal "/dev/zero") (literal "/dev/random") (literal "/dev/urandom") (literal "/dev/tty") (literal "/dev/dtracehelper") (literal "/dev/autofs_nowait") (regex #"^/dev/fd/")
  (literal "/etc") (literal "/var") (literal "/tmp") (literal "/private") (literal "/private/var"){lectures}){orig}
(deny file-read* (subpath "/Library/Keychains") (subpath "/Library/Application Support/com.apple.TCC"))
(deny file-read* (regex #"/\\.env[^/]*$"))
(allow network-bind (local ip "localhost:*"))
(allow network-inbound (local ip "localhost:*"))
(allow network-outbound (remote ip "localhost:*"))
{"(deny network-outbound" + refus_ports + ")" if refus_ports else ""}
(allow system-socket)
(allow file-write* (subpath "{essai}") (literal "/dev/null") (literal "/dev/zero") (literal "/dev/tty") (literal "/dev/dtracehelper") (regex #"^/dev/fd/"))
(allow mach-lookup)
(deny mach-lookup{services})
(allow iokit-open)
(allow iokit-get-properties)
(allow ipc-posix-shm*)
(allow ipc-posix-sem*)
(allow user-preference-read)
"""


def _extraire(gitdir, arbre, essai):
    """L'arbre exact (git archive) dans un dossier d'essai neuf, hors de l'atelier ; tarfile filtre « data » :
    ni chemin absolu, ni « .. », ni lien qui sorte."""
    shutil.rmtree(essai, ignore_errors=True)
    essai.mkdir(parents=True)
    brut = _git(["archive", "--format=tar", arbre], gitdir, texte=False, timeout=300)
    with tarfile.open(fileobj=io.BytesIO(brut)) as t:
        t.extractall(essai, filter="data")


def tester(nom, chantiers=None, python=None, delai_s=DELAI_TESTS_S, projets=None):
    """La suite de tests du projet sur un instantané de la copie, sous bac à sable. Rend (réussi, sortie, arbre)."""
    copie, prive = _lieux(nom, chantiers)
    meta = _meta(prive, nom)
    projets = projets or PROJETS
    if meta.get("projet") not in projets and python is None:
        raise Refus("chantier sans projet connu")
    gitdir = prive / f"{nom}.git"
    arbre = _arbre(copie, gitdir)
    essai = prive.resolve() / f"{nom}-essai"
    _extraire(gitdir, arbre, essai)
    (essai / ".tmp" / "maison").mkdir(parents=True, exist_ok=True)
    python = Path(python or projets[meta["projet"]] / ".venv" / "bin" / "python")
    venv = python.parent.parent.resolve() if python.parent.parent.exists() else python.parent.parent
    regles = _profil_tests(essai, venv, projets.get(meta.get("projet")), _ports_locaux())   # en ligne (-p) : aucun fichier
    # git d'Xcode en direct : le relais /usr/bin/git passe par xcrun, qui veut écrire dans /var/folders (refusé)
    env = {"PATH": "/Applications/Xcode.app/Contents/Developer/usr/bin:/usr/bin:/bin:/usr/local/bin",
           "HOME": str(essai / ".tmp" / "maison"), "TMPDIR": str(essai / ".tmp"),
           "PYTHONDONTWRITEBYTECODE": "1", "LANG": "fr_FR.UTF-8",
           "HF_HOME": str(Path.home() / ".cache" / "huggingface"), "HF_HUB_OFFLINE": "1"}
    # -P : le dossier courant n'est pas mis en tête de sys.path (un pytest.py de la copie ne remplace pas pytest)
    # (2026-10-23) en priorité basse : sa voix et Whisper passent devant (priorite.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import priorite
    p = subprocess.Popen(priorite.basse(["/usr/bin/sandbox-exec", "-p", regles, str(python), "-P", "-m", "pytest", "-q",
                          "-p", "no:cacheprovider", "-x"]), cwd=str(essai), env=env, stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT, text=True, start_new_session=True)
    try:
        sortie, _ = p.communicate(timeout=delai_s)
        ok = p.returncode == 0
    except subprocess.TimeoutExpired:
        try:
            os.killpg(p.pid, signal.SIGKILL)
        except OSError:
            pass
        p.communicate()
        ok, sortie = False, f"tests arrêtés après {delai_s} s"
    shutil.rmtree(essai, ignore_errors=True)
    return ok, "\n".join((sortie or "").strip().splitlines()[-25:]), arbre


def _resultat_chemin(nom, chantiers=None):
    return _lieux(nom, chantiers)[1] / f"{nom}.tests.json"


def lancer_tests(nom, chantiers=None):
    """Les tests en arrière-plan (un processus détaché : la conversation n'attend pas ~1 à 2 min)."""
    copie, prive = _lieux(nom, chantiers)
    _meta(prive, nom)
    en_cours = 0
    for f in prive.glob("*.tests.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if d.get("etat") == "en cours" and time.time() - d.get("debut", 0) < DELAI_TESTS_S + 120:
            if f.name == f"{nom}.tests.json":
                raise Refus("des tests tournent déjà pour ce chantier : attends leur résultat (etat_chantier)")
            en_cours += 1
    if en_cours >= ESSAIS_SIMULTANES:
        raise Refus(f"déjà {en_cours} séries de tests en cours : attends qu'une finisse")
    res = _resultat_chemin(nom, chantiers)
    res.write_text(json.dumps({"etat": "en cours", "debut": time.time()}), encoding="utf-8")
    subprocess.Popen([sys.executable, str(Path(__file__).resolve()), "tester", nom,
                      "" if chantiers is None else str(Path(chantiers).resolve())],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, close_fds=True)


def resultat_tests(nom, chantiers=None):
    try:
        return json.loads(_resultat_chemin(nom, chantiers).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def etat(nom, chantiers=None):
    copie, prive = _lieux(nom, chantiers)
    _meta(prive, nom)
    gitdir = prive / f"{nom}.git"
    arbre = _arbre(copie, gitdir)
    diff = _git(["diff", "--cached", "--name-status", "--no-renames", "HEAD"], gitdir).strip()
    r = resultat_tests(nom, chantiers)
    tests = "aucun test lancé" if not r else (r["etat"] if r["etat"] == "en cours" else
                                               f"{'RÉUSSIS' if r.get('ok') else 'EN ÉCHEC'} : {r.get('resume', '')}")
    if r and r.get("etat") == "fini" and r.get("arbre") != arbre:
        tests += " (la copie a changé depuis : à relancer)"
    return f"Chantier {nom} ({copie})\nChangements :\n{diff or '(aucun)'}\nTests : {tests}"


def proposer(nom, resume, chantiers=None, promotions=None, tests=None):
    """Fabrique la promotion (patch + fiche). Rend le chemin de la fiche. Ne l'applique jamais."""
    copie, prive = _lieux(nom, chantiers)
    meta = _meta(prive, nom)
    gitdir = prive / f"{nom}.git"
    arbre = _arbre(copie, gitdir)
    sur = ["--no-renames", "--no-textconv", "--no-ext-diff", "--ignore-submodules=all"]
    patch = _git(["diff", "--cached", "--binary", *sur, meta["base"]], gitdir)
    if not patch.strip():
        raise Refus("aucun changement dans ce chantier")
    brut = _git(["diff", "--cached", "--raw", "-z", *sur, meta["base"]], gitdir)
    fichiers, speciaux = [], []
    morceaux = brut.split("\0")
    for i in range(0, len(morceaux) - 1, 2):
        entete, chemin = morceaux[i], morceaux[i + 1]
        if not entete.startswith(":"):
            continue
        fichiers.append(chemin)
        nouveau_mode = entete[1:].split()[1]
        if nouveau_mode in SPECIAUX:
            speciaux.append(f"{chemin} ({SPECIAUX[nouveau_mode]})")
    coeur = [f for f in fichiers if any(m.search(f) for m in COEUR)] + speciaux
    if tests is None:                                    # les tests de CET état exact
        r = resultat_tests(nom, chantiers)
        if not r or r.get("etat") != "fini":
            raise Refus("lance d'abord tester_chantier et attends son résultat")
        if r.get("arbre") != arbre:
            raise Refus("la copie a changé depuis les derniers tests : relance tester_chantier")
        tests = (bool(r.get("ok")), r.get("sortie", ""))
    ok, sortie = tests
    promotions = Path(promotions or PROMOTIONS)
    promotions.mkdir(parents=True, exist_ok=True)
    pid = f"{time.strftime('%Y%m%d-%H%M%S')}-{nom}"
    # (audit JARVIS 2, M7, 2026-10-20) le patch qui fait foi est rangé dans PRIVE (hors de cwd : ni lu ni écrit par
    # Hakim) avec son sha256 dans la fiche ; la copie de promotions/ n'est qu'une commodité de lecture — Ahmed applique
    # celle de PRIVE, ou vérifie l'empreinte (shasum -a 256) avant d'appliquer l'autre
    octets = patch.encode("utf-8")
    sha = hashlib.sha256(octets).hexdigest()
    (prive / "promotions").mkdir(parents=True, exist_ok=True, mode=0o700)
    fait_foi = prive / "promotions" / f"{pid}.patch"
    fait_foi.write_bytes(octets)
    (promotions / f"{pid}.patch").write_bytes(octets)
    fiche = {"id": pid, "chantier": nom, "projet": meta["projet"], "base": meta["base"], "arbre": arbre,
             "resume": str(resume or "")[:3000], "fichiers": fichiers, "coeur": coeur, "tests_ok": ok,
             "tests": sortie[-4000:], "cree": time.time(), "etat": "proposée",
             "patch_sha256": sha, "patch_qui_fait_foi": str(fait_foi)}
    (promotions / f"{pid}.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    (prive / "promotions" / f"{pid}.json").write_text(json.dumps(fiche, ensure_ascii=False, indent=1), encoding="utf-8")
    return promotions / f"{pid}.json"


def fermer(nom, chantiers=None):
    copie, prive = _lieux(nom, chantiers)
    trouve = copie.exists()
    shutil.rmtree(copie, ignore_errors=True)                # _lieux a vérifié : un vrai dossier de CHANTIERS
    for f in (prive / f"{nom}.git", prive / f"{nom}-essai"):
        shutil.rmtree(f, ignore_errors=True)
    for f in (prive / f"{nom}.json", prive / f"{nom}.tests.json", prive / f"{nom}.sb"):
        try:
            f.unlink()
        except OSError:
            pass
    return trouve


def lister_promotions(promotions=None):
    p = Path(promotions or PROMOTIONS)
    out = []
    for f in sorted(p.glob("*.json"), reverse=True)[:20]:
        try:
            out.append(json.loads(f.read_text(encoding="utf-8")))
        except (OSError, ValueError):
            pass
    return out


if __name__ == "__main__":
    if len(sys.argv) == 4 and sys.argv[1] == "tester":
        n, ch = sys.argv[2], sys.argv[3] or None
        try:
            ok, sortie, arbre = tester(n, ch)
        except Exception as e:                                    # noqa: BLE001 — le résultat dit l'échec
            ok, sortie, arbre = False, f"tests impossibles : {e}", None
        derniere = sortie.splitlines()[-1] if sortie else ""
        _resultat_chemin(n, ch).write_text(json.dumps(
            {"etat": "fini", "ok": ok, "resume": derniere, "sortie": sortie, "arbre": arbre, "fin": time.time()}),
            encoding="utf-8")
