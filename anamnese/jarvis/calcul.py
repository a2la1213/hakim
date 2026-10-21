"""Le terminal de calcul de Jarvis (demande d'Ahmed, 2026-10-16 : « lui donner accès au terminal pour
qu'il puisse effectuer des calculs »).

Jarvis écrit du Python ; il s'exécute dans le venv de Jarvis (numpy, scipy, sympy) sous un bac à
sable macOS (sandbox-exec), la garde étant dans le code et non dans la consigne :
- aucun réseau ;
- aucune lecture du dossier personnel d'Ahmed (ses projets, ses clés), sauf le venv et le dossier
  de travail du calcul ;
- aucune écriture hors de ce dossier ; aucun autre programme lancé (pas de shell) ;
- temps de calcul limité, sortie tronquée.
Le dossier de travail est dans celui de Jarvis : une image ou un fichier produit se lit avec Read.
Le vrai terminal (agir sur ses projets) viendra avec l'étape « agir à ta place », commande par
commande, avec l'accord d'Ahmed.
"""
import os
import resource
import shutil
import subprocess
import time
import uuid
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import groupes  # noqa: E402

DOSSIER = Path.home() / "AIOS" / "jarvis" / "cwd" / "calculs"
VENV_PYTHON = Path(__file__).resolve().parent / ".venv" / "bin" / "python"
DELAI_S = 60
SORTIE_MAX = 20_000
MEMOIRE_MAX_KO = 3 * 1024 * 1024          # 3 Go : au-delà, le Mac (16 Go) swapperait
DOSSIER_MAX = 500 * 1024 * 1024
GARDE_J = 2


def _profil(travail, python_reel, venv, base_python, python_venv):
    """Le profil sandbox-exec : TOUT est refusé par défaut (relecture Opus, 2026-10-16 : « tout permis
    sauf » laissait lire /private/tmp, /Library, les sorties des autres sessions…). Sont permis : le
    socle système d'Apple (system.sb : dyld, bibliothèques, fuseau horaire), l'exécution de ce
    Python, la lecture du venv, de l'installation de Python et du dossier du calcul, l'écriture dans
    ce seul dossier. Ni réseau, ni fork, ni autre programme, ni le reste du disque."""
    lectures = "".join(f' (subpath "{p}")' for p in (travail, venv, base_python))
    return f"""(version 1)
(deny default)
(import "system.sb")
(allow process-exec (literal "{python_reel}") (literal "{python_venv}"))
(allow file-read-metadata)
(allow file-read*{lectures})
(allow file-write* (subpath "{travail}"))
(allow sysctl-read)
"""


def purger(dossier=None, jours=GARDE_J):
    dossier = Path(dossier or DOSSIER)
    if not dossier.is_dir():
        return
    limite = time.time() - jours * 86400
    for d in dossier.iterdir():
        if d.is_dir() and d.stat().st_mtime < limite:
            shutil.rmtree(d, ignore_errors=True)


def executer(code, delai_s=DELAI_S, dossier=None, python=None):
    """Exécute `code` (Python) sous bac à sable. Rend un texte : sortie, erreurs, fichiers produits."""
    if not isinstance(code, str) or not code.strip():
        return "Aucun code à exécuter."
    if len(code) > 100_000:
        return "Code trop long (100 000 caractères au plus)."
    delai_s = max(1, min(int(delai_s or DELAI_S), 300))
    racine = Path(dossier or DOSSIER)
    purger(racine)
    travail = racine / f"{time.strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"
    travail.mkdir(parents=True, exist_ok=True)
    travail = travail.resolve()
    (travail / "calcul.py").write_text(code, encoding="utf-8")
    python = Path(python or VENV_PYTHON)
    python_reel = python.resolve()
    base_python = python_reel.parent.parent                 # l'installation de Python (bibliothèque standard)
    venv = python.parent.parent.resolve()
    regles = _profil(travail, python_reel, venv, base_python, python.absolute())     # en ligne (-p), jamais un fichier

    def limites():                                          # dans le processus fils, avant exec
        resource.setrlimit(resource.RLIMIT_CPU, (delai_s, delai_s + 5))
        resource.setrlimit(resource.RLIMIT_FSIZE, (200 * 1024 * 1024, 200 * 1024 * 1024))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))

    env = {"PATH": "/usr/bin:/bin", "HOME": str(travail), "TMPDIR": str(travail), "MPLBACKEND": "Agg",
           "PYTHONDONTWRITEBYTECODE": "1", "OPENBLAS_NUM_THREADS": "4", "LANG": "fr_FR.UTF-8"}
    t0 = time.time()
    # Groupe de processus à lui (tué en entier au dépassement), et une garde qui surveille la mémoire
    # et la taille du dossier : macOS n'applique pas de plafond de mémoire par rlimit.
    proc = subprocess.Popen(["/usr/bin/sandbox-exec", "-p", regles, str(python.absolute()), "-I", "-B",
                             str(travail / "calcul.py")], cwd=str(travail), env=env, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True, preexec_fn=limites, stdin=subprocess.DEVNULL,
                            start_new_session=True)
    groupes.ajouter(proc.pid)            # tué avec le serveur s'il meurt (Stop) : jamais sans garde
    raison = []

    def garder():
        while proc.poll() is None:
            try:
                rss_ko = int(subprocess.run(["/bin/ps", "-o", "rss=", "-p", str(proc.pid)], capture_output=True,
                                            text=True, timeout=5).stdout.strip() or 0)
            except (ValueError, subprocess.SubprocessError, OSError):
                rss_ko = 0
            taille = sum(f.stat().st_size for f in travail.rglob("*") if f.is_file())
            if rss_ko > MEMOIRE_MAX_KO or taille > DOSSIER_MAX or time.time() - t0 > delai_s + 10:
                raison.append("mémoire" if rss_ko > MEMOIRE_MAX_KO else ("dossier trop lourd" if taille > DOSSIER_MAX else "délai dépassé"))
                _tuer(proc)
                return
            time.sleep(0.5)

    import threading
    threading.Thread(target=garder, daemon=True).start()
    try:
        sortie, erreurs = proc.communicate()
    finally:
        groupes.retirer(proc.pid)
    code_retour = f"arrêté ({raison[0]})" if raison else proc.returncode
    duree = time.time() - t0
    produits = sorted(str(f) for f in travail.iterdir() if f.is_file() and f.name not in ("calcul.py", ".profil.sb"))
    morceaux = [f"Calcul exécuté en {duree:.1f} s (code de retour : {code_retour})."]
    if sortie.strip():
        morceaux.append("Sortie :\n" + _tronquer(sortie))
    if erreurs.strip():
        morceaux.append("Erreurs :\n" + _tronquer(erreurs))
    if produits:
        morceaux.append("Fichiers produits (lisibles avec Read) :\n" + "\n".join(f"- {f}" for f in produits[:30]))
    if not sortie.strip() and not erreurs.strip():
        morceaux.append("Aucune sortie : pense à print() les résultats.")
    return "\n\n".join(morceaux)


def _tuer(proc):
    import signal
    try:
        os.killpg(proc.pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError):
        pass


def _tronquer(t):
    return t if len(t) <= SORTIE_MAX else t[:SORTIE_MAX // 2] + "\n[…tronqué…]\n" + t[-SORTIE_MAX // 2:]
