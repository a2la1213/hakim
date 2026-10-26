"""(26/10, Ahmed) le débit de la voix change, sa hauteur non : l'étirement temporel garde la fréquence d'un son."""
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "jarvis"))
import etirement as E  # noqa: E402


def frequence(x, sr):
    s = np.abs(np.fft.rfft(x * np.hanning(len(x))))
    return np.fft.rfftfreq(len(x), 1 / sr)[int(np.argmax(s))]


def test_la_duree_change_la_hauteur_reste():
    sr = 24000
    t = np.arange(int(1.5 * sr)) / sr
    x = (0.5 * np.sin(2 * np.pi * 180 * t)).astype(np.float32)
    for tempo in (0.9, 1.05):
        y = E.etirer(x, tempo, sr)
        assert abs(len(y) - len(x) / tempo) < sr * 0.02
        assert abs(frequence(y[sr // 10: -sr // 10], sr) - 180) < 3, "la hauteur ne bouge pas"
    assert E.etirer(x, 1.0, sr) is not None and len(E.etirer(x, 1.0, sr)) == len(x)
