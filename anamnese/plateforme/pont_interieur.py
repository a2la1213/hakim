"""Le pont, côté intérieur du bac à sable Linux (13/11 ; plateforme/bac_a_sable.py).

Lancé DANS le bac à sable (python -I -S : la bibliothèque standard seule) : il écoute 127.0.0.1:<port> dans le réseau à
part du bac à sable et mène chaque connexion à la socket Unix liée (/run/passerelle.sock), dont l'autre bout est la
passerelle gardée (jarvis/web.py). Puis il lance la commande, attend sa fin et rend son code. Il ne voit et ne peut rien de
plus que la commande elle-même.

Usage : pont_interieur.py <port> <socket> -- <commande…>
"""
import os
import signal
import socket
import subprocess
import sys
import threading


def pomper(a, b):
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


def relier(c, chemin):
    try:
        d = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        d.connect(chemin)
    except OSError:
        c.close()
        return
    pomper(c, d)


def ecouter(srv, chemin):
    while True:
        try:
            c, _ = srv.accept()
        except OSError:
            return
        threading.Thread(target=relier, args=(c, chemin), daemon=True).start()


def main(argv):
    if "--" not in argv or len(argv) < 4:
        print(__doc__, file=sys.stderr)
        return 2
    port, chemin = int(argv[0]), argv[1]
    commande = argv[argv.index("--") + 1:]
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("127.0.0.1", port))
    srv.listen(64)
    threading.Thread(target=ecouter, args=(srv, chemin), daemon=True).start()
    proc = subprocess.Popen(commande)
    for s in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(s, lambda n, _f: proc.send_signal(n))
    rc = proc.wait()
    if rc < 0:                                   # tué par un signal : le même pour le lanceur (le code reste lisible)
        signal.signal(-rc, signal.SIG_DFL)
        os.kill(os.getpid(), -rc)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
