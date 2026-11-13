"""(13/11) Le bac à sable sous Linux et WSL2 (bubblewrap) : l'équivalent Linux de test_les_services_du_mac_sont_refuses et des
garde-fous propres à Linux. Les tests communs (projets, clés, écriture dehors, DNS, terminaux, adresses locales, délai, groupe
tué, téléphone, juge de nuit, fiche de la famille, calcul sans fork…) sont ceux de test_jarvis_terminal.py, test_jarvis_calcul.py,
test_jarvis_chantiers.py et test_jarvis_taches.py, rejoués tels quels sous Linux. Sur le Mac : sautés."""
import os
import socket
import sys
import threading
from pathlib import Path

import pytest

RACINE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RACINE / "jarvis"))

pytestmark = pytest.mark.skipif(sys.platform != "linux", reason="bubblewrap : Linux et WSL2 seulement")


@pytest.fixture
def run(tmp_path):
    if not (RACINE / "jarvis" / ".venv" / "bin" / "python").exists():
        pytest.skip("venv de Jarvis absent")
    import terminal
    sonde = terminal.executer("echo sonde", delai_s=10, atelier=tmp_path / "atelier")
    if "sonde" not in sonde.split("Sortie :")[-1]:
        pytest.skip(f"bubblewrap indisponible ici : {sonde[:200]}")
    return lambda cmd, **kw: terminal.executer(cmd, atelier=tmp_path / "atelier", **kw)


def sortie(r):
    return r.split("Sortie :")[-1]


def test_les_services_du_systeme_sont_hors_d_atteinte(run):
    """systemd, D-Bus, sudo, crontab, l'interopérabilité de WSL (powershell.exe, cmd.exe), les disques de Windows : rien."""
    r = sortie(run("systemctl --user status 2>&1 | head -2; echo rc1=$?; "
                   "sudo -n true 2>&1; echo rc2=$?; "
                   "(crontab -l 2>&1 || echo pas-de-crontab); "
                   "ls /run/user /run/WSL /run/dbus /mnt/c 2>&1; "
                   "env | grep -E '^(DBUS_|WSL_INTEROP|DISPLAY|WAYLAND)' || echo env-propre; "
                   "command -v powershell.exe cmd.exe wsl.exe || echo pas-de-windows"))
    assert "env-propre" in r and "pas-de-windows" in r
    assert "rc2=0" not in r                                   # sudo n'aboutit jamais (no_new_privs, aucun privilège)
    for d in ("/run/user", "/run/WSL", "/run/dbus", "/mnt/c"):
        assert f"cannot access '{d}'" in r or "No such file" in r, r


def test_il_ne_voit_que_ses_propres_processus(run):
    r = sortie(run("ps -e -o pid=,comm= | wc -l; cat /proc/1/cmdline | tr '\\0' ' '"))
    import re
    n = int(re.search(r"^\s*(\d+)\s*$", r, re.M).group(1))           # la sortie est dans son enveloppe
    assert n < 10, r                                           # ses processus seulement (la machine en a des centaines)
    assert "systemd" not in r and "/init" not in r


def test_pas_de_sortie_directe_ni_de_socket_abstraite_de_l_hote(run):
    """Sans la passerelle : aucune adresse ne répond (réseau à part). Une socket abstraite de l'hôte (D-Bus, X11, WSLg en ont)
    ne se joint pas non plus : elles vivent dans le réseau de l'hôte."""
    nom = f"\0naissance-essai-{os.getpid()}"
    s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    s.bind(nom)
    s.listen(1)
    vu = []
    threading.Thread(target=lambda: vu.append(s.accept()), daemon=True).start()
    try:
        r = sortie(run("curl -sS -m 5 --noproxy '*' http://1.1.1.1/ 2>&1; echo rc=$?; "
                       f"python3 -c \"import socket; c=socket.socket(socket.AF_UNIX); c.connect('\\0{nom[1:]}'); print('JOINT')\" 2>&1 | tail -1"))
        assert "rc=0" not in r and "JOINT" not in r and not vu, r
    finally:
        s.close()


def test_la_passerelle_passe_par_le_pont(run):
    """La seule sortie : 127.0.0.1:<port> du bac à sable mène à la passerelle gardée (elle refuse les adresses locales)."""
    r = run("curl -sS -m 5 http://127.0.0.1:4317/")
    assert "Bloqué par la garde" in r


def test_ses_cles_et_sa_configuration_restent_dehors(run):
    """~/.config (les clés : plateforme/cles.py, la clé d'API, Claude Code) n'existe pas dans le bac à sable."""
    for d in (Path.home() / ".config", Path.home() / ".claude", Path.home() / ".ssh"):
        assert "No such file" in run(f"ls '{d}'"), d


def test_une_cle_github_est_recouverte_et_ne_s_ecrit_pas(run, tmp_path, monkeypatch):
    import terminal
    fichiers = tmp_path / "fichiers"
    (fichiers / "telephone").mkdir(parents=True)
    (fichiers / "telephone" / "GitHubKey.txt").write_text("ghp_SECRET")
    (fichiers / "telephone" / "signature.keystore").write_text("KEYSTORE")
    monkeypatch.setattr(terminal, "FICHIERS", fichiers)
    monkeypatch.setattr(terminal, "TELEPHONE", fichiers / "telephone")
    r = run(f"cat '{fichiers}/telephone/GitHubKey.txt' '{fichiers}/telephone/signature.keystore'; "
            f"echo pirate > '{fichiers}/telephone/GitHubKey.txt'; echo note > '{fichiers}/telephone/note.txt'")
    assert "ghp_SECRET" not in r and "KEYSTORE" not in r
    assert (fichiers / "telephone" / "GitHubKey.txt").read_text() == "ghp_SECRET"     # ni lue ni écrite
    assert (fichiers / "telephone" / "note.txt").read_text().strip() == "note"         # le reste du téléphone s'écrit


def test_le_calcul_garde_ses_fils_d_execution():
    import calcul
    if not calcul.VENV_PYTHON.exists():
        pytest.skip("venv de Jarvis absent")
    sonde = calcul.executer("print('sonde')", delai_s=20)
    if "system call filtering" in sonde:
        pytest.skip("seccomp indisponible ici (un conteneur émulé : Rosetta) ; le calcul reste fermé")
    r = calcul.executer("import threading\nt = threading.Thread(target=lambda: print('fil'))\nt.start(); t.join()\n"
                        "import os\ntry:\n    os.fork(); print('FORK')\nexcept OSError as e:\n    print('fork refusé', e.errno)", delai_s=20)
    assert "fil" in r and "fork refusé 1" in r and "FORK" not in r


def test_les_tests_d_un_chantier_ne_lisent_que_le_code_d_origine(tmp_path):
    import chantiers
    (tmp_path / "jarvis").mkdir()
    (tmp_path / "data").mkdir()
    for f in ("a.py", "notes.md", ".env", "jarvis/b.py", "data/memory.db", "image.png"):
        (tmp_path / f).write_text("x")
    noms = {str(p.relative_to(tmp_path)) for p in chantiers._code_d_origine(tmp_path)}
    assert noms == {"a.py", "notes.md", "jarvis/b.py"}
