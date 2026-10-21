"""L'alerte de l'atelier vers 4 Go (demande de Hakim, 2026-10-20)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import terminal  # noqa: E402


def test_alerte_atelier():
    assert terminal.alerte_atelier(taille_ko=3 * 1024 * 1024) == ""
    a = terminal.alerte_atelier(taille_ko=int(4.3 * 1024 * 1024))
    assert "4,3 Go sur 5,0" in a and "arrêtée net" in a
