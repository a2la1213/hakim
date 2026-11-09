"""(09/11, mesuré : l'oreille vive tenait 7,1 Go de tampons Metal pour un Whisper small) son cache MLX est vidé seulement quand
aucune demande n'attend (jamais entre deux morceaux de papa collés)."""
import os
import sys
import types
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))


def test_vider_cache_seulement_si_libre(monkeypatch):
    vides = []
    core = types.SimpleNamespace(clear_cache=lambda: vides.append(1), set_cache_limit=lambda n: None)
    mlx = types.ModuleType("mlx"); mlx.core = core
    monkeypatch.setitem(sys.modules, "mlx", mlx)
    monkeypatch.setitem(sys.modules, "mlx.core", core)
    import stt_vif
    r, w = os.pipe()
    with os.fdopen(r) as entree, os.fdopen(w, "w") as sortie:
        assert stt_vif.vider_cache_si_libre(entree) is True and vides == [1]
        sortie.write('{"id": 1}\n'); sortie.flush()
        assert stt_vif.vider_cache_si_libre(entree) is False and vides == [1]
    assert stt_vif.CACHE_MAX_OCTETS == 256 * 1024 * 1024
