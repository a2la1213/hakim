"""Le terminal de Jarvis (demande d'Ahmed, 2026-10-16 : « il faudrait lui donner accès au terminal » ;
Jarvis lui-même : « je ne peux pas télécharger de vraies données ni mesurer un vrai GPU »).

Un VRAI shell (zsh) dans son atelier `~/AIOS/jarvis/cwd/atelier` (persistant, lisible par Read) :
- internet, mais seulement par une passerelle locale (le mandataire gardé de jarvis/web.py) :
  jamais une adresse locale ou privée (le cockpit, Ollama, le réseau de la maison) ;
- le GPU (MLX / Metal), Python avec numpy, scipy, sympy, mlx (venv de Jarvis), pip et uv pour
  installer DANS l'atelier, curl, git, ffmpeg ;
- les fichiers qu'Ahmed lui donne (pièces jointes et fichiers préparés, dans `fichiers/`) ;
- MAIS ni ses projets, ni ses clés, ni le reste de son dossier personnel, ni les dossiers
  temporaires des autres programmes : le bac à sable (sandbox-exec) refuse la lecture hors de
  l'atelier, des pièces jointes, du venv et des outils, et toute écriture hors de l'atelier ;
- durée, mémoire et taille de l'atelier surveillées ; groupe de processus tué en entier.
Agir sur ses projets (git, code dans ~/Desktop) viendra commande par commande, avec son accord.
"""
import json
import os
import shutil
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI))
import groupes  # noqa: E402
import priorite  # noqa: E402
CWD = Path.home() / "AIOS" / "jarvis" / "cwd"
ATELIER = CWD / "atelier"
FICHIERS = CWD / "fichiers"
# (Ahmed, 2026-10-22 : « lecture ET écriture ») les fichiers de son téléphone, synchronisés dans les deux sens par
# Syncthing (dossier « Z Fold 7 », corbeille de 30 jours sur le Mac) : le seul endroit hors de l'atelier où Hakim écrit
TELEPHONE = FICHIERS / "telephone"
VENV = ICI / ".venv"
DELAI_S = 120
DELAI_MAX_S = 1800
SORTIE_MAX = 20_000
MEMOIRE_MAX_KO = 6 * 1024 * 1024         # 6 Go : le Mac en a 16, la voix et Whisper en tiennent déjà ~6
ATELIER_MAX_KO = 10 * 1024 * 1024        # 10 Go de téléchargements et de résultats au plus (5 Go jusqu'au 21/10, Ahmed)

_proxy = None
_verrou = threading.Lock()


# Provenance (H6 + X1, 2026-10-20) : une sortie réseau du terminal fait entrer un contenu de tiers dans le tour de
# Hakim. La passerelle le note dans la marque du tour (provenance.py : une ligne en ajout seul, que le cockpit lit
# et retire à la fin du tour) — une ligne par hôte et par minute au plus.
MARQUE_EXTERNE = Path.home() / "AIOS" / "jarvis" / "tour-externe.jsonl"   # (audit du 2026-10-23) pas de variable d'environnement
_sorties_notees = {}


def noter_sortie(hote, marque=None):
    maintenant = time.time()
    m = Path(marque or MARQUE_EXTERNE)
    # (relecture Opus du 2026-10-20) la minute de répit ne vaut que tant que la marque du tour existe : un tour neuf
    # (marque retirée par le cockpit) qui recontacte le même hôte est marqué à son tour
    if m.exists() and maintenant - _sorties_notees.get(hote, 0) < 60:
        return False
    _sorties_notees[hote] = maintenant
    try:                                   # l'hôte devient connu (hors lecture privée) pour la règle de sortie
        import sortie
        sortie.noter(f"https://{hote}/")
    except Exception:
        pass
    try:
        fd = os.open(m, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            os.write(fd, (json.dumps({"outil": f"terminal → {hote}"[:120], "ts": maintenant}, ensure_ascii=False) + "\n").encode())
        finally:
            os.close(fd)
        return True
    except OSError:
        return False


def avant_connexion(hote):
    """(relecture Opus du 2026-10-20) la règle de sortie à la passerelle, AVANT la résolution du nom ; depuis l'audit
    du 2026-10-23, pendant une lecture privée, seuls les dépôts d'outils passent sans le geste d'Ahmed (jarvis/sortie.py)."""
    import sortie
    import web
    try:
        sortie.verifier_terminal(hote)          # (audit du 2026-10-23) sites d'outils seulement, ou le geste d'Ahmed
    except sortie.Refus as e:
        raise web.Refus(str(e))


def passerelle():
    """Le mandataire gardé (une fois par processus) : toute sortie réseau du terminal passe par lui."""
    global _proxy
    with _verrou:
        if _proxy is None:
            sys.path.insert(0, str(ICI))
            import web
            _proxy = web._ProxyGarde()
            _proxy.sur_sortie = noter_sortie
            _proxy.avant_connexion = avant_connexion
        return _proxy


def _chemins_outils():
    uv_python = Path.home() / ".local" / "share" / "uv"
    return [VENV.resolve(), uv_python, Path.home() / ".local" / "bin"]


# Les services de macOS qui feraient sortir une commande de son bac à sable (relecture JARVIS 2, C1, 2026-10-20) :
# lancer une app ou un fichier (Launch Services), soumettre une tâche au système (launchd), écrire des réglages
# (cfprefsd), piloter d'autres apps (Apple Events), le presse-papiers, le trousseau, la capture d'écran.
SERVICES_REFUSES = ["com.apple.coreservices.launchservicesd", "com.apple.lsd.mapdb", "com.apple.lsd.modifydb",
                    "com.apple.lsd.open", "com.apple.lsd.xpc", "com.apple.lsd.advertisingidentifiers",
                    "com.apple.cfprefsd.daemon", "com.apple.cfprefsd.agent", "com.apple.pasteboard.1",
                    "com.apple.coreservices.appleevents", "com.apple.SecurityServer", "com.apple.securityd.xpc",
                    "com.apple.xpc.smd", "com.apple.backgroundtaskmanagementagent", "com.apple.backgroundtaskmanagement.agent",
                    "com.apple.tccd", "com.apple.tccd.system", "com.apple.screencaptureui.agent", "com.apple.replayd",
                    "com.apple.windowserver.active", "com.apple.dock.server", "com.apple.coreservices.quarantine-resolver",
                    # (relecture Opus du 2026-10-20) téléchargements HORS du processus (nsurlsessiond : la garde réseau ne
                    # les verrait pas), éléments d'ouverture et récents (sharedfilelistd : persistance), index Spotlight
                    # (mds : noms et métadonnées de tous les fichiers d'Ahmed)
                    "com.apple.nsurlsessiond", "com.apple.nsurlsessiond.NSURLSessionProxyService",
                    "com.apple.coreservices.sharedfilelistd.xpc", "com.apple.coreservices.sharedfilelistd.mig",
                    "com.apple.coreservices.sharedfilelistd.async-mig", "com.apple.metadata.mds", "com.apple.metadata.mds.legacy"]
PROGRAMMES_REFUSES = ["/usr/bin/open", "/bin/launchctl", "/usr/bin/osascript", "/usr/bin/defaults", "/usr/bin/security",
                      "/usr/bin/pbcopy", "/usr/bin/pbpaste", "/usr/bin/automator", "/usr/bin/shortcuts", "/usr/bin/sudo",
                      "/usr/bin/su", "/usr/bin/login", "/usr/bin/at", "/usr/bin/crontab", "/usr/sbin/screencapture",
                      "/usr/bin/tccutil", "/usr/bin/sfltool", "/usr/bin/killall", "/usr/bin/caffeinate", "/usr/sbin/systemsetup",
                      "/usr/bin/plutil", "/usr/libexec/PlistBuddy", "/usr/sbin/networksetup", "/usr/bin/say", "/usr/bin/afplay"]


XCODE_OUTILS = "/Applications/Xcode.app/Contents/Developer/Toolchains/XcodeDefault.xctoolchain/usr/bin"
SDK_MACOS = "/Applications/Xcode.app/Contents/Developer/Platforms/MacOSX.platform/Developer/SDKs/MacOSX.sdk"
JDK = Path("/usr/local/opt/openjdk")      # Java (Homebrew, « keg-only » : pas dans /usr/local/bin)


def profil(atelier, port, fichiers=None, telephone=None):
    """TOUT est refusé par défaut (relecture JARVIS 2, C1, 2026-10-20 : « allow default » laissait joignables les
    services de macOS — ouvrir une app, soumettre une tâche à launchd, écrire des réglages — donc une sortie du bac à
    sable). Sont permis : le socle système d'Apple (system.sb), l'exécution des programmes du système et de ses outils
    (sauf ceux qui pilotent le Mac : open, launchctl, osascript, defaults…), la lecture des dossiers système, de son
    atelier, de ../fichiers et de ses outils ; l'écriture dans l'atelier et dans les fichiers du téléphone seulement ; le réseau par la seule passerelle
    gardée ; les services Mach sauf ceux qui font sortir (SERVICES_REFUSES) ; le GPU (MLX, Metal)."""
    fichiers = FICHIERS if fichiers is None else fichiers
    telephone = TELEPHONE if telephone is None else telephone
    ecritures = f' (subpath "{telephone.resolve()}")' if telephone.exists() else ""
    lectures = "".join(f' (subpath "{p}")' for p in [atelier, fichiers.resolve() if fichiers.exists() else fichiers]
                       + _chemins_outils())
    programmes = "".join(f' (literal "{p}")' for p in PROGRAMMES_REFUSES)
    services = "".join(f' (global-name "{n}")' for n in SERVICES_REFUSES)
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
  (subpath "/opt") (subpath "/Applications/Xcode.app/Contents/Developer") (subpath "/Applications/Xcode.app/Contents/SharedFrameworks") (subpath "/private/etc")
  (subpath "/private/var/db/timezone") (subpath "/private/var/select") (subpath "/private/var/db/xcode_select_link")
  (literal "/dev") (literal "/dev/null") (literal "/dev/zero") (literal "/dev/random") (literal "/dev/urandom") (literal "/dev/tty") (literal "/dev/dtracehelper") (literal "/dev/autofs_nowait") (regex #"^/dev/fd/") (literal "/etc") (literal "/var") (literal "/tmp") (literal "/private") (literal "/private/var"){lectures})
(deny file-read* (subpath "/Library/Keychains") (subpath "/Library/Application Support/com.apple.TCC"))
(allow file-write* (subpath "{atelier}"){ecritures} (literal "/dev/null") (literal "/dev/zero") (literal "/dev/tty") (literal "/dev/dtracehelper")
  (regex #"^/dev/fd/"))
(allow file-ioctl (literal "/dev/tty") (literal "/dev/dtracehelper"))
(allow network-outbound (remote ip "localhost:{port}"))
; (relecture Opus du 2026-10-20) plus de résolveur DNS local (mDNSResponder) : les noms passent par la passerelle, et
; un nom inventé (des données en sous-domaine) ne sort plus par une requête DNS. Sondé : curl, git, pip/uv, yt-dlp,
; httpx et urllib marchent par la passerelle.
(allow system-socket)
(allow mach-lookup)
(deny mach-lookup{services})
(allow iokit-open)
(allow iokit-get-properties)
(allow ipc-posix-shm*)
(allow ipc-posix-sem*)
(allow user-preference-read)
(allow pseudo-tty)
"""


def _taille_ko(chemin):
    try:
        return int(subprocess.run(["/usr/bin/du", "-sk", str(chemin)], capture_output=True, text=True,
                                  timeout=20).stdout.split()[0])
    except (ValueError, IndexError, subprocess.SubprocessError, OSError):
        return 0


ATELIER_ALERTE_KO = 8 * 1024 * 1024       # demande de Hakim (2026-10-20, accord d'Ahmed) : prévenu à 80 % (8 Go sur 10)


_mesure_atelier = {"t": 0.0, "ko": 0}


def alerte_atelier(atelier=None, taille_ko=None):
    """Une phrase d'alerte si l'atelier dépasse 8 Go (à 10 Go, la commande en cours est tuée net) ; sinon ''.
    La taille est mesurée au plus une fois par minute (du sur 10 Go prend du temps)."""
    if taille_ko is None:
        if time.time() - _mesure_atelier["t"] > 60:
            _mesure_atelier.update(t=time.time(), ko=_taille_ko(atelier or ATELIER))
        taille_ko = _mesure_atelier["ko"]
    ko = taille_ko
    if ko < ATELIER_ALERTE_KO:
        return ""
    go = lambda k: f"{k / (1024 * 1024):.1f}".replace(".", ",")
    return (f"⚠ Ton atelier pèse {go(ko)} Go sur {go(ATELIER_MAX_KO)} : au-delà, la commande en cours est arrêtée net. "
            "Fais de la place maintenant (supprime ou compresse ce qui ne sert plus : caches, gros résultats intermédiaires).")


def preparer(commande, atelier, port):
    """(arguments, environnement) pour lancer `commande` (zsh) sous le bac à sable de l'atelier, avec la
    passerelle réseau sur `port`. Partagé par l'exécution directe et les tâches de fond (taches.py)."""
    (atelier / ".tmp").mkdir(parents=True, exist_ok=True)
    # Le profil passe EN LIGNE (-p), jamais par un fichier : relecture Opus du 2026-10-20, il était écrit dans
    # atelier/.tmp (que Hakim écrit) sous un nom prévisible — un lien symbolique posé là faisait écraser un fichier
    # hors de l'atelier par le serveur, et un tube nommé aurait pu servir un profil permissif.
    regles = profil(atelier, port)
    mandataire = f"http://127.0.0.1:{port}"
    env = {
        "HOME": str(atelier), "TMPDIR": str(atelier / ".tmp"), "LANG": "fr_FR.UTF-8", "TERM": "dumb",
        "TMPPREFIX": str(atelier / ".tmp" / "zsh"),       # les heredocs de zsh (sinon /tmp, refusé)
        # les outils de développement d'Xcode en direct (git, clang…) : le relais /usr/bin/git passe par xcrun, qui veut
        # écrire son cache dans /var/folders — refusé par le bac à sable « tout refusé par défaut » (C1, 2026-10-20)
        "PATH": ":".join([str(atelier / ".venv" / "bin"), str(VENV / "bin"), "/usr/local/bin", "/opt/homebrew/bin",
                          "/Applications/Xcode.app/Contents/Developer/usr/bin", XCODE_OUTILS, str(JDK / "bin"),
                          str(Path.home() / ".local" / "bin"), "/usr/bin", "/bin", "/usr/sbin", "/sbin"]),
        "HTTP_PROXY": mandataire, "HTTPS_PROXY": mandataire, "ALL_PROXY": mandataire,
        "http_proxy": mandataire, "https_proxy": mandataire, "all_proxy": mandataire, "NO_PROXY": "", "no_proxy": "",
        "PIP_CACHE_DIR": str(atelier / ".cache" / "pip"), "UV_CACHE_DIR": str(atelier / ".cache" / "uv"),
        "HF_HOME": str(atelier / ".cache" / "huggingface"), "MPLBACKEND": "Agg", "PYTHONUNBUFFERED": "1",
        "GIT_TERMINAL_PROMPT": "0",
        # (2026-10-21, demande d'Ahmed : « écrire en LaTeX, en faire des PDF, coder dans tous les langages ») : clang,
        # clang++, swift et l'éditeur de liens de Rust pris dans la chaîne d'Xcode en direct (le relais /usr/bin/clang
        # passe par xcrun, qui ne trouve pas Xcode dans le bac à sable) ; le cache de Tectonic (LaTeX → PDF) dans
        # l'atelier, pré-rempli des paquets courants, le reste téléchargé par la passerelle.
        "DEVELOPER_DIR": "/Applications/Xcode.app/Contents/Developer", "SDKROOT": SDK_MACOS,
        "TECTONIC_CACHE_DIR": str(atelier / ".cache" / "tectonic"),
        "CLANG_MODULE_CACHE_PATH": str(atelier / ".cache" / "clang-modules"),   # Swift et clang (sinon /var/folders, refusé)
        "GOCACHE": str(atelier / ".cache" / "go-build"), "GOPATH": str(atelier / "go"),
        "JAVA_HOME": str(JDK), "COMPOSER_HOME": str(atelier / ".cache" / "composer"),
    }
    # (2026-10-23) en priorité basse : sa voix et Whisper passent devant (priorite.py)
    return priorite.basse(["/usr/bin/sandbox-exec", "-p", regles, "/bin/zsh", "-f", "-c", commande]), env


def surveiller(proc, t0, delai_s, atelier, raison):
    """La garde (bloquante) : durée, mémoire, taille de l'atelier ; tue le groupe et note la raison."""
    dernier_du = 0.0
    while proc.poll() is None:
        if time.time() - t0 > delai_s:
            raison.append(f"délai de {delai_s} s dépassé")
        else:
            try:
                rss = subprocess.run(["/bin/ps", "-o", "rss=", "-g", str(proc.pid)], capture_output=True,
                                     text=True, timeout=5).stdout.split()
                if sum(int(x) for x in rss if x.isdigit()) > MEMOIRE_MAX_KO:
                    raison.append("mémoire (6 Go) dépassée")
            except (subprocess.SubprocessError, OSError):
                pass
            if not raison and time.time() - dernier_du > 10:
                dernier_du = time.time()
                if _taille_ko(atelier) > ATELIER_MAX_KO:
                    raison.append(f"atelier plein ({ATELIER_MAX_KO // (1024 * 1024)} Go)")
        if raison:
            try:
                os.killpg(proc.pid, signal.SIGKILL)
            except (ProcessLookupError, PermissionError):
                pass
            return
        time.sleep(0.5)


def executer(commande, delai_s=DELAI_S, atelier=None):
    """Exécute `commande` (zsh) dans l'atelier, sous bac à sable. Rend un texte."""
    if not isinstance(commande, str) or not commande.strip():
        return "Aucune commande."
    if len(commande) > 50_000:
        return "Commande trop longue (50 000 caractères au plus)."
    delai_s = max(1, min(int(delai_s or DELAI_S), DELAI_MAX_S))
    atelier = Path(atelier or ATELIER)
    (atelier / ".tmp").mkdir(parents=True, exist_ok=True)
    atelier = atelier.resolve()
    proxy = passerelle()
    args, env = preparer(commande, atelier, proxy.port)
    t0 = time.time()
    proc = subprocess.Popen(args, cwd=str(atelier), env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            stdin=subprocess.DEVNULL, text=True, errors="replace", start_new_session=True)
    groupes.ajouter(proc.pid)            # tuée avec le serveur s'il meurt (Stop) : jamais sans garde
    raison = []
    threading.Thread(target=surveiller, args=(proc, t0, delai_s, atelier, raison), daemon=True).start()
    try:
        sortie, _ = proc.communicate()
    finally:
        groupes.retirer(proc.pid)        # le groupe entier : rien ne reste en arrière-plan
    duree = time.time() - t0
    etat = f"arrêtée ({raison[0]})" if raison else f"code de retour {proc.returncode}"
    texte = sortie or ""
    if len(texte) > SORTIE_MAX:
        texte = texte[:SORTIE_MAX // 2] + "\n[…tronqué…]\n" + texte[-SORTIE_MAX // 2:]
    bloques = [f"- {c} : {r}" for c, r in proxy.refus[-5:]]
    proxy.refus.clear()
    morceaux = [f"Commande exécutée dans l'atelier ({atelier}) en {duree:.1f} s, {etat}."]
    import enveloppe
    morceaux.append("Sortie :\n" + enveloppe.enveloppe(texte, "sortie de ta commande (peut contenir du texte venu d'internet)")
                    if texte.strip() else "(aucune sortie)")
    if bloques:
        morceaux.append("Connexions bloquées par la garde (adresses locales ou privées) :\n" + "\n".join(bloques))
    return "\n\n".join(morceaux)


def vider_atelier(atelier=None):
    atelier = Path(atelier or ATELIER)
    if atelier.exists():
        shutil.rmtree(atelier, ignore_errors=True)
