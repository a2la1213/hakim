"""Embeddings AUTONOMES via model2vec (statique, CPU, multilingue).

Remplace Ollama pour le MCP : aucun serveur externe, aucun onnxruntime.
Le modèle (potion-multilingual-128M, 256-dim) se charge à la 1re utilisation et
est mis en cache par HuggingFace.

(09/11, Ahmed : « alléger le Mac et accélérer tout le process ») UN SEUL processus garde le modèle en mémoire : le
serveur de rappel (cli.py rappel-serveur, lancé par le cockpit) ouvre la socket locale data/sens.sock (servir()). Les
autres (démon, MCP, corps.py serveur et ses commandes d'un coup) lui demandent le vecteur de leur texte au lieu de charger
chacun leur copie : mesuré le 09/11, le modèle pèse 1,33 Go par processus et met ~13 s à se charger. Le vecteur rendu est
EXACTEMENT celui d'un chargement local (même modèle, même appel encode([texte]), flottants transmis sans perte en JSON).
Repli : serveur absent → chargement local paresseux, comme avant ; dès que le serveur revient, la copie locale est rendue.
ANAMNESE_EMBED_DISTANT=0 garde l'ancien comportement (toujours local).
"""
import gc
import json
import os
import socket
import threading
import time

import config

_model = None
_verrou_modele = threading.Lock()          # un seul chargement, et un encode à la fois dans un même processus

SOCK = config.EMBED_SOCK
LOCAL_SEUL = os.environ.get("ANAMNESE_EMBED_DISTANT", "1") == "0"
REESSAI_S = 60.0                           # modèle chargé ici (repli) : on regarde si le serveur est revenu, au plus 1 fois/min
DELAI_CONNEXION_S = 1.0
DELAI_REPONSE_S = 60.0                     # le serveur qui démarre charge son modèle (~13 s, plus si le Mac swappe)
ATTENTE_REFUS_S = 3.0                      # socket présente mais refusée : le cockpit relance le serveur en ~3 s

_client = None                             # (pid, socket, fichier de lecture) : une connexion gardée par processus
_verrou_client = threading.Lock()
_essai_ts = 0.0
_priorite = threading.Event()              # côté serveur : levé quand aucun rappel du cockpit n'est en cours
_priorite.set()


def _get():
    global _model
    with _verrou_modele:
        if _model is None:
            from model2vec import StaticModel
            _model = StaticModel.from_pretrained(config.EMBED_MODEL_M2V)
        return _model


def _local(text):
    m = _get()
    with _verrou_modele:
        vec = m.encode([text])[0]
    return [float(x) for x in vec]


def _fermer_client():
    global _client
    if _client is not None:
        for x in (_client[2], _client[1]):
            try:
                x.close()
            except OSError:
                pass
    _client = None


def _connecter(attendre=True):
    """La socket connectée au serveur, ou None s'il n'y en a pas (rien n'écoute à SOCK)."""
    fin = time.monotonic() + (ATTENTE_REFUS_S if attendre else 0.0)
    while True:
        if not os.path.exists(SOCK):
            return None
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        s.settimeout(DELAI_CONNEXION_S)
        try:
            s.connect(SOCK)
            s.settimeout(DELAI_REPONSE_S)
            return s
        except OSError:
            s.close()
            if time.monotonic() >= fin:      # socket périmée (serveur mort sans nettoyer) : personne ne revient
                return None
            time.sleep(0.25)


def distant(text, attendre=True):
    """Le vecteur de `text` demandé au serveur du sens, ou None (serveur absent, en panne ou trop lent). attendre=False :
    une socket refusée n'est pas réessayée (le modèle est déjà chargé ici, rien ne presse)."""
    global _client
    with _verrou_client:
        for essai in (0, 1):
            if _client is not None and _client[0] != os.getpid():
                _client = None                   # connexion héritée d'un fork : jamais partagée avec le parent
            if _client is None:
                s = _connecter(attendre)
                if s is None:
                    return None
                _client = (os.getpid(), s, s.makefile("rb"))
            _pid, s, f = _client
            try:
                s.sendall((json.dumps({"texte": text}) + "\n").encode("ascii"))   # ASCII : même un texte cassé (surrogates) passe
                ligne = f.readline()
                if not ligne:
                    raise ConnectionError("serveur du sens fermé")
                v = json.loads(ligne).get("vecteur")
                return v if isinstance(v, list) else None
            except socket.timeout:
                _fermer_client()                 # trop lent : pas de seconde attente, repli local
                return None
            except (OSError, ValueError):
                _fermer_client()                 # connexion d'un serveur relancé depuis : une seconde chance
        return None


def _liberer():
    """Le serveur est revenu : la copie locale du modèle (1,33 Go) est rendue."""
    global _model
    with _verrou_modele:
        _model = None
    gc.collect()


def embed(text):
    """Retourne un vecteur (list[float]) pour `text`."""
    global _essai_ts
    if LOCAL_SEUL or not isinstance(text, str):      # autre chose qu'un texte : exactement l'appel d'avant
        return _local(text)
    if _model is not None:
        maintenant = time.monotonic()
        if maintenant - _essai_ts < REESSAI_S:
            return _local(text)
        _essai_ts = maintenant
        v = distant(text, attendre=False) if os.path.exists(SOCK) else None
        if v is None:
            return _local(text)
        _liberer()
        return v
    v = distant(text)
    if v is not None:
        return v
    _essai_ts = time.monotonic()
    return _local(text)


# ---- le serveur du sens (dans le processus du rappel automatique) ----

class priorite:
    """Pendant un rappel demandé par le cockpit (le tour de papa), les demandes des autres processus attendent (au plus
    2 s) : elles ne lui disputent pas le processeur."""
    def __enter__(self):
        _priorite.clear()
        return self

    def __exit__(self, *_):
        _priorite.set()
        return False


def _servir_client(conn):
    try:
        with conn, conn.makefile("rb") as f:
            for ligne in f:
                try:
                    texte = json.loads(ligne).get("texte")
                    if not isinstance(texte, str):
                        raise TypeError("texte attendu")
                    _priorite.wait(2.0)
                    r = {"vecteur": _local(texte)}
                except Exception as e:
                    r = {"erreur": f"{type(e).__name__}: {e}"[:200]}
                conn.sendall((json.dumps(r) + "\n").encode("utf-8"))
    except OSError:
        pass


def _accepter(srv):
    while True:
        try:
            conn, _ = srv.accept()
        except OSError:
            return                               # socket fermée : fin du serveur
        threading.Thread(target=_servir_client, args=(conn,), daemon=True).start()


def _vivant(chemin):
    """Un autre serveur écoute-t-il déjà à cette socket ?"""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.settimeout(DELAI_CONNEXION_S)
    try:
        s.connect(chemin)
        return True
    except OSError:
        return False
    finally:
        s.close()


def servir(chemin=None, prechauffer=True, veille_s=5.0):
    """Ouvre la socket du sens et la sert dans des fils à part ; ce processus garde seul le modèle (jamais de socket pour
    lui-même). La socket est ouverte AVANT le chargement : un client qui arrive pendant ces ~13 s attend le vecteur au lieu
    de charger sa propre copie. Si un autre serveur y répond déjà (un cockpit d'essai sur le port 4399 à côté du vrai,
    ou le précédent qui finit de s'en aller), on ne la lui prend pas : on veille et on la reprend quand il n'y répond plus.
    Rend une fonction qui ferme et nettoie (appelée aussi à la sortie) ; fermer.sert() dit si ce processus sert."""
    global LOCAL_SEUL
    import atexit
    LOCAL_SEUL = True
    chemin = str(chemin or SOCK)
    etat = {"srv": None, "inode": None, "fini": False}
    verrou = threading.Lock()

    def prendre():
        with verrou:
            if etat["fini"] or etat["srv"] is not None:
                return
            try:
                os.unlink(chemin)                # celle d'un serveur mort sans nettoyer
            except FileNotFoundError:
                pass
            srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
            srv.bind(chemin)
            os.chmod(chemin, 0o600)
            etat["inode"] = os.stat(chemin).st_ino
            srv.listen(32)
            etat["srv"] = srv
        threading.Thread(target=_accepter, args=(srv,), daemon=True, name="sens-accepter").start()

    def veiller():
        while not etat["fini"] and etat["srv"] is None:
            time.sleep(veille_s)
            if not etat["fini"] and not _vivant(chemin):
                try:
                    prendre()
                except OSError:
                    pass

    if os.path.exists(chemin) and _vivant(chemin):
        threading.Thread(target=veiller, daemon=True, name="sens-veille").start()
    else:
        prendre()
    if prechauffer:
        threading.Thread(target=_get, daemon=True, name="sens-prechauffe").start()

    def fermer():
        with verrou:
            etat["fini"] = True
            srv = etat["srv"]
        if srv is None:
            return
        for geste in (lambda: srv.shutdown(socket.SHUT_RDWR), srv.close):
            try:
                geste()
            except OSError:
                pass
        try:                                     # seulement la nôtre : un serveur plus récent a pu la reprendre
            if os.stat(chemin).st_ino == etat["inode"]:
                os.unlink(chemin)
        except OSError:
            pass
    fermer.sert = lambda: etat["srv"] is not None and not etat["fini"]
    atexit.register(fermer)
    return fermer
