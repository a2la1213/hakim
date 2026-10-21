"""L'alerte de l'atelier à 80 % (demande de Hakim, 2026-10-20) ; atelier porté de 5 à 10 Go (Ahmed, 2026-10-21)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import terminal  # noqa: E402


def test_alerte_atelier():
    assert terminal.alerte_atelier(taille_ko=7 * 1024 * 1024) == ""
    a = terminal.alerte_atelier(taille_ko=int(8.3 * 1024 * 1024))
    assert "8,3 Go sur 10,0" in a and "arrêtée net" in a
