"""(06/11, Ahmed : « sa voix de rap, sur le Mac, le téléphone et la montre, en darija, français et anglais mélangés ») les voix
connues de Hakim et ses morceaux de langue, sans charger de modèle (testable sans MLX).

- VOIX : les timbres qu'il peut prendre, par NOM seulement (jamais un chemin venu de dehors) : « rap », la voix de ses chansons
  (ACE-Step, séparée par Demucs, 10 s à 24 kHz), dans ~/AIOS/jarvis/voix-hakim-rap.wav ;
- segments_valides : le texte découpé par le cockpit (voix-hakim.js), un lang_code par morceau ;
- assembler : les morceaux recollés, un souffle court entre deux langues.
"""
import os
from pathlib import Path

import numpy as np

VOIX = {"rap": Path(os.environ.get("JARVIS_VOIX_RAP", Path.home() / "AIOS" / "jarvis" / "voix-hakim-rap.wav"))}
SEGMENTS_MAX = 16
BLANC_S = 0.06          # entre deux langues : une respiration, pas un trou


def reference_de(voix):
    """Le fichier de timbre d'une voix connue, s'il existe ; sinon None (la voix par défaut)."""
    f = VOIX.get(str(voix or ""))
    return f if f is not None and f.is_file() else None


def segments_valides(segments, langues, defaut="fr"):
    """[(texte, langue)] ; None si ce n'est pas une liste de morceaux. Une langue inconnue devient `defaut`."""
    if not isinstance(segments, list) or not segments:
        return None
    out = []
    for s in segments[:SEGMENTS_MAX]:
        if not isinstance(s, dict):
            continue
        t = str(s.get("texte") or "").strip()[:1500]
        if not t:
            continue
        lg = s.get("langue") if s.get("langue") in langues else defaut
        if out and out[-1][1] == lg:                 # deux morceaux de la même langue : un seul appel
            out[-1] = (f"{out[-1][0]} {t}", lg)
        else:
            out.append((t, lg))
    return out or None


def assembler(audios, sr, blanc_s=BLANC_S):
    """Les morceaux bout à bout (float32), un blanc de `blanc_s` entre deux."""
    l = [np.asarray(a, dtype=np.float32).reshape(-1) for a in audios if a is not None and len(a)]
    if not l:
        return np.zeros(int(0.05 * sr), dtype=np.float32)
    blanc = np.zeros(int(blanc_s * sr), dtype=np.float32)
    out = [l[0]]
    for a in l[1:]:
        out += [blanc, a]
    return np.concatenate(out)
