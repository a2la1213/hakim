"""(30/10, 14:53, Ahmed via Hakim : « qu'il puisse étiqueter les LIEUX de ma position : ici c'est chez nous, le parc, Genève » ;
Hakim : « que les coordonnées restent dans le cockpit, sur le Mac, et ne passent jamais dans ma mémoire, mes lettres ou mes
fichiers ; moi, je ne manipule que les NOMS ») ses outils ne voient et ne disent que des noms."""
import json
import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import lieux  # noqa: E402


def test_nommer_passe_par_le_cockpit_qui_seul_connait_la_position(tmp_path, monkeypatch):
    monkeypatch.setattr(lieux, "JARVIS", tmp_path)

    def cockpit():
        for _ in range(100):
            try:
                d = json.loads((tmp_path / "lieux-demandes.jsonl").read_text().splitlines()[-1])
            except (OSError, IndexError):
                time.sleep(0.02)
                continue
            (tmp_path / "lieux-reponses.jsonl").write_text(json.dumps({"id": d["id"], "texte": f"C'est noté : ici, c'est « {d['nom']} » ({d['rayon_m']} m autour)."}) + "\n")
            return
    threading.Thread(target=cockpit, daemon=True).start()
    r = lieux.nommer("chez nous", 150, attente_s=3)
    assert "« chez nous »" in r and "150 m" in r
    assert lieux.nommer("x" * 50).startswith("Refusé")
    assert "ne répond pas" in lieux.nommer("le parc", 200, attente_s=0.2)


def test_lister_ne_dit_que_les_noms(tmp_path, monkeypatch):
    monkeypatch.setattr(lieux, "JARVIS", tmp_path)
    (tmp_path / "lieux.json").write_text(json.dumps({"lieux": [{"nom": "chez nous", "lat": 46.2044, "lon": 6.1432, "rayon_m": 150, "ts": 1_793_380_000},
                                                              {"nom": "le parc", "lat": 46.21, "lon": 6.15, "rayon_m": 200, "ts": 1_793_381_000}]}))
    (tmp_path / "lieu-actuel.json").write_text(json.dumps({"nom": "chez nous", "depuis_ms": 1_793_380_000_000}))
    t = lieux.lister()
    assert "chez nous" in t and "le parc" in t and "tu y es" in t
    assert "46" not in t and "6.1" not in t and "6,1" not in t, "jamais une coordonnée"


def test_rien_ne_s_efface_la_trace_de_chaque_lieu(tmp_path, monkeypatch):
    """(30/10, 15:05, Ahmed : « renommer, modifier quand on déménage, effacer, MAIS en gardant toujours une trace »)"""
    monkeypatch.setattr(lieux, "JARVIS", tmp_path)
    (tmp_path / "lieux.json").write_text(json.dumps({"lieux": [
        {"nom": "la maison de la famille", "lat": 46.2, "lon": 6.1, "rayon_m": 150, "ts": 1_793_380_000,
         "historique": [{"quoi": "nommé", "ts": 1_793_380_000}]},
        {"nom": "la maison de la famille", "lat": 46.0, "lon": 6.0, "rayon_m": 150, "ts": 1_700_000_000, "archive": True,
         "historique": [{"quoi": "nommé", "ts": 1_700_000_000}, {"quoi": "archivé", "ts": 1_793_380_000}]}]}))
    t = lieux.lister()
    assert "Leur mémoire (archivés, jamais effacés)" in t and "archivé (quitté)" in t and "46" not in t
    assert lieux.renommer("x", "!").startswith("Refusé")
