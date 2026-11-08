"""(27/10) La jauge de fatigue lit ses vrais tours et sonde le Mac à chaque battement (interieur.tick) : dans les tests,
elle lit et écrit dans un dossier jetable, et le corps est une mesure fixe (ni sous-processus, ni vrais fichiers)."""
import pytest


@pytest.fixture(autouse=True)
def _jauge_fatigue_isolee(tmp_path, monkeypatch):
    import jauge_fatigue
    monkeypatch.setattr(jauge_fatigue, "JETONS", tmp_path / "jetons-absents.jsonl")
    monkeypatch.setattr(jauge_fatigue, "CORPS", tmp_path / "corps-echantillons.jsonl")
    monkeypatch.setattr(jauge_fatigue, "_sondes", lambda: {"charge": 0.2, "memoire_libre": 60.0, "swap": (5000.0, 2500.0),
                                                           "chaleur": "aucun avertissement"})
