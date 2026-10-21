"""Transcription locale pour Jarvis (feuille de route, étape 5) : mlx-whisper, hors ligne, gratuit.

Usage : stt.py <fichier audio> [langue]  → une ligne JSON : {"texte", "langue", "ms"} ou {"erreur"}.
Le décodage passe par ffmpeg (webm/opus de Chrome, mp4 de Safari). L'amorce oriente Whisper vers
le mélange français-arabe d'Ahmed (étape 5 bis) : expressions courantes et noms des projets.
Code de sortie : 0 réussi, 2 mlx-whisper absent (le cockpit propose alors la reconnaissance du
navigateur), 1 autre échec.
"""
import json
import os
import re
import sys
import time

MODELE = os.environ.get("JARVIS_WHISPER", "mlx-community/whisper-large-v3-turbo")
AMORCE = ("Salam alaykoum frérot. Wa alaykoum salam. Inchallah, hamdoulillah, wallah, machallah, "
          "bismillah. On parle d'Anamnèse, de Jarvis, du robot IA et de Claude Code.")
# l'amorce de la langue détectée : en arabe, l'amorce française (arabizi) faisait écrire « Kiva halka ya akhi »
# au lieu de « كيف حالك يا أخي » (vu le 2026-10-18)
AMORCES = {"fr": AMORCE,
           "ar": "السلام عليكم يا أخي. وعليكم السلام. إن شاء الله، الحمد لله، ما شاء الله. نتكلم عن أنامنيز وجارفيس.",
           "en": "Hello brother. We talk about Anamnèse, Jarvis, the AI robot and Claude Code."}


# En automatique, la langue est choisie PARMI celles d'Ahmed (2026-10-18 : « parfois le détecteur détecte
# l'islandais ») : Whisper donne ses probabilités pour ~100 langues, on garde la meilleure des trois.
LANGUES_PERMISES = tuple(x.strip() for x in os.environ.get("JARVIS_LANGUES", "fr,ar,en").split(",") if x.strip())


def choisir_langue(probs, permises=LANGUES_PERMISES):
    """La plus probable des langues permises ; aucune n'a de probabilité : la première (le français)."""
    meilleure = max(permises, key=lambda lg: probs.get(lg, 0.0))
    return meilleure if probs.get(meilleure, 0.0) > 0 else permises[0]


# ---- les inventions de Whisper (relevées dans le fil de Hakim les 18-19/10) ----
# - un bruit de moteur détecté « anglais » rendait l'AMORCE anglaise mot pour mot (« We talk about Anamnèse,
#   Jarvis… », no_speech_prob 0,0 : le score de silence de Whisper n'y voit rien) — reproduit le 2026-10-19 ;
# - des boucles (« de temps de temps… », « huhuhu ») ; « Thank you. » sur une moto ; du texte sur du silence.
SEUIL_PAROLE = 0.4          # parole réelle : la langue est sûre à 0,99 ; silence : 0,30 ; moteur : 0,64 (mesuré)
FANTOMES = re.compile(r"^(thank you( (so much|very much|for watching))?|thanks( for watching)?|you|"
                      r"merci d'avoir regardé|sous-titres.*|sous-titrage.*|amara\.org.*)$", re.I)


def _mots(texte):
    return re.findall(r"[\w']+", (texte or "").lower())


def parole_probable(probs, permises=LANGUES_PERMISES):
    """Y a-t-il de la parole dans une langue d'Ahmed ? (d'après la détection de langue de Whisper)"""
    return max((probs.get(lg, 0.0) for lg in permises), default=0.0) >= SEUIL_PAROLE


# La phrase « des projets » de chaque amorce : ce qu'Ahmed ne dit jamais tel quel (au contraire des
# salutations, qui sont aussi dans l'amorce et qu'il dit tout le temps — relecture Opus du 2026-10-19).
PHRASES_PROJETS = ("On parle d'Anamnèse, de Jarvis, du robot IA et de Claude Code.",
                   "We talk about Anamnèse, Jarvis, the AI robot and Claude Code.", "نتكلم عن أنامنيز وجارفيس.")


def _bloc(a, b):
    import difflib
    return difflib.SequenceMatcher(None, a, b, autojunk=False).find_longest_match(0, len(a), 0, len(b)).size


def _echo_de_l_amorce(texte, amorce):
    """Un écho : l'essentiel du segment recopie la phrase des projets (≥ 3 mots d'affilée), ou un long passage
    de l'amorce (≥ 8 mots d'affilée). Une salutation courte n'en est jamais un."""
    mots = _mots(texte)
    if len(mots) < 3:
        return False
    if any(_bloc(mots, _mots(p)) >= max(3, int(0.7 * len(mots))) for p in PHRASES_PROJETS):
        return True
    return _bloc(mots, _mots(amorce)) >= 8


def _boucle(texte, compression):
    if compression and compression > 2.2:
        return True
    mots = _mots(texte)
    for n in (1, 2, 3):                                           # un même groupe de 1 à 3 mots répété 4 fois de suite
        for i in range(0, max(0, len(mots) - 4 * n + 1)):
            if all(mots[i + k * n:i + (k + 1) * n] == mots[i:i + n] for k in range(1, 4)):
                return True
    return bool(re.search(r"(\w{1,3})\1{5,}", (texte or "").lower()))   # « huhuhuhuhu »


def filtrer_segments(segments, amorce):
    """Le texte des segments crédibles : sans écho de l'amorce, sans boucle, sans formule fantôme."""
    return " ".join((sg.get("text") or "").strip() for sg in segments_gardes(segments, amorce)).strip()


def segments_gardes(segments, amorce):
    """Les segments crédibles eux-mêmes (avec leurs instants : l'empreinte vocale les attribue à une voix)."""
    gardes = []
    for sg in segments or []:
        t = (sg.get("text") or "").strip()
        if not t or _echo_de_l_amorce(t, amorce) or _boucle(t, sg.get("compression_ratio")):
            continue
        if FANTOMES.match(t.strip(" .!?…")):
            continue
        if sg.get("no_speech_prob", 0) > 0.6 and sg.get("avg_logprob", 0) < -0.8:
            continue
        gardes.append(sg)
    return gardes


def disponible():
    try:
        import mlx_whisper  # noqa: F401
    except ImportError:
        return False
    return True


def transcrire(fichier, langue=None, contexte="", voix=None):
    """contexte : ce qui a déjà été transcrit de la même phrase (transcription en continu) ; il guide
    Whisper sur la suite (noms, orthographe, langue). voix : « reconnaitre » (l'empreinte vocale d'Ahmed, un
    indice) ou « apprendre » (Ahmed l'a demandé) ; None : rien."""
    import mlx_whisper
    t0 = time.time()
    audio = mlx_whisper.audio.load_audio(fichier)              # lu une fois : pour la langue et pour le texte
    # même quand la langue est imposée, le silence et le bruit sont reconnus (relecture Opus du lot C)
    detectee, probs = detecter_langue(audio, avec_probs=True)
    if not parole_probable(probs):                               # du silence, du bruit : rien à transcrire
        return {"texte": "", "langue": None, "ms": int((time.time() - t0) * 1000), "silence": True}
    langue = langue or detectee
    base = AMORCES.get(langue, AMORCE)
    amorce = base + (" " + contexte.strip()[-200:] if contexte and contexte.strip() else "")
    exacte = os.environ.get("JARVIS_PROSODIE_EXACTE") == "1"     # le temps de chaque mot : ~1 s de plus par transcription
    r = mlx_whisper.transcribe(audio, path_or_hf_repo=MODELE, initial_prompt=amorce, language=langue,
                               condition_on_previous_text=False, word_timestamps=exacte)
    texte = filtrer_segments(r.get("segments") or [{"text": r.get("text")}], base)
    sortie = {"texte": texte, "langue": r.get("language"), "ms": int((time.time() - t0) * 1000)}
    if voix and texte:
        try:
            import numpy as np
            import empreinte_vocale
            brut = np.array(audio, dtype=np.float32)
            duree = round(len(brut) / 16000, 1)
            pas_apprise = empreinte_vocale.etat()["echantillons"] < 2
            if str(voix).startswith("apprendre"):
                # (2026-10-20, retour d'Ahmed après la calibration) : pendant l'apprentissage, sa voix est AUSSI reconnue
                # (le score avant d'apprendre) — avant, il n'y avait plus aucun score tant que l'apprentissage durait
                v = empreinte_vocale.reconnaitre(brut)
                sortie["voix"] = {**(v or {"raison": "pas_apprise" if pas_apprise else "court"}), "duree_s": duree}
                registre = str(voix).split(":", 1)[1] if ":" in str(voix) else None   # calibration guidée
                if len(brut) >= 3 * 16000:                                      # une vraie phrase, pas un bout
                    n = empreinte_vocale.apprendre(brut, registre=registre, guide=bool(registre))
                    if n:
                        sortie["voix"]["appris"] = n
                else:
                    sortie["voix"]["pas_appris"] = "moins de 3 s d'audio"
            elif voix == "reconnaitre":
                # la prosodie mot par mot (2026-10-20) : les mots appuyés, le contour de fin — des indices
                try:
                    import prosodie
                    gardes = segments_gardes(r.get("segments") or [], base)
                    mots = ([(w["word"].strip(" ,.?!;:"), float(w["start"]), float(w["end"])) for sg in gardes
                             for w in (sg.get("words") or []) if w.get("word", "").strip(" ,.?!;:")] if exacte else None)
                    p = prosodie.analyser(brut, gardes, mots=mots) if len(brut) >= 1.5 * 16000 else None
                    if p:
                        sortie["prosodie"] = p
                except Exception as e:
                    print(f"[voix] prosodie indisponible : {type(e).__name__}: {e}", file=sys.stderr)
                v = empreinte_vocale.reconnaitre(brut)
                sortie["voix"] = {**(v or {"raison": "pas_apprise" if pas_apprise else "court"}), "duree_s": duree}
                # plusieurs voix dans le même message : le texte est étiqueté par voix
                etiquete, resume = empreinte_vocale.etiqueter(brut, segments_gardes(r.get("segments") or [], base),
                                                            nouveau_tour=not (contexte and contexte.strip()))
                if etiquete and resume and (resume["autres"] or resume["plusieurs"]):
                    sortie["texte"] = etiquete
                    sortie["voix"] = {**(sortie.get("voix") or {}), "locuteurs": resume["voix"],
                                      "verdict": "plusieurs" if resume["plusieurs"] and resume["ahmed"]
                                      else ("autre" if not resume["ahmed"] else (sortie.get("voix") or {}).get("verdict", "ahmed"))}
        except Exception as e:                                           # jamais bloquant pour la transcription
            print(f"[voix] empreinte indisponible : {type(e).__name__}: {e}", file=sys.stderr)
    return sortie


def detecter_langue(audio, avec_probs=False):
    """La langue de l'audio parmi LANGUES_PERMISES (le même calcul que Whisper, restreint)."""
    import mlx.core as mx
    from mlx_whisper.audio import N_FRAMES, N_SAMPLES, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.transcribe import ModelHolder
    modele = ModelHolder.get_model(MODELE, mx.float16)
    mel = log_mel_spectrogram(audio, n_mels=modele.dims.n_mels, padding=N_SAMPLES)
    _, probs = modele.detect_language(pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16))
    return (choisir_langue(probs), probs) if avec_probs else choisir_langue(probs)


def main(argv):
    if len(argv) >= 2 and argv[1] == "--etat":
        import importlib.util
        print(json.dumps({"disponible": disponible(), "modele": MODELE,
                          "tts": importlib.util.find_spec("mlx_audio") is not None}))
        return 0
    if len(argv) < 2:
        print(json.dumps({"erreur": "usage : stt.py <fichier audio> [langue]"}))
        return 1
    if not disponible():
        print(json.dumps({"erreur": "mlx-whisper n'est pas installé"}))
        return 2
    try:
        print(json.dumps(transcrire(argv[1], argv[2] if len(argv) > 2 else None), ensure_ascii=False))
        return 0
    except Exception as e:  # ffmpeg absent, fichier illisible, modèle introuvable…
        print(json.dumps({"erreur": f"{type(e).__name__}: {e}"[:300]}, ensure_ascii=False))
        return 1


if __name__ == "__main__":
    sys.exit(main(sys.argv))
