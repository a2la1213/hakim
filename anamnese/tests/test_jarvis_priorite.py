"""Ce que Hakim lance passe après sa voix (jarvis/priorite.py, 2026-10-23) : le préfixe est bien mis, et le processus
lancé tourne VRAIMENT avec la priorité basse (nice 10), au même pid (la garde tue toujours le bon groupe)."""
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import priorite  # noqa: E402

pytestmark = pytest.mark.skipif(not Path(priorite.TASKPOLICY).exists(), reason="taskpolicy : macOS seulement")


def test_prefixe_devant_la_commande():
    args = priorite.basse(["/usr/bin/sandbox-exec", "-p", "(version 1)", "/bin/zsh", "-c", "true"])
    assert args[:6] == priorite.PREFIXE
    assert args[6:] == ["/usr/bin/sandbox-exec", "-p", "(version 1)", "/bin/zsh", "-c", "true"]


def test_le_processus_tourne_en_priorite_basse_au_meme_pid():
    p = subprocess.run(priorite.basse(["/bin/sh", "-c", "echo $$; /bin/ps -o nice= -p $$"]), capture_output=True, text=True,
                       timeout=20)
    pid, nice = p.stdout.split()
    assert int(nice) == 10
    q = subprocess.Popen(priorite.basse(["/bin/sh", "-c", "echo $$"]), stdout=subprocess.PIPE, text=True)
    assert int(q.communicate(timeout=20)[0]) == q.pid           # nice et taskpolicy remplacent leur processus


def test_le_terminal_de_hakim_part_en_priorite_basse():
    import terminal
    args, _env = terminal.preparer("true", Path("/tmp"), 1)
    assert args[:6] == priorite.PREFIXE and "/usr/bin/sandbox-exec" in args
