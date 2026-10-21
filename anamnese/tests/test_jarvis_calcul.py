"""Le terminal de calcul de Jarvis (jarvis/calcul.py, demande d'Ahmed du 2026-10-16) : le calcul
marche, et le bac à sable tient (réseau, dossier personnel, écriture, autre programme, durée).
Les tests sautent si sandbox-exec ne peut pas tourner ici (bac à sable imbriqué) ou si le venv de
Jarvis manque."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import calcul  # noqa: E402


@pytest.fixture
def run(tmp_path):
    if not calcul.VENV_PYTHON.exists():
        pytest.skip("venv de Jarvis absent")
    sonde = calcul.executer("print('sonde')", delai_s=10, dossier=tmp_path)
    if "sonde" not in sonde:
        pytest.skip(f"sandbox-exec indisponible ici : {sonde[:120]}")
    return lambda code, **kw: calcul.executer(code, dossier=tmp_path, **kw)


def test_calcule_avec_sympy_et_numpy(run):
    r = run("import numpy as np, sympy as sp\nx = sp.symbols('x')\nprint(sp.integrate(sp.sin(x)**2, (x, 0, sp.pi)))\n"
            "print(round(float(np.linalg.det(np.array([[2, 1], [1, 3]]))), 6))")
    assert "pi/2" in r and "5.0" in r


def test_ni_reseau_ni_maison_ni_ecriture_ni_shell(run, tmp_path):
    maison = Path.home()
    assert "Error" in run("import urllib.request\nurllib.request.urlopen('https://example.com', timeout=5)")
    assert "PermissionError" in run(f"open({str(maison / '.zshrc')!r}).read()") or \
        "FileNotFoundError" in run(f"open({str(maison / '.zshrc')!r}).read()")
    assert "PermissionError" in run(f"import os\nos.listdir({str(maison / 'Desktop')!r})")
    cible = maison / "Desktop" / "jarvis-calcul-essai.txt"
    run(f"open({str(cible)!r}, 'w').write('x')")
    assert not cible.exists()
    assert "Error" in run("import subprocess\nsubprocess.run(['/bin/ls'])")


def test_duree_limitee_et_fichiers_rendus(run):
    r = run("while True: pass", delai_s=2)
    assert "code de retour : -24" in r or "délai dépassé" in r
    r = run("open('res.csv', 'w').write('a,b')\nprint('ok')")
    assert "res.csv" in r and "lisibles avec Read" in r


def test_le_reste_du_disque_et_le_fork_sont_fermes(run):
    """Relecture Opus (2026-10-16) : « tout permis sauf la maison » laissait lire /private/tmp et /Library."""
    assert "PermissionError" in run("import os\nos.listdir('/private/tmp')")
    assert "PermissionError" in run("open('/Library/Preferences/.GlobalPreferences.plist', 'rb').read()") or \
        "FileNotFoundError" in run("open('/Library/Preferences/.GlobalPreferences.plist', 'rb').read()")
    r = run("import os\npid = os.fork()\nprint('fils' if pid == 0 else 'parent')")
    assert "fils" not in r


def test_memoire_plafonnee(run, monkeypatch):
    monkeypatch.setattr(calcul, "MEMOIRE_MAX_KO", 300 * 1024)               # 300 Mo pour l'essai
    r = run("import numpy as np\na = np.ones((80_000_000,))\nimport time\ntime.sleep(5)\nprint('fini')", delai_s=20)
    assert "arrêté (mémoire)" in r and "fini" not in r
