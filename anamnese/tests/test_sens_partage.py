"""(09/11, Ahmed : « alléger le Mac ») Le serveur du sens : un seul processus garde le modèle d'embeddings (1,33 Go), les
autres lui demandent leurs vecteurs par la socket locale ; serveur absent → chargement local, comme avant."""
import inspect
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import numpy as np
import pytest

import embeddings

RACINE = Path(__file__).resolve().parent.parent


class FauxModele:
    """encode([texte]) comme model2vec : un tableau float32 (des valeurs qui ne tombent pas juste en décimal)."""
    def __init__(self):
        self.appels = []

    def encode(self, textes):
        self.appels.append((list(textes), threading.current_thread().name))
        t = textes[0]
        return np.array([[len(t) / 3.0, 0.1, -7.123456789, float(sum(map(ord, t)) % 97) / 7.0]], dtype=np.float32)


def attendu(texte):
    return [float(x) for x in FauxModele().encode([texte])[0]]


@pytest.fixture(autouse=True)
def _client_neuf(monkeypatch):
    """Un processus client qui n'a encore rien chargé (un test d'avant a pu charger le vrai modèle ici)."""
    monkeypatch.setattr(embeddings, "_model", None)
    monkeypatch.setattr(embeddings, "_essai_ts", 0.0)


@pytest.fixture
def court():
    """Un dossier au chemin court : une socket Unix ne dépasse pas 104 octets sur macOS."""
    d = tempfile.mkdtemp(prefix="sens", dir="/tmp")
    yield os.path.join(d, "s.sock")
    shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def serveur(monkeypatch, court):
    """Un serveur du sens dans ce processus, sur un faux modèle ; ce processus redevient ensuite un client."""
    faux = FauxModele()
    monkeypatch.setattr(embeddings, "_get", lambda: faux)
    fermer = embeddings.servir(court, prechauffer=False)
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)
    monkeypatch.setattr(embeddings, "SOCK", court)
    yield faux
    fermer()


def test_un_autre_processus_recoit_le_vecteur_sans_charger_le_modele(serveur, court):
    """Le mécanisme : un processus client (ici, interdit de charger model2vec) obtient son vecteur du serveur."""
    code = ("import sys, json; sys.modules['model2vec'] = None\n"
            "import embeddings\n"
            "v = embeddings.embed('bonjour papa')\n"
            "print(json.dumps({'v': v, 'modele_local': embeddings._model is not None}))\n")
    env = {**os.environ, "ANAMNESE_EMBED_SOCK": court, "PYTHONPATH": str(RACINE)}
    r = subprocess.run([sys.executable, "-B", "-c", code], capture_output=True, text=True, timeout=60, env=env, cwd=str(RACINE))
    assert r.returncode == 0, r.stderr[-2000:]
    o = json.loads(r.stdout.strip().splitlines()[-1])
    assert o == {"v": attendu("bonjour papa"), "modele_local": False}
    assert [a[0] for a in serveur.appels] == [["bonjour papa"]]          # encodé une fois, par le serveur


def test_le_vecteur_transmis_est_exactement_celui_d_un_chargement_local(serveur):
    for t in ("", "é à ç — ﷽ 🤍", "x" * 5000, "le tour de papa", "transcription cassée \udcff"):
        assert embeddings.embed(t) == attendu(t)
    assert embeddings._model is None
    ici = threading.current_thread().name
    assert len(serveur.appels) == 5 and all(qui != ici for _t, qui in serveur.appels)    # tous encodés par le serveur


def test_repli_local_si_aucun_serveur(monkeypatch, court):
    faux = FauxModele()
    charge = []
    monkeypatch.setattr(embeddings, "SOCK", court)                       # rien n'y écoute
    monkeypatch.setattr(embeddings, "_get", lambda: charge.append(1) or faux)
    assert embeddings.embed("salut") == attendu("salut")
    assert charge and faux.appels == [(["salut"], threading.current_thread().name)]


def test_repli_local_si_socket_perimee(monkeypatch, court):
    """Un serveur mort sans nettoyer laisse sa socket : refusée, puis repli local au bout de l'attente."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(court)
    s.close()
    assert os.path.exists(court)
    faux = FauxModele()
    monkeypatch.setattr(embeddings, "SOCK", court)
    monkeypatch.setattr(embeddings, "ATTENTE_REFUS_S", 0.3)
    monkeypatch.setattr(embeddings, "_get", lambda: faux)
    debut = time.monotonic()
    assert embeddings.embed("salut") == attendu("salut")
    assert time.monotonic() - debut < 5


def test_socket_refusee_le_client_attend_le_serveur_relance(monkeypatch, court):
    """Le serveur vient de mourir (socket refusée) et le cockpit le relance : le client l'attend au lieu de charger."""
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(court)
    s.close()
    faux = FauxModele()
    monkeypatch.setattr(embeddings, "_get", lambda: faux)
    monkeypatch.setattr(embeddings, "SOCK", court)
    fermer = []
    threading.Timer(0.6, lambda: fermer.append(embeddings.servir(court, prechauffer=False))).start()
    try:
        assert embeddings.embed("revenu") == attendu("revenu")
        assert faux.appels and faux.appels[0][1] != threading.current_thread().name   # encodé par le serveur
    finally:
        time.sleep(0.1)
        for f in fermer:
            f()
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)


def test_la_copie_locale_est_rendue_quand_le_serveur_revient(serveur, monkeypatch):
    monkeypatch.setattr(embeddings, "_model", object())                  # chargé ici pendant une absence du serveur
    monkeypatch.setattr(embeddings, "_essai_ts", time.monotonic())
    embeddings.embed("a")
    assert embeddings._model is not None                                 # pas avant une minute : on ne frappe pas à chaque appel
    monkeypatch.setattr(embeddings, "_essai_ts", time.monotonic() - embeddings.REESSAI_S - 1)
    assert embeddings.embed("b") == attendu("b")
    assert embeddings._model is None


def test_connexion_rompue_puis_serveur_relance(monkeypatch, court):
    """Le cockpit relance le serveur : la connexion gardée est morte, le client se reconnecte au nouveau."""
    faux = FauxModele()
    monkeypatch.setattr(embeddings, "_get", lambda: faux)
    fermer = embeddings.servir(court, prechauffer=False)
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)
    monkeypatch.setattr(embeddings, "SOCK", court)
    try:
        assert embeddings.embed("un") == attendu("un")
        fermer()
        embeddings._client[1].shutdown(socket.SHUT_RDWR)                  # le serveur parti, sa connexion est close
        fermer = embeddings.servir(court, prechauffer=False)
        monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)
        assert embeddings.embed("deux") == attendu("deux")
        assert embeddings._model is None
    finally:
        fermer()


def test_un_second_serveur_ne_prend_pas_la_socket_d_un_vivant_puis_la_reprend(monkeypatch, court):
    """Un cockpit d'essai (port 4399) à côté du vrai : son serveur de rappel ne vole pas la socket du vrai (sinon, en
    s'arrêtant, il l'emporterait et tous rechargeraient le modèle) ; il la reprend quand le premier n'y répond plus."""
    monkeypatch.setattr(embeddings, "_get", FauxModele)
    fermer1 = embeddings.servir(court, prechauffer=False)
    inode1 = os.stat(court).st_ino
    fermer2 = embeddings.servir(court, prechauffer=False, veille_s=0.1)
    try:
        time.sleep(0.4)
        assert fermer1.sert() and not fermer2.sert() and os.stat(court).st_ino == inode1
        fermer1()
        fin = time.monotonic() + 5
        while not fermer2.sert() and time.monotonic() < fin:
            time.sleep(0.05)
        assert fermer2.sert() and os.path.exists(court)
        monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)
        monkeypatch.setattr(embeddings, "SOCK", court)
        assert embeddings.distant("encore") == attendu("encore")
    finally:
        fermer2()
    assert not os.path.exists(court)


def test_une_socket_perimee_est_reprise_tout_de_suite(monkeypatch, court):
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(court)
    s.close()
    monkeypatch.setattr(embeddings, "_get", FauxModele)
    fermer = embeddings.servir(court, prechauffer=False)
    try:
        assert fermer.sert()
    finally:
        fermer()
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)


def test_le_serveur_qui_s_en_va_ne_retire_que_sa_socket(monkeypatch, court):
    monkeypatch.setattr(embeddings, "_get", FauxModele)
    fermer = embeddings.servir(court, prechauffer=False)
    os.unlink(court)                                                      # un autre l'a reprise entre-temps
    autre = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    autre.bind(court)
    try:
        fermer()
        assert os.path.exists(court)
    finally:
        autre.close()
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", False)


def test_le_rappel_du_cockpit_passe_avant_les_demandes_des_autres(serveur):
    fini = threading.Event()
    with embeddings.priorite():
        threading.Thread(target=lambda: (embeddings.distant("x"), fini.set()), daemon=True).start()
        assert not fini.wait(0.5)                                         # attend la fin du rappel en cours
    assert fini.wait(5)


def test_le_serveur_de_rappel_ouvre_le_serveur_du_sens():
    import cli
    import rappel
    assert "embeddings.servir()" in inspect.getsource(cli)
    assert "embeddings.priorite()" in inspect.getsource(rappel.serveur)


def test_sans_distant_toujours_local(monkeypatch, serveur):
    """ANAMNESE_EMBED_DISTANT=0 : l'ancien comportement, même si un serveur écoute."""
    monkeypatch.setattr(embeddings, "LOCAL_SEUL", True)
    n = len(serveur.appels)
    embeddings.embed("z")
    assert serveur.appels[-1][1] == threading.current_thread().name and len(serveur.appels) == n + 1
