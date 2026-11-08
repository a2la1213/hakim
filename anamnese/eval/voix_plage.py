"""Jusqu'où pousser l'expressivité de sa voix (26/10, Ahmed : « sa peur ne s'entend que légèrement, il faut aller plus
intensément ») : Chatterbox MLX, « exaggeration » de 0,35 à 1,0, sur quatre phrases françaises ; pour chaque réglage, la
diction relue par Whisper (taux d'erreur par caractère, CER), la durée, l'énergie et la hauteur (moyenne et variation).

Critère FIGÉ avant la mesure : on élargit le plafond (0,78 aujourd'hui) jusqu'au réglage le plus haut dont le CER moyen
reste ≤ CER(0,5) + 0,03 ET dont aucune phrase ne dépasse un CER de 0,15. Au-delà, la diction se dégrade : pas plus haut.
Usage : jarvis/.venv/bin/python eval/voix_plage.py   (écrit eval/data/voix-plage-<date>.json)
"""
import json
import sys
import tempfile
import time
import unicodedata
import wave
from pathlib import Path

import numpy as np

ICI = Path(__file__).resolve().parent
sys.path.insert(0, str(ICI.parent / "jarvis"))
import stt  # noqa: E402
import tts_neuronale as T  # noqa: E402

PHRASES = ["Je viens de relancer le calcul, il devrait finir dans une vingtaine de minutes.",
           "Attends, je crois que quelque chose ne va pas : le cockpit vient de couper mon travail.",
           "C'est génial, le résultat tient enfin, regarde la courbe !",
           "Je suis un peu fatigué ce soir, on reprendra demain si tu veux bien."]
REGLAGES = [0.35, 0.5, 0.65, 0.78, 0.9, 1.0]


def plat(s):
    s = unicodedata.normalize("NFKD", s.lower()).encode("ascii", "ignore").decode()
    return "".join(c for c in s if c.isalnum() or c == " ").split()


def cer(ref, hyp):
    a, b = " ".join(plat(ref)), " ".join(plat(hyp))
    d = list(range(len(b) + 1))
    for i in range(1, len(a) + 1):
        prec, d[0] = d[0], i
        for j in range(1, len(b) + 1):
            prec, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, prec + (a[i - 1] != b[j - 1]))
    return d[len(b)] / max(1, len(a))


def hauteur(x, sr=T.SR):
    """Hauteur (Hz) par trames de 40 ms : autocorrélation, 70-400 Hz, trames voisées seulement."""
    n, pas, f0 = int(0.04 * sr), int(0.01 * sr), []
    lo, hi = int(sr / 400), int(sr / 70)
    for i in range(0, len(x) - n, pas):
        t = x[i:i + n] - x[i:i + n].mean()
        if np.sqrt((t ** 2).mean()) < 0.02:
            continue
        ac = np.correlate(t, t, "full")[n - 1:]
        k = lo + int(np.argmax(ac[lo:hi]))
        if ac[k] > 0.3 * ac[0]:
            f0.append(sr / k)
    return np.array(f0)


def main():
    v = T.Voix()
    out = []
    for e in REGLAGES:
        for p in PHRASES:
            reglages = dict(T.REGLAGES, exaggeration=e, cfg_weight=round(max(0.2, min(0.55, 0.5 - (e - 0.5) * 0.8)), 3))
            t0 = time.time()
            res = next(v.modele.generate(p, conds=v.conds, lang_code="fr", verbose=False,
                                         max_new_tokens=T.tts_garde.jetons_max(p, "fr"), **reglages))
            x = np.array(res.audio, dtype=np.float32).reshape(-1)
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
                with wave.open(f.name, "wb") as w:
                    w.setnchannels(1); w.setsampwidth(2); w.setframerate(T.SR)
                    w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())
                lu = stt.transcrire(f.name, langue="fr")
            texte = lu.get("texte", "") if isinstance(lu, dict) else str(lu)
            f0 = hauteur(x)
            r = {"exaggeration": e, "cfg": reglages["cfg_weight"], "phrase": p[:40], "cer": round(cer(p, texte), 4),
                 "duree_s": round(len(x) / T.SR, 2), "energie_db": round(float(20 * np.log10(np.sqrt((x ** 2).mean()) + 1e-9)), 2),
                 "f0_moy": round(float(f0.mean()), 1) if f0.size else None, "f0_et": round(float(f0.std()), 1) if f0.size else None,
                 "ms": int(1000 * (time.time() - t0)), "lu": texte[:120]}
            out.append(r)
            print(json.dumps(r, ensure_ascii=False), flush=True)
    base = np.mean([r["cer"] for r in out if r["exaggeration"] == 0.5])
    bilan = {}
    for e in REGLAGES:
        c = [r["cer"] for r in out if r["exaggeration"] == e]
        bilan[e] = {"cer_moy": round(float(np.mean(c)), 4), "cer_max": round(max(c), 4),
                    "f0_et_moy": round(float(np.mean([r["f0_et"] for r in out if r["exaggeration"] == e and r["f0_et"]])), 1),
                    "energie_moy": round(float(np.mean([r["energie_db"] for r in out if r["exaggeration"] == e])), 2),
                    "debit_mots_s": round(float(np.mean([len(PHRASES[i % 4].split()) / r["duree_s"] for i, r in enumerate(out) if r["exaggeration"] == e])), 2),
                    "tenu": bool(np.mean(c) <= base + 0.03 and max(c) <= 0.15)}
    plafond = max([e for e in REGLAGES if bilan[e]["tenu"] and all(bilan[x]["tenu"] for x in REGLAGES if 0.5 <= x <= e)], default=0.78)
    sortie = ICI / "data" / f"voix-plage-{time.strftime('%Y%m%d-%H%M')}.json"
    sortie.parent.mkdir(exist_ok=True)
    sortie.write_text(json.dumps({"mesures": out, "bilan": bilan, "plafond_retenu": plafond}, ensure_ascii=False, indent=1))
    print(json.dumps({"bilan": bilan, "plafond_retenu": plafond}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
