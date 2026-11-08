"""L'alerte de l'atelier à 80 % (demande de Hakim, 2026-10-20) ; atelier porté de 5 à 10 Go (Ahmed, 2026-10-21)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import terminal  # noqa: E402


def test_alerte_atelier():
    assert terminal.alerte_atelier(taille_ko=7 * 1024 * 1024) == ""
    a = terminal.alerte_atelier(taille_ko=int(8.3 * 1024 * 1024))
    assert "8,3 Go sur 10,0" in a and "arrêtée net" in a


def test_le_piege_de_la_maison():
    """(30/10, bug relevé par Hakim : « Iris ne voyait pas les mêmes fichiers que moi dans atelier/crypto_minute ») dans son
    terminal, ~ EST l'atelier : « ~/AIOS/jarvis/cwd/atelier/x » écrivait dans une copie imbriquée (atelier/AIOS/…). Refusé
    avant de tourner, avec le bon chemin."""
    for c in ("cd ~/AIOS/jarvis/cwd/atelier/crypto_minute && ls", "python $HOME/AIOS/jarvis/cwd/atelier/x.py",
              "cat ${HOME}/AIOS/x", "ls ~/AIOS"):
        r = terminal.piege_maison(c)
        assert r and "/Users/admin/AIOS/jarvis/cwd/atelier" in r and "imbriquée" in r, c
    for c in ("ls /Users/admin/AIOS/jarvis/cwd/atelier", "cd crypto_minute && ls", "ls ~/.cache", "echo '~/AIOSX'"):
        assert terminal.piege_maison(c) is None, c
