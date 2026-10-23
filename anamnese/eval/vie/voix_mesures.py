"""La voix réellement émise : les derniers morceaux gardés (~/AIOS/jarvis/voix-recente, ecouter_ma_voix) — durée,
énergie (dB), hauteur médiane (autocorrélation, 70–400 Hz). Usage : jarvis/.venv/bin/python eval/vie/voix_mesures.py"""
import json
import wave
from pathlib import Path

import numpy as np

DOSSIER = Path.home() / "AIOS" / "jarvis" / "voix-recente"
SORTIE = Path(__file__).resolve().parents[1] / "data" / "vie" / "voix.json"


def f0(x, sr):
    out = []
    n = int(0.04 * sr)
    for i in range(0, len(x) - n, n):
        f = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((f ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(f, f, "full")[n - 1:]
        lo, hi = int(sr / 400), int(sr / 70)
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.3 * ac[0]:
            out.append(sr / k)
    return float(np.median(out)) if out else None


def main():
    res = []
    for f in sorted(DOSSIER.glob("*.wav")):
        with wave.open(str(f)) as w:
            sr, n, ch, sw = w.getframerate(), w.getnframes(), w.getnchannels(), w.getsampwidth()
            raw = w.readframes(n)
        x = np.frombuffer(raw, dtype={2: np.int16, 4: np.int32}[sw]).astype(np.float64)
        x = x.reshape(-1, ch).mean(axis=1) / float(2 ** (8 * sw - 1))
        rms = float(np.sqrt((x ** 2).mean())) if len(x) else 0.0
        res.append({"ts": int(f.name.split("-")[0]) / 1000, "duree_s": round(n / sr, 2),
                    "energie_db": round(20 * np.log10(max(rms, 1e-9)), 1), "hauteur_hz": f0(x, sr) and round(f0(x, sr), 1)})
    SORTIE.parent.mkdir(parents=True, exist_ok=True)
    SORTIE.write_text(json.dumps(res, ensure_ascii=False))
    print(len(res), "morceaux ;", res[:2])


if __name__ == "__main__":
    main()
