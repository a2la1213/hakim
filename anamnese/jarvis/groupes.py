"""Les commandes que Jarvis lance (terminal, calcul) tournent chacune dans leur propre groupe de
processus, surveillé par un fil du serveur MCP (durée, mémoire, taille). Relecture Opus du 2026-10-16 :
quand le cockpit coupe Jarvis (Stop, interruption à la voix, arrêt), le serveur MCP meurt — et avec lui
la surveillance — mais la commande, dans sa propre session, continuait SANS AUCUNE limite. Ce registre
permet au serveur de tuer toutes ses commandes en cours avant de mourir."""
import atexit
import os
import signal
import threading

_EN_COURS = set()
_verrou = threading.Lock()


def ajouter(pid):
    with _verrou:
        _EN_COURS.add(pid)


def retirer(pid):
    """La commande est finie : son groupe entier est tué (un « & » laissé derrière elle ne survit pas,
    sans surveillance), puis oublié."""
    tuer(pid)
    with _verrou:
        _EN_COURS.discard(pid)


def en_cours():
    with _verrou:
        return set(_EN_COURS)


def tuer(pid):
    try:
        os.killpg(pid, signal.SIGKILL)
    except (ProcessLookupError, PermissionError, OSError):
        pass


def tuer_tout():
    for pid in en_cours():
        tuer(pid)


def installer_arret():
    """Dans un serveur MCP : à sa fin (normale, SIGTERM du cockpit, SIGHUP, Ctrl-C), ses commandes meurent."""
    atexit.register(tuer_tout)

    def _arret(signum, _frame):
        tuer_tout()
        os._exit(128 + signum)

    for s in (signal.SIGTERM, signal.SIGHUP, signal.SIGINT):
        signal.signal(s, _arret)
