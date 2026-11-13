"""Les clés (13/11). Sur le Mac : le trousseau (`security`), comme toujours. Ailleurs :
- par défaut, un fichier par clé dans ~/.config/naissance/cles/ (dossier 700, fichiers 600, écrits d'un coup) ;
- ou secret-tool (le trousseau de GNOME, si un service de secrets répond) quand NAISSANCE_CLES=secret-tool.
Le fichier n'est PAS chiffré : il est protégé par les droits de l'utilisateur et, surtout, par le bac à sable (le terminal de
l'IA et ses agents ne voient pas ~/.config : plateforme/bac_a_sable.py). Une clé n'est jamais écrite dans un journal ni dans
la ligne de commande d'un programme (secret-tool la lit sur son entrée standard)."""
import os
import re
import shutil
import subprocess
from pathlib import Path

from . import MAC

DOSSIER = Path(os.environ.get("NAISSANCE_CLES_DIR", Path.home() / ".config" / "naissance" / "cles"))
_NOM = re.compile(r"[^A-Za-z0-9._-]+")


def _mode():
    m = os.environ.get("NAISSANCE_CLES", "fichier")
    return "secret-tool" if m == "secret-tool" and shutil.which("secret-tool") else "fichier"


def chemin(service, compte=None):
    nom = _NOM.sub("_", str(service)) + (f"@{_NOM.sub('_', str(compte))}" if compte else "")
    return DOSSIER / nom


def lire(service, compte=None):
    """La clé, ou None. (Sur le Mac : le même appel que le code d'origine.)"""
    if MAC:
        args = ["/usr/bin/security", "find-generic-password", "-s", service] + (["-a", compte] if compte else []) + ["-w"]
        try:
            r = subprocess.run(args, capture_output=True, text=True, timeout=10)
        except (OSError, subprocess.SubprocessError):
            return None
        v = r.stdout.strip()
        return v if r.returncode == 0 and v else None
    if _mode() == "secret-tool":
        try:
            r = subprocess.run(["secret-tool", "lookup", "service", service] + (["account", compte] if compte else []),
                               capture_output=True, text=True, timeout=10)
            v = r.stdout.strip()
            return v if r.returncode == 0 and v else None
        except (OSError, subprocess.SubprocessError):
            return None
    for f in ([chemin(service, compte)] + ([] if compte else sorted(DOSSIER.glob(_NOM.sub("_", service) + "@*")))):
        try:
            v = f.read_text(encoding="utf-8").strip()
        except OSError:
            continue
        if v:
            return v
    return None


def present(service, compte=None):
    return lire(service, compte) is not None


def ecrire(service, valeur, compte=None):
    """Range la clé (remplace l'ancienne). Rend True si c'est fait."""
    valeur = str(valeur or "").strip()
    if not valeur:
        return False
    if MAC:
        r = subprocess.run(["/usr/bin/security", "-i"], capture_output=True, text=True, timeout=10,
                           input=f"add-generic-password -U -s {service} -a {compte or 'cle'} -w {valeur}\n")
        return r.returncode == 0
    if _mode() == "secret-tool":
        r = subprocess.run(["secret-tool", "store", "--label", service, "service", service] + (["account", compte] if compte else []),
                           input=valeur, capture_output=True, text=True, timeout=10)
        return r.returncode == 0
    DOSSIER.mkdir(parents=True, exist_ok=True)
    os.chmod(DOSSIER, 0o700)
    f = chemin(service, compte)
    tmp = f.with_name(f".{f.name}.{os.getpid()}")
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, (valeur + "\n").encode("utf-8"))
    finally:
        os.close(fd)
    os.replace(tmp, f)
    return True


def commande_lecture(service, compte=None):
    """Une commande shell qui écrit la clé sur sa sortie (pour apiKeyHelper de claude) ; la clé n'y figure pas."""
    if MAC:
        return f"/usr/bin/security find-generic-password -s {service} -w"
    if _mode() == "secret-tool":
        return f"secret-tool lookup service {service}"
    p = str(chemin(service, compte)).replace("'", "'\\''")
    return f"/bin/cat '{p}'"
