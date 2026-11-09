"""(03/11, Ahmed : « ta transcription doit se faire mot à mot ; il prend le premier mot, puis en parallèle le deuxième ;
ça doit aussi driver son attention » ; « Whisper pour la voix ») l'oreille VIVE : un petit Whisper (small, ~0,4 s pour 6 s
de voix sur le M4), à part de l'oreille principale (large-v3-turbo, qui partage son processus avec sa voix), transcrit en
continu ce que papa est EN TRAIN de dire. Ses mots sont un aperçu : la page les montre et son oreille les suit ; le texte
qui part à Hakim reste celui de la grande oreille.

Un processus qui reste en vie : une ligne JSON par demande sur l'entrée {id, fichier, langue, contexte}, une ligne par
réponse {id, texte, ms} ou {id, erreur}.

(03/11, micro ouvert) {id, op: "famille", fichier, parole, voix} : 3 s d'ambiance rangées dans ses familles de sons
(sons_familles.py), par ce que l'encodeur de ce même Whisper en comprend → {id, famille, nouvelle, fois} ou {id, ecoute}.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import stt  # noqa: E402  (l'amorce et le filtre des inventions, les mêmes que la grande oreille)

MODELE = os.environ.get("JARVIS_WHISPER_VIF", "mlx-community/whisper-small-mlx")
# (09/11, mesuré à 21:15 : 7,1 Go d'« IOAccelerator » sur 7,4 Go, 4 918 régions, pour un Whisper small de ~0,5 Go ; le Mac swappait à
# 16,8/17,4 Go) les tampons Metal que MLX GARDE en cache après chaque demande, comme voix_serveur le 24/10 : le cache est borné, et
# vidé dès qu'aucune demande n'attend (jamais entre deux morceaux de papa qui se suivent). Le modèle chargé reste.
CACHE_MAX_OCTETS = int(os.environ.get("JARVIS_VIF_CACHE_MO", "256")) * 1024 * 1024


def borner_cache():
    try:
        import mlx.core as mx
        mx.set_cache_limit(CACHE_MAX_OCTETS)
    except Exception:  # noqa: BLE001
        pass


def vider_cache_si_libre(entree=sys.stdin):
    """Vide le cache Metal quand rien n'attend sur l'entrée (le vider entre deux demandes collées les ralentirait)."""
    try:
        import select
        if select.select([entree], [], [], 0)[0]:
            return False
    except Exception:  # noqa: BLE001  (une entrée sans descripteur : on vide)
        pass
    try:
        import mlx.core as mx
        mx.clear_cache()
        return True
    except Exception:  # noqa: BLE001
        return False


def transcrire(mlx_whisper, fichier, langue=None, contexte="", avec_temps=False):
    """(06/11) avec_temps : le temps de chaque mot ([mot, début, fin] en secondes du fichier), pour caler la voix séparée sur le fil."""
    t0 = time.time()
    base = stt.AMORCES.get(langue or "fr", stt.AMORCE)
    amorce = base + (" " + contexte.strip()[-200:] if contexte and contexte.strip() else "")
    r = mlx_whisper.transcribe(fichier, path_or_hf_repo=MODELE, initial_prompt=amorce, language=langue or None,
                               condition_on_previous_text=False, word_timestamps=bool(avec_temps))
    if not langue and r.get("language") not in stt.LANGUES_PERMISES:     # une langue qui n'est pas la sienne : en français
        r = mlx_whisper.transcribe(fichier, path_or_hf_repo=MODELE, initial_prompt=amorce, language="fr",
                                   condition_on_previous_text=False, word_timestamps=bool(avec_temps))
    texte = stt.filtrer_segments(r.get("segments") or [{"text": r.get("text")}], base)
    sortie = {"texte": texte, "langue": r.get("language"), "ms": int((time.time() - t0) * 1000)}
    if avec_temps:
        sortie["mots"] = [[w["word"].strip(), round(float(w["start"]), 3), round(float(w["end"]), 3)]
                          for sg in stt.segments_gardes(r.get("segments") or [], base) for w in (sg.get("words") or [])
                          if (w.get("word") or "").strip()]
    return sortie


def forme(fichier):
    """Ce que l'encodeur comprend de 3 s de son : la moyenne et l'écart de ses sorties dans le temps (2 × 768 nombres)."""
    import mlx.core as mx
    import numpy as np
    from mlx_whisper.audio import N_FRAMES, load_audio, log_mel_spectrogram, pad_or_trim
    from mlx_whisper.transcribe import ModelHolder
    modele = ModelHolder.get_model(MODELE, mx.float16)
    mel = log_mel_spectrogram(load_audio(fichier), n_mels=modele.dims.n_mels)
    x = modele.encoder(pad_or_trim(mel, N_FRAMES, axis=-2).astype(mx.float16)[None])[0]
    v = np.array(x[: max(1, mel.shape[0] // 2)].astype(mx.float32))
    return np.concatenate([v.mean(axis=0), v.std(axis=0)])


def famille(fichier, parole=None, voix=0):
    import sons_familles
    t0 = time.time()
    r = sons_familles.entendre(forme(fichier), parole=parole, voix=voix)
    return {**(r or {"ecoute": True}), "ms": int((time.time() - t0) * 1000)}


def main():
    import mlx_whisper
    import numpy as np
    borner_cache()
    mlx_whisper.transcribe(np.zeros(16000, dtype=np.float32), path_or_hf_repo=MODELE, language="fr")   # chargé d'avance
    vider_cache_si_libre()
    print(json.dumps({"pret": True, "modele": MODELE}), flush=True)
    for ligne in sys.stdin:
        try:
            d = json.loads(ligne)
        except ValueError:
            continue
        try:
            if d.get("op") == "qui":
                # (06/11, Ahmed : « il entend sa propre voix et ça le perturbe ») un morceau que l'oreille Azure a transcrit (sans dire qui
                # parlait) : est-ce SA voix ? (empreinte_vocale.qui_parle, sur le processeur, ~0,1 s par fenêtre de 1,5 s)
                import empreinte_vocale
                import mlx_whisper.audio
                import numpy as np
                t0 = time.time()
                sortie = {**empreinte_vocale.qui_parle(np.array(mlx_whisper.audio.load_audio(str(d["fichier"])), dtype=np.float32)),
                          "ms": int((time.time() - t0) * 1000)}
            elif d.get("op") == "famille":
                sortie = famille(str(d["fichier"]), bool(d.get("parole")), int(d.get("voix") or 0))
            else:
                sortie = transcrire(mlx_whisper, str(d["fichier"]), d.get("langue") or None, str(d.get("contexte") or ""),
                                    bool(d.get("avec_temps")))
        except Exception as e:  # noqa: BLE001  (une demande ratée ne tue pas l'oreille)
            sortie = {"erreur": str(e)[:200]}
        print(json.dumps({"id": d.get("id"), **sortie}, ensure_ascii=False), flush=True)
        vider_cache_si_libre()


if __name__ == "__main__":
    main()
