"""Les tâches de fond de Hakim (jarvis/taches.py, lot C de la liste du 2026-10-19, point 12) : un long
calcul ne bloque plus la conversation (vu en réel : « gros calcul qui a bloqué la conversation et planté,
Connection closed vers 16:34 »). La tâche est lancée, Hakim reçoit un numéro tout de suite, et un
SUPERVISEUR à part (qui survit au cerveau et à son serveur MCP) garde la durée, la mémoire et la taille,
écrit le journal et l'état. Les tests sautent si sandbox-exec ne peut pas tourner ici."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


@pytest.fixture
def t(tmp_path):
    if not (Path(__file__).resolve().parents[1] / "jarvis" / ".venv" / "bin" / "python").exists():
        pytest.skip("venv de Jarvis absent")
    import terminal
    sonde = terminal.executer("echo sonde", delai_s=10, atelier=tmp_path / "atelier")
    if "sonde" not in sonde.split("Sortie :")[-1]:
        pytest.skip(f"sandbox-exec indisponible ici : {sonde[:120]}")
    import taches
    return lambda: None, taches, tmp_path / "atelier", tmp_path / "taches"


def attendre(taches, dossier, tid, etat, s=20):
    for _ in range(int(s * 10)):
        e = taches.etat(tid, dossier=dossier)
        if e and e["etat"] == etat:
            return e
        time.sleep(0.1)
    raise AssertionError(f"{tid} n'atteint pas « {etat} » : {taches.etat(tid, dossier=dossier)}")


def test_la_tache_rend_la_main_tout_de_suite_puis_finit(t):
    _, taches, atelier, dossier = t
    t0 = time.time()
    tid = taches.lancer("sleep 2; echo 'résultat 42'", delai_s=60, atelier=atelier, dossier=dossier)
    assert time.time() - t0 < 2 and tid.startswith("T-")
    assert taches.etat(tid, dossier=dossier)["etat"] == "en cours"
    e = attendre(taches, dossier, tid, "finie")
    assert e["code"] == 0 and "résultat 42" in taches.journal(tid, dossier=dossier)


def test_arreter_une_tache(t):
    _, taches, atelier, dossier = t
    tid = taches.lancer("sleep 120", delai_s=600, atelier=atelier, dossier=dossier)
    attendre(taches, dossier, tid, "en cours")
    time.sleep(0.5)
    taches.arreter(tid, dossier=dossier)
    e = attendre(taches, dossier, tid, "arrêtée")
    assert "Ahmed ou Hakim" in e["raison"]


def test_la_garde_du_delai_tient(t):
    _, taches, atelier, dossier = t
    tid = taches.lancer("sleep 60", delai_s=2, atelier=atelier, dossier=dossier)
    e = attendre(taches, dossier, tid, "arrêtée", s=30)
    assert "délai" in e["raison"]


def test_la_tache_survit_a_celui_qui_l_a_lancee(t, tmp_path):
    """Le serveur MCP meurt (Stop, cerveau au repos) : la tâche de fond, elle, continue et finit."""
    _, taches, atelier, dossier = t
    jarvis = Path(__file__).resolve().parents[1] / "jarvis"
    code = (f"import sys; sys.path.insert(0, {str(jarvis)!r}); import taches; "
            f"print(taches.lancer('sleep 2; echo survivante', delai_s=60, atelier={str(atelier)!r}, dossier={str(dossier)!r}))")
    tid = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, timeout=30).stdout.strip()
    e = attendre(taches, dossier, tid, "finie")
    assert e["code"] == 0 and "survivante" in taches.journal(tid, dossier=dossier)


def test_au_plus_trois_taches_a_la_fois(t):
    _, taches, atelier, dossier = t
    ids = [taches.lancer("sleep 30", delai_s=60, atelier=atelier, dossier=dossier) for _ in range(3)]
    with pytest.raises(taches.Refus):
        taches.lancer("echo de trop", delai_s=60, atelier=atelier, dossier=dossier)
    for tid in ids:
        taches.arreter(tid, dossier=dossier)


def test_la_commande_ne_peut_pas_toucher_l_etat_des_taches(t):
    """L'état (dont le numéro de processus que « arrêter » tue) vit HORS de l'atelier : une commande ne peut
    ni le réécrire ni faire tuer autre chose."""
    _, taches, atelier, dossier = t
    tid = taches.lancer("sleep 1", delai_s=60, atelier=atelier, dossier=dossier)
    attendre(taches, dossier, tid, "finie")
    cible = dossier / f"{tid}.json"
    avant = cible.read_text()
    tid2 = taches.lancer(f"echo '{{\"pid\": 1}}' > {cible}; echo fait", delai_s=60, atelier=atelier, dossier=dossier)
    attendre(taches, dossier, tid2, "finie")
    assert cible.read_text() == avant
    assert "not permitted" in taches.journal(tid2, dossier=dossier)


def test_un_journal_qui_deborde_arrete_la_tache(t, monkeypatch):
    """Relecture Opus du lot C : le journal vit hors de l'atelier ; sans plafond, `yes` remplissait le disque."""
    _, taches, atelier, dossier = t
    tid = taches.lancer("python3 -c \"import sys\nwhile True: sys.stdout.write('x' * 65536)\"", delai_s=120,
                        atelier=atelier, dossier=dossier)
    # plafond abaissé pour le test : le superviseur relit la constante depuis son module (processus à part)
    e = attendre(taches, dossier, tid, "arrêtée", s=90)
    assert "journal trop gros" in e["raison"]
    assert (dossier / f"{tid}.log").stat().st_size < 60 * 1024 * 1024
