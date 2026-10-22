"""Le terminal de Jarvis (jarvis/terminal.py, 2026-10-16) : un vrai shell dans son atelier ; la garde
tient (projets, clés, dossiers temporaires, écriture hors de l'atelier, adresses locales). Les tests
sautent si sandbox-exec ne peut pas tourner ici (bac à sable imbriqué) ou si le venv de Jarvis manque."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


@pytest.fixture
def run(tmp_path):
    if not (Path(__file__).resolve().parents[1] / "jarvis" / ".venv" / "bin" / "python").exists():
        pytest.skip("venv de Jarvis absent")
    import terminal
    sonde = terminal.executer("echo sonde", delai_s=10, atelier=tmp_path / "atelier")
    if "sonde" not in sonde.split("Sortie :")[-1]:
        pytest.skip(f"sandbox-exec indisponible ici : {sonde[:120]}")
    return lambda cmd, **kw: terminal.executer(cmd, atelier=tmp_path / "atelier", **kw)


def test_un_vrai_shell_qui_ecrit_dans_son_atelier(run):
    r = run("echo '6*7' | bc && echo bonjour > note.txt && cat note.txt")
    assert "42" in r and "bonjour" in r


def test_ni_projets_ni_cles_ni_ecriture_dehors(run):
    maison = Path.home()
    assert "not permitted" in run(f"cat {maison / 'Desktop' / 'anamnese' / 'config.py'}")
    assert "not permitted" in run(f"ls {maison / '.ssh'}") or "No such file" in run(f"ls {maison / '.ssh'}")
    assert "not permitted" in run("ls /private/tmp")
    cible = maison / "Desktop" / "jarvis-terminal-essai.txt"
    run(f"echo x > {cible}")
    assert not cible.exists()


def test_pas_de_lien_dur_vers_un_fichier_du_dehors(run, tmp_path):
    """(audit du cockpit, C-M4, 2026-10-20) Un lien dur dans l'atelier vers un fichier du dehors serait lu par le Read
    de Hakim comme un fichier de l'atelier : sa création est refusée par le bac à sable. (Les liens symboliques, eux,
    sont refusés au Read par Claude Code --restricted : sondé le même jour.)"""
    dehors = tmp_path / "dehors.txt"
    dehors.write_text("SECRET")
    r = run(f"ln {dehors} dur.txt; cat dur.txt")
    assert "SECRET" not in r and not (tmp_path / "atelier" / "dur.txt").exists()


def test_pas_de_resolution_dns_locale(run):
    """(relecture Opus du 2026-10-20) un nom de domaine inventé ne sort pas par une requête DNS : la résolution locale
    est refusée (les commandes passent par la passerelle, qui résout elle-même)."""
    r = run("python3 -c \"import socket; socket.gethostbyname('donnees-secretes.example.com')\" 2>&1 | tail -1")
    assert "gaierror" in r or "not known" in r


def test_les_terminaux_d_ahmed_sont_hors_d_atteinte(run):
    """(relecture Opus du 2026-10-20) /dev/ttys* (les terminaux ouverts d'Ahmed) : ni lus (frappes), ni écrits
    (séquences injectées) ; /dev/null et /dev/urandom restent utilisables."""
    import glob
    ttys = sorted(glob.glob("/dev/ttys0*"))
    if ttys:
        r = run(f"head -c 1 {ttys[0]} ; echo x > {ttys[0]}")
        assert r.count("not permitted") >= 2, r
    assert "ok" in run("head -c 4 /dev/urandom > /dev/null && echo ok")


def test_les_services_du_mac_sont_refuses(run, tmp_path):
    """(relecture JARVIS 2, C1, 2026-10-20) : ouvrir une app, soumettre une tâche à launchd, écrire des réglages,
    piloter le Mac : refusé, y compris par les API (CFPreferences) sans passer par les programmes."""
    for cmd in ("open -a TextEdit", "launchctl submit -l essai.hakim -- /usr/bin/true", "defaults write essai.hakim a -string b",
                "osascript -e 'beep'", "echo x | pbcopy", "security find-generic-password -s x"):
        assert "not permitted" in run(cmd), cmd
    (tmp_path / "atelier").mkdir(exist_ok=True)
    (tmp_path / "atelier" / "cf.py").write_text(
        "import ctypes, ctypes.util as u\n"
        "cf = ctypes.cdll.LoadLibrary(u.find_library('CoreFoundation'))\n"
        "cf.CFStringCreateWithCString.restype = ctypes.c_void_p\n"
        "s = lambda x: ctypes.c_void_p(cf.CFStringCreateWithCString(None, x, 0x08000100))\n"
        "cf.CFPreferencesSetAppValue(s(b'a'), s(b'b'), s(b'essai.hakim.cf'))\n"
        "cf.CFPreferencesAppSynchronize.restype = ctypes.c_bool\n"
        "print('synchro', cf.CFPreferencesAppSynchronize(s(b'essai.hakim.cf')))\n")
    assert "synchro False" in run("python3 cf.py")


def test_jamais_une_adresse_locale(run):
    r = run("curl -sS -m 5 http://127.0.0.1:4317/ ; curl -sS -m 5 http://localhost:11434/")
    assert "Bloqué par la garde" in r


def test_delai_et_groupe_tue(run):
    r = run("sleep 30 & sleep 30; echo fin", delai_s=2)
    assert "délai de 2 s dépassé" in r and "fin" not in r.split("Sortie :")[-1]


def test_heredoc(run):
    """Jarvis l'a vu en réel : « le heredoc a échoué » (zsh écrivait dans /tmp)."""
    r = run("cat <<'FIN' > s.py\nprint(2 + 2)\nFIN\npython s.py")
    assert "4" in r.split("Sortie :")[-1]


def test_la_commande_meurt_avec_son_serveur(tmp_path, run):
    """Relecture Opus (2026-10-16) : Stop tue le serveur MCP ; la commande, dans sa propre session,
    lui survivait sans plus aucune garde. Le serveur, en mourant (SIGTERM), doit tuer ses commandes."""
    import os
    import signal
    import subprocess
    import time
    jarvis = Path(__file__).resolve().parents[1] / "jarvis"
    script = (f"import sys, threading, time\nsys.path.insert(0, {str(jarvis)!r})\nimport terminal, groupes\n"
              "groupes.installer_arret()\n"
              f"threading.Thread(target=terminal.executer, args=('sleep 300',), kwargs={{'delai_s': 600, 'atelier': {str(tmp_path / 'atelier')!r}}}, daemon=True).start()\n"
              "for _ in range(200):\n    if groupes.en_cours(): break\n    time.sleep(0.05)\n"
              "print(next(iter(groupes.en_cours())), flush=True)\ntime.sleep(600)\n")
    serveur = subprocess.Popen([sys.executable, "-c", script], stdout=subprocess.PIPE, text=True)
    try:
        pid = int(serveur.stdout.readline())
        os.killpg(pid, 0)                                   # la commande tourne
        serveur.send_signal(signal.SIGTERM)
        serveur.wait(10)
        for _ in range(50):
            try:
                os.killpg(pid, 0)
            except ProcessLookupError:
                break
            time.sleep(0.1)
        else:
            os.killpg(pid, signal.SIGKILL)
            raise AssertionError("la commande a survécu à son serveur")
    finally:
        serveur.kill()


def test_rien_ne_reste_en_arriere_plan(run, tmp_path):
    """Un « & » sans sortie ne survit pas à la fin de la commande (il n'aurait plus de surveillance)."""
    import os
    import time
    r = run("(sleep 300 > /dev/null 2>&1 &) ; echo $$ ; sleep 0.2")
    time.sleep(0.5)
    vivants = os.popen("pgrep -f 'sleep 300' || true").read().split()
    assert not vivants, f"sleep orphelin : {vivants} — {r[-200:]}"


def test_le_telephone_s_ecrit_mais_pas_le_reste_des_fichiers(run, tmp_path, monkeypatch):
    """(Ahmed, 2026-10-22 : « lecture ET écriture » sur les fichiers de son téléphone, synchronisés par Syncthing) ;
    le reste de ../fichiers reste en lecture seule."""
    import terminal
    fichiers = tmp_path / "fichiers"
    tel = fichiers / "telephone" / "Z Fold 7"
    tel.mkdir(parents=True)
    (fichiers / "autre.txt").write_text("x")
    monkeypatch.setattr(terminal, "FICHIERS", fichiers)
    monkeypatch.setattr(terminal, "TELEPHONE", fichiers / "telephone")
    r = run(f"echo note > '{tel}/note.txt' && cat '{tel}/note.txt'; echo y > '{fichiers}/autre.txt'; cat '{fichiers}/autre.txt'")
    assert (tel / "note.txt").read_text().strip() == "note" and "note" in r
    assert (fichiers / "autre.txt").read_text() == "x" and "not permitted" in r
