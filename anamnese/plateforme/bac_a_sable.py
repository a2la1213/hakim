"""Le bac à sable sous Linux (WSL2 compris) : bubblewrap (bwrap), à la place de sandbox-exec (13/11).

Les mêmes interdits que les profils du Mac (jarvis/terminal.py, calcul.py, chantiers.py, fichiers.py), par une autre
mécanique : sandbox-exec REFUSE ce qui n'est pas permis ; bwrap construit une racine VIDE où seul ce qui est permis
existe. Un fichier interdit n'y est donc pas « refusé » : il n'existe pas (« No such file or directory »).
- espaces de noms neufs (--unshare-all) : utilisateur, processus (il ne voit que les siens : process-info same-sandbox),
  réseau (ni Internet, ni le réseau de la maison, ni le cockpit, ni les sockets abstraites de l'hôte : D-Bus, X11, WSLg),
  IPC, nom d'hôte, cgroup ; aucun privilège (no_new_privs : sudo, su, crontab ne peuvent rien) ; il meurt avec son parent ;
- lecture : le système (/usr, /etc, /opt, les bibliothèques) et seulement les dossiers donnés ; écriture : seulement ceux
  donnés ; /tmp est un tmpfs neuf (les dossiers temporaires des autres programmes n'y sont pas) ; /dev minimal (ni les
  terminaux de l'utilisateur, ni les disques) ; /proc à lui ; pas de /run (ni D-Bus, ni systemd, ni l'interopérabilité
  de WSL : /run/WSL), pas de /mnt (ni les disques de Windows, ni powershell.exe, cmd.exe, wsl.exe), pas de /home sauf
  ce qui est donné, pas de ~/.config (les clés : plateforme/cles.py) ;
- le réseau du terminal : une seule sortie, la passerelle gardée (jarvis/web.py), par un pont : une socket Unix privée
  liée dans le bac à sable, et à l'intérieur 127.0.0.1:<port> qui y mène (pont_interieur.py) ; pas de DNS ;
- les noms interdits (une clé GitHub, les .keystore/.jks/.p12/.pfx/.pem/.key du téléphone) : recouverts au lancement
  (vides, en lecture seule) ; un fichier de ce nom CRÉÉ pendant la commande n'est pas recouvert (limite connue) ;
- le calcul : pas de shell ni d'autre programme (ni /bin ni /usr/bin dans sa racine) et pas de fork (un filtre seccomp :
  fork, vfork et clone sans CLONE_THREAD refusés ; les fils d'exécution de numpy restent permis).
"""
import os
import re
import shutil
import socket
import struct
import tempfile
import threading
from pathlib import Path

ICI = Path(__file__).resolve().parent
BWRAP = os.environ.get("NAISSANCE_BWRAP") or shutil.which("bwrap") or "/usr/bin/bwrap"
PONT_INTERIEUR = ICI / "pont_interieur.py"
SOCKET_INTERIEURE = "/run/passerelle.sock"

# les mêmes noms interdits que les profils du Mac (terminal.profil : « (deny file-read* file-write* (regex …)) »)
NOMS_INTERDITS = re.compile(r"^[Gg]it[Hh]ub[Kk]ey[^/]*$")
CLES_DU_TELEPHONE = re.compile(r"\.(keystore|jks|p12|pfx|pem|key)$")
SCAN_MAX = 50_000                      # entrées parcourues au plus pour recouvrir les noms interdits


def disponible():
    return Path(BWRAP).exists()


def _systeme(args, programmes=True):
    """La racine système en lecture seule. programmes=False : seulement les bibliothèques (le calcul : ni shell ni outil)."""
    if programmes:
        args += ["--ro-bind", "/usr", "/usr"]
    else:
        for d in ("/usr/lib", "/usr/lib64", "/usr/lib32", "/usr/libx32", "/usr/share/zoneinfo"):
            if Path(d).is_dir():
                args += ["--ro-bind", d, d]
    for d in ("/bin", "/sbin", "/lib", "/lib64", "/lib32", "/libx32"):
        p = Path(d)
        if p.is_symlink():                            # Ubuntu : /bin → usr/bin (le /usr fusionné)
            cible = os.readlink(d)
            if programmes or "lib" in d:
                args += ["--symlink", cible, d]
        elif p.is_dir() and (programmes or "lib" in d):
            args += ["--ro-bind", d, d]
    args += ["--ro-bind", "/etc", "/etc"]
    if programmes and Path("/opt").is_dir():
        args += ["--ro-bind", "/opt", "/opt"]
    if Path("/sys/devices/system/cpu").is_dir():   # le nombre de cœurs (numpy, onnxruntime) ; rien d'autre de /sys
        args += ["--ro-bind", "/sys/devices/system/cpu", "/sys/devices/system/cpu"]
    # /dev minimal (ni disques ni terminaux de l'hôte) ; /dev/shm à lui (les sémaphores de multiprocessing : ipc-posix-shm du Mac)
    args += ["--proc", "/proc", "--dev", "/dev", "--tmpfs", "/dev/shm", "--tmpfs", "/tmp"]
    return args


def _masques(racines, telephone=None):
    """Les chemins à recouvrir : les noms interdits partout où le bac à sable lit, les clés dans les fichiers du téléphone."""
    vus, trouves = 0, []
    for racine in racines:
        racine = Path(racine)
        if not racine.is_dir():
            continue
        for dossier, sous, fichiers in os.walk(racine):
            vus += len(sous) + len(fichiers)
            if vus > SCAN_MAX:
                break
            tel = telephone is not None and (Path(dossier) == Path(telephone) or Path(telephone) in Path(dossier).parents)
            for n in list(sous):
                if NOMS_INTERDITS.match(n):
                    trouves.append((Path(dossier) / n, True))
                    sous.remove(n)
            for n in fichiers:
                if NOMS_INTERDITS.match(n) or (tel and CLES_DU_TELEPHONE.search(n)):
                    trouves.append((Path(dossier) / n, False))
    return trouves


def _recouvrir(args, masques):
    for chemin, est_dossier in masques:
        if est_dossier:
            args += ["--tmpfs", str(chemin), "--remount-ro", str(chemin)]
        else:
            args += ["--ro-bind", "/dev/null", str(chemin)]
    return args


def commande(argv, lectures=(), ecritures=(), fichiers_lus=(), reseau=None, programmes=True, chdir=None,
             telephone=None, liaisons=(), hote="bac-a-sable", masquer_dans=()):
    """La ligne de commande bwrap qui lance `argv`.
    lectures / ecritures : dossiers (même chemin dedans et dehors) ; fichiers_lus : fichiers seuls, en lecture ;
    reseau : None (aucun : sa propre boucle locale seulement) ou un port (la passerelle par le pont : 127.0.0.1:<port>) ;
    liaisons : (source, cible, écriture?) en plus (le pont, le lanceur intérieur) ; masquer_dans : les dossiers où chercher
    les noms interdits (ceux du terminal : les fichiers qu'on lui donne et ceux du téléphone ; pas ses outils ni son atelier)."""
    args = [BWRAP, "--unshare-all", "--die-with-parent", "--hostname", hote]
    _systeme(args, programmes=programmes)
    for p in lectures:
        if Path(p).exists():
            args += ["--ro-bind", str(p), str(p)]
    for f in fichiers_lus:
        if Path(f).is_file():
            args += ["--ro-bind", str(f), str(f)]
    for p in ecritures:
        Path(p).mkdir(parents=True, exist_ok=True)
        args += ["--bind", str(p), str(p)]
    for source, cible, ecrire in liaisons:
        args += ["--bind" if ecrire else "--ro-bind", str(source), str(cible)]
    _recouvrir(args, _masques(masquer_dans, telephone=telephone))
    if chdir:
        args += ["--chdir", str(chdir)]
    return args + ["--", *[str(a) for a in argv]]


# ---- le pont vers la passerelle gardée ----

class Pont:
    """Une socket Unix privée (dossier 700) dont chaque connexion est menée à 127.0.0.1:<port> (la passerelle gardée).
    Liée dans le bac à sable en /run/passerelle.sock ; pont_interieur.py y mène 127.0.0.1:<port> du dedans."""

    def __init__(self, port):
        self.port = int(port)
        base = os.environ.get("XDG_RUNTIME_DIR") if os.access(os.environ.get("XDG_RUNTIME_DIR", "") or "/nonexistent", os.W_OK) else None
        self.dossier = Path(tempfile.mkdtemp(prefix="pont-", dir=base))
        os.chmod(self.dossier, 0o700)
        self.chemin = self.dossier / "passerelle.sock"
        self._s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._s.bind(str(self.chemin))
        os.chmod(self.chemin, 0o600)
        self._s.listen(64)
        threading.Thread(target=self._accepter, daemon=True).start()

    def _accepter(self):
        while True:
            try:
                c, _ = self._s.accept()
            except OSError:
                return
            threading.Thread(target=self._relier, args=(c,), daemon=True).start()

    def _relier(self, c):
        try:
            d = socket.create_connection(("127.0.0.1", self.port), timeout=10)
            d.settimeout(None)
        except OSError:
            c.close()
            return
        pomper(c, d)


def pomper(a, b):
    """Recopie dans les deux sens jusqu'à la fin des deux côtés."""
    def sens(x, y):
        try:
            while True:
                m = x.recv(65536)
                if not m:
                    break
                y.sendall(m)
        except OSError:
            pass
        finally:
            try:
                y.shutdown(socket.SHUT_WR)
            except OSError:
                pass
    t = threading.Thread(target=sens, args=(b, a), daemon=True)
    t.start()
    sens(a, b)
    t.join()
    for s in (a, b):
        try:
            s.close()
        except OSError:
            pass


_ponts = {}
_verrou = threading.Lock()


def pont(port):
    with _verrou:
        p = _ponts.get(int(port))
        if p is None or not p.chemin.exists():
            p = _ponts[int(port)] = Pont(port)
        return p


# ---- les quatre bacs à sable ----

def terminal(commande_zsh, atelier, port, lectures, ecritures, fichiers_lus, python, telephone=None, masquer_dans=()):
    """Le terminal de l'IA (jarvis/terminal.py) : zsh dans son atelier ; réseau par la passerelle seulement (port), ou
    aucun (port 9 : le juge de nuit). `python` lance le pont intérieur (le venv de l'IA, lisible dans le bac à sable)."""
    argv = ["/bin/zsh", "-f", "-c", commande_zsh]
    liaisons = []
    if port and int(port) != 9:
        p = pont(port)
        liaisons = [(p.chemin, SOCKET_INTERIEURE, True), (PONT_INTERIEUR, "/run/pont_interieur.py", False)]
        argv = [str(python), "-I", "-S", "/run/pont_interieur.py", str(int(port)), SOCKET_INTERIEURE, "--", *argv]
    return commande(argv, lectures=lectures, ecritures=ecritures, fichiers_lus=fichiers_lus, liaisons=liaisons,
                    chdir=atelier, telephone=telephone, hote="atelier", masquer_dans=masquer_dans)


def calcul(python, script, travail, lectures):
    """Le calcul (jarvis/calcul.py) : ce Python seulement, ni réseau, ni shell, ni fork. Rend (args, fd du filtre seccomp)."""
    fd = filtre_sans_fork()
    args = commande([python, "-I", "-B", script], lectures=lectures, ecritures=[travail], programmes=False, chdir=travail,
                    hote="calcul")
    i = args.index("--")
    return args[:i] + ["--seccomp", str(fd)] + args[i:], fd


def tests(suite, essai, lectures, fichiers_lus):
    """Les tests d'un chantier (jarvis/chantiers.py) : écriture dans l'essai seul, réseau : sa propre boucle locale
    seulement (aucun port de la machine, plus strict que le Mac qui garde la boucle locale sauf les ports ouverts)."""
    return commande(suite, lectures=lectures, ecritures=[essai], fichiers_lus=fichiers_lus, chdir=essai, hote="chantier")


def decodeur(argv, lecture, ecriture):
    """Un décodeur (jarvis/fichiers.py : pdftotext, ffprobe…) : il lit ce fichier, écrit dans ce dossier, sans réseau."""
    lecture = Path(lecture)
    return commande(argv, lectures=[lecture] if lecture.is_dir() else [], fichiers_lus=[lecture] if lecture.is_file() else [],
                    ecritures=[ecriture], chdir=ecriture, hote="decodeur")


# ---- le filtre seccomp « sans fork » (BPF écrit à la main : pas de dépendance) ----

_AUDIT_ARCH_X86_64, _AUDIT_ARCH_AARCH64 = 0xC000003E, 0xC00000B7
_CLONE_THREAD = 0x00010000
_RET_ALLOW = 0x7FFF0000
_EPERM, _ENOSYS = 1, 38                  # les numéros de LINUX (le module errno de Python donne ceux de la machine : 78 sur le Mac)


def _errno(e):
    return 0x00050000 | (e & 0xFFFF)


def programme_sans_fork():
    """Le programme BPF : fork, vfork, clone sans CLONE_THREAD → EPERM ; clone3 → ENOSYS (la glibc retombe sur clone,
    les fils d'exécution restent permis) ; l'ABI x32 refusée. x86_64 et aarch64 (Rosetta traduit vers aarch64)."""
    LD_W_ABS, JEQ, JGE, JSET, RET = 0x20, 0x15, 0x35, 0x45, 0x06
    i = []

    def ins(code, jt, jf, k):
        i.append([code, jt, jf, k])

    # les sauts comptent à partir de l'instruction SUIVANTE (cible = n + 1 + saut)
    ins(LD_W_ABS, 0, 0, 4)                        # 0  arch
    ins(JEQ, 2, 0, _AUDIT_ARCH_X86_64)            # 1  → 4 (x86_64)
    ins(JEQ, 7, 0, _AUDIT_ARCH_AARCH64)           # 2  → 10 (aarch64)
    ins(RET, 0, 0, _RET_ALLOW)                    # 3  autre architecture : rien
    ins(LD_W_ABS, 0, 0, 0)                        # 4  x86_64 : nr
    ins(JGE, 9, 0, 0x40000000)                    # 5  ABI x32 → 15 (EPERM)
    ins(JEQ, 8, 0, 57)                            # 6  fork → 15
    ins(JEQ, 7, 0, 58)                            # 7  vfork → 15
    ins(JEQ, 8, 0, 435)                           # 8  clone3 → 17 (ENOSYS)
    ins(JEQ, 3, 6, 56)                            # 9  clone → 13 ; sinon → 16
    ins(LD_W_ABS, 0, 0, 0)                        # 10 aarch64 : nr
    ins(JEQ, 5, 0, 435)                           # 11 clone3 → 17
    ins(JEQ, 0, 3, 220)                           # 12 clone → 13 ; sinon → 16
    ins(LD_W_ABS, 0, 0, 16)                       # 13 drapeaux (les 32 bits bas de args[0])
    ins(JSET, 1, 0, _CLONE_THREAD)                # 14 un fil d'exécution → 16 ; sinon → 15
    ins(RET, 0, 0, _errno(_EPERM))           # 15
    ins(RET, 0, 0, _RET_ALLOW)                    # 16
    ins(RET, 0, 0, _errno(_ENOSYS))          # 17
    return i


def _assembler(prog):
    return b"".join(struct.pack("<HBBI", c, jt, jf, k) for c, jt, jf, k in prog)


def filtre_sans_fork():
    """Un descripteur (tube) qui contient le filtre, à passer à bwrap par --seccomp (pass_fds)."""
    lu, ecrit = os.pipe()
    os.write(ecrit, _assembler(programme_sans_fork()))
    os.close(ecrit)
    return lu
