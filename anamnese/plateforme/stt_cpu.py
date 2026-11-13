"""L'écoute sans MLX (13/11) : faster-whisper sur le processeur, en int8. Le secours d'Azure sur un PC sans GPU (profil
« pc-sans-gpu ») : la même forme de réponse que jarvis/stt.py (texte, langue, ms, silence, mots, segments), les mêmes
amorces et le même filtre des inventions de Whisper. Le modèle (NAISSANCE_WHISPER, « small » par défaut : ~250 Mo, quelques
secondes par phrase sur un i7 de 4 cœurs) se télécharge à la première écoute dans le cache de Hugging Face.
Pas d'empreinte vocale ici (elle demande l'oreille des voix, éteinte dans ce profil)."""
import os
import sys
import time
from pathlib import Path

MODELE = os.environ.get("NAISSANCE_WHISPER", "small")
FILS = int(os.environ.get("NAISSANCE_WHISPER_FILS", str(max(1, min(4, os.cpu_count() or 2)))))
_modele = None


def _stt():
    jarvis = str(Path(__file__).resolve().parents[1] / "jarvis")
    if jarvis not in sys.path:
        sys.path.append(jarvis)
    import stt
    return stt


def charger_audio(fichier):
    """L'audio en 16 kHz mono (float32) par ffmpeg : decode_audio de faster-whisper passe par PyAV, dont les versions récentes
    ne prennent plus ses arguments (« metadata_errors », vu le 13/11 avec av 19 dans le conteneur d'essai)."""
    import shutil
    import subprocess
    import numpy as np
    ffmpeg = shutil.which("ffmpeg") or "/usr/bin/ffmpeg"
    r = subprocess.run([ffmpeg, "-nostdin", "-loglevel", "error", "-i", str(fichier), "-f", "f32le", "-ac", "1", "-ar", "16000", "-"],
                       capture_output=True, timeout=120, check=True)
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def disponible():
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def modele():
    global _modele
    if _modele is None:
        from faster_whisper import WhisperModel
        _modele = WhisperModel(MODELE, device="cpu", compute_type="int8", cpu_threads=FILS)
    return _modele


def langues(audio):
    """{langue: probabilité} pour le début de l'audio (la détection de faster-whisper)."""
    m = modele()
    if hasattr(m, "detect_language"):
        try:
            _l, _p, toutes = m.detect_language(audio)
            return dict(toutes)
        except Exception:
            pass
    _segs, info = m.transcribe(audio, language=None, beam_size=1, without_timestamps=True)
    return dict(getattr(info, "all_language_probs", None) or [(info.language, info.language_probability)])


def transcrire(fichier, langue=None, contexte="", voix=None, avec_temps=False, musique=False):
    stt = _stt()
    t0 = time.time()
    audio = charger_audio(fichier)
    probs = langues(audio)
    if not stt.parole_probable(probs):
        return {"texte": "", "langue": None, "ms": int((time.time() - t0) * 1000), "silence": True}
    langue = langue or stt.choisir_langue(probs)
    base = stt.AMORCES.get(langue, stt.AMORCE)
    amorce = base + (" " + contexte.strip()[-200:] if contexte and contexte.strip() else "")
    mots = bool(avec_temps or voix == "reconnaitre:mots")
    segs, info = modele().transcribe(audio, language=langue, initial_prompt=amorce, condition_on_previous_text=False,
                                     word_timestamps=mots, vad_filter=True, beam_size=1)
    segments = [{"text": s.text, "start": s.start, "end": s.end, "compression_ratio": s.compression_ratio,
                 "no_speech_prob": s.no_speech_prob,
                 "words": [{"word": w.word, "start": w.start, "end": w.end} for w in (s.words or [])]} for s in segs]
    texte = stt.filtrer_segments(segments or [{"text": ""}], base)
    sortie = {"texte": texte, "langue": info.language, "ms": int((time.time() - t0) * 1000), "moteur": f"faster-whisper {MODELE} (CPU)"}
    gardes = stt.segments_gardes(segments, base)
    if mots:
        sortie["mots"] = [[w["word"].strip(), round(float(w["start"]), 3), round(float(w["end"]), 3)]
                          for sg in gardes for w in sg["words"] if (w.get("word") or "").strip()]
    if avec_temps:
        sortie["segments"] = [{"debut": float(sg["start"]), "fin": float(sg["end"]), "texte": (sg["text"] or "").strip(),
                               "mots": [[w["word"].strip(), float(w["start"]), float(w["end"])] for w in sg["words"]
                                        if (w.get("word") or "").strip()]} for sg in gardes]
    return sortie
